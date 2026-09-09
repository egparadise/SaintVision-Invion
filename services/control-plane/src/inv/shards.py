"""All-or-nothing admission of explicitly independent approved shard Runs.

Each shard keeps its own ToolGateway/Lease/Node journal. This is not a networked
collective runtime: socket/MPI/NCCL plans need a separately authorized profile.
There is no all-start-at-once promise; delivery may be uncertain on any Node.
"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID
from psycopg.types.json import Jsonb
from .approvals import digest
from .errors import DomainError
from .leases import lock_run, lock_resources
from .tooling import ToolGateway


class BoundDatabase:
    """Private adapter so every nested admission uses its parent's transaction."""

    def __init__(self, db, tenant, conn):
        self.recovery_epoch, self.tenant, self.conn = db.recovery_epoch, tenant, conn

    @contextmanager
    def transaction(self, tenant):
        if tenant != self.tenant:
            raise DomainError("AUTH-0011", "Nested transaction scope differs", 403)
        yield self.conn


@dataclass(frozen=True)
class ShardAdmission:
    node: object
    command: dict
    workload: dict
    proofs: dict
    policy: object
    runtime: object


class ShardRuntime:
    def __init__(self, database, profile):
        self.db, self.profile = database, profile

    def enqueue(
        self,
        tenant,
        project,
        plan_id,
        shards,
        *,
        signing_key,
        splittable,
        communication="none"
    ):
        if communication != "none" or splittable is not True:
            raise DomainError(
                "NODE-0062",
                "Independent shard declaration required; collective network profile unavailable",
                422,
            )
        if (
            not isinstance(plan_id, str)
            or not 1 <= len(plan_id) <= 200
            or not isinstance(shards, list)
            or not 1 <= len(shards) <= 16
            or not all(isinstance(s, ShardAdmission) for s in shards)
            or signing_key is None
        ):
            raise DomainError("VAL-0003", "Invalid bounded shard plan", 422)
        # Freeze all mutable request data before calculating the plan identity.
        shards = [
            ShardAdmission(
                s.node,
                deepcopy(s.command),
                deepcopy(s.workload),
                deepcopy(s.proofs),
                s.policy,
                s.runtime,
            )
            for s in shards
        ]
        runs = [s.command["runId"] for s in shards]
        commands = [str(UUID(s.command["commandId"])) for s in shards]
        if len(set(runs)) != len(shards) or len(set(commands)) != len(shards):
            raise DomainError(
                "VAL-0003", "Each shard requires a distinct Run and command", 422
            )
        if any(
            s.node.tenant_id != tenant
            or s.command["tenantId"] != tenant
            or s.command["projectId"] != project
            for s in shards
        ):
            raise DomainError("AUTH-0011", "Shard scope differs", 403)
        material = {
            "communication": "none",
            "epoch": self.db.recovery_epoch,
            "profile": self.profile.version,
            "shards": [
                {
                    "command": s.command,
                    "workload": s.workload,
                    "proofs": s.proofs,
                    "nodeId": s.node.node_id,
                }
                for s in shards
            ],
        }
        fingerprint = digest(material)
        with self.db.transaction(tenant) as conn:
            # Plan identity conflict precedes every claim. The row is committed
            # only after every claim, queue permit, link and outbox event passes.
            conn.execute(
                "INSERT INTO inv.shard_plans(tenant_id,project_id,plan_id,request_hash,shard_count) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (tenant, project, plan_id, fingerprint, len(shards)),
            )
            prior = conn.execute(
                "SELECT request_hash FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s FOR UPDATE",
                (project, plan_id),
            ).fetchone()
            if prior["request_hash"] != fingerprint:
                raise DomainError("IDEM-0001", "Shard plan content differs")
            linked = conn.execute(
                "SELECT command_id FROM inv.shard_commands WHERE project_id=%s AND plan_id=%s ORDER BY shard_index",
                (project, plan_id),
            ).fetchall()
            if linked:
                if len(linked) != len(shards):
                    raise DomainError("NODE-0062", "Shard plan is incomplete")
                return {"planId": plan_id, "queued": len(linked), "replayed": True}
            for run in sorted(runs):
                lock_run(conn, run, project)
            for approval in sorted({s.command["approvalId"] for s in shards}):
                conn.execute(
                    "SELECT approval_id FROM inv.approval_requests WHERE approval_id=%s FOR SHARE",
                    (approval,),
                ).fetchone()
            resources = conn.execute(
                "SELECT DISTINCT resource_id FROM inv.resource_leases WHERE run_id=ANY(%s) AND released_at IS NULL",
                (runs,),
            ).fetchall()
            lock_resources(conn, [r["resource_id"] for r in resources])
            conn.execute(
                "SELECT subject_id FROM inv.project_grants WHERE project_id=%s ORDER BY subject_id FOR SHARE",
                (project,),
            ).fetchall()
            gateway = ToolGateway(BoundDatabase(self.db, tenant, conn), self.profile)
            for index, s in enumerate(shards):
                # A preexisting claim might already be executing; never adopt it
                # into a new plan whose other shards have not been admitted.
                if conn.execute(
                    "SELECT 1 FROM inv.tool_claims WHERE command_id=%s",
                    (commands[index],),
                ).fetchone():
                    raise DomainError(
                        "NODE-0062",
                        "Existing execution cannot be adopted into a new plan",
                    )
                gateway.claim(
                    s.node,
                    s.command,
                    s.workload,
                    s.proofs,
                    policy=s.policy,
                    runtime=s.runtime,
                    queue_signing_key=signing_key,
                )
                conn.execute(
                    "INSERT INTO inv.shard_commands VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        tenant,
                        project,
                        plan_id,
                        index,
                        s.node.node_id,
                        s.command["runId"],
                        commands[index],
                    ),
                )
        return {"planId": plan_id, "queued": len(shards), "replayed": False}

    def status(self, tenant, project, plan_id):
        with self.db.transaction(tenant) as conn:
            plan = conn.execute(
                "SELECT shard_count FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s",
                (project, plan_id),
            ).fetchone()
            if not plan:
                raise DomainError("RES-0004", "Shard plan not found", 404)
            rows = conn.execute(
                """SELECT s.shard_index,s.run_id,s.node_id,d.phase,r.envelope AS receipt
              FROM inv.shard_commands s JOIN inv.execution_deliveries d USING(tenant_id,command_id)
              LEFT JOIN inv.node_stop_receipts r USING(tenant_id,command_id)
              WHERE s.project_id=%s AND s.plan_id=%s ORDER BY s.shard_index""",
                (project, plan_id),
            ).fetchall()
            return {
                "planId": plan_id,
                "shardCount": plan["shard_count"],
                "allPhysicallyStopped": len(rows) == plan["shard_count"]
                and all(r["receipt"] is not None for r in rows),
                "shards": [
                    {
                        "index": r["shard_index"],
                        "runId": r["run_id"],
                        "nodeId": r["node_id"],
                        "phase": r["phase"],
                    }
                    for r in rows
                ],
            }
