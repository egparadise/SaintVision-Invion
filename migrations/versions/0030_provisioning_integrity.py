"""Merge both published results histories; preserve account integrity and audit.

Forward only: restore a verified backup or apply a reviewed forward fix.
"""

from alembic import op

revision = "0030_provisioning_integrity"
down_revision = ("0028_result_readiness_merge", "0029_run_outputs")
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
    -- Downloads use the canonical kernel HTTP boundary and its current grant,
    -- receipt and immutable Evidence checks. Retain the published revision,
    -- while retiring its less restrictive alternate resolver.
    REVOKE ALL ON FUNCTION public.run_committed_outputs(uuid,text) FROM PUBLIC,inv_app;
    CREATE TABLE inv.account_provisioning_events (
      tenant_id uuid NOT NULL, event_id uuid NOT NULL, project_id text NOT NULL,
      user_id char(30) NOT NULL, subject_id text NOT NULL,
      grant_scope text NOT NULL CHECK(grant_scope IN ('request','approve','request-and-approve')),
      recovery_epoch uuid NOT NULL, operator_name text NOT NULL,
      reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 300),
      created_links jsonb NOT NULL CHECK(jsonb_typeof(created_links)='array'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,event_id),
      FOREIGN KEY(tenant_id,project_id) REFERENCES inv.business_projects,
      FOREIGN KEY(tenant_id,user_id) REFERENCES public.users(tenant_id,user_id)
    );
    ALTER TABLE inv.account_provisioning_events ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.account_provisioning_events FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.account_provisioning_events
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.account_provisioning_events
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    REVOKE ALL ON inv.account_provisioning_events FROM PUBLIC,inv_app,inv_kernel;
    """)


def downgrade():
    raise RuntimeError(
        "Provisioning audit and merged guards are forward-only; restore a verified backup"
    )
