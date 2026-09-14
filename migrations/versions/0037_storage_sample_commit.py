"""Durable sample intents and atomic references to existing evidence/check rows."""

from alembic import op

revision = "0037_storage_sample_commit"
down_revision = "0036_recovery_target_outcome"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE inv.storage_sample_requests (
      tenant_id uuid NOT NULL, request_id uuid NOT NULL, project_id text NOT NULL,
      run_id text NOT NULL, subject_id text NOT NULL, contribution_id char(30) NOT NULL,
      run_version bigint NOT NULL, attempt integer NOT NULL, root_path text NOT NULL,
      sample_limit integer NOT NULL CHECK(sample_limit BETWEEN 1 AND 32),
      challenge jsonb NOT NULL, challenge_sha256 text NOT NULL CHECK(challenge_sha256 ~ '^[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,request_id),
      FOREIGN KEY(tenant_id,project_id,run_id) REFERENCES inv.runs(tenant_id,project_id,run_id),
      FOREIGN KEY(tenant_id,contribution_id) REFERENCES public.storage_contributions(tenant_id,contribution_id),
      UNIQUE(tenant_id,challenge_sha256),
      CHECK(coalesce(challenge#>>'{channel,tenant_id}'=tenant_id::text AND challenge->>'run_id'=run_id
        AND challenge->>'project_id'=project_id AND challenge->>'contribution_id'=contribution_id::text,false))
    );
    CREATE UNIQUE INDEX storage_sample_nonce ON inv.storage_sample_requests(tenant_id,(challenge->>'nonce'));
    CREATE TABLE inv.storage_sample_consumptions (
      tenant_id uuid NOT NULL, request_id uuid NOT NULL,
      response_sha256 text NOT NULL CHECK(response_sha256 ~ '^[0-9a-f]{64}$'),
      evidence_id text NOT NULL, check_id char(30) NOT NULL,
      consumed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(tenant_id,request_id),
      FOREIGN KEY(tenant_id,request_id) REFERENCES inv.storage_sample_requests,
      FOREIGN KEY(tenant_id,evidence_id) REFERENCES inv.evidence,
      FOREIGN KEY(tenant_id,check_id) REFERENCES public.storage_checks(tenant_id,check_id),
      UNIQUE(tenant_id,evidence_id), UNIQUE(tenant_id,check_id)
    );
    DO $$ DECLARE tab text; BEGIN
      FOREACH tab IN ARRAY ARRAY['storage_sample_requests','storage_sample_consumptions'] LOOP
        EXECUTE format('ALTER TABLE inv.%I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE inv.%I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY tenant_isolation ON inv.%I USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
        EXECUTE format('REVOKE ALL ON inv.%I FROM PUBLIC,inv_app,inv_kernel',tab);
        EXECUTE format('GRANT SELECT,INSERT ON inv.%I TO inv_kernel',tab);
        EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON inv.%I FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()',tab);
      END LOOP;
      FOREACH tab IN ARRAY ARRAY['nodes','storage_contributions','data_locations'] LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN storage_lock_sentinel boolean NOT NULL DEFAULT true CHECK(storage_lock_sentinel)',tab);
        EXECUTE format('GRANT UPDATE(storage_lock_sentinel) ON public.%I TO inv_kernel',tab);
        EXECUTE format('CREATE POLICY storage_kernel_tenant ON public.%I TO inv_kernel USING(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid) WITH CHECK(tenant_id=nullif(current_setting(''inv.tenant_id'',true),'''')::uuid)',tab);
      END LOOP;
    END $$;
    GRANT SELECT(tenant_id,node_id,status) ON public.nodes TO inv_kernel;
    GRANT SELECT(tenant_id,contribution_id,node_id,status,registered_by_user_id,normalized_path,version) ON public.storage_contributions TO inv_kernel;
    GRANT SELECT(tenant_id,contribution_id,location_id,version,relative_path,byte_size,checksum_sha256) ON public.data_locations TO inv_kernel;
    GRANT SELECT,INSERT ON public.storage_checks TO inv_kernel;
    CREATE POLICY storage_kernel_tenant ON public.storage_checks TO inv_kernel
      USING(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid)
      WITH CHECK(tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid);
    CREATE TRIGGER immutable_signed_sample BEFORE UPDATE OR DELETE ON public.storage_checks
      FOR EACH ROW WHEN (OLD.detail->>'scope'='node-storage-sample-v1')
      EXECUTE FUNCTION inv.immutable_record();
    """)


def downgrade():
    raise RuntimeError("Signed sample history requires a reviewed forward fix")
