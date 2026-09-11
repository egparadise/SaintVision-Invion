"""Projects and workspaces: creating them, and seeing the ones you may see.

The entry point for "select a project with a real account". Two things run
through every endpoint here.

**Access is read from the database on every request.** Not from the credential:
a project created a moment ago belongs to the person who created it, and a
membership revoked a moment ago is gone — neither of which a set fixed at
sign-in can express. It is also the same row the execution kernel reads, so the
screen and the kernel cannot disagree about who may do what.

**A project that cannot execute yet says so, in words.** Creating a project
deliberately does not grant the right to run code on somebody's machine; an
operator links it to the execution kernel separately. Reporting that as a state
is the difference between "waiting for an operator" and an authorisation error
at the moment someone presses run.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ...identity.principal import Principal
from ...services import projects as project_service
from ...services.audit import record_event
from .. import schemas
from ..deps import get_now, get_principal, get_session

router = APIRouter(prefix="/v1", tags=["projects"])


@router.get("/projects")
def list_projects(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    """Every project this caller is a member of, with what they may do in each.

    The role is returned beside ``canRequest``/``canApprove`` rather than
    instead of them: a suspended user keeps their role and may do nothing, so a
    screen rendering the role alone would offer controls the platform refuses.
    """
    items = project_service.list_projects(
        session, tenant_id=principal.tenant_id, user_id=principal.user_id
    )
    return {"projects": items, "count": len(items)}


@router.post("/projects", status_code=201)
def create_project(
    payload: schemas.ProjectCreateRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Create a project. The creator becomes its owner in the same transaction.

    A project with no members is one nobody can administer, including whoever
    just made it — and that failure shows up a request later, looking like an
    authorisation bug rather than a missing step here.
    """
    body = project_service.create_project(
        session,
        tenant_id=principal.tenant_id,
        code=payload.code,
        display_name=payload.display_name,
        created_by_user_id=principal.user_id,
        now=now,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="project.created",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={"projectId": body["projectId"], "code": payload.code},
    )
    response.headers["Location"] = f"/v1/projects/{body['projectId']}"
    return body


@router.get("/projects/{project_id}")
def read_project(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    permission = project_service.require_project_access(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )
    from ...db.models import Project

    project = session.get(Project, project_id)
    body = project_service.project_body(
        session, project, tenant_id=principal.tenant_id
    )
    body["permission"] = permission
    return body


@router.get("/projects/{project_id}/workspaces")
def list_workspaces(
    project_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict:
    items = project_service.list_workspaces(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        user_id=principal.user_id,
    )
    return {"projectId": project_id, "workspaces": items, "count": len(items)}


@router.post("/projects/{project_id}/workspaces", status_code=201)
def create_workspace(
    project_id: str,
    payload: schemas.WorkspaceCreateRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Create a workspace. It starts ``provisioning``, never ``ready``.

    Nothing has prepared storage for it yet, and a workspace that claims to be
    ready before anything provisioned it fails at the moment someone puts files
    in it.
    """
    body = project_service.create_workspace(
        session,
        tenant_id=principal.tenant_id,
        project_id=project_id,
        name=payload.name,
        created_by_user_id=principal.user_id,
        now=now,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="workspace.created",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={"projectId": project_id, "workspaceId": body["workspaceId"]},
    )
    response.headers["Location"] = f"/v1/workspaces/{body['workspaceId']}"
    return body


@router.put("/workspaces/{workspace_id}/tool")
def set_workspace_tool(
    workspace_id: str,
    payload: schemas.WorkspaceToolRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
    now: dt.datetime = Depends(get_now),
) -> dict:
    """Choose which development tool this workspace uses.

    The response carries the choice **and** whether that tool is usable on this
    machine right now, because the two are different facts with different
    lifetimes: the choice is a property of the workspace and persists, while
    installed-and-signed-in is a property of a node and can change between two
    requests. A screen that shows only the choice will eventually offer to run
    something that cannot run.
    """
    body = project_service.set_workspace_tool(
        session,
        tenant_id=principal.tenant_id,
        workspace_id=workspace_id,
        tool_name=payload.tool_name,
        acting_user_id=principal.user_id,
    )
    record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action="workspace.tool_set",
        outcome="allow",
        tenant_id=principal.tenant_id,
        trace_id=getattr(request.state, "trace_id", None),
        detail={"workspaceId": workspace_id, "toolName": payload.tool_name},
    )
    return body
