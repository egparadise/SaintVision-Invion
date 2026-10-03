"""Remove the unused cross-tenant registry read from ``inv_app``.

``0001_s02_baseline`` granted the application role table-wide SELECT on
``public.tenants``.  Unlike the dedicated discovery issuer, which receives only
``tenant_id`` in 0045, no product path running as ``inv_app`` reads this table.
The grant therefore exposed every tenant slug and display name without serving
an application operation.

This is deliberately irreversible.  Downgrading must not silently restore a
cross-tenant read that the forward security review removed.  Restore a database
backup only when the old exposure is explicitly accepted, or use a reviewed
forward migration for a newly demonstrated column-level need.

0065 is reserved by card 263.  Until that revision lands this branch follows
the current 0064 head; the integration train must place 0065 before this
revision if that reservation is exercised.
"""

from alembic import op


revision = "0066_tenant_registry_revoke"
down_revision = "0064_model_version_run_fk"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("REVOKE SELECT ON public.tenants FROM inv_app")


def downgrade():
    raise RuntimeError(
        "Restoring inv_app cross-tenant registry SELECT requires a reviewed forward fix"
    )
