"""Whether a person is registered with the kernel, answered inside their tenant.

Revision ID: 0028_subject_kernel_link
Revises: 0027_business_api_guards
Create Date: 2026-09-11

The companion to ``public.project_kernel_link``. A person can sign in, belong to
a project and still be unable to approve anything, because approval identity
lives in ``inv.business_subjects`` — operator-registered, immutable and
one-to-one, so a two-person rule cannot be satisfied by one person holding two
identities. Without this the person meets a refusal indistinguishable from
"your role does not permit this", which a project owner would then go and
change, fixing nothing.

**This revision exists in the shape it does because of a defect in 0024.** That
function took ``p_tenant_id`` from the caller and trusted it. A SECURITY DEFINER
function runs as its owner and therefore *bypasses row level security*, so a
caller could pass any tenant's id and learn whether a project in another tenant
was linked. Revision 0027 closed it by binding the answer to
``current_setting('inv.tenant_id')`` — the scope the session is actually in,
which the caller cannot forge because ``SET LOCAL`` is set from the verified
credential.

The same mistake was in the first draft of this function. It is written here the
corrected way from the start:

* the answer is false unless the requested tenant **is** the session's tenant,
  so a definer function cannot be used to read across tenants;
* ``search_path`` is ``pg_catalog`` only and every name is fully qualified,
  because resolving through the caller's path is how a definer function becomes
  a privilege escalation;
* it returns one boolean about one user the caller already names, so it cannot
  be used to enumerate who may approve.
"""

from __future__ import annotations

from alembic import op

revision = "0028_subject_kernel_link"
down_revision = "0027_business_api_guards"
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
        SET search_path = pg_catalog
        AS $fn$
            SELECT EXISTS (
                SELECT 1 FROM inv.business_subjects s
                WHERE s.tenant_id = p_tenant_id
                  AND s.user_id = p_user_id
                  AND s.enabled
                  -- The caller supplies p_tenant_id and a definer function
                  -- bypasses RLS, so the answer is bound to the scope the
                  -- session is actually in rather than the one it asked about.
                  AND p_tenant_id = nullif(
                      pg_catalog.current_setting('inv.tenant_id', true), ''
                  )::uuid
            )
        $fn$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, char(30)) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, char(30)) TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, char(30))")
