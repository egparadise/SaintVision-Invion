"""Separate durable pre-dispatch terminal intent from confirmed frame audit."""

from alembic import op

revision = "0034_terminal_frame_intents"
down_revision = "0033_workspace_bridge_merge"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.terminal_frame_intents (
      tenant_id uuid NOT NULL, command_id uuid NOT NULL,
      sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 4096),
      frame_digest text NOT NULL CHECK(frame_digest ~ '^[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,command_id,sequence),
      FOREIGN KEY(tenant_id,command_id) REFERENCES inv.tool_claims(tenant_id,command_id)
    );
    ALTER TABLE inv.terminal_frame_intents ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.terminal_frame_intents FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.terminal_frame_intents
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.terminal_frame_intents FROM PUBLIC,inv_app;
    GRANT SELECT,INSERT ON inv.terminal_frame_intents TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.terminal_frame_intents
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Terminal intent history requires verified restore or forward fix")
