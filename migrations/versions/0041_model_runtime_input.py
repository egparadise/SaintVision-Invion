"""Immutable bounded runtime bytes, bound to the existing model Run reservation."""

from alembic import op

revision = "0041_model_runtime_input"
down_revision = "0040_model_run_input"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.model_runtime_inputs (
      tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
      input_id uuid NOT NULL, recovery_epoch uuid NOT NULL,
      requester_id text NOT NULL, workload jsonb NOT NULL,
      locations jsonb NOT NULL CHECK(jsonb_typeof(locations)='array' AND octet_length(locations::text)<=1048576),
      snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 1 AND 65536),
      PRIMARY KEY(tenant_id,run_id), UNIQUE(tenant_id,input_id),
      FOREIGN KEY(tenant_id,run_id) REFERENCES inv.model_run_inputs(tenant_id,run_id),
      FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id)
    );
    ALTER TABLE inv.model_runtime_inputs ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.model_runtime_inputs FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.model_runtime_inputs
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.model_runtime_inputs FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT,INSERT ON inv.model_runtime_inputs TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.model_runtime_inputs
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Model runtime commitments require a reviewed forward fix")
