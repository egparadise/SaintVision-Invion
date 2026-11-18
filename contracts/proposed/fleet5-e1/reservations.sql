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
