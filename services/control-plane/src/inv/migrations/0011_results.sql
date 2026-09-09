-- The first durable transmission reservation creates exactly one RunAttempt.
-- Uncertain transmission never creates a second attempt or renews authority.
CREATE TABLE inv.execution_attempts (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 node_id text NOT NULL, command_id uuid NOT NULL, attempt integer NOT NULL,
 proofs jsonb NOT NULL CHECK(jsonb_typeof(proofs)='object'),
 PRIMARY KEY(tenant_id,command_id), UNIQUE(tenant_id,run_id,attempt),
 UNIQUE(tenant_id,project_id,run_id,attempt,command_id),
 FOREIGN KEY(tenant_id,project_id,run_id,node_id,command_id)
  REFERENCES inv.tool_claims(tenant_id,project_id,run_id,node_id,command_id),
 FOREIGN KEY(tenant_id,run_id,attempt) REFERENCES inv.run_attempts(tenant_id,run_id,attempt)
);
CREATE TABLE inv.result_commitments (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 attempt integer NOT NULL, command_id uuid NOT NULL, object_id uuid NOT NULL,
 evidence_id text NOT NULL, envelope jsonb NOT NULL,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id), UNIQUE(tenant_id,evidence_id),
 UNIQUE(tenant_id,run_id,attempt,command_id,evidence_id),
 FOREIGN KEY(tenant_id,project_id,run_id,attempt,command_id)
  REFERENCES inv.execution_attempts(tenant_id,project_id,run_id,attempt,command_id),
 FOREIGN KEY(tenant_id,project_id,object_id)
  REFERENCES inv.storage_objects(tenant_id,project_id,object_id),
 CHECK(envelope->>'evidenceId'=evidence_id AND envelope->>'runId'=run_id
  AND (envelope->>'tenantId')::uuid=tenant_id AND envelope->>'result'='succeeded')
);
ALTER TABLE inv.evidence ADD UNIQUE(tenant_id,run_id,evidence_id);
CREATE TABLE inv.result_completions (
 tenant_id uuid NOT NULL, run_id text NOT NULL, attempt integer NOT NULL,
 command_id uuid NOT NULL, evidence_id text NOT NULL,
 completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id), UNIQUE(tenant_id,run_id,attempt),
 FOREIGN KEY(tenant_id,run_id,attempt,command_id,evidence_id)
  REFERENCES inv.result_commitments(tenant_id,run_id,attempt,command_id,evidence_id),
 FOREIGN KEY(tenant_id,run_id,evidence_id) REFERENCES inv.evidence(tenant_id,run_id,evidence_id)
);
DO $body$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['execution_attempts','result_commitments','result_completions'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
 END LOOP;
END; $body$;
CREATE TRIGGER result_object_guard BEFORE INSERT ON inv.result_commitments
 FOR EACH ROW EXECUTE FUNCTION inv.guard_checkpoint_object();
-- Pins are conservative and indefinite until an explicit retention release
-- contract exists. No lifecycle may delete an Evidence or prepared result.
CREATE FUNCTION inv.guard_result_pin() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NEW.state IN ('deleting','deleted') AND EXISTS (
  SELECT 1 FROM inv.result_commitments WHERE tenant_id=NEW.tenant_id
   AND project_id=NEW.project_id AND object_id=NEW.object_id
 ) THEN RAISE EXCEPTION 'result pins object' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER result_pin_guard BEFORE UPDATE ON inv.storage_objects
 FOR EACH ROW EXECUTE FUNCTION inv.guard_result_pin();
CREATE FUNCTION inv.guard_managed_success() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NEW.state='succeeded' AND EXISTS (
  SELECT 1 FROM inv.execution_attempts WHERE tenant_id=NEW.tenant_id
   AND run_id=NEW.run_id AND attempt=NEW.attempt
 ) AND NOT EXISTS (
  SELECT 1 FROM inv.result_completions WHERE tenant_id=NEW.tenant_id
   AND run_id=NEW.run_id AND attempt=NEW.attempt
 ) THEN RAISE EXCEPTION 'managed success requires committed result' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER managed_success_guard BEFORE UPDATE ON inv.runs
 FOR EACH ROW EXECUTE FUNCTION inv.guard_managed_success();
REVOKE ALL ON FUNCTION inv.guard_result_pin(),inv.guard_managed_success() FROM PUBLIC;
