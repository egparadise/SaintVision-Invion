-- Preparation has no lease or start authority. Only committed generations count.
CREATE TABLE inv.shard_recovery_requests (
 tenant_id uuid NOT NULL, project_id text NOT NULL,
 plan_id text NOT NULL CHECK(length(plan_id) BETWEEN 1 AND 200),
 source_plan_id text NOT NULL, requester_id text NOT NULL, recovery_epoch uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,project_id,plan_id),
 FOREIGN KEY(tenant_id,project_id,source_plan_id) REFERENCES inv.shard_plans,
 FOREIGN KEY(tenant_id,project_id,requester_id) REFERENCES inv.project_grants,
 CHECK(plan_id<>source_plan_id)
);
CREATE TABLE inv.shard_recovery_members (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL,
 shard_index integer NOT NULL CHECK(shard_index BETWEEN 0 AND 15),
 run_id text NOT NULL, approval_id text NOT NULL, node_id text NOT NULL,
 workload jsonb NOT NULL CHECK(jsonb_typeof(workload)='object' AND octet_length(workload::text)<=2097152),
 PRIMARY KEY(tenant_id,project_id,plan_id,shard_index), UNIQUE(tenant_id,run_id),
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_recovery_requests,
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests,
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes
);
CREATE TABLE inv.shard_recoveries (
 tenant_id uuid NOT NULL, project_id text NOT NULL, plan_id text NOT NULL,
 source_plan_id text NOT NULL, root_plan_id text NOT NULL,
 generation integer NOT NULL CHECK(generation BETWEEN 2 AND 3), recovery_epoch uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,project_id,plan_id), UNIQUE(tenant_id,project_id,source_plan_id),
 UNIQUE(tenant_id,project_id,root_plan_id,generation),
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_plans,
 FOREIGN KEY(tenant_id,project_id,plan_id) REFERENCES inv.shard_recovery_requests,
 FOREIGN KEY(tenant_id,project_id,source_plan_id) REFERENCES inv.shard_plans,
 FOREIGN KEY(tenant_id,project_id,root_plan_id) REFERENCES inv.shard_plans,
 CHECK(plan_id<>source_plan_id AND plan_id<>root_plan_id)
);
DO $body$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['shard_recovery_requests','shard_recovery_members','shard_recoveries'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
  EXECUTE format('GRANT SELECT,INSERT ON inv.%I TO inv_kernel',tab);
 END LOOP;
END; $body$;
CREATE FUNCTION inv.guard_shard_recovery() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE previous inv.shard_recoveries; source_count integer;
BEGIN
 SELECT * INTO previous FROM inv.shard_recoveries
  WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND plan_id=NEW.source_plan_id;
 IF (NEW.root_plan_id,NEW.generation) IS DISTINCT FROM
  (coalesce(previous.root_plan_id,NEW.source_plan_id),coalesce(previous.generation,1)+1)
  OR NEW.recovery_epoch IS DISTINCT FROM (SELECT epoch FROM inv.control_epoch WHERE singleton)
  OR NOT EXISTS(SELECT 1 FROM inv.shard_recovery_requests q WHERE
   (q.tenant_id,q.project_id,q.plan_id,q.source_plan_id,q.recovery_epoch)=
   (NEW.tenant_id,NEW.project_id,NEW.plan_id,NEW.source_plan_id,NEW.recovery_epoch)) THEN
  RAISE EXCEPTION 'recovery lineage or epoch differs' USING ERRCODE='23514';
 END IF;
 SELECT shard_count INTO source_count FROM inv.shard_plans
  WHERE (tenant_id,project_id,plan_id)=(NEW.tenant_id,NEW.project_id,NEW.source_plan_id);
 IF NOT EXISTS(SELECT 1 FROM inv.shard_parents p JOIN inv.runs r USING(tenant_id,run_id)
  WHERE (p.tenant_id,p.project_id,p.plan_id)=(NEW.tenant_id,NEW.project_id,NEW.source_plan_id)
  AND p.recovery_epoch=NEW.recovery_epoch AND r.state IN ('failed','cancelled'))
  OR EXISTS(SELECT 1 FROM inv.shard_commands s JOIN inv.runs r USING(tenant_id,run_id)
   LEFT JOIN inv.node_stop_receipts n USING(tenant_id,command_id)
   WHERE (s.tenant_id,s.project_id,s.plan_id)=(NEW.tenant_id,NEW.project_id,NEW.source_plan_id)
   AND (r.state NOT IN ('succeeded','failed','cancelled') OR n.command_id IS NULL
    OR n.envelope->>'recoveryEpoch'<>NEW.recovery_epoch::text
    OR EXISTS(SELECT 1 FROM inv.resource_leases l WHERE
     (l.tenant_id,l.run_id)=(s.tenant_id,s.run_id) AND l.released_at IS NULL)))
  OR source_count<>(SELECT count(*) FROM inv.shard_commands s
   JOIN inv.shard_recovery_members m USING(tenant_id,project_id,plan_id,shard_index,run_id,node_id)
   JOIN inv.shard_commands old ON (old.tenant_id,old.project_id,old.plan_id,old.shard_index)=
    (s.tenant_id,s.project_id,NEW.source_plan_id,s.shard_index)
   JOIN inv.tool_claims a ON (a.tenant_id,a.command_id)=(s.tenant_id,s.command_id)
   JOIN inv.tool_claims b ON (b.tenant_id,b.command_id)=(old.tenant_id,old.command_id)
   WHERE (s.tenant_id,s.project_id,s.plan_id)=(NEW.tenant_id,NEW.project_id,NEW.plan_id)
    AND a.action_digest=b.action_digest AND a.recovery_epoch=NEW.recovery_epoch
    AND b.recovery_epoch=NEW.recovery_epoch)
  THEN RAISE EXCEPTION 'stopped source and matching fresh members required' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER recovery_guard BEFORE INSERT ON inv.shard_recoveries
 FOR EACH ROW EXECUTE FUNCTION inv.guard_shard_recovery();
REVOKE ALL ON FUNCTION inv.guard_shard_recovery() FROM PUBLIC;
