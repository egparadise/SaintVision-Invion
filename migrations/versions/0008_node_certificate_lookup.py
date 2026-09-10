"""A minimal, RLS-exempt lookup from certificate fingerprint to node.

Revision ID: 0008_node_certificate_lookup
Revises: 0006_control_api
Create Date: 2026-09-10

Authenticating an inbound node is a chicken-and-egg problem against row level
security: the tenant scope has to come *from* the credential, so the lookup
that resolves the credential cannot already be inside a scope. With RLS forced
and no ``inv.tenant_id`` set, a plain SELECT on ``nodes`` correctly returns
nothing, and every heartbeat is rejected.

The answer is not to relax RLS on ``nodes`` or to give the application role
BYPASSRLS — both would open every row to every unscoped query. It is one
SECURITY DEFINER function with the narrowest surface that answers the question:

* it takes an **exact** fingerprint, never a pattern, so it cannot enumerate;
* it returns three fields — node id, tenant id, status — and nothing else, so a
  caller learns who the certificate belongs to and not what that node holds;
* it is the only RLS-exempt path, and it is auditable as a single object.

``search_path`` is pinned inside the function. A SECURITY DEFINER function that
resolves names through the caller's search_path can be made to execute the
caller's objects with the owner's rights, which is the classic way this feature
becomes a privilege escalation.
"""

from __future__ import annotations

from alembic import op

revision = "0008_node_certificate_lookup"
down_revision = "0006_control_api"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.node_by_certificate"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(fingerprint char(64))
        RETURNS TABLE (node_id char(30), tenant_id uuid, status varchar(16))
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        -- Pinned: resolving through the caller's search_path is how a
        -- SECURITY DEFINER function becomes a privilege escalation.
        SET search_path = pg_catalog, public
        AS $$
            SELECT n.node_id, n.tenant_id, n.status
            FROM public.nodes n
            WHERE n.certificate_fingerprint = fingerprint
            LIMIT 1
        $$;
        """
    )
    # Nobody by default; the application role explicitly.
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(char(64)) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(char(64)) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(char(64))")
