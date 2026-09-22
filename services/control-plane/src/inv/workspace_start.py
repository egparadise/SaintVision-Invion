"""First approved Workspace execution: immutable upload, attempt 1, no fake recovery.

No filesystem path, caller-supplied policy, token or resource lease enters this API.
The existing resource server authenticates identity; current project/business grants
are checked before and after Node observation. Approval/leases/queue commit together.
"""

import base64
from copy import deepcopy
import hashlib

from psycopg.types.json import Jsonb
from .approvals import ApprovalStore, digest, view
from .business_handoff import scope as business_scope
from .containment import require_execution
from .contracts import validate_contract
from .db import BoundDatabase
from .errors import DomainError
from .leases import lock_run
from .policy import action_digest
from .runs import public, event
from .snapshots import identity
from .workspace_files import decode_snapshot
from .workspace_resume import WorkspaceResume, bounded_snapshot, independent_run


def frozen_start(conn, project, run_id, start_id):
    row = conn.execute(
        "SELECT * FROM inv.workspace_starts WHERE project_id=%s AND run_id=%s AND start_id=%s",
        (project, run_id, identity(start_id)),
    ).fetchone()
    if not row:
        raise DomainError("STORE-0022", "First Workspace input unavailable", 404)
    return row


def approved_start(conn, run, workload, epoch):
    independent_run(conn, run["run_id"])
    ref = workload["workspaceStart"]
    row = frozen_start(conn, workload["projectId"], run["run_id"], ref["startId"])
    if (
        run["attempt"] != 0
        or str(row["recovery_epoch"]) != epoch
        or row["workload"] != workload
        or row["workspace_id"] != workload["workspaceId"]
    ):
        raise DomainError("AUTH-0044", "First Workspace input or epoch differs", 403)
    raw = bytes(row["snapshot"])
    bounded_snapshot(raw, workload["workspaceId"])
    if len(raw) != ref["inputSizeBytes"] or hashlib.sha256(raw).hexdigest() != ref["inputSha256"]:
        raise DomainError("VERIFY-0023", "First Workspace input bytes differ")
    return dict(
        startId=ref["startId"],
        stepId=ref["stepId"],
        sha256=ref["inputSha256"],
        sizeBytes=len(raw),
        dataBase64=base64.b64encode(raw).decode(),
    )


def require_start_admission(conn, database, run_id):
    if (
        not getattr(database, "workspace_admission", False)
        and conn.execute(
            "SELECT 1 FROM inv.workspace_starts s JOIN inv.runs r USING(tenant_id,run_id) WHERE s.run_id=%s AND r.attempt=0",
            (run_id,),
        ).fetchone()
    ):
        raise DomainError("AUTH-0044", "First Workspace execution requires atomic admission", 403)


