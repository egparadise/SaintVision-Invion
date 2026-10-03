"""Remove the unused cross-tenant audit reader boundary.

``0047_audit_events_isolation`` created ``inv_audit_reader`` as a dedicated,
NOLOGIN role with unconditional SELECT visibility over ``public.audit_events``.
That privilege made tenant-less denials observable, but no product connection,
role-assumption, membership-grant or operator read path was ever implemented.
Keeping a dormant cross-tenant grant therefore preserves exposure without a
consumer.

The role itself is retained because PostgreSQL roles are cluster-scoped.  This
revision removes its table and schema privileges and its unconditional policy.
It is deliberately security-irreversible: downgrade repeats the same removals
instead of recreating an unused cross-tenant reader.  A future audit export must
arrive as a reviewed, narrower forward design.
"""

from alembic import op


revision = "0067_audit_reader_revoke"
down_revision = "0066_tenant_registry_revoke"
branch_labels = None
depends_on = None
irreversible = True


def upgrade():
    op.execute("DROP POLICY IF EXISTS audit_events_audit_read ON public.audit_events")
    op.execute("REVOKE SELECT ON public.audit_events FROM inv_audit_reader")
    op.execute("REVOKE USAGE ON SCHEMA public FROM inv_audit_reader")


def downgrade():
    """Keep the least-privilege boundary while moving the revision marker back."""
    op.execute("DROP POLICY IF EXISTS audit_events_audit_read ON public.audit_events")
    op.execute("REVOKE SELECT ON public.audit_events FROM inv_audit_reader")
    op.execute("REVOKE USAGE ON SCHEMA public FROM inv_audit_reader")
