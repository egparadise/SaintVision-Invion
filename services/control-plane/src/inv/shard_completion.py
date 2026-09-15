"""Deterministic parent policy: every child has current verified output.

Ordered result references are the aggregate. Numeric reducers and collectives
need their own approved execution; this coordinator never starts a process.
"""

from contextlib import nullcontext
from uuid import uuid4
from psycopg.types.json import Jsonb
from .approvals import digest
from .contracts import validate_contract
from .ids import new_id
from .leases import lock_run
from .runs import RunStore, event, public
from .snapshots import object_key
from .state import TERMINAL


def create_parent(conn, db, tenant, project, plan_id):
    run_id = new_id("run")
    conn.execute(
        "INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES(%s,%s,%s)",
        (tenant, project, run_id),
    )
    conn.execute(
        "INSERT INTO inv.shard_parents VALUES(%s,%s,%s,%s,%s)",
        (tenant, project, plan_id, run_id, db.recovery_epoch),
    )
    store = RunStore(db)
    for target in ("validated", "planned", "scheduled", "running"):
        row = lock_run(conn, run_id, project)
        store._transition(conn, tenant, row, target, row["version"])
    event(conn, tenant, run_id, "inv.shard.parent_created", {"planId": plan_id, "runId": run_id})
    return run_id


