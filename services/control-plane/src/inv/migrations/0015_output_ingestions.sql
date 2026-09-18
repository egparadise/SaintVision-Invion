CREATE TABLE inv.output_ingestions (
 tenant_id uuid NOT NULL, command_id uuid NOT NULL,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
 next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 token uuid, finished boolean NOT NULL DEFAULT false, last_error text,
 PRIMARY KEY(tenant_id,command_id),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.node_stop_receipts(tenant_id,command_id)
);
ALTER TABLE inv.output_ingestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.output_ingestions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.output_ingestions
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