class WorkspaceStart:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db, self.runtime = workspace.db, workspace.runtime
        self.control, self.ledger = workspace.control, workspace.ledger

    def _runtime_binding(self):
        return dict(
            nodeId=self.runtime.node.node_id,
            profileVersion=self.runtime.profile.version,
            policyVersion=self.runtime.policy_version,
            cpuResourceId=self.runtime.resources["cpu"],
            memoryResourceId=self.runtime.resources["memory"],
        )

    def _scope(
        self,
        conn,
        principal,
        project,
        run_id,
        workload,
        *,
        required="can_request",
        current_intent=True,
    ):
        run = lock_run(conn, run_id, project)
        self.control.grant(conn, principal, project, required)
        linked = conn.execute(
            "SELECT 1 FROM inv.business_projects WHERE project_id=%s", (project,)
        ).fetchone()
        if linked:
            # Business service owns creation of public metadata and the mapping.
            # Both authorities must agree; a missing mapping is never a fallback.
            run, _, current = business_scope(conn, self.db, principal, project, run_id, required)
            intent = deepcopy(workload)
            intent.pop("workspaceStart", None)
            if current_intent and (
                current["status"] != "ready"
                or current["workspace_id"] != intent["workspaceId"]
                or current["spec"] != intent
                or current["spec_sha256"] != digest(intent)
            ):
                raise DomainError("AUTH-0045", "Current business Workspace intent required", 403)
        return run, bool(linked)

    def prepare(self, principal, project, run_id, data, key):
        validate_contract("RunId", run_id)
        validate_contract("WorkspaceStartPrepareInput", data)
        workload = deepcopy(data["workload"])
        if (
            workload["tenantId"] != principal.tenant_id
            or workload["projectId"] != project
            or "workspaceResume" in workload
            or "workspaceStart" in workload
            or data["targetNodeId"] != self.runtime.node.node_id
            or workload.get("targetNodeId", data["targetNodeId"]) != data["targetNodeId"]
        ):
            raise DomainError("AUTH-0011", "First Workspace intent scope differs", 403)
        start_id = identity(data["startId"])
        try:
            raw = base64.b64decode(data["snapshotBase64"], validate=True)
            if base64.b64encode(raw).decode() != data["snapshotBase64"]:
                raise ValueError()
        except ValueError:
            raise DomainError("VAL-0003", "Canonical base64 input required", 422) from None
        bounded_snapshot(raw, workload["workspaceId"])
        payload = {"runId": run_id, **data}
        # Ledger stores a request digest, not uploaded bytes or untrusted logs.
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.ledger._ledger(
                conn, principal, project, "workspace.start.prepare", key, payload
            )
            run, linked = self._scope(conn, principal, project, run_id, workload)
            if prior is not None:
                validate_contract("WorkspaceStartPrepareResult", prior)
                return prior
            require_execution(conn)
            independent_run(conn, run_id)
            self.workspace._node_membership(conn, project)
            if (
                run["state"] != "draft"
                or run["attempt"] != 0
                or run["version"] != data["expectedVersion"]
            ):
                raise DomainError("GRAPH-0003", "First execution requires current draft Run")
            if conn.execute(
                "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (run_id,),
            ).fetchone():
                raise DomainError("LEASE-0003", "First execution cannot inherit reservations")
            if conn.execute(
                "SELECT 1 FROM inv.workspace_starts WHERE start_id=%s", (start_id,)
            ).fetchone():
                raise DomainError("IDEM-0001", "First input identity is already used")
            workload["workspaceStart"] = dict(
                startId=start_id,
                stepId=data["stepId"],
                inputSha256=hashlib.sha256(raw).hexdigest(),
                inputSizeBytes=len(raw),
                **self._runtime_binding(),
            )
            policy = self.runtime.policy(principal, workload, for_approval=True)
            conn.execute(
                """INSERT INTO inv.workspace_starts
                (tenant_id,project_id,run_id,start_id,workspace_id,step_id,requester_id,recovery_epoch,workload,snapshot)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    principal.tenant_id,
                    project,
                    run_id,
                    start_id,
                    workload["workspaceId"],
                    data["stepId"],
                    principal.subject_id,
                    self.db.recovery_epoch,
                    Jsonb(workload),
                    raw,
                ),
            )
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            bound.business_handoff = linked
            for target in ("validated", "planned"):
                changed = self.control.runs._transition(
                    conn, principal.tenant_id, run, target, run["version"]
                )
                run = lock_run(conn, run_id, project)
            approval = ApprovalStore(bound).request(
                principal,
                run_id,
                workload,
                policy.decision,
                policy_version=policy.version,
                expected_version=changed["version"],
                key="workspace-start:" + start_id,
            )
            result = dict(
                startId=start_id,
                workload=workload,
                approval=approval,
                run=public(lock_run(conn, run_id, project)),
            )
            validate_contract("WorkspaceStartPrepareResult", result)
            event(
                conn,
                principal.tenant_id,
                run_id,
                "inv.workspace.start_prepared",
                workload["workspaceStart"],
            )
            return self.ledger._save(conn, project, "workspace.start.prepare", key, result)

    def get(self, principal, project, run_id, start_id):
        validate_contract("RunId", run_id)
        with self.db.transaction(principal.tenant_id) as conn:
            self.control.grant(conn, principal, project)
            row = frozen_start(conn, project, run_id, start_id)
            run, _ = self._scope(
                conn,
                principal,
                project,
                run_id,
                row["workload"],
                required=None,
                current_intent=False,
            )
            approval = conn.execute(
                "SELECT * FROM inv.approval_requests WHERE run_id=%s AND action_digest=%s",
                (run_id, action_digest(row["workload"])),
            ).fetchone()
            manifest, _ = decode_snapshot(bytes(row["snapshot"]), row["workspace_id"])
            result = dict(
                startId=start_id,
                workload=row["workload"],
                run=public(run),
                approval=view(approval) if approval else None,
                frozenFiles=[
                    {k: f[k] for k in ("path", "sizeBytes", "sha256")} for f in manifest["files"]
                ],
            )
            validate_contract("WorkspaceStartView", result)
            return result

    def _preflight(self, conn, principal, project, run_id, data, key):
        prior = self.ledger._ledger(
            conn, principal, project, "workspace.start.enqueue", key, {"runId": run_id, **data}
        )
        self.control.grant(conn, principal, project, "can_request")
        row = frozen_start(conn, project, run_id, data["startId"])
        run, linked = self._scope(
            conn, principal, project, run_id, row["workload"], current_intent=prior is None
        )
        if row["requester_id"] != principal.subject_id:
            raise DomainError("AUTH-0045", "First input belongs to another requester", 403)
        if prior is None and any(
            row["workload"]["workspaceStart"][k] != v for k, v in self._runtime_binding().items()
        ):
            raise DomainError(
                "AUTH-0044", "Approved Node, resources or runtime version changed", 403
            )
        return prior, row, run, linked

    def enqueue(self, principal, project, run_id, data, key):
        validate_contract("RunId", run_id)
        validate_contract("WorkspaceStartEnqueueInput", data)
        with self.db.transaction(principal.tenant_id) as conn:
            prior, frozen, _, _ = self._preflight(conn, principal, project, run_id, data, key)
            if prior is not None:
                validate_contract("WorkspaceStartEnqueueResult", prior)
                return prior
            self.workspace._node_membership(conn, project)
        capabilities = self.runtime.observe()
        policy = self.runtime.policy(principal, frozen["workload"])
        with self.db.transaction(principal.tenant_id) as conn:
            prior, frozen, run, linked = self._preflight(
                conn, principal, project, run_id, data, key
            )
            if prior is not None:
                validate_contract("WorkspaceStartEnqueueResult", prior)
                return prior
            if run["version"] != data["expectedVersion"] or run["state"] != "awaiting_approval":
                raise DomainError("GRAPH-0003", "Current approved Run version required")
            approval = conn.execute(
                "SELECT run_id FROM inv.approval_requests WHERE approval_id=%s FOR SHARE",
                (data["approvalId"],),
            ).fetchone()
            if not approval or approval["run_id"] != run_id:
                raise DomainError("AUTH-0011", "Approval Run differs", 403)
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            bound.business_handoff = linked
            bound.workspace_admission = True
            command = ApprovalStore(bound).dispatch(
                principal,
                project,
                data["approvalId"],
                frozen["workload"],
                key="workspace-start:" + data["startId"],
            )
            WorkspaceResume(bound, self.workspace.working).enqueue(
                self.runtime.node,
                command,
                frozen["workload"],
                self.runtime.allocations(frozen["workload"]),
                self.runtime.profile,
                policy=policy,
                runtime=capabilities,
                signing_key=self.runtime.signing_key,
                key="workspace-start:" + data["startId"],
            )
            self.workspace._node_membership(conn, project, lock=True)
            result = dict(
                startId=data["startId"], runId=run_id, commandId=command["commandId"], accepted=True
            )
            validate_contract("WorkspaceStartEnqueueResult", result)
            return self.ledger._save(conn, project, "workspace.start.enqueue", key, result)
