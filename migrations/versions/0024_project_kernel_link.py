"""Let the business API tell a user whether their project can actually run.

Revision ID: 0024_project_kernel_link
Revises: 0023_containment_approvals
Create Date: 2026-09-11

A project created through the business API is not yet able to execute anything.
The execution kernel will only act on a project that has a row in
``inv.business_projects`` and an operator-registered subject mapping in
``inv.business_subjects`` — both deliberately operator-owned, so that creating a
project cannot also grant it the right to run code on someone's machine.

That separation is correct. What it produces without this revision is a screen
that shows a project, a workspace and a "run" button, and an execution request
that is refused with an authorisation error the person cannot act on — because
the thing that is missing is not their permission, it is an operator step
nobody told them about.

``inv_app`` cannot read those tables and should not be able to: they decide
which projects may execute, and the web process is the last thing that should be
able to enumerate or alter that. So this is one function with the narrowest
possible answer — two booleans for one project — behind the same pattern as
``public.node_by_certificate``:

* it answers about one project the caller already names, so it cannot enumerate;
* it returns whether the link exists and whether it is enabled, and nothing
  else — no subject ids, no other projects, no grant details;
* ``search_path`` is pinned, because a SECURITY DEFINER function that resolves
  names through the caller's path is the usual way this feature becomes a
  privilege escalation.

The result is that "created but not yet connected" becomes a state the API can
report and a screen can explain, instead of a permission error at the moment
someone tries to run something.
"""

from __future__ import annotations

from alembic import op

revision = "0024_project_kernel_link"
down_revision = "0023_containment_approvals"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.project_kernel_link"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_project_id text
        ) RETURNS TABLE (linked boolean, enabled boolean)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        -- Pinned: resolving through the caller's search_path is how a
        -- SECURITY DEFINER function becomes a privilege escalation.
        SET search_path = pg_catalog, public, inv
        AS $fn$
            SELECT
                EXISTS (
                    SELECT 1 FROM inv.business_projects b
                    WHERE b.tenant_id = p_tenant_id AND b.project_id = p_project_id
                ),
                COALESCE(
                    (
                        SELECT b.enabled FROM inv.business_projects b
                        WHERE b.tenant_id = p_tenant_id
                          AND b.project_id = p_project_id
                    ),
                    false
                )
        $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, text) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, text)")
