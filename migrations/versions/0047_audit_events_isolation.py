"""audit_events tenant isolation (F-S02-01).

The S02 baseline granted ``inv_app`` SELECT and INSERT on ``audit_events`` and
left the table out of the RLS loop, so the application role could read every
tenant's authorisation decisions. ``AuditEvent``'s own docstring already claimed
the opposite -- that NULL-tenant rows sit outside RLS and are therefore read
through an audit role *separate* from the application role -- and that role did
not exist. This revision makes the DDL say what the model says.

Three policies, one per role, because the three needs are different:

* ``inv_app`` may write only rows of the tenant its transaction is scoped to,
  and may not read at all. The SELECT privilege is revoked *and* the policy's
  USING clause stays in place, so re-granting SELECT -- the exact mistake the
  baseline made -- does not reopen cross-tenant reads.
* ``inv_audit_writer`` owns the one SECURITY DEFINER primitive below and may
  append nothing but a NULL-tenant denial. AC-02 requires a rejected credential
  that resolves to no tenant to still be recorded; that row cannot be written
  under a tenant policy, and losing it is the failure AC-02 exists to prevent.
* ``inv_audit_reader`` reads. Its USING clause is unconditional on purpose: a
  NULL-tenant row belongs to no tenant, so a tenant predicate would hide exactly
  the rows this role exists to read. That the role therefore reads across
  tenants is recorded in ``tools/rls-boundary-baseline.json`` with its reason
  rather than left for a reader of the evidence to discover.

Reversible, unlike 0045 and 0046: adding RLS can be undone by removing it, and
an operator holding a rollback should not be told to restore from a backup for
a change that unpicks cleanly. The two roles are not dropped on downgrade --
they may be shared with another database in the cluster, the same reason
0001_s02_baseline gives for keeping ``inv_app``.
"""

from alembic import op

