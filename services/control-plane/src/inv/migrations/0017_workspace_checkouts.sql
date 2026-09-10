ALTER TABLE inv.workspace_restores ADD COLUMN recovery_epoch uuid;
CREATE TABLE inv.workspace_checkouts (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 checkout_id uuid NOT NULL, restore_id uuid NOT NULL, workspace_id text NOT NULL,
 source_attempt integer NOT NULL, step_id text NOT NULL, recovery_epoch uuid NOT NULL,
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 generation text NOT NULL CHECK(generation ~ '^generation-[0-9a-f]{32}$'),
 filesystem_identity jsonb NOT NULL CHECK(jsonb_array_length(filesystem_identity)=4),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,checkout_id), UNIQUE(tenant_id,run_id,source_attempt,recovery_epoch),
 FOREIGN KEY(tenant_id,restore_id) REFERENCES inv.workspace_restores(tenant_id,restore_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id)
);
ALTER TABLE inv.workspace_checkouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.workspace_checkouts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.workspace_checkouts
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.workspace_checkouts FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
