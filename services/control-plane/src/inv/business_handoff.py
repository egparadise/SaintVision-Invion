"""Business Workspace handoff backed by actual kernel authority and evidence.

The immutable binding does not store a client-writable execution state. Queue,
attempt, physical stop and result are read from the kernel. Editing is released
only after those records prove safety, under the same Run lock as admission.
"""

import hashlib
from uuid import uuid4

from .approvals import ApprovalStore, digest, view as approval_view
from .business_auth import permission
from .contracts import validate_contract
from .control import Control
from .db import BoundDatabase
from .errors import DomainError
from .leases import lock_run
from .runs import public, event
from .snapshots import identity
from .workspace_files import PrivateTree
from .workspace_resume import bounded_snapshot


def require_handoff(conn, database, run_id):
    if (
        not getattr(database, "business_handoff", False)
        and conn.execute("SELECT 1 FROM inv.business_runs WHERE run_id=%s", (run_id,)).fetchone()
    ):
        raise DomainError("AUTH-0045", "Business Run requires its atomic handoff", 403)


def scope(conn, database, principal, project, run_id, required="can_request"):
    run = lock_run(conn, run_id, project)
    Control(database).grant(conn, principal, project, required)
    actor = permission(conn, project, principal.subject_id, required, linked=True)
    link = conn.execute(
        "SELECT * FROM inv.business_runs WHERE project_id=%s AND run_id=%s", (project, run_id)
    ).fetchone()
    if not link:
        raise DomainError("RES-0004", "Business Run mapping unavailable", 404)
    rows = conn.execute(
        """SELECT r.workspace_id,w.project_id,w.status,l.project_id AS workload_project,
                  l.spec,l.spec_sha256
           FROM public.runs r JOIN public.workspaces w
             ON w.tenant_id=r.tenant_id AND w.workspace_id=r.workspace_id
           JOIN public.workloads l ON l.tenant_id=r.tenant_id AND l.workload_id=r.workload_id
           WHERE r.run_id=%s FOR SHARE OF r,w,l""",
        (run_id,),
    ).fetchone()
    if (
        not rows
        or rows["workspace_id"] != link["workspace_id"]
        or (rows["project_id"] != project or rows["workload_project"] != project)
    ):
        raise DomainError("AUTH-0011", "Business Run or Workspace project differs", 403)
    return run, actor, rows


def load(conn, database, principal, binding_id, required=None):
    row = conn.execute(
        "SELECT * FROM public.execution_bindings WHERE binding_id=%s", (identity(binding_id),)
    ).fetchone()
    if not row:
        raise DomainError("RES-0004", "Execution binding unavailable", 404)
    run, actor, workspace = scope(
        conn, database, principal, row["project_id"], row["run_id"], required
    )
    lock = conn.execute(
        "SELECT * FROM public.workspace_edit_locks WHERE lock_id=%s FOR UPDATE", (row["lock_id"],)
    ).fetchone()
    return row, lock, run, actor, workspace


def check_admission(conn, database, principal, project, run_id, data, binding_id, *, replay=False):
    linked = conn.execute("SELECT 1 FROM inv.business_runs WHERE run_id=%s", (run_id,)).fetchone()
    if not linked:
        if binding_id is not None:
            raise DomainError("AUTH-0045", "Unexpected business binding", 403)
        return
    if binding_id is None:
        raise DomainError("AUTH-0045", "Business Run requires its binding", 403)
    row, lock, run, _, workspace = load(conn, database, principal, binding_id, "can_request")
    if (
        row["project_id"] != project
        or row["run_id"] != run_id
        or (
            str(row["resume_id"]) != data["resumeId"]
            or row["approval_id"] != data["approvalId"]
            or row["bound_run_version"] != data["expectedVersion"]
            or lock["held_by_subject_id"] != principal.subject_id
        )
    ):
        raise DomainError("AUTH-0045", "Binding identity differs", 403)
    if replay:
        return  # Previously accepted response cannot issue another command.
    if lock["released_at"] is not None or str(row["recovery_epoch"]) != database.recovery_epoch:
        raise DomainError("AUTH-0045", "Binding is no longer current", 403)
    if run["version"] != row["bound_run_version"] or workspace["status"] != "ready":
        raise DomainError("GRAPH-0003", "Current ready Workspace binding required")
    frozen = conn.execute(
        "SELECT workload FROM inv.workspace_resumptions WHERE resume_id=%s", (row["resume_id"],)
    ).fetchone()
    intent = dict(frozen["workload"])
    intent.pop("workspaceResume")
    if workspace["spec"] != intent or workspace["spec_sha256"] != digest(intent):
        raise DomainError("AUTH-0045", "Business workload changed after approval", 403)


