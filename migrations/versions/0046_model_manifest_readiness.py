"""Minimum tenant-bound replica readiness projection for the kernel manifest API."""

from alembic import op


revision = "0046_model_manifest_readiness"
down_revision = "0045_discovery_machine_cred"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION public.model_location_readiness(p_location_ids text[])
    RETURNS TABLE(location_id text,current_version bigint,ready_nodes text[])
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $fn$
      SELECT l.location_id::text,l.version::bigint,
        coalesce(
          array_agg(DISTINCT r.node_id::text ORDER BY r.node_id::text)
            FILTER (WHERE r.state='ready'),
          ARRAY[]::text[]
        ) AS ready_nodes
      FROM public.data_locations l
      LEFT JOIN public.data_replicas r
        ON r.tenant_id=l.tenant_id AND r.location_id=l.location_id
      WHERE l.tenant_id=nullif(current_setting('inv.tenant_id',true),'')::uuid
        AND l.location_id::text=ANY(p_location_ids)
      GROUP BY l.location_id,l.version
      ORDER BY l.location_id::text
    $fn$;
    REVOKE ALL ON FUNCTION public.model_location_readiness(text[]) FROM PUBLIC,inv_app;
    GRANT EXECUTE ON FUNCTION public.model_location_readiness(text[]) TO inv_kernel;
    """)


def downgrade():
    raise RuntimeError("Model manifest readiness projection requires a reviewed forward fix")

