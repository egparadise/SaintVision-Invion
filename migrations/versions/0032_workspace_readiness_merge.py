"""Keep published history and report only current pending Workspace input."""

from alembic import op

revision = "0032_workspace_readiness_merge"
down_revision = ("0031_resource_offer_integrity", "0031_workspace_input_state")
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.workspace_input_state(p_tenant_id uuid,p_workspace_id text)
    RETURNS TABLE(prepared boolean,kind text,run_id text,step_id text,snapshot_bytes integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $fn$
      WITH candidates AS (
        SELECT 'first'::text AS kind,s.run_id,s.step_id,s.snapshot,s.created_at
        FROM inv.workspace_starts s
        JOIN public.workspaces w ON (w.tenant_id,w.workspace_id,w.project_id)=(s.tenant_id,s.workspace_id,s.project_id)
        JOIN inv.runs r ON (r.tenant_id,r.project_id,r.run_id)=(s.tenant_id,s.project_id,s.run_id)
        JOIN inv.control_epoch e ON e.singleton AND e.epoch=s.recovery_epoch
        WHERE s.tenant_id=p_tenant_id AND s.workspace_id=p_workspace_id
          AND p_tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid
          AND r.attempt=0 AND r.state IN ('draft','validated','planned','awaiting_approval','scheduled')
        UNION ALL
        SELECT 'resume'::text,rp.run_id,rp.step_id,rp.snapshot,rp.created_at
        FROM inv.workspace_resumptions rp
        JOIN public.workspaces w ON (w.tenant_id,w.workspace_id,w.project_id)=(rp.tenant_id,rp.workspace_id,rp.project_id)
        JOIN inv.runs r ON (r.tenant_id,r.project_id,r.run_id)=(rp.tenant_id,rp.project_id,rp.run_id)
        JOIN inv.control_epoch e ON e.singleton AND e.epoch=rp.recovery_epoch
        WHERE rp.tenant_id=p_tenant_id AND rp.workspace_id=p_workspace_id
          AND p_tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid
          AND rp.source_attempt=r.attempt AND r.state IN ('recovering','awaiting_approval','scheduled')
      )
      SELECT true,c.kind,c.run_id,c.step_id,octet_length(c.snapshot)
      FROM candidates c ORDER BY c.created_at DESC,c.run_id DESC,c.kind LIMIT 1
    $fn$;
    REVOKE ALL ON FUNCTION public.workspace_input_state(uuid,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.workspace_input_state(uuid,text) TO inv_app;
    """)


def downgrade():
    raise RuntimeError("Published readiness history is forward-only; restore a verified backup")
