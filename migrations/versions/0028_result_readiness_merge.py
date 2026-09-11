"""Preserve both published histories and scope read-only readiness to this tenant."""

from alembic import op

revision = "0028_result_readiness_merge"
down_revision = ("0027_business_api_guards", "0026_subject_kernel_link")
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.subject_kernel_link(p_tenant_id uuid, p_user_id char(30))
    RETURNS TABLE (registered boolean) LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog AS $fn$
      SELECT coalesce(p_tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid,false)
        AND EXISTS(SELECT 1 FROM inv.business_subjects s
          JOIN public.users u ON (u.tenant_id,u.user_id)=(s.tenant_id,s.user_id)
          WHERE s.tenant_id=p_tenant_id AND s.user_id=p_user_id AND s.enabled
            AND u.status='active' AND u.external_subject=s.subject_id)
    $fn$;
    REVOKE ALL ON FUNCTION public.subject_kernel_link(uuid,char(30)) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.subject_kernel_link(uuid,char(30)) TO inv_app;
    CREATE FUNCTION public.business_execution_permission(p_tenant_id uuid, p_project_id text, p_user_id char(30))
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = pg_catalog AS $fn$
      SELECT coalesce(p_tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid,false)
        AND EXISTS(SELECT 1 FROM inv.business_subjects s
          JOIN public.users u ON (u.tenant_id,u.user_id)=(s.tenant_id,s.user_id)
          JOIN inv.project_grants g ON (g.tenant_id,g.subject_id)=(s.tenant_id,s.subject_id)
          JOIN inv.business_projects b ON (b.tenant_id,b.project_id)=(g.tenant_id,g.project_id)
          JOIN public.projects p ON (p.tenant_id,p.project_id)=(b.tenant_id,b.project_id)
          JOIN public.project_members m ON (m.tenant_id,m.project_id,m.user_id)=(p.tenant_id,p.project_id,s.user_id)
          WHERE s.tenant_id=p_tenant_id AND s.user_id=p_user_id AND g.project_id=p_project_id
            AND s.enabled AND g.enabled AND g.can_request AND b.enabled
            AND u.status='active' AND u.external_subject=s.subject_id AND p.status='active'
            AND m.role_code IN ('owner','maintainer','operator'))
    $fn$;
    REVOKE ALL ON FUNCTION public.business_execution_permission(uuid,text,char(30)) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.business_execution_permission(uuid,text,char(30)) TO inv_app;
    """)


def downgrade():
    raise RuntimeError(
        "Readiness guards and published histories are forward-only; restore a verified backup"
    )
