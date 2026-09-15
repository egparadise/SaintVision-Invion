"""Make an offer set on the screen change what the kernel can reserve.

Revision ID: 0030_apply_resource_offer
Revises: 0029_run_outputs
Create Date: 2026-09-11

``public.resource_offers`` records how much of a machine its owner allows the
platform to use. ``inv.resources.offered`` is what the execution kernel actually
checks before granting a lease. **Nothing connected them.** An operator lowering
an offer on a settings screen changed a number no scheduler reads, and the
machine kept accepting the work the owner had just said it should stop taking.

This applies the business-side offer to the kernel's column, under the kernel's
own rules rather than a second set:

* ``offered <= capacity`` — a node cannot offer more than the kernel measured it
  to have. The business side already refuses this against its own capability
  row, and the kernel refuses it again against what it observed, which are
  different facts and should both hold.
* ``offered >= the sum of unreleased leases`` — **the kernel's rule, and it is
  stricter than the one the business side documents.** Lowering an offer below
  what is currently leased would leave the kernel committed to more than the
  owner now permits. Refusing is better than either breaking the promise or
  silently over-committing.

``inv_app`` cannot write ``inv.resources`` and must not: the offered column
decides what can be spent. This is one function that applies one number to one
resource the caller already names, bound to the session's tenant — a definer
function bypasses row level security, so a caller-supplied tenant id is not a
scope. Revision 0027 had to correct that in 0024 and the same mistake is easy to
repeat on a write path, where it would be worse.

The kind vocabularies differ (``ram``/``disk`` here, ``memory``/``storage``
there) and the translation lives in this one function rather than in application
code that could disagree with it.
"""

from __future__ import annotations

from alembic import op

revision = "0030_apply_resource_offer"
down_revision = "0029_run_outputs"
branch_labels = None
depends_on = None

APP_ROLE = "inv_app"
FUNCTION = "public.apply_resource_offer"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FUNCTION}(
            p_tenant_id uuid, p_node_id char(30), p_kind text, p_offered bigint
        ) RETURNS TABLE (applied boolean, reason text, kernel_resource_id text,
                         kernel_capacity bigint)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $fn$
        DECLARE
            core_kind text;
            row_resource record;
            leased bigint;
        BEGIN
            -- A definer function bypasses RLS, so the tenant the caller names
            -- is only trusted when it is the one the session is scoped to.
            IF p_tenant_id IS DISTINCT FROM nullif(
                pg_catalog.current_setting('inv.tenant_id', true), ''
            )::uuid THEN
                RETURN QUERY SELECT false, 'tenant scope mismatch', NULL::text, NULL::bigint;
                RETURN;
            END IF;
            IF p_offered < 0 THEN
                RETURN QUERY SELECT false, 'a negative offer is not a quantity',
                                    NULL::text, NULL::bigint;
                RETURN;
            END IF;

            core_kind := CASE p_kind
                WHEN 'cpu' THEN 'cpu' WHEN 'gpu' THEN 'gpu'
                WHEN 'ram' THEN 'memory' WHEN 'disk' THEN 'storage' END;
            IF core_kind IS NULL THEN
                RETURN QUERY SELECT false, 'unknown resource kind', NULL::text, NULL::bigint;
                RETURN;
            END IF;

            SELECT r.resource_id, r.capacity INTO row_resource
            FROM inv.resources r
            WHERE r.tenant_id = p_tenant_id AND r.node_id = p_node_id
              AND r.kind = core_kind
            ORDER BY r.resource_id
            LIMIT 1
            FOR UPDATE;

            IF NOT FOUND THEN
                -- Not created here. inv.resources is what the kernel measured;
                -- inventing a row would be capacity nobody observed.
                RETURN QUERY SELECT false,
                    'the execution kernel has not observed this resource on this node',
                    NULL::text, NULL::bigint;
                RETURN;
            END IF;

            IF p_offered > row_resource.capacity THEN
                RETURN QUERY SELECT false, 'a node cannot offer more than it has',
                                    row_resource.resource_id, row_resource.capacity;
                RETURN;
            END IF;

            SELECT coalesce(sum(l.amount), 0) INTO leased
            FROM inv.resource_leases l
            WHERE l.tenant_id = p_tenant_id
              AND l.resource_id = row_resource.resource_id
              AND l.released_at IS NULL;

            IF p_offered < leased THEN
                -- The kernel's rule, stricter than "a ceiling for future work":
                -- it will not hold more than the owner now permits.
                RETURN QUERY SELECT false,
                    'work already leased exceeds this offer; release it first',
                    row_resource.resource_id, row_resource.capacity;
                RETURN;
            END IF;

            -- Aliased and qualified: the RETURNS TABLE names are PL/pgSQL
            -- variables in this body, and an unqualified column of the same
            -- name is ambiguous rather than wrong-and-silent.
            UPDATE inv.resources AS r SET offered = p_offered
            WHERE r.tenant_id = p_tenant_id
              AND r.resource_id = row_resource.resource_id;

            RETURN QUERY SELECT true, NULL::text, row_resource.resource_id,
                                row_resource.capacity;
        END
        $fn$;
        """
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION {FUNCTION}(uuid, char(30), text, bigint) FROM PUBLIC"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {FUNCTION}(uuid, char(30), text, bigint) "
        f"TO {APP_ROLE}"
    )


def downgrade() -> None:
    op.execute(
        f"DROP FUNCTION IF EXISTS {FUNCTION}(uuid, char(30), text, bigint)"
    )
