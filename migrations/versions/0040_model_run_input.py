"""Bind existing Run reservations to immutable model inputs, without a second runtime."""

from alembic import op

revision = "0040_model_run_input"
down_revision = "0039_model_manifest"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.model_run_inputs (
      tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
      model_id text NOT NULL, model_version text NOT NULL,
      manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
      node_id text NOT NULL, input jsonb NOT NULL CHECK(jsonb_typeof(input)='object'),
      PRIMARY KEY(tenant_id,run_id),
      FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      FOREIGN KEY(tenant_id,project_id,model_id,model_version) REFERENCES inv.model_manifests,
      FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
    );
    ALTER TABLE inv.model_run_inputs ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.model_run_inputs FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.model_run_inputs
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.model_run_inputs FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT,INSERT ON inv.model_run_inputs TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.model_run_inputs
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Model input commitments require a reviewed forward fix")
