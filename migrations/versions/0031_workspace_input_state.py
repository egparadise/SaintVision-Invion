"""Whether a workspace has input prepared, and how much room is left.

Revision ID: 0031_workspace_input_state
Revises: 0030_apply_resource_offer
Create Date: 2026-09-11

``execution-readiness`` reports five preconditions. A user who satisfies all five
then meets a sixth that nothing told them about: **there is no input**. The
kernel's ``prepare`` endpoints accept the workspace files and record them in
``inv.workspace_starts`` (first execution) or ``inv.workspace_resumptions``
(after a recovery), and until one of those rows exists there is nothing to
approve and nothing to run.

That is a readiness question, not a result question, so it belongs beside the
other five rather than being discovered by pressing a button. This function is
how the business surface **reads** it — the writing is the kernel's and stays
there.

It also returns the size bound, because the bound is small and surprising.
``snapshot`` is capped at 64 KiB and the file content inside it at 32 KiB: these
travel inside a signed launch payload, not through an object store. A person
editing anything substantial will hit that, and a screen that only says
"rejected" after the fact is worse than one that could have said so while they
were typing.

Tenant-bound from the start, like every definer function added after revision
0027 had to correct that omission in 0024.
"""

from __future__ import annotations

from alembic import op

revision = "0031_workspace_input_state"
down_revision = "0030_apply_resource_offer"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.workspace_input_state"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_workspace_id text
        ) RETURNS TABLE (
            prepared boolean,
            kind text,
            run_id text,
            step_id text,
            snapshot_bytes integer
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $fn$
            SELECT * FROM (
                SELECT true, 'first'::text, s.run_id, s.step_id,
                       pg_catalog.octet_length(s.snapshot)
                FROM inv.workspace_starts s
                WHERE s.tenant_id = p_tenant_id
                  AND s.workspace_id = p_workspace_id
                  AND p_tenant_id = nullif(
                      pg_catalog.current_setting('inv.tenant_id', true), ''
                  )::uuid
                UNION ALL
                SELECT true, 'resume'::text, r.run_id, r.step_id,
                       pg_catalog.octet_length(r.snapshot)
                FROM inv.workspace_resumptions r
                WHERE r.tenant_id = p_tenant_id
                  AND r.workspace_id = p_workspace_id
                  AND p_tenant_id = nullif(
                      pg_catalog.current_setting('inv.tenant_id', true), ''
                  )::uuid
                ORDER BY 3 DESC
                LIMIT 1
            ) latest
        $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, text) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, text)")
