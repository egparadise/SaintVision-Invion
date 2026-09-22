"""Authenticated Workspace admission against the execution kernel's own rows.

The operator installs the restricted policy/profile and pins the Node. A browser
supplies intent, never a policy decision, authenticated Node, lease or signing key.
Network observation happens before the final transaction. The Run, current grants,
approval, reservation, claim and queue are checked/committed together afterwards.
"""

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from time import sleep

from .approvals import ApprovalStore, digest, view
from .contracts import validate_contract
from .control import Control
from .db import BoundDatabase
from .errors import DomainError
from .leases import Allocation, lock_run
from .observation import NodeObservation
from .policy import action_digest
from .runs import public
from .sandbox import REQUIRED_CAPABILITIES, RuntimeCapabilities, compile_launch
from .snapshots import identity
from .tooling import CurrentPolicy
from .workspace_files import decode_snapshot
from .workspace_resume import WorkspaceResume


class RestrictedWorkspaceRuntime:
    """Operator-approved L2 profile, two distinct votes, one pinned Linux Node.

    The profile is an operator trust assertion about the installed restricted agent.
    A fresh nonce/mTLS probe confirms its identity/epoch/profile; it does not certify
    arbitrary OS/GPU/BuildKit capabilities. Node runtime enforces the launch again.
    """

    def __init__(self, database, *, profile, node, resources, signing_key, policy_version, client):
        if set(resources) != {"cpu", "memory"} or not policy_version:
            raise ValueError("Explicit CPU/memory allocation and policy version required")
        for resource in resources.values():
            validate_contract("ResourceId", resource)
        if len(set(resources.values())) != 2:
            raise ValueError("Distinct CPU and memory resources required")
        self.db, self.profile, self.node = database, profile, node
        self.resources, self.signing_key = dict(resources), signing_key
        self.policy_version, self.client = policy_version, client
        self.destinations = {}

    def for_workload(self, workload):
        target = workload.get("targetNodeId", self.node.node_id)
        if target == self.node.node_id:
            return self
        destination = self.destinations.get(target)
        if destination is None or destination.node.tenant_id != self.node.tenant_id:
            raise DomainError("AUTH-0030", "Target Node is not configured for this Workspace", 403)
        return destination

    def policy(self, principal, workload, *, for_approval=False):
        if (
            principal.tenant_id != self.node.tenant_id
            or workload["tenantId"] != principal.tenant_id
        ):
            raise DomainError("AUTH-0011", "Configured Workspace tenant differs", 403)
        intent = deepcopy(workload)
        intent.pop("workspaceResume", None)
        intent.pop("workspaceStart", None)
        if intent.pop("terminal", None) is not None and (
            not self.profile.allow_terminal
            or sum(name in workload for name in ("workspaceResume", "workspaceStart")) != 1
        ):
            raise DomainError("SANDBOX-0002", "Explicit frozen terminal policy required", 403)
        compile_launch(intent, self.profile)
        now = datetime.now(timezone.utc)
        return CurrentPolicy(
            self.policy_version,
            now,
            {
                "decisionId": str(uuid4()),
                "tenantId": principal.tenant_id,
                "projectId": workload["projectId"],
                "subjectId": principal.subject_id,
                "effect": "require_approval",
                "riskLevel": "L2",
                "actionDigest": action_digest(workload),
                "expiresAt": (now + timedelta(seconds=600 if for_approval else 30)).isoformat(),
                "requiredApprovals": 2,
                "approvedBy": [],
            },
        )

    def observe(self):
        for attempt in range(3):
            try:
                # A concurrent fresh probe may have overtaken this response.
                # Retry with a NEW nonce; never accept the superseded response.
                observation = NodeObservation(self.db, self.client).poll(self.node)
                break
            except DomainError as error:
                if not (
                    attempt < 2
                    and error.code == "NODE-0050"
                    and error.status in {409, 503}
                    and error.retryable
                ):
                    raise
                sleep(0.01 * (2**attempt))
        if observation["profileVersion"] != self.profile.version:
            raise DomainError("SANDBOX-0001", "Observed Node profile differs", 403)
        return RuntimeCapabilities(
            self.node.node_id,
            self.db.recovery_epoch,
            self.profile.version,
            datetime.now(timezone.utc) + timedelta(seconds=20),
            REQUIRED_CAPABILITIES,
        )

    def allocations(self, workload):
        return [
            Allocation(self.resources["cpu"], workload["resources"]["cpuMillis"]),
            Allocation(self.resources["memory"], workload["resources"]["memoryBytes"]),
        ]