class ShardCompletion:
    def __init__(self, db, provider=None):
        self.db, self.provider = db, provider

    def once(self, tenant, *, command_id=None):
        # Provider -> plan -> sorted children -> parent. No caller holds a Run
        # when entering this method; this matches result publication lock order.
        with (
            self.provider.locked() if self.provider else nullcontext(None) as files,
            self.db.transaction(tenant) as conn,
        ):
            plan = conn.execute(
                """SELECT p.* FROM inv.shard_parents p JOIN inv.runs r ON (p.tenant_id,p.run_id)=(r.tenant_id,r.run_id)
                WHERE r.state IN ('running','verifying','cancelled','failed') AND p.recovery_epoch=%s
                AND (%s::uuid IS NULL OR EXISTS(SELECT 1 FROM inv.shard_commands s WHERE (s.tenant_id,s.project_id,s.plan_id)=(p.tenant_id,p.project_id,p.plan_id) AND s.command_id=%s))
                AND EXISTS(SELECT 1 FROM inv.shard_commands s JOIN inv.runs c ON (s.tenant_id,s.run_id)=(c.tenant_id,c.run_id)
                    WHERE (s.tenant_id,s.project_id,s.plan_id)=(p.tenant_id,p.project_id,p.plan_id)
                    AND ((r.state IN ('cancelled','failed') AND c.state NOT IN ('succeeded','failed','cancelled'))
                        OR (r.state IN ('running','verifying') AND c.state IN ('failed','cancelled'))
                        OR (r.state IN ('running','verifying') AND NOT EXISTS(SELECT 1 FROM inv.shard_commands z JOIN inv.runs u ON (z.tenant_id,z.run_id)=(u.tenant_id,u.run_id) WHERE (z.tenant_id,z.project_id,z.plan_id)=(p.tenant_id,p.project_id,p.plan_id) AND u.state<>'succeeded'))))
                ORDER BY p.plan_id LIMIT 1""",
                (self.db.recovery_epoch, command_id, command_id),
            ).fetchone()
            if not plan:
                return "idle"
            from .shards import ShardRuntime

            members = ShardRuntime._lock_members(conn, plan["project_id"], plan["plan_id"])
            parent = lock_run(conn, plan["run_id"], plan["project_id"])
            if parent["state"] == "succeeded":
                return "idle"
            failed = any(run["state"] in {"failed", "cancelled"} for _, run in members)
            if parent["state"] in {"failed", "cancelled"} or failed:
                for _, run in members:
                    if run["state"] not in TERMINAL:
                        RunStore(self.db)._transition(
                            conn, tenant, run, "cancelled", run["version"]
                        )
                        event(
                            conn,
                            tenant,
                            run["run_id"],
                            "inv.run.cancel_requested",
                            {"planId": plan["plan_id"], "reason": "shard_fail_fast"},
                        )
                if parent["state"] not in TERMINAL:
                    RunStore(self.db)._transition(conn, tenant, parent, "failed", parent["version"])
                    event(
                        conn,
                        tenant,
                        parent["run_id"],
                        "inv.shard.parent_failed",
                        {"planId": plan["plan_id"]},
                    )
                return "failed"
            if files is None or not all(run["state"] == "succeeded" for _, run in members):
                return "idle"
            rows = conn.execute(
                """SELECT s.shard_index,s.run_id,s.command_id,c.evidence_id,p.object_id,o.content_hash,o.size_bytes,o.state
                FROM inv.shard_commands s JOIN inv.runs r ON (s.tenant_id,s.run_id)=(r.tenant_id,r.run_id)
                JOIN inv.result_completions c ON (s.tenant_id,s.command_id,r.attempt)=(c.tenant_id,c.command_id,c.attempt)
                JOIN inv.result_commitments p ON (c.tenant_id,c.command_id)=(p.tenant_id,p.command_id)
                JOIN inv.storage_objects o ON (p.tenant_id,p.project_id,p.object_id)=(o.tenant_id,o.project_id,o.object_id)
                WHERE s.project_id=%s AND s.plan_id=%s ORDER BY s.shard_index""",
                (plan["project_id"], plan["plan_id"]),
            ).fetchall()
            if len(rows) != len(members) or any(r["state"] != "ready" for r in rows):
                return "idle"
            for row in rows:
                files.read(object_key(row["object_id"]), row["content_hash"], row["size_bytes"])
            manifest = [
                {
                    "index": r["shard_index"],
                    "runId": r["run_id"],
                    "commandId": str(r["command_id"]),
                    "evidenceId": r["evidence_id"],
                    "objectId": str(r["object_id"]),
                    "sha256": r["content_hash"],
                    "sizeBytes": r["size_bytes"],
                }
                for r in rows
            ]
            source = conn.execute(
                "SELECT request_hash FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s",
                (plan["project_id"], plan["plan_id"]),
            ).fetchone()["request_hash"]
            decision = str(uuid4())
            envelope = {
                "evidenceId": new_id("evd"),
                "tenantId": tenant,
                "runId": parent["run_id"],
                "traceId": uuid4().hex,
                "timestamp": conn.execute("SELECT clock_timestamp() AS now")
                .fetchone()["now"]
                .isoformat(),
                "actorId": "shard-completion:v1",
                "action": "aggregate-verified-shards",
                "policyDecisionId": decision,
                "inputSha256": source,
                "outputSha256": digest(manifest),
                "result": "succeeded",
            }
            validate_contract("EvidenceEnvelope", envelope)
            conn.execute(
                "INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES(%s,%s,%s,%s)",
                (tenant, parent["run_id"], envelope["evidenceId"], Jsonb(envelope)),
            )
            conn.execute(
                "INSERT INTO inv.shard_completions(tenant_id,project_id,plan_id,run_id,evidence_id,manifest,manifest_hash,policy_decision_id,policy_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    tenant,
                    plan["project_id"],
                    plan["plan_id"],
                    parent["run_id"],
                    envelope["evidenceId"],
                    Jsonb(manifest),
                    digest(manifest),
                    decision,
                    "shard-completion:v1",
                ),
            )
            store = RunStore(self.db)
            if parent["state"] == "running":
                store._transition(conn, tenant, parent, "verifying", parent["version"])
                parent = lock_run(conn, parent["run_id"], plan["project_id"])
            store._transition(
                conn, tenant, parent, "succeeded", parent["version"], evidence_ready=True
            )
            event(
                conn,
                tenant,
                parent["run_id"],
                "inv.shard.parent_completed",
                {"planId": plan["plan_id"], "manifestSha256": digest(manifest)},
            )
            return "completed"
