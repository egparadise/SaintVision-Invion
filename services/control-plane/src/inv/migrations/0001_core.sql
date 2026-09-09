-- Core persistence, PostgreSQL 16+. Run as schema owner; use a separate runtime role.
CREATE SCHEMA inv;
-- Operator provisions a fresh epoch outside the DB backup before runtime starts.
CREATE TABLE inv.control_epoch (singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), epoch uuid NOT NULL);
CREATE SEQUENCE inv.fencing_token_seq AS bigint MINVALUE 1 NO CYCLE;
CREATE TABLE inv.tenants (
 tenant_id uuid PRIMARY KEY, name text NOT NULL
);
CREATE TABLE inv.projects (
 tenant_id uuid NOT NULL REFERENCES inv.tenants(tenant_id),
 project_id text NOT NULL CHECK (project_id ~ '^prj_[0-9A-HJKMNP-TV-Z]{26}$'),
 PRIMARY KEY (tenant_id, project_id)
);
CREATE TABLE inv.nodes (
 tenant_id uuid NOT NULL REFERENCES inv.tenants(tenant_id),
 node_id text NOT NULL CHECK (node_id ~ '^nod_[0-9A-HJKMNP-TV-Z]{26}$'),
 status text NOT NULL CHECK (status IN ('online','offline','draining','quarantined')),
 heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 recovery_epoch uuid, clock_skew_seconds numeric CHECK (clock_skew_seconds BETWEEN -86400 AND 86400),
 PRIMARY KEY (tenant_id, node_id)
);
CREATE TABLE inv.resources (
 tenant_id uuid NOT NULL, resource_id text NOT NULL CHECK (resource_id ~ '^res_[0-9A-HJKMNP-TV-Z]{26}$'),
 node_id text NOT NULL, kind text NOT NULL CHECK (kind IN ('cpu','memory','gpu','storage','network')),
 capacity bigint NOT NULL CHECK (capacity >= 0 AND capacity <= 9007199254740991),
 offered bigint NOT NULL CHECK (offered >= 0 AND offered <= capacity),
 PRIMARY KEY (tenant_id, resource_id),
 FOREIGN KEY (tenant_id, node_id) REFERENCES inv.nodes(tenant_id, node_id)
);
CREATE TABLE inv.runs (
 tenant_id uuid NOT NULL, project_id text NOT NULL,
 run_id text NOT NULL CHECK (run_id ~ '^run_[0-9A-HJKMNP-TV-Z]{26}$'),
 state text NOT NULL DEFAULT 'draft' CHECK (state IN
 ('draft','validated','planned','awaiting_approval','scheduled','running','verifying','recovering','succeeded','failed','cancelled')),
 version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
 attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, run_id),
 UNIQUE (tenant_id, project_id, run_id),
 FOREIGN KEY (tenant_id, project_id) REFERENCES inv.projects(tenant_id, project_id)
);
CREATE TABLE inv.run_attempts (
 tenant_id uuid NOT NULL, run_id text NOT NULL, attempt integer NOT NULL CHECK (attempt > 0),
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, run_id, attempt),
 FOREIGN KEY (tenant_id, run_id) REFERENCES inv.runs(tenant_id, run_id)
);
CREATE TABLE inv.resource_leases (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL, resource_id text NOT NULL,
 lease_id text NOT NULL CHECK (lease_id ~ '^lse_[0-9A-HJKMNP-TV-Z]{26}$'),
 amount bigint NOT NULL CHECK (amount > 0 AND amount <= 9007199254740991),
 fencing_token bigint NOT NULL DEFAULT nextval('inv.fencing_token_seq') CHECK (fencing_token > 0),
 granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL, released_at timestamptz,
 recovery_epoch uuid NOT NULL, stop_receipt uuid,
 CHECK ((released_at IS NULL) = (stop_receipt IS NULL)),
 PRIMARY KEY (tenant_id, lease_id),
 UNIQUE (tenant_id, resource_id, fencing_token),
 CHECK (expires_at > granted_at),
 FOREIGN KEY (tenant_id, project_id, run_id) REFERENCES inv.runs(tenant_id, project_id, run_id),
 FOREIGN KEY (tenant_id, resource_id) REFERENCES inv.resources(tenant_id, resource_id)
);
CREATE INDEX leases_resource_active ON inv.resource_leases(tenant_id, resource_id, expires_at) WHERE released_at IS NULL;
CREATE INDEX leases_run ON inv.resource_leases(tenant_id, run_id);
CREATE TABLE inv.idempotency (
 tenant_id uuid NOT NULL, project_id text NOT NULL, operation text NOT NULL, key text NOT NULL CHECK (length(key) BETWEEN 1 AND 200),
 request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
 response jsonb CHECK (octet_length(response::text) <= 1048576), created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, project_id, operation, key),
 FOREIGN KEY (tenant_id, project_id) REFERENCES inv.projects(tenant_id, project_id)
);
CREATE TABLE inv.checkpoints (
 tenant_id uuid NOT NULL, run_id text NOT NULL, attempt integer NOT NULL,
 step_id text NOT NULL, content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
 checkpoint jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, run_id, attempt, step_id),
 FOREIGN KEY (tenant_id, run_id, attempt) REFERENCES inv.run_attempts(tenant_id, run_id, attempt)
);
CREATE TABLE inv.evidence (
 tenant_id uuid NOT NULL, run_id text NOT NULL,
 evidence_id text NOT NULL CHECK (evidence_id ~ '^evd_[0-9A-HJKMNP-TV-Z]{26}$'),
 envelope jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, evidence_id),
 FOREIGN KEY (tenant_id, run_id) REFERENCES inv.runs(tenant_id, run_id),
 CHECK (envelope->>'tenantId' IS NOT NULL AND (envelope->>'tenantId')::uuid = tenant_id),
 CHECK (envelope->>'runId' IS NOT NULL AND envelope->>'runId' = run_id),
 CHECK (envelope->>'evidenceId' IS NOT NULL AND envelope->>'evidenceId' = evidence_id),
 CHECK (envelope->>'result' IS NOT NULL AND envelope->>'result' IN ('succeeded','failed','denied'))
);
CREATE TABLE inv.outbox (
 tenant_id uuid NOT NULL, run_id text NOT NULL, event_id uuid NOT NULL,
 event_type text NOT NULL CHECK (event_type LIKE 'inv.%'), payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), published_at timestamptz,
 PRIMARY KEY (tenant_id, event_id),
 FOREIGN KEY (tenant_id, run_id) REFERENCES inv.runs(tenant_id, run_id)
);
CREATE TABLE inv.consumer_inbox (
 tenant_id uuid NOT NULL REFERENCES inv.tenants(tenant_id), consumer text NOT NULL, event_id uuid NOT NULL,
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id, consumer, event_id)
);
-- Policies apply to SELECT/UPDATE/DELETE and to the new values of INSERT/UPDATE.
DO $body$
DECLARE tab text;
BEGIN
 FOREACH tab IN ARRAY ARRAY['tenants','projects','nodes','resources','runs','run_attempts',
 'resource_leases','idempotency','checkpoints','evidence','outbox','consumer_inbox'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY', tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY', tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING (tenant_id = nullif(current_setting(''inv.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = nullif(current_setting(''inv.tenant_id'', true), '''')::uuid)', tab);
 END LOOP;
END; $body$;
CREATE FUNCTION inv.immutable_record() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN RAISE EXCEPTION 'immutable record' USING ERRCODE = '23514'; END; $body$;
CREATE TRIGGER evidence_immutable BEFORE UPDATE OR DELETE ON inv.evidence FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE TRIGGER checkpoint_immutable BEFORE UPDATE OR DELETE ON inv.checkpoints FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_run() RETURNS trigger LANGUAGE plpgsql AS $body$
DECLARE allowed boolean;
BEGIN
 IF TG_OP = 'INSERT' THEN
  IF NEW.state <> 'draft' OR NEW.version <> 1 OR NEW.attempt <> 0 THEN
   RAISE EXCEPTION 'runs begin in draft at version 1, attempt 0' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
 END IF;
 IF NEW.tenant_id <> OLD.tenant_id OR NEW.project_id <> OLD.project_id OR NEW.run_id <> OLD.run_id THEN
  RAISE EXCEPTION 'run identity is immutable' USING ERRCODE = '23514';
 END IF;
 IF NEW.state = OLD.state THEN
  IF NEW.version <> OLD.version OR NEW.attempt <> OLD.attempt THEN
   RAISE EXCEPTION 'state required for version or attempt change' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
 END IF;
 allowed := (OLD.state NOT IN ('succeeded','failed','cancelled') AND NEW.state IN ('failed','cancelled'))
 OR (OLD.state='draft' AND NEW.state='validated')
 OR (OLD.state='validated' AND NEW.state='planned')
 OR (OLD.state='planned' AND NEW.state IN ('awaiting_approval','scheduled'))
 OR (OLD.state='awaiting_approval' AND NEW.state='scheduled')
 OR (OLD.state='scheduled' AND NEW.state='running')
 OR (OLD.state='running' AND NEW.state IN ('verifying','recovering'))
 OR (OLD.state='verifying' AND NEW.state IN ('succeeded','recovering'))
 OR (OLD.state='recovering' AND NEW.state='scheduled');
 IF NOT allowed OR NEW.version <> OLD.version + 1
 OR NEW.attempt <> OLD.attempt + (CASE WHEN NEW.state='running' THEN 1 ELSE 0 END) THEN
  RAISE EXCEPTION 'invalid run transition' USING ERRCODE = '23514';
 END IF;
 IF NEW.state='succeeded' AND NOT EXISTS
 (SELECT 1 FROM inv.evidence e WHERE e.tenant_id=NEW.tenant_id AND e.run_id=NEW.run_id AND e.envelope->>'result'='succeeded') THEN
  RAISE EXCEPTION 'success requires evidence' USING ERRCODE = '23514';
 END IF;
 NEW.updated_at := clock_timestamp();
 RETURN NEW;
END; $body$;
CREATE TRIGGER run_guard BEFORE INSERT OR UPDATE ON inv.runs FOR EACH ROW EXECUTE FUNCTION inv.guard_run();
-- Resources may be revised, but identity cannot be relocated across nodes.
CREATE FUNCTION inv.guard_resource_identity() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF (NEW.tenant_id, NEW.resource_id, NEW.node_id, NEW.kind) IS DISTINCT FROM
    (OLD.tenant_id, OLD.resource_id, OLD.node_id, OLD.kind) THEN
  RAISE EXCEPTION 'resource identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER resource_identity BEFORE UPDATE ON inv.resources FOR EACH ROW EXECUTE FUNCTION inv.guard_resource_identity();
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA inv FROM PUBLIC;
