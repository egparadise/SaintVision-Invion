"""Merge published offer work and enforce one host offer across every kernel slice.

Forward only: restore a verified backup or apply a reviewed forward fix.
"""

from alembic import op

revision = "0031_resource_offer_integrity"
down_revision = ("0030_provisioning_integrity", "0030_apply_resource_offer")
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    REVOKE ALL ON FUNCTION public.apply_resource_offer(uuid,char(30),text,bigint) FROM PUBLIC,inv_app;
    CREATE FUNCTION public.apply_capability_offer(
        p_tenant uuid, p_capability char(30), p_actor char(30), p_offered bigint
    ) RETURNS TABLE(applied boolean, reason text, resource_ids text[], capacity bigint)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $fn$
    DECLARE cap public.node_capabilities; node_id_value text; resource record;
      ids text[]; core_kind text; total_capacity numeric; total_leased numeric;
      remaining bigint; held bigint; next_offer bigint;
    BEGIN
      IF p_tenant IS DISTINCT FROM nullif(current_setting('inv.tenant_id',true),'')::uuid THEN
        RETURN QUERY SELECT false,'tenant_scope_mismatch',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      -- The trusted web service supplies its verified principal. Recheck it at
      -- the definer boundary; do not allow the old node/kind-only write path.
      PERFORM u.user_id FROM public.users u WHERE u.tenant_id=p_tenant AND u.user_id=p_actor
        AND u.status='active' FOR SHARE;
      IF NOT FOUND OR NOT public.business_admin_allowed(p_tenant,p_actor,'resources.manage') THEN
        RAISE EXCEPTION 'current resource administrator required' USING ERRCODE='42501';
      END IF;
      SELECT c.node_id INTO node_id_value FROM public.node_capabilities c
        WHERE c.tenant_id=p_tenant AND c.capability_id=p_capability;
      IF NOT FOUND THEN
        RETURN QUERY SELECT false,'capability_not_found',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      PERFORM n.node_id FROM public.nodes n WHERE n.tenant_id=p_tenant AND n.node_id=node_id_value FOR UPDATE;
      SELECT c.* INTO cap FROM public.node_capabilities c
        WHERE c.tenant_id=p_tenant AND c.capability_id=p_capability FOR UPDATE;
      IF p_offered IS NULL OR p_offered<0 OR p_offered>9007199254740991 OR p_offered>cap.total_quantity THEN
        RETURN QUERY SELECT false,'invalid_quantity',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      -- A GPU capability identifies a device; inv.resources has no device key.
      -- Recording intent is allowed, silently applying it to a different GPU is not.
      IF cap.kind='gpu' THEN
        RETURN QUERY SELECT false,'device_mapping_required',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      core_kind := CASE cap.kind WHEN 'cpu' THEN 'cpu' WHEN 'ram' THEN 'memory' WHEN 'disk' THEN 'storage' END;
      IF core_kind IS NULL OR cap.unit IS DISTINCT FROM (CASE cap.kind WHEN 'cpu' THEN 'millicores' ELSE 'bytes' END) THEN
        RETURN QUERY SELECT false,'unsupported_units',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      -- Same Node -> all sorted Resource locks used by reservation and offer writers.
      PERFORM n.node_id FROM inv.nodes n WHERE n.tenant_id=p_tenant AND n.node_id=node_id_value FOR UPDATE;
      IF NOT FOUND THEN
        RETURN QUERY SELECT false,'resource_not_registered',ARRAY[]::text[],NULL::bigint; RETURN;
      END IF;
      ids := ARRAY[]::text[];
      FOR resource IN SELECT r.resource_id FROM inv.resources r
        WHERE r.tenant_id=p_tenant AND r.node_id=node_id_value AND r.kind=core_kind
        ORDER BY r.resource_id FOR UPDATE LOOP
        ids := array_append(ids,resource.resource_id);
      END LOOP;
      IF cardinality(ids)=0 THEN
        RETURN QUERY SELECT false,'resource_not_registered',ids,NULL::bigint; RETURN;
      END IF;
      -- Separate statements after waiting: see the latest committed reservations,
      -- including expired/old-epoch leases without confirmed physical release.
      SELECT sum(r.capacity) INTO total_capacity FROM inv.resources r
        WHERE r.tenant_id=p_tenant AND r.resource_id=ANY(ids);
      SELECT coalesce(sum(l.amount),0) INTO total_leased FROM inv.resource_leases l
        WHERE l.tenant_id=p_tenant AND l.resource_id=ANY(ids) AND l.released_at IS NULL;
      IF p_offered>total_capacity THEN
        RETURN QUERY SELECT false,'exceeds_kernel_capacity',ids,least(total_capacity,9007199254740991)::bigint; RETURN;
      END IF;
      IF p_offered<total_leased THEN
        RETURN QUERY SELECT false,'below_unreleased_leases',ids,least(total_capacity,9007199254740991)::bigint; RETURN;
      END IF;
      IF EXISTS(SELECT 1 FROM inv.resources r WHERE r.tenant_id=p_tenant AND r.resource_id=ANY(ids)
        AND r.capacity < (SELECT coalesce(sum(l.amount),0) FROM inv.resource_leases l
          WHERE l.tenant_id=r.tenant_id AND l.resource_id=r.resource_id AND l.released_at IS NULL)) THEN
        RETURN QUERY SELECT false,'leased_capacity_inconsistent',ids,least(total_capacity,9007199254740991)::bigint; RETURN;
      END IF;
      remaining := p_offered-total_leased;
      FOR resource IN SELECT r.resource_id,r.capacity FROM inv.resources r
        WHERE r.tenant_id=p_tenant AND r.resource_id=ANY(ids) ORDER BY r.resource_id LOOP
        SELECT coalesce(sum(l.amount),0) INTO held FROM inv.resource_leases l
          WHERE l.tenant_id=p_tenant AND l.resource_id=resource.resource_id AND l.released_at IS NULL;
        next_offer := held+least(remaining,resource.capacity-held);
        UPDATE inv.resources r SET offered=next_offer
          WHERE r.tenant_id=p_tenant AND r.resource_id=resource.resource_id;
        remaining := remaining-(next_offer-held);
      END LOOP;
      RETURN QUERY SELECT true,NULL::text,ids,least(total_capacity,9007199254740991)::bigint;
    END $fn$;
    REVOKE ALL ON FUNCTION public.apply_capability_offer(uuid,char(30),char(30),bigint) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.apply_capability_offer(uuid,char(30),char(30),bigint) TO inv_app;
    """)


def downgrade():
    raise RuntimeError(
        "Offer authority and merged history are forward-only; restore a verified backup"
    )
