CREATE TABLE inv.shard_plans (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL CHECK(length(plan_id) BETWEEN 1 AND 200),
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 shard_count integer NOT NULL CHECK(shard_count BETWEEN 1 AND 16),
 PRIMARY KEY(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects(tenant_id,project_id)
);
CREATE TABLE inv.shard_commands (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL,
 shard_index integer NOT NULL CHECK(shard_index BETWEEN 0 AND 15),
 node_id text NOT NULL, run_id text NOT NULL, command_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,project_id,plan_id,shard_index), UNIQUE(tenant_id,command_id),
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_plans(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,project_id,run_id,node_id,command_id) REFERENCES inv.tool_claims(tenant_id,project_id,run_id,node_id,command_id)
);
DO $body$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['shard_plans','shard_commands'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
 END LOOP;
END; $body$;
CREATE TRIGGER shard_plan_immutable BEFORE UPDATE OR DELETE ON inv.shard_plans FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE TRIGGER shard_command_immutable BEFORE UPDATE OR DELETE ON inv.shard_commands FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
