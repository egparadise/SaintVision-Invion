-- Immutable editor snapshots; runtime tests explicitly deferred for WORKSPACE-BRIDGE.
CREATE TABLE inv.workspace_edits (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 checkout_id uuid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
 subject_id text NOT NULL, recovery_epoch uuid NOT NULL,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 1 AND 65536),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,checkout_id,revision),
 FOREIGN KEY(tenant_id,checkout_id) REFERENCES inv.workspace_checkouts,
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id)
);
ALTER TABLE inv.workspace_edits ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.workspace_edits FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.workspace_edits
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.workspace_edits
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
GRANT SELECT,INSERT ON inv.workspace_edits TO inv_kernel;

CREATE TABLE inv.terminal_tickets (
 tenant_id uuid NOT NULL, ticket_hash text NOT NULL CHECK(ticket_hash ~ '^[0-9a-f]{64}$'),
 project_id text NOT NULL, run_id text NOT NULL, command_id uuid NOT NULL,
 session_id uuid NOT NULL, subject_id text NOT NULL, origin text NOT NULL,
 recovery_epoch uuid NOT NULL, expires_at timestamptz NOT NULL, consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,ticket_hash),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.tool_claims(tenant_id,command_id),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '30 seconds')
);
ALTER TABLE inv.terminal_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.terminal_tickets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.terminal_tickets
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
GRANT SELECT,INSERT,UPDATE(consumed_at) ON inv.terminal_tickets TO inv_kernel;
CREATE FUNCTION inv.guard_terminal_ticket() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR OLD.consumed_at IS NOT NULL OR NEW.consumed_at IS NULL
 OR (to_jsonb(NEW)-'consumed_at') IS DISTINCT FROM (to_jsonb(OLD)-'consumed_at') THEN
  RAISE EXCEPTION 'Terminal ticket is immutable and single use' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.terminal_tickets
 FOR EACH ROW EXECUTE FUNCTION inv.guard_terminal_ticket();
REVOKE ALL ON FUNCTION inv.guard_terminal_ticket() FROM PUBLIC;

CREATE TABLE inv.terminal_connections (
 tenant_id uuid NOT NULL, command_id uuid NOT NULL, connection_id uuid,
 expires_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,command_id),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.tool_claims(tenant_id,command_id)
);
ALTER TABLE inv.terminal_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.terminal_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.terminal_connections
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
GRANT SELECT,INSERT,UPDATE(connection_id,expires_at) ON inv.terminal_connections TO inv_kernel;

CREATE TABLE inv.terminal_frame_audit (
 tenant_id uuid NOT NULL, command_id uuid NOT NULL, sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 4096),
 frame_digest text NOT NULL CHECK(frame_digest ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(tenant_id,command_id,sequence),
 FOREIGN KEY(tenant_id,command_id) REFERENCES inv.tool_claims(tenant_id,command_id)
);

ALTER TABLE inv.operator_grants ADD COLUMN can_git boolean NOT NULL DEFAULT false;
CREATE TABLE inv.git_operations (
 tenant_id uuid NOT NULL, operation_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 checkout_id uuid NOT NULL, key text NOT NULL CHECK(length(key) BETWEEN 1 AND 200),
 requester_id text NOT NULL, requester_person_id uuid NOT NULL, recovery_epoch uuid NOT NULL,
 gate_version bigint NOT NULL, request_hash text NOT NULL, content_digest text NOT NULL,
 remote_scope text NOT NULL CHECK(remote_scope ~ '^[0-9a-f]{64}$'),
 payload jsonb NOT NULL CHECK(octet_length(payload::text)<=100000),
 snapshot bytea NOT NULL CHECK(octet_length(snapshot) BETWEEN 1 AND 65536),
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 phase text NOT NULL DEFAULT 'pending' CHECK(phase IN ('pending','rejected','dispatched','completed')),
 result jsonb,
 PRIMARY KEY(tenant_id,operation_id), UNIQUE(tenant_id,project_id,requester_id,key),
 FOREIGN KEY(tenant_id,checkout_id) REFERENCES inv.workspace_checkouts,
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '5 minutes'),
 CHECK((phase='completed')=(result IS NOT NULL))
);
CREATE UNIQUE INDEX git_one_unresolved_remote ON inv.git_operations(tenant_id,remote_scope) WHERE phase='dispatched';
CREATE TABLE inv.git_votes (
 tenant_id uuid NOT NULL, operation_id uuid NOT NULL, actor_id text NOT NULL, person_id uuid NOT NULL,
 decision text NOT NULL CHECK(decision IN ('approve','reject')), content_digest text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,operation_id,actor_id), UNIQUE(tenant_id,operation_id,person_id),
 FOREIGN KEY(tenant_id,operation_id) REFERENCES inv.git_operations
);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['terminal_frame_audit','git_operations','git_votes'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT,INSERT ON inv.%I TO inv_kernel',tab);
 END LOOP;
END $$;
GRANT UPDATE(phase,result) ON inv.git_operations TO inv_kernel;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.terminal_frame_audit FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.git_votes FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_git_operation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-'phase'-'result') IS DISTINCT FROM (to_jsonb(OLD)-'phase'-'result')
 OR NOT ((OLD.phase='pending' AND NEW.phase IN ('rejected','dispatched','completed'))
         OR (OLD.phase='dispatched' AND NEW.phase='completed')) THEN
  RAISE EXCEPTION 'Git intent and publication history are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.git_operations FOR EACH ROW EXECUTE FUNCTION inv.guard_git_operation();
REVOKE ALL ON FUNCTION inv.guard_git_operation() FROM PUBLIC;
