CREATE TABLE inv.shard_parents (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL, run_id text NOT NULL,
 recovery_epoch uuid NOT NULL,
 PRIMARY KEY(tenant_id,project_id,plan_id), UNIQUE(tenant_id,run_id),
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_plans(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id)
);
CREATE TABLE inv.shard_completions (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL,
 run_id text NOT NULL, evidence_id text NOT NULL, manifest jsonb NOT NULL,
 manifest_hash text NOT NULL CHECK(manifest_hash ~ '^[0-9a-f]{64}$'),
 policy_decision_id uuid NOT NULL, policy_version text NOT NULL CHECK(policy_version='shard-completion:v1'),
 completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_parents(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,run_id,evidence_id) REFERENCES inv.evidence(tenant_id,run_id,evidence_id)
);
DO $body$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['shard_parents','shard_completions'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
 END LOOP;
END; $body$;
CREATE FUNCTION inv.guard_shard_parent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='runs' THEN
  IF NEW.state='succeeded' AND EXISTS(SELECT 1 FROM inv.shard_parents WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id)
  AND NOT EXISTS(SELECT 1 FROM inv.shard_completions WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id) THEN
   RAISE EXCEPTION 'Shard parent requires aggregate Evidence' USING ERRCODE='23514';
  END IF;
 ELSE
  IF EXISTS(SELECT 1 FROM inv.shard_parents WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id) THEN
   RAISE EXCEPTION 'Shard parent is an aggregator, not an execution target' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER shard_parent_success BEFORE UPDATE ON inv.runs FOR EACH ROW EXECUTE FUNCTION inv.guard_shard_parent();
CREATE TRIGGER no_parent_execution BEFORE INSERT ON inv.tool_claims FOR EACH ROW EXECUTE FUNCTION inv.guard_shard_parent();
CREATE TRIGGER no_parent_reservations BEFORE INSERT ON inv.resource_leases FOR EACH ROW EXECUTE FUNCTION inv.guard_shard_parent();
