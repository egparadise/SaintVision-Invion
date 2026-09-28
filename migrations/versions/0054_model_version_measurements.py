"""Bind a model version's verification to the measurement that proved it (W3 seam, 0054).

``verify_model_version`` records that "a trusted worker hashed the actual
weights" (``services/lineage.py``). Until now nothing in the database said
*which* observation that was: ``verified_at`` was a timestamp anyone with the
service in hand could set from the stored digest. Design #209 v1.1 (Codex
contract) closes that with two things this migration creates together:

* ``inv.model_version_measurements`` -- the kernel-owned, append-only record of
  one signed node observation of one immutable DataLocation: the channel
  binding at issue time (node, recovery epoch, channel version, leaf
  certificate), the contribution/location snapshot, the observed digest and
  size, and the challenge/response digests. Only the kernel's accept path may
  insert; the application role may read; nothing may update or delete
  (``inv.immutable_record``). The DDL is the kernel's SQL
  (``inv/migrations/0027_model_version_measurements.sql``), executed here the
  way 0048 executes 0026.
* ``public.model_versions.verified_measurement_id`` -- nullable, with the
  composite foreign key ``(tenant_id, verified_measurement_id)`` to that table
  and the CHECK ``(verified_at IS NULL) = (verified_measurement_id IS NULL)``.
  A version is verified exactly when a measurement is bound to it, and both
  are set in one statement by the service. The application role gets
  column-level UPDATE on the new column, as 0004 gave it on ``verified_at``
  (``LIFECYCLE_UPDATE_COLUMNS``); the grant is idempotent and always issued.

**Existing data.** A row with ``verified_at`` set and no measurement to bind
would violate the CHECK. Such rows are not rewritten and not guessed at: the
upgrade refuses before any DDL, naming the version ids, so an operator can
either re-verify them through the seam or clear ``verified_at`` in a reviewed
data fix. A fresh database has none.

**Convergence** follows 0052/0053: the catalogue is read first and each part
is added only when absent, kept when present with exactly the expected shape
(column type and nullability; the foreign key's type, referenced table,
columns, actions, match type, deferrability and validity; the CHECK's
expression), and refused when present with a different shape. Offline
rendering issues everything and asks nothing.

**Downgrade** refuses while any version is bound to a measurement or any
measurement row exists (dropping either would discard evidence); otherwise it
drops the CHECK, the foreign key, the column and the table.

Numbered 0054 on ``0053_eval_suite_project_scope`` by the coordinator's
decision (card 83 / #209).
"""

from importlib import resources

from alembic import op
import sqlalchemy as sa

revision = "0054_model_version_measurements"
down_revision = "0053_eval_suite_project_scope"
branch_labels = None
depends_on = None

TABLE = "model_versions"
COLUMN = "verified_measurement_id"
FK = "fk_model_versions_verified_measurement"
CHECK = "ck_model_versions_verified_iff_measurement"
MEASUREMENTS = "inv.model_version_measurements"
KERNEL_SQL = "migrations/0027_model_version_measurements.sql"

#: The kernel table, or no rows.
MEASUREMENTS_PRESENT = f"SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'inv' AND c.relname = 'model_version_measurements' AND c.relkind = 'r'"

#: The kernel table's shape when present: the column set (order-free) and the
#: policy, so a same-named table made by something else is refused.
MEASUREMENTS_SHAPE = """
SELECT (
         SELECT array_agg(a.attname::text ORDER BY a.attname)
         FROM pg_attribute a
         WHERE a.attrelid = 'inv.model_version_measurements'::regclass AND a.attnum > 0 AND NOT a.attisdropped
       ) AS columns,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = 'inv.model_version_measurements'::regclass AND p.polname = 'tenant_isolation') AS policies
"""

EXPECTED_MEASUREMENT_COLUMNS = sorted([
    "tenant_id", "measurement_id", "request_id", "project_id", "model_version_id", "uri",
    "contribution_id", "contribution_version", "location_id", "location_version", "relative_path",
    "node_id", "recovery_epoch", "channel_version", "certificate_sha256",
    "sha256", "byte_size", "observed_at", "recorded_at", "challenge_sha256", "response_sha256", "duration_seconds",
])

COLUMN_SHAPE = f"""
SELECT data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = '{TABLE}' AND column_name = '{COLUMN}'
"""
EXPECTED_COLUMN = ("character", 30, "YES")

FK_SHAPE = f"""
SELECT c.contype::text,
       c.confrelid::regclass::text,
       (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
       (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum),
       c.confupdtype::text, c.confdeltype::text, c.confmatchtype::text,
       c.condeferrable, c.condeferred, c.convalidated
FROM pg_constraint c
WHERE c.conname = '{FK}' AND c.conrelid = 'public.{TABLE}'::regclass
"""
EXPECTED_FK = ("f", MEASUREMENTS, ["tenant_id", COLUMN], ["tenant_id", "measurement_id"], "a", "a", "s", False, False, True)

CHECK_SHAPE = f"""
SELECT c.contype::text, pg_get_constraintdef(c.oid), c.convalidated
FROM pg_constraint c
WHERE c.conname = '{CHECK}' AND c.conrelid = 'public.{TABLE}'::regclass
"""
CHECK_EXPRESSION = "(verified_at IS NULL) = (verified_measurement_id IS NULL)"
#: How PostgreSQL renders that expression back (pg_get_constraintdef).
EXPECTED_CHECK = ("c", f"CHECK (({CHECK_EXPRESSION}))", True)
GRANT = f"GRANT UPDATE ({COLUMN}) ON {TABLE} TO inv_app"

