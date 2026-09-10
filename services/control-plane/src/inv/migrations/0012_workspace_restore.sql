CREATE TABLE inv.workspace_restores (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 restore_id uuid NOT NULL, workspace_id text NOT NULL CHECK(workspace_id ~ '^wsp_[0-9A-HJKMNP-TV-Z]{26}$'),
 source_attempt integer NOT NULL, step_id text NOT NULL,
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 generation text NOT NULL CHECK(generation ~ '^generation-[0-9a-f]{32}$'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 restored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,restore_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,run_id,source_attempt,step_id)
  REFERENCES inv.checkpoint_objects(tenant_id,run_id,attempt,step_id)
);
ALTER TABLE inv.workspace_restores ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.workspace_restores FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.workspace_restores
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.workspace_restores
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