def status(conn, binding, lock, run):
    approval = conn.execute(
        "SELECT * FROM inv.approval_requests WHERE approval_id=%s", (binding["approval_id"],)
    ).fetchone()
    delivery = conn.execute(
        """SELECT d.* FROM inv.approval_dispatches a JOIN inv.execution_deliveries d
           ON d.tenant_id=a.tenant_id AND d.command_id=a.command_id
           WHERE a.approval_id=%s""",
        (binding["approval_id"],),
    ).fetchone()
    receipt = completion = attempt = None
    if delivery:
        receipt = conn.execute(
            "SELECT receipt_id,envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (delivery["command_id"],),
        ).fetchone()
        completion = conn.execute(
            "SELECT evidence_id FROM inv.result_completions WHERE command_id=%s",
            (delivery["command_id"],),
        ).fetchone()
        attempt = conn.execute(
            "SELECT attempt FROM inv.execution_attempts WHERE command_id=%s",
            (delivery["command_id"],),
        ).fetchone()
    active = conn.execute(
        "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL LIMIT 1",
        (run["run_id"],),
    ).fetchone()
    safe = not active and (
        (not delivery and run["state"] in {"failed", "cancelled"})
        or (
            delivery
            and receipt
            and run["state"] in {"succeeded", "failed", "cancelled", "recovering"}
            and (run["state"] != "succeeded" or completion)
        )
    )
    state = "approved" if approval["status"] in {"approved", "dispatched"} else "frozen"
    if delivery:
        state = "queued" if delivery["phase"] == "queued" else "executing"
    if safe:
        state = "settled" if delivery else "abandoned"
    frozen = conn.execute(
        "SELECT workload FROM inv.workspace_resumptions WHERE resume_id=%s", (binding["resume_id"],)
    ).fetchone()["workload"]
    result = {
        "bindingId": str(binding["binding_id"]),
        "projectId": binding["project_id"],
        "runId": binding["run_id"],
        "workspaceId": lock["workspace_id"],
        "lockId": str(lock["lock_id"]),
        "resumeId": str(binding["resume_id"]),
        "checkoutId": str(lock["checkout_id"]),
        "recoveryEpoch": str(binding["recovery_epoch"]),
        "boundRunVersion": binding["bound_run_version"],
        "inputSha256": lock["content_sha256"],
        "inputSizeBytes": lock["input_size_bytes"],
        "approval": approval_view(approval),
        "state": state,
        "run": public(run),
        "commandId": str(delivery["command_id"]) if delivery else None,
        "deliveryPhase": delivery["phase"] if delivery else None,
        "executionConfirmed": bool(receipt and receipt["envelope"]["processStarted"]),
        "attempt": attempt["attempt"] if attempt else None,
        "stopReceiptId": str(receipt["receipt_id"]) if receipt else None,
        "evidenceId": completion["evidence_id"] if completion else None,
        "releaseAllowed": bool(safe),
        "resourceReleasePending": bool(active),
        "releasedAt": lock["released_at"].isoformat() if lock["released_at"] else None,
        "workload": frozen,
    }
    validate_contract("BusinessBindingView", result)
    return result


