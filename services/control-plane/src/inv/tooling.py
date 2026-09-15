"""Durable ToolGateway admission. This module does not launch a process.

Trusted adapters supply NodePrincipal, current PDP snapshot, runtime capabilities,
and immutable configuration. No browser-provided identity or claims are accepted.
Lock order: Run -> Approval -> Node/Resource -> sorted grants. Existing writers
never acquire an earlier lock after a later one. PDP/transport I/O stays outside tx.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from .approvals import ApprovalStore, digest
from .contracts import validate_contract
from .db import Database
from .errors import DomainError
from .leases import lock_run, lock_resources, assert_fences, wire
from .policy import action_digest, enforce_decision
from .runs import event
from .sandbox import SandboxProfile, RuntimeCapabilities, compile_launch


@dataclass(frozen=True)
class NodePrincipal:
    tenant_id: str
    node_id: str

    def __post_init__(self):
        if str(UUID(self.tenant_id)) != self.tenant_id:
            raise ValueError("Canonical verified tenant required")
        validate_contract("NodeId", self.node_id)


@dataclass(frozen=True)
class CurrentPolicy:
    version: str
    evaluated_at: datetime
    decision: dict


@dataclass(frozen=True)
class ClaimResult:
    may_start: bool
    claim: dict
    launch: dict | None


def claim_view(row):
    return {
        "commandId": str(row["command_id"]),
        "claimId": str(row["claim_id"]),
        "runId": row["run_id"],
        "tenantId": str(row["tenant_id"]),
        "projectId": row["project_id"],
        "nodeId": row["node_id"],
        "actionDigest": row["action_digest"],
        "planDigest": row["plan_digest"],
        "policyVersion": row["policy_version"],
        "profileVersion": row["profile_version"],
        "recoveryEpoch": str(row["recovery_epoch"]),
        "notAfter": row["not_after"].isoformat(),
    }


class ToolGateway:
    def __init__(self, database: Database, profile: SandboxProfile):
        self.db = database
        self.profile = profile
        self.approvals = ApprovalStore(database)

    def claim(
        self,
        node: NodePrincipal,
        command,
        workload,
        proofs,
        *,
        policy: CurrentPolicy,
        runtime: RuntimeCapabilities,
        queue_signing_key=None,
    ):
        # Snapshot mutable input before validation/hash use; no callback may mutate it.
        command = deepcopy(command)
        workload = deepcopy(workload)
        proofs = deepcopy(proofs)
        validate_contract("AuthorizedCommand", command)
        validate_contract("WorkloadSpec", workload)
        if ("workspaceResume" in workload or "workspaceStart" in workload) and (
            queue_signing_key is None or not getattr(self.db, "workspace_admission", False)
        ):
            raise DomainError(
                "AUTH-0044", "Workspace Steps require atomic reservation and delivery", 403
            )
        if (
            command["tenantId"] != node.tenant_id
            or workload["tenantId"] != node.tenant_id
            or workload["projectId"] != command["projectId"]
            or workload.get("targetNodeId", node.node_id) != node.node_id
        ):
            raise DomainError("AUTH-0011", "Execution scope differs", 403)
        if not isinstance(proofs, dict) or not proofs or len(proofs) > 128:
            raise DomainError("LEASE-0002", "Execution allocation set does not match")
        for lease_id, token in proofs.items():
            validate_contract("LeaseId", lease_id)
            if type(token) is not str or len(token) > 100:
                raise DomainError("LEASE-0002", "Invalid allocation proof")
        request_hash = digest(
            {
                "command": command,
                "workload": workload,
                "proofs": proofs,
                "node": node.node_id,
            }
        )
        with self.db.transaction(node.tenant_id) as conn:
            run = lock_run(conn, command["runId"], command["projectId"])
            from .shard_recovery import require_recovery_admission

            require_recovery_admission(conn, self.db, run["run_id"])
            from .business_handoff import require_handoff

            require_handoff(conn, self.db, run["run_id"])
            from .workspace_start import require_start_admission

            require_start_admission(conn, self.db, run["run_id"])
            from .model_locality import require_model_admission

            require_model_admission(conn, run["run_id"])
            prior = conn.execute(
                "SELECT * FROM inv.tool_claims WHERE command_id=%s",
                (command["commandId"],),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise DomainError(
                        "IDEM-0001", "Command already has different execution content"
                    )
                if (
                    queue_signing_key is not None
                    and not conn.execute(
                        "SELECT 1 FROM inv.execution_deliveries WHERE command_id=%s",
                        (command["commandId"],),
                    ).fetchone()
                ):
                    raise DomainError(
                        "NODE-0061",
                        "Existing transient claim requires observation; it cannot be queued",
                        409,
                    )
                # A replay is an observation, never a renewed launch permission. This
                # remains false after cancellation, expiry, or lost first response.
                return ClaimResult(False, claim_view(prior), None)
            from .containment import require_execution

            require_execution(conn)
            approval = conn.execute(
                "SELECT * FROM inv.approval_requests WHERE approval_id=%s AND run_id=%s FOR SHARE",
                (command["approvalId"], command["runId"]),
            ).fetchone()
            dispatch = conn.execute(
                "SELECT command_id FROM inv.approval_dispatches WHERE approval_id=%s",
                (command["approvalId"],),
            ).fetchone()
            if not approval or not dispatch or str(dispatch["command_id"]) != command["commandId"]:
                raise DomainError("AUTH-0040", "Durable approval dispatch is missing", 403)
            expected = {
                "commandId": str(dispatch["command_id"]),
                "approvalId": approval["approval_id"],
                "runId": approval["run_id"],
                "tenantId": str(approval["tenant_id"]),
                "projectId": approval["project_id"],
                "actionDigest": approval["action_digest"],
                "policyVersion": approval["policy_version"],
                "recoveryEpoch": str(approval["recovery_epoch"]),
                "expiresAt": approval["expires_at"].isoformat(),
            }
            if command != expected or action_digest(workload) != approval["action_digest"]:
                raise DomainError(
                    "AUTH-0040",
                    "Execution content differs from its durable approval",
                    403,
                )
            if (
                run["state"] != "scheduled"
                or run["version"] != approval["bound_run_version"] + 1
                or approval["status"] != "dispatched"
            ):
                raise DomainError(
                    "AUTH-0041",
                    "Run is not the current approved scheduled execution",
                    403,
                )
            allocations = conn.execute(
                "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
                (run["run_id"],),
            ).fetchall()
            resources = lock_resources(conn, [r["resource_id"] for r in allocations])
            assert_fences(conn, run["run_id"], proofs)
            if any(r["node_id"] != node.node_id for r in resources.values()):
                raise DomainError("AUTH-0042", "Allocation belongs to a different Node", 403)
            health = conn.execute(
                """SELECT status='online' AND heartbeat_at>=clock_timestamp()-interval '15 seconds'
                AND heartbeat_at<=clock_timestamp() AND abs(clock_skew_seconds)<=5 AND recovery_epoch=%s::uuid AS ready
                FROM inv.nodes WHERE node_id=%s""",
                (self.db.recovery_epoch, node.node_id),
            ).fetchone()
            if not health or not health["ready"]:
                raise DomainError("RES-0006", "Node is unavailable or heartbeat is stale", 503)
            totals = {}
            for allocation in allocations:
                kind = resources[allocation["resource_id"]]["kind"]
                totals[kind] = totals.get(kind, 0) + allocation["amount"]
            if (
                totals.get("cpu", 0) < workload["resources"]["cpuMillis"]
                or totals.get("memory", 0) < workload["resources"]["memoryBytes"]
            ):
                raise DomainError("RES-0001", "Allocation does not cover the workload limits")
            votes = conn.execute(
                "SELECT actor_id FROM inv.approval_votes WHERE approval_id=%s AND decision='approve' ORDER BY actor_id",
                (approval["approval_id"],),
            ).fetchall()
            actors = {v["actor_id"] for v in votes}
            requester = approval["requester_id"]
            if requester in actors or len(actors) < approval["required_approvals"]:
                raise DomainError("AUTH-0033", "Distinct approval quorum is missing", 403)
            for actor in sorted(actors | {requester}):
                self.approvals._grant(
                    conn,
                    command["projectId"],
                    actor,
                    "can_request" if actor == requester else "can_approve",
                )
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                approval["expires_at"] <= now
                or str(approval["recovery_epoch"]) != self.db.recovery_epoch
            ):
                raise DomainError(
                    "AUTH-0031",
                    "Approval expired or belongs to an old recovery epoch",
                    403,
                )
            if (
                not isinstance(policy, CurrentPolicy)
                or policy.version != approval["policy_version"]
                or not isinstance(policy.evaluated_at, datetime)
                or policy.evaluated_at.tzinfo is None
                or not now - timedelta(seconds=5) <= policy.evaluated_at <= now
            ):
                raise DomainError(
                    "AUTH-0043", "Current matching policy snapshot is unavailable", 403
                )
            decision = deepcopy(policy.decision)
            validate_contract("PolicyDecision", decision)
            expires = datetime.fromisoformat(decision["expiresAt"].replace("Z", "+00:00"))
            if (
                decision["approvedBy"]
                or not now < expires <= policy.evaluated_at + timedelta(seconds=30)
                or decision["requiredApprovals"] > approval["required_approvals"]
            ):
                raise DomainError("AUTH-0043", "Policy snapshot requires a new approval", 403)
            decision["approvedBy"] = sorted(actors)
            enforce_decision(
                decision,
                action=workload,
                tenant_id=node.tenant_id,
                project_id=command["projectId"],
                subject_id=requester,
                now=now,
            )
            if not isinstance(runtime, RuntimeCapabilities):
                raise DomainError("SANDBOX-0001", "Verified runtime is unavailable", 403)
            runtime.check(
                node_id=node.node_id,
                epoch=self.db.recovery_epoch,
                profile_version=self.profile.version,
                now=now,
            )
            workspace_input = None
            if "workspaceResume" in workload:
                from .workspace_resume import approved_resume

                workspace_input = approved_resume(conn, run, workload, self.db.recovery_epoch)
            elif "workspaceStart" in workload:
                from .workspace_start import approved_start

                workspace_input = approved_start(conn, run, workload, self.db.recovery_epoch)
            plan = compile_launch(workload, self.profile, workspace_input=workspace_input)
            deadline = min(
                approval["expires_at"],
                expires,
                runtime.expires_at,
                *[r["expires_at"] for r in allocations],
            )
            if (deadline - now).total_seconds() < 1:
                raise DomainError("AUTH-0043", "Insufficient admission validity remains", 403)
            row = conn.execute(
                """INSERT INTO inv.tool_claims(tenant_id,project_id,run_id,command_id,claim_id,node_id,
                request_hash,action_digest,plan_digest,policy_version,profile_version,policy_decision_id,recovery_epoch,not_after)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    node.tenant_id,
                    command["projectId"],
                    run["run_id"],
                    command["commandId"],
                    uuid4(),
                    node.node_id,
                    request_hash,
                    action_digest(workload),
                    digest(plan),
                    policy.version,
                    self.profile.version,
                    decision["decisionId"],
                    self.db.recovery_epoch,
                    deadline,
                ),
            ).fetchone()
            result = claim_view(row)
            validate_contract("ExecutionClaim", result)
            event(conn, node.tenant_id, run["run_id"], "inv.execution.claimed", result)
            admitted = ClaimResult(True, result, plan)
            if queue_signing_key is not None:
                from .dispatch import persist_delivery

                allocations = [
                    {
                        "nodeId": node.node_id,
                        "kind": resources[r["resource_id"]]["kind"],
                        "lease": wire(r),
                    }
                    for r in allocations
                ]
                persist_delivery(conn, admitted, allocations, queue_signing_key, now=now)
                # Only the durable queue may start this command. Do not also grant
                # the caller a transient, separately sealable launch permission.
                return ClaimResult(False, result, None)
            return admitted
