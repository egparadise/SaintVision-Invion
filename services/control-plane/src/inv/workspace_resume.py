"""Freeze a restored checkout for a separately approved, bounded next Step.

The frozen bytes travel inside the signed launch and seed the Node's private
tmpfs. No host path or mutable shared mount is granted. Existing local edits are
never replaced on replay. Callers must authorize the project and quiesce editors.
"""

import base64
from copy import deepcopy
import hashlib
from uuid import uuid5, NAMESPACE_URL
from psycopg.types.json import Jsonb
from .approvals import digest
from .contracts import validate_contract
from .errors import DomainError
from .leases import lock_run
from .runs import event
from .snapshots import identity, SnapshotStore, object_key
from .workspace_files import canonical, decode_snapshot

MAX_RESUME_BYTES = 65536
MAX_RESUME_CONTENT = 32768
MAX_WORKSPACE_ATTEMPTS = 3


def independent_run(conn, run_id):
    if conn.execute(
        "SELECT 1 FROM inv.shard_commands WHERE run_id=%s UNION ALL SELECT 1 FROM inv.shard_parents WHERE run_id=%s LIMIT 1",
        (run_id, run_id),
    ).fetchone():
        raise DomainError("GRAPH-0005", "Shard recovery requires a coordinated new shard plan")


def bounded_snapshot(raw, workspace_id):
    if len(raw) > MAX_RESUME_BYTES:
        raise DomainError("STORE-0020", "Resume manifest exceeds 64 KiB", 422)
    manifest, content = decode_snapshot(raw, workspace_id)
    if sum(len(v) for v in content.values()) > MAX_RESUME_CONTENT:
        raise DomainError("STORE-0020", "Resume file content exceeds 32 KiB", 422)
    return manifest


def approved_resume(conn, run, workload, epoch):
    """Called under the Run lock at approval and at ToolGateway admission."""
    ref = workload.get("workspaceResume")
    independent_run(conn, run["run_id"])
    if ref is None:
        raise DomainError("AUTH-0044", "Recovery requires a frozen Workspace Step", 403)
    row = conn.execute(
        "SELECT * FROM inv.workspace_resumptions WHERE resume_id=%s AND project_id=%s AND run_id=%s",
        (ref["resumeId"], workload["projectId"], run["run_id"]),
    ).fetchone()
    if (
        not row
        or str(row["recovery_epoch"]) != epoch
        or row["source_attempt"] != run["attempt"]
        or run["attempt"] >= MAX_WORKSPACE_ATTEMPTS
        or row["workload"] != workload
        or row["workspace_id"] != workload["workspaceId"]
    ):
        raise DomainError("AUTH-0044", "Workspace Step or recovery epoch differs", 403)
    raw = bytes(row["snapshot"])
    bounded_snapshot(raw, workload["workspaceId"])
    if len(raw) != ref["inputSizeBytes"] or hashlib.sha256(raw).hexdigest() != ref["inputSha256"]:
        raise DomainError("VERIFY-0023", "Frozen Workspace bytes differ")
    return {
        "resumeId": ref["resumeId"],
        "stepId": ref["stepId"],
        "sha256": ref["inputSha256"],
        "sizeBytes": len(raw),
        "dataBase64": base64.b64encode(raw).decode(),
    }


