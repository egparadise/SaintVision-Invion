"""Remove the unused cross-tenant registry read from ``inv_app``.

``0001_s02_baseline`` granted the application role table-wide SELECT on
``public.tenants``.  Unlike the dedicated discovery issuer, which receives only
``tenant_id`` in 0045, no product path running as ``inv_app`` reads this table.
The grant therefore exposed every tenant slug and display name without serving
an application operation.

This is deliberately security-irreversible.  Downgrading may remove the
revision marker so older migration rehearsals can continue, but it repeats the
REVOKE instead of restoring the cross-tenant read.  Restoring that exposure
requires a reviewed forward migration for a newly demonstrated column-level
need.

0065 is reserved by card 263.  Until that revision lands this branch follows
the current 0064 head; the integration train must place 0065 before this
revision if that reservation is exercised.
"""

from alembic import op


revision = "0066_tenant_registry_revoke"
down_revision = "0064_model_version_run_fk"
branch_labels = None
depends_on = None
# The migration tooling treats this explicit marker as an irreversible security
# boundary even though downgrade remains executable and fail-closed.  This is
# distinct from a symmetric reversible migration and from a downgrade that can
# only raise.
irreversible = True


def upgrade():
    op.execute("REVOKE SELECT ON public.tenants FROM inv_app")


def downgrade():
    """Keep the security boundary while allowing older revisions to rehearse.

    Re-granting SELECT here would quietly recreate the tenant-enumeration
    exposure.  Repeating the REVOKE is intentionally asymmetric: application
    code that genuinely needs the old grant fails closed until a reviewed
    forward migration defines a narrower contract.
    """
    op.execute("REVOKE SELECT ON public.tenants FROM inv_app")
