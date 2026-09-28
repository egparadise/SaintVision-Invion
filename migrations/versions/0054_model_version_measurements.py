"""Bind a model version's verification to the measurement that proved it (W3 seam, 0054).

``verify_model_version`` records that "a trusted worker hashed the actual
weights" (``services/lineage.py``). Until now nothing in the database said
*which* observation that was: ``verified_at`` was a timestamp anyone with the
service in hand could set from the stored digest. Design #209 v1.1 (Codex
contract) closes that with three things this migration creates together:

* ``inv.model_version_measurements`` -- the kernel-owned, append-only record of
  one signed node observation of one immutable DataLocation: the channel
  binding at issue time (node, recovery epoch, channel version, leaf
  certificate), the contribution/location snapshot, the observed digest and
  size, and the challenge/response digests. Only ``inv_kernel`` may insert;
  nothing may update or delete (``inv.immutable_record``); the application
  role has **no privilege on the table and no access to the schema**. The DDL
  is the kernel's SQL (``inv/migrations/0027_model_version_measurements.sql``),
  executed here the way 0048 executes 0026.
* ``public.model_version_measurement(text)`` -- the one way the application
  reads a measurement: a tenant-bound ``SECURITY DEFINER`` reader in the 0044
  ``model_registry_snapshot`` shape (``search_path`` pinned, body
  schema-qualified, the tenant taken from ``inv.tenant_id`` and never from an
  argument). ``EXECUTE`` to ``inv_app`` only. Its definition is pinned in
  ``tools/definer-policy.json``, and both the policy hash and the "present and
  identical" check below are computed from the same body constant.
* ``public.model_versions.verified_measurement_id`` -- nullable, with the
  composite foreign key ``(tenant_id, verified_measurement_id)`` to the kernel
  table and the CHECK ``(verified_at IS NULL) = (verified_measurement_id IS
  NULL)``. A version is verified exactly when a measurement is bound to it,
  and both are set in one statement by the service. The application role gets
  column-level UPDATE on the new column, as 0004 gave it on ``verified_at``.

**Existing data.** A row with ``verified_at`` set and no measurement to bind
would violate the CHECK. Such rows are not rewritten and not guessed at: the
upgrade refuses before any DDL, naming the version ids, so an operator can
either re-verify them through the seam or clear ``verified_at`` in a reviewed
data fix. A fresh database has none.

**Convergence** follows 0052/0053, and for the kernel table it is the *whole*
security and constraint shape, not a name list (Codex #213 F1): every column's
type and nullability, every constraint's definition, every index's definition,
``ENABLE`` and ``FORCE`` row security, the policy's command, roles, USING and
WITH CHECK, the privileges of every non-owner role, and the immutable trigger
with its function and enabled state. A same-named table that differs in any
of those is refused before the public side is touched; the kernel SQL is never
re-run over an existing table (it is not idempotent). The reader function is
kept only when its definition is byte-identical to this revision's. Offline
rendering issues everything and asks nothing.

**Downgrade** refuses while any version is bound to a measurement or any
measurement row exists (dropping either would discard evidence); otherwise it
drops the CHECK, the foreign key, the column, the reader and the table.

Numbered 0054 on ``0053_eval_suite_project_scope`` by the coordinator's
decision (card 83 / #209).
"""

from __future__ import annotations

import hashlib
import re
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
READER = "public.model_version_measurement(text)"

# ---------------------------------------------------------------- the kernel table's whole shape

#: The kernel table, or no rows.
MEASUREMENTS_PRESENT = (
    "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE n.nspname = 'inv' AND c.relname = 'model_version_measurements' AND c.relkind = 'r'"
)

_REL = "'inv.model_version_measurements'::regclass"

#: One question per part of the shape. The marker comment is what the PG-free
#: stand-in dispatches on; PostgreSQL ignores it.
KERNEL_SHAPE_QUERIES = {
    "columns": f"""
/* shape:columns */
SELECT a.attname::text, format_type(a.atttypid, a.atttypmod), a.attnotnull
FROM pg_attribute a
WHERE a.attrelid = {_REL} AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
""",
    "constraints": f"""
/* shape:constraints */
SELECT c.contype::text, pg_get_constraintdef(c.oid)
FROM pg_constraint c WHERE c.conrelid = {_REL}
ORDER BY 1, 2
""",
    "indexes": f"""
/* shape:indexes */
SELECT indexdef FROM pg_indexes
WHERE schemaname = 'inv' AND tablename = 'model_version_measurements'
ORDER BY 1
""",
    "rls": f"""
/* shape:rls */
SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c WHERE c.oid = {_REL}
""",
    "policies": f"""
/* shape:policies */
SELECT p.polname::text, p.polcmd::text, p.polpermissive,
       (SELECT array_agg(CASE WHEN r = 0 THEN 'public' ELSE pg_get_userbyid(r) END ORDER BY r) FROM unnest(p.polroles) r),
       pg_get_expr(p.polqual, p.polrelid), pg_get_expr(p.polwithcheck, p.polrelid)
FROM pg_policy p WHERE p.polrelid = {_REL}
ORDER BY 1
""",
    "privileges": f"""
/* shape:privileges */
SELECT CASE WHEN a.grantee = 0 THEN 'public' ELSE pg_get_userbyid(a.grantee) END, a.privilege_type
FROM pg_class c, aclexplode(c.relacl) a
WHERE c.oid = {_REL} AND a.grantee <> c.relowner
ORDER BY 1, 2
""",
    "triggers": f"""
/* shape:triggers */
SELECT t.tgname::text, t.tgenabled::text, n.nspname::text, p.proname::text, t.tgtype
FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE t.tgrelid = {_REL} AND NOT t.tgisinternal
ORDER BY t.tgname
""",
}

