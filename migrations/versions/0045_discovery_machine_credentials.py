"""Issue and audit short-lived, installation-bound discovery credentials."""

from alembic import op

revision = "0045_discovery_machine_cred"
down_revision = "0044_model_registry_binding"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$ BEGIN
      CREATE ROLE inv_discovery_issuer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
        NOINHERIT NOBYPASSRLS;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    ALTER ROLE inv_discovery_issuer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOBYPASSRLS;
    DO $$ BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_auth_members m
        JOIN pg_roles granted_role ON granted_role.oid = m.roleid
        WHERE granted_role.rolname = 'inv_discovery_issuer'
      ) THEN
        RAISE EXCEPTION 'inv_discovery_issuer already has members; review membership before migration';
      END IF;
    END $$;
    GRANT USAGE ON SCHEMA public TO inv_discovery_issuer;
    GRANT SELECT(tenant_id) ON public.tenants TO inv_discovery_issuer;

    CREATE TABLE discovery_machine_credentials (
      credential_id varchar(30) PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
      installation_id varchar(128) NOT NULL
        CHECK (installation_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
      scope varchar(40) NOT NULL CHECK (scope = 'discovery:announce'),
      token_sha256 char(64) NOT NULL UNIQUE CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
      issued_by varchar(128) NOT NULL,
      issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      expires_at timestamptz NOT NULL CHECK (expires_at > issued_at),
      revoked_at timestamptz NULL,
      announcement_id varchar(30) NULL,
      last_announcement_at timestamptz NULL,
      CHECK ((announcement_id IS NULL) = (last_announcement_at IS NULL))
    );
    CREATE INDEX ix_discovery_machine_credentials_tenant_install
      ON discovery_machine_credentials(tenant_id, installation_id);
    CREATE INDEX ix_discovery_machine_credentials_expires_at
      ON discovery_machine_credentials(expires_at);
    CREATE UNIQUE INDEX uq_discovery_machine_credentials_one_active
      ON discovery_machine_credentials(tenant_id, installation_id)
      WHERE revoked_at IS NULL;
    ALTER TABLE discovery_machine_credentials ENABLE ROW LEVEL SECURITY;
    ALTER TABLE discovery_machine_credentials FORCE ROW LEVEL SECURITY;
    CREATE POLICY discovery_machine_credentials_tenant_isolation
      ON discovery_machine_credentials FOR ALL TO inv_app
      USING (
        tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid
        OR token_sha256 = nullif(current_setting('inv.discovery_token_sha256',true),'')
      )
      WITH CHECK (
        tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid
      );
    CREATE POLICY discovery_machine_credentials_issuer_access
      ON discovery_machine_credentials FOR ALL TO inv_discovery_issuer
      USING (true) WITH CHECK (true);
    REVOKE ALL ON discovery_machine_credentials FROM PUBLIC, inv_app, inv_kernel,
      inv_discovery_issuer;
    GRANT SELECT ON discovery_machine_credentials TO inv_app;
    GRANT UPDATE (revoked_at, announcement_id, last_announcement_at) ON discovery_machine_credentials TO inv_app;
    GRANT SELECT (credential_id, tenant_id, installation_id, scope, issued_by,
      issued_at, expires_at, revoked_at, announcement_id, last_announcement_at)
      ON discovery_machine_credentials TO inv_discovery_issuer;
    GRANT INSERT (credential_id, tenant_id, installation_id, scope, token_sha256, issued_by,
      issued_at, expires_at, announcement_id, last_announcement_at)
      ON discovery_machine_credentials TO inv_discovery_issuer;
    GRANT UPDATE (revoked_at) ON discovery_machine_credentials TO inv_discovery_issuer;

    CREATE TABLE discovery_credential_events (
      event_id uuid PRIMARY KEY,
      tenant_id uuid NOT NULL REFERENCES tenants(tenant_id),
      credential_id varchar(30) NULL,
      installation_id varchar(128) NULL,
      actor varchar(128) NOT NULL,
      event_type varchar(16) NOT NULL
        CHECK (event_type IN ('issued','revoked','announced','denied','admitted')),
      outcome varchar(8) NOT NULL CHECK (outcome IN ('allow','deny')),
      reason_code varchar(40) NULL,
      occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    CREATE INDEX ix_discovery_credential_events_tenant_time
      ON discovery_credential_events(tenant_id, occurred_at);
    ALTER TABLE discovery_credential_events ENABLE ROW LEVEL SECURITY;
    ALTER TABLE discovery_credential_events FORCE ROW LEVEL SECURITY;
    CREATE POLICY discovery_credential_events_tenant_isolation
      ON discovery_credential_events FOR ALL TO inv_app
      USING (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid);
    CREATE POLICY discovery_credential_events_issuer_access
      ON discovery_credential_events FOR ALL TO inv_discovery_issuer
      USING (true) WITH CHECK (true);
    REVOKE ALL ON discovery_credential_events FROM PUBLIC, inv_app, inv_kernel,
      inv_discovery_issuer;
    GRANT SELECT, INSERT ON discovery_credential_events TO inv_app;
    GRANT INSERT ON discovery_credential_events TO inv_discovery_issuer;
    """)


def downgrade():
    raise RuntimeError(
        "Issued discovery credentials are security records; use a reviewed forward fix"
    )