revision = "0047_audit_events_isolation"
down_revision = "0046_model_manifest_readiness"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$ BEGIN
      CREATE ROLE inv_audit_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
        NOINHERIT NOBYPASSRLS;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    ALTER ROLE inv_audit_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOBYPASSRLS;
    -- A member of the owning role can act as the definer, which would turn the
    -- narrow primitive into a general append path (the 0045 guard, same reason).
    DO $$ BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_auth_members m
        JOIN pg_roles granted_role ON granted_role.oid = m.roleid
        WHERE granted_role.rolname = 'inv_audit_writer'
      ) THEN
        RAISE EXCEPTION 'inv_audit_writer has members; refusing denial-primitive ownership';
      END IF;
    END $$;
    DO $$ BEGIN
      CREATE ROLE inv_audit_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
        NOINHERIT NOBYPASSRLS;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    ALTER ROLE inv_audit_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOBYPASSRLS;
    -- Reading audit records must not be reachable from a runtime role; an
    -- operator who granted it there gets a stopped migration, not a quiet pass.
    DO $$ BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_auth_members m
        JOIN pg_roles granted_role ON granted_role.oid = m.roleid
        JOIN pg_roles member_role ON member_role.oid = m.member
        WHERE granted_role.rolname = 'inv_audit_reader'
          AND member_role.rolname IN ('inv_app', 'inv_kernel')
      ) THEN
        RAISE EXCEPTION 'a runtime role is a member of inv_audit_reader; review membership before migration';
      END IF;
    END $$;
    GRANT USAGE ON SCHEMA public TO inv_audit_reader;
    -- CREATE is needed only to receive ownership of the function below, and is
    -- revoked again in the same transaction.
    GRANT USAGE, CREATE ON SCHEMA public TO inv_audit_writer;

    ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
    -- FORCE, or the migration owner silently bypasses every policy below.
    ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
    CREATE POLICY audit_events_tenant_isolation ON audit_events FOR ALL TO inv_app
      USING (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('inv.tenant_id',true),'')::uuid);
    CREATE POLICY audit_events_denial_append ON audit_events FOR INSERT TO inv_audit_writer
      WITH CHECK (tenant_id IS NULL AND outcome = 'deny');
    CREATE POLICY audit_events_audit_read ON audit_events FOR SELECT TO inv_audit_reader
      USING (true);
    -- The application never reads audit records; it only appends them. INSERT
    -- stays, so append-only for this role is unchanged (PLAN-DB-001).
    REVOKE SELECT ON audit_events FROM inv_app;
    GRANT INSERT ON audit_events TO inv_audit_writer;
    GRANT SELECT ON audit_events TO inv_audit_reader;

    -- The only way the application can record a denial it cannot attribute to a
    -- tenant. tenant_id, outcome and occurred_at are constants here: the caller
    -- chooses the facts of the denial, never whose row it is, whether it was an
    -- allow, or when it happened.
    CREATE FUNCTION public.record_auth_denial(
      p_event_id text,
      p_actor_type text,
      p_action text,
      p_reason_code text,
      p_actor_id text,
      p_trace_id text,
      p_target_type text,
      p_target_id text,
      p_detail jsonb,
      p_source_ip text,
      p_user_agent text
    ) RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    -- Pinned, because a SECURITY DEFINER function that resolves names through
    -- the caller's search_path becomes a privilege escalation. Everything the
    -- body touches is schema-qualified, so pg_catalog alone is enough.
    SET search_path = pg_catalog
    AS $fn$
    BEGIN
      IF p_event_id IS NULL OR p_actor_type IS NULL OR p_action IS NULL
         OR p_reason_code IS NULL THEN
        RAISE EXCEPTION 'a denial record needs an event id, actor type, action and reason code'
          USING ERRCODE = '22023';
      END IF;
      INSERT INTO public.audit_events
        (event_id, occurred_at, tenant_id, actor_type, actor_id, action, outcome,
         reason_code, trace_id, target_type, target_id, detail, source_ip, user_agent)
      VALUES
        (p_event_id, clock_timestamp(), NULL, p_actor_type, p_actor_id, p_action,
         'deny', p_reason_code, p_trace_id, p_target_type, p_target_id,
         coalesce(p_detail, '{}'::jsonb), p_source_ip, p_user_agent);
    END
    $fn$;
    GRANT inv_audit_writer TO CURRENT_USER;
    ALTER FUNCTION public.record_auth_denial(text,text,text,text,text,text,text,text,jsonb,text,text)
      OWNER TO inv_audit_writer;
    REVOKE CREATE ON SCHEMA public FROM inv_audit_writer;
    REVOKE inv_audit_writer FROM CURRENT_USER;
    REVOKE ALL ON FUNCTION public.record_auth_denial(text,text,text,text,text,text,text,text,jsonb,text,text)
      FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.record_auth_denial(text,text,text,text,text,text,text,text,jsonb,text,text)
      TO inv_app;
    """)


def downgrade():
    """Undo the isolation. Restores the baseline grant, keeps the roles.

    Dropping ``inv_audit_writer`` or ``inv_audit_reader`` here would fail
    whenever another database in the cluster still owns objects or memberships
    through them, so they are left in place with no privileges on this database.
    """
    op.execute("""
    DROP FUNCTION IF EXISTS
      public.record_auth_denial(text,text,text,text,text,text,text,text,jsonb,text,text);
    DROP POLICY IF EXISTS audit_events_audit_read ON audit_events;
    DROP POLICY IF EXISTS audit_events_denial_append ON audit_events;
    DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events;
    ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY;
    REVOKE INSERT ON audit_events FROM inv_audit_writer;
    REVOKE SELECT ON audit_events FROM inv_audit_reader;
    REVOKE USAGE ON SCHEMA public FROM inv_audit_reader;
    REVOKE USAGE ON SCHEMA public FROM inv_audit_writer;
    GRANT SELECT ON audit_events TO inv_app;
    """)
