-- Durable tenant admission barrier; neither liveness nor a control response proves stop.
CREATE TABLE inv.tenant_controls (
 tenant_id uuid PRIMARY KEY REFERENCES inv.tenants,
 kill_switch boolean NOT NULL DEFAULT false,
 version bigint NOT NULL DEFAULT 0 CHECK(version BETWEEN 0 AND 9007199254740991),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE inv.node_controls (
 tenant_id uuid NOT NULL, node_id text NOT NULL,
 version bigint NOT NULL DEFAULT 0 CHECK(version BETWEEN 0 AND 9007199254740991),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,node_id), FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes
);
CREATE TABLE inv.operator_grants (
 tenant_id uuid NOT NULL REFERENCES inv.tenants, subject_id text NOT NULL,
 enabled boolean NOT NULL DEFAULT true,
 can_contain boolean NOT NULL DEFAULT false, can_resume boolean NOT NULL DEFAULT false,
 lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,subject_id)
);
CREATE TABLE inv.containment_requests (
 tenant_id uuid NOT NULL REFERENCES inv.tenants, operation text NOT NULL
 CHECK(operation IN ('kill','clear','drain','resume')),
 key text NOT NULL CHECK(length(key) BETWEEN 1 AND 200),
 request_id uuid NOT NULL, subject_id text NOT NULL,
 node_id text, reason_code text NOT NULL CHECK(reason_code IN ('maintenance','incident','operator_request')),
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 response jsonb, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,operation,key), UNIQUE(tenant_id,request_id),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes,
 CHECK((operation IN ('kill','clear'))=(node_id IS NULL)),
 CHECK(response IS NULL OR octet_length(response::text)<=16384)
);
INSERT INTO inv.tenant_controls(tenant_id) SELECT tenant_id FROM inv.tenants;
INSERT INTO inv.node_controls(tenant_id,node_id) SELECT tenant_id,node_id FROM inv.nodes;
CREATE FUNCTION inv.seed_containment_control() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='tenants' THEN
  INSERT INTO inv.tenant_controls(tenant_id) VALUES(NEW.tenant_id);
 ELSE
  INSERT INTO inv.node_controls(tenant_id,node_id) VALUES(NEW.tenant_id,NEW.node_id);
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER containment_seed AFTER INSERT ON inv.tenants FOR EACH ROW EXECUTE FUNCTION inv.seed_containment_control();
CREATE TRIGGER containment_seed AFTER INSERT ON inv.nodes FOR EACH ROW EXECUTE FUNCTION inv.seed_containment_control();
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['tenant_controls','node_controls','operator_grants','containment_requests'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT ON inv.%I TO inv_kernel',tab);
 END LOOP;
END $$;
GRANT INSERT(tenant_id) ON inv.tenant_controls TO inv_kernel;
GRANT INSERT(tenant_id,node_id) ON inv.node_controls TO inv_kernel;
GRANT UPDATE(kill_switch,version,updated_at) ON inv.tenant_controls TO inv_kernel;
GRANT UPDATE(version,updated_at) ON inv.node_controls TO inv_kernel;
GRANT UPDATE(lock_sentinel) ON inv.operator_grants TO inv_kernel;
GRANT INSERT,UPDATE(response) ON inv.containment_requests TO inv_kernel;
CREATE FUNCTION inv.guard_containment_request() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR OLD.response IS NOT NULL OR NEW.response IS NULL
  OR (to_jsonb(NEW)-'response') IS DISTINCT FROM (to_jsonb(OLD)-'response') THEN
  RAISE EXCEPTION 'Containment request history is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.containment_requests
 FOR EACH ROW EXECUTE FUNCTION inv.guard_containment_request();
REVOKE ALL ON FUNCTION inv.seed_containment_control(),inv.guard_containment_request() FROM PUBLIC;
