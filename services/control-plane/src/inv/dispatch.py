"""Durable delivery: one start reservation, then observation/cancellation only.

All writers lock Run before the delivery row. Network calls never hold DB locks.
Only an authenticated physical receipt can close a delivery or release resources.
"""

from dataclasses import dataclass
from uuid import uuid4, UUID
import base64
import json
from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .errors import DomainError
from .leases import assert_fences, lock_resources, lock_run
from .node_execution import seal_permit
from .runs import RunStore, event
from .tooling import NodePrincipal


def persist_delivery(conn, admitted, allocations, key, *, now):
    envelope = seal_permit(admitted, allocations, key, now=now)
    c = admitted.claim
    conn.execute(
        """INSERT INTO inv.execution_deliveries(tenant_id,project_id,run_id,node_id,command_id,envelope)
        VALUES(%s,%s,%s,%s,%s,%s)""",
        (
            c["tenantId"],
            c["projectId"],
            c["runId"],
            c["nodeId"],
            c["commandId"],
            Jsonb(envelope),
        ),
    )
    event(
        conn,
        c["tenantId"],
        c["runId"],
        "inv.execution.enqueued",
        {"commandId": c["commandId"]},
    )


@dataclass(frozen=True)
class DeliveryAttempt:
    node: NodePrincipal
    project_id: str
    run_id: str
    command_id: str
    token: str
    operation: str
    envelope: dict