_CAST = re.compile(r"::[a-z_]+(?: [a-z_]+)*")


def normalise(expression: str) -> str:
    """One spelling for an expression PostgreSQL may render several ways.

    Casts, parentheses, whitespace and case are rendering; operators, names
    and literals are meaning. ``normalise`` keeps only the latter, and both
    the expected shape and the catalogue's answer go through it.
    """
    text = _CAST.sub("", expression)
    return re.sub(r"[\s()]", "", text).lower()


TENANT_PREDICATE = "tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid"

EXPECTED_KERNEL_SHAPE = {
    "columns": [
        ("tenant_id", "uuid", True),
        ("measurement_id", "character(30)", True),
        ("request_id", "uuid", True),
        ("project_id", "character(30)", True),
        ("model_version_id", "character(30)", True),
        ("uri", "text", True),
        ("contribution_id", "character(30)", True),
        ("contribution_version", "bigint", True),
        ("location_id", "character(30)", True),
        ("location_version", "bigint", True),
        ("relative_path", "text", True),
        ("node_id", "character(30)", True),
        ("recovery_epoch", "uuid", True),
        ("channel_version", "bigint", True),
        ("certificate_sha256", "text", True),
        ("sha256", "character(64)", True),
        ("byte_size", "bigint", True),
        ("observed_at", "timestamp with time zone", True),
        ("recorded_at", "timestamp with time zone", True),
        ("challenge_sha256", "text", True),
        ("response_sha256", "text", True),
        ("duration_seconds", "double precision", True),
    ],
    "constraints": sorted(
        [
            ("p", normalise("PRIMARY KEY (tenant_id, measurement_id)")),
            ("u", normalise("UNIQUE (tenant_id, request_id)")),
            ("c", normalise("CHECK (uri ~~ 'inv://models/%')")),
            ("c", normalise("CHECK (contribution_version >= 1)")),
            ("c", normalise("CHECK (location_version >= 1)")),
            ("c", normalise("CHECK ((length(relative_path) >= 1) AND (length(relative_path) <= 4096))")),
            ("c", normalise("CHECK (certificate_sha256 ~ '^[0-9a-f]{64}$')")),
            ("c", normalise("CHECK (sha256 ~ '^[0-9a-f]{64}$')")),
            ("c", normalise("CHECK (byte_size >= 0)")),
            ("c", normalise("CHECK (challenge_sha256 ~ '^[0-9a-f]{64}$')")),
            ("c", normalise("CHECK (response_sha256 ~ '^[0-9a-f]{64}$')")),
            ("c", normalise("CHECK (duration_seconds >= 0)")),
            ("c", normalise("CHECK (observed_at <= recorded_at)")),
        ]
    ),
    "indexes": sorted(
        normalise(definition)
        for definition in (
            "CREATE INDEX model_version_measurements_by_version ON inv.model_version_measurements USING btree (tenant_id, model_version_id, observed_at DESC)",
            "CREATE UNIQUE INDEX model_version_measurements_pkey ON inv.model_version_measurements USING btree (tenant_id, measurement_id)",
            "CREATE UNIQUE INDEX model_version_measurements_tenant_id_request_id_key ON inv.model_version_measurements USING btree (tenant_id, request_id)",
        )
    ),
    "rls": [(True, True)],
    "policies": [("tenant_isolation", "*", True, ["public"], normalise(TENANT_PREDICATE), normalise(TENANT_PREDICATE))],
    "privileges": [("inv_kernel", "INSERT"), ("inv_kernel", "SELECT")],
    #: BEFORE (2) | ROW (1) | DELETE (8) | UPDATE (16); enabled ('O').
    "triggers": [("immutable", "O", "inv", "immutable_record", 27)],
}


