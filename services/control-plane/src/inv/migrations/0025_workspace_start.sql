-- First execution has attempt 0 before admission; it has no historical checkout.
CREATE TABLE inv.workspace_starts (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 start_id uuid NOT NULL, workspace_id text NOT NULL, step_id text NOT NULL CHECK(length(step_id) BETWEEN 1 AND 200),
 requester_id text NOT NULL, recovery_epoch uuid NOT NULL,
 workload jsonb NOT NULL, snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 1 AND 65536),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,start_id), UNIQUE(tenant_id,run_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 CHECK(workload->>'workspaceId'=workspace_id AND workload->'workspaceStart'->>'startId'=start_id::text)
);
ALTER TABLE inv.workspace_starts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.workspace_starts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.workspace_starts
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.workspace_starts FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
GRANT SELECT,INSERT ON inv.workspace_starts TO inv_kernel;

CREATE FUNCTION inv.guard_workspace_start() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE first_step text;
BEGIN
 IF TG_TABLE_NAME='workspace_starts' THEN
  IF NOT EXISTS(SELECT 1 FROM inv.runs WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id
   AND run_id=NEW.run_id AND state='draft' AND attempt=0 AND version=1)
   OR NEW.recovery_epoch<>(SELECT epoch FROM inv.control_epoch WHERE singleton)
  THEN RAISE EXCEPTION 'First Workspace input requires a new draft Run in current epoch' USING ERRCODE='23514'; END IF;
 ELSIF NEW.state='succeeded' AND NEW.attempt=1 THEN
  SELECT step_id INTO first_step FROM inv.workspace_starts WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id;
  IF FOUND AND NOT EXISTS(SELECT 1 FROM inv.checkpoint_objects WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id AND attempt=1 AND step_id=first_step)
  THEN RAISE EXCEPTION 'First execution success requires actual Workspace checkpoint' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER first_input_guard BEFORE INSERT ON inv.workspace_starts FOR EACH ROW EXECUTE FUNCTION inv.guard_workspace_start();
CREATE TRIGGER first_completion_guard BEFORE UPDATE ON inv.runs FOR EACH ROW EXECUTE FUNCTION inv.guard_workspace_start();
REVOKE ALL ON FUNCTION inv.guard_workspace_start() FROM PUBLIC;