class DeliveryQueue:
    def __init__(self, database):
        self.db = database

    def _can_start(self, conn, row, run, claim, now):
        if run["state"] != "scheduled" or claim["not_after"] <= now:
            return False
        if str(claim["recovery_epoch"]) != self.db.recovery_epoch:
            return False
        approval = conn.execute(
            """SELECT a.* FROM inv.approval_requests a JOIN inv.approval_dispatches d
            ON (a.tenant_id,a.approval_id)=(d.tenant_id,d.approval_id)
            WHERE a.run_id=%s AND d.command_id=%s AND a.status='dispatched' FOR SHARE OF a""",
            (run["run_id"], row["command_id"]),
        ).fetchone()
        if not approval or approval["bound_run_version"] + 1 != run["version"]:
            return False
        allocations = json.loads(base64.b64decode(row["envelope"]["payload"]))["allocations"]
        try:
            from .containment import require_execution

            require_execution(conn)
            lock_resources(conn, [a["lease"]["resourceId"] for a in allocations])
            ready = conn.execute(
                """SELECT 1 FROM inv.nodes WHERE node_id=%s AND status='online'
                AND recovery_epoch=%s::uuid AND abs(clock_skew_seconds)<=5
                AND heartbeat_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()""",
                (row["node_id"], self.db.recovery_epoch),
            ).fetchone()
            if not ready:
                return False
            assert_fences(
                conn,
                run["run_id"],
                {a["lease"]["leaseId"]: a["lease"]["fencingToken"] for a in allocations},
            )
            voters = conn.execute(
                "SELECT actor_id FROM inv.approval_votes WHERE approval_id=%s AND decision='approve' ORDER BY actor_id",
                (approval["approval_id"],),
            ).fetchall()
            actors = {v["actor_id"] for v in voters}
            requester = approval["requester_id"]
            if requester in actors or len(actors) < approval["required_approvals"]:
                return False
            store = ApprovalStore(self.db)
            for actor in sorted(actors | {requester}):
                store._grant(
                    conn,
                    row["project_id"],
                    actor,
                    "can_request" if actor == requester else "can_approve",
                )
        except DomainError:
            return False
        return (
            claim["not_after"] > conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        )

    def acquire(self, tenant_id, *, command_id=None):
        if command_id is not None:
            command_id = str(UUID(command_id))
        with self.db.transaction(tenant_id) as conn:
            # An active start can be preempted by one cancel worker. Otherwise a
            # worker lease must expire before observation can take it over.
            run = conn.execute(
                """SELECT r.*,q.command_id AS selected_command_id FROM inv.runs r JOIN inv.execution_deliveries q
                ON (r.tenant_id,r.run_id)=(q.tenant_id,q.run_id)
                WHERE q.phase<>'stopped' AND (%s::uuid IS NULL OR q.command_id=%s::uuid)
                AND ((q.next_attempt_at<=clock_timestamp() AND (q.lease_until IS NULL OR q.lease_until<=clock_timestamp()))
                 OR (r.state='cancelled' AND q.operation='execute'))
                ORDER BY q.created_at,q.command_id LIMIT 1 FOR UPDATE OF r SKIP LOCKED""",
                (command_id, command_id),
            ).fetchone()
            if not run:
                return None
            row = conn.execute(
                "SELECT * FROM inv.execution_deliveries WHERE command_id=%s AND phase<>'stopped' FOR UPDATE",
                (run["selected_command_id"],),
            ).fetchone()
            if not row or (command_id is not None and str(row["command_id"]) != command_id):
                return None
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            takeover = run["state"] == "cancelled" and row["operation"] == "execute"
            if not takeover and (
                row["next_attempt_at"] > now
                or (row["lease_until"] is not None and row["lease_until"] > now)
            ):
                return None
            if conn.execute(
                "SELECT 1 FROM inv.node_stop_receipts WHERE command_id=%s",
                (row["command_id"],),
            ).fetchone():
                self._stopped(conn, row)
                return None
            claim = conn.execute(
                "SELECT * FROM inv.tool_claims WHERE command_id=%s",
                (row["command_id"],),
            ).fetchone()
            operation = (
                "cancel"
                if run["state"] in {"cancelled", "failed"} or row["operation"] == "cancel"
                else "observe"
            )
            may_start = row["phase"] == "queued" and self._can_start(conn, row, run, claim, now)
            if row["phase"] == "queued" and not may_start:
                # No transmission was reserved. An invalidated admission must
                # obtain a Node tombstone, not observe an unseen command forever.
                # Keep all leases until the authenticated physical receipt.
                operation = "cancel"
                if run["state"] not in {"succeeded", "failed", "cancelled"}:
                    RunStore(self.db)._transition(conn, tenant_id, run, "failed", run["version"])
                    event(
                        conn,
                        tenant_id,
                        run["run_id"],
                        "inv.execution.start_authority_lost",
                        {"commandId": str(row["command_id"]), "action": "cancel_and_await_receipt"},
                    )
            if may_start:
                # _can_start holds the Node row lock. All first reservations on
                # that Node serialize here, matching its single execution slot.
                if conn.execute(
                    """SELECT 1 FROM inv.execution_deliveries WHERE node_id=%s AND command_id<>%s
                    AND phase='uncertain' AND operation='execute' AND lease_until>clock_timestamp() LIMIT 1""",
                    (row["node_id"], row["command_id"]),
                ).fetchone():
                    return None
                operation = "execute"
                # Record logical attempt ownership before any network side effect.
                # Running means an attempt is in flight; physical start remains
                # unknown until Node evidence arrives. Replays never increment it.
                current = RunStore(self.db)._transition(
                    conn, tenant_id, run, "running", run["version"]
                )
                allocations = json.loads(base64.b64decode(row["envelope"]["payload"]))[
                    "allocations"
                ]
                conn.execute(
                    """INSERT INTO inv.execution_attempts
                    (tenant_id,project_id,run_id,node_id,command_id,attempt,proofs)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        tenant_id,
                        row["project_id"],
                        run["run_id"],
                        row["node_id"],
                        row["command_id"],
                        current["attempt"],
                        Jsonb(
                            {a["lease"]["leaseId"]: a["lease"]["fencingToken"] for a in allocations}
                        ),
                    ),
                )
            token = str(uuid4())
            conn.execute(
                """UPDATE inv.execution_deliveries SET phase='uncertain',operation=%s,worker_token=%s,
                lease_until=clock_timestamp()+interval '45 seconds',attempts=attempts+1,
                updated_at=clock_timestamp(),last_error_code=NULL WHERE command_id=%s""",
                (operation, token, row["command_id"]),
            )
            event(
                conn,
                tenant_id,
                run["run_id"],
                "inv.execution.delivery_reserved",
                {"commandId": str(row["command_id"]), "operation": operation},
            )
            return DeliveryAttempt(
                NodePrincipal(tenant_id, row["node_id"]),
                row["project_id"],
                run["run_id"],
                str(row["command_id"]),
                token,
                operation,
                row["envelope"],
            )

    def _stopped(self, conn, row):
        conn.execute(
            """UPDATE inv.execution_deliveries SET phase='stopped',operation=NULL,worker_token=NULL,
            lease_until=NULL,last_error_code=NULL,updated_at=clock_timestamp() WHERE command_id=%s""",
            (row["command_id"],),
        )
        event(
            conn,
            str(row["tenant_id"]),
            row["run_id"],
            "inv.execution.delivery_stopped",
            {"commandId": str(row["command_id"])},
        )

    def finish(self, attempt, *, error_code=None, not_sent=False):
        with self.db.transaction(attempt.node.tenant_id) as conn:
            run = lock_run(conn, attempt.run_id, attempt.project_id)
            row = conn.execute(
                "SELECT * FROM inv.execution_deliveries WHERE command_id=%s FOR UPDATE",
                (attempt.command_id,),
            ).fetchone()
            if not row or row["phase"] == "stopped":
                return "stopped" if row else "unknown"
            if str(row["worker_token"]) != attempt.token:
                return "superseded"
            if conn.execute(
                "SELECT 1 FROM inv.node_stop_receipts WHERE command_id=%s",
                (attempt.command_id,),
            ).fetchone():
                self._stopped(conn, row)
                return "stopped"
            if not_sent and attempt.operation == "execute":
                if run["state"] not in {"succeeded", "failed", "cancelled"}:
                    RunStore(self.db)._transition(
                        conn, attempt.node.tenant_id, run, "cancelled", run["version"]
                    )
                conn.execute(
                    """UPDATE inv.execution_deliveries SET operation='cancel',worker_token=NULL,lease_until=NULL,
                    next_attempt_at=clock_timestamp(),last_error_code=%s,updated_at=clock_timestamp() WHERE command_id=%s""",
                    (error_code, attempt.command_id),
                )
                event(
                    conn,
                    attempt.node.tenant_id,
                    attempt.run_id,
                    "inv.execution.preflight_cancelled",
                    {"commandId": attempt.command_id},
                )
                return "uncertain"
            # A transport return is not proof. NodeDelivery must first commit its
            # authenticated receipt; no receipt leaves the queue uncertain.
            conn.execute(
                """UPDATE inv.execution_deliveries SET worker_token=NULL,lease_until=NULL,
                next_attempt_at=clock_timestamp()+least(power(2,least(attempts,5)),30)*interval '1 second',
                last_error_code=%s,updated_at=clock_timestamp() WHERE command_id=%s""",
                (error_code or "NODE-0060", attempt.command_id),
            )
            return "uncertain"


class DeliveryWorker:
    def __init__(self, database, delivery, *, output_provider=None):
        self.queue, self.delivery = DeliveryQueue(database), delivery
        from .output_ingestion import OutputIngestion

        self.outputs = OutputIngestion(database, output_provider)
        from .shard_completion import ShardCompletion

        self.parents = ShardCompletion(database, output_provider)

    def once(self, tenant_id, *, command_id=None):
        from .containment import ContainmentReconciler

        reconciled = ContainmentReconciler(self.queue.db).once(tenant_id)
        attempt = self.queue.acquire(tenant_id, command_id=command_id)
        if attempt is None:
            outcome = self.outputs.once(tenant_id, command_id=command_id)
            parent = self.parents.once(tenant_id, command_id=command_id)
            return outcome if outcome != "idle" else parent if parent != "idle" else reconciled
        error, not_sent = None, False
        try:
            self.delivery.deliver(
                attempt.node,
                attempt.envelope,
                observation_only=attempt.operation == "observe",
                cancel_only=attempt.operation == "cancel",
            )
        except Exception as exc:
            error = exc.code if isinstance(exc, DomainError) else "SYS-0001"
            not_sent = isinstance(exc, DomainError) and getattr(exc, "not_sent", False)
        outcome = self.queue.finish(attempt, error_code=error, not_sent=not_sent)
        if outcome == "stopped":
            self.outputs.once(tenant_id, command_id=attempt.command_id)
            self.parents.once(tenant_id, command_id=attempt.command_id)
        return outcome
