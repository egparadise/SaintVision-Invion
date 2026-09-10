-- Group role only: an operator provisions the separate LOGIN credential and
-- grants membership. The web process must never own schemas or have BYPASSRLS.
DO $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='inv_kernel') THEN
  CREATE ROLE inv_kernel NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='inv_kernel' AND
  (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
  RAISE EXCEPTION 'inv_kernel must be a nonprivileged NOLOGIN group role';
 END IF;
END $$;
GRANT USAGE ON SCHEMA inv TO inv_kernel;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA inv TO inv_kernel;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA inv TO inv_kernel;
REVOKE INSERT,UPDATE,DELETE ON inv.control_epoch,inv.evidence,inv.checkpoints FROM inv_kernel;
GRANT INSERT ON inv.evidence,inv.checkpoints TO inv_kernel;
-- CHECK-fixed sentinels allow SELECT FOR SHARE without changing authority.
GRANT UPDATE(singleton) ON inv.control_epoch TO inv_kernel;
REVOKE INSERT,UPDATE,DELETE ON inv.project_grants,inv.project_nodes FROM inv_kernel;
GRANT UPDATE(lock_sentinel) ON inv.project_grants,inv.project_nodes TO inv_kernel;
REVOKE UPDATE,DELETE ON inv.approval_votes,inv.approval_dispatches,inv.approval_audit,
 inv.tool_claims,inv.node_stop_receipts FROM inv_kernel;
REVOKE INSERT,UPDATE,DELETE ON inv.node_channels,inv.node_channel_audit FROM inv_kernel;
GRANT UPDATE(lock_sentinel) ON inv.node_channels TO inv_kernel;
