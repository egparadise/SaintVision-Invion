-- A committed claim is never automatically reclaimed, even after a lost response.
CREATE TABLE inv.tool_claims (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 command_id uuid NOT NULL, claim_id uuid NOT NULL, node_id text NOT NULL,
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 action_digest text NOT NULL CHECK(action_digest ~ '^[0-9a-f]{64}$'),
 plan_digest text NOT NULL CHECK(plan_digest ~ '^[0-9a-f]{64}$'),
 policy_version text NOT NULL, profile_version text NOT NULL,
 policy_decision_id text NOT NULL, recovery_epoch uuid NOT NULL,
 not_after timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id), UNIQUE(tenant_id,claim_id),
 CHECK(not_after > created_at),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.approval_dispatches(tenant_id,command_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
ALTER TABLE inv.tool_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.tool_claims FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.tool_claims
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.tool_claims
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
