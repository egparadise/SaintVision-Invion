CREATE TABLE inv.node_stop_receipts (
 tenant_id uuid NOT NULL, command_id uuid NOT NULL, claim_id uuid NOT NULL, receipt_id uuid NOT NULL,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'), envelope jsonb NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id), UNIQUE(tenant_id,receipt_id),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.tool_claims(tenant_id,command_id),
 FOREIGN KEY(tenant_id,claim_id) REFERENCES inv.tool_claims(tenant_id,claim_id)
);
ALTER TABLE inv.node_stop_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.node_stop_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.node_stop_receipts
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.node_stop_receipts
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
