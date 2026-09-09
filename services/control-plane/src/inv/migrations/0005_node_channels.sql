-- Provisioning is a separate operator role, never a browser/Node payload.
CREATE TABLE inv.node_channels (
 tenant_id uuid NOT NULL, node_id text NOT NULL, recovery_epoch uuid NOT NULL,
 version bigint NOT NULL CHECK(version BETWEEN 1 AND 9007199254740991),
 endpoint text NOT NULL CHECK(length(endpoint) BETWEEN 9 AND 2048),
 certificate_sha256 text NOT NULL CHECK(certificate_sha256 ~ '^[0-9a-f]{64}$'),
 certificate_not_after timestamptz NOT NULL, enabled boolean NOT NULL,
 lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,node_id),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
CREATE TABLE inv.node_channel_audit (
 tenant_id uuid NOT NULL, node_id text NOT NULL, version bigint NOT NULL,
 action text NOT NULL CHECK(action IN ('provision','revoke')),
 certificate_sha256 text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,node_id,version),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
ALTER TABLE inv.node_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.node_channels FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.node_channels
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
ALTER TABLE inv.node_channel_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.node_channel_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.node_channel_audit
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.node_channel_audit
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.channel_monotonic() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='DELETE' OR NEW.tenant_id<>OLD.tenant_id OR NEW.node_id<>OLD.node_id
   OR NEW.version<>OLD.version+1 THEN
  RAISE EXCEPTION 'node channel requires forward CAS update' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER channel_monotonic BEFORE UPDATE OR DELETE ON inv.node_channels
 FOR EACH ROW EXECUTE FUNCTION inv.channel_monotonic();

ALTER TABLE inv.node_stop_receipts ADD COLUMN channel_version bigint;
ALTER TABLE inv.node_stop_receipts ADD COLUMN peer_sha256 text;
ALTER TABLE inv.node_stop_receipts ADD CONSTRAINT receipt_channel_proof CHECK
 ((channel_version IS NULL AND peer_sha256 IS NULL) OR
 (channel_version IS NOT NULL AND channel_version>0 AND peer_sha256 IS NOT NULL AND peer_sha256 ~ '^[0-9a-f]{64}$'));
