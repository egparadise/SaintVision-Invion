"""Creating and listing the things a person works in.

The first half of "a project made with a real account reaches the execution
kernel, and an unauthorised request is refused". Two decisions carry most of
the weight.

**Project access is read now, not carried.** ``Principal.project_ids`` is fixed
when the credential is verified, which makes it a snapshot: a project created a
second ago is not in it, so the person who just created a project could not open
it. Worse in the other direction — a membership revoked after a token was issued
stays effective until that token expires. So every check here reads
``project_members``, which is also the row the execution kernel reads
(``inv.business_auth``). One fact, read at the moment it is used, by both halves.

**Creating a project makes the creator its owner, in the same transaction.** A
project with no members is one nobody can administer, including the person who
just made it, and the failure appears one request later as a permission error
that looks like a bug in authorisation rather than a missing step in creation.

**A created project cannot execute yet, and says so.** The kernel acts only on
projects linked in ``inv.business_projects``, which is operator-owned on
purpose: creating a project must not also grant the right to run code on
someone's machine. Without that state being reported, a screen shows a project,
a workspace and a run button, and the run fails with an authorisation error
about something the user cannot fix. ``kernelLinked`` turns that into a sentence
an operator can act on.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Any, Final

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..db.models import Project, ProjectMember, User, Workspace
from ..errors import AUTH_PROJECT_SCOPE, RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id
from . import settings as settings_service

#: Project codes are used in URLs and in operator conversation, so they are
#: constrained rather than free text.
CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")

WORKSPACE_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[\w][\w .-]{0,126}[\w]$")


def kernel_link(
    session: Session, *, tenant_id: uuid.UUID, project_id: str
) -> dict[str, bool]:
    """Whether the execution kernel will act on this project.

    Answered through a definer function with a two-boolean result, because the
    application must not be able to read or change which projects may execute —
    see migration 0024. A project that is not linked is not broken; it is
    waiting for an operator.
    """
    row = session.execute(
        text("SELECT linked, enabled FROM public.project_kernel_link(:t, :p)"),
        {"t": str(tenant_id), "p": project_id},
    ).one_or_none()
    if row is None:
        return {"kernelLinked": False, "kernelEnabled": False}
    return {"kernelLinked": bool(row[0]), "kernelEnabled": bool(row[1])}


def create_project(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    code: str,
    display_name: str,
    created_by_user_id: str,
    now: dt.datetime,
) -> dict[str, Any]:
    """Create a project and make its creator the owner.

    Both in one transaction. A project that exists without an owner is one
    nobody can administer — and the person most surprised by that is whoever
    just created it.
    """
    if not CODE_PATTERN.match(code):
        raise InvError(
            VAL_SCHEMA,
            "a project code is lowercase letters, digits and hyphens, 3-64 characters",
            extra={"code": code},
        )
    if not display_name.strip():
        raise InvError(VAL_SCHEMA, "a project needs a display name")

    creator = session.get(User, created_by_user_id, populate_existing=True, with_for_update={"read": True})
    if creator is None or creator.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "user not found")
    if creator.status != "active":
        # A suspended account creating projects would survive its own
        # suspension by leaving owned projects behind.
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "a suspended user cannot create projects",
            extra={"userStatus": creator.status},
        )

    existing = session.scalars(
        select(Project).where(Project.tenant_id == tenant_id, Project.code == code)
    ).one_or_none()
    if existing is not None:
        raise InvError(
            VAL_SCHEMA,
            "a project with this code already exists",
            extra={"code": code},
        )

    project = Project(
        project_id=new_id("project"),
        tenant_id=tenant_id,
        code=code,
        display_name=display_name.strip(),
        status="active",
        created_at=now,
    )
    session.add(project)
    session.flush()
    session.add(
        ProjectMember(
            tenant_id=tenant_id,
            project_id=project.project_id,
            user_id=created_by_user_id,
            role_code="owner",
            granted_at=now,
        )
    )
    session.flush()
    return project_body(session, project, tenant_id=tenant_id)


def project_body(
    session: Session, project: Project, *, tenant_id: uuid.UUID
) -> dict[str, Any]:
    members = session.execute(
        select(func.count()).select_from(ProjectMember).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project.project_id,
        )
    ).scalar_one()
    body = {
        "projectId": project.project_id,
        "code": project.code,
        "displayName": project.display_name,
        "status": project.status,
        "memberCount": members,
        "createdAt": project.created_at.isoformat(),
    }
    body.update(kernel_link(session, tenant_id=tenant_id, project_id=project.project_id))
    if not body["kernelLinked"]:
        # Said plainly, because the alternative is an authorisation error about
        # something the person reading it cannot fix.
        body["kernelNote"] = (
            "This project is not connected to the execution kernel yet, so it "
            "cannot run anything. An operator links it; creating a project "
            "deliberately does not grant the right to run code on a machine."
        )
    elif not body["kernelEnabled"]:
        body["kernelNote"] = (
            "The execution kernel link for this project is disabled. An "
            "operator can re-enable it."
        )
    return body


def list_projects(
    session: Session, *, tenant_id: uuid.UUID, user_id: str
) -> list[dict[str, Any]]:
    """Projects this user is actually a member of, read now.

    Not from the credential. A project created moments ago belongs in this list,
    and a membership revoked moments ago does not — neither of which a set fixed
    at sign-in time can express.
    """
    rows = session.execute(
        select(Project, ProjectMember.role_code)
        .join(
            ProjectMember,
            (ProjectMember.tenant_id == Project.tenant_id)
            & (ProjectMember.project_id == Project.project_id),
        )
        .where(Project.tenant_id == tenant_id, ProjectMember.user_id == user_id)
        .order_by(Project.code)
    ).all()
    out = []
    for project, role_code in rows:
        body = project_body(session, project, tenant_id=tenant_id)
        body["roleCode"] = role_code
        permission = settings_service.effective_permission(
            session, tenant_id=tenant_id, project_id=project.project_id, user_id=user_id)
        body["canRequest"] = permission["canRequest"]
        body["canApprove"] = permission["canApprove"]
        out.append(body)
    return out


def require_project_access(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str
) -> dict[str, Any]:
    """The live replacement for ``Principal.require_project``.

    Reports the same denial whether the project does not exist or the caller
    simply cannot see it. Distinguishing them would confirm the existence of
    another project's identifier to someone who has no access to it.
    """
    membership = session.get(ProjectMember, (tenant_id, project_id, user_id), populate_existing=True)
    user = session.get(User, user_id, populate_existing=True)
    if membership is None or user is None or user.tenant_id != tenant_id or user.status != "active":
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "project is not accessible to this principal",
            extra={"projectId": project_id},
        )
    return settings_service.effective_permission(
        session, tenant_id=tenant_id, project_id=project_id, user_id=user_id
    )


# --------------------------------------------------------------------------
# Workspaces
# --------------------------------------------------------------------------


def create_workspace(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    name: str,
    created_by_user_id: str,
    now: dt.datetime,
) -> dict[str, Any]:
    """Create a workspace inside a project the caller may act in.

    Requires ``canRequest`` rather than ownership: a maintainer who may run work
    is a maintainer who needs somewhere to run it. Creating one is not an
    administrative act.

    It starts ``provisioning``, not ``ready``. Nothing has prepared any storage
    yet, and a workspace that claims to be ready before anything provisioned it
    is one that fails at the moment someone puts files in it.
    """
    if not WORKSPACE_NAME_PATTERN.match(name or ""):
        raise InvError(
            VAL_SCHEMA, "a workspace name is 2-128 characters", extra={"name": name}
        )
    settings_service.lock_project(session, tenant_id, project_id)
    permission = require_project_access(
        session, tenant_id=tenant_id, project_id=project_id, user_id=created_by_user_id
    )
    if not permission["canRequest"]:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "this project role may not create workspaces",
            extra={"roleCode": permission["roleCode"]},
        )

    clash = session.scalars(
        select(Workspace).where(
            Workspace.tenant_id == tenant_id,
            Workspace.project_id == project_id,
            Workspace.name == name,
        )
    ).one_or_none()
    if clash is not None:
        raise InvError(
            VAL_SCHEMA, "a workspace with this name already exists in the project"
        )

    workspace = Workspace(
        workspace_id=new_id("workspace"),
        tenant_id=tenant_id,
        project_id=project_id,
        name=name,
        status="provisioning",
        created_by_user_id=created_by_user_id,
        created_at=now,
    )
    session.add(workspace)
    session.flush()
    return workspace_body(workspace)


def workspace_body(workspace: Workspace) -> dict[str, Any]:
    return {
        "workspaceId": workspace.workspace_id,
        "projectId": workspace.project_id,
        "name": workspace.name,
        "status": workspace.status,
        "nodeId": workspace.node_id,
        "toolName": workspace.tool_name,
        "createdAt": workspace.created_at.isoformat(),
        "allowedNext": sorted(
            settings_service.WORKSPACE_TRANSITIONS.get(workspace.status, ())
        ),
    }


def set_workspace_tool(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    tool_name: str | None,
    acting_user_id: str,
) -> dict[str, Any]:
    """Choose which development tool this workspace uses.

    Requires ``canRequest``, not ownership: whoever may run work in a workspace
    is who needs to say what runs it.

    The name is checked against the adapter definitions rather than a list
    repeated here — the tools are code, and a second list would be a second
    answer. What this does **not** check is whether the tool is installed and
    signed in: that is a property of a node at the moment of execution, and a
    workspace configured last week cannot promise anything about a machine
    today. Recording an unusable choice and reporting it as unusable is more
    honest than refusing to record it, because the fix is on the node.
    """
    from ..adapters import agents

    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "workspace not found")
    settings_service.lock_project(session, tenant_id, workspace.project_id)
    session.refresh(workspace, with_for_update=True)
    if workspace.status not in {"provisioning", "ready", "suspended"}:
        raise InvError(VAL_SCHEMA, "workspace is no longer configurable")
    if tool_name is not None and tool_name not in agents.BY_NAME:
        raise InvError(
            VAL_SCHEMA,
            f"unknown development tool: {tool_name!r}",
            extra={"known": sorted(agents.BY_NAME)},
        )
    permission = require_project_access(
        session,
        tenant_id=tenant_id,
        project_id=workspace.project_id,
        user_id=acting_user_id,
    )
    if not permission["canRequest"]:
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "this project role may not configure a workspace tool",
            extra={"roleCode": permission["roleCode"]},
        )
    if tool_name is not None and agents.BY_NAME[tool_name].prompt_args is None:
        # A tool with no headless mode cannot be driven by the platform at all,
        # so choosing it would configure a workspace that can never run.
        raise InvError(
            VAL_SCHEMA,
            f"{tool_name} has no non-interactive mode, so the platform cannot "
            f"drive it",
            extra={"toolName": tool_name},
        )

    workspace.tool_name = tool_name
    workspace.version += 1
    session.flush()
    body = workspace_body(workspace)
    # Said beside the choice, not instead of it: the node decides whether this
    # is usable right now, and the answer can change between requests.
    body["toolReadiness"] = ({"adapter": tool_name, "nodeId": workspace.node_id,
        "ready": False, "state": "unknown", "measurementScope": "workspace-node",
        "reason": "Fresh authenticated Node tool observation is required"} if tool_name else None)
    return body


def list_workspaces(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str
) -> list[dict[str, Any]]:
    """Workspaces in a project the caller may see. Deleted ones are excluded.

    A deleted workspace in a list is a workspace someone will try to open.
    """
    require_project_access(
        session, tenant_id=tenant_id, project_id=project_id, user_id=user_id
    )
    rows = session.scalars(
        select(Workspace)
        .where(
            Workspace.tenant_id == tenant_id,
            Workspace.project_id == project_id,
            Workspace.status != "deleted",
        )
        .order_by(Workspace.name)
    ).all()
    return [workspace_body(w) for w in rows]
