"""Operator controls and deterministic cleanup, never a claim of physical stop.

Database.transaction holds tenant gate -> Run -> Node/resource locks. Kill/clear
take the gate exclusively before other locks. Node drain serializes on its Node.
Worker cleanup retains claims until a real receipt arrives and never re-executes.
"""

from uuid import uuid4
from psycopg.types.json import Jsonb
from .approvals import digest
from .contracts import validate_contract
from .errors import DomainError


def require_execution(conn):
    gate = conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()
    if not gate or gate["kill_switch"]:
        raise DomainError("AUTH-0061", "Tenant execution is stopped by its operator", 409)


def operator(conn, principal, permission=None):
    row = conn.execute(
        "SELECT * FROM inv.operator_grants WHERE subject_id=%s FOR SHARE",
        (principal.subject_id,),
    ).fetchone()
    if (
        not row
        or not row["enabled"]
        or row["person_id"] is None
        or not (row["can_contain"] or row["can_resume"] or row["can_approve"])
        or (permission and not row[permission])
    ):
        raise DomainError("AUTH-0062", "Current operator permission required", 403)
    return row


def pending(conn, node_id=None):
    leases = conn.execute(
        """SELECT count(*) AS n FROM inv.resource_leases l JOIN inv.resources r USING(tenant_id,resource_id)
        WHERE l.released_at IS NULL AND (%s::text IS NULL OR r.node_id=%s)""",
        (node_id, node_id),
    ).fetchone()["n"]
    deliveries = conn.execute(
        "SELECT count(*) AS n FROM inv.execution_deliveries WHERE phase<>'stopped' AND (%s::text IS NULL OR node_id=%s)",
        (node_id, node_id),
    ).fetchone()["n"]
    runs = conn.execute(
        """SELECT count(*) AS n FROM inv.runs r WHERE state NOT IN ('succeeded','failed','cancelled')
        AND (%s::text IS NULL OR EXISTS(SELECT 1 FROM inv.tool_claims c WHERE c.run_id=r.run_id AND c.node_id=%s))""",
        (node_id, node_id),
    ).fetchone()["n"]
    return {"activeLeases": leases, "pendingDeliveries": deliveries, "unsettledRuns": runs}


