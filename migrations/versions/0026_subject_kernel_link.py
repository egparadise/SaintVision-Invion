"""Let the business API tell a person whether they may approve yet.

Revision ID: 0026_subject_kernel_link
Revises: 0025_workspace_tool_choice
Create Date: 2026-09-11

The companion to ``public.project_kernel_link``. A person can sign in, belong to
a project and still be unable to approve anything, because approval identity
lives in ``inv.business_subjects`` — operator-registered, immutable and
one-to-one, so that a two-person rule cannot be satisfied by one person holding
two identities.

That is a good property and it is invisible. Without this function the person
meets an authorisation refusal and has no way to tell it apart from "your role
does not permit this", which a project owner could fix and which nobody should
go and change in response to the real cause.

Narrow for the same reasons as 0024: one boolean about one user the caller
already names, so the application cannot enumerate who may approve; and a pinned
``search_path``, because a SECURITY DEFINER function that resolves names through
the caller's path is how this feature becomes a privilege escalation.
"""

from __future__ import annotations

from alembic import op

revision = "0026_subject_kernel_link"
down_revision = "0025_workspace_tool_choice"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.subject_kernel_link"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_user_id char(30)
        ) RETURNS TABLE (registered boolean)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public, inv
        AS $fn$
            SELECT EXISTS (
                SELECT 1 FROM inv.business_subjects s
                WHERE s.tenant_id = p_tenant_id
                  AND s.user_id = p_user_id
                  AND s.enabled
            )
        $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, char(30)) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, char(30)) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, char(30))")
