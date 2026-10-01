"""Admitted build dispatch boundary for a future rootless BuildKit transport.

The transport never receives a raw ``BuildPlan``.  It receives an internal
capability only after ROOF policy and the live resource lease have both been
checked.  Network or daemon calls happen outside database transactions.  A
second transaction repeats the live checks before a receipt can become
Evidence.

This module does not implement a BuildKit daemon, persist Evidence, or release
the kernel lease.  Those operations require an authenticated physical cleanup
receipt and remain outside this adapter boundary.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from .build_governance import (
    BuildProviderObservation,
    authorize_build,
    finalize_build,
)
from .contracts import validate_contract
from .errors import DomainError
from .leases import fence, lock_resources, lock_run


NODE_FRESHNESS_SECONDS = 15


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
) -> None:
    """Lock Run -> Node -> Resource -> lease and reject stale dispatch authority."""

    lock_run(conn, run_id, request["projectId"])
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
    if (
        node["heartbeat_at"] is None
        or node["heartbeat_at"] > now
        or node["heartbeat_at"] < now - timedelta(seconds=NODE_FRESHNESS_SECONDS)
        or abs(node["clock_skew_seconds"]) > 5
    ):
        raise DomainError("RES-0003", "Build node observation is stale", 409)


def _reason_code(error: Exception) -> str:
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
            _lock_live_build_authority(
                conn,
                frozen_request,
                frozen_plan,
                run_id,
                database_recovery_epoch=self.db.recovery_epoch,
                now=now,
            )

        admitted = _AdmittedBuild(
            request=deepcopy(frozen_request),
            plan=deepcopy(frozen_plan),
            decision=deepcopy(frozen_decision),
            policy_version=policy_version,
            run_id=run_id,
            evidence_id=evidence_id,
            actor_id=actor_id,
            binding_digest=binding["bindingDigest"],
        )

        attempted = False
        try:
            attempted = True
            receipt = self._transport.dispatch(admitted)
            final_provider = self._transport.observe(deepcopy(frozen_plan))
            with self.db.transaction(frozen_request["tenantId"]) as conn:
                now = _database_now(conn)
                _lock_live_build_authority(
                    conn,
                    frozen_request,
                    frozen_plan,
                    run_id,
                    database_recovery_epoch=self.db.recovery_epoch,
                    now=now,
                )
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
                    admitted_binding_digest=admitted.binding_digest,
                    run_id=run_id,
                    evidence_id=evidence_id,
                    actor_id=actor_id,
                )
            return BuildAdapterResult(receipt=receipt, evidence=evidence)
        except Exception as error:
            if attempted:
                try:
                    self._transport.cancel_and_quarantine(admitted, _reason_code(error))
                except Exception as cleanup_error:
                    raise DomainError(
                        "VERIFY-0022",
                        "Build cancellation and quarantine are not verified",
                        409,
                    ) from cleanup_error
            raise