class WorkspaceAPI:
    def __init__(self, database, working, runtime):
        self.db, self.working, self.runtime = database, working, runtime
        self.control, self.ledger = Control(database), ApprovalStore(database)

    def _scope(self, conn, principal, project, run_id):
        validate_contract("RunId", run_id)
        run = lock_run(conn, run_id, project)
        self.control.grant(conn, principal, project, "can_request")
        return run

    def _node_membership(self, conn, project, *, lock=False, runtime=None):
        # Preflight is read-only. The final row lock follows admission's Node
        # locks, matching placement/provisioning; failure rolls admission back.
        query = "SELECT enabled FROM inv.project_nodes WHERE project_id=%s AND node_id=%s"
        row = conn.execute(
            query + (" FOR SHARE" if lock else ""),
            (project, (runtime or self.runtime).node.node_id),
        ).fetchone()
        if not row or not row["enabled"]:
            raise DomainError("AUTH-0030", "Project Node membership unavailable", 403)

    def prepare(self, principal, project, run_id, data, key, *, root_fd=None):
        validate_contract("WorkspacePrepareInput", data)
        workload = deepcopy(data["workload"])
        if (
            workload["tenantId"] != principal.tenant_id
            or workload["projectId"] != project
            or "workspaceResume" in workload
            or "workspaceStart" in workload
        ):
            raise DomainError("AUTH-0011", "Workspace intent scope differs", 403)
        checkout_id, resume_id = identity(data["checkoutId"]), identity(data["resumeId"])
        # All service writers must use this root lock. External writers have no
        # service ownership; capture detects races and fails instead of approving
        # a torn snapshot. Frozen bytes are immutable even after later edits.
        root_lock = self.working.locked() if root_fd is None else nullcontext(root_fd)
        with root_lock as root_fd, self.db.transaction(principal.tenant_id) as conn:
            from .business_handoff import require_handoff

            require_handoff(conn, self.db, run_id)
            prior = self.ledger._ledger(
                conn, principal, project, "workspace.api.prepare", key, {"runId": run_id, **data}
            )
            self._scope(conn, principal, project, run_id)
            if prior is not None:
                validate_contract("WorkspacePrepareResult", prior)
                return prior
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            frozen = WorkspaceResume(bound, self.working)._prepare(
                conn,
                root_fd,
                principal.tenant_id,
                project,
                run_id,
                checkout_id,
                resume_id,
                data["stepId"],
                workload,
                data["expectedVersion"],
                digest(
                    {
                        "api": data,
                        "runId": run_id,
                        "epoch": self.db.recovery_epoch,
                        "root": [str(self.working.root), *self.working.identity],
                    }
                ),
            )
            policy = self.runtime.for_workload(frozen["workload"]).policy(
                principal, frozen["workload"], for_approval=True
            )
            approval = ApprovalStore(bound).request(
                principal,
                run_id,
                frozen["workload"],
                policy.decision,
                policy_version=policy.version,
                expected_version=data["expectedVersion"],
                key="workspace-api:" + resume_id,
            )
            result = {
                "resumeId": resume_id,
                "workload": frozen["workload"],
                "approval": approval,
                "run": public(lock_run(conn, run_id, project)),
            }
            validate_contract("WorkspacePrepareResult", result)
            return self.ledger._save(conn, project, "workspace.api.prepare", key, result)

    @staticmethod
    def _frozen(conn, project, run_id, resume_id):
        row = conn.execute(
            "SELECT * FROM inv.workspace_resumptions WHERE project_id=%s AND run_id=%s AND resume_id=%s",
            (project, run_id, identity(resume_id)),
        ).fetchone()
        if not row:
            raise DomainError("STORE-0022", "Workspace resumption unavailable", 404)
        return row

    def get(self, principal, project, run_id, resume_id):
        with self.db.transaction(principal.tenant_id) as conn:
            run = lock_run(conn, run_id, project)
            self.control.grant(conn, principal, project)
            row = self._frozen(conn, project, run_id, resume_id)
            approval = conn.execute(
                "SELECT * FROM inv.approval_requests WHERE run_id=%s AND action_digest=%s ORDER BY bound_run_version DESC LIMIT 1",
                (run_id, action_digest(row["workload"])),
            ).fetchone()
            manifest, _ = decode_snapshot(bytes(row["snapshot"]), row["workspace_id"])
            result = {
                "resumeId": resume_id,
                "workload": row["workload"],
                "run": public(run),
                "approval": view(approval) if approval else None,
                "frozenFiles": [
                    {k: f[k] for k in ("path", "sizeBytes", "sha256")} for f in manifest["files"]
                ],
            }
            validate_contract("WorkspaceResumptionView", result)
            return result

    def enqueue(self, principal, project, run_id, data, key, *, binding_id=None):
        validate_contract("WorkspaceEnqueueInput", data)
        payload = {"runId": run_id, **data}
        # Persist only a retryable idempotency slot before network I/O. No approval
        # consumption, resource reservation or execution occurs in this preflight.
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.ledger._ledger(
                conn, principal, project, "workspace.api.enqueue", key, payload
            )
            self._scope(conn, principal, project, run_id)
            from .business_handoff import check_admission

            check_admission(
                conn,
                self.db,
                principal,
                project,
                run_id,
                data,
                binding_id,
                replay=prior is not None,
            )
            if prior is not None:
                validate_contract("WorkspaceEnqueueResult", prior)
                return prior
            frozen = self._frozen(conn, project, run_id, data["resumeId"])
            runtime = self.runtime.for_workload(frozen["workload"])
            self._node_membership(conn, project, runtime=runtime)
        capabilities = runtime.observe()
        policy = runtime.policy(principal, frozen["workload"])
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.ledger._ledger(
                conn, principal, project, "workspace.api.enqueue", key, payload
            )
            run = self._scope(conn, principal, project, run_id)
            check_admission(
                conn,
                self.db,
                principal,
                project,
                run_id,
                data,
                binding_id,
                replay=prior is not None,
            )
            if prior is not None:
                validate_contract("WorkspaceEnqueueResult", prior)
                return prior
            if run["version"] != data["expectedVersion"] or run["state"] != "awaiting_approval":
                raise DomainError("GRAPH-0003", "Current approved Run version required")
            frozen = self._frozen(conn, project, run_id, data["resumeId"])
            approval = conn.execute(
                "SELECT run_id FROM inv.approval_requests WHERE approval_id=%s FOR SHARE",
                (data["approvalId"],),
            ).fetchone()
            if not approval or approval["run_id"] != run_id:
                raise DomainError("AUTH-0011", "Approval Run differs", 403)
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            bound.business_handoff = binding_id is not None
            command = ApprovalStore(bound).dispatch(
                principal,
                project,
                data["approvalId"],
                frozen["workload"],
                key="workspace-api:" + data["resumeId"],
            )
            WorkspaceResume(bound, self.working).enqueue(
                runtime.node,
                command,
                frozen["workload"],
                runtime.allocations(frozen["workload"]),
                runtime.profile,
                policy=policy,
                runtime=capabilities,
                signing_key=runtime.signing_key,
                key="workspace-api:" + data["resumeId"],
            )
            self._node_membership(conn, project, lock=True, runtime=runtime)
            # Accepted into the durable queue; only the worker/Node can start it.
            result = {
                "resumeId": data["resumeId"],
                "runId": run_id,
                "commandId": command["commandId"],
                "accepted": True,
            }
            validate_contract("WorkspaceEnqueueResult", result)
            return self.ledger._save(conn, project, "workspace.api.enqueue", key, result)
