"""The business chain, as endpoints.

One route per step, not one route for the whole chain. The steps are separated
by a human decision and by work happening on a node, so a single call that did
all six would either block for minutes or lie about what it had finished.

Each route re-establishes the project permission from scratch. Carrying a
permission decision forward from an earlier call would mean a revoked
membership keeps working until the chain ends, which is exactly the window a
revocation exists to close.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ...identity.principal import Principal
from ...ids import new_id
from ...services import handoff as handoff_service
from ...services.audit import record_event
from .. import schemas
from ..deps import get_now, get_principal, get_session

router = APIRouter(tags=["execution"])


def _permission(
    session: Session, principal: Principal, project_id: str
) -> handoff_service.ProjectPermission:
    return handoff_service.check_project_permission(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )


@router.get("/projects/{project_id}/permission")
def read_permission(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Step 1. What this caller may do here, stated before they try.

    A read, so it changes nothing — but it is the same function the mutating
    routes call, not a second implementation that could drift from it.
    """
    permission = _permission(session, principal, project_id)
    return {
        "projectId": permission.project_id,
        "userId": permission.user_id,
        "roleCode": permission.role_code,
        "canRequest": permission.can_request,
        "canApprove": permission.can_approve,
        # The digest of this decision, so a caller can quote what it was told.
        "decisionSha256": permission.digest(),
    }


@router.post("/workspaces/{workspace_id}/edit-lock", status_code=201)
def stop_editing(
    workspace_id: str,
    payload: schemas.EditLockRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Step 2. Stop editing, and record what the workspace held.

    Deliberately a POST that creates a resource rather than a flag on the
    workspace row: the lock is a thing with a holder, a reason and a lifetime,
    and it has to be releasable by something other than the run that took it
    when that run never finishes.
    """
    permission = _permission(session, principal, payload.project_id)
    handoff_service.require_can_request(permission)
    lock = handoff_service.stop_editing(
        session,
        tenant_id=principal.tenant_id,
        workspace_id=workspace_id,
        run_id=payload.run_id,
        user_id=principal.user_id,
        content_sha256=payload.content_sha256,
        now=now,
        reason=payload.reason,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="workspace.editing.stopped",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={
            "workspaceId": workspace_id,
            "runId": payload.run_id,
            "contentSha256": payload.content_sha256,
        },
    )
    response.headers["Location"] = f"/v1/edit-locks/{lock.lock_id}"
    return {
        "lockId": lock.lock_id,
        "workspaceId": lock.workspace_id,
        "runId": lock.run_id,
        "contentSha256": lock.content_sha256,
        "acquiredAt": lock.acquired_at.isoformat(),
    }


@router.delete("/edit-locks/{lock_id}", status_code=200)
def resume_editing(
    lock_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Let editing continue. Idempotent, so a retry is not an error."""
    lock = handoff_service.resume_editing(
        session, tenant_id=principal.tenant_id, lock_id=lock_id, now=now
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="workspace.editing.resumed",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={"lockId": lock_id, "workspaceId": lock.workspace_id},
    )
    return {
        "lockId": lock.lock_id,
        "releasedAt": lock.released_at.isoformat() if lock.released_at else None,
    }


@router.post("/runs/{run_id}/bindings", status_code=201)
def freeze_inputs(
    run_id: str,
    payload: schemas.FreezeInputsRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Step 3. Bind these exact bytes to this epoch and this run version.

    The response carries every identifier the execution core needs, including
    the epoch. A caller that passes them through verbatim cannot accidentally
    prepare work under one epoch and submit it under another, because the values
    it holds are the ones this side recorded.
    """
    permission = _permission(session, principal, payload.project_id)
    lock = handoff_service.get_edit_lock(
        session, tenant_id=principal.tenant_id, lock_id=payload.lock_id
    )
    binding = handoff_service.freeze_inputs(
        session,
        tenant_id=principal.tenant_id,
        project_id=payload.project_id,
        run_id=run_id,
        workspace_id=payload.workspace_id,
        lock=lock,
        permission=permission,
        step_id=payload.step_id,
        source_attempt=payload.source_attempt,
        bound_run_version=payload.bound_run_version,
        input_sha256=payload.input_sha256,
        input_size_bytes=payload.input_size_bytes,
        resume_id=payload.resume_id,
        checkout_id=payload.checkout_id,
        now=now,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="execution.inputs.frozen",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={
            "bindingId": binding.binding_id,
            "runId": run_id,
            "recoveryEpoch": str(binding.recovery_epoch),
            "inputSha256": binding.input_sha256,
        },
    )
    response.headers["Location"] = f"/v1/bindings/{binding.binding_id}"
    return handoff_service.binding_body(binding)


@router.get("/bindings/{binding_id}")
def read_binding(
    binding_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    return handoff_service.binding_body(
        handoff_service.get_binding(
            session, tenant_id=principal.tenant_id, binding_id=binding_id
        )
    )


@router.post("/bindings/{binding_id}/approval", status_code=200)
def attach_approval(
    binding_id: str,
    payload: schemas.AttachApprovalRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Step 4. Record that this approval decided *these* frozen inputs.

    The approval itself is the execution core's — quorum, nonce, votes, audit.
    What this adds is the pairing, so a valid approval cannot later be presented
    alongside different bytes.

    A permission snapshot is written here rather than at the end. Who could
    approve is a fact about this moment, and a membership change afterwards must
    not rewrite what the decision rested on.
    """
    permission = _permission(session, principal, payload.project_id)
    snapshot_id = handoff_service.record_permission_snapshot(
        session, tenant_id=principal.tenant_id, permission=permission, now=now
    )
    binding = handoff_service.attach_approval(
        session,
        tenant_id=principal.tenant_id,
        binding_id=binding_id,
        approval_id=payload.approval_id,
        permission=permission,
        permission_snapshot_id=snapshot_id,
        now=now,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="execution.approval.attached",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={
            "bindingId": binding_id,
            "approvalId": payload.approval_id,
            "permissionSnapshotId": snapshot_id,
        },
    )
    return handoff_service.binding_body(binding)


@router.post("/bindings/{binding_id}/state", status_code=200)
def advance_binding(
    binding_id: str,
    payload: schemas.BindingStateRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Steps 5 and 6, as the execution core reports them.

    ``queued`` once the reservation and the delivery have committed,
    ``executing`` when the node accepts, ``settled`` when the result is stored.
    Each transition re-checks the epoch and the edit lock, because queueing is
    where resources start being spent and settling is where the workspace is
    released.
    """
    binding = handoff_service.advance(
        session,
        tenant_id=principal.tenant_id,
        binding_id=binding_id,
        to=payload.state,
        note=payload.note,
        now=now,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action=f"execution.binding.{payload.state}",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={"bindingId": binding_id, "note": payload.note},
    )
    return handoff_service.binding_body(binding)
