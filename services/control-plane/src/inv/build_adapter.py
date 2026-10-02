"""Admitted build dispatch boundary for a future rootless BuildKit transport.

The transport never receives a raw ``BuildPlan``.  It receives an internal
capability only after ROOF policy and the live resource lease have both been
checked.  Network or daemon calls happen outside database transactions.  A
second transaction repeats the live checks before a receipt can become
Evidence.

This module does not implement a BuildKit daemon, persist Evidence, or release
the kernel lease.  Those operations require an authenticated physical cleanup
receipt and remain outside this adapter boundary.  Its one-shot claim is
deliberately fail-closed: a crash after claim commit requires operator
reconciliation and never permits an automatic second dispatch.

Only the leased resource Node is checked here.  The provider observation does
not prove the builder process location, drain state, or health, so a public
route or concrete transport must remain disconnected until that measured
binding exists.  Pre-admission denials likewise have no persisted Evidence at
this private boundary; claimed dispatches and quarantines emit redacted outbox
audit events instead.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from psycopg.types.json import Jsonb

from .build_governance import (
    BuildProviderObservation,
    authorize_build,
    finalize_build,
)
from .contracts import validate_contract
from .errors import DomainError
from .leases import fence, lock_resources, lock_run
from .policy import action_digest

NODE_FRESHNESS_SECONDS = 15


def _audit_event(conn, tenant_id: str, run_id: str, event_type: str, payload: dict) -> None:
    """Write one redacted build boundary event without importing the Run service."""

    conn.execute(
        """INSERT INTO inv.outbox(tenant_id,run_id,event_id,event_type,payload)
        VALUES (%s,%s,%s,%s,%s)""",
        (tenant_id, run_id, uuid4(), event_type, Jsonb(payload)),
    )


@dataclass(frozen=True)
class _AdmittedBuild:
    """Capability created only after the database admission transaction."""

    request: dict
    plan: dict
    decision: dict
    policy_version: str
    run_id: str
    evidence_id: str
    actor_id: str
    leased_node_id: str
    roof_binding_digest: str
    binding_digest: str


@dataclass(frozen=True)
class BuildAdapterResult:
    receipt: dict
    evidence: dict


class BuildTransport(Protocol):
    """Private rootless builder boundary; implementations are trusted adapters."""

    def observe(self, plan: dict) -> BuildProviderObservation:
        """Return a fresh measured builder observation without dispatching."""

    def dispatch(self, admitted: _AdmittedBuild) -> dict:
        """Execute only an admitted capability and return a strict receipt."""

    def cancel_and_quarantine(self, admitted: _AdmittedBuild, reason_code: str) -> None:
        """Stop any possible side effect and quarantine unverified state."""


def _database_now(conn) -> datetime:
    row = conn.execute("SELECT clock_timestamp() AS now").fetchone()
    if not row or not isinstance(row.get("now"), datetime) or row["now"].tzinfo is None:
        raise DomainError("SYS-0001", "Database clock is unavailable", 503)
    return row["now"]


def _lock_live_build_authority(
    conn,
    request: dict,
    plan: dict,
    run_id: str,
    *,
    database_recovery_epoch: str,
    now: datetime,
) -> str:
    """Lock Run -> Node -> Resource -> lease and reject stale dispatch authority."""

    run = lock_run(conn, run_id, request["projectId"])
    if run["state"] not in {"scheduled", "running", "verifying"}:
        raise DomainError("RES-0005", "Run cannot dispatch a build in its current state")
    resource_id = plan["lease"]["resourceId"]
    resources = lock_resources(conn, [resource_id])
    resource = resources[resource_id]
    lease = conn.execute(
        """SELECT * FROM inv.resource_leases
        WHERE lease_id=%s AND run_id=%s AND resource_id=%s FOR UPDATE""",
        (plan["lease"]["leaseId"], run_id, resource_id),
    ).fetchone()
    if (
        not lease
        or str(lease["tenant_id"]) != request["tenantId"]
        or lease["project_id"] != request["projectId"]
        or lease["released_at"] is not None
        or lease["expires_at"] <= now
        or str(lease["recovery_epoch"]) != database_recovery_epoch
        or fence(lease) != plan["lease"]["fencingToken"]
        or lease["expires_at"]
        != datetime.fromisoformat(plan["lease"]["expiresAt"].replace("Z", "+00:00"))
    ):
        raise DomainError("LEASE-0002", "Build allocation is stale or differs", 409)

    node = conn.execute(
        """SELECT status,recovery_epoch,heartbeat_at,clock_skew_seconds
        FROM inv.nodes WHERE node_id=%s""",
        (resource["node_id"],),
    ).fetchone()
    if (
        not node
        or node["status"] != "online"
        or str(node["recovery_epoch"]) != database_recovery_epoch
    ):
        raise DomainError("NODE-0033", "Build node is not current and online", 409)
    heartbeat = node["heartbeat_at"]
    skew = node["clock_skew_seconds"]
    try:
        skew_is_current = (
            skew is not None
            and (not hasattr(skew, "is_finite") or skew.is_finite())
            and abs(skew) <= 5
        )
    except (ArithmeticError, TypeError, ValueError):
        skew_is_current = False
    if (
        not isinstance(heartbeat, datetime)
        or heartbeat.tzinfo is None
        or heartbeat > now
        or heartbeat < now - timedelta(seconds=NODE_FRESHNESS_SECONDS)
        or not skew_is_current
    ):
        raise DomainError("RES-0003", "Build node observation is stale", 409)
    return str(resource["node_id"])


def _claim_build_dispatch(
    conn,
    request: dict,
    plan: dict,
    decision: dict,
    run_id: str,
    binding_digest: str,
) -> None:
    """Atomically consume one policy decision for exactly one dispatch.

    The key is derived from ``decisionId`` alone because PolicyDecision has no
    Run identity.  Run, lease, Node, and fence remain in ``binding_digest`` so
    any attempted cross-run or next-lease reuse conflicts with different
    content.  A committed claim is never replayed, even when its digest is
    identical.  That makes an ambiguous crash fail closed until an operator
    reconciles the external builder state.
    """

    claim_key = action_digest({"decisionId": decision["decisionId"]})
    inserted = conn.execute(
        """INSERT INTO inv.idempotency(
        tenant_id,project_id,operation,key,request_hash,response
        ) VALUES (%s,%s,'build.dispatch',%s,%s,%s)
        ON CONFLICT DO NOTHING RETURNING key""",
        (
            request["tenantId"],
            request["projectId"],
            claim_key,
            binding_digest,
            Jsonb(
                {
                    "state": "claimed",
                    "bindingDigest": binding_digest,
                    "decisionId": decision["decisionId"],
                }
            ),
        ),
    ).fetchone()
    if not inserted:
        prior = conn.execute(
            """SELECT request_hash FROM inv.idempotency
            WHERE project_id=%s AND operation='build.dispatch' AND key=%s FOR UPDATE""",
            (request["projectId"], claim_key),
        ).fetchone()
        message = (
            "Build dispatch identity already has different content"
            if prior and prior["request_hash"] != binding_digest
            else "Build dispatch identity is already consumed"
        )
        raise DomainError("IDEM-0001", message, 409)
    _audit_event(
        conn,
        request["tenantId"],
        run_id,
        "inv.build.dispatch_claimed",
        {
            "bindingDigest": binding_digest,
            "resourceId": plan["lease"]["resourceId"],
            "leaseId": plan["lease"]["leaseId"],
        },
    )


def _record_build_quarantine(
    database, request: dict, admitted: _AdmittedBuild, reason_code: str
) -> None:
    """Persist a redacted post-dispatch quarantine audit after cleanup."""

    with database.transaction(request["tenantId"]) as conn:
        lock_run(conn, admitted.run_id, request["projectId"])
        _audit_event(
            conn,
            request["tenantId"],
            admitted.run_id,
            "inv.build.dispatch_quarantined",
            {
                "bindingDigest": admitted.binding_digest,
                "leasedNodeId": admitted.leased_node_id,
                "reasonCode": reason_code,
            },
        )


def _reason_code(error: BaseException) -> str:
    return error.code if isinstance(error, DomainError) else "SYS-0001"


class BuildExecutionAdapter:
    """Sequence two short admission transactions around one external dispatch."""

    def __init__(self, database, transport: BuildTransport):
        self.db = database
        self._transport = transport

    def execute(
        self,
        principal,
        request: dict,
        plan: dict,
        decision: dict,
        *,
        policy_version: str,
        run_id: str,
        evidence_id: str,
        actor_id: str,
    ) -> BuildAdapterResult:
        """Dispatch one admitted build and return unpersisted strict Evidence."""

        validate_contract("BuildRequest", request)
        validate_contract("BuildPlan", plan)
        validate_contract("PolicyDecision", decision)
        frozen_request = deepcopy(request)
        frozen_plan = deepcopy(plan)
        frozen_decision = deepcopy(decision)

        provider = self._transport.observe(deepcopy(frozen_plan))
        with self.db.transaction(frozen_request["tenantId"]) as conn:
            now = _database_now(conn)
            binding = authorize_build(
                conn,
                principal,
                frozen_request,
                frozen_plan,
                frozen_decision,
                policy_version=policy_version,
                provider=provider,
                now=now,
            )
            leased_node_id = _lock_live_build_authority(
                conn,
                frozen_request,
                frozen_plan,
                run_id,
                database_recovery_epoch=self.db.recovery_epoch,
                now=now,
            )

            dispatch_binding = {
                "roofBindingDigest": binding["bindingDigest"],
                "runId": run_id,
                "leasedNodeId": leased_node_id,
                "leaseId": frozen_plan["lease"]["leaseId"],
                "resourceId": frozen_plan["lease"]["resourceId"],
                "fencingToken": frozen_plan["lease"]["fencingToken"],
            }
            binding_digest = action_digest(dispatch_binding)
            _claim_build_dispatch(
                conn,
                frozen_request,
                frozen_plan,
                frozen_decision,
                run_id,
                binding_digest,
            )

        admitted = _AdmittedBuild(
            request=deepcopy(frozen_request),
            plan=deepcopy(frozen_plan),
            decision=deepcopy(frozen_decision),
            policy_version=policy_version,
            run_id=run_id,
            evidence_id=evidence_id,
            actor_id=actor_id,
            leased_node_id=leased_node_id,
            roof_binding_digest=binding["bindingDigest"],
            binding_digest=binding_digest,
        )

        try:
            receipt = self._transport.dispatch(admitted)
            final_provider = self._transport.observe(deepcopy(frozen_plan))
            with self.db.transaction(frozen_request["tenantId"]) as conn:
                now = _database_now(conn)
                final_leased_node_id = _lock_live_build_authority(
                    conn,
                    frozen_request,
                    frozen_plan,
                    run_id,
                    database_recovery_epoch=self.db.recovery_epoch,
                    now=now,
                )
                if final_leased_node_id != admitted.leased_node_id:
                    raise DomainError("NODE-0033", "Build node authority changed", 409)
                evidence = finalize_build(
                    conn,
                    principal,
                    frozen_request,
                    frozen_plan,
                    frozen_decision,
                    receipt,
                    policy_version=policy_version,
                    provider=final_provider,
                    now=now,
                    admitted_binding_digest=admitted.roof_binding_digest,
                    run_id=run_id,
                    evidence_id=evidence_id,
                    actor_id=actor_id,
                )
            return BuildAdapterResult(receipt=receipt, evidence=evidence)
        except BaseException as error:
            try:
                reason_code = _reason_code(error)
                self._transport.cancel_and_quarantine(admitted, reason_code)
                _record_build_quarantine(self.db, frozen_request, admitted, reason_code)
            except BaseException as cleanup_error:
                raise DomainError(
                    "VERIFY-0022",
                    "Build cancellation and quarantine are not verified",
                    409,
                ) from cleanup_error
            raise
