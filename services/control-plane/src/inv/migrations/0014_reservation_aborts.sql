-- Non-execution proof is distinct from an authenticated Node stop receipt.
CREATE TABLE inv.reservation_aborts (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 abort_id uuid NOT NULL, reason text NOT NULL CHECK(reason IN ('cancelled_before_claim','admission_failed')),
 recovery_epoch uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,run_id), UNIQUE(tenant_id,run_id,abort_id),
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id)
);
ALTER TABLE inv.reservation_aborts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inv.reservation_aborts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON inv.reservation_aborts
 USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
 WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.reservation_aborts
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_reservation_abort() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM 1 FROM inv.runs WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id AND state='cancelled' FOR UPDATE;
 IF NOT FOUND OR EXISTS(SELECT 1 FROM inv.tool_claims WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id)
 OR EXISTS(SELECT 1 FROM inv.run_attempts WHERE tenant_id=NEW.tenant_id AND run_id=NEW.run_id) THEN
  RAISE EXCEPTION 'Cannot reclaim a reservation with possible execution' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER prove_no_execution BEFORE INSERT ON inv.reservation_aborts
 FOR EACH ROW EXECUTE FUNCTION inv.guard_reservation_abort();
ALTER TABLE inv.resource_leases ADD COLUMN reservation_abort uuid;
ALTER TABLE inv.resource_leases DROP CONSTRAINT resource_leases_check;
ALTER TABLE inv.resource_leases ADD CONSTRAINT lease_release_proof CHECK (
 (released_at IS NULL AND stop_receipt IS NULL AND reservation_abort IS NULL) OR
 (released_at IS NOT NULL AND num_nonnulls(stop_receipt,reservation_abort)=1)
);
ALTER TABLE inv.resource_leases ADD FOREIGN KEY(tenant_id,run_id,reservation_abort)
 REFERENCES inv.reservation_aborts(tenant_id,run_id,abort_id);
