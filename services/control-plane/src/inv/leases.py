"""Atomic reservation. Every capacity writer follows Run -> Node -> Resource locks.

The runtime role belongs to this trusted service only, never tenants or SQL clients.
An application that writes these tables directly must implement the same protocol.
"""

from dataclasses import dataclass
from uuid import UUID
import hashlib
import json
from psycopg.types.json import Jsonb
from .db import Database
from .errors import DomainError
from .ids import new_id


@dataclass(frozen=True, order=True)
class Allocation:
    resource_id: str
    amount: int


def lock_run(conn, run_id, project_id=None):
    row = conn.execute(
        "SELECT * FROM inv.runs WHERE run_id=%s FOR UPDATE", (run_id,)
    ).fetchone()
    if not row or (project_id is not None and row["project_id"] != project_id):
        raise DomainError("RES-0004", "Run not found", 404)
    return row


def lock_resources(conn, ids):
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT resource_id,node_id FROM inv.resources WHERE resource_id=ANY(%s)",
        (sorted(ids),),
    ).fetchall()
    if len(rows) != len(ids):
        raise DomainError("RES-0004", "Resource not found", 404)
    # All node locks precede all resource locks. Resource identity is immutable.
    for node in sorted({r["node_id"] for r in rows}):
        conn.execute(
            "SELECT node_id FROM inv.nodes WHERE node_id=%s FOR UPDATE", (node,)
        ).fetchone()
    result = {}
    for resource in sorted(ids):
        result[resource] = conn.execute(
            "SELECT * FROM inv.resources WHERE resource_id=%s FOR UPDATE", (resource,)
        ).fetchone()
    return result


def active_total(conn, resource_id):
    # Separate statement AFTER lock acquisition, using wall clock after any wait.
    return conn.execute(
        """SELECT coalesce(sum(amount),0) AS used FROM inv.resource_leases
        WHERE resource_id=%s AND released_at IS NULL""",
        (resource_id,),
    ).fetchone()["used"]


def fence(row):
    return str(row["recovery_epoch"]) + ":" + str(row["fencing_token"])


def wire(row):
    return {
        "leaseId": row["lease_id"],
        "tenantId": str(row["tenant_id"]),
        "runId": row["run_id"],
        "resourceId": row["resource_id"],
        "amount": row["amount"],
        "fencingToken": fence(row),
        "grantedAt": row["granted_at"].isoformat(),
        "expiresAt": row["expires_at"].isoformat(),
    }


