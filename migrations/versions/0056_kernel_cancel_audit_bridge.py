"""Atomic kernel cancellation projection into the business Run and audit log.

The public cancel route remains kernel-owned.  This revision gives ``inv_kernel``
one tenant-bound SECURITY DEFINER primitive rather than table write grants.  The
primitive accepts only authenticated-subject and correlation identifiers, then
re-derives the active business user and verifies that the same transaction has
already moved the canonical ``inv.runs`` row to ``cancelled``.

Revision ID: 0056_kernel_cancel_audit_bridge
Revises: 0055_adapter_conformance_records
"""

from alembic import op


revision = "0056_kernel_cancel_audit_bridge"
down_revision = "0055_adapter_conformance_records"
branch_labels = None
depends_on = None

OWNER = "inv_cancel_bridge_owner"
FUNCTION = "public.record_kernel_run_cancel"
SIGNATURE = f"{FUNCTION}(text,text,text,text,text)"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
          CREATE ROLE {OWNER} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOBYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        ALTER ROLE {OWNER} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
          NOINHERIT NOBYPASSRLS;
        DO $$
        DECLARE members text;
        BEGIN
          SELECT pg_catalog.string_agg(member_role.rolname, ', ' ORDER BY member_role.rolname)
            INTO members
            FROM pg_catalog.pg_auth_members m
            JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = m.roleid
            JOIN pg_catalog.pg_roles member_role ON member_role.oid = m.member
           WHERE granted_role.rolname = '{OWNER}';
          IF members IS NOT NULL THEN
            RAISE EXCEPTION
              '{OWNER} already has members (%); refusing cancellation-bridge ownership',
              members;
          END IF;
        END $$;

        GRANT USAGE ON SCHEMA inv, public TO {OWNER};
        -- CREATE is needed only while transferring function ownership and is
        -- revoked before the migration transaction commits.
        GRANT CREATE ON SCHEMA public TO {OWNER};
        GRANT SELECT (tenant_id,project_id,run_id,state) ON inv.runs TO {OWNER};
        GRANT SELECT (tenant_id,project_id,run_id,workspace_id)
          ON inv.business_runs TO {OWNER};
        GRANT SELECT (tenant_id,project_id,enabled)
          ON inv.business_projects TO {OWNER};
        GRANT SELECT (tenant_id,subject_id,user_id,enabled)
          ON inv.business_subjects TO {OWNER};
        GRANT UPDATE (lock_sentinel)
          ON inv.business_projects, inv.business_subjects TO {OWNER};
        GRANT SELECT (tenant_id,project_id,status) ON public.projects TO {OWNER};
        GRANT SELECT (tenant_id,user_id,status) ON public.users TO {OWNER};
        GRANT SELECT (tenant_id,project_id,user_id,role_code)
          ON public.project_members TO {OWNER};
        GRANT UPDATE (kernel_lock_sentinel)
          ON public.projects, public.users, public.project_members TO {OWNER};
        GRANT SELECT (tenant_id,run_id,workspace_id,workload_id,state,version)
          ON public.runs TO {OWNER};
        GRANT UPDATE (state,termination_reason,ended_at,version)
          ON public.runs TO {OWNER};
        GRANT SELECT (tenant_id,workspace_id,project_id)
          ON public.workspaces TO {OWNER};
        GRANT SELECT (tenant_id,workload_id,project_id)
          ON public.workloads TO {OWNER};
        GRANT INSERT (event_id,occurred_at,tenant_id,actor_type,actor_id,action,
          outcome,reason_code,trace_id,target_type,target_id,detail)
          ON public.audit_events TO {OWNER};

        CREATE POLICY cancel_bridge_projects_read ON public.projects
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_users_read ON public.users
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_project_members_read ON public.project_members
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_workspaces_read ON public.workspaces
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_workloads_read ON public.workloads
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_runs_read ON public.runs
          FOR SELECT TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_runs_update ON public.runs
          FOR UPDATE TO {OWNER}
          USING (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid)
          WITH CHECK (tenant_id = NULLIF(
            pg_catalog.current_setting('inv.tenant_id',true),'')::uuid);
        CREATE POLICY cancel_bridge_audit_append ON public.audit_events
          FOR INSERT TO {OWNER}
          WITH CHECK (
            tenant_id = NULLIF(
              pg_catalog.current_setting('inv.tenant_id',true),'')::uuid
            AND actor_type = 'user'
            AND action = 'run.cancel.requested'
            AND outcome = 'allow'
            AND target_type = 'run'
            AND detail = '{{"reason":"cancelled_by_user"}}'::jsonb
          );

        CREATE FUNCTION {FUNCTION}(
          p_subject_id text,
          p_project_id text,
          p_run_id text,
          p_event_id text,
          p_trace_id text
        ) RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $fn$
        DECLARE
          v_tenant uuid;
          v_kernel_state text;
          v_kernel_project text;
          v_workspace_id character(30);
          v_public_state text;
          v_user_id character(30);
        BEGIN
          v_tenant := NULLIF(
            pg_catalog.current_setting('inv.tenant_id', true), '')::uuid;
          IF v_tenant IS NULL THEN
            RAISE EXCEPTION 'tenant scope is required' USING ERRCODE = '42501';
          END IF;
          IF p_event_id IS NULL
             OR p_event_id !~ '^aud_[0-9A-HJKMNP-TV-Z]{{26}}$'
             OR p_trace_id IS NULL
             OR p_trace_id !~ '^[0-9a-f]{{32}}$' THEN
            RAISE EXCEPTION 'canonical event and trace identifiers are required'
              USING ERRCODE = '22023';
          END IF;

          SELECT r.state, r.project_id
            INTO v_kernel_state, v_kernel_project
            FROM inv.runs r
           WHERE r.tenant_id = v_tenant AND r.run_id = p_run_id;
          IF v_kernel_state IS DISTINCT FROM 'cancelled'
             OR v_kernel_project IS DISTINCT FROM p_project_id THEN
            RAISE EXCEPTION 'kernel cancellation authority is absent'
              USING ERRCODE = '23514';
          END IF;

          SELECT br.workspace_id
            INTO v_workspace_id
            FROM inv.business_runs br
           WHERE br.tenant_id = v_tenant
             AND br.project_id = p_project_id
             AND br.run_id = p_run_id;
          IF v_workspace_id IS NULL THEN
            RAISE EXCEPTION 'business run mapping is absent' USING ERRCODE = '23514';
          END IF;

          SELECT s.user_id
            INTO v_user_id
            FROM inv.business_projects bp
            JOIN inv.business_subjects s ON s.tenant_id = bp.tenant_id
            JOIN public.projects p ON p.tenant_id = bp.tenant_id
              AND p.project_id = bp.project_id
            JOIN public.users u ON u.tenant_id = s.tenant_id
              AND u.user_id = s.user_id
            JOIN public.project_members pm ON pm.tenant_id = bp.tenant_id
              AND pm.project_id = bp.project_id AND pm.user_id = s.user_id
           WHERE bp.tenant_id = v_tenant
             AND bp.project_id = p_project_id
             AND bp.enabled
             AND s.subject_id = p_subject_id
             AND s.enabled
             AND p.status = 'active'
             AND u.status = 'active'
             AND pm.role_code IN ('owner','maintainer','operator')
           FOR SHARE OF bp, s, p, u, pm;
          IF v_user_id IS NULL THEN
            RAISE EXCEPTION 'active business cancellation authority is absent'
              USING ERRCODE = '42501';
          END IF;

          SELECT r.state
            INTO v_public_state
            FROM public.runs r
            JOIN public.workspaces w ON w.tenant_id = r.tenant_id
              AND w.workspace_id = r.workspace_id
            JOIN public.workloads l ON l.tenant_id = r.tenant_id
              AND l.workload_id = r.workload_id
           WHERE r.tenant_id = v_tenant
             AND r.run_id = p_run_id
             AND r.workspace_id = v_workspace_id
             AND w.project_id = p_project_id
             AND l.project_id = p_project_id
           FOR UPDATE OF r;
          IF v_public_state IS NULL THEN
            RAISE EXCEPTION 'business run identity differs' USING ERRCODE = '23514';
          END IF;
          IF v_public_state = 'cancelled' THEN
            RETURN false;
          END IF;
          IF v_public_state IN ('succeeded','failed') THEN
            RAISE EXCEPTION 'business run is already terminal' USING ERRCODE = '23514';
          END IF;

          UPDATE public.runs
             SET state = 'cancelled',
                 termination_reason = 'cancelled_by_user',
                 ended_at = pg_catalog.clock_timestamp(),
                 version = version + 1
           WHERE tenant_id = v_tenant AND run_id = p_run_id;

          INSERT INTO public.audit_events
            (event_id, occurred_at, tenant_id, actor_type, actor_id, action,
             outcome, reason_code, trace_id, target_type, target_id, detail)
          VALUES
            (p_event_id, pg_catalog.clock_timestamp(), v_tenant, 'user', v_user_id,
             'run.cancel.requested', 'allow', NULL, p_trace_id, 'run', p_run_id,
             pg_catalog.jsonb_build_object('reason', 'cancelled_by_user'));
          RETURN true;
        END
        $fn$;

        GRANT {OWNER} TO CURRENT_USER;
        ALTER FUNCTION {SIGNATURE} OWNER TO {OWNER};
        REVOKE CREATE ON SCHEMA public FROM {OWNER};
        REVOKE {OWNER} FROM CURRENT_USER;
        REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC, inv_app;
        GRANT EXECUTE ON FUNCTION {SIGNATURE} TO inv_kernel;
        """
    )


def downgrade() -> None:
    """Remove the bridge while retaining its cluster-shared NOLOGIN owner role."""

    op.execute(
        f"""
        DROP FUNCTION IF EXISTS {SIGNATURE};
        DROP POLICY IF EXISTS cancel_bridge_audit_append ON public.audit_events;
        DROP POLICY IF EXISTS cancel_bridge_runs_update ON public.runs;
        DROP POLICY IF EXISTS cancel_bridge_runs_read ON public.runs;
        DROP POLICY IF EXISTS cancel_bridge_workloads_read ON public.workloads;
        DROP POLICY IF EXISTS cancel_bridge_workspaces_read ON public.workspaces;
        DROP POLICY IF EXISTS cancel_bridge_project_members_read ON public.project_members;
        DROP POLICY IF EXISTS cancel_bridge_users_read ON public.users;
        DROP POLICY IF EXISTS cancel_bridge_projects_read ON public.projects;
        REVOKE INSERT (event_id,occurred_at,tenant_id,actor_type,actor_id,action,
          outcome,reason_code,trace_id,target_type,target_id,detail)
          ON public.audit_events FROM {OWNER};
        REVOKE SELECT (tenant_id,run_id,workspace_id,workload_id,state,version),
          UPDATE (state,termination_reason,ended_at,version)
          ON public.runs FROM {OWNER};
        REVOKE SELECT (tenant_id,workload_id,project_id)
          ON public.workloads FROM {OWNER};
        REVOKE SELECT (tenant_id,workspace_id,project_id)
          ON public.workspaces FROM {OWNER};
        REVOKE SELECT (tenant_id,project_id,user_id,role_code)
          ON public.project_members FROM {OWNER};
        REVOKE UPDATE (kernel_lock_sentinel)
          ON public.projects, public.users, public.project_members FROM {OWNER};
        REVOKE SELECT (tenant_id,user_id,status) ON public.users FROM {OWNER};
        REVOKE SELECT (tenant_id,project_id,status) ON public.projects FROM {OWNER};
        REVOKE SELECT (tenant_id,subject_id,user_id,enabled)
          ON inv.business_subjects FROM {OWNER};
        REVOKE SELECT (tenant_id,project_id,enabled)
          ON inv.business_projects FROM {OWNER};
        REVOKE UPDATE (lock_sentinel)
          ON inv.business_projects, inv.business_subjects FROM {OWNER};
        REVOKE SELECT (tenant_id,project_id,run_id,workspace_id)
          ON inv.business_runs FROM {OWNER};
        REVOKE SELECT (tenant_id,project_id,run_id,state) ON inv.runs FROM {OWNER};
        REVOKE USAGE ON SCHEMA public, inv FROM {OWNER};
        REVOKE {OWNER} FROM inv_kernel, inv_app;
        """
    )
