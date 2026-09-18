"""Immutable bounded model retry lineage; no reuse of an old command/permit."""

from alembic import op

revision = "0042_model_retry_lineage"
down_revision = "0041_model_runtime_input"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.model_retry_lineage (
      tenant_id uuid NOT NULL, project_id text NOT NULL,
      root_run_id text NOT NULL, parent_run_id text NOT NULL, child_run_id text NOT NULL,
      generation integer NOT NULL CHECK(generation BETWEEN 2 AND 3),
      PRIMARY KEY(tenant_id,parent_run_id), UNIQUE(tenant_id,child_run_id),
      UNIQUE(tenant_id,root_run_id,generation),
      FOREIGN KEY(tenant_id,project_id,root_run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      FOREIGN KEY(tenant_id,project_id,parent_run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      FOREIGN KEY(tenant_id,project_id,child_run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      CHECK(parent_run_id<>child_run_id AND root_run_id<>child_run_id)
    );
    ALTER TABLE inv.model_retry_lineage ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.model_retry_lineage FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.model_retry_lineage
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.model_retry_lineage FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT,INSERT ON inv.model_retry_lineage TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.model_retry_lineage
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Model retry lineage requires a reviewed forward fix")