class BusinessHandoff:
    def __init__(self, workspace):
        self.workspace, self.db = workspace, workspace.db
        self.ledger = ApprovalStore(self.db)

    def stop(self, principal, workspace_id, data, key):
        validate_contract("BusinessEditLockInput", data)
        validate_contract("WorkspaceId", workspace_id)
        project, run_id = data["projectId"], data["runId"]
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            prior = self.ledger._ledger(
                conn,
                principal,
                project,
                "business.lock",
                key,
                {"workspaceId": workspace_id, **data},
            )
            run, _, current = scope(conn, self.db, principal, project, run_id)
            if current["workspace_id"] != workspace_id:
                raise DomainError("AUTH-0011", "Workspace differs from Run", 403)
            if prior is not None:
                return prior
            if (
                current["status"] != "ready"
                or run["state"] != "recovering"
                or run["version"] != data["expectedVersion"]
            ):
                raise DomainError(
                    "GRAPH-0003", "Ready Workspace and current recovering Run required"
                )
            if conn.execute(
                "SELECT 1 FROM public.workspace_edit_locks WHERE workspace_id=%s AND released_at IS NULL",
                (workspace_id,),
            ).fetchone():
                raise DomainError("GRAPH-0003", "Workspace editing is already stopped")
            checkout = conn.execute(
                "SELECT * FROM inv.workspace_checkouts WHERE checkout_id=%s AND run_id=%s AND project_id=%s",
                (identity(data["checkoutId"]), run_id, project),
            ).fetchone()
            if (
                not checkout
                or checkout["workspace_id"] != workspace_id
                or checkout["source_attempt"] != run["attempt"]
                or str(checkout["recovery_epoch"]) != self.db.recovery_epoch
            ):
                raise DomainError("STORE-0022", "Current Workspace checkout required")
            self.workspace.working.inspect_committed(
                root_fd,
                checkout["generation"],
                workspace_id,
                checkout["content_hash"],
                checkout["filesystem_identity"],
            )
            source = PrivateTree(self.workspace.working.root / checkout["generation"] / "files")
            if source.identity != (
                self.workspace.working.identity[0],
                checkout["filesystem_identity"][-1],
            ):
                raise DomainError("STORE-0022", "Checkout files were replaced")
            raw = source.capture(workspace_id)
            bounded_snapshot(raw, workspace_id)
            lock_id = str(uuid4())
            conn.execute(
                """INSERT INTO public.workspace_edit_locks
                (tenant_id,project_id,run_id,workspace_id,lock_id,checkout_id,held_by_subject_id,
                 content_sha256,input_size_bytes,recovery_epoch,bound_run_version)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    principal.tenant_id,
                    project,
                    run_id,
                    workspace_id,
                    lock_id,
                    checkout["checkout_id"],
                    principal.subject_id,
                    hashlib.sha256(raw).hexdigest(),
                    len(raw),
                    self.db.recovery_epoch,
                    run["version"],
                ),
            )
            result = {
                "lockId": lock_id,
                "workspaceId": workspace_id,
                "runId": run_id,
                "contentSha256": hashlib.sha256(raw).hexdigest(),
                "inputSizeBytes": len(raw),
            }
            event(conn, principal.tenant_id, run_id, "inv.workspace.editing_stopped", result)
            return self.ledger._save(conn, project, "business.lock", key, result)

    def prepare(self, principal, run_id, data, key):
        from .workspace_api import WorkspaceAPI

        validate_contract("BusinessBindingInput", data)
        project = data["projectId"]
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            prior = self.ledger._ledger(
                conn, principal, project, "business.prepare", key, {"runId": run_id, **data}
            )
            run, _, current = scope(conn, self.db, principal, project, run_id)
            if prior is not None:
                return prior
            lock = conn.execute(
                "SELECT * FROM public.workspace_edit_locks WHERE lock_id=%s FOR UPDATE",
                (identity(data["lockId"]),),
            ).fetchone()
            if (
                not lock
                or lock["run_id"] != run_id
                or lock["project_id"] != project
                or lock["held_by_subject_id"] != principal.subject_id
            ):
                raise DomainError("AUTH-0045", "Owned edit lock required", 403)
            if (
                lock["released_at"]
                or str(lock["recovery_epoch"]) != self.db.recovery_epoch
                or lock["bound_run_version"] != run["version"]
            ):
                raise DomainError("GRAPH-0003", "Edit lock is no longer current")
            intent = data["prepare"]["workload"]
            if (
                current["status"] != "ready"
                or current["workspace_id"] != intent["workspaceId"]
                or current["spec"] != intent
                or current["spec_sha256"] != digest(intent)
            ):
                raise DomainError("AUTH-0045", "Current business workload required", 403)
            if data["prepare"]["checkoutId"] != str(lock["checkout_id"]):
                raise DomainError("AUTH-0045", "Edit lock checkout differs", 403)
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            bound.business_handoff = True
            prepared = WorkspaceAPI(bound, self.workspace.working, self.workspace.runtime).prepare(
                principal,
                project,
                run_id,
                data["prepare"],
                "business:" + data["lockId"],
                root_fd=root_fd,
            )
            ref = prepared["workload"]["workspaceResume"]
            if (
                ref["inputSha256"] != lock["content_sha256"]
                or ref["inputSizeBytes"] != lock["input_size_bytes"]
            ):
                raise DomainError("VERIFY-0023", "Workspace changed after editing stopped")
            row = conn.execute(
                """INSERT INTO public.execution_bindings
                (tenant_id,project_id,run_id,binding_id,lock_id,resume_id,approval_id,recovery_epoch,bound_run_version)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    principal.tenant_id,
                    project,
                    run_id,
                    str(uuid4()),
                    lock["lock_id"],
                    prepared["resumeId"],
                    prepared["approval"]["approvalId"],
                    self.db.recovery_epoch,
                    prepared["run"]["version"],
                ),
            ).fetchone()
            result = status(conn, row, lock, lock_run(conn, run_id, project))
            event(
                conn,
                principal.tenant_id,
                run_id,
                "inv.business.binding_prepared",
                {"bindingId": result["bindingId"], "approvalId": result["approval"]["approvalId"]},
            )
            return self.ledger._save(conn, project, "business.prepare", key, result)

    def get(self, principal, binding_id):
        with self.db.transaction(principal.tenant_id) as conn:
            row, lock, run, _, _ = load(conn, self.db, principal, binding_id)
            return status(conn, row, lock, run)

    def enqueue(self, principal, binding_id, key):
        with self.db.transaction(principal.tenant_id) as conn:
            row, lock, _, _, _ = load(conn, self.db, principal, binding_id, "can_request")
            if lock["held_by_subject_id"] != principal.subject_id:
                raise DomainError("AUTH-0045", "Binding requester required", 403)
            data = {
                "resumeId": str(row["resume_id"]),
                "approvalId": row["approval_id"],
                "expectedVersion": row["bound_run_version"],
            }
        return self.workspace.enqueue(
            principal, row["project_id"], row["run_id"], data, key, binding_id=binding_id
        )

    def approved(self, principal, binding_id, data):
        validate_contract("BusinessApprovalInput", data)
        with self.db.transaction(principal.tenant_id) as conn:
            row, lock, run, _, _ = load(conn, self.db, principal, binding_id, "can_approve")
            result = status(conn, row, lock, run)
            if (
                data["approvalId"] != row["approval_id"]
                or result["approval"]["status"] != "approved"
            ):
                raise DomainError("AUTH-0045", "The actual fresh quorum approval is required", 403)
            if lock["held_by_subject_id"] == principal.subject_id:
                raise DomainError("AUTH-0045", "Requester cannot attest approval", 403)
            current_run, approval = self.ledger._locked(conn, row["approval_id"], row["project_id"])
            self.ledger._current(conn, current_run, approval, {"approved"})
            voters = conn.execute(
                "SELECT actor_id FROM inv.approval_votes WHERE approval_id=%s AND decision='approve' ORDER BY actor_id",
                (row["approval_id"],),
            ).fetchall()
            if len(voters) != 2 or any(v["actor_id"] == approval["requester_id"] for v in voters):
                raise DomainError("AUTH-0033", "Distinct current approval quorum required", 403)
            for voter in voters:
                self.ledger._grant(conn, row["project_id"], voter["actor_id"], "can_approve")
            return result

    def release(self, principal, lock_id, key):
        with self.db.transaction(principal.tenant_id) as conn:
            lock = conn.execute(
                "SELECT * FROM public.workspace_edit_locks WHERE lock_id=%s", (identity(lock_id),)
            ).fetchone()
            if not lock:
                raise DomainError("RES-0004", "Edit lock unavailable", 404)
            prior = self.ledger._ledger(
                conn, principal, lock["project_id"], "business.release", key, {"lockId": lock_id}
            )
            # Same Run -> authority -> edit lock order as prepare/enqueue.
            run, _, _ = scope(conn, self.db, principal, lock["project_id"], lock["run_id"])
            lock = conn.execute(
                "SELECT * FROM public.workspace_edit_locks WHERE lock_id=%s FOR UPDATE",
                (lock["lock_id"],),
            ).fetchone()
            if lock["held_by_subject_id"] != principal.subject_id:
                raise DomainError(
                    "AUTH-0045", "Only the current lock owner may release editing", 403
                )
            if prior is not None:
                return prior
            if lock["released_at"] is None:
                binding = conn.execute(
                    "SELECT * FROM public.execution_bindings WHERE lock_id=%s", (lock["lock_id"],)
                ).fetchone()
                if binding and not status(conn, binding, lock, run)["releaseAllowed"]:
                    raise DomainError(
                        "GRAPH-0003", "Execution must stop and settle before editing resumes"
                    )
                conn.execute(
                    "UPDATE public.workspace_edit_locks SET released_at=clock_timestamp() WHERE lock_id=%s",
                    (lock["lock_id"],),
                )
                event(
                    conn,
                    principal.tenant_id,
                    lock["run_id"],
                    "inv.workspace.editing_resumed",
                    {"lockId": lock_id},
                )
            row = conn.execute(
                "SELECT released_at FROM public.workspace_edit_locks WHERE lock_id=%s",
                (lock["lock_id"],),
            ).fetchone()
            return self.ledger._save(
                conn,
                lock["project_id"],
                "business.release",
                key,
                {"lockId": lock_id, "releasedAt": row["released_at"].isoformat()},
            )

    def reconcile(self, principal, binding_id, key):
        current = self.get(principal, binding_id)
        self.release(principal, current["lockId"], key)
        return self.get(principal, binding_id)
