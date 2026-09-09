-- A queued permit and its admission claim commit together. Once transmission
-- is reserved, no worker may turn uncertainty into another start permission.
ALTER TABLE inv.tool_claims ADD UNIQUE(tenant_id,project_id,run_id,node_id,command_id);
CREATE TABLE inv.execution_deliveries (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 node_id text NOT NULL, command_id uuid NOT NULL,
 envelope jsonb NOT NULL CHECK(jsonb_typeof(envelope)='object' AND octet_length(envelope::text)<=2097152),
 phase text NOT NULL DEFAULT 'queued' CHECK(phase IN ('queued','uncertain','stopped')),
 operation text CHECK(operation IN ('execute','observe','cancel')),
 worker_token uuid, lease_until timestamptz,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
 next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 last_error_code text CHECK(last_error_code ~ '^[A-Z]+-[0-9]{4}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id),
 FOREIGN KEY(tenant_id,project_id,run_id,node_id,command_id)
  REFERENCES inv.tool_claims(tenant_id,project_id,run_id,node_id,command_id),
 CHECK((worker_token IS NULL)=(lease_until IS NULL))
);
CREATE INDEX execution_delivery_pending ON inv.execution_deliveries(tenant_id,next_attempt_at,created_at) WHERE phase<>'stopped';
ALTER TABLE inv.execution_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.execution_deliveries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.execution_deliveries
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE FUNCTION inv.guard_delivery() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.phase<>'queued' OR NEW.operation IS NOT NULL OR NEW.worker_token IS NOT NULL OR NEW.attempts<>0 THEN
   RAISE EXCEPTION 'delivery must begin queued without a worker' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='DELETE' OR
 (NEW.tenant_id,NEW.project_id,NEW.run_id,NEW.node_id,NEW.command_id,NEW.envelope,NEW.created_at)
 IS DISTINCT FROM
 (OLD.tenant_id,OLD.project_id,OLD.run_id,OLD.node_id,OLD.command_id,OLD.envelope,OLD.created_at)
 OR (OLD.phase<>'queued' AND NEW.phase='queued')
 OR (OLD.phase='stopped' AND NEW IS DISTINCT FROM OLD)
 OR NEW.attempts<OLD.attempts THEN
  RAISE EXCEPTION 'immutable delivery content or backwards progress' USING ERRCODE='23514';
 END IF;
 IF NEW.phase='stopped' AND NOT EXISTS (
  SELECT 1 FROM inv.node_stop_receipts r WHERE r.tenant_id=NEW.tenant_id AND r.command_id=NEW.command_id
 ) THEN
  RAISE EXCEPTION 'physical receipt required before stopped delivery' USING ERRCODE='23514';
 END IF;
 IF NEW.operation='execute' AND NEW.worker_token IS NOT NULL AND NEW.worker_token IS DISTINCT FROM OLD.worker_token AND OLD.phase<>'queued' THEN
  RAISE EXCEPTION 'start permission cannot be reissued' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER delivery_guard BEFORE INSERT OR UPDATE OR DELETE ON inv.execution_deliveries FOR EACH ROW EXECUTE FUNCTION inv.guard_delivery();
REVOKE ALL ON FUNCTION inv.guard_delivery() FROM PUBLIC;
