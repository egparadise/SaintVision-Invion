"""Let the business API resolve a Run's committed outputs.

Revision ID: 0029_run_outputs
Revises: 0028_subject_kernel_link
Create Date: 2026-09-11

``public.artifacts`` has no link to any byte store — nothing writes it, and an
artifact row there cannot be resolved to a file. The outputs that actually exist
are the kernel's: ``inv.result_commitments`` ties a Run and attempt to an
``object_id``, a ``content_hash`` and the Evidence that recorded it, and
``inv.storage_objects`` holds the size and state. So a download that is real
reads those, not a table that describes files nobody wrote.

``inv_app`` cannot read either table and should not: they are the record of what
executed. This returns the four fields a download needs for one Run the caller
already names, so the application can authorise the request and hand the object
key to the store — it cannot enumerate another project's outputs and it cannot
change any of them.

Written with the tenant binding from the start. A SECURITY DEFINER function runs
as its owner and therefore bypasses row level security, so a caller-supplied
tenant id is not a scope — revision 0027 had to correct exactly that in 0024,
and repeating the mistake here would reintroduce a cross-tenant read on the path
that returns file contents.
"""

from __future__ import annotations

from alembic import op

revision = "0029_run_outputs"
down_revision = "0028_subject_kernel_link"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.run_committed_outputs"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_run_id text
        ) RETURNS TABLE (
            object_id uuid,
            content_hash text,
            size_bytes bigint,
            state text,
            evidence_id text,
            attempt integer,
            prepared_at timestamptz
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $fn$
            SELECT c.object_id, c.content_hash, o.size_bytes, o.state,
                   c.evidence_id, c.attempt, c.prepared_at
            FROM inv.result_commitments c
            JOIN inv.storage_objects o
              ON o.tenant_id = c.tenant_id
             AND o.project_id = c.project_id
             AND o.object_id = c.object_id
            WHERE c.tenant_id = p_tenant_id
              AND c.run_id = p_run_id
              -- The caller supplies the tenant and a definer function bypasses
              -- RLS, so the answer is bound to the scope the session is in.
              AND p_tenant_id = nullif(
                  pg_catalog.current_setting('inv.tenant_id', true), ''
              )::uuid
            ORDER BY c.attempt, c.prepared_at
        $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, text) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, text)")
