"""Tenant-scoped project status and separate operator-owned business admin grants."""
from alembic import op

revision = "0027_business_api_guards"
down_revision = "0026_business_start_merge"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE inv.business_admin_grants (
            tenant_id uuid NOT NULL, user_id char(30) NOT NULL,
            permission text NOT NULL CHECK(permission IN ('users.manage','resources.manage')),
            enabled boolean NOT NULL DEFAULT true,
            PRIMARY KEY(tenant_id,user_id,permission),
            FOREIGN KEY(tenant_id,user_id) REFERENCES public.users(tenant_id,user_id)
        );
        ALTER TABLE inv.business_admin_grants ENABLE ROW LEVEL SECURITY;
        ALTER TABLE inv.business_admin_grants FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON inv.business_admin_grants
          USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
          WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
        REVOKE ALL ON inv.business_admin_grants FROM PUBLIC, inv_app, inv_kernel;

        CREATE OR REPLACE FUNCTION public.business_admin_allowed(
            p_tenant uuid,p_user text,p_permission text
        ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog AS $fn$
        DECLARE allowed boolean;
        BEGIN
            IF p_tenant IS DISTINCT FROM nullif(current_setting('inv.tenant_id',true),'')::uuid
            THEN RETURN false; END IF;
            SELECT true INTO allowed FROM inv.business_admin_grants g
            JOIN public.users u ON u.tenant_id=g.tenant_id AND u.user_id=g.user_id
            WHERE g.tenant_id=p_tenant AND g.user_id=p_user AND g.permission=p_permission
              AND g.enabled AND u.status='active' FOR SHARE OF g;
            RETURN coalesce(allowed,false);
        END $fn$;
        REVOKE ALL ON FUNCTION public.business_admin_allowed(uuid,text,text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.business_admin_allowed(uuid,text,text) TO inv_app;

        CREATE OR REPLACE FUNCTION public.project_kernel_link(p_tenant_id uuid,p_project_id text)
        RETURNS TABLE(linked boolean,enabled boolean) LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog AS $fn$
          SELECT EXISTS(SELECT 1 FROM inv.business_projects b
            WHERE b.tenant_id=p_tenant_id AND b.project_id=p_project_id
              AND p_tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid),
          EXISTS(SELECT 1 FROM inv.business_projects b
            WHERE b.tenant_id=p_tenant_id AND b.project_id=p_project_id AND b.enabled
              AND p_tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
        $fn$;
        REVOKE ALL ON FUNCTION public.project_kernel_link(uuid,text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION public.project_kernel_link(uuid,text) TO inv_app;
    """)


def downgrade():
    raise RuntimeError("Forward only: restore a verified backup; do not restore unscoped authorization")
