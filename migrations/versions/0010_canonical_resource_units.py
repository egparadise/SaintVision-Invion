"""Give every resource quantity one unit, and make the wrong unit unstorable.

Revision ID: 0010_canonical_resource_units
Revises: 0009_idempotency_and_inbox_scope
Create Date: 2026-09-10

``unit`` was free text on three tables. A node declared its capability in one
unit, its offer in another and every observation in a third, and nothing ever
compared the strings — ``node_spare`` subtracted ``used_quantity`` from
``offered_quantity`` regardless. 32 "GiB" offered against 4096 "MB" used gives
a spare of zero and the machine looks full; swap the two and it looks perfectly
idle and wins every placement. Both readings were accepted.

Placement is the product. A comparison between two numbers in unknown units is
not a weaker version of that feature, it is a different feature that happens to
return a node id.

So the unit stops being data and becomes a property of the kind — millicores
for CPU, bytes for RAM and disk, whole devices for GPU (``saintvision.units``).
Three consequences here:

* ``node_capabilities.unit`` is constrained to the canonical unit for its kind,
  so a row in the wrong unit cannot exist.
* ``resource_offers.unit`` and ``resource_snapshots.unit`` are **dropped**. A
  unit stored in three places is a unit that can disagree in three places; the
  capability owns it and the other two inherit it by joining.
* The quantities become ``bigint``. Every canonical unit counts an indivisible
  thing, and ``NUMERIC(20,4)`` left room to store a third of a byte. It also
  makes the columns hold exactly what ``inv.resources.capacity`` holds, which
  is what a single source of truth across the seam requires.

Existing rows are converted, not reinterpreted. A row whose unit this migration
does not recognise **aborts the migration** rather than being guessed at: an
uninterpretable unit is not a smaller problem than a missing one, and the
migration is the last moment where a human is still watching.

Two further integrity gaps are closed here, because they are in these tables
and on this same placement path:

**Observations could name another node's capability.** ``resource_snapshots``
had no foreign key at all. An authenticated node could post utilisation against
any ``capability_id`` in its tenant, including a capability belonging to a
different machine — which lands in ``node_spare`` as that machine being busy,
or as this one being measured and idle when it is neither. The composite
foreign key on ``(tenant_id, node_id, capability_id)`` makes it unstorable
rather than merely checked.

**``shard_count`` had a ceiling in the API and none in the database.** The API
said ``le=1024``; the table said ``>= 1``. Anything reaching the table by
another path — a service call, a backfill, the next endpoint — had no bound at
all, and the bound is what stops one request planning four billion shards.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_canonical_resource_units"
down_revision = "0009_idempotency_and_inbox_scope"
branch_labels = None
depends_on = None

#: Mirrors saintvision.units.CANONICAL_UNIT. Written out rather than imported:
#: a migration that reads today's application constants describes today's code
#: instead of the change it made, and would mean something different if it were
#: ever replayed against an older database.
UNIT_MATCHES_KIND = (
    "(kind = 'cpu'  AND unit = 'millicores') OR "
    "(kind = 'ram'  AND unit = 'bytes') OR "
    "(kind = 'disk' AND unit = 'bytes') OR "
    "(kind = 'gpu'  AND unit = 'devices')"
)

#: The same multipliers as ``saintvision.units._ACCEPTED``, as SQL. A unit that
#: is not listed converts to NULL, which :func:`_guard` turns into a failure.
#: Created in ``pg_temp`` so it cannot outlive the migration and become an
#: undocumented database object.
CONVERTER = """
CREATE FUNCTION pg_temp.to_canonical(kind text, qty numeric, unit text)
RETURNS numeric LANGUAGE sql IMMUTABLE AS $fn$
    SELECT qty * CASE
        WHEN kind = 'cpu' THEN CASE lower(btrim(unit))
            WHEN 'millicores' THEN 1 WHEN 'mcores' THEN 1 WHEN 'millicore' THEN 1
            WHEN 'cores' THEN 1000 WHEN 'core' THEN 1000 WHEN 'cpus' THEN 1000
            WHEN 'vcpu' THEN 1000 WHEN 'vcpus' THEN 1000 END
        WHEN kind IN ('ram', 'disk') THEN CASE lower(btrim(unit))
            WHEN 'bytes' THEN 1 WHEN 'byte' THEN 1 WHEN 'b' THEN 1
            WHEN 'kb' THEN 1000 WHEN 'mb' THEN 1000000 WHEN 'gb' THEN 1000000000
            WHEN 'tb' THEN 1000000000000
            WHEN 'kib' THEN 1024 WHEN 'mib' THEN 1048576 WHEN 'gib' THEN 1073741824
            WHEN 'tib' THEN 1099511627776 END
        WHEN kind = 'gpu' THEN CASE lower(btrim(unit))
            WHEN 'devices' THEN 1 WHEN 'device' THEN 1 WHEN 'gpus' THEN 1
            WHEN 'gpu' THEN 1 WHEN 'count' THEN 1 END
    END
