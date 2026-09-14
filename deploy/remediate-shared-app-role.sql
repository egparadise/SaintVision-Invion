-- Proposed operator action, NOT part of startup or migrations.
-- Confirm service configuration uses deployment-specific logins first.
-- This disables future inv_app logins and removes its password, retaining
-- inherited application privileges for deployment-specific members.
-- Stop obsolete test runners first: older fixtures can re-enable this role.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename = 'inv_app') THEN
    RAISE EXCEPTION 'inv_app sessions remain; reconcile services before remediation';
  END IF;
END $$;
ALTER ROLE inv_app NOLOGIN PASSWORD NULL;
COMMIT;
