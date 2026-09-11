"""Changing who may do what, and what a machine offers.

The business surface's write side. Everything here is a value someone sets on a
screen, and the property that matters is not that it is stored — it is that
**storing it changes what happens next**.

That is not rhetorical. The execution kernel reads these exact rows before it
will start anything: ``inv.business_auth.permission`` selects
``public.project_members.role_code``, ``public.users.status`` and
``public.projects.status`` on every request. So a role written here decides the
next execution request, an archived project stops accepting work, and a
suspended user stops being able to approve — without anything being copied,
synchronised or invalidated. The screen sets a value and the kernel obeys it,
because they are the same row.

The consequence is that the **role vocabulary is a contract, not a preference**.
If this module wrote ``admin`` where the kernel looks for ``owner``, the setting
would save, the screen would show it, and it would mean nothing.
``tests/test_settings.py`` asserts the two sides agree rather than trusting that
they do.

Three rules encoded here, each a way a settings screen quietly breaks something:

**A project always has an owner.** Demoting or removing the last one leaves a
project nobody can administer, and nothing fails at the time — it fails later,
when someone needs to change a membership and there is no one who may.

**An offer is not edited, it is superseded.** ``resource_offers`` carries
``effective_from``/``effective_to`` so a placement made last week can be
explained with last week's offer. Editing the row in place rewrites the reason
for a decision that has already happened.

**An offer is a ceiling for future work, not a recall of current work.** Lowering
it does not release leases the execution core already holds; those run until
they are returned. Saying so in the response is the difference between an
operator who knows that and one who discovers it.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Final

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db.models import (
    NodeCapability,
    Project,
    ProjectMember,
    ResourceOffer,
    Node,
    User,
    Workspace,
)
from ..errors import AUTH_PROJECT_SCOPE, RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..ids import new_id
from ..units import canonical_unit, to_canonical

#: The project roles. This vocabulary is read by the execution kernel
#: (``inv.business_auth``), so it is a contract: a value outside this set saves
#: and then means nothing, which is worse than an error.
PROJECT_ROLES: Final[tuple[str, ...]] = (
    "owner",
    "maintainer",
    "operator",
    "approver",
    "viewer",
)

#: Who may ask for work to run. Mirrors ``inv.business_auth.REQUEST_ROLES``.
CAN_REQUEST: Final[frozenset[str]] = frozenset({"owner", "maintainer", "operator"})

#: Who may approve it. Deliberately not a superset of the above — an approver
#: who may also request is one person short of a two-person rule.
CAN_APPROVE: Final[frozenset[str]] = frozenset({"owner", "approver"})

#: Who may change settings. Narrower than everything else on purpose.
CAN_ADMINISTER: Final[frozenset[str]] = frozenset({"owner"})

WORKSPACE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "provisioning": frozenset({"ready", "deleting"}),
    "ready": frozenset({"suspended", "deleting"}),
    "suspended": frozenset({"ready", "deleting"}),
    "deleting": frozenset({"deleted"}),
    "deleted": frozenset(),
}


# --------------------------------------------------------------------------
# The permission check every setting is guarded by, and that the kernel mirrors
# --------------------------------------------------------------------------


def lock_project(session: Session, tenant_id: uuid.UUID, project_id: str) -> Project:
    # Serialize every membership writer before checking the actor and owner count.
    project = session.scalars(select(Project).where(
        Project.tenant_id == tenant_id, Project.project_id == project_id
    ).with_for_update().execution_options(populate_existing=True)).one_or_none()
    if project is None:
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")
    return project


def require_global_administrator(session: Session, *, tenant_id: uuid.UUID,
                                 user_id: str, permission: str,
                                 target_user_id: str | None = None) -> None:
    # Project ownership never grants tenant administration. Sorted user locks
    # also serialize two administrators changing each other's status.
    session.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.user_id.in_(sorted({user_id, target_user_id or user_id})),
    ).order_by(User.user_id).with_for_update().execution_options(populate_existing=True)).all()
    allowed = session.execute(text(
        "SELECT public.business_admin_allowed(:t,:u,:p)"
    ), {"t": tenant_id, "u": user_id, "p": permission}).scalar_one()
    if not allowed:
        raise InvError(AUTH_PROJECT_SCOPE, "current tenant administration permission required")


def effective_permission(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str
) -> dict[str, Any]:
    """What this user may do in this project, right now.

    Reads the three rows the kernel reads, in the same order and for the same
    reason. Row level security gives tenant isolation and stops there — a user
    belongs to some projects in their tenant and not others, and no policy
    expresses that, so this is not defence in depth.

    ``users.status`` is part of the answer, not a separate concern. If
    suspension were only checked at login, a suspended user's open session would
    keep approving until it expired.
    """
    project = session.get(Project, project_id)
    if project is None or project.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "project not found")
    user = session.get(User, user_id, populate_existing=True, with_for_update={"read": True})
    membership = session.get(ProjectMember, (tenant_id, project_id, user_id), populate_existing=True)

    active = (
        project.status == "active"
        and user is not None
        and user.tenant_id == tenant_id
        and user.status == "active"
        and membership is not None
    )
    role = membership.role_code if membership is not None else None
    return {
        "projectId": project_id,
        "userId": user_id,
        "roleCode": role,
        "projectStatus": project.status,
        "userStatus": user.status if user is not None else None,
        # False whenever any of the three rows says no, so a caller cannot read
        # the role and reach its own conclusion.
        "canRequest": bool(active and role in CAN_REQUEST),
        "canApprove": bool(active and role in CAN_APPROVE),
        "canAdminister": bool(active and role in CAN_ADMINISTER),
    }


def require_administrator(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str,
    allow_archived: bool = False,
) -> dict[str, Any]:
    permission = effective_permission(
        session, tenant_id=tenant_id, project_id=project_id, user_id=user_id
    )
    archived_owner = (allow_archived and permission["projectStatus"] == "archived"
                      and permission["userStatus"] == "active"
                      and permission["roleCode"] in CAN_ADMINISTER)
    if not (permission["canAdminister"] or archived_owner):
        raise InvError(
            AUTH_PROJECT_SCOPE,
            "only a project owner may change project settings",
            extra={"roleCode": permission["roleCode"]},
        )
    return permission


# --------------------------------------------------------------------------
# Membership
# --------------------------------------------------------------------------


def _owner_count(session: Session, tenant_id: uuid.UUID, project_id: str) -> int:
    return len(
        session.scalars(
            select(ProjectMember.user_id).where(
                ProjectMember.tenant_id == tenant_id,
                ProjectMember.project_id == project_id,
                ProjectMember.role_code == "owner",
            )
        ).all()
    )


def set_member_role(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    user_id: str,
    role_code: str,
    acting_user_id: str,
    now: dt.datetime,
) -> dict[str, Any]:
    """Grant or change one membership.

    Refuses to remove the last owner by demotion. A project with no owner keeps
    working until the day someone has to change something, and then nobody can —
    which is a failure that arrives long after the change that caused it.
    """
    if role_code not in PROJECT_ROLES:
        raise InvError(
            VAL_SCHEMA,
            f"unknown project role: {role_code!r}",
            extra={"allowed": list(PROJECT_ROLES)},
        )
    lock_project(session, tenant_id, project_id)
    require_administrator(
        session, tenant_id=tenant_id, project_id=project_id, user_id=acting_user_id
    )
    user = session.get(User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "user not found")

    existing = session.get(ProjectMember, (tenant_id, project_id, user_id))
    if (
        existing is not None
        and existing.role_code == "owner"
        and role_code != "owner"
        and _owner_count(session, tenant_id, project_id) == 1
    ):
        raise InvError(
            VAL_SCHEMA,
            "this is the project's only owner; promote another owner first",
            extra={"projectId": project_id},
        )

    if existing is None:
        session.add(
            ProjectMember(
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=user_id,
                role_code=role_code,
                granted_at=now,
            )
        )
    else:
        existing.role_code = role_code
    session.flush()
    return effective_permission(
        session, tenant_id=tenant_id, project_id=project_id, user_id=user_id
    )


def remove_member(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    user_id: str,
    acting_user_id: str,
) -> None:
    lock_project(session, tenant_id, project_id)
    require_administrator(
        session, tenant_id=tenant_id, project_id=project_id, user_id=acting_user_id
    )
    existing = session.get(ProjectMember, (tenant_id, project_id, user_id))
    if existing is None:
        return
    if existing.role_code == "owner" and _owner_count(session, tenant_id, project_id) == 1:
        raise InvError(
            VAL_SCHEMA, "this is the project's only owner; promote another owner first"
        )
    session.delete(existing)
    session.flush()


def list_members(
    session: Session, *, tenant_id: uuid.UUID, project_id: str
) -> list[dict[str, Any]]:
    project = session.get(Project, project_id, populate_existing=True)
    project_active = project is not None and project.tenant_id == tenant_id and project.status == "active"
    rows = session.execute(
        select(ProjectMember, User)
        .join(
            User,
            (User.tenant_id == ProjectMember.tenant_id)
            & (User.user_id == ProjectMember.user_id),
        )
        .where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
        )
        .order_by(ProjectMember.user_id)
    ).all()
    return [
        {
            "userId": member.user_id,
            "displayName": user.display_name,
            "roleCode": member.role_code,
            "userStatus": user.status,
            # Shown beside the role because the role alone does not decide it:
            # a suspended owner may do nothing at all.
            "canRequest": project_active and user.status == "active" and member.role_code in CAN_REQUEST,
            "canApprove": project_active and user.status == "active" and member.role_code in CAN_APPROVE,
            "grantedAt": member.granted_at.isoformat(),
        }
        for member, user in rows
    ]


# --------------------------------------------------------------------------
# User and project status
# --------------------------------------------------------------------------


def set_user_status(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: str,
    status: str,
    now: dt.datetime,
) -> User:
    """Suspend or restore a user.

    Takes effect on the next permission check anywhere, because the kernel reads
    this row rather than a copy of it. Nothing has to be invalidated and no
    session has to expire.
    """
    if status not in ("active", "suspended", "retired"):
        raise InvError(VAL_SCHEMA, f"unknown user status: {status!r}")
    user = session.get(User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "user not found")
    if user.status == "retired" and status != "retired":
        # Retirement is how a person leaves. Reversing it would mean a departed
        # account can be brought back without anyone re-granting anything.
        raise InvError(VAL_SCHEMA, "a retired user cannot be reactivated")
    user.status = status
    user.updated_at = now
    session.flush()
    return user


def set_project_status(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    status: str,
    acting_user_id: str,
) -> Project:
    """Archive or reactivate a project. Archiving stops all execution in it."""
    if status not in ("active", "archived"):
        raise InvError(VAL_SCHEMA, f"unknown project status: {status!r}")
    project = lock_project(session, tenant_id, project_id)
    require_administrator(
        session, tenant_id=tenant_id, project_id=project_id, user_id=acting_user_id,
        allow_archived=True,
    )
    project.status = status
    project.version += 1
    session.flush()
    return project


# --------------------------------------------------------------------------
# Workspaces
# --------------------------------------------------------------------------


def set_workspace_status(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    status: str,
    acting_user_id: str,
    now: dt.datetime,
) -> Workspace:
    """Move a workspace through its lifecycle, one legal step at a time.

    ``deleted`` is reachable only through ``deleting``. A workspace that jumps
    straight to deleted is one whose files nothing was asked to remove.
    """
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "workspace not found")
    lock_project(session, tenant_id, workspace.project_id)
    session.refresh(workspace, with_for_update=True)
    require_administrator(
        session,
        tenant_id=tenant_id,
        project_id=workspace.project_id,
        user_id=acting_user_id,
    )
    allowed = WORKSPACE_TRANSITIONS.get(workspace.status, frozenset())
    if status != workspace.status and status not in allowed:
        raise InvError(
            VAL_SCHEMA,
            f"a workspace cannot go from {workspace.status!r} to {status!r}",
            extra={"allowed": sorted(allowed)},
        )
    workspace.status = status
    workspace.deleted_at = now if status == "deleted" else None
    workspace.version += 1
    session.flush()
    return workspace


# --------------------------------------------------------------------------
# What a machine offers
# --------------------------------------------------------------------------


def current_offer(
    session: Session, *, tenant_id: uuid.UUID, capability_id: str, now: dt.datetime
) -> ResourceOffer | None:
    return session.scalars(
        select(ResourceOffer)
        .where(
            ResourceOffer.tenant_id == tenant_id,
            ResourceOffer.capability_id == capability_id,
            ResourceOffer.effective_from <= now,
            (ResourceOffer.effective_to.is_(None))
            | (ResourceOffer.effective_to > now),
        )
        .order_by(ResourceOffer.effective_from.desc())
    ).first()


def set_resource_offer(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    capability_id: str,
    offered_quantity: float,
    unit: str,
    now: dt.datetime,
) -> dict[str, Any]:
    """Change how much of one capability the platform may use.

    The previous offer is **closed**, not edited. ``effective_from`` and
    ``effective_to`` exist so a placement decision made last week can be
    explained with the offer that was in force last week; rewriting the row
    would rewrite the reason for something that already happened.

    The quantity is converted from whatever unit the caller sent — a screen
    offering "32 GiB" and a screen offering bytes must land on the same number,
    and ``saintvision.units`` is the only place that conversion happens.

    Lowering an offer is a ceiling for future reservations, not a recall of
    current ones. Work the execution core has already leased runs until it is
    returned. The response says so rather than leaving the operator to find out.
    """
    capability = session.get(NodeCapability, capability_id)
    if capability is None or capability.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "capability not found")
    # Match placement's Node -> capability lock order; reread after waiting.
    session.scalars(select(Node).where(Node.node_id == capability.node_id,
                                      Node.tenant_id == tenant_id).with_for_update()).one()
    session.refresh(capability, with_for_update=True)

    canonical = to_canonical(capability.kind, offered_quantity, unit)
    if canonical > capability.total_quantity:
        raise InvError(
            VAL_SCHEMA,
            "a node cannot offer more than it has",
            extra={
                "offered": canonical,
                "total": capability.total_quantity,
                "unit": canonical_unit(capability.kind),
            },
        )

    previous = session.scalars(select(ResourceOffer).where(
        ResourceOffer.tenant_id == tenant_id, ResourceOffer.capability_id == capability_id,
        ResourceOffer.effective_to.is_(None),
    ).with_for_update().execution_options(populate_existing=True)).one_or_none()
    if previous is not None:
        if previous.offered_quantity == canonical:
            # Setting the same number is not a change. Writing a new row anyway
            # would fill the history with events that record nothing.
            return _offer_body(capability, previous, previous, now)
        now = max(now, previous.effective_from + dt.timedelta(microseconds=1))
        previous.effective_to = now

    offer = ResourceOffer(
        offer_id=new_id("offer"),
        tenant_id=tenant_id,
        capability_id=capability_id,
        offered_quantity=canonical,
        effective_from=now,
    )
    session.add(offer)
    session.flush()
    return _offer_body(capability, offer, previous, now)


def _offer_body(
    capability: NodeCapability,
    offer: ResourceOffer,
    previous: ResourceOffer | None,
    now: dt.datetime,
) -> dict[str, Any]:
    lowered = previous is not None and offer.offered_quantity < previous.offered_quantity
    return {
        "capabilityId": capability.capability_id,
        "nodeId": capability.node_id,
        "kind": capability.kind,
        "unit": canonical_unit(capability.kind),
        "offeredQuantity": offer.offered_quantity,
        "totalQuantity": capability.total_quantity,
        "previousOfferedQuantity": (
            previous.offered_quantity if previous is not None else None
        ),
        "effectiveFrom": offer.effective_from.isoformat(),
        # Said plainly, because it is the part that surprises people.
        "note": (
            "A lowered offer applies to new reservations. Work already leased "
            "by the execution core runs until it is returned."
            if lowered
            else "The offer is a ceiling the platform may use, not a promise."
        ),
    }


def node_offers(
    session: Session, *, tenant_id: uuid.UUID, node_id: str, now: dt.datetime
) -> list[dict[str, Any]]:
    """Everything one machine currently offers, beside what it actually has."""
    capabilities = session.scalars(
        select(NodeCapability)
        .where(
            NodeCapability.tenant_id == tenant_id, NodeCapability.node_id == node_id
        )
        .order_by(NodeCapability.kind, NodeCapability.device_index)
    ).all()
    out = []
    for capability in capabilities:
        offer = current_offer(
            session,
            tenant_id=tenant_id,
            capability_id=capability.capability_id,
            now=now,
        )
        out.append(
            {
                "capabilityId": capability.capability_id,
                "kind": capability.kind,
                "deviceIndex": capability.device_index,
                "vendor": capability.vendor,
                "model": capability.model,
                "unit": canonical_unit(capability.kind),
                "totalQuantity": capability.total_quantity,
                "offeredQuantity": offer.offered_quantity if offer else 0,
                "divisible": capability.divisible,
            }
        )
    return out