#: Versions verified before the seam existed: they cannot satisfy the CHECK
#: and are not guessed at.
UNBOUND_VERIFIED = f"""
SELECT model_version_id FROM public.{TABLE}
WHERE verified_at IS NOT NULL AND ({COLUMN} IS NULL)
ORDER BY model_version_id
"""
BOUND_VERIFIED = f"SELECT model_version_id FROM public.{TABLE} WHERE {COLUMN} IS NOT NULL ORDER BY model_version_id"
MEASUREMENT_ROWS = f"SELECT count(*) FROM {MEASUREMENTS}"


def _kernel_sql() -> str:
    return resources.files("inv").joinpath(KERNEL_SQL).read_text("utf-8")


def _add_column() -> None:
    op.add_column(TABLE, sa.Column(COLUMN, sa.CHAR(30), nullable=True))


def _add_fk() -> None:
    op.create_foreign_key(
        FK, TABLE, "model_version_measurements", ["tenant_id", COLUMN], ["tenant_id", "measurement_id"],
        referent_schema="inv",
    )


def _add_check() -> None:
    op.create_check_constraint(CHECK, TABLE, CHECK_EXPRESSION)


def _refuse(what: str, shape, expected) -> None:
    raise RuntimeError(
        f"{what} already exists with a different definition ({shape!r}; expected "
        f"{expected!r}). Something other than this migration owns that name; resolve "
        "it with a reviewed fix before running again."
    )


def upgrade():
    context = op.get_context()

    if context.as_sql:
        op.execute(_kernel_sql())
        _add_column()
        _add_fk()
        _add_check()
        op.execute(GRANT)
        return

    bind = op.get_bind()

    # Data first: a verified row that nothing can bind is a stop, not a guess.
    if bind.exec_driver_sql(COLUMN_SHAPE).fetchall():
        unbound = bind.exec_driver_sql(UNBOUND_VERIFIED).fetchall()
    else:
        unbound = bind.exec_driver_sql(
            f"SELECT model_version_id FROM public.{TABLE} WHERE verified_at IS NOT NULL ORDER BY model_version_id"
        ).fetchall()
    if unbound:
        listed = ", ".join(row[0] for row in unbound[:10])
        raise RuntimeError(
            f"{len(unbound)} model version(s) are verified without a measurement to bind "
            f"({listed}); the CHECK would refuse them. Re-verify them through the "
            "measurement seam or clear verified_at in a reviewed data fix, then run this again."
        )

    if bind.exec_driver_sql(MEASUREMENTS_PRESENT).fetchall():
        row = bind.exec_driver_sql(MEASUREMENTS_SHAPE).fetchall()[0]
        columns = sorted(row[0] or [])
        if columns != EXPECTED_MEASUREMENT_COLUMNS or int(row[1]) != 1:
            _refuse(MEASUREMENTS, (columns, int(row[1])), (EXPECTED_MEASUREMENT_COLUMNS, 1))
        # Present and right: the kernel SQL is not re-run (it is not idempotent).
    else:
        op.execute(_kernel_sql())

    column = bind.exec_driver_sql(COLUMN_SHAPE).fetchall()
    if column:
        shape = (column[0][0], column[0][1], column[0][2])
        if shape != EXPECTED_COLUMN:
            _refuse(f"{TABLE}.{COLUMN}", shape, EXPECTED_COLUMN)
    else:
        _add_column()

    fk = bind.exec_driver_sql(FK_SHAPE).fetchall()
    if fk:
        r = fk[0]
        shape = (r[0], r[1], list(r[2] or []), list(r[3] or []), r[4], r[5], r[6], bool(r[7]), bool(r[8]), bool(r[9]))
        if shape != EXPECTED_FK:
            _refuse(FK, shape, EXPECTED_FK)
    else:
        _add_fk()

    check = bind.exec_driver_sql(CHECK_SHAPE).fetchall()
    if check:
        r = check[0]
        shape = (r[0], r[1], bool(r[2]))
        if shape != EXPECTED_CHECK:
            _refuse(CHECK, shape, EXPECTED_CHECK)
    else:
        _add_check()

    # Idempotent; re-issued on every run so a resume cannot leave it out.
    op.execute(GRANT)


def downgrade():
    context = op.get_context()
    if not context.as_sql:
        bind = op.get_bind()
        if bind.exec_driver_sql(COLUMN_SHAPE).fetchall():
            bound = bind.exec_driver_sql(BOUND_VERIFIED).fetchall()
            if bound:
                listed = ", ".join(row[0] for row in bound[:10])
                raise RuntimeError(
                    f"{len(bound)} model version(s) are bound to a measurement ({listed}); "
                    "dropping the binding would discard the evidence of their verification. "
                    "Apply a reviewed forward fix instead."
                )
        if bind.exec_driver_sql(MEASUREMENTS_PRESENT).fetchall():
            count = bind.exec_driver_sql(MEASUREMENT_ROWS).scalar()
            if count:
                raise RuntimeError(
                    f"{count} measurement row(s) exist in {MEASUREMENTS}; dropping the table "
                    "would discard signed node observations. Apply a reviewed forward fix instead."
                )
    op.execute(f"ALTER TABLE public.{TABLE} DROP CONSTRAINT IF EXISTS {CHECK}")
    op.execute(f"ALTER TABLE public.{TABLE} DROP CONSTRAINT IF EXISTS {FK}")
    op.execute(f"ALTER TABLE public.{TABLE} DROP COLUMN IF EXISTS {COLUMN}")
    op.execute(f"DROP TABLE IF EXISTS {MEASUREMENTS}")
