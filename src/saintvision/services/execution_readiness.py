"""Why this workspace cannot run yet, and who can fix each reason.

"실제 계정으로 생성한 Workspace가 실행 가능해지고" has five preconditions, and
they are owned by four different people. Without something that states all five
at once, the failure a user meets is whichever one the execution path happens to
check first — reported as an authorisation error, which is only the right words
for one of them.

The five, and who owns each:

1. **The project is linked to the execution kernel.** ``inv.business_projects``,
   operator-owned, because creating a project must not also grant the right to
   run code on somebody's machine.
2. **The requester is registered as a kernel subject.**
   ``inv.business_subjects``, operator-owned and one-to-one, because a
   two-person rule one person can satisfy with two identities is not a
   two-person rule.
3. **The requester's project role permits requesting.** ``project_members`` —
   owned by a project owner, changeable through this API.
4. **The workspace is ready.** Owned by whoever provisioned it.
5. **A development tool is chosen and usable on a node.** The choice is a
   property of the workspace; usability is a property of a machine right now.

This module answers all five in one call, and for each unmet one it says who
fixes it. That distinction is the whole point: "you are not allowed" and "an
operator has not finished setting this up" feel identical to whoever is blocked
and need completely different next actions.

**It never makes anything ready.** The two operator-owned links are deliberately
out of reach of the web process; a function here that could satisfy them would
be a way for the application to grant itself execution rights, which is exactly
what their ownership prevents.
"""

from __future__ import annotations

import uuid
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db.models import Workspace
from ..errors import RES_NODE_NOT_FOUND, InvError
from . import projects as project_service
from . import settings as settings_service

#: Who resolves an unmet precondition. Reported per check, because "you may not"
#: and "nobody has set this up yet" need different actions from different people.
OPERATOR: Final[str] = "operator"
PROJECT_OWNER: Final[str] = "project owner"
NODE_OWNER: Final[str] = "node owner"
REQUESTER: Final[str] = "requester"


def _check(
    name: str, satisfied: bool, *, owner: str, detail: str, remedy: str | None = None
) -> dict[str, Any]:
    body = {"check": name, "satisfied": satisfied, "detail": detail}
    if not satisfied:
        body["resolvedBy"] = owner
        if remedy:
            body["remedy"] = remedy
    return body


def _subject_registered(
    session: Session, *, tenant_id: uuid.UUID, user_id: str
) -> bool:
    """Whether the kernel knows this person as an approval subject.

    Asked through the same narrow definer route as the project link: the
    application must not be able to enumerate who may approve, only ask about
    one person it already names.
    """
    row = session.execute(
        text("SELECT registered FROM public.subject_kernel_link(:t, :u)"),
        {"t": str(tenant_id), "u": user_id},
    ).one_or_none()
    return bool(row[0]) if row is not None else False


def workspace_readiness(
    session: Session, *, tenant_id: uuid.UUID, workspace_id: str, user_id: str
) -> dict[str, Any]:
    """Every precondition for running work in this workspace, at once."""
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "workspace not found")

    # Authorises first, so the checklist cannot be used to probe a workspace in
    # a project the caller cannot see.
    permission = project_service.require_project_access(
        session,
        tenant_id=tenant_id,
        project_id=workspace.project_id,
        user_id=user_id,
    )

    link = project_service.kernel_link(
        session, tenant_id=tenant_id, project_id=workspace.project_id
    )
    checks: list[dict[str, Any]] = [
        _check(
            "project_linked_to_kernel",
            link["kernelLinked"] and link["kernelEnabled"],
            owner=OPERATOR,
            detail=(
                "the execution kernel acts only on projects an operator has "
                "linked; creating a project deliberately does not grant that"
            ),
            remedy=(
                "ask the operator to enable this project for managed execution"
            ),
        ),
        _check(
            "requester_registered_with_kernel",
            _subject_registered(session, tenant_id=tenant_id, user_id=user_id),
            owner=OPERATOR,
            detail=(
                "approval identity is registered by an operator and is one "
                "subject to one user, so a two-person rule cannot be satisfied "
                "by one person holding two identities"
            ),
            remedy=(
                "ask the operator to register this account for managed execution"
            ),
        ),
        _check(
            "role_permits_requesting",
            permission["canRequest"],
            owner=PROJECT_OWNER,
            detail=(
                f"this user's project role is {permission['roleCode']!r}; roles "
                f"that may request work are "
                f"{sorted(settings_service.CAN_REQUEST)}"
            ),
            remedy="a project owner changes the role through the members API",
        ),
        _check(
            "workspace_ready",
            workspace.status == "ready",
            owner=PROJECT_OWNER,
            detail=f"the workspace status is {workspace.status!r}",
            remedy=(
                "the workspace becomes ready once its storage is provisioned"
                if workspace.status == "provisioning"
                else "a project owner returns the workspace to ready"
            ),
        ),
    ]

    allowed = bool(session.execute(text(
        "SELECT public.business_execution_permission(:t,:p,:u)"),
        {"t": str(tenant_id), "p": workspace.project_id, "u": user_id}).scalar())
    checks.append(_check("kernel_request_permission", allowed, owner=OPERATOR,
        detail="the current account and project must have an enabled execution grant",
        remedy="ask the operator to review this account's project execution permission"))
    checks.append(_tool_check(workspace))

    unmet = [c for c in checks if not c["satisfied"]]
    return {
        "workspaceId": workspace_id,
        "projectId": workspace.project_id,
        "executable": False,
        "scope": "workspace-preconditions-not-execution-admission",
        "nodeReadiness": "unknown",
        "admissionRequired": True,
        "checks": checks,
        # Grouped, because the person reading this needs to know whether to act
        # or to ask somebody else.
        "blockedBy": sorted({c["resolvedBy"] for c in unmet}),
        "summary": f"{len(unmet)} of {len(checks)} preconditions are unmet; Node validation and execution admission are required.",
    }


def _tool_check(workspace: Workspace) -> dict[str, Any]:
    # CP PATH/login files say nothing about the selected Node. This read cannot
    # run a local CLI probe or substitute its readiness for remote observation.
    if workspace.tool_name is None:
        return _check("tool_chosen_and_usable", False, owner=REQUESTER,
            detail="no development tool has been chosen for this workspace",
            remedy="choose a development tool for this workspace")
    return _check("tool_chosen_and_usable", False, owner=NODE_OWNER,
        detail=f"{workspace.tool_name}: readiness on the workspace Node is unknown",
        remedy="connect the selected Node and verify its tool installation and login")