class WorkspaceResume:
    def __init__(self, database, working):
        self.db, self.working = database, working

    def prepare(
        self,
        tenant,
        project,
        run_id,
        checkout_id,
        resume_id,
        step_id,
        workload,
        *,
        expected_version,
    ):
        checkout_id, resume_id = identity(checkout_id), identity(resume_id)
        workload = deepcopy(workload)
        validate_contract("WorkloadSpec", workload)
        if (
            workload["tenantId"] != tenant
            or workload["projectId"] != project
            or "workspaceResume" in workload
            or not isinstance(step_id, str)
            or not 1 <= len(step_id) <= 200
        ):
            raise DomainError("VAL-0003", "Invalid next Workspace Step", 422)
        request_hash = digest(
            {
                "run": run_id,
                "checkout": checkout_id,
                "step": step_id,
                "workload": workload,
                "version": expected_version,
                "epoch": self.db.recovery_epoch,
                "root": [str(self.working.root), *self.working.identity],
            }
        )
        with self.working.locked() as root_fd, self.db.transaction(tenant) as conn:
            return self._prepare(
                conn,
                root_fd,
                tenant,
                project,
                run_id,
                checkout_id,
                resume_id,
                step_id,
                workload,
                expected_version,
                request_hash,
            )

    def _prepare(
        self,
        conn,
        root_fd,
        tenant,
        project,
        run_id,
        checkout_id,
        resume_id,
        step_id,
        workload,
        expected_version,
        request_hash,
    ):
        """Internal: caller holds the working-root lock and owns the transaction."""
        run = lock_run(conn, run_id, project)
        prior = conn.execute(
            "SELECT * FROM inv.workspace_resumptions WHERE resume_id=%s", (resume_id,)
        ).fetchone()
        if prior:
            if prior["request_hash"] != request_hash:
                raise DomainError("IDEM-0001", "Resume identity already differs")
            # The immutable request is an observation, not new execution authority.
            return {"workload": prior["workload"], "replayed": True}
        if run["state"] != "recovering" or run["version"] != expected_version:
            raise DomainError("GRAPH-0003", "Resume requires current recovering Run")
        if run["attempt"] >= MAX_WORKSPACE_ATTEMPTS:
            raise DomainError("GRAPH-0005", "Workspace recovery attempt budget exhausted")
        independent_run(conn, run_id)
        if conn.execute(
            "SELECT 1 FROM inv.workspace_resumptions WHERE run_id=%s AND source_attempt=%s AND recovery_epoch=%s",
            (run_id, run["attempt"], self.db.recovery_epoch),
        ).fetchone():
            raise DomainError("IDEM-0001", "Attempt already has a frozen next Step")
        if conn.execute(
            "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (run_id,),
        ).fetchone():
            raise DomainError("LEASE-0003", "Resume awaits physical resource release")
        row = conn.execute(
            "SELECT * FROM inv.workspace_checkouts WHERE checkout_id=%s AND project_id=%s AND run_id=%s",
            (checkout_id, project, run_id),
        ).fetchone()
        if (
            not row
            or str(row["recovery_epoch"]) != self.db.recovery_epoch
            or row["source_attempt"] != run["attempt"]
            or row["workspace_id"] != workload["workspaceId"]
        ):
            raise DomainError("STORE-0022", "Current Workspace checkout required")
        if step_id == row["step_id"]:
            raise DomainError("VAL-0003", "Use a distinct next Step identity", 422)
        self.working.inspect_committed(
            root_fd,
            row["generation"],
            row["workspace_id"],
            row["content_hash"],
            row["filesystem_identity"],
        )
        from .workspace_editor import checkout_snapshot

        raw, _ = checkout_snapshot(conn, self.working, root_fd, row)
        bounded_snapshot(raw, row["workspace_id"])
        ref = {
            "resumeId": resume_id,
            "checkoutId": checkout_id,
            "sourceAttempt": row["source_attempt"],
            "checkpointAttempt": row["checkpoint_attempt"] or row["source_attempt"],
            "sourceStepId": row["step_id"],
            "stepId": step_id,
            "inputSha256": hashlib.sha256(raw).hexdigest(),
            "inputSizeBytes": len(raw),
        }
        workload["workspaceResume"] = ref
        validate_contract("WorkloadSpec", workload)
        conn.execute(
            """INSERT INTO inv.workspace_resumptions
            (tenant_id,project_id,run_id,resume_id,checkout_id,workspace_id,source_attempt,step_id,recovery_epoch,request_hash,workload,snapshot)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                tenant,
                project,
                run_id,
                resume_id,
                checkout_id,
                row["workspace_id"],
                run["attempt"],
                step_id,
                self.db.recovery_epoch,
                request_hash,
                Jsonb(workload),
                raw,
            ),
        )
        event(conn, tenant, run_id, "inv.workspace.resume_prepared", ref)
        return {"workload": workload, "replayed": False}

    def enqueue(
        self, node, command, workload, allocations, profile, *, policy, runtime, signing_key, key
    ):
        """New leases, claim and delivery either all commit or all roll back.

        This prevents cancellation/crash from stranding a new reservation on a
        Run that already has historical attempts. Only durable queue delivery
        starts it; replay returns observation of the original command.
        """
        from .approvals import ApprovalStore, Principal
        from .db import BoundDatabase
        from .leases import LeaseStore
        from .tooling import ToolGateway

        validate_contract("AuthorizedCommand", command)
        validate_contract("WorkloadSpec", workload)
        if "workspaceResume" not in workload or command["tenantId"] != node.tenant_id:
            raise DomainError("AUTH-0044", "Workspace execution scope differs", 403)
        payload = {
            "command": command,
            "workload": workload,
            "node": node.node_id,
            "allocations": [[a.resource_id, a.amount] for a in sorted(allocations)],
            "profile": profile.version,
        }
        store = ApprovalStore(self.db)
        principal = Principal(node.tenant_id, "workspace-admission:" + node.node_id)
        project, run_id = command["projectId"], command["runId"]
        with self.db.transaction(node.tenant_id) as conn:
            prior = store._ledger(conn, principal, project, "workspace.enqueue", key, payload)
            if prior is not None:
                return prior
            run = lock_run(conn, run_id, project)
            approved_resume(conn, run, workload, self.db.recovery_epoch)
            conn.execute(
                "SELECT approval_id FROM inv.approval_requests WHERE approval_id=%s FOR SHARE",
                (command["approvalId"],),
            ).fetchone()
            bound = BoundDatabase(self.db, node.tenant_id, conn)
            bound.workspace_admission = True
            leases = LeaseStore(bound).reserve(
                node.tenant_id,
                project,
                run_id,
                allocations,
                key="workspace:" + workload["workspaceResume"]["resumeId"],
                ttl_seconds=60,
            )
            admitted = ToolGateway(bound, profile).claim(
                node,
                command,
                workload,
                {l["leaseId"]: l["fencingToken"] for l in leases},
                policy=policy,
                runtime=runtime,
                queue_signing_key=signing_key,
            )
            return store._save(
                conn, project, "workspace.enqueue", key, {"claim": admitted.claim, "leases": leases}
            )


def workspace_output(artifact, launch):
    """Return canonical modified Workspace bytes only for its approved input."""
    input = launch.get("workspaceInput")
    value = artifact.get("workspace")
    if input is None:
        if value is not None:
            raise DomainError("VERIFY-0023", "Unexpected Workspace output")
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"resumeId", "stepId", "inputSha256", "snapshot"}
        or value["resumeId"] != input["resumeId"]
        or value["stepId"] != input["stepId"]
        or value["inputSha256"] != input["sha256"]
    ):
        raise DomainError("VERIFY-0023", "Workspace output is not bound to approved Step")
    raw = canonical(value["snapshot"])
    bounded_snapshot(raw, launch["workspaceId"])
    return raw


def commit_workspace_output(conn, files, tenant, project, run, command, receipt, result_bytes):
    from .node_transport import strict_json
    from .output_ingestion import output_bytes

    delivery = conn.execute(
        "SELECT envelope FROM inv.execution_deliveries WHERE command_id=%s", (command,)
    ).fetchone()
    if not delivery:
        return
    launch = strict_json(base64.b64decode(delivery["envelope"]["payload"]))["launch"]
    if "workspaceInput" not in launch:
        return
    if output_bytes(receipt) != result_bytes:
        raise DomainError("VERIFY-0023", "Workspace result differs from actual Node receipt")
    raw = workspace_output(strict_json(result_bytes), launch)
    oid = str(uuid5(NAMESPACE_URL, "inv.workspace-output:" + tenant + ":" + command))
    obj = SnapshotStore._row(conn, project, oid)
    if (
        obj["state"] != "ready"
        or files.read(object_key(oid), obj["content_hash"], obj["size_bytes"]) != raw
    ):
        raise DomainError("VERIFY-0023", "Modified Workspace object differs")
    content = {
        "objectId": oid,
        "sha256": obj["content_hash"],
        "sizeBytes": len(raw),
        "provider": "local-bounded-v1",
    }
    step = launch["workspaceInput"]["stepId"]
    conn.execute(
        "INSERT INTO inv.checkpoints(tenant_id,run_id,attempt,step_id,content_hash,checkpoint) VALUES(%s,%s,%s,%s,%s,%s)",
        (tenant, run["run_id"], run["attempt"], step, digest(content), Jsonb(content)),
    )
    conn.execute(
        "INSERT INTO inv.checkpoint_objects VALUES(%s,%s,%s,%s,%s,%s)",
        (tenant, project, run["run_id"], run["attempt"], step, oid),
    )
    event(
        conn,
        tenant,
        run["run_id"],
        "inv.workspace.step_committed",
        {
            "commandId": command,
            "resumeId": launch["workspaceInput"]["resumeId"],
            "stepId": step,
            "attempt": run["attempt"],
            "sha256": obj["content_hash"],
        },
    )
