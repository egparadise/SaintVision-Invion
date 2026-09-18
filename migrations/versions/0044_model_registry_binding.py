"""Explicit immutable registry/manifest identities; never an execution permit."""
from alembic import op

revision = '0044_model_registry_binding'
down_revision = '0043_replica_retention'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION public.model_registry_snapshot(p_tenant uuid,p_project text,p_version text)
    RETURNS TABLE(registry_model_id text,registry_version text,content_hash text,
      byte_size bigint,stage text,verified_at timestamptz,pinned_until timestamptz)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
    BEGIN
      IF p_tenant IS DISTINCT FROM nullif(current_setting('inv.tenant_id',true),'')::uuid
      THEN RETURN; END IF;
      RETURN QUERY SELECT m.model_id::text,v.version::text,v.content_sha256::text,
        v.byte_size,v.stage::text,v.verified_at,v.retention_pinned_until
      FROM public.models m JOIN public.model_versions v
        ON v.tenant_id=m.tenant_id AND v.model_id=m.model_id
      WHERE m.tenant_id=p_tenant AND m.project_id=p_project
        AND v.model_version_id=p_version
      FOR SHARE OF m,v;
    END $fn$;
    REVOKE ALL ON FUNCTION public.model_registry_snapshot(uuid,text,text) FROM PUBLIC,inv_app;
    GRANT EXECUTE ON FUNCTION public.model_registry_snapshot(uuid,text,text) TO inv_kernel;

    CREATE TABLE inv.model_registry_bindings (
      tenant_id uuid NOT NULL,project_id text NOT NULL,registry_version_id char(30) NOT NULL,
      model_id text NOT NULL,model_version text NOT NULL,
      manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
      binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,project_id,registry_version_id),
      FOREIGN KEY(tenant_id,registry_version_id)
        REFERENCES public.model_versions(tenant_id,model_version_id),
      FOREIGN KEY(tenant_id,project_id,model_id,model_version)
        REFERENCES inv.model_manifests(tenant_id,project_id,model_id,version)
    );
    ALTER TABLE inv.model_registry_bindings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.model_registry_bindings FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.model_registry_bindings
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.model_registry_bindings FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT,INSERT ON inv.model_registry_bindings TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.model_registry_bindings
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError('Model registry bindings require a reviewed forward fix')
