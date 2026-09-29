"""Record what the conformance suite observed (G-03 stage two, 0055).

Stage one (#200) answered ``NOT_OBSERVED`` because nothing stored a
``ConformanceReport``. Design #218 v1.2 (Codex approved) creates the one place
that does: ``adapter_conformance_records``, a **host-global, append-only**
statement of "the suite ran in this server against the fixture adapter and
this is what came out".

**No ``tenant_id`` and no row-level security -- on purpose** (design §2-1 (c),
Codex approved). Conformance is a property of the control-plane host and is
identical for every project; the project in the read route is who may read,
not who owns. A tenant column would either replicate one host fact per tenant
(and let two tenants hold different answers) or leave host rows NULL, which the
fail-closed tenant policy hides from everyone. The price is stated in the
schema: a row may hold **nothing tenant-, project- or user-identifying and no
free text** --

* ``host_id`` is a ``uuid``, so a hostname, an address or a path is a type
  error rather than a stored value (§2-9);
* ``adapter`` is one of the platform's tool names; ``subject`` and
  ``provenance`` are closed single-value sets, ``'fixture-adapter'`` and
  ``'in-server'``, because that is the only producer this revision ships
  (§2-2, F2). A wider value is refused by the CHECK until a producer exists;
* ``checks`` carries ``name``/``passed``/``skipped`` and never ``detail``: the
  suite's ``detail`` is stringified exceptions and, for a CLI adapter, host
  process output (§2-5);
* the counts must be non-negative, sum to ``total``, and ``total`` must equal
  the number of check entries (§2-2, §2-8).

The read query is one shape -- "the latest record for this host and this
adapter" -- and the index is that query's order, tie broken deterministically
on ``record_id`` (§2-3): ``(host_id, adapter, recorded_at DESC, record_id DESC)``.

Append-only: ``inv_app`` gets SELECT and INSERT and nothing else, like
``run_records`` (§2-4). The table joins ``APPEND_ONLY_TABLES``.

**Convergence.** A same-named table is kept only when its column, constraint,
index and privilege shape is this revision's; anything else is refused before
DDL, as 0052-0054 do. Offline rendering issues the DDL and asks nothing.

**Downgrade** drops the table -- the design's one reason to reverse is "it was
deployed by mistake" (§2-7). Observation rows are evidence, so while any exist
the downgrade refuses and asks for a reviewed forward fix, the way 0054 guards
its measurement rows; an empty table is dropped and the revision reverses
cleanly. That is why the AC-11 fixture manifest classifies it PRESERVED.

Numbered 0055 on ``0054_model_version_measurements`` by the coordinator's
decision (card 103).
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0055_adapter_conformance_records"
down_revision = "0054_model_version_measurements"
branch_labels = None
depends_on = None

TABLE = "adapter_conformance_records"
APP_ROLE = "inv_app"
INDEX = "ix_adapter_conformance_records_latest"

INV_ID = sa.CHAR(30)
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

#: The single subject and provenance this revision can produce (design §2-2, F2).
#: A row saying anything else has no producer and is refused by the database.
SUBJECT_ALLOWED = "subject = 'fixture-adapter'"
PROVENANCE_ALLOWED = "provenance = 'in-server'"
COUNTS_NON_NEGATIVE = "total >= 0 AND passed >= 0 AND failed >= 0 AND skipped >= 0"
COUNTS_SUM_TO_TOTAL = "passed + failed + skipped = total"
CHECKS_MATCH_TOTAL = "jsonb_typeof(checks) = 'array' AND jsonb_array_length(checks) = total"

CHECKS = {
    "subject_allowed": SUBJECT_ALLOWED,
    "provenance_allowed": PROVENANCE_ALLOWED,
    "counts_non_negative": COUNTS_NON_NEGATIVE,
    "counts_sum_to_total": COUNTS_SUM_TO_TOTAL,
    "checks_match_total": CHECKS_MATCH_TOTAL,
}

# ------------------------------------------------------------- convergence

TABLE_PRESENT = f"SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = '{TABLE}'"
ROWS_PRESENT = f"SELECT count(*) FROM public.{TABLE}"

SHAPE_QUERIES = {
    "columns": f"""
        SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = '{TABLE}'
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
    """,
    "constraints": f"""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'public.{TABLE}'::regclass
        ORDER BY conname
    """,
    "indexes": f"""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = '{TABLE}'
        ORDER BY indexname
    """,
    "privileges": f"""
        SELECT grantee, string_agg(privilege_type, ',' ORDER BY privilege_type)
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND table_name = '{TABLE}'
          AND grantee NOT IN (SELECT tableowner FROM pg_tables
                              WHERE schemaname = 'public' AND tablename = '{TABLE}')
        GROUP BY grantee
        ORDER BY grantee
    """,
    "rls": f"SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = 'public.{TABLE}'::regclass",
}

EXPECTED_COLUMNS = (
    ("record_id", "character(30)", True),
    ("host_id", "uuid", True),
    ("adapter", "character varying(64)", True),
    ("contract_version", "character varying(32)", True),
    ("suite_contract_version", "character varying(32)", True),
    ("subject", "character varying(32)", True),
    ("provenance", "character varying(32)", True),
    ("total", "integer", True),
    ("passed", "integer", True),
    ("failed", "integer", True),
    ("skipped", "integer", True),
    ("checks", "jsonb", True),
    ("recorded_at", "timestamp with time zone", True),
    ("created_at", "timestamp with time zone", True),
    ("version", "integer", True),
)

EXPECTED_CONSTRAINTS = {
    f"ck_{TABLE}_{name}": f"CHECK ({expression})" for name, expression in CHECKS.items()
} | {f"pk_{TABLE}": "PRIMARY KEY (record_id)"}

EXPECTED_INDEXES = {
    f"pk_{TABLE}": f"CREATE UNIQUE INDEX pk_{TABLE} ON public.{TABLE} USING btree (record_id)",
    INDEX: (
        f"CREATE INDEX {INDEX} ON public.{TABLE} USING btree "
        "(host_id, adapter, recorded_at DESC, record_id DESC)"
    ),
}

EXPECTED_PRIVILEGES = {APP_ROLE: "INSERT,SELECT"}

#: No row security at all: the table is host-global by design (§2-1 (c)).
EXPECTED_RLS = (False, False)


def normalise(text: str) -> str:
    """Compare definitions by meaning: casts, parentheses, whitespace and case."""
    text = re.sub(r"::[a-z_]+(?: [a-z_]+)*(?:\[\])?", "", text)
    text = re.sub(r"[()]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _observed_shape(bind) -> dict:
    rows = {part: bind.exec_driver_sql(sql).fetchall() for part, sql in SHAPE_QUERIES.items()}
    return {
        "columns": tuple((r[0], r[1], bool(r[2])) for r in rows["columns"]),
        "constraints": {r[0]: normalise(r[1]) for r in rows["constraints"]},
        "indexes": {r[0]: normalise(r[1]) for r in rows["indexes"]},
        "privileges": {r[0]: r[1] for r in rows["privileges"]},
        "rls": tuple(bool(v) for v in rows["rls"][0]) if rows["rls"] else None,
    }


def expected_shape() -> dict:
    return {
        "columns": EXPECTED_COLUMNS,
        "constraints": {k: normalise(v) for k, v in EXPECTED_CONSTRAINTS.items()},
        "indexes": {k: normalise(v) for k, v in EXPECTED_INDEXES.items()},
        "privileges": dict(EXPECTED_PRIVILEGES),
        "rls": EXPECTED_RLS,
    }


def shape_differences(observed: dict, expected: dict) -> list[str]:
    return [part for part in expected if observed.get(part) != expected[part]]


# ------------------------------------------------------------------- DDL


def _create() -> None:
    op.create_table(
        TABLE,
        sa.Column("record_id", INV_ID, primary_key=True),
        #: The control-plane host that ran the suite, from
        #: ``INV_CONTROL_PLANE_HOST_ID``; a uuid so nothing identifying fits.
        sa.Column("host_id", UUID, nullable=False),
        sa.Column("adapter", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.String(32), nullable=False),
        sa.Column("suite_contract_version", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("passed", sa.Integer, nullable=False),
        sa.Column("failed", sa.Integer, nullable=False),
        sa.Column("skipped", sa.Integer, nullable=False),
        sa.Column("checks", JSONB, nullable=False),
        sa.Column("recorded_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        *(sa.CheckConstraint(expression, name=name) for name, expression in CHECKS.items()),
    )
    # The read order, verbatim: the query and the index must agree or one of
    # them silently stops meaning "latest".
    op.execute(
        f"CREATE INDEX {INDEX} ON {TABLE} (host_id, adapter, recorded_at DESC, record_id DESC)"
    )
    op.execute(f"GRANT SELECT, INSERT ON {TABLE} TO {APP_ROLE}")


def upgrade():
    context = op.get_context()
    if context.as_sql:
        _create()
        return

    bind = op.get_bind()
    if bind.exec_driver_sql(TABLE_PRESENT).fetchall():
        differences = shape_differences(_observed_shape(bind), expected_shape())
        if differences:
            raise RuntimeError(
                f"{TABLE} exists with a different shape ({', '.join(differences)}); "
                "refusing to converge over it. Apply a reviewed forward fix instead."
            )
        return
    _create()


def downgrade():
    context = op.get_context()
    if not context.as_sql:
        bind = op.get_bind()
        if bind.exec_driver_sql(TABLE_PRESENT).fetchall():
            count = bind.exec_driver_sql(ROWS_PRESENT).scalar()
            if count:
                raise RuntimeError(
                    f"{count} conformance record(s) exist in {TABLE}; dropping the table "
                    "would discard observations. Apply a reviewed forward fix instead."
                )
    op.execute(f"DROP TABLE IF EXISTS {TABLE}")
