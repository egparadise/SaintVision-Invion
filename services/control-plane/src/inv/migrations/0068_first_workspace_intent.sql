-- Two narrow append-only bridges. No runtime role may assume this function owner.
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='inv_first_workspace_writer') THEN
  CREATE ROLE inv_first_workspace_writer NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='inv_first_workspace_writer'
           AND (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolinherit))
    OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='inv_first_workspace_writer'::regrole) THEN
  RAISE EXCEPTION 'Dedicated first Workspace writer role is unsafe';
 END IF;
END $$;
GRANT USAGE ON SCHEMA inv,public TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,project_id,subject_id,enabled,can_request) ON inv.project_grants TO inv_first_workspace_writer;
GRANT UPDATE(lock_sentinel) ON inv.project_grants TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,project_id,enabled) ON inv.business_projects TO inv_first_workspace_writer;
GRANT UPDATE(lock_sentinel) ON inv.business_projects TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,subject_id,user_id,enabled) ON inv.business_subjects TO inv_first_workspace_writer;
GRANT UPDATE(lock_sentinel) ON inv.business_subjects TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,project_id,status) ON public.projects TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,user_id,status) ON public.users TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,project_id,user_id,role_code) ON public.project_members TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,workspace_id,project_id,status,version,node_id) ON public.workspaces TO inv_first_workspace_writer;
GRANT SELECT(tenant_id,project_id,workload_id,spec,spec_sha256,version) ON public.workloads TO inv_first_workspace_writer;
GRANT UPDATE(kernel_lock_sentinel) ON public.projects,public.users,public.project_members,public.workspaces,public.workloads TO inv_first_workspace_writer;
GRANT INSERT(tenant_id,project_id,workload_id,kind,objective,spec,spec_sha256,contract_version,created_by_user_id,version) ON public.workloads TO inv_first_workspace_writer;
GRANT INSERT(tenant_id,run_id,workspace_id,workload_id,requested_by_user_id,state,attempt_count,retry_budget,version) ON public.runs TO inv_first_workspace_writer;
GRANT INSERT(tenant_id,project_id,run_id,state,version,attempt) ON inv.runs TO inv_first_workspace_writer;
GRANT INSERT(tenant_id,project_id,run_id,workspace_id) ON inv.business_runs TO inv_first_workspace_writer;
GRANT SELECT(version,node_id) ON public.workspaces TO inv_kernel;
GRANT SELECT(version) ON public.workloads TO inv_kernel;
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['projects','users','project_members','workspaces','workloads','runs'] LOOP
  EXECUTE format('CREATE POLICY first_workspace_writer_tenant ON public.%I TO inv_first_workspace_writer USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
 END LOOP;
END $$;

CREATE FUNCTION inv.append_first_workspace_intent(p_project text,p_workspace text,p_spec jsonb,p_sha text,p_canonical text,p_objective text,p_workspace_version bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$
DECLARE
 v_tenant uuid := nullif(current_setting('inv.tenant_id',true),'')::uuid;
 v_subject text := nullif(current_setting('inv.first_workspace_subject',true),'');
 v_user text; v_status text; v_version bigint; v_resources jsonb; v_arg jsonb;
BEGIN
 IF v_tenant IS NULL OR v_subject IS NULL OR v_subject !~ '^oidc:[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'Verified service context required' USING ERRCODE='42501'; END IF;
 IF NOT coalesce((SELECT enabled AND can_request FROM inv.project_grants WHERE tenant_id=v_tenant AND project_id=p_project AND subject_id=v_subject FOR SHARE),false)
 OR NOT coalesce((SELECT enabled FROM inv.business_projects WHERE tenant_id=v_tenant AND project_id=p_project FOR SHARE),false)
 OR NOT coalesce((SELECT status='active' FROM public.projects WHERE tenant_id=v_tenant AND project_id=p_project FOR SHARE),false) THEN
  RAISE EXCEPTION 'Current project permission required' USING ERRCODE='42501'; END IF;
 SELECT user_id INTO v_user FROM inv.business_subjects WHERE tenant_id=v_tenant AND subject_id=v_subject AND enabled FOR SHARE;
 IF v_user IS NULL OR NOT coalesce((SELECT status='active' FROM public.users WHERE tenant_id=v_tenant AND user_id=v_user FOR SHARE),false)
 OR NOT coalesce((SELECT role_code IN ('owner','maintainer','operator') FROM public.project_members WHERE tenant_id=v_tenant AND project_id=p_project AND user_id=v_user FOR SHARE),false) THEN
  RAISE EXCEPTION 'Current active requester required' USING ERRCODE='42501'; END IF;
 SELECT status,version INTO v_status,v_version FROM public.workspaces WHERE tenant_id=v_tenant AND project_id=p_project AND workspace_id=p_workspace FOR SHARE;
 IF v_status IS DISTINCT FROM 'ready' OR v_version IS DISTINCT FROM p_workspace_version THEN
  RAISE EXCEPTION 'Current selected ready Workspace required' USING ERRCODE='42501'; END IF;
 IF p_sha !~ '^[a-f0-9]{64}$' OR p_sha IS NULL OR p_canonical IS NULL OR octet_length(p_canonical)>65536 OR
    p_canonical::jsonb IS DISTINCT FROM p_spec OR encode(sha256(convert_to(p_canonical,'UTF8')),'hex') IS DISTINCT FROM p_sha
    OR length(p_objective) NOT BETWEEN 1 AND 1000 OR p_objective IS NULL
    OR jsonb_typeof(p_spec) IS DISTINCT FROM 'object'
    OR NOT (p_spec ?& ARRAY['apiVersion','kind','workloadId','tenantId','projectId','workspaceId','resources','imageDigest','command','timeoutSeconds','targetNodeId'])
    OR (p_spec-ARRAY['apiVersion','kind','workloadId','tenantId','projectId','workspaceId','resources','imageDigest','command','timeoutSeconds','targetNodeId']) <> '{}'::jsonb
    OR p_spec->>'apiVersion' IS DISTINCT FROM 'inv.saintvision.ai/v1alpha1'
    OR p_spec->>'kind' IS DISTINCT FROM 'Workload' OR p_spec->>'tenantId' IS DISTINCT FROM v_tenant::text
    OR p_spec->>'projectId' IS DISTINCT FROM p_project OR p_spec->>'workspaceId' IS DISTINCT FROM p_workspace
    OR coalesce(p_spec->>'workloadId','') !~ '^wld_[0-9A-HJKMNP-TV-Z]{26}$'
    OR coalesce(p_spec->>'targetNodeId','') !~ '^nod_[0-9A-HJKMNP-TV-Z]{26}$'
    OR coalesce(p_spec->>'imageDigest','') !~ '^sha256:[a-f0-9]{64}$'
    OR jsonb_typeof(p_spec->'command') IS DISTINCT FROM 'array'
    OR jsonb_typeof(p_spec->'timeoutSeconds') IS DISTINCT FROM 'number'
    OR coalesce(p_spec->>'timeoutSeconds','') !~ '^[1-9][0-9]*$' THEN
  RAISE EXCEPTION 'Closed canonical CPU metadata required' USING ERRCODE='42501'; END IF;
 IF (p_spec->>'timeoutSeconds')::numeric > 30 OR jsonb_array_length(p_spec->'command') NOT BETWEEN 1 AND 64 THEN
  RAISE EXCEPTION 'Bounded CPU command required' USING ERRCODE='42501'; END IF;
 FOR v_arg IN SELECT * FROM jsonb_array_elements(p_spec->'command') LOOP
  IF jsonb_typeof(v_arg) <> 'string' OR length(v_arg#>>'{}') NOT BETWEEN 1 AND 4096 THEN
   RAISE EXCEPTION 'Bounded command argument required' USING ERRCODE='42501'; END IF;
 END LOOP;
 v_resources := p_spec->'resources';
 IF jsonb_typeof(v_resources) IS DISTINCT FROM 'object' OR
 NOT(v_resources ?& ARRAY['cpuMillis','memoryBytes','gpuCount','minVramBytes']) OR
 (v_resources-ARRAY['cpuMillis','memoryBytes','gpuCount','minVramBytes']) <> '{}'::jsonb OR
 jsonb_typeof(v_resources->'cpuMillis') IS DISTINCT FROM 'number' OR jsonb_typeof(v_resources->'memoryBytes') IS DISTINCT FROM 'number' OR
 coalesce(v_resources->>'cpuMillis','') !~ '^[1-9][0-9]*$' OR coalesce(v_resources->>'memoryBytes','') !~ '^[1-9][0-9]*$' OR
 v_resources->'gpuCount' IS DISTINCT FROM '0'::jsonb OR v_resources->'minVramBytes' IS DISTINCT FROM '0'::jsonb THEN
  RAISE EXCEPTION 'Bounded CPU resources required' USING ERRCODE='42501'; END IF;
 IF (v_resources->>'cpuMillis')::numeric > 500 OR (v_resources->>'memoryBytes')::numeric NOT BETWEEN 8388608 AND 67108864 THEN
  RAISE EXCEPTION 'CPU resource bounds exceeded' USING ERRCODE='42501'; END IF;
 IF NOT coalesce((SELECT enabled FROM inv.project_nodes WHERE tenant_id=v_tenant AND project_id=p_project AND node_id=p_spec->>'targetNodeId' FOR SHARE),false)
 OR EXISTS(SELECT 1 FROM public.workspaces WHERE tenant_id=v_tenant AND workspace_id=p_workspace AND node_id IS NOT NULL AND node_id<>p_spec->>'targetNodeId') THEN
  RAISE EXCEPTION 'Selected target membership differs' USING ERRCODE='42501'; END IF;
 INSERT INTO public.workloads(tenant_id,project_id,workload_id,kind,objective,spec,spec_sha256,contract_version,created_by_user_id,version)
 VALUES(v_tenant,p_project,p_spec->>'workloadId','batch',p_objective,p_spec,p_sha,'1.0.0',v_user,1);
END $$;

CREATE FUNCTION inv.append_first_workspace_run(p_project text,p_workspace text,p_workload text,p_run text,p_workspace_version bigint,p_workload_version bigint,p_sha text,p_canonical text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$
DECLARE
 v_tenant uuid := nullif(current_setting('inv.tenant_id',true),'')::uuid;
 v_subject text := nullif(current_setting('inv.first_workspace_subject',true),'');
 v_user text; v_status text; v_workspace_version bigint; v_spec jsonb; v_sha text; v_workload_version bigint;
BEGIN
 IF v_tenant IS NULL OR v_subject IS NULL OR v_subject !~ '^oidc:[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'Verified service context required' USING ERRCODE='42501'; END IF;
 IF NOT coalesce((SELECT enabled AND can_request FROM inv.project_grants WHERE tenant_id=v_tenant AND project_id=p_project AND subject_id=v_subject FOR SHARE),false)
 OR NOT coalesce((SELECT enabled FROM inv.business_projects WHERE tenant_id=v_tenant AND project_id=p_project FOR SHARE),false)
 OR NOT coalesce((SELECT status='active' FROM public.projects WHERE tenant_id=v_tenant AND project_id=p_project FOR SHARE),false) THEN
  RAISE EXCEPTION 'Current project permission required' USING ERRCODE='42501'; END IF;
 SELECT user_id INTO v_user FROM inv.business_subjects WHERE tenant_id=v_tenant AND subject_id=v_subject AND enabled FOR SHARE;
 IF v_user IS NULL OR NOT coalesce((SELECT status='active' FROM public.users WHERE tenant_id=v_tenant AND user_id=v_user FOR SHARE),false)
 OR NOT coalesce((SELECT role_code IN ('owner','maintainer','operator') FROM public.project_members WHERE tenant_id=v_tenant AND project_id=p_project AND user_id=v_user FOR SHARE),false) THEN
  RAISE EXCEPTION 'Current active requester required' USING ERRCODE='42501'; END IF;
 SELECT status,version INTO v_status,v_workspace_version FROM public.workspaces WHERE tenant_id=v_tenant AND project_id=p_project AND workspace_id=p_workspace FOR SHARE;
 SELECT spec,spec_sha256,version INTO v_spec,v_sha,v_workload_version FROM public.workloads WHERE tenant_id=v_tenant AND project_id=p_project AND workload_id=p_workload FOR SHARE;
 IF v_status IS DISTINCT FROM 'ready' OR v_workspace_version IS DISTINCT FROM p_workspace_version OR
    v_workload_version IS DISTINCT FROM p_workload_version OR v_spec->>'workloadId' IS DISTINCT FROM p_workload OR
    v_spec->>'tenantId' IS DISTINCT FROM v_tenant::text OR v_spec->>'projectId' IS DISTINCT FROM p_project OR
    v_spec->>'workspaceId' IS DISTINCT FROM p_workspace OR v_sha IS DISTINCT FROM p_sha OR
    p_canonical IS NULL OR octet_length(p_canonical)>65536 OR p_canonical::jsonb IS DISTINCT FROM v_spec OR encode(sha256(convert_to(p_canonical,'UTF8')),'hex') IS DISTINCT FROM v_sha OR
    p_run IS NULL OR p_run !~ '^run_[0-9A-HJKMNP-TV-Z]{26}$' THEN
  RAISE EXCEPTION 'Current selected intent required' USING ERRCODE='42501'; END IF;
 IF v_spec ? 'targetNodeId' AND (
 NOT coalesce((SELECT enabled FROM inv.project_nodes WHERE tenant_id=v_tenant AND project_id=p_project AND node_id=v_spec->>'targetNodeId' FOR SHARE),false)
 OR EXISTS(SELECT 1 FROM public.workspaces WHERE tenant_id=v_tenant AND workspace_id=p_workspace AND node_id IS NOT NULL AND node_id<>v_spec->>'targetNodeId')) THEN
  RAISE EXCEPTION 'Current target membership differs' USING ERRCODE='42501'; END IF;
 INSERT INTO inv.runs(tenant_id,project_id,run_id,state,version,attempt) VALUES(v_tenant,p_project,p_run,'draft',1,0);
 INSERT INTO public.runs(tenant_id,run_id,workspace_id,workload_id,requested_by_user_id,state,attempt_count,retry_budget,version)
 VALUES(v_tenant,p_run,p_workspace,p_workload,v_user,'draft',0,2,1);
 INSERT INTO inv.business_runs(tenant_id,project_id,run_id,workspace_id) VALUES(v_tenant,p_project,p_run,p_workspace);
END $$;

GRANT SELECT(tenant_id,project_id,node_id,enabled) ON inv.project_nodes TO inv_first_workspace_writer;
GRANT UPDATE(lock_sentinel) ON inv.project_nodes TO inv_first_workspace_writer;
-- ALTER FUNCTION OWNER requires CREATE temporarily; no runtime receives it.
GRANT CREATE ON SCHEMA inv TO inv_first_workspace_writer;
ALTER FUNCTION inv.append_first_workspace_intent(text,text,jsonb,text,text,text,bigint) OWNER TO inv_first_workspace_writer;
ALTER FUNCTION inv.append_first_workspace_run(text,text,text,text,bigint,bigint,text,text) OWNER TO inv_first_workspace_writer;
REVOKE CREATE ON SCHEMA inv FROM inv_first_workspace_writer;
REVOKE ALL ON FUNCTION inv.append_first_workspace_intent(text,text,jsonb,text,text,text,bigint),inv.append_first_workspace_run(text,text,text,text,bigint,bigint,text,text) FROM PUBLIC,inv_app;
GRANT EXECUTE ON FUNCTION inv.append_first_workspace_intent(text,text,jsonb,text,text,text,bigint),inv.append_first_workspace_run(text,text,text,text,bigint,bigint,text,text) TO inv_kernel;