def _shape_from(rows_by_part) -> dict:
    """The catalogue's answers in the expected form."""
    columns = [(r[0], r[1], bool(r[2])) for r in rows_by_part["columns"]]
    constraints = sorted((r[0], normalise(r[1])) for r in rows_by_part["constraints"])
    indexes = sorted(normalise(r[0]) for r in rows_by_part["indexes"])
    rls = [(bool(r[0]), bool(r[1])) for r in rows_by_part["rls"]]
    policies = [
        (r[0], r[1], bool(r[2]), sorted(r[3] or []), normalise(r[4] or ""), normalise(r[5] or ""))
        for r in rows_by_part["policies"]
    ]
    privileges = sorted((r[0], r[1]) for r in rows_by_part["privileges"])
    triggers = [(r[0], r[1], r[2], r[3], int(r[4])) for r in rows_by_part["triggers"]]
    return {
        "columns": columns, "constraints": constraints, "indexes": indexes, "rls": rls,
        "policies": policies, "privileges": privileges, "triggers": triggers,
    }


def kernel_shape(bind) -> dict:
    return _shape_from({part: bind.exec_driver_sql(sql).fetchall() for part, sql in KERNEL_SHAPE_QUERIES.items()})


# ---------------------------------------------------------------- the reader

#: The reader's body, verbatim between the dollar quotes. Both the DDL and the
#: definition PostgreSQL renders back (``pg_get_functiondef``) are built from
#: this one constant, so the policy hash and the resume check cannot drift
#: from what is created.
READER_BODY = """
BEGIN
  RETURN QUERY SELECT m.model_version_id::text, m.sha256::text, m.byte_size, m.observed_at
  FROM inv.model_version_measurements m
  WHERE m.tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid
    AND m.measurement_id = p_measurement_id;
END
"""

READER_DDL = f"""
CREATE FUNCTION public.model_version_measurement(p_measurement_id text)
RETURNS TABLE(model_version_id text, sha256 text, byte_size bigint, observed_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $fn${READER_BODY}$fn$;
"""

READER_GRANTS = (
    f"REVOKE ALL ON FUNCTION {READER} FROM PUBLIC",
    f"GRANT EXECUTE ON FUNCTION {READER} TO inv_app",
)


def reader_definition() -> str:
    """What ``pg_get_functiondef`` renders for the reader (0044's shape, verified)."""
    return (
        "CREATE OR REPLACE FUNCTION public.model_version_measurement(p_measurement_id text)\n"
        " RETURNS TABLE(model_version_id text, sha256 text, byte_size bigint, observed_at timestamp with time zone)\n"
        " LANGUAGE plpgsql\n"
        " SECURITY DEFINER\n"
        " SET search_path TO 'pg_catalog'\n"
        f"AS $function${READER_BODY}$function$\n"
    )


def reader_definition_sha256() -> str:
    return hashlib.sha256(reader_definition().encode("utf-8")).hexdigest()


READER_PRESENT = """
/* shape:reader */
SELECT pg_get_functiondef(p.oid)
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.proname = 'model_version_measurement'
  AND pg_catalog.oidvectortypes(p.proargtypes) = 'text'
"""

# ---------------------------------------------------------------- the public side

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
    # ``op.f``: the name is final. Without it Alembic applies the metadata
    # naming convention a second time and creates ``ck_model_versions_ck_...``.
    op.create_check_constraint(op.f(CHECK), TABLE, CHECK_EXPRESSION)


def _create_reader() -> None:
    op.execute(READER_DDL)


def _grants() -> None:
    # Idempotent; re-issued on every run so a resume cannot leave them out.
    op.execute(GRANT)
    for statement in READER_GRANTS:
        op.execute(statement)


def _refuse(what: str, shape, expected) -> None:
    raise RuntimeError(
        f"{what} already exists with a different definition ({shape!r}; expected "
        f"{expected!r}). Something other than this migration owns that name; resolve "
        "it with a reviewed fix before running again."
    )


def _require_kernel_shape(bind) -> None:
    """Every part of the kernel table's shape, or a refusal naming the first that differs."""
    actual = kernel_shape(bind)
    for part, expected in EXPECTED_KERNEL_SHAPE.items():
        if actual[part] != expected:
            _refuse(f"{MEASUREMENTS} ({part})", actual[part], expected)


def upgrade():
    context = op.get_context()

    if context.as_sql:
        op.execute(_kernel_sql())
        _create_reader()
        _add_column()
        _add_fk()
        _add_check()
        _grants()
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
        _require_kernel_shape(bind)
        # Present and whole: the kernel SQL is not re-run (it is not idempotent).
    else:
        op.execute(_kernel_sql())

    reader = bind.exec_driver_sql(READER_PRESENT).fetchall()
    if reader:
        if reader[0][0] != reader_definition():
            _refuse(READER, hashlib.sha256(reader[0][0].encode("utf-8")).hexdigest(), reader_definition_sha256())
    else:
        _create_reader()

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

    _grants()


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
    op.execute(f"DROP FUNCTION IF EXISTS {READER}")
    op.execute(f"DROP TABLE IF EXISTS {MEASUREMENTS}")
