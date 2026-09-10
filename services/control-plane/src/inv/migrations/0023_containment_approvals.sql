-- L2 containment changes need two distinct current people, fixed content and expiry.
-- Never infer real-person identities or retroactively approve existing controls.
ALTER TABLE inv.operator_grants ADD COLUMN person_id uuid;
ALTER TABLE inv.operator_grants ADD COLUMN can_approve boolean NOT NULL DEFAULT false;
ALTER TABLE inv.operator_grants ADD UNIQUE(tenant_id,person_id);
CREATE FUNCTION inv.guard_operator_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR NEW.tenant_id<>OLD.tenant_id OR NEW.subject_id<>OLD.subject_id
 OR (OLD.person_id IS NOT NULL AND NEW.person_id IS DISTINCT FROM OLD.person_id) THEN
  RAISE EXCEPTION 'Verified operator identity is immutable; disable instead' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER identity_guard BEFORE UPDATE OR DELETE ON inv.operator_grants
 FOR EACH ROW EXECUTE FUNCTION inv.guard_operator_identity();
CREATE TABLE inv.containment_approvals (
 tenant_id uuid NOT NULL REFERENCES inv.tenants, approval_id uuid NOT NULL,
 key text NOT NULL CHECK(length(key) BETWEEN 1 AND 200),
 requester_id text NOT NULL, requester_person_id uuid NOT NULL,
 operation text NOT NULL CHECK(operation IN ('kill','clear','drain','resume')),
 node_id text, expected_version bigint NOT NULL CHECK(expected_version>=0),
 gate_version bigint NOT NULL CHECK(gate_version>=0), recovery_epoch uuid NOT NULL,
 reason_code text NOT NULL CHECK(reason_code IN ('maintenance','incident','operator_request')),
 content_digest text NOT NULL CHECK(content_digest ~ '^[0-9a-f]{64}$'),
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','consumed')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), expires_at timestamptz NOT NULL,
 consumed_request_id uuid,
 PRIMARY KEY(tenant_id,approval_id), UNIQUE(tenant_id,requester_id,key),
 FOREIGN KEY(tenant_id,node_id) REFERENCES inv.nodes,
 FOREIGN KEY(tenant_id,consumed_request_id) REFERENCES inv.containment_requests(tenant_id,request_id),
 CHECK((operation IN ('kill','clear'))=(node_id IS NULL)),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '5 minutes'),
 CHECK((status='consumed')=(consumed_request_id IS NOT NULL))
);
CREATE TABLE inv.containment_challenges (
 tenant_id uuid NOT NULL, approval_id uuid NOT NULL, actor_id text NOT NULL,
 person_id uuid NOT NULL, nonce text NOT NULL CHECK(nonce ~ '^[0-9a-f]{64}$'),
 expires_at timestamptz NOT NULL, used_at timestamptz,
 PRIMARY KEY(tenant_id,nonce), FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.containment_approvals
);
CREATE TABLE inv.containment_votes (
 tenant_id uuid NOT NULL, approval_id uuid NOT NULL, actor_id text NOT NULL,
 person_id uuid NOT NULL, key text NOT NULL CHECK(length(key) BETWEEN 1 AND 200),
 decision text NOT NULL CHECK(decision IN ('approve','reject')), request_hash text NOT NULL,
 response jsonb, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,approval_id,actor_id), UNIQUE(tenant_id,approval_id,person_id),
 UNIQUE(tenant_id,approval_id,key), FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.containment_approvals
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['containment_approvals','containment_challenges','containment_votes'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT,INSERT ON inv.%I TO inv_kernel',tab);
 END LOOP;
END $$;
GRANT UPDATE(status,consumed_request_id) ON inv.containment_approvals TO inv_kernel;
GRANT UPDATE(used_at) ON inv.containment_challenges TO inv_kernel;
GRANT UPDATE(response) ON inv.containment_votes TO inv_kernel;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.containment_votes
 FOR EACH ROW EXECUTE FUNCTION inv.guard_containment_request();
CREATE FUNCTION inv.guard_containment_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-'status'-'consumed_request_id') IS DISTINCT FROM
  (to_jsonb(OLD)-'status'-'consumed_request_id') OR OLD.status IN ('rejected','consumed')
  OR NOT ((OLD.status='pending' AND NEW.status IN ('approved','rejected')) OR
          (OLD.status='approved' AND NEW.status='consumed')) THEN
  RAISE EXCEPTION 'Containment approval history is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.containment_approvals
 FOR EACH ROW EXECUTE FUNCTION inv.guard_containment_approval();
REVOKE ALL ON FUNCTION inv.guard_operator_identity(),inv.guard_containment_approval() FROM PUBLIC;
