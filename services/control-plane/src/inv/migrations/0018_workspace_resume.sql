ALTER TABLE inv.workspace_checkouts ADD UNIQUE(tenant_id,project_id,run_id,checkout_id,workspace_id,source_attempt,recovery_epoch);
CREATE TABLE inv.workspace_resumptions (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 resume_id uuid NOT NULL, checkout_id uuid NOT NULL, workspace_id text NOT NULL,
 source_attempt integer NOT NULL, step_id text NOT NULL CHECK(length(step_id) BETWEEN 1 AND 200),
 recovery_epoch uuid NOT NULL, request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 workload jsonb NOT NULL, snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 1 AND 65536),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,resume_id), UNIQUE(tenant_id,run_id,source_attempt,recovery_epoch),
 FOREIGN KEY(tenant_id,project_id,run_id,checkout_id,workspace_id,source_attempt,recovery_epoch)
 REFERENCES inv.workspace_checkouts(tenant_id,project_id,run_id,checkout_id,workspace_id,source_attempt,recovery_epoch),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 CHECK(workload->>'workspaceId'=workspace_id AND workload->'workspaceResume'->>'resumeId'=resume_id::text)
);
ALTER TABLE inv.workspace_resumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.workspace_resumptions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.workspace_resumptions
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.workspace_resumptions FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_workspace_resume() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE step text;
BEGIN
 IF OLD.state='recovering' AND NEW.state='awaiting_approval' AND (
  EXISTS(SELECT 1 FROM inv.resource_leases WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id AND released_at IS NULL)
  OR NOT EXISTS(SELECT 1 FROM inv.workspace_resumptions WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id
   AND source_attempt=NEW.attempt AND recovery_epoch=(SELECT epoch FROM inv.control_epoch WHERE singleton))
 ) THEN RAISE EXCEPTION 'Recovery approval requires stopped prior execution and frozen Step' USING ERRCODE='23514'; END IF;
 IF NEW.state='succeeded' THEN
  SELECT step_id INTO step FROM inv.workspace_resumptions WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id
   AND source_attempt=NEW.attempt-1 AND recovery_epoch=(SELECT epoch FROM inv.control_epoch WHERE singleton);
  IF FOUND AND NOT EXISTS(SELECT 1 FROM inv.checkpoint_objects WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id AND attempt=NEW.attempt AND step_id=step)
  THEN RAISE EXCEPTION 'Resumed success requires modified Workspace checkpoint' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER workspace_resume_guard BEFORE UPDATE ON inv.runs FOR EACH ROW EXECUTE FUNCTION inv.guard_workspace_resume();
REVOKE ALL ON FUNCTION inv.guard_workspace_resume() FROM PUBLIC;
CREATE OR REPLACE FUNCTION inv.guard_run() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE allowed boolean;
BEGIN
 IF TG_OP = 'INSERT' THEN
  IF NEW.state <> 'draft' OR NEW.version <> 1 OR NEW.attempt <> 0 THEN
   RAISE EXCEPTION 'runs begin in draft at version 1, attempt 0' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
 END IF;
 IF NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id OR NEW.run_id <> OLD.run_id THEN
  RAISE EXCEPTION 'run identity is immutable' USING ERRCODE = '23514';
 END IF;
 IF NEW.state = OLD.state THEN
  IF NEW.version <> OLD.version OR NEW.attempt <> OLD.attempt THEN
   RAISE EXCEPTION 'state required for version or attempt change' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
 END IF;
 allowed := (OLD.state NOT IN ('succeeded','failed','cancelled') AND NEW.state IN ('failed','cancelled'))
 OR (OLD.state='draft' AND NEW.state='validated')
 OR (OLD.state='validated' AND NEW.state='planned')
 OR (OLD.state='planned' AND NEW.state IN ('awaiting_approval','scheduled'))
 OR (OLD.state='awaiting_approval' AND NEW.state='scheduled')
 OR (OLD.state='scheduled' AND NEW.state='running')
 OR (OLD.state='running' AND NEW.state IN ('verifying','recovering'))
 OR (OLD.state='verifying' AND NEW.state IN ('succeeded','recovering'))
 OR (OLD.state='recovering' AND NEW.state IN ('scheduled','awaiting_approval'));
 IF NOT allowed OR NEW.version <> OLD.version + 1
 OR NEW.attempt <> OLD.attempt + (CASE WHEN NEW.state='running' THEN 1 ELSE 0 END) THEN
  RAISE EXCEPTION 'invalid run transition' USING ERRCODE = '23514';
 END IF;
 IF NEW.state='succeeded' AND NOT EXISTS
 (SELECT 1 FROM inv.evidence e WHERE e.tenant_id=NEW.tenant_id AND e.run_id=NEW.run_id AND e.envelope->>'result'='succeeded') THEN
  RAISE EXCEPTION 'success requires evidence' USING ERRCODE = '23514';
 END IF;
 NEW.updated_at := clock_timestamp();
 RETURN NEW;
END; $body$;
