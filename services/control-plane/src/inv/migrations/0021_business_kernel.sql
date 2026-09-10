-- PR14's business concepts, connected to canonical inv execution records.
-- No old revision renaming, automatic epoch roll, public approval-ID rewrite,
-- LOGIN credential creation, or broad inv grants to inv_app.
CREATE TABLE inv.business_projects (
 tenant_id uuid NOT NULL, project_id text NOT NULL,
 enabled boolean NOT NULL DEFAULT true,
 lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,project_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.projects,
 FOREIGN KEY(tenant_id,project_id) REFERENCES public.projects(tenant_id,project_id)
);
CREATE TABLE inv.business_subjects (
 tenant_id uuid NOT NULL, subject_id text NOT NULL CHECK(subject_id ~ '^oidc:[0-9a-f]{64}$'),
 user_id char(30) NOT NULL, enabled boolean NOT NULL DEFAULT true,
 lock_sentinel boolean NOT NULL DEFAULT true CHECK(lock_sentinel),
 PRIMARY KEY(tenant_id,subject_id), UNIQUE(tenant_id,user_id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES public.users(tenant_id,user_id)
);
CREATE TABLE inv.business_runs (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 workspace_id char(30) NOT NULL,
 PRIMARY KEY(tenant_id,run_id), UNIQUE(tenant_id,project_id,run_id,workspace_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES inv.business_projects,
 FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
 FOREIGN KEY(tenant_id,run_id) REFERENCES public.runs(tenant_id,run_id),
 FOREIGN KEY(tenant_id,workspace_id) REFERENCES public.workspaces(tenant_id,workspace_id)
);
CREATE TABLE public.workspace_edit_locks (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 workspace_id char(30) NOT NULL, lock_id uuid NOT NULL,
 checkout_id uuid NOT NULL, held_by_subject_id text NOT NULL,
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 input_size_bytes bigint NOT NULL CHECK(input_size_bytes BETWEEN 1 AND 65536),
 recovery_epoch uuid NOT NULL, bound_run_version bigint NOT NULL CHECK(bound_run_version>0),
 acquired_at timestamptz NOT NULL DEFAULT clock_timestamp(), released_at timestamptz,
 PRIMARY KEY(tenant_id,lock_id), UNIQUE(tenant_id,project_id,run_id,lock_id),
 FOREIGN KEY(tenant_id,project_id,run_id,workspace_id) REFERENCES inv.business_runs(tenant_id,project_id,run_id,workspace_id),
 FOREIGN KEY(tenant_id,checkout_id) REFERENCES inv.workspace_checkouts,
 FOREIGN KEY(tenant_id,held_by_subject_id) REFERENCES inv.business_subjects,
 CHECK(released_at IS NULL OR released_at>=acquired_at)
);
CREATE UNIQUE INDEX workspace_edit_lock_held ON public.workspace_edit_locks(tenant_id,workspace_id)
 WHERE released_at IS NULL;
CREATE TABLE public.execution_bindings (
 tenant_id uuid NOT NULL, project_id text NOT NULL, run_id text NOT NULL,
 binding_id uuid NOT NULL, lock_id uuid NOT NULL, resume_id uuid NOT NULL,
 approval_id text NOT NULL, recovery_epoch uuid NOT NULL,
 bound_run_version bigint NOT NULL CHECK(bound_run_version>0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,binding_id), UNIQUE(tenant_id,lock_id),
 UNIQUE(tenant_id,resume_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,project_id,run_id,lock_id) REFERENCES public.workspace_edit_locks(tenant_id,project_id,run_id,lock_id),
 FOREIGN KEY(tenant_id,resume_id) REFERENCES inv.workspace_resumptions,
 FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests
);

DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['business_projects','business_subjects','business_runs'] LOOP
  EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT ON inv.%I TO inv_kernel',tab);
 END LOOP;
 FOREACH tab IN ARRAY ARRAY['workspace_edit_locks','execution_bindings'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_isolation ON public.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
  EXECUTE format('GRANT SELECT,INSERT ON public.%I TO inv_kernel',tab);
  EXECUTE format('GRANT SELECT ON public.%I TO inv_app',tab);
 END LOOP;
 -- Fixed sentinels provide PostgreSQL row-lock privilege without granting
 -- authority to change identity, membership, project status or public Run state.
 FOREACH tab IN ARRAY ARRAY['projects','users','project_members','runs','workspaces','workloads'] LOOP
  EXECUTE format('ALTER TABLE public.%I ADD COLUMN kernel_lock_sentinel boolean NOT NULL DEFAULT true CHECK(kernel_lock_sentinel)',tab);
  EXECUTE format('GRANT UPDATE(kernel_lock_sentinel) ON public.%I TO inv_kernel',tab);
  EXECUTE format('CREATE POLICY kernel_tenant_isolation ON public.%I TO inv_kernel USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
 END LOOP;
END $$;
GRANT SELECT(tenant_id,project_id,status) ON public.projects TO inv_kernel;
GRANT SELECT(tenant_id,user_id,status) ON public.users TO inv_kernel;
GRANT SELECT(tenant_id,project_id,user_id,role_code) ON public.project_members TO inv_kernel;
GRANT SELECT(tenant_id,run_id,workspace_id,workload_id,state) ON public.runs TO inv_kernel;
GRANT SELECT(tenant_id,workspace_id,project_id,status) ON public.workspaces TO inv_kernel;
GRANT SELECT(tenant_id,workload_id,project_id,spec,spec_sha256) ON public.workloads TO inv_kernel;
GRANT UPDATE(lock_sentinel) ON inv.business_projects,inv.business_subjects TO inv_kernel;
GRANT UPDATE(released_at) ON public.workspace_edit_locks TO inv_kernel;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.business_runs
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();
CREATE FUNCTION inv.guard_business_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-'enabled'-'lock_sentinel') IS DISTINCT FROM
  (to_jsonb(OLD)-'enabled'-'lock_sentinel') THEN
  RAISE EXCEPTION 'Business identity mapping is immutable; disable instead' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER identity_guard BEFORE UPDATE OR DELETE ON inv.business_subjects
 FOR EACH ROW EXECUTE FUNCTION inv.guard_business_identity();
CREATE TRIGGER identity_guard BEFORE UPDATE OR DELETE ON inv.business_projects
 FOR EACH ROW EXECUTE FUNCTION inv.guard_business_identity();
REVOKE ALL ON FUNCTION inv.guard_business_identity() FROM PUBLIC;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON public.execution_bindings
 FOR EACH ROW EXECUTE FUNCTION inv.immutable_record();

CREATE FUNCTION inv.guard_business_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM public.workspace_edit_locks l
  JOIN inv.workspace_resumptions s ON s.tenant_id=l.tenant_id AND s.checkout_id=l.checkout_id
  JOIN inv.approval_requests a ON a.tenant_id=s.tenant_id AND a.run_id=s.run_id
  JOIN inv.runs r ON r.tenant_id=s.tenant_id AND r.run_id=s.run_id
  WHERE l.tenant_id=NEW.tenant_id AND l.lock_id=NEW.lock_id AND l.released_at IS NULL
   AND l.project_id=NEW.project_id AND l.run_id=NEW.run_id
   AND s.resume_id=NEW.resume_id AND a.approval_id=NEW.approval_id
   AND a.requester_id=l.held_by_subject_id AND a.status='pending'
   AND s.workspace_id=l.workspace_id AND s.run_id=l.run_id AND s.project_id=l.project_id
   AND l.content_sha256=s.workload->'workspaceResume'->>'inputSha256'
   AND l.input_size_bytes=(s.workload->'workspaceResume'->>'inputSizeBytes')::bigint
   AND a.bound_run_version=NEW.bound_run_version AND r.version=NEW.bound_run_version
   AND r.state='awaiting_approval' AND a.required_approvals=2
   AND s.recovery_epoch=NEW.recovery_epoch AND a.recovery_epoch=NEW.recovery_epoch
   AND l.recovery_epoch=NEW.recovery_epoch
   AND NEW.recovery_epoch=(SELECT epoch FROM inv.control_epoch WHERE singleton)
 ) THEN RAISE EXCEPTION 'Binding requires the actual frozen input and new approval' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER binding_guard BEFORE INSERT ON public.execution_bindings
 FOR EACH ROW EXECUTE FUNCTION inv.guard_business_binding();

CREATE FUNCTION inv.guard_business_unlock() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE b public.execution_bindings; cmd uuid; r inv.runs;
BEGIN
 IF TG_OP='DELETE' OR (to_jsonb(NEW)-'released_at') IS DISTINCT FROM (to_jsonb(OLD)-'released_at')
  OR (OLD.released_at IS NOT NULL AND NEW.released_at IS DISTINCT FROM OLD.released_at)
 THEN RAISE EXCEPTION 'Edit lock history is immutable' USING ERRCODE='23514'; END IF;
 IF NEW.released_at IS NULL OR OLD.released_at IS NOT NULL THEN RETURN NEW; END IF;
 SELECT * INTO b FROM public.execution_bindings WHERE tenant_id=OLD.tenant_id AND lock_id=OLD.lock_id;
 IF NOT FOUND THEN RETURN NEW; END IF;
 SELECT * INTO r FROM inv.runs WHERE tenant_id=b.tenant_id AND run_id=b.run_id FOR SHARE;
 SELECT command_id INTO cmd FROM inv.approval_dispatches WHERE tenant_id=b.tenant_id AND approval_id=b.approval_id;
 IF EXISTS(SELECT 1 FROM inv.resource_leases WHERE tenant_id=b.tenant_id AND run_id=b.run_id AND released_at IS NULL)
  OR (cmd IS NULL AND r.state NOT IN ('cancelled','failed'))
  OR (cmd IS NOT NULL AND (
   NOT EXISTS(SELECT 1 FROM inv.node_stop_receipts WHERE tenant_id=b.tenant_id AND command_id=cmd)
   OR r.state NOT IN ('succeeded','failed','cancelled','recovering')
   OR (r.state='succeeded' AND NOT EXISTS(SELECT 1 FROM inv.result_completions WHERE tenant_id=b.tenant_id AND command_id=cmd))
  )) THEN RAISE EXCEPTION 'Physical completion required before releasing edit lock' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER unlock_guard BEFORE UPDATE OR DELETE ON public.workspace_edit_locks
 FOR EACH ROW EXECUTE FUNCTION inv.guard_business_unlock();
REVOKE ALL ON FUNCTION inv.guard_business_binding(),inv.guard_business_unlock() FROM PUBLIC;

-- A worker may release a completed execution even after its requester's grant
-- is revoked. This grants no new execution authority. Run writers and lease
-- release already hold the Run lock; the edit lock is acquired afterwards.
CREATE FUNCTION inv.reconcile_business_locks() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE public.workspace_edit_locks l SET released_at=clock_timestamp()
 FROM public.execution_bindings b JOIN inv.runs r ON r.tenant_id=b.tenant_id AND r.run_id=b.run_id
 WHERE l.tenant_id=NEW.tenant_id AND l.run_id=NEW.run_id AND l.released_at IS NULL
  AND b.tenant_id=l.tenant_id AND b.lock_id=l.lock_id
  AND NOT EXISTS(SELECT 1 FROM inv.resource_leases WHERE tenant_id=b.tenant_id AND run_id=b.run_id AND released_at IS NULL)
  AND (
   (r.state IN ('failed','cancelled') AND NOT EXISTS(
    SELECT 1 FROM inv.approval_dispatches WHERE tenant_id=b.tenant_id AND approval_id=b.approval_id))
   OR (r.state IN ('succeeded','failed','cancelled','recovering') AND EXISTS(
    SELECT 1 FROM inv.approval_dispatches d JOIN inv.node_stop_receipts s
     ON s.tenant_id=d.tenant_id AND s.command_id=d.command_id
    WHERE d.tenant_id=b.tenant_id AND d.approval_id=b.approval_id
     AND (r.state<>'succeeded' OR EXISTS(
      SELECT 1 FROM inv.result_completions WHERE tenant_id=d.tenant_id AND command_id=d.command_id))))
  );
 RETURN NEW;
END $$;
CREATE TRIGGER business_run_settlement AFTER UPDATE OF state ON inv.runs
 FOR EACH ROW EXECUTE FUNCTION inv.reconcile_business_locks();
CREATE TRIGGER business_lease_settlement AFTER UPDATE OF released_at ON inv.resource_leases
 FOR EACH ROW WHEN (OLD.released_at IS NULL AND NEW.released_at IS NOT NULL)
 EXECUTE FUNCTION inv.reconcile_business_locks();
REVOKE ALL ON FUNCTION inv.reconcile_business_locks() FROM PUBLIC;
