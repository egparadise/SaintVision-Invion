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
from .approvals import ApprovalStore, digest
from .control import Control
from .errors import DomainError
from .leases import lock_run, lock_resources
from .tooling import ToolGateway
from .runs import RunStore, event, public
from .state import TERMINAL
from .reservations import reclaim_unclaimed
from .leases import fence
from .db import BoundDatabase


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

    @contextmanager
    def _admission_transaction(self, tenant, project, plan_id, shards):
        failure = None
        with self.db.transaction(tenant) as conn:
            conn.execute(
                "SELECT plan_id FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s FOR UPDATE",
                (project, plan_id),
            ).fetchone()
            # Locks survive savepoint rollback, closing the claim/cleanup race.
            rows = {
                run: lock_run(conn, run, project)
                for run in sorted(s.command["runId"] for s in shards)
            }
            for approval in sorted({s.command["approvalId"] for s in shards}):
                conn.execute(
                    "SELECT approval_id FROM inv.approval_requests WHERE approval_id=%s FOR SHARE",
                    (approval,),
                ).fetchone()
            resources = conn.execute(
                "SELECT DISTINCT resource_id FROM inv.resource_leases WHERE run_id=ANY(%s) AND released_at IS NULL",
                (list(rows),),
            ).fetchall()
            lock_resources(conn, [r["resource_id"] for r in resources])
            try:
                with conn.transaction():
                    yield conn
            except Exception as error:
                failure = error
                for s in sorted(shards, key=lambda s: s.command["runId"]):
                    row = rows[s.command["runId"]]
                    leases = conn.execute(
                        "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                        (row["run_id"],),
                    ).fetchall()
                    # Never cancel another committed execution or stale allocation.
                    if (
                        row["state"] in TERMINAL
                        or s.proofs != {l["lease_id"]: fence(l) for l in leases}
                        or conn.execute(
                            "SELECT 1 FROM inv.tool_claims WHERE run_id=%s", (row["run_id"],)
                        ).fetchone()
                    ):
                        continue
                    if conn.execute(
                        "SELECT 1 FROM inv.run_attempts WHERE run_id=%s", (row["run_id"],)
                    ).fetchone():
                        continue
                    RunStore(self.db)._transition(conn, tenant, row, "cancelled", row["version"])
                    reclaim_unclaimed(
                        conn,
                        tenant,
                        {**row, "state": "cancelled"},
                        self.db.recovery_epoch,
                        reason="admission_failed",
                        proofs=s.proofs,
                    )
        if failure is not None:
            raise failure

    def enqueue(
        self, tenant, project, plan_id, shards, *, signing_key, splittable, communication="none"
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
            raise DomainError("VAL-0003", "Each shard requires a distinct Run and command", 422)
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
        with self._admission_transaction(tenant, project, plan_id, shards) as conn:
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
                parent = conn.execute(
                    "SELECT run_id FROM inv.shard_parents WHERE project_id=%s AND plan_id=%s",
                    (project, plan_id),
                ).fetchone()
                return {
                    "planId": plan_id,
                    "queued": len(linked),
                    "replayed": True,
                    "parentRunId": parent["run_id"] if parent else None,
                }
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
            from .shard_completion import create_parent

            parent_id = create_parent(conn, self.db, tenant, project, plan_id)
        return {
            "planId": plan_id,
            "queued": len(shards),
            "replayed": False,
            "parentRunId": parent_id,
        }

    def status(self, tenant, project, plan_id):
        with self.db.transaction(tenant) as conn:
            plan = conn.execute(
                "SELECT shard_count FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s",
                (project, plan_id),
            ).fetchone()
            if not plan:
                raise DomainError("RES-0004", "Shard plan not found", 404)
            parent = conn.execute(
                "SELECT r.run_id,r.state,c.manifest_hash FROM inv.shard_parents p JOIN inv.runs r ON (p.tenant_id,p.run_id)=(r.tenant_id,r.run_id) LEFT JOIN inv.shard_completions c ON (p.tenant_id,p.project_id,p.plan_id)=(c.tenant_id,c.project_id,c.plan_id) WHERE p.project_id=%s AND p.plan_id=%s",
                (project, plan_id),
            ).fetchone()
            rows = conn.execute(
                """SELECT s.shard_index,s.run_id,s.node_id,s.command_id,d.phase,r.envelope AS receipt,
              u.state,c.evidence_id,p.object_id,o.content_hash,o.size_bytes,o.state AS object_state
              FROM inv.shard_commands s JOIN inv.execution_deliveries d USING(tenant_id,command_id)
              LEFT JOIN inv.node_stop_receipts r USING(tenant_id,command_id)
              JOIN inv.runs u ON (s.tenant_id,s.run_id)=(u.tenant_id,u.run_id)
              LEFT JOIN inv.result_completions c ON (s.tenant_id,s.command_id,u.attempt)=(c.tenant_id,c.command_id,c.attempt)
              LEFT JOIN inv.result_commitments p ON (s.tenant_id,s.command_id)=(p.tenant_id,p.command_id)
              LEFT JOIN inv.storage_objects o ON (p.tenant_id,p.project_id,p.object_id)=(o.tenant_id,o.project_id,o.object_id)
              WHERE s.project_id=%s AND s.plan_id=%s ORDER BY s.shard_index""",
                (project, plan_id),
            ).fetchall()
            succeeded = len(rows) == plan["shard_count"] and all(
                r["state"] == "succeeded"
                and r["evidence_id"] is not None
                and r["object_state"] == "ready"
                for r in rows
            )
            manifest = (
                [
                    {
                        "index": r["shard_index"],
                        "runId": r["run_id"],
                        "evidenceId": r["evidence_id"],
                        "objectId": str(r["object_id"]),
                        "sha256": r["content_hash"],
                        "sizeBytes": r["size_bytes"],
                    }
                    for r in rows
                ]
                if succeeded
                else None
            )
            return {
                "planId": plan_id,
                "parentRunId": parent["run_id"] if parent else None,
                "parentState": parent["state"] if parent else None,
                "aggregateManifestSha256": parent["manifest_hash"] if parent else None,
                "shardCount": plan["shard_count"],
                "allPhysicallyStopped": len(rows) == plan["shard_count"]
                and all(r["receipt"] is not None for r in rows),
                "allSucceeded": succeeded,
                "resultManifest": manifest,
                "resultManifestSha256": (digest(manifest) if manifest is not None else None),
                "shards": [
                    {
                        "index": r["shard_index"],
                        "runId": r["run_id"],
                        "nodeId": r["node_id"],
                        "phase": r["phase"],
                        "state": r["state"],
                        "evidenceId": r["evidence_id"],
                    }
                    for r in rows
                ],
            }

    @staticmethod
    def _lock_members(conn, project, plan_id):
        plan = conn.execute(
            "SELECT shard_count FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s FOR UPDATE",
            (project, plan_id),
        ).fetchone()
        if not plan:
            raise DomainError("RES-0004", "Shard plan not found", 404)
        members = conn.execute(
            "SELECT run_id,command_id FROM inv.shard_commands WHERE project_id=%s AND plan_id=%s ORDER BY run_id",
            (project, plan_id),
        ).fetchall()
        if len(members) != plan["shard_count"]:
            raise DomainError("NODE-0062", "Shard plan is incomplete")
        return [(member, lock_run(conn, member["run_id"], project)) for member in members]

    def cancel(self, principal, project, plan_id, *, key, expected_parent_version=None):
        """One authorized, atomic cancellation request for all nonterminal members.

        Queue workers deliver individual cancellations. Physical leases remain
        reserved until each authenticated stop receipt, including uncertain ones.
        """
        approvals = ApprovalStore(self.db)
        with self.db.transaction(principal.tenant_id) as conn:
            prior = approvals._ledger(
                conn,
                principal,
                project,
                "shard.cancel",
                key,
                {
                    "planId": plan_id,
                    **(
                        {"parentVersion": expected_parent_version}
                        if expected_parent_version is not None
                        else {}
                    ),
                },
            )
            members = self._lock_members(conn, project, plan_id)
            link = conn.execute(
                "SELECT run_id FROM inv.shard_parents WHERE project_id=%s AND plan_id=%s",
                (project, plan_id),
            ).fetchone()
            parent = lock_run(conn, link["run_id"], project) if link else None
            Control(self.db).grant(conn, principal, project, "can_request")
            if prior is not None:
                return prior
            if expected_parent_version is not None and (
                not parent or parent["version"] != expected_parent_version
            ):
                raise DomainError("GRAPH-0003", "Parent version changed")
            if (
                expected_parent_version is not None
                and parent["state"] in TERMINAL
                and parent["state"] != "cancelled"
            ):
                raise DomainError("GRAPH-0002", "Parent is already terminal")
            changed = []
            for member, run in members:
                if run["state"] not in TERMINAL:
                    RunStore(self.db)._transition(
                        conn, principal.tenant_id, run, "cancelled", run["version"]
                    )
                    event(
                        conn,
                        principal.tenant_id,
                        run["run_id"],
                        "inv.run.cancel_requested",
                        {"planId": plan_id},
                    )
                    changed.append(run["run_id"])
            parent_result = None
            if parent:
                if parent["state"] not in TERMINAL:
                    parent_public = RunStore(self.db)._transition(
                        conn, principal.tenant_id, parent, "cancelled", parent["version"]
                    )
                    event(
                        conn,
                        principal.tenant_id,
                        parent["run_id"],
                        "inv.run.cancel_requested",
                        {"planId": plan_id},
                    )
                else:
                    parent_public = public(parent)
                pending = conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=ANY(%s) AND released_at IS NULL",
                    ([r["run_id"] for _, r in members],),
                ).fetchone()
                parent_result = {**parent_public, "resourceReleasePending": bool(pending)}
            return approvals._save(
                conn,
                project,
                "shard.cancel",
                key,
                {"planId": plan_id, "cancelledRuns": changed, "parentRun": parent_result},
            )

    def reconcile_failures(self, tenant, project, plan_id):
        """Project-authorized worker adapter; observe receipts, never retry work."""
        with self.db.transaction(tenant) as conn:
            members = self._lock_members(conn, project, plan_id)
            failed = []
            for member, run in members:
                row = conn.execute(
                    """SELECT r.envelope FROM inv.node_stop_receipts r
                    JOIN inv.execution_attempts a USING(tenant_id,command_id)
                    WHERE r.command_id=%s AND a.run_id=%s AND a.attempt=%s""",
                    (member["command_id"], run["run_id"], run["attempt"]),
                ).fetchone()
                if not row or run["state"] not in {"running", "verifying"}:
                    continue
                receipt = row["envelope"]
                if receipt["recoveryEpoch"] != self.db.recovery_epoch:
                    continue
                if (
                    receipt["processStarted"]
                    and receipt["exitCode"] == 0
                    and receipt["reason"] == "exited"
                ):
                    continue
                RunStore(self.db)._transition(conn, tenant, run, "failed", run["version"])
                event(
                    conn,
                    tenant,
                    run["run_id"],
                    "inv.shard.failed",
                    {"planId": plan_id, "commandId": str(member["command_id"])},
                )
                failed.append(run["run_id"])
            return {"planId": plan_id, "failedRuns": failed}
