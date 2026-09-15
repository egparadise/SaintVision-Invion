"""Current business permission intersects the operator's kernel grant.

Links are operator-owned; browser IDs and JWT roles never create them. One
issuer-qualified subject maps to one business user, preserving distinct voters.
Legacy kernel-only projects have no business link and retain their own grants.
"""

from .errors import DomainError

REQUEST_ROLES = frozenset({"owner", "maintainer", "operator"})
APPROVE_ROLES = frozenset({"owner", "approver"})


def permission(conn, project, subject, required=None, *, linked=False):
    link = conn.execute(
        "SELECT enabled FROM inv.business_projects WHERE project_id=%s FOR SHARE", (project,)
    ).fetchone()
    if link is None and not linked:
        return None
    if not link or not link["enabled"]:
        raise DomainError("AUTH-0030", "Business project permission unavailable", 403)
    project_row = conn.execute(
        "SELECT status FROM public.projects WHERE project_id=%s FOR SHARE", (project,)
    ).fetchone()
    mapping = conn.execute(
        "SELECT * FROM inv.business_subjects WHERE subject_id=%s FOR SHARE", (subject,)
    ).fetchone()
    if (
        not project_row
        or project_row["status"] != "active"
        or not mapping
        or not mapping["enabled"]
    ):
        raise DomainError("AUTH-0030", "Business project permission unavailable", 403)
    user = conn.execute(
        "SELECT status FROM public.users WHERE user_id=%s FOR SHARE", (mapping["user_id"],)
    ).fetchone()
    member = conn.execute(
        "SELECT role_code FROM public.project_members WHERE project_id=%s AND user_id=%s FOR SHARE",
        (project, mapping["user_id"]),
    ).fetchone()
    if not user or user["status"] != "active" or not member:
        raise DomainError("AUTH-0030", "Business project permission unavailable", 403)
    result = {
        "userId": mapping["user_id"],
        "roleCode": member["role_code"],
        "can_request": member["role_code"] in REQUEST_ROLES,
        "can_approve": member["role_code"] in APPROVE_ROLES,
    }
    if not (result["can_request"] or result["can_approve"]) or (required and not result[required]):
        raise DomainError("AUTH-0030", "Business project permission unavailable", 403)
    return result
