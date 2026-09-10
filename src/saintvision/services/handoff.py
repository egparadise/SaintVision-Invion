"""The business chain that reaches the execution core.

Six steps, in this order, each refusing when a fact the previous step
established has since changed:

1. **Project permission.** May this user request execution in this project?
2. **Stop editing.** Quiesce the workspace and record what it contained.
3. **Freeze the inputs.** Bind those exact bytes to an epoch and a run version.
4. **New approval.** A fresh decision against the frozen content, never a reused one.
5. **Reserve resources and queue.** The execution core's, driven from the binding.
6. **Execute and store the result.** The execution core's, settled back here.

Steps 3 to 6 are implemented in ``inv`` — ``workspace_resume.prepare``,
``ApprovalStore``, ``LeaseStore.reserve``, the delivery queue and the result
ledger. This module does **not** reimplement them. It owns steps 1 and 2, which
did not exist, and it owns the ordering: the record that says these six things
happened to one workspace, in one epoch, for one approval.

**Why the order is the substance.** Each step is only meaningful because of the
one before it:

* freezing inputs that nothing stopped from changing captures whatever the read
  happened to see;
* approving inputs that were not frozen approves a moving target;
* reserving resources for an approval that has since expired, or in an epoch
  that has since rolled, executes a decision nobody made.

So every step here re-reads the previous step's fact and compares, rather than
trusting that it was true when it was written. Between two steps there is a
network round trip and a human, which is more than enough time for a workspace
to be edited, a membership to be revoked, or a control plane to restart.

**On the epoch.** The execution core rolls a recovery epoch whenever an
operator reconciles after a restart. Everything it holds — leases, claims,
deliveries — is bound to the epoch in force when it was made, and refuses to act
under a different one. That refusal is only useful if the business surface knows
which epoch it bound to, which is what ``execution_bindings.recovery_epoch``
records. Without it, a binding prepared before a roll looks identical to one
prepared after.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ..db.models import (
    ExecutionBinding,
    Project,
    ProjectMember,
    Run,
    Workspace,
    WorkspaceEditLock,
)
from ..errors import AUTH_PROJECT_SCOPE, RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id

#: Project role codes that may request execution. Read from
#: ``project_members.role_code``, which is the authoritative membership record —
#: ``inv.project_grants`` is a projection of this and never the other way round.
CAN_REQUEST: Final[frozenset[str]] = frozenset({"owner", "maintainer", "operator"})

#: Who may approve. Deliberately narrower, and deliberately not a superset check
#: on the same row: an approver who is also the requester is a quorum of one.
CAN_APPROVE: Final[frozenset[str]] = frozenset({"owner", "approver"})

#: A binding that never reached an approval is abandoned after this. A frozen
#: workspace that nobody approves must not stay frozen forever.
FREEZE_TTL_SECONDS: Final[int] = 900


@dataclass(frozen=True, slots=True)
class ProjectPermission:
    """What one user may do in one project, at one moment."""

    user_id: str
    project_id: str
    role_code: str
    can_request: bool
    can_approve: bool

    def digest(self) -> str:
        """A stable hash of the decision, so it can be recorded and compared.

        Recorded at approval time rather than recomputed later: "who could do
        what" is an artefact of the moment the decision was made, and a
        membership change afterwards must not silently rewrite history.
        """
        material = (
            f"{self.user_id}\n{self.project_id}\n{self.role_code}\n"
            f"{int(self.can_request)}{int(self.can_approve)}"
        )
        return hashlib.sha256(material.encode()).hexdigest()


def check_project_permission(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str
) -> ProjectPermission:
    """Step 1. May this user act in this project?

    Row level security gives tenant isolation and stops there. A user is a
    member of some projects and not others inside one tenant, and no policy
    expresses that — so this check is not defence in depth, it is the only
    thing standing between a tenant's users and each other's projects.

    The project must also be active. Archiving a project that still accepts
    executions archives nothing.
    """
    project = session.get(Project, project_id)
    if project is None or project.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "project not found")
    if project.status != "active":
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "the project is not active",
            extra={"projectId": project_id, "status": project.status},
        )

    membership = session.get(ProjectMember, (tenant_id, project_id, user_id))
    if membership is None:
        # Not "forbidden because of your role" — not a member at all. Reported
        # the same way, because telling a non-member which projects exist is
        # itself a disclosure.
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "no project membership",
            extra={"projectId": project_id},
        )
    return ProjectPermission(
        user_id=user_id,
        project_id=project_id,
        role_code=membership.role_code,
        can_request=membership.role_code in CAN_REQUEST,
        can_approve=membership.role_code in CAN_APPROVE,
    )


def require_can_request(permission: ProjectPermission) -> None:
    if not permission.can_request:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "this project role may not request execution",
            extra={"roleCode": permission.role_code},
        )


def stop_editing(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    run_id: str,
    user_id: str,
    content_sha256: str,
    now: dt.datetime,
    reason: str = "execution",
) -> WorkspaceEditLock:
    """Step 2. Quiesce the workspace and record what it held.

    The digest is supplied by the caller because only the caller has the bytes:
    the control plane does not hold workspace contents, the node does. What this
    guarantees is narrower and still worth having — that from this moment the
    platform will refuse a freeze whose digest differs, so an edit landing
    between the quiesce and the freeze is caught rather than absorbed.

    Acquisition is a plain INSERT against a partial unique index. Two callers
    quiescing the same workspace race in PostgreSQL, one loses, and the loser is
    told a lock is already held — which is the correct answer and the one an
    application-level check cannot reliably give.
    """
    if len(content_sha256) != 64 or content_sha256 != content_sha256.lower():
        raise InvError(VAL_SCHEMA, "content_sha256 must be 64 lowercase hex characters")

    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "workspace not found")
    if workspace.status != "ready":
        raise InvError(
            VAL_SCHEMA,
            "the workspace is not ready",
            extra={"workspaceId": workspace_id, "status": workspace.status},
        )

    held = session.scalars(
        select(WorkspaceEditLock).where(
            WorkspaceEditLock.tenant_id == tenant_id,
            WorkspaceEditLock.workspace_id == workspace_id,
            WorkspaceEditLock.released_at.is_(None),
        )
    ).one_or_none()
    if held is not None:
        if held.run_id == run_id:
            # The same run quiescing twice is a retry, not a conflict.
            return held
        raise InvError(
            VAL_SCHEMA,
            "editing is already stopped for another run",
            extra={"workspaceId": workspace_id, "heldForRunId": held.run_id},
        )

    lock = WorkspaceEditLock(
        lock_id=new_id("edit_lock"),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        run_id=run_id,
        held_by_user_id=user_id,
        content_sha256=content_sha256,
        reason=reason,
        acquired_at=now,
    )
    session.add(lock)
    session.flush()
    return lock


def resume_editing(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    lock_id: str,
    now: dt.datetime,
) -> WorkspaceEditLock:
    """Let editing continue. Idempotent: releasing a released lock is not an error."""
    lock = session.get(WorkspaceEditLock, lock_id)
    if lock is None or lock.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "edit lock not found")
    if lock.released_at is None:
        lock.released_at = now
        session.flush()
    return lock


def current_recovery_epoch(session: Session) -> str:
    """The execution core's epoch, read from its own table.

    Read rather than configured. The epoch is whatever ``inv.control_epoch``
    says right now; a copy in this side's configuration would be a second
    answer, and the entire point of recording it is that there is only one.

    Both halves scope by ``SET LOCAL inv.tenant_id``, so one transaction spans
    both schemas and this reads inside the caller's existing scope.
    """
    row = session.execute(
        text("SELECT epoch FROM inv.control_epoch WHERE singleton")
    ).one_or_none()
    if row is None:
        raise InvError(
            VAL_SCHEMA,
            "the execution core has no recovery epoch; it has not been initialised",
            public=False,
        )
    return str(row[0])


def freeze_inputs(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    run_id: str,
    workspace_id: str,
    lock: WorkspaceEditLock,
    permission: ProjectPermission,
    step_id: str,
    source_attempt: int,
    bound_run_version: int,
    input_sha256: str,
    input_size_bytes: int,
    now: dt.datetime,
    resume_id: str | None = None,
    checkout_id: str | None = None,
) -> ExecutionBinding:
    """Step 3. Record which moment this Run is being prepared for.

    The digests must agree. ``lock.content_sha256`` is what the workspace held
    when editing stopped; ``input_sha256`` is what the freeze captured. If they
    differ, something was written in between, and the honest answer is to refuse
    rather than to approve bytes nobody looked at.

    The epoch is read here, not passed in. A caller-supplied epoch is a caller's
    claim about when it is, and the whole purpose of this field is to be a fact.
    """
    require_can_request(permission)
    if lock.released_at is not None:
        raise InvError(
            VAL_SCHEMA,
            "editing resumed before the inputs were frozen",
            extra={"lockId": lock.lock_id},
        )
    if lock.run_id != run_id or lock.workspace_id != workspace_id:
        raise InvError(VAL_SCHEMA, "the edit lock is for a different run or workspace")
    if input_sha256 != lock.content_sha256:
        raise InvError(
            VAL_SCHEMA,
            "the workspace changed after editing was stopped",
            extra={"atStop": lock.content_sha256, "atFreeze": input_sha256},
        )

    run = session.get(Run, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "run not found")

    binding = ExecutionBinding(
        binding_id=new_id("binding"),
        tenant_id=tenant_id,
        project_id=project_id,
        run_id=run_id,
        workspace_id=workspace_id,
        lock_id=lock.lock_id,
        recovery_epoch=current_recovery_epoch(session),
        bound_run_version=bound_run_version,
        source_attempt=source_attempt,
        resume_id=resume_id,
        checkout_id=checkout_id,
        input_sha256=input_sha256,
        input_size_bytes=input_size_bytes,
        step_id=step_id,
        state="frozen",
        created_by_user_id=permission.user_id,
        created_at=now,
    )
    session.add(binding)
    session.flush()
    return binding


def assert_binding_is_current(
    session: Session, binding: ExecutionBinding, *, now: dt.datetime
) -> None:
    """Everything a later step must re-check before acting on a binding.

    Called at each of the remaining steps rather than once at the start. Between
    freezing and queueing there is a human decision, and a human decision takes
    long enough for a control plane to restart.
    """
    epoch = current_recovery_epoch(session)
    if str(binding.recovery_epoch) != epoch:
        raise InvError(
            VAL_SCHEMA,
            "the recovery epoch moved after these inputs were frozen; "
            "the reservation they describe no longer exists",
            extra={"boundEpoch": str(binding.recovery_epoch), "currentEpoch": epoch},
        )
    lock = session.get(WorkspaceEditLock, binding.lock_id)
    if lock is None or lock.released_at is not None:
        raise InvError(
            VAL_SCHEMA,
            "editing resumed on this workspace; the frozen inputs are no longer frozen",
        )
    if lock.content_sha256 != binding.input_sha256:
        raise InvError(VAL_SCHEMA, "the frozen inputs no longer match the edit lock")


def attach_approval(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    binding_id: str,
    approval_id: str,
    permission: ProjectPermission,
    permission_snapshot_id: str | None,
    now: dt.datetime,
) -> ExecutionBinding:
    """Step 4. A fresh approval, against these exact frozen inputs.

    The approval itself is the execution core's — quorum, nonce, votes and
    audit live there. What this records is that *this* binding is the thing it
    approved, so a later step cannot pair a valid approval with different bytes.

    Only a binding still in ``frozen`` accepts one. A second approval on an
    already-approved binding is not a retry; it is two decisions about one
    moment, and the unique key on (run, epoch, version) exists to make that
    impossible one level up.
    """
    binding = _load(session, tenant_id, binding_id)
    if binding.state != "frozen":
        raise InvError(
            VAL_SCHEMA,
            "this binding already carries a decision",
            extra={"state": binding.state},
        )
    assert_binding_is_current(session, binding, now=now)
    if (now - binding.created_at).total_seconds() > FREEZE_TTL_SECONDS:
        raise InvError(
            VAL_SCHEMA,
            "the frozen inputs are too old to approve; freeze again",
            extra={"ttlSeconds": FREEZE_TTL_SECONDS},
        )
    if not approval_id.startswith("apr_"):
        raise InvError(
            VAL_SCHEMA,
            "an execution-core approval id is required",
            extra={"approvalId": approval_id},
        )
    if permission.user_id == binding.created_by_user_id:
        # The requester approving their own request is a quorum of one. The
        # execution core enforces this too; saying it here means the caller is
        # told why rather than receiving a constraint violation.
        raise InvError(
            AUTH_PROJECT_SCOPE, "the requester may not approve their own execution"
        )
    if not permission.can_approve:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "this project role may not approve execution",
            extra={"roleCode": permission.role_code},
        )

    binding.approval_id = approval_id
    binding.permission_snapshot_id = permission_snapshot_id
    binding.state = "approved"
    session.flush()
    return binding


def advance(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    binding_id: str,
    to: str,
    now: dt.datetime,
    note: str | None = None,
) -> ExecutionBinding:
    """Steps 5 and 6, recorded as the execution core reports them.

    ``queued`` after the reservation and delivery commit; ``executing`` when the
    node accepts; ``settled`` when the result is stored. The forward-only rule
    means a late report cannot walk a binding backwards into a state whose
    guarantees no longer hold.
    """
    order = ["frozen", "approved", "queued", "executing", "settled"]
    binding = _load(session, tenant_id, binding_id)
    if to == "abandoned":
        return _settle(session, binding, state="abandoned", now=now, note=note)
    if to not in order:
        raise InvError(VAL_SCHEMA, f"unknown binding state: {to!r}")
    if binding.state in ("settled", "abandoned"):
        raise InvError(
            VAL_SCHEMA,
            "this binding has already ended",
            extra={"state": binding.state},
        )
    if order.index(to) <= order.index(binding.state):
        raise InvError(
            VAL_SCHEMA,
            "a binding only moves forward",
            extra={"from": binding.state, "to": to},
        )
    # Re-checked here as well: queueing is where resources are actually spent.
    assert_binding_is_current(session, binding, now=now)
    if to == "settled":
        return _settle(session, binding, state="settled", now=now, note=note)
    binding.state = to
    binding.note = note
    session.flush()
    return binding


def _settle(
    session: Session,
    binding: ExecutionBinding,
    *,
    state: str,
    now: dt.datetime,
    note: str | None,
) -> ExecutionBinding:
    """End the binding and let editing continue.

    Releasing the lock is part of settling rather than a separate call. A
    workspace left quiesced after its run finished is a workspace nobody can
    edit and nobody remembers why.
    """
    binding.state = state
    binding.settled_at = now
    binding.note = note
    session.execute(
        update(WorkspaceEditLock)
        .where(
            WorkspaceEditLock.tenant_id == binding.tenant_id,
            WorkspaceEditLock.lock_id == binding.lock_id,
            WorkspaceEditLock.released_at.is_(None),
        )
        .values(released_at=now)
        .execution_options(synchronize_session=False)
    )
    session.flush()
    return binding


def _load(session: Session, tenant_id: uuid.UUID, binding_id: str) -> ExecutionBinding:
    binding = session.get(ExecutionBinding, binding_id)
    if binding is None or binding.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "execution binding not found")
    return binding


def get_binding(
    session: Session, *, tenant_id: uuid.UUID, binding_id: str
) -> ExecutionBinding:
    return _load(session, tenant_id, binding_id)


def get_edit_lock(
    session: Session, *, tenant_id: uuid.UUID, lock_id: str
) -> WorkspaceEditLock:
    lock = session.get(WorkspaceEditLock, lock_id)
    if lock is None or lock.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "edit lock not found")
    return lock


def record_permission_snapshot(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    permission: ProjectPermission,
    now: dt.datetime,
) -> str:
    """Freeze who could do what, at the moment the decision was made.

    Written at approval rather than recomputed on demand. A membership revoked
    tomorrow must not make yesterday's approval look unauthorised, and a
    membership granted tomorrow must not make it look authorised either. The
    digest lets two snapshots be compared without reading both payloads.
    """
    from ..db.models import PermissionSnapshot

    snapshot = PermissionSnapshot(
        snapshot_id=new_id("permission_snapshot"),
        tenant_id=tenant_id,
        subject_type="user",
        subject_id=permission.user_id,
        grants=[
            {
                "projectId": permission.project_id,
                "roleCode": permission.role_code,
                "canRequest": permission.can_request,
                "canApprove": permission.can_approve,
            }
        ],
        digest_sha256=permission.digest(),
        taken_at=now,
    )
    session.add(snapshot)
    session.flush()
    return snapshot.snapshot_id


def binding_body(binding: ExecutionBinding) -> dict[str, Any]:
    """The wire shape. Every identifier the execution core needs, and the epoch."""
    return {
        "bindingId": binding.binding_id,
        "projectId": binding.project_id,
        "runId": binding.run_id,
        "workspaceId": binding.workspace_id,
        "lockId": binding.lock_id,
        # The mapping. Both halves use these values verbatim.
        "recoveryEpoch": str(binding.recovery_epoch),
        "boundRunVersion": binding.bound_run_version,
        "sourceAttempt": binding.source_attempt,
        "resumeId": binding.resume_id,
        "checkoutId": binding.checkout_id,
        "stepId": binding.step_id,
        "inputSha256": binding.input_sha256,
        "inputSizeBytes": binding.input_size_bytes,
        "approvalId": binding.approval_id,
        "state": binding.state,
        "createdAt": binding.created_at.isoformat(),
        "settledAt": binding.settled_at.isoformat() if binding.settled_at else None,
        "note": binding.note,
    }
