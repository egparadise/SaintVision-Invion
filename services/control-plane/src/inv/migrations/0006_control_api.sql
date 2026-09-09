-- Per-run ordering is serialized on the Run row, not a global sequence that can
-- commit out of order and cause a reconnecting browser to skip late events.
ALTER TABLE inv.runs ADD COLUMN event_sequence bigint NOT NULL DEFAULT 0 CHECK(event_sequence >= 0);
ALTER TABLE inv.outbox ADD COLUMN sequence bigint;
WITH ranked AS (
 SELECT tenant_id,event_id,row_number() OVER(PARTITION BY tenant_id,run_id ORDER BY created_at,event_id) AS n FROM inv.outbox
) UPDATE inv.outbox o SET sequence=r.n FROM ranked r WHERE o.tenant_id=r.tenant_id AND o.event_id=r.event_id;
UPDATE inv.runs r SET event_sequence=(SELECT coalesce(max(sequence),0) FROM inv.outbox o WHERE o.tenant_id=r.tenant_id AND o.run_id=r.run_id);
ALTER TABLE inv.outbox ALTER COLUMN sequence SET NOT NULL;
ALTER TABLE inv.outbox ADD CONSTRAINT outbox_run_sequence UNIQUE(tenant_id,run_id,sequence);
ALTER TABLE inv.outbox ADD CHECK(sequence > 0);
CREATE FUNCTION inv.sequence_event() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 UPDATE inv.runs SET event_sequence=event_sequence+1 WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id RETURNING event_sequence INTO NEW.sequence;
 IF NOT FOUND THEN RAISE EXCEPTION 'event run absent' USING ERRCODE='23503'; END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER outbox_sequence BEFORE INSERT ON inv.outbox FOR EACH ROW EXECUTE FUNCTION inv.sequence_event();
CREATE FUNCTION inv.guard_event() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='DELETE' OR (NEW.tenant_id,NEW.run_id,NEW.event_id,NEW.event_type,NEW.payload,NEW.created_at,NEW.sequence)
 IS DISTINCT FROM (OLD.tenant_id,OLD.run_id,OLD.event_id,OLD.event_type,OLD.payload,OLD.created_at,OLD.sequence) THEN
  RAISE EXCEPTION 'event content is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER outbox_content BEFORE UPDATE OR DELETE ON inv.outbox FOR EACH ROW EXECUTE FUNCTION inv.guard_event();
CREATE TABLE inv.project_nodes (
 tenant_id uuid NOT NULL, project_id text NOT NULL, node_id text NOT NULL,
 enabled boolean NOT NULL DEFAULT true, lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,project_id,node_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects(tenant_id,project_id),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
ALTER TABLE inv.project_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.project_nodes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.project_nodes USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
REVOKE ALL ON FUNCTION inv.sequence_event(),inv.guard_event() FROM PUBLIC;
ALTER TABLE inv.nodes ADD COLUMN probe_started_at timestamptz;
CREATE TABLE inv.node_probes (
 tenant_id uuid NOT NULL, node_id text NOT NULL, nonce text NOT NULL CHECK(nonce ~ '^[0-9a-f]{64}$'),
 issued_at timestamptz NOT NULL DEFAULT clock_timestamp(), consumed_at timestamptz,
 PRIMARY KEY(tenant_id,nonce), FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes(tenant_id,node_id)
);
ALTER TABLE inv.node_probes ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.node_probes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.node_probes USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