class Containment:
    def __init__(self, database):
        self.db = database

    def _view(self, conn, node_id=None):
        gate = conn.execute("SELECT * FROM inv.tenant_controls").fetchone()
        if node_id is None:
            version, status = gate["version"], None
        else:
            row = conn.execute(
                "SELECT n.status,c.version FROM inv.nodes n JOIN inv.node_controls c USING(tenant_id,node_id) WHERE n.node_id=%s",
                (node_id,),
            ).fetchone()
            if not row:
                raise DomainError("RES-0004", "Node control unavailable", 404)
            version, status = row["version"], row["status"]
        work = pending(conn, node_id)
        result = {
            "nodeId": node_id,
            "version": version,
            "killSwitchActive": gate["kill_switch"],
            "nodeStatus": status,
            **work,
            "settled": not any(work.values()),
        }
        validate_contract("ContainmentView", result)
        return result

    def get(self, principal, node_id=None):
        if node_id is not None:
            validate_contract("NodeId", node_id)
        with self.db.transaction(principal.tenant_id) as conn:
            operator(conn, principal)
            return self._view(conn, node_id)

    def change(self, principal, operation, data, key, node_id=None):
        validate_contract("ContainmentInput", data)
        if operation not in {"kill", "clear", "drain", "resume"}:
            raise DomainError("VAL-0003", "Unknown containment operation", 422)
        if (node_id is None) != (operation in {"kill", "clear"}):
            raise DomainError("VAL-0003", "Containment scope differs", 422)
        if node_id is not None:
            validate_contract("NodeId", node_id)
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise DomainError("VAL-0003", "Idempotency-Key required", 422)
        request_hash = digest(
            {"operation": operation, "node": node_id, "actor": principal.subject_id, **data}
        )
        with self.db.transaction(principal.tenant_id, containment_write=node_id is None) as conn:
            operator(
                conn, principal, "can_resume" if operation in {"clear", "resume"} else "can_contain"
            )
            if node_id is not None:
                node = conn.execute(
                    "SELECT * FROM inv.nodes WHERE node_id=%s FOR UPDATE", (node_id,)
                ).fetchone()
                if not node:
                    raise DomainError("RES-0004", "Node unavailable", 404)
                if str(node["recovery_epoch"]) != self.db.recovery_epoch:
                    raise DomainError("NODE-0033", "Node requires epoch reconciliation", 409)
            conn.execute(
                """INSERT INTO inv.containment_requests(tenant_id,operation,key,request_id,subject_id,node_id,reason_code,request_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    principal.tenant_id,
                    operation,
                    key,
                    uuid4(),
                    principal.subject_id,
                    node_id,
                    data["reasonCode"],
                    request_hash,
                ),
            )
            prior = conn.execute(
                "SELECT * FROM inv.containment_requests WHERE operation=%s AND key=%s FOR UPDATE",
                (operation, key),
            ).fetchone()
            if prior["request_hash"] != request_hash:
                raise DomainError("IDEM-0001", "Containment request key has different content")
            if prior["response"] is not None:
                return prior["response"]
            current = self._view(conn, node_id)
            if current["version"] != data["expectedVersion"]:
                raise DomainError("GRAPH-0003", "Control version changed; reload before retry")
            from .containment_approvals import ControlApprovals

            ControlApprovals(self.db).consume(
                conn, principal, operation, node_id, data, prior["request_id"]
            )
            if operation == "kill":
                conn.execute(
                    "UPDATE inv.tenant_controls SET kill_switch=true,version=version+1,updated_at=clock_timestamp()"
                )
            elif operation == "clear":
                if not current["settled"]:
                    raise DomainError(
                        "LEASE-0003", "Kill switch must remain active until all work settles"
                    )
                conn.execute(
                    "UPDATE inv.tenant_controls SET kill_switch=false,version=version+1,updated_at=clock_timestamp()"
                )
            else:
                if operation == "drain":
                    if node["status"] == "quarantined":
                        raise DomainError(
                            "NODE-0062", "Quarantined Node requires operator reconciliation", 409
                        )
                    target = "draining"
                else:
                    require_execution(conn)
                    if node["status"] != "draining" or not current["settled"]:
                        raise DomainError("LEASE-0003", "A drained and settled Node is required")
                    ready = conn.execute(
                        """SELECT 1 FROM inv.nodes n JOIN inv.node_channels c USING(tenant_id,node_id)
                        JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
                        WHERE n.node_id=%s AND n.heartbeat_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()
                        AND abs(n.clock_skew_seconds)<=5 AND c.enabled AND c.certificate_not_after>clock_timestamp()
                        AND c.recovery_epoch=n.recovery_epoch AND s.recovery_epoch=n.recovery_epoch
                        AND s.channel_version=c.version AND s.received_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()""",
                        (node_id,),
                    ).fetchone()
                    if not ready:
                        raise DomainError(
                            "NODE-0062",
                            "Fresh authenticated Node resource observation required",
                            409,
                        )
                    target = "online"
                conn.execute("UPDATE inv.nodes SET status=%s WHERE node_id=%s", (target, node_id))
                conn.execute(
                    "UPDATE inv.node_controls SET version=version+1,updated_at=clock_timestamp() WHERE node_id=%s",
                    (node_id,),
                )
            result = {
                "requestId": str(prior["request_id"]),
                "approvalId": data["approvalId"],
                "operation": operation,
                "control": self._view(conn, node_id),
            }
            validate_contract("ContainmentResult", result)
            conn.execute(
                "UPDATE inv.containment_requests SET response=%s WHERE operation=%s AND key=%s",
                (Jsonb(result), operation, key),
            )
            return result


class ContainmentReconciler:
    """One Run per transaction; SKIP LOCKED, no network, no user grant reuse."""

    def __init__(self, database):
        self.db = database

    def once(self, tenant):
        from .leases import lock_resources
        from .reservations import reclaim_unclaimed
        from .runs import RunStore, event

        with self.db.transaction(tenant) as conn:
            killed = conn.execute("SELECT kill_switch FROM inv.tenant_controls").fetchone()[
                "kill_switch"
            ]
            row = conn.execute(
                """SELECT r.* FROM inv.runs r WHERE (state NOT IN ('succeeded','failed','cancelled') AND (
                 %s OR (r.state IN ('planned','scheduled','awaiting_approval') AND EXISTS(
                  SELECT 1 FROM inv.resource_leases l JOIN inv.resources x USING(tenant_id,resource_id)
                  JOIN inv.nodes n USING(tenant_id,node_id)
                  WHERE l.run_id=r.run_id AND l.released_at IS NULL AND n.status='draining'))
                 OR (NOT EXISTS(SELECT 1 FROM inv.tool_claims c WHERE c.run_id=r.run_id)
                  AND NOT EXISTS(SELECT 1 FROM inv.run_attempts a WHERE a.run_id=r.run_id)
                  AND EXISTS(SELECT 1 FROM inv.resource_leases l WHERE l.run_id=r.run_id AND l.released_at IS NULL AND l.expires_at<=clock_timestamp()))
                )) OR (state='cancelled'
                  AND NOT EXISTS(SELECT 1 FROM inv.tool_claims c WHERE c.run_id=r.run_id)
                  AND NOT EXISTS(SELECT 1 FROM inv.run_attempts a WHERE a.run_id=r.run_id)
                  AND NOT EXISTS(SELECT 1 FROM inv.resource_leases l WHERE l.run_id=r.run_id AND l.released_at IS NULL AND l.recovery_epoch<>%s::uuid)
                  AND EXISTS(SELECT 1 FROM inv.resource_leases l WHERE l.run_id=r.run_id AND l.released_at IS NULL))
                ORDER BY r.created_at,r.run_id LIMIT 1 FOR UPDATE OF r SKIP LOCKED""",
                (killed, self.db.recovery_epoch),
            ).fetchone()
            if not row:
                return "idle"
            leases = conn.execute(
                "SELECT resource_id FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (row["run_id"],),
            ).fetchall()
            lock_resources(conn, [r["resource_id"] for r in leases])
            if row["state"] == "cancelled" and not leases:
                return "idle"
            # Re-read Node status after its lock; a completed drain/resume cannot
            # retroactively cancel a new admission selected from an older snapshot.
            drained = conn.execute(
                """SELECT 1 FROM inv.resource_leases l JOIN inv.resources x USING(tenant_id,resource_id)
                JOIN inv.nodes n USING(tenant_id,node_id) WHERE l.run_id=%s AND l.released_at IS NULL AND n.status='draining'""",
                (row["run_id"],),
            ).fetchone()
            expired = conn.execute(
                "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL AND expires_at<=clock_timestamp()",
                (row["run_id"],),
            ).fetchone()
            if row["state"] != "cancelled" and not killed and not drained and not expired:
                return "idle"
            reason = (
                "cancelled_unclaimed"
                if row["state"] == "cancelled"
                else "kill_switch" if killed else "node_drain" if drained else "unclaimed_expired"
            )
            changed = RunStore(self.db)._transition(conn, tenant, row, "cancelled", row["version"])
            reclaimed = reclaim_unclaimed(
                conn,
                tenant,
                {**row, "state": "cancelled"},
                self.db.recovery_epoch,
                reason="cancelled_before_claim",
            )
            event(
                conn,
                tenant,
                row["run_id"],
                "inv.containment.run_cancelled",
                {"reason": reason, "reclaimedUnclaimed": reclaimed, "run": changed},
            )
            return "cancelled"
