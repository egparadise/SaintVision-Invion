"""Internal product caller for the admitted rootless BuildKit path (S08-BE).

This is the consumer ``build_adapter`` has been waiting for.  It is deliberately
internal: there is no public build route, and the caller never synthesises a
``BuildRequest``, ``BuildPlan`` or ``PolicyDecision``.  It receives a committed Run,
its policy decision and its live lease, asks the adapter to dispatch exactly once,
and then commits every durable consequence of that dispatch in **one** transaction.

What this module owns, per the card 211 contract decision:

* the authority comparison for the two node-agent receipts -- the provider health
  receipt and the physical cleanup receipt -- which means ``nodeId == leasedNodeId``
  and a three-way recovery-epoch agreement, not a shape check;
* the atomic commit of Evidence persistence, kernel lease release and the
  ``inv.build.dispatch_completed`` outbox event.  Either all four land or none do:
  a release without Evidence is a lease nobody can account for, and Evidence
  without a release is a resource nobody can reclaim.

What it does **not** own: collecting the receipts or validating their low-level
shape (``buildkit_transport``), and the strict schemas of
``BuildProviderHealthReceipt``/``BuildPhysicalCleanupReceipt``/
``BuildAuditEvent.event = dispatch_completed``, which a separate contract PR fixes.
This module reads the field names that decision already fixed and compares them; it
does not decide what the field set is.  Until that contract lands there is no
``validate_contract`` call here, and the product enable setting is deliberately
absent from the product configuration.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import datetime as dt
import os
import re
from typing import Any, Mapping
from uuid import uuid4

from psycopg.types.json import Jsonb

from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest

#: Product dispatch is enabled by exactly this value and nothing else.  The CI
#: reference transport keeps its own ``INV_BUILDKIT_REFERENCE_ENABLED``; reusing that
#: name here would let a reference measurement turn into product execution.  This name
#: is **not** added to the product configuration object: the contract defers that until
#: the authenticated receipts, the isolation refusal, the epoch agreement and this
#: transaction are all implemented, tested and measured at an exact head.
PRODUCT_ENABLE_SETTING = "INV_BUILDKIT_PRODUCT_ENABLED"
PRODUCT_ENABLE_VALUE = "1"

#: Isolation values the hosted CI reference lane is allowed to record for itself.  A
#: product dispatch that accepted them would be building without the isolation whose
#: absence they describe, so they are refused here by name.
CI_REFERENCE_ISOLATION = frozenset({"unavailable-ci-reference", "unconfined-ci-reference"})

HEALTH_SCHEMA = "build-provider-health-receipt:1"
CLEANUP_SCHEMA = "build-physical-cleanup-receipt:1"
WRITER_KIND = "node-agent"
DAEMON_COMM = "buildkitd"
COMPLETED_EVENT = "inv.build.dispatch_completed"
PARTIAL_EXPORT_DISPOSITIONS = frozenset({"quarantined", "purged"})
CACHE_DISPOSITIONS = frozenset({"retained", "quarantined", "purged"})

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: The daemon identity fields that must be identical before and after the dispatch.
#: ``comm`` is included because a rootlesskit process answering in buildkitd's place
#: would otherwise satisfy a pid-only comparison.
DAEMON_IDENTITY_FIELDS = ("pid", "processUid", "processStartTicks", "comm")

#: A transport attribute the product path requires to be ``True``.  F-R4 made the service
#: record a reconciliation marker through the transport when a dispatch loses the commit, but
#: the production collector's ``quarantine_node`` only raises: nothing durable is written, so
#: the race loser would consume its one-shot decision claim with no marker anywhere (#312 N2).
#: Absent or false means the capability is not connected, and a dispatch that could not be
#: reconciled does not start.
QUARANTINE_CAPABILITY = "records_durable_quarantine"

#: How old a node-agent health observation may be, measured against the database clock.
#: The adapter checks its own provider observation with the same window; this is a
#: different observation by a different writer and needs its own check (#312 F-R1).
HEALTH_FRESHNESS_SECONDS = 15

#: The observations ``BuildCleanupReceipt`` repeats from the physical receipt.  Two cleanup
#: receipts that disagree about the same fact must not release a lease, so they are
#: compared exactly rather than trusted separately (#312 F-R2).  ``leaseReleased`` is not
#: here: it is proven by the conditional UPDATE, never by a caller's statement.
DUPLICATED_CLEANUP_OBSERVATIONS = (
    "cacheDisposition", "builderClaimReleased", "cgroupRemoved", "verifiedAt",
)


@dataclass(frozen=True)
class BuildExecutionResult:
    """What the caller returns once everything durable has committed."""

    evidence_id: str
    evidence_digest: str
    lease_released: bool
    cleanup_verified: bool


def canonical_digest(document: Mapping[str, Any]) -> str:
    """The digest the receipt is persisted under, over canonical JSON."""

    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _uuid_key(value: Any) -> str:
    """The comparison form for a UUID-shaped value.

    The contract's patterns are lowercase-only, so a validated document is already in this
    form -- but not every side of these comparisons is a validated document.  The database
    hands back ``str(UUID(...))`` and a caller may hand in a plan field from somewhere
    else, and ``'A1B2' != 'a1b2'`` would refuse a dispatch whose authority actually agrees.
    Normalising before comparing keeps the refusal about disagreement rather than casing.
    """

    return str(value).strip().lower()


def _refuse_product_dispatch(detail: str) -> DomainError:
    """One retryable refusal shape for every missing product prerequisite."""

    return DomainError("RES-0006", detail, 503, retryable=True)


class BuildExecutionService:
    """Sequence one admitted build and commit its consequences atomically."""

    def __init__(self, database, adapter, transport, *, environment: Mapping[str, str] | None = None):
        self.db = database
        self._adapter = adapter
        self._transport = transport
        self._environment = dict(environment if environment is not None else os.environ)

    # ---------------------------------------------------------------- preconditions

    def _require_reconciliation_channel(self) -> None:
        """Refuse before the external dispatch if a lost race could not be recorded.

        This is checked at the start rather than in the failure path because by the time the
        marker is needed the build has already run on the node: refusing then leaves exactly
        the unaccounted state the marker exists to report (#312 N2).
        """

        if getattr(self._transport, QUARANTINE_CAPABILITY, False) is not True:
            raise DomainError(
                "RES-0006",
                "node quarantine is not connected, so a dispatch that lost its commit "
                "could not be recorded for reconciliation",
                503,
                retryable=True,
            )

    def _database_now(self, tenant_id: str):
        """The authoritative current time, read from the database rather than this host."""

        with self.db.transaction(tenant_id) as conn:
            row = conn.execute("SELECT clock_timestamp() AS now").fetchone()
        now = row.get("now") if isinstance(row, dict) else None
        if now is None or getattr(now, "tzinfo", None) is None:
            raise DomainError("SYS-0001", "Database clock is unavailable", 503)
        return now

    def _require_product_enable(self) -> None:
        if self._environment.get(PRODUCT_ENABLE_SETTING) != PRODUCT_ENABLE_VALUE:
            raise _refuse_product_dispatch("BuildKit product dispatch is not enabled")

    def _health_authority(
        self, health: Any, *, leased_node_id: str, lease_epoch: str, now=None
    ) -> dict:
        """Compare a collected health receipt against this dispatch's authority."""

        if not isinstance(health, dict):
            raise _refuse_product_dispatch("builder health receipt is unavailable")
        if health.get("schemaVersion") != HEALTH_SCHEMA:
            raise _refuse_product_dispatch("builder health receipt schema is not authoritative")
        if health.get("writerKind") != WRITER_KIND:
            raise _refuse_product_dispatch(
                "builder health receipt was not written by the node agent"
            )
        if health.get("nodeId") != leased_node_id:
            raise _refuse_product_dispatch(
                "builder health receipt describes a node this build did not lease"
            )
        self._require_epoch_agreement(health.get("recoveryEpoch"), lease_epoch)
        isolation = health.get("isolation")
        if not isinstance(isolation, dict) or not isolation:
            raise _refuse_product_dispatch("builder health receipt records no isolation")
        for key, value in isolation.items():
            if value in CI_REFERENCE_ISOLATION:
                raise _refuse_product_dispatch(
                    f"builder isolation {key} is a CI reference value, not product isolation"
                )
        if now is not None:
            self._require_fresh_observation(health.get("observedAt"), now)
        return self._daemon_identity(health, "builder health receipt")

    @staticmethod
    def _require_fresh_observation(observed_at: Any, now) -> None:
        """Refuse an observation that is stale or ahead of the authoritative clock."""

        try:
            observed = dt.datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise DomainError(
                "RES-0003", "builder health observation has no readable observedAt", 409
            ) from None
        if observed.tzinfo is None:
            raise DomainError("RES-0003", "builder health observedAt has no time zone", 409)
        age = (now - observed).total_seconds()
        if age < 0 or age > HEALTH_FRESHNESS_SECONDS:
            raise DomainError("RES-0003", "builder health observation is stale", 409)

    def _require_epoch_agreement(self, receipt_epoch: Any, lease_epoch: str) -> None:
        """Three-way agreement: receipt, this database's epoch and the lease's.

        The decision names the system epoch as ``inv.system_state.recovery_epoch``;
        this tree carries it on the database handle, which is the same value every
        other authority check in ``build_adapter`` compares against.
        """

        system_epoch = _uuid_key(self.db.recovery_epoch)
        if _uuid_key(receipt_epoch) != system_epoch or _uuid_key(lease_epoch) != system_epoch:
            raise _refuse_product_dispatch(
                "builder, database and lease do not agree on the recovery epoch"
            )

    @staticmethod
    def _daemon_identity(document: Mapping[str, Any], label: str) -> dict:
        daemon = document.get("daemonIdentity")
        if not isinstance(daemon, dict):
            raise _refuse_product_dispatch(f"{label} records no daemon identity")
        identity = {}
        for field in DAEMON_IDENTITY_FIELDS:
            if field not in daemon:
                raise _refuse_product_dispatch(f"{label} daemon identity lacks {field}")
            identity[field] = daemon[field]
        if identity["comm"] != DAEMON_COMM:
            raise _refuse_product_dispatch(
                f"{label} daemon is {identity['comm']!r}, not {DAEMON_COMM}"
            )
        return identity

    def _leased_node_id(self, tenant_id: str, resource_id: str) -> str:
        """The node this build's resource belongs to, read from the database.

        Asked before the dispatch so the health receipt can be compared against it.
        It is not the transport's answer to give: a builder that could name its own
        node would make ``nodeId == leasedNodeId`` a statement about itself.
        """

        with self.db.transaction(tenant_id) as conn:
            row = conn.execute(
                "SELECT node_id FROM inv.resources WHERE resource_id=%s",
                (resource_id,),
            ).fetchone()
        if not row or not row.get("node_id"):
            raise _refuse_product_dispatch("the leased resource names no node")
        return str(row["node_id"])

    # ---------------------------------------------------------------- cleanup authority

    def _cleanup_authority(
        self,
        receipt: Any,
        *,
        build_session_id: str,
        leased_node_id: str,
        resource_id: str,
        lease_id: str,
        lease_epoch: str,
        daemon_before: Mapping[str, Any],
    ) -> dict:
        """Every required observation must agree, or the lease is not released."""

        def refuse(detail: str) -> DomainError:
            return DomainError("VERIFY-0022", detail, 409)

        if not isinstance(receipt, dict):
            raise refuse("Build cleanup is not verified: no physical receipt")
        if receipt.get("schemaVersion") != CLEANUP_SCHEMA:
            raise refuse("Build cleanup receipt schema is not authoritative")
        if receipt.get("writerKind") != WRITER_KIND:
            raise refuse("Build cleanup receipt was not written by the node agent")
        if _uuid_key(receipt.get("buildSessionId")) != _uuid_key(build_session_id):
            raise refuse("Build cleanup receipt buildSessionId does not bind this dispatch")
        for field, expected in (
            ("nodeId", leased_node_id),
            ("resourceId", resource_id),
            ("leaseId", lease_id),
        ):
            if receipt.get(field) != expected:
                raise refuse(f"Build cleanup receipt {field} does not bind this dispatch")
        system_epoch = _uuid_key(self.db.recovery_epoch)
        if (
            _uuid_key(receipt.get("recoveryEpoch")) != system_epoch
            or _uuid_key(lease_epoch) != system_epoch
        ):
            raise refuse("Build cleanup receipt does not agree on the recovery epoch")
        identity = self._daemon_identity(receipt, "Build cleanup receipt")
        if any(identity[field] != daemon_before[field] for field in DAEMON_IDENTITY_FIELDS):
            raise refuse("Build cleanup receipt describes a different daemon")
        if not receipt.get("stopResult"):
            raise refuse("Build cleanup receipt records no stop result")
        if receipt.get("partialExportDisposition") not in PARTIAL_EXPORT_DISPOSITIONS:
            raise refuse("Build cleanup receipt does not dispose of the partial export")
        if receipt.get("cacheDisposition") not in CACHE_DISPOSITIONS:
            raise refuse("Build cleanup receipt does not dispose of the cache")
        if receipt.get("builderClaimReleased") is not True:
            raise refuse("Build cleanup receipt does not release the builder claim")
        if receipt.get("cgroupRemoved") is not True:
            raise refuse("Build cleanup receipt does not remove the cgroup")
        if not receipt.get("verifiedAt"):
            raise refuse("Build cleanup receipt records no verification time")
        return dict(receipt)

    @staticmethod
    def _require_duplicated_observations(caller: Any, physical: Mapping[str, Any]) -> None:
        """The BuildReceipt's cleanup receipt must agree with the physical one, exactly.

        The public receipt repeats four of the physical receipt's observations.  Checking
        only the physical one leaves the pair free to contradict each other, and a release
        justified by two receipts that disagree is justified by neither (#312 F-R2).
        """

        if not isinstance(caller, dict):
            raise DomainError(
                "VERIFY-0022", "the dispatched BuildReceipt carries no cleanup receipt", 409
            )
        for field in DUPLICATED_CLEANUP_OBSERVATIONS:
            if field not in caller:
                raise DomainError(
                    "VERIFY-0022",
                    f"the BuildReceipt cleanup receipt does not repeat {field}",
                    409,
                )
            if caller[field] != physical.get(field):
                raise DomainError(
                    "VERIFY-0022",
                    f"the two cleanup receipts disagree about {field}",
                    409,
                )

    def _require_physical_pair(self, cleanup: Any) -> None:
        """The product path requires the pair the contract only requires together.

        ``BuildCleanupReceipt`` makes ``physicalReceipt`` and ``physicalReceiptDigest``
        ``dependentRequired`` on each other, so a receipt carrying **neither** is contract
        valid -- that is the legacy caller's shape.  A product release has to be justified
        by a physical receipt, so the caller requires both rather than inheriting a
        permission written for callers that never had one.
        """

        if not isinstance(cleanup, dict):
            raise DomainError("VERIFY-0022", "Build cleanup receipt is unavailable", 409)
        receipt = cleanup.get("physicalReceipt")
        digest = cleanup.get("physicalReceiptDigest")
        if receipt is None or digest is None:
            raise DomainError(
                "VERIFY-0022",
                "Build cleanup receipt carries no physical receipt pair, which the product "
                "path requires even though the contract allows a legacy receipt without one",
                409,
            )
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise DomainError(
                "VERIFY-0022", "Build cleanup physicalReceiptDigest is malformed", 409
            )
        if canonical_digest(receipt) != digest:
            raise DomainError(
                "VERIFY-0022",
                "Build cleanup physicalReceiptDigest does not match the physical receipt",
                409,
            )

    # ---------------------------------------------------------------- the one transaction

    def _commit_consequences(
        self,
        *,
        tenant_id: str,
        project_id: str,
        run_id: str,
        evidence_id: str,
        evidence: Mapping[str, Any],
        cleanup_receipt: Any,
        caller_cleanup: Any,
        build_session_id: str,
        daemon_before: Mapping[str, Any],
        lease_id: str,
        leased_node_id: str,
        resource_id: str,
        binding_digest: str,
        decision_id: str,
    ) -> BuildExecutionResult:
        """Persist Evidence, release the lease and record the event, or nothing."""

        with self.db.transaction(tenant_id) as conn:
            lease = conn.execute(
                """SELECT tenant_id,project_id,resource_id,recovery_epoch,released_at
                FROM inv.resource_leases
                WHERE lease_id=%s AND run_id=%s FOR UPDATE""",
                (lease_id, run_id),
            ).fetchone()
            if (
                not lease
                or str(lease["tenant_id"]) != tenant_id
                or lease["project_id"] != project_id
                or str(lease["resource_id"]) != resource_id
                or lease["released_at"] is not None
                or _uuid_key(lease["recovery_epoch"]) != _uuid_key(self.db.recovery_epoch)
            ):
                # The adapter revalidated before this point; this is the same check at
                # commit time, because the only state that may be released is the state
                # that is still exactly the state that was dispatched.
                raise DomainError("LEASE-0002", "Build allocation is stale or differs", 409)
            # The cleanup comparison happens here, against the locked lease's own epoch,
            # because the decision puts the receipt verification inside this transaction:
            # a release may only be justified by a receipt that agrees with the state
            # being released at the moment it is released.
            verified = self._cleanup_authority(
                cleanup_receipt,
                build_session_id=build_session_id,
                leased_node_id=leased_node_id,
                resource_id=resource_id,
                lease_id=lease_id,
                lease_epoch=str(lease["recovery_epoch"]),
                daemon_before=daemon_before,
            )
            self._require_duplicated_observations(caller_cleanup, verified)
            # The release happens before the receipt is written down, because the receipt has
            # to state whether the lease was released and only this UPDATE can answer that.
            # Both statements are in one transaction, so a failure after this point unwinds
            # the release with everything else.
            released = conn.execute(
                """UPDATE inv.resource_leases
                SET released_at=clock_timestamp()
                WHERE lease_id=%s AND run_id=%s AND released_at IS NULL
                RETURNING lease_id""",
                (lease_id, run_id),
            ).fetchone()
            if not released:
                raise DomainError("LEASE-0002", "Build lease was released concurrently", 409)
            # The contract's own names: BuildCleanupReceipt references the physical receipt
            # and its canonical digest as ``physicalReceipt``/``physicalReceiptDigest``.  The
            # pair is only ``dependentRequired`` there -- neither present is valid for a
            # legacy caller -- so the product path requires it here before committing.
            # ``leaseReleased`` is true because the UPDATE above matched, not because anyone
            # said so, and the receipt is finished *before* the envelope is digested: r1 added
            # that field after the row was written, so the stored envelope was either missing
            # a required field or no longer the one its digest covers (#312 N1).
            persisted_cleanup = {
                **deepcopy(dict(caller_cleanup)),
                "physicalReceipt": deepcopy(verified),
                "physicalReceiptDigest": canonical_digest(verified),
                "leaseReleased": True,
            }
            self._require_physical_pair(persisted_cleanup)
            # The row is the public contract's own shape, checked before it exists rather
            # than trusted afterwards.
            validate_contract("BuildCleanupReceipt", persisted_cleanup)
            envelope = {
                **deepcopy(dict(evidence)),
                "cleanupReceipt": persisted_cleanup,
            }
            evidence_digest = canonical_digest(envelope)
            conn.execute(
                "INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES (%s,%s,%s,%s)",
                (tenant_id, run_id, evidence_id, Jsonb(envelope)),
            )
            # The public payload is exactly the six keys the contract allows, and the
            # canonical validator says so before the row exists rather than after (#312 F-R3).
            payload = {
                "decisionId": decision_id,
                "bindingDigest": binding_digest,
                "resourceId": resource_id,
                "leaseId": lease_id,
                "evidenceId": evidence_id,
                "evidenceDigest": evidence_digest,
            }
            validate_contract("BuildDispatchCompletedPayload", payload)
            conn.execute(
                """INSERT INTO inv.outbox(tenant_id,run_id,event_id,event_type,payload)
                VALUES (%s,%s,%s,%s,%s)""",
                (
                    tenant_id,
                    run_id,
                    uuid4(),
                    COMPLETED_EVENT,
                    Jsonb(payload),
                ),
            )
        return BuildExecutionResult(
            evidence_id=evidence_id,
            evidence_digest=evidence_digest,
            lease_released=True,
            cleanup_verified=True,
        )

    # ---------------------------------------------------------------- the entry point

    def execute(
        self,
        principal,
        request: Mapping[str, Any],
        plan: Mapping[str, Any],
        decision: Mapping[str, Any],
        *,
        policy_version: str,
        run_id: str,
        evidence_id: str,
        actor_id: str,
    ) -> BuildExecutionResult:
        """Dispatch one admitted build and commit its durable consequences."""

        self._require_product_enable()
        self._require_reconciliation_channel()
        # ``BuildPlan.buildSessionId`` is optional in the contract so a legacy plan without
        # one stays valid. The product path requires it: the physical cleanup receipt binds
        # itself to a session, and a dispatch with no session of its own has nothing for
        # that receipt to be about.
        plan_session = plan.get("buildSessionId")
        if not plan_session:
            raise _refuse_product_dispatch(
                "the admitted BuildPlan names no buildSessionId, which the product path "
                "requires even though the contract leaves it optional"
            )
        lease_id = plan["lease"]["leaseId"]
        resource_id = plan["lease"]["resourceId"]
        lease_epoch = plan["lease"].get("recoveryEpoch")

        leased_node_id = self._leased_node_id(request["tenantId"], resource_id)
        health = self._transport.collect_product_health()
        daemon_before = self._health_authority(
            health,
            leased_node_id=leased_node_id,
            lease_epoch=lease_epoch,
            now=self._database_now(request["tenantId"]),
        )

        dispatched = self._adapter.execute(
            principal,
            dict(request),
            dict(plan),
            dict(decision),
            policy_version=policy_version,
            run_id=run_id,
            evidence_id=evidence_id,
            actor_id=actor_id,
        )
        receipt_session = dispatched.receipt.get("buildSessionId") or plan_session
        if not receipt_session:
            raise DomainError("VERIFY-0002", "Build receipt names no session", 422)
        if _uuid_key(receipt_session) != _uuid_key(plan_session):
            raise DomainError(
                "VERIFY-0002", "Build receipt session differs from the admitted plan", 422
            )
        # Downstream uses the *admitted* form, not the transport's casing: the plan is the
        # document that was admitted, and the receipt only has to agree with it.
        build_session_id = plan_session

        daemon_after = self._daemon_identity(
            {"daemonIdentity": self._transport.daemon_identity()}, "post-dispatch observation"
        )
        if any(daemon_after[field] != daemon_before[field] for field in DAEMON_IDENTITY_FIELDS):
            # A different daemon answered after the dispatch, so any side effect this
            # build may have produced is unaccounted for: go straight to cleanup.
            self._transport.cancel_and_quarantine_session(build_session_id, "VERIFY-0002")
            raise DomainError("VERIFY-0002", "Build daemon identity changed", 422)

        cleanup_receipt = self._transport.collect_cleanup_receipt(build_session_id)
        try:
            return self._commit_consequences(
                tenant_id=request["tenantId"],
                project_id=request["projectId"],
                run_id=run_id,
                evidence_id=evidence_id,
                evidence=dispatched.evidence,
                cleanup_receipt=cleanup_receipt,
                caller_cleanup=dispatched.receipt.get("cleanup"),
                build_session_id=build_session_id,
                daemon_before=daemon_before,
                lease_id=lease_id,
                leased_node_id=leased_node_id,
                resource_id=resource_id,
                binding_digest=action_digest(
                    {
                        "decisionId": decision["decisionId"],
                        "leaseId": lease_id,
                        "resourceId": resource_id,
                    }
                ),
                decision_id=decision["decisionId"],
            )
        except DomainError as error:
            # LEASE-0002 here means the external dispatch already happened and this caller
            # lost the commit: nothing durable landed, so the node holds state nobody has
            # accounted for. The one-shot decision claim is consumed, so an automatic retry
            # answers IDEM-0001 -- which makes a durable reconciliation marker the only way
            # an operator learns about it (#312 F-R4).
            if error.code in {"VERIFY-0022", "LEASE-0002"}:
                # Nothing committed: no Evidence, no release. The node keeps the
                # unaccounted state, so it is quarantined rather than handed the next
                # build, and an operator reconciles it.
                try:
                    self._transport.quarantine_node(leased_node_id, error.code)
                except DomainError:
                    # A failing reconciliation attempt must not replace the reason this
                    # dispatch failed: an operator who sees the transport's own refusal here
                    # loses the fact that a race was lost after an external dispatch.  The
                    # product path refuses such a transport up front, so reaching this is a
                    # transport regression -- and the original cause is what says so.
                    pass
            raise
