"""Forward-only, tenant-scoped model commitments referencing the existing catalog."""

from alembic import op

revision = "0039_model_manifest"
down_revision = "0038_approval_review_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.model_manifests (
      tenant_id uuid NOT NULL, project_id text NOT NULL, model_id text NOT NULL,
      version text NOT NULL, manifest jsonb NOT NULL CHECK(jsonb_typeof(manifest)='object'),
      manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
      source_run_id text NOT NULL, recovery_epoch uuid NOT NULL,
      committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,project_id,model_id,version),
      FOREIGN KEY(tenant_id,project_id,source_run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      CHECK(coalesce(manifest->>'modelId'=model_id AND manifest->>'version'=version,false))
    );
    CREATE TABLE inv.model_shard_locations (
      tenant_id uuid NOT NULL, project_id text NOT NULL, model_id text NOT NULL,
      version text NOT NULL, shard_index integer NOT NULL CHECK(shard_index BETWEEN 0 AND 1023),
      location_id char(30) NOT NULL, location_version bigint NOT NULL CHECK(location_version>0),
      PRIMARY KEY(tenant_id,project_id,model_id,version,location_id),
      FOREIGN KEY(tenant_id,project_id,model_id,version) REFERENCES inv.model_manifests,
      FOREIGN KEY(tenant_id,location_id) REFERENCES public.data_locations(tenant_id,location_id)
    );
    DO $$ DECLARE tab text; BEGIN
      FOREACH tab IN ARRAY ARRAY['model_manifests','model_shard_locations'] LOOP
        EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
        EXECUTE format('REVOKE ALL ON inv.%I FROM PUBLIC,inv_app,inv_kernel',tab);
        EXECUTE format('GRANT SELECT,INSERT ON inv.%I TO inv_kernel',tab);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
      END LOOP;
    END $$;
    """)


def downgrade():
    raise RuntimeError("Model commitments and GC references require a reviewed forward fix")
