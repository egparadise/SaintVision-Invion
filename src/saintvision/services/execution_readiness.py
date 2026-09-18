"""Explain workspace preconditions and who can resolve each unmet condition.

Project/subject links, business membership, workspace lifecycle, the separate
kernel execution grant, Node tool readiness and pending input are independent
checks. None of them grants admission. The web process reads the kernel-owned
links and prepared input; it cannot use this diagnostic to create authority.
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

#: The kernel's bound on a workspace snapshot. Small and surprising: the files
#: travel inside a signed launch payload rather than through an object store, so
#: a person editing anything substantial hits it. Reported with the readiness
#: answer rather than after a rejection.
MAX_INPUT_BYTES: Final[int] = 65536
MAX_INPUT_CONTENT_BYTES: Final[int] = 32768

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


def _subject_registered(session: Session, *, tenant_id: uuid.UUID, user_id: str) -> bool:
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
            remedy=("ask the operator to enable this project for managed execution"),
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
            remedy=("ask the operator to register this account for managed execution"),
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

    allowed = bool(
        session.execute(
            text("SELECT public.business_execution_permission(:t,:p,:u)"),
            {"t": str(tenant_id), "p": workspace.project_id, "u": user_id},
        ).scalar()
    )
    checks.append(
        _check(
            "kernel_request_permission",
            allowed,
            owner=OPERATOR,
            detail="the current account and project must have an enabled execution grant",
            remedy="ask the operator to review this account's project execution permission",
        )
    )
    checks.append(_tool_check(workspace))
    checks.append(_input_check(session, tenant_id=tenant_id, workspace_id=workspace_id))

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


def _input_check(session: Session, *, tenant_id: uuid.UUID, workspace_id: str) -> dict[str, Any]:
    """Whether anything has been prepared to run.

    An additional precondition, and one a user meets *after* satisfying the
    other five: everything is permitted, everything is linked, and there is
    still nothing to approve because no input was submitted.

    Read, never written. The kernel's prepare endpoints accept the files and
    record them; this side only asks whether that happened. Writing here would
    make a second account of what is about to execute, which is the mistake this
    surface has already made four times.
    """
    row = session.execute(
        text(
            "SELECT prepared, kind, run_id, step_id, snapshot_bytes "
            "FROM public.workspace_input_state(:t, :w)"
        ),
        {"t": str(tenant_id), "w": workspace_id},
    ).one_or_none()

    if row is None:
        body = _check(
            "input_prepared",
            False,
            owner=REQUESTER,
            detail=(
                "no pending input in the current recovery epoch belongs to this "
                "workspace and project"
            ),
            remedy=(
                "prepare the files for a new execution or recovery; the snapshot is capped at "
                f"{MAX_INPUT_BYTES} bytes with at most "
                f"{MAX_INPUT_CONTENT_BYTES} bytes of file content"
            ),
        )
        return {
            **body,
            "snapshotBytes": None,
            "maxSnapshotBytes": MAX_INPUT_BYTES,
            "maxContentBytes": MAX_INPUT_CONTENT_BYTES,
            "runId": None,
        }

    prepared, kind, run_id, step_id, snapshot_bytes = row
    body = _check(
        "input_prepared",
        bool(prepared),
        owner=REQUESTER,
        detail=(
            f"{kind} input is prepared for run {run_id} step {step_id!r} "
            f"({snapshot_bytes} of {MAX_INPUT_BYTES} bytes)"
        ),
    )
    # Reported whether or not the check passed: a screen that shows how close to
    # the bound the last submission came is one that can warn before the next
    # one is refused.
    body["snapshotBytes"] = snapshot_bytes
    body["maxSnapshotBytes"] = MAX_INPUT_BYTES
    body["maxContentBytes"] = MAX_INPUT_CONTENT_BYTES
    body["runId"] = run_id
    return body


def _tool_check(workspace: Workspace) -> dict[str, Any]:
    # CP PATH/login files say nothing about the selected Node. This read cannot
    # run a local CLI probe or substitute its readiness for remote observation.
    if workspace.tool_name is None:
        return _check(
            "tool_chosen_and_usable",
            False,
            owner=REQUESTER,
            detail="no development tool has been chosen for this workspace",
            remedy="choose a development tool for this workspace",
        )
    return _check(
        "tool_chosen_and_usable",
        False,
        owner=NODE_OWNER,
        detail=f"{workspace.tool_name}: readiness on the workspace Node is unknown",
        remedy="connect the selected Node and verify its tool installation and login",
    )
