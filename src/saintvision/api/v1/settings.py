"""Settings endpoints: who may do what, and what each machine offers.

The screens Gemini builds call these. Two conventions run through all of them,
and both exist because a settings screen that lies is worse than one that fails.

**Every write returns the effective result, not an acknowledgement.** Setting a
role returns what that user may now do — ``canRequest``, ``canApprove`` — rather
than echoing the role back. The role alone does not decide it: a suspended user
with the ``owner`` role may do nothing, and a screen that renders the role it
just sent shows a permission the platform will refuse. Returning the computed
answer means the screen cannot disagree with the kernel.

**Every quantity carries its unit.** A field named ``offeredQuantity`` beside a
field named ``unit`` is not decoration — the same machine can be described in
GiB by one screen and bytes by another, and the conversion happens once, at this
boundary, in ``saintvision.units``.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...identity.principal import Principal
from ...services import settings as settings_service
from ...services.audit import record_event
from .. import schemas
from ..deps import get_now, get_principal, get_session

router = APIRouter(prefix="/v1", tags=["settings"])


def _audit(session, request, principal, action, detail, now):
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action=action,
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail=detail,
    )


# --------------------------------------------------------------------------
# Permission, read the same way the kernel reads it
# --------------------------------------------------------------------------


@router.get("/projects/{project_id}/permissions/me")
def read_my_permission(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """What the caller may do here.

    A screen calls this to decide which controls to show. It is the same
    function every write is guarded by, so the controls shown and the controls
    that work cannot drift apart.
    """
    from ...services.projects import require_project_access

    return require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )


@router.get("/projects/{project_id}/members")
def list_members(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    from ...services.projects import require_project_access

    require_project_access(
        session, tenant_id=principal.tenant_id, project_id=project_id, user_id=principal.user_id
    )
    members = settings_service.list_members(
        session, tenant_id=principal.tenant_id, project_id=project_id
    )
    return {
        "projectId": project_id,
        "members": members,
        # So a screen can render the choices without hardcoding them, and so a
        # new role cannot appear in a dropdown the platform does not accept.
        "roles": list(settings_service.PROJECT_ROLES),
    }


@router.put("/projects/{project_id}/members/{user_id}")
def set_member_role(
    project_id: str,
    user_id: str,
    payload: schemas.MemberRoleRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Grant or change a membership, and return what it now permits."""
    result = settings_service.set_member_role(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=user_id,
        role_code=payload.role_code,
        acting_user_id=principal.user_id,
        now=now,
    )
    _audit(
        session,
        request,
        principal,
        "project.member.role_set",
        {"projectId": project_id, "userId": user_id, "roleCode": payload.role_code},
        now,
    )
    return result


@router.delete("/projects/{project_id}/members/{user_id}", status_code=200)
def remove_member(
    project_id: str,
    user_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    settings_service.remove_member(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=user_id,
        acting_user_id=principal.user_id,
    )
    _audit(
        session,
        request,
        principal,
        "project.member.removed",
        {"projectId": project_id, "userId": user_id},
        now,
    )
    return {"projectId": project_id, "userId": user_id, "removed": True}


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


@router.put("/users/{user_id}/status")
def set_user_status(
    user_id: str,
    payload: schemas.UserStatusRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Suspend or restore a user.

    Effective immediately everywhere, including inside the execution kernel,
    because the kernel reads this row rather than a copy of it.
    """
    settings_service.require_global_administrator(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission="users.manage",
        target_user_id=user_id,
    )
    user = settings_service.set_user_status(
        session,
        tenant_id=principal.tenant_id,
        user_id=user_id,
        status=payload.status,
        now=now,
    )
    _audit(
        session,
        request,
        principal,
        "user.status_set",
        {"userId": user_id, "status": payload.status},
        now,
    )
    return {"userId": user.user_id, "status": user.status}


@router.put("/projects/{project_id}/status")
def set_project_status(
    project_id: str,
    payload: schemas.ProjectStatusRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Archive or reactivate a project. Archiving stops execution in it."""
    project = settings_service.set_project_status(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        status=payload.status,
        acting_user_id=principal.user_id,
    )
    _audit(
        session,
        request,
        principal,
        "project.status_set",
        {"projectId": project_id, "status": payload.status},
        now,
    )
    return {"projectId": project.project_id, "status": project.status}


@router.put("/workspaces/{workspace_id}/status")
def set_workspace_status(
    workspace_id: str,
    payload: schemas.WorkspaceStatusRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    workspace = settings_service.set_workspace_status(
        session,
        tenant_id=principal.tenant_id,
        workspace_id=workspace_id,
        status=payload.status,
        acting_user_id=principal.user_id,
        now=now,
    )
    _audit(
        session,
        request,
        principal,
        "workspace.status_set",
        {"workspaceId": workspace_id, "status": payload.status},
        now,
    )
    return {
        "workspaceId": workspace.workspace_id,
        "status": workspace.status,
        "allowedNext": sorted(settings_service.WORKSPACE_TRANSITIONS.get(workspace.status, ())),
    }


# --------------------------------------------------------------------------
# What a machine offers
# --------------------------------------------------------------------------


@router.get("/nodes/{node_id}/offers")
def read_node_offers(
    node_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Everything this machine offers, beside everything it has."""
    return {
        "nodeId": node_id,
        "capabilities": settings_service.node_offers(
            session, tenant_id=principal.tenant_id, node_id=node_id, now=now
        ),
    }


@router.put("/capabilities/{capability_id}/offer")
def set_resource_offer(
    capability_id: str,
    payload: schemas.ResourceOfferRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Change how much of one capability the platform may use.

    The caller sends whatever unit its screen uses; the conversion happens here
    and the response states the canonical unit the platform stored. A screen
    that sends GiB and a screen that sends bytes describe the same machine.
    """
    settings_service.require_global_administrator(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission="resources.manage",
    )
    result = settings_service.set_resource_offer(
        session,
        tenant_id=principal.tenant_id,
        capability_id=capability_id,
        acting_user_id=principal.user_id,
        offered_quantity=payload.offered_quantity,
        unit=payload.unit,
        now=now,
    )
    _audit(
        session,
        request,
        principal,
        "node.offer_set",
        {
            "capabilityId": capability_id,
            "offeredQuantity": result["offeredQuantity"],
            "unit": result["unit"],
        },
        now,
    )
    return result