$fn$;
"""


def _guard(table: str, column: str, join: str) -> str:
    """Abort if any row carries a unit the conversion does not recognise."""
    return f"""
DO $guard$
DECLARE bad text;
BEGIN
    SELECT string_agg(DISTINCT t.unit, ', ') INTO bad
    FROM {table} t {join}
    WHERE pg_temp.to_canonical(c.kind, t.{column}, t.unit) IS NULL;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION
            'cannot convert {table}: unrecognised unit(s) %. Correct these rows and '
            're-run. Guessing at a unit here is how work lands on the wrong machine.',
            bad;
    END IF;
END $guard$;
"""


_CAPABILITY_JOIN = (
    "JOIN node_capabilities c ON c.tenant_id = t.tenant_id "
    "AND c.capability_id = t.capability_id"
)


def upgrade() -> None:
    op.execute(CONVERTER)

    # Check everything before changing anything: a migration that half-converts
    # and then fails leaves rows whose unit column no longer describes them.
    op.execute(
        _guard(
            "node_capabilities",
            "total_quantity",
            "JOIN node_capabilities c ON c.capability_id = t.capability_id",
        )
    )
    op.execute(_guard("resource_offers", "offered_quantity", _CAPABILITY_JOIN))
    op.execute(_guard("resource_snapshots", "used_quantity", _CAPABILITY_JOIN))

    # Offers and observations convert first: both read the capability's *kind*,
    # and the capability's own unit is still the original one until the third
    # statement.
    op.execute(
        """
        UPDATE resource_offers t
        SET offered_quantity = pg_temp.to_canonical(c.kind, t.offered_quantity, t.unit)
        FROM node_capabilities c
        WHERE c.tenant_id = t.tenant_id AND c.capability_id = t.capability_id
        """
    )
    op.execute(
        """
        UPDATE resource_snapshots t
        SET used_quantity = pg_temp.to_canonical(c.kind, t.used_quantity, t.unit)
        FROM node_capabilities c
        WHERE c.tenant_id = t.tenant_id AND c.capability_id = t.capability_id
        """
    )
    op.execute(
        """
        UPDATE node_capabilities
        SET total_quantity = pg_temp.to_canonical(kind, total_quantity, unit),
            unit = CASE kind WHEN 'cpu' THEN 'millicores'
                             WHEN 'gpu' THEN 'devices'
                             ELSE 'bytes' END
        """
    )

    # An integral unit deserves an integral type. This also makes the columns
    # hold exactly what inv.resources.capacity holds.
    for table, column in (
        ("node_capabilities", "total_quantity"),
        ("resource_offers", "offered_quantity"),
        ("resource_snapshots", "used_quantity"),
    ):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE bigint USING round({column})::bigint"
        )

    op.create_check_constraint(
        "unit_matches_kind", "node_capabilities", UNIT_MATCHES_KIND
    )

    # One unit, on the capability. The offer and the observation join for it.
    op.drop_column("resource_offers", "unit")
    op.drop_column("resource_snapshots", "unit")

    # Needed as the target of the snapshot foreign key below.
    op.create_unique_constraint(
        "uq_node_capabilities_tenant_id_node_id_capability_id",
        "node_capabilities",
        ["tenant_id", "node_id", "capability_id"],
    )
    # An observation may only name a capability of the node that reported it.
    # There was previously no key of any kind on this column.
    op.create_foreign_key(
        "fk_resource_snapshots_capability",
        "resource_snapshots",
        "node_capabilities",
        ["tenant_id", "node_id", "capability_id"],
        ["tenant_id", "node_id", "capability_id"],
    )

    # The ceiling the API already claimed, in the place that can enforce it.
    op.create_check_constraint(
        "shard_count_bounded", "distributed_plans", "shard_count <= 1024"
    )

    # A shard's requirement is compared with `>=` against a node's spare
    # capacity, and that comparison *is* the placement decision. Leaving the
    # requirement in cores while the capacity moved to millicores would have
    # kept the original defect and only changed which side of it was wrong.
    op.execute(
        "ALTER TABLE distributed_plans "
        "ALTER COLUMN shard_cpu_cores TYPE bigint USING round(shard_cpu_cores * 1000)"
    )
    op.alter_column(
        "distributed_plans", "shard_cpu_cores", new_column_name="shard_cpu_millicores"
    )
    op.alter_column(
        "distributed_plans", "shard_gpu_count", new_column_name="shard_gpu_devices"
    )
    op.execute(
        "ALTER TABLE plan_placements ALTER COLUMN assigned_cpu_cores "
        "TYPE bigint USING round(assigned_cpu_cores * 1000)"
    )
    op.alter_column(
        "plan_placements", "assigned_cpu_cores", new_column_name="assigned_cpu_millicores"
    )
    op.alter_column(
        "plan_placements", "assigned_gpu_count", new_column_name="assigned_gpu_devices"
    )


def downgrade() -> None:
    op.alter_column(
        "plan_placements", "assigned_gpu_devices", new_column_name="assigned_gpu_count"
    )
    op.alter_column(
        "plan_placements", "assigned_cpu_millicores", new_column_name="assigned_cpu_cores"
    )
    op.execute(
        "ALTER TABLE plan_placements ALTER COLUMN assigned_cpu_cores "
        "TYPE numeric(20, 4) USING assigned_cpu_cores / 1000.0"
    )
    op.alter_column(
        "distributed_plans", "shard_gpu_devices", new_column_name="shard_gpu_count"
    )
    op.alter_column(
        "distributed_plans", "shard_cpu_millicores", new_column_name="shard_cpu_cores"
    )
    op.execute(
        "ALTER TABLE distributed_plans ALTER COLUMN shard_cpu_cores "
        "TYPE numeric(20, 4) USING shard_cpu_cores / 1000.0"
    )
    op.drop_constraint("shard_count_bounded", "distributed_plans", type_="check")
    op.drop_constraint(
        "fk_resource_snapshots_capability", "resource_snapshots", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_node_capabilities_tenant_id_node_id_capability_id",
        "node_capabilities",
        type_="unique",
    )
    op.drop_constraint("unit_matches_kind", "node_capabilities", type_="check")

    # The dropped columns come back holding the canonical unit, which is what
    # the rows are actually in. Restoring the units they were originally
    # written in is not possible: that information was the thing being removed,
    # and this is why the revision is reversible in structure but not in
    # meaning. Anyone rolling back gets correct numbers, not their old ones.
    op.add_column(
        "resource_offers",
        sa.Column("unit", sa.String(16), nullable=False, server_default="bytes"),
    )
    op.add_column(
        "resource_snapshots",
        sa.Column("unit", sa.String(16), nullable=False, server_default="bytes"),
    )
    for table in ("resource_offers", "resource_snapshots"):
        op.execute(
            f"""
            UPDATE {table} t SET unit = c.unit
            FROM node_capabilities c
            WHERE c.tenant_id = t.tenant_id AND c.capability_id = t.capability_id
            """
        )

    for table, column in (
        ("node_capabilities", "total_quantity"),
        ("resource_offers", "offered_quantity"),
        ("resource_snapshots", "used_quantity"),
    ):
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE numeric(20, 4)")
