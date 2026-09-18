CREATE TABLE inv.node_resource_snapshots (
 tenant_id uuid NOT NULL, node_id text NOT NULL, recovery_epoch uuid NOT NULL,
 channel_version bigint NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 snapshot jsonb NOT NULL CHECK(octet_length(snapshot::text)<=8192),
 PRIMARY KEY(tenant_id,node_id),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
ALTER TABLE inv.node_resource_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.node_resource_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.node_resource_snapshots
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
