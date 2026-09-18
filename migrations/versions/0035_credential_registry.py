"""Private credential version metadata and explicit per-Run grants."""

from alembic import op

revision = "0035_credential_registry"
down_revision = "0034_terminal_frame_intents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.credential_versions (
      tenant_id uuid NOT NULL, project_id text NOT NULL,
      credential_id uuid NOT NULL, version_id uuid NOT NULL,
      purpose text NOT NULL CHECK(purpose IN ('llm.invoke','git.read','git.publish','storage.read','storage.write','storage.gc','backup.write','backup.restore')),
      destination text NOT NULL CHECK(destination ~ '^[a-z][a-z0-9-]{0,63}$'),
      file_name text NOT NULL CHECK(file_name ~ '^[0-9a-f]{32}[.]secret$'),
      device bigint NOT NULL CHECK(device>=0), inode bigint NOT NULL CHECK(inode>0),
      content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(tenant_id,credential_id,version_id),
      UNIQUE(tenant_id,project_id,credential_id,version_id),
      FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects
    );
    CREATE TABLE inv.credential_grants (
      tenant_id uuid NOT NULL, project_id text NOT NULL,
      credential_id uuid NOT NULL, version_id uuid NOT NULL,
      subject_id text NOT NULL, run_id text NOT NULL,
      enabled boolean NOT NULL DEFAULT false, expires_at timestamptz NOT NULL,
      revoked_at timestamptz, recovery_epoch uuid NOT NULL,
      PRIMARY KEY(tenant_id,credential_id,version_id,subject_id,run_id),
      FOREIGN KEY(tenant_id,project_id,credential_id,version_id) REFERENCES inv.credential_versions(tenant_id,project_id,credential_id,version_id),
      FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      FOREIGN KEY(tenant_id,project_id,subject_id) REFERENCES inv.project_grants
    );
    ALTER TABLE inv.credential_versions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.credential_versions FORCE ROW LEVEL SECURITY;
    ALTER TABLE inv.credential_grants ENABLE ROW LEVEL SECURITY;
    ALTER TABLE inv.credential_grants FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON inv.credential_versions
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    CREATE POLICY tenant_isolation ON inv.credential_grants
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    REVOKE ALL ON inv.credential_versions,inv.credential_grants FROM PUBLIC,inv_app,inv_kernel;
    GRANT SELECT ON inv.credential_versions,inv.credential_grants TO inv_kernel;
    CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.credential_versions
      FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Credential version history requires verified restore or forward fix")
