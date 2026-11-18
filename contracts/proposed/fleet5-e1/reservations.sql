-- Candidate storage, outside automatic migrations pending a shared writer fence.
CREATE TABLE e1.reservations (
    tenant_id uuid NOT NULL,
    pc text NOT NULL CHECK (pc = 'PC1'),
    node_id text NOT NULL CHECK (node_id = 'nod_00000000000000000000000PC1'),
    request_id uuid NOT NULL,
    holder text NOT NULL,
    generation bigint NOT NULL CHECK (generation > 0),
    binding jsonb NOT NULL,
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (tenant_id, pc),
    UNIQUE (tenant_id, node_id),
    UNIQUE (tenant_id, request_id)
);

ALTER TABLE e1.reservations
    ADD COLUMN public_key_sha256 text NOT NULL CHECK (public_key_sha256 ~ '^[0-9a-f]{64}$'),
    ADD COLUMN manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    ADD COLUMN operation_id text NOT NULL CHECK (length(operation_id) BETWEEN 1 AND 256),
    ADD UNIQUE (tenant_id, public_key_sha256),
    ADD UNIQUE (tenant_id, digest);
CREATE UNIQUE INDEX reservation_csr ON e1.reservations (tenant_id, (binding->>'csrSHA256'));

-- Scoped fallback audit until A1 publishes the shared journal migration.
CREATE TABLE e1.reservation_audit (
    tenant_id uuid NOT NULL,
    operation_id text NOT NULL,
    manifest_digest text NOT NULL,
    digest text NOT NULL,
    PRIMARY KEY (tenant_id, operation_id),
    UNIQUE (tenant_id, digest),
    FOREIGN KEY (tenant_id, digest) REFERENCES e1.reservations (tenant_id, digest)
);

ALTER TABLE e1.reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE e1.reservations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON e1.reservations
    USING (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid);
ALTER TABLE e1.reservation_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE e1.reservation_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON e1.reservation_audit
    USING (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid);

CREATE FUNCTION e1.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable E1 evidence';
END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON e1.reservations
    FOR EACH ROW EXECUTE FUNCTION e1.reject_change();
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON e1.reservation_audit
    FOR EACH ROW EXECUTE FUNCTION e1.reject_change();
-- Installed atomically with the E1 candidate, outside migration discovery.
CREATE SCHEMA fleet_writer;
REVOKE ALL ON SCHEMA fleet_writer FROM PUBLIC;
CREATE TABLE fleet_writer.principals (
    login name PRIMARY KEY,
    tenant_id uuid NOT NULL,
    UNIQUE (login, tenant_id)
);
CREATE FUNCTION fleet_writer.authenticated_tenant() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT tenant_id FROM fleet_writer.principals WHERE login = session_user
$$;
CREATE TABLE fleet_writer.authority (
    tenant_id uuid PRIMARY KEY,
    login name NOT NULL,
    holder text NOT NULL CHECK (length(trim(holder)) > 0),
    generation bigint NOT NULL CHECK (generation > 0),
    FOREIGN KEY (login, tenant_id) REFERENCES fleet_writer.principals(login, tenant_id)
);
CREATE FUNCTION fleet_writer.guard_transfer() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP <> 'UPDATE' THEN RAISE EXCEPTION 'authority deletion forbidden'; END IF;
    IF NEW.tenant_id <> OLD.tenant_id OR NEW.generation <> OLD.generation + 1 THEN
        RAISE EXCEPTION 'authority transfer requires next generation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guard_transfer BEFORE UPDATE OR DELETE ON fleet_writer.authority
FOR EACH ROW EXECUTE FUNCTION fleet_writer.guard_transfer();
CREATE FUNCTION fleet_writer.lock_holder(scope uuid)
RETURNS TABLE(holder text, generation bigint)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
    SELECT a.holder, a.generation FROM fleet_writer.authority a
    WHERE a.tenant_id = scope AND a.login = session_user
      AND scope = fleet_writer.authenticated_tenant()
      AND scope::text = current_setting('inv.tenant_id', true)
    FOR UPDATE OF a
$$;
CREATE TABLE fleet_writer.journal (
    tenant_id uuid NOT NULL,
    operation_id text NOT NULL,
    kind text NOT NULL,
    holder text NOT NULL,
    generation bigint NOT NULL,
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (tenant_id, operation_id)
);
ALTER TABLE fleet_writer.journal ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleet_writer.journal FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON fleet_writer.journal
    USING (tenant_id = fleet_writer.authenticated_tenant()
           AND tenant_id::text = current_setting('inv.tenant_id', true));
CREATE FUNCTION fleet_writer.check_append() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT FROM fleet_writer.lock_holder(NEW.tenant_id) a
                   WHERE (a.holder,a.generation) = (NEW.holder,NEW.generation)) THEN
        RAISE EXCEPTION 'stale writer';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_append BEFORE INSERT ON fleet_writer.journal
FOR EACH ROW EXECUTE FUNCTION fleet_writer.check_append();
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON fleet_writer.journal
FOR EACH ROW EXECUTE FUNCTION e1.reject_change();
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA fleet_writer FROM PUBLIC;
CREATE POLICY authenticated_scope ON e1.reservations AS RESTRICTIVE
    USING (tenant_id = fleet_writer.authenticated_tenant());
CREATE POLICY authenticated_scope ON e1.reservation_audit AS RESTRICTIVE
    USING (tenant_id = fleet_writer.authenticated_tenant());
CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON e1.reservations
FOR EACH STATEMENT EXECUTE FUNCTION e1.reject_change();
CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON e1.reservation_audit
FOR EACH STATEMENT EXECUTE FUNCTION e1.reject_change();
CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON fleet_writer.journal
FOR EACH STATEMENT EXECUTE FUNCTION e1.reject_change();
CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON fleet_writer.authority
FOR EACH STATEMENT EXECUTE FUNCTION e1.reject_change();
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA e1, fleet_writer FROM PUBLIC;
