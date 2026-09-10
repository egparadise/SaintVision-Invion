"""Fresh approval, physical fencing and at most three independent generations.

Trusted service adapter; targets are operator-configured restricted Node runtimes.
Every shard is rerun with the identical WorkloadSpec and a new Run/approval. No
partial result adoption, implicit collective communication or uncertain restart.
"""

from copy import deepcopy
from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .contracts import validate_contract
from .control import Control
from .db import BoundDatabase
from .errors import DomainError
from .leases import LeaseStore, lock_run, lock_resources
from .policy import action_digest
from .runs import RunStore, event
from .shards import ShardAdmission, ShardRuntime
from .state import TERMINAL


def require_recovery_admission(conn, db, run_id):
    if (
        not getattr(db, "shard_recovery_admission", False)
        and conn.execute(
            "SELECT 1 FROM inv.shard_recovery_members WHERE run_id=%s", (run_id,)
        ).fetchone()
    ):
        raise DomainError("AUTH-0045", "Shard replacement requires atomic recovery admission", 403)


class ShardRecovery:
    def __init__(self, database, targets):
        self.db, self.targets = database, dict(targets)
        if not self.targets or any(k != v.node.node_id for k, v in self.targets.items()):
            raise ValueError("Explicit Node runtime mapping required")
        self.ledger, self.control = ApprovalStore(database), Control(database)

    def _target(self, principal, node_id):
        validate_contract("NodeId", node_id)
        target = self.targets.get(node_id)
        if target is None or target.node.tenant_id != principal.tenant_id:
            raise DomainError("AUTH-0030", "Configured replacement Node unavailable", 403)
        return target

    @staticmethod
    def _project(conn, project):
        validate_contract("ProjectId", project)
        if not conn.execute(
            "SELECT 1 FROM inv.projects WHERE project_id=%s", (project,)
        ).fetchone():
            raise DomainError("RES-0004", "Project unavailable", 404)

    @staticmethod
    def _membership(conn, project, node_id, *, lock=False):
        row = conn.execute(
            "SELECT enabled FROM inv.project_nodes WHERE project_id=%s AND node_id=%s"
            + (" FOR SHARE" if lock else ""),
            (project, node_id),
        ).fetchone()
        if not row or not row["enabled"]:
            raise DomainError("AUTH-0030", "Project Node membership unavailable", 403)

    def _source(self, conn, project, source_id):
        lineage = conn.execute(
            "SELECT root_plan_id,generation FROM inv.shard_recoveries WHERE project_id=%s AND plan_id=%s",
            (project, source_id),
        ).fetchone()
        root = lineage["root_plan_id"] if lineage else source_id
        # Serialize all generations before plan -> sorted children -> parent.
        conn.execute(
            "SELECT plan_id FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s FOR UPDATE",
            (project, root),
        ).fetchone()
        members = ShardRuntime._lock_members(conn, project, source_id)
        link = conn.execute(
            "SELECT run_id,recovery_epoch FROM inv.shard_parents WHERE project_id=%s AND plan_id=%s",
            (project, source_id),
        ).fetchone()
        parent = lock_run(conn, link["run_id"], project) if link else None
        if not parent or parent["state"] not in {"failed", "cancelled"}:
            raise DomainError("NODE-0063", "Recovery requires a failed or cancelled parent")
        generation = (lineage["generation"] if lineage else 1) + 1
        if generation > 3:
            raise DomainError("NODE-0064", "Shard generation limit reached")
        if str(link["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("LEASE-0004", "Source epoch requires operator reconciliation", 503)
        for member, run in members:
            receipt = conn.execute(
                "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
                (member["command_id"],),
            ).fetchone()
            if (
                run["state"] not in TERMINAL
                or not receipt
                or receipt["envelope"]["recoveryEpoch"] != self.db.recovery_epoch
                or conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                    (run["run_id"],),
                ).fetchone()
            ):
                raise DomainError(
                    "LEASE-0003", "Every source shard requires verified physical stop"
                )
        successor = conn.execute(
            "SELECT plan_id FROM inv.shard_recoveries WHERE project_id=%s AND source_plan_id=%s",
            (project, source_id),
        ).fetchone()
        if successor:
            raise DomainError("NODE-0064", "Source plan already has a committed replacement")
        source = conn.execute(
            """SELECT s.shard_index,c.action_digest FROM inv.shard_commands s
            JOIN inv.tool_claims c USING(tenant_id,command_id)
            WHERE s.project_id=%s AND s.plan_id=%s ORDER BY s.shard_index""",
            (project, source_id),
        ).fetchall()
        return root, generation, source

    def prepare(self, principal, project, source_id, plan_id, intents, *, key):
        validate_contract(
            "ShardRecoveryPrepareInput",
            {"sourcePlanId": source_id, "planId": plan_id, "intents": intents},
        )
        if (
            not isinstance(plan_id, str)
            or not 1 <= len(plan_id) <= 200
            or plan_id == source_id
            or not isinstance(intents, list)
            or not 1 <= len(intents) <= 16
        ):
            raise DomainError("VAL-0003", "Bounded replacement plan required", 422)
        intents = deepcopy(intents)
        for intent in intents:
            if not isinstance(intent, dict) or set(intent) != {"nodeId", "workload"}:
                raise DomainError(
                    "VAL-0003", "Replacement intent requires Node and workload only", 422
                )
            validate_contract("WorkloadSpec", intent["workload"])
            if "workspaceResume" in intent["workload"]:
                raise DomainError(
                    "NODE-0063", "Workspace transfer requires a separate recovery contract"
                )
            self._target(principal, intent["nodeId"])
        payload = {"sourcePlanId": source_id, "planId": plan_id, "intents": intents}
        with self.db.transaction(principal.tenant_id) as conn:
            self._project(conn, project)
            prior = self.ledger._ledger(
                conn, principal, project, "shard.recovery.prepare", key, payload
            )
            if prior is not None:
                self.control.grant(conn, principal, project, "can_request")
                return prior
            _, generation, source = self._source(conn, project, source_id)
            self.control.grant(conn, principal, project, "can_request")
            if len(source) != len(intents) or any(
                action_digest(intent["workload"]) != old["action_digest"]
                for intent, old in zip(intents, source)
            ):
                raise DomainError(
                    "AUTH-0011", "Replacement must preserve every ordered source action", 403
                )
            if conn.execute(
                "SELECT 1 FROM inv.shard_recovery_requests WHERE project_id=%s AND plan_id=%s UNION ALL SELECT 1 FROM inv.shard_plans WHERE project_id=%s AND plan_id=%s",
                (project, plan_id, project, plan_id),
            ).fetchone():
                raise DomainError("IDEM-0001", "Replacement plan identity is already used")
            conn.execute(
                "INSERT INTO inv.shard_recovery_requests(tenant_id,project_id,plan_id,source_plan_id,requester_id,recovery_epoch) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    principal.tenant_id,
                    project,
                    plan_id,
                    source_id,
                    principal.subject_id,
                    self.db.recovery_epoch,
                ),
            )
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            runs, approvals, prepared = RunStore(bound), ApprovalStore(bound), []
            for index, intent in enumerate(intents):
                target = self._target(principal, intent["nodeId"])
                self._membership(conn, project, target.node.node_id)
                policy = target.policy(principal, intent["workload"], for_approval=True)
                run = runs.create(principal.tenant_id, project)
                for state in ("validated", "planned"):
                    run = runs.transition(
                        principal.tenant_id, run["runId"], state, expected_version=run["version"]
                    )
                approval = approvals.request(
                    principal,
                    run["runId"],
                    intent["workload"],
                    policy.decision,
                    policy_version=policy.version,
                    expected_version=run["version"],
                    key=run["runId"],
                )
                conn.execute(
                    "INSERT INTO inv.shard_recovery_members VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        principal.tenant_id,
                        project,
                        plan_id,
                        index,
                        run["runId"],
                        approval["approvalId"],
                        intent["nodeId"],
                        Jsonb(intent["workload"]),
                    ),
                )
                prepared.append(
                    {
                        "index": index,
                        "runId": run["runId"],
                        "nodeId": intent["nodeId"],
                        "approval": approval,
                    }
                )
            result = {
                "planId": plan_id,
                "sourcePlanId": source_id,
                "generation": generation,
                "shards": prepared,
            }
            validate_contract("ShardRecoveryPrepared", result)
            return self.ledger._save(conn, project, "shard.recovery.prepare", key, result)

    def _request(self, conn, principal, project, plan_id):
        row = conn.execute(
            "SELECT * FROM inv.shard_recovery_requests WHERE project_id=%s AND plan_id=%s",
            (project, plan_id),
        ).fetchone()
        if not row or row["requester_id"] != principal.subject_id:
            raise DomainError("RES-0004", "Replacement request unavailable", 404)
        if str(row["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("LEASE-0004", "Replacement request epoch is stale", 503)
        members = conn.execute(
            "SELECT * FROM inv.shard_recovery_members WHERE project_id=%s AND plan_id=%s ORDER BY shard_index",
            (project, plan_id),
        ).fetchall()
        return row, members

    def enqueue(self, principal, project, plan_id, *, key):
        validate_contract("ShardPlanId", plan_id)
        payload = {"planId": plan_id}
        with self.db.transaction(principal.tenant_id) as conn:
            self._project(conn, project)
            prior = self.ledger._ledger(
                conn, principal, project, "shard.recovery.enqueue", key, payload
            )
            self.control.grant(conn, principal, project, "can_request")
            if prior is not None:
                return prior
            request, members = self._request(conn, principal, project, plan_id)
            for member in members:
                self._membership(conn, project, member["node_id"])
        # No network operations under database locks, and no authority from a caller.
        targets = {m["node_id"]: self._target(principal, m["node_id"]) for m in members}
        if len({target.profile for target in targets.values()}) != 1:
            raise DomainError("SANDBOX-0001", "One common restricted shard profile required", 403)
        observed = {node: target.observe() for node, target in sorted(targets.items())}
        policies = {
            m["run_id"]: targets[m["node_id"]].policy(principal, m["workload"]) for m in members
        }
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.ledger._ledger(
                conn, principal, project, "shard.recovery.enqueue", key, payload
            )
            if prior is not None:
                self.control.grant(conn, principal, project, "can_request")
                return prior
            request, members = self._request(conn, principal, project, plan_id)
            root, generation, _ = self._source(conn, project, request["source_plan_id"])
            for member in sorted(members, key=lambda m: m["run_id"]):
                run = lock_run(conn, member["run_id"], project)
                if run["state"] != "awaiting_approval":
                    raise DomainError("GRAPH-0003", "Replacement Run changed before admission")
            for approval_id in sorted(m["approval_id"] for m in members):
                conn.execute(
                    "SELECT approval_id FROM inv.approval_requests WHERE approval_id=%s FOR UPDATE",
                    (approval_id,),
                ).fetchone()
            # Reserve all Nodes/Resources in one global order before per-Run calls.
            conn.execute(
                "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE",
                (project,),
            ).fetchone()
            conn.execute(
                "SELECT project_id FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE",
                (project,),
            ).fetchone()
            lock_resources(
                conn,
                sorted(
                    {
                        a.resource_id
                        for m in members
                        for a in targets[m["node_id"]].allocations(m["workload"])
                    }
                ),
            )
            for node in sorted(targets):
                self._membership(conn, project, node, lock=True)
            conn.execute(
                "SELECT subject_id FROM inv.project_grants WHERE project_id=%s ORDER BY subject_id FOR SHARE",
                (project,),
            ).fetchall()
            self.control.grant(conn, principal, project, "can_request")
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            bound.shard_recovery_admission = True
            shards = []
            for member in members:
                target = targets[member["node_id"]]
                command = ApprovalStore(bound).dispatch(
                    principal,
                    project,
                    member["approval_id"],
                    member["workload"],
                    key=member["run_id"],
                )
                leases = LeaseStore(bound).reserve(
                    principal.tenant_id,
                    project,
                    member["run_id"],
                    target.allocations(member["workload"]),
                    key=member["run_id"],
                    ttl_seconds=60,
                )
                shards.append(
                    ShardAdmission(
                        target.node,
                        command,
                        member["workload"],
                        {l["leaseId"]: l["fencingToken"] for l in leases},
                        policies[member["run_id"]],
                        observed[member["node_id"]],
                    )
                )
            # The profile is common; each target may pin its own signing public key.
            runtime = ShardRuntime(bound, next(iter(targets.values())).profile)
            result = runtime.enqueue(
                principal.tenant_id,
                project,
                plan_id,
                shards,
                signing_key={k: v.signing_key for k, v in targets.items()},
                splittable=True,
            )
            conn.execute(
                "INSERT INTO inv.shard_recoveries(tenant_id,project_id,plan_id,source_plan_id,root_plan_id,generation,recovery_epoch) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    principal.tenant_id,
                    project,
                    plan_id,
                    request["source_plan_id"],
                    root,
                    generation,
                    self.db.recovery_epoch,
                ),
            )
            result.update(
                sourcePlanId=request["source_plan_id"], rootPlanId=root, generation=generation
            )
            validate_contract("ShardRecoveryEnqueued", result)
            event(
                conn,
                principal.tenant_id,
                result["parentRunId"],
                "inv.shard.replacement_queued",
                result,
            )
            return self.ledger._save(conn, project, "shard.recovery.enqueue", key, result)