class LeaseStore:
    def __init__(self, database: Database):
        self.db = database

    def reserve(
        self,
        tenant_id: str,
        project_id: str,
        run_id: str,
        allocations: list[Allocation],
        *,
        key: str,
        ttl_seconds: int = 30
    ) -> list[dict]:
        if (
            not allocations
            or len(allocations) > 128
            or len({a.resource_id for a in allocations}) != len(allocations)
        ):
            raise DomainError(
                "VAL-0003", "A nonempty, unique resource set is required", 422
            )
        if any(
            type(a.amount) is not int or not 0 < a.amount <= 9007199254740991
            for a in allocations
        ):
            raise DomainError("VAL-0003", "Allocation amount is invalid", 422)
        if (
            type(ttl_seconds) is not int
            or not 1 <= ttl_seconds <= 300
            or not isinstance(key, str)
            or not 1 <= len(key) <= 200
        ):
            raise DomainError("VAL-0003", "Invalid lease TTL or idempotency key", 422)
        ordered = sorted(allocations)
        digest = hashlib.sha256(
            json.dumps(
                {
                    "run": run_id,
                    "resources": [[a.resource_id, a.amount] for a in ordered],
                    "ttl": ttl_seconds,
                    "epoch": self.db.recovery_epoch,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        with self.db.transaction(tenant_id) as conn:
            conn.execute(
                """INSERT INTO inv.idempotency(tenant_id,project_id,operation,key,request_hash)
                VALUES (%s,%s,'lease.reserve',%s,%s) ON CONFLICT DO NOTHING""",
                (tenant_id, project_id, key, digest),
            )
            prior = conn.execute(
                """SELECT request_hash,response FROM inv.idempotency
                WHERE project_id=%s AND operation='lease.reserve' AND key=%s FOR UPDATE""",
                (project_id, key),
            ).fetchone()
            if prior["request_hash"] != digest:
                raise DomainError(
                    "IDEM-0001", "Idempotency key was used with a different request"
                )
            if prior["response"] is not None:
                return prior["response"]
            result = self._reserve_locked(
                conn, tenant_id, project_id, run_id, ordered, ttl_seconds
            )
            conn.execute(
                """UPDATE inv.idempotency SET response=%s
                WHERE project_id=%s AND operation='lease.reserve' AND key=%s""",
                (Jsonb(result), project_id, key),
            )
            return result

    def _reserve_locked(
        self, conn, tenant_id, project_id, run_id, ordered, ttl_seconds
    ):
        """Internal validated allocation API; caller owns its durable ledger.

        Canonical order: Run/admission -> project mutex -> ceiling -> Nodes -> Resources.
        Placement's opt-in short-commit path reuses the same admission and commit
        primitives but omits the legacy project mutex after locking the ceiling row.
        """
        run = self._admit_locked(conn, project_id, run_id)
        conn.execute(
            "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE",
            (project_id,),
        ).fetchone()
        limits = conn.execute(
            "SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE",
            (project_id,),
        ).fetchone()
        resources = lock_resources(conn, [a.resource_id for a in ordered])
        return self._reserve_prepared_locked(
            conn,
            tenant_id,
            project_id,
            run_id,
            ordered,
            ttl_seconds,
            run=run,
            limits=limits,
            resources=resources,
        )

    def _admit_locked(self, conn, project_id, run_id, *, run=None):
        """Lock one Run and perform the canonical four admission checks."""

        run = run or lock_run(conn, run_id, project_id)
        from .containment import require_execution

        require_execution(conn)
        from .shard_recovery import require_recovery_admission

        require_recovery_admission(conn, self.db, run_id)
        from .business_handoff import require_handoff

        require_handoff(conn, self.db, run_id)
        from .workspace_start import require_start_admission

        require_start_admission(conn, self.db, run_id)
        if run["state"] not in {"planned", "scheduled", "running"}:
            raise DomainError(
                "RES-0005", "Run cannot acquire resources in its current state"
            )
        if conn.execute(
            "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (run_id,),
        ).fetchone():
            raise DomainError(
                "LEASE-0003",
                "Previous allocations require verified stop acknowledgements",
            )
        return run

    def _reserve_prepared_locked(
        self,
        conn,
        tenant_id,
        project_id,
        run_id,
        ordered,
        ttl_seconds,
        *,
        run,
        limits,
        resources,
    ):
        """Validate and insert after the caller acquired canonical locks once."""

        if run["run_id"] != run_id or run["project_id"] != project_id:
            raise DomainError("RES-0004", "Run not found", 404)
        if set(resources) != {allocation.resource_id for allocation in ordered}:
            raise DomainError("RES-0004", "Resource not found", 404)
        if limits:
            for kind, field in [("cpu", "cpu_millis"), ("memory", "memory_bytes")]:
                used = conn.execute(
                    """SELECT coalesce(sum(l.amount),0) AS used FROM inv.resource_leases l
                    JOIN inv.resources r USING(tenant_id,resource_id)
                    WHERE l.project_id=%s AND l.released_at IS NULL AND r.kind=%s""",
                    (project_id, kind),
                ).fetchone()["used"]
                needed = sum(
                    a.amount
                    for a in ordered
                    if resources[a.resource_id]["kind"] == kind
                )
                if used + needed > limits[field]:
                    raise DomainError(
                        "RES-0001", "Project resource ceiling exhausted", retryable=True
                    )
        for node in sorted({r["node_id"] for r in resources.values()}):
            valid = conn.execute(
                """SELECT status='online' AND heartbeat_at >= clock_timestamp()-interval '15 seconds'
                AND heartbeat_at <= clock_timestamp() AND abs(clock_skew_seconds) <= 5
                AND recovery_epoch=%s::uuid AS ready FROM inv.nodes WHERE node_id=%s""",
                (self.db.recovery_epoch, node),
            ).fetchone()
            if not valid["ready"]:
                raise DomainError(
                    "RES-0006",
                    "Node is unavailable or heartbeat is stale",
                    retryable=True,
                )
        result = []
        for allocation in ordered:
            resource = resources[allocation.resource_id]
            if (
                active_total(conn, allocation.resource_id) + allocation.amount
                > resource["offered"]
            ):
                raise DomainError(
                    "RES-0001", "Insufficient offered capacity", retryable=True
                )
            row = conn.execute(
                """INSERT INTO inv.resource_leases
                (tenant_id,project_id,run_id,resource_id,lease_id,amount,recovery_epoch,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+make_interval(secs=>%s)) RETURNING *""",
                (
                    tenant_id,
                    project_id,
                    run_id,
                    allocation.resource_id,
                    new_id("lse"),
                    allocation.amount,
                    self.db.recovery_epoch,
                    ttl_seconds,
                ),
            ).fetchone()
            result.append(wire(row))
        return result

    def _locked_lease(self, conn, lease_id, token):
        candidate = conn.execute(
            "SELECT run_id,resource_id FROM inv.resource_leases WHERE lease_id=%s",
            (lease_id,),
        ).fetchone()
        if not candidate:
            raise DomainError("RES-0004", "Lease not found", 404)
        run = lock_run(conn, candidate["run_id"])
        lock_resources(conn, [candidate["resource_id"]])
        row = conn.execute(
            "SELECT *,expires_at>clock_timestamp() AS fresh FROM inv.resource_leases WHERE lease_id=%s FOR UPDATE",
            (lease_id,),
        ).fetchone()
        if type(token) is not str or fence(row) != token:
            raise DomainError("LEASE-0002", "Stale fencing token")
        return run, row

    def renew(self, tenant_id, lease_id, token, *, ttl_seconds=30):
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300:
            raise DomainError("VAL-0003", "Invalid lease TTL", 422)
        with self.db.transaction(tenant_id) as conn:
            run, row = self._locked_lease(conn, lease_id, token)
            if (
                str(row["recovery_epoch"]) != self.db.recovery_epoch
                or not row["fresh"]
                or row["released_at"] is not None
                or run["state"] not in {"scheduled", "running", "verifying"}
            ):
                raise DomainError(
                    "LEASE-0001", "Lease expired, released, or run stopped"
                )
            # Monotonic extension: retries never shorten the current expiry.
            renewed = conn.execute(
                """UPDATE inv.resource_leases SET expires_at=greatest(expires_at,
                clock_timestamp()+make_interval(secs=>%s)) WHERE lease_id=%s RETURNING *""",
                (ttl_seconds, lease_id),
            ).fetchone()
            return wire(renewed)

    def release(
        self, tenant_id, lease_id, token, *, authenticated_node_id, stop_receipt
    ):
        # Trusted Node adapter only: verify process termination before acknowledging.
        # A browser cancellation is not a physical stop acknowledgement.
        try:
            receipt = str(UUID(stop_receipt))
        except (ValueError, TypeError, AttributeError) as error:
            raise DomainError(
                "VAL-0003", "A durable stop receipt UUID is required", 422
            ) from error
        with self.db.transaction(tenant_id) as conn:
            _, row = self._locked_lease(conn, lease_id, token)
            resource = conn.execute(
                "SELECT node_id FROM inv.resources WHERE resource_id=%s",
                (row["resource_id"],),
            ).fetchone()
            if resource["node_id"] != authenticated_node_id:
                raise DomainError(
                    "AUTH-0021", "Stop acknowledgement belongs to another node", 403
                )
            conn.execute(
                """UPDATE inv.resource_leases SET released_at=coalesce(released_at,clock_timestamp()),
                stop_receipt=coalesce(stop_receipt,%s::uuid) WHERE lease_id=%s""",
                (receipt, lease_id),
            )
            return {"leaseId": lease_id, "released": True}

    def set_offer(self, tenant_id, resource_id, *, offered):
        if type(offered) is not int or offered < 0:
            raise DomainError("VAL-0003", "Invalid resource offer", 422)
        with self.db.transaction(tenant_id) as conn:
            resource = lock_resources(conn, [resource_id])[resource_id]
            if offered > resource["capacity"] or offered < active_total(
                conn, resource_id
            ):
                raise DomainError(
                    "RES-0002", "Offer conflicts with capacity or active reservations"
                )
            conn.execute(
                "UPDATE inv.resources SET offered=%s WHERE resource_id=%s",
                (offered, resource_id),
            )


def assert_fences(conn, run_id, proofs):
    """Call inside the same transaction as result/checkpoint writes, after Run lock."""
    rows = conn.execute(
        "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
        (run_id,),
    ).fetchall()
    # Require the exact live allocation set; expired allocations must first be released.
    if (
        not rows
        or not isinstance(proofs, dict)
        or set(proofs) != {r["lease_id"] for r in rows}
    ):
        raise DomainError("LEASE-0002", "Execution allocation set does not match")
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    epoch = str(
        conn.execute("SELECT epoch FROM inv.control_epoch WHERE singleton").fetchone()[
            "epoch"
        ]
    )
    if any(
        type(proofs[r["lease_id"]]) is not str
        or proofs[r["lease_id"]] != fence(r)
        or str(r["recovery_epoch"]) != epoch
        or r["expires_at"] <= now
        for r in rows
    ):
        raise DomainError("LEASE-0002", "Expired or stale execution fence")
