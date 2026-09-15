"""Immutable action and policy snapshots for approval review."""
from alembic import op
revision = "0038_approval_review_snapshot"
down_revision = "0037_storage_sample_commit"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    CREATE TABLE inv.approval_review_snapshots (
      tenant_id uuid NOT NULL, approval_id text NOT NULL,
      workload jsonb NOT NULL CHECK(jsonb_typeof(workload)='object'),
      policy jsonb NOT NULL CHECK(jsonb_typeof(policy)='object'),
      policy_sha256 text NOT NULL CHECK(policy_sha256 ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(tenant_id,approval_id),
      FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests(tenant_id,approval_id)
    );
    ALTER TABLE inv.approval_review_snapshots ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.approval_review_snapshots FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.approval_review_snapshots
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.approval_review_snapshots FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT,INSERT ON inv.approval_review_snapshots TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.approval_review_snapshots
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)

def downgrade():
    raise RuntimeError("Approval review history requires a reviewed forward fix")
