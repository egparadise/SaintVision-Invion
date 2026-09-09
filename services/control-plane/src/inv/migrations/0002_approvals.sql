-- Durable approval boundary. Runtime may only READ the identity/grant projection.
CREATE TABLE inv.project_grants (
 tenant_id uuid NOT NULL, project_id text NOT NULL, subject_id text NOT NULL CHECK(length(subject_id) BETWEEN 1 AND 200),
 can_request boolean NOT NULL DEFAULT false, can_approve boolean NOT NULL DEFAULT false, enabled boolean NOT NULL DEFAULT true,
 lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,project_id,subject_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects(tenant_id,project_id)
);
CREATE TABLE inv.approval_requests (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 approval_id text NOT NULL CHECK(approval_id ~ '^apr_[0-9A-HJKMNP-TV-Z]{26}$'),
 requester_id text NOT NULL, action_digest text NOT NULL CHECK(action_digest ~ '^[0-9a-f]{64}$'),
 policy_decision_id text NOT NULL, policy_version text NOT NULL,
 recovery_epoch uuid NOT NULL, bound_run_version bigint NOT NULL CHECK(bound_run_version > 0),
 required_approvals integer NOT NULL CHECK(required_approvals IN (1,2)),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','expired','dispatched')),
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,approval_id), UNIQUE(tenant_id,run_id),
 CHECK(expires_at > created_at),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,project_id,requester_id) REFERENCES inv.project_grants(tenant_id,project_id,subject_id)
);
CREATE TABLE inv.approval_nonces (
 tenant_id uuid NOT NULL, approval_id text NOT NULL, actor_id text NOT NULL,
 nonce_hash text NOT NULL CHECK(nonce_hash ~ '^[0-9a-f]{64}$'),
 expires_at timestamptz NOT NULL, consumed_at timestamptz,
 PRIMARY KEY(tenant_id,approval_id,actor_id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests(tenant_id,approval_id)
);
CREATE TABLE inv.approval_votes (
 tenant_id uuid NOT NULL, approval_id text NOT NULL, actor_id text NOT NULL,
 decision text NOT NULL CHECK(decision IN ('approve','reject')),
 nonce_hash text NOT NULL CHECK(nonce_hash ~ '^[0-9a-f]{64}$'),
 decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,approval_id,actor_id),
 FOREIGN KEY(tenant_id,approval_id,actor_id) REFERENCES inv.approval_nonces(tenant_id,approval_id,actor_id)
);
CREATE TABLE inv.approval_dispatches (
 tenant_id uuid NOT NULL, approval_id text NOT NULL, command_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,approval_id), UNIQUE(tenant_id,command_id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests(tenant_id,approval_id)
);
CREATE TABLE inv.approval_audit (
 tenant_id uuid NOT NULL, approval_id text NOT NULL, event_id uuid NOT NULL,
 actor_id text NOT NULL, phase text NOT NULL CHECK(phase IN ('requested','approved','rejected','expired','dispatched')),
 record jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,event_id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests(tenant_id,approval_id)
);
DO $body$
DECLARE tab text;
BEGIN
 FOREACH tab IN ARRAY ARRAY['project_grants','approval_requests','approval_nonces','approval_votes','approval_dispatches','approval_audit'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format($policy$CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)$policy$,tab);
 END LOOP;
 FOREACH tab IN ARRAY ARRAY['approval_votes','approval_dispatches','approval_audit'] LOOP
  EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
 END LOOP;
END; $body$;
CREATE FUNCTION inv.guard_approval_request() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'approval history is immutable' USING ERRCODE='23514'; END IF;
 IF (to_jsonb(NEW)-'status') IS DISTINCT FROM (to_jsonb(OLD)-'status') THEN
  RAISE EXCEPTION 'approval scope is immutable; create a new run' USING ERRCODE='23514';
 END IF;
 IF NEW.status=OLD.status THEN RETURN NEW; END IF;
 IF NOT ((OLD.status='pending' AND NEW.status IN ('approved','rejected','expired')) OR
         (OLD.status='approved' AND NEW.status IN ('dispatched','expired'))) THEN
  RAISE EXCEPTION 'invalid approval transition' USING ERRCODE='23514';
 END IF;
 IF NEW.status='approved' AND (SELECT count(*) FROM inv.approval_votes WHERE tenant_id=NEW.tenant_id AND approval_id=NEW.approval_id AND decision='approve') < NEW.required_approvals THEN
  RAISE EXCEPTION 'approval quorum missing' USING ERRCODE='23514';
 END IF;
 IF NEW.status='dispatched' AND NOT EXISTS(SELECT 1 FROM inv.approval_dispatches WHERE tenant_id=NEW.tenant_id AND approval_id=NEW.approval_id) THEN
  RAISE EXCEPTION 'durable dispatch missing' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER approval_request_guard BEFORE UPDATE OR DELETE ON inv.approval_requests FOR EACH ROW EXECUTE FUNCTION inv.guard_approval_request();
CREATE FUNCTION inv.guard_approval_schedule() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF OLD.state='awaiting_approval' AND NEW.state='scheduled' AND NOT EXISTS (
  SELECT 1 FROM inv.approval_requests a JOIN inv.approval_dispatches d USING(tenant_id,approval_id)
  WHERE a.tenant_id=NEW.tenant_id AND a.run_id=NEW.run_id AND a.status='dispatched'
    AND a.bound_run_version=OLD.version AND a.expires_at>clock_timestamp()
    AND a.recovery_epoch=(SELECT epoch FROM inv.control_epoch WHERE singleton)
 ) THEN
  RAISE EXCEPTION 'scheduled requires a current durable approval dispatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $body$;
CREATE TRIGGER approval_schedule_guard BEFORE UPDATE ON inv.runs FOR EACH ROW EXECUTE FUNCTION inv.guard_approval_schedule();
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA inv FROM PUBLIC;
