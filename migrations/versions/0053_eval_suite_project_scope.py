"""Give an evaluation suite a project, so W5 can be bound to a path.

The business lane's write routes are graded per project (``canApprove`` on
``/projects/{p}/…``), and every one of them binds the path's project to a row
before it acts: a run through its workload, a model version through its model.
``eval_suites`` has no such row -- it carries a tenant and nothing narrower --
so ``POST /projects/{p}/eval/suites/{suite_id}/runs`` (W5, G-04·G-05 design
§5-1) had nothing to bind to. A tenant-wide route behind a project grade is
the shape #158 §1-4 and Codex F-R1 refused: naming a scope in the path does
not create a permission.

**What this adds.** ``eval_suites.project_id``, nullable, with the composite
foreign key ``(tenant_id, project_id) -> projects (tenant_id, project_id)`` and
an index on the pair. Nullable because every suite that exists today has no
project and this migration does not invent one: an existing suite stays
``NULL`` and the W5 route treats a ``NULL`` suite as absent (404) rather than
as reachable from every project. ``eval_runs`` needs no column: a run belongs
to its suite, and the suite's project is the run's.

**Why the migration reads before it writes.** The column is new and nullable,
so no existing row can violate it; the foreign key is over a column that is
``NULL`` everywhere, so no existing row can violate that either. Those are
arguments. ``upgrade`` checks the catalogue and the data before it changes
anything, because the migration is what acts on the answer -- and because a
re-run after an interruption has to converge rather than fail on the half it
already did (the way 0052 does it):

* neither the column nor the constraint is there -- add the column, the
  foreign key and the index;
* the column is there with exactly the right shape (``character(30)``, the
  ``InvId`` type every id column uses, nullable) -- keep it; add whatever of the
  foreign key and the index is
  missing, and leave alone whatever is present with the right shape;
* the column or the constraint is there with a **different** shape -- refuse.
  Something other than this migration owns the name;
* a row already references a project that does not exist in its tenant --
  refuse before any DDL, naming the suite ids only.

**Downgrade** drops the index, the foreign key and the column -- unless any
suite has a project, in which case it refuses: dropping the column would
silently discard which project those suites belong to, and the route that
depends on it would then answer 404 for suites people can see today. Move the
suites (a reviewed data fix) and run it again.

Numbered 0053 on ``0052_model_version_digest_scope`` by the coordinator's
decision of 2026-09-28 on #191 (0052 went to the digest-scope fix; W5 moved
from 0052 to 0053).
"""

from alembic import op
import sqlalchemy as sa

revision = "0053_eval_suite_project_scope"
down_revision = "0052_model_version_digest_scope"
branch_labels = None
depends_on = None

TABLE = "eval_suites"
COLUMN = "project_id"
FK = "fk_eval_suites_tenant_id_project_id"
INDEX = "ix_eval_suites_tenant_id_project_id"
REFERENCED = "projects"

#: The column's shape, or no rows.
COLUMN_SHAPE = f"""
SELECT data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = current_schema() AND table_name = '{TABLE}' AND column_name = '{COLUMN}'
"""

#: The foreign key's shape under the expected name, or no rows.
FK_SHAPE = f"""
SELECT c.contype::text AS contype,
       c.confrelid::regclass::text AS referenced,
       (
         SELECT array_agg(a.attname::text ORDER BY k.ord)
         FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
         JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
       ) AS columns,
       (
         SELECT array_agg(a.attname::text ORDER BY k.ord)
         FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
         JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum
       ) AS referenced_columns
FROM pg_constraint c
WHERE c.conname = '{FK}' AND c.conrelid = '{TABLE}'::regclass
"""

#: Whether the index exists under the expected name.
INDEX_PRESENT = f"""
SELECT 1 FROM pg_indexes
WHERE schemaname = current_schema() AND tablename = '{TABLE}' AND indexname = '{INDEX}'
"""

#: Rows that would violate the foreign key. Only meaningful when the column
#: already exists (a resume); on a fresh run there is no column to read.
VIOLATIONS = f"""
SELECT s.suite_id
FROM {TABLE} s
LEFT JOIN {REFERENCED} p ON p.tenant_id = s.tenant_id AND p.project_id = s.{COLUMN}
WHERE s.{COLUMN} IS NOT NULL AND p.project_id IS NULL
ORDER BY s.suite_id
"""

#: Suites that hold a project: what a downgrade would silently discard.
SCOPED = f"SELECT suite_id FROM {TABLE} WHERE {COLUMN} IS NOT NULL ORDER BY suite_id"

EXPECTED_COLUMN = ("character", 30, "YES")
EXPECTED_FK = ("f", REFERENCED, ["tenant_id", COLUMN], ["tenant_id", "project_id"])


def _add_column() -> None:
    op.add_column(TABLE, sa.Column(COLUMN, sa.CHAR(30), nullable=True))


def _add_fk() -> None:
    op.create_foreign_key(
        FK, TABLE, REFERENCED, ["tenant_id", COLUMN], ["tenant_id", "project_id"]
    )


def _add_index() -> None:
    op.create_index(INDEX, TABLE, ["tenant_id", COLUMN])


def upgrade():
    context = op.get_context()

    if context.as_sql:
        # Offline: render every statement for a reviewer, ask nothing.
        _add_column()
        _add_fk()
        _add_index()
        return

    bind = op.get_bind()

    column = bind.exec_driver_sql(COLUMN_SHAPE).fetchall()
    if column:
        shape = (column[0][0], column[0][1], column[0][2])
        if shape != EXPECTED_COLUMN:
            raise RuntimeError(
                f"{TABLE}.{COLUMN} already exists with a different definition "
                f"({shape!r}; expected {EXPECTED_COLUMN!r}). Something other than "
                "this migration owns that column; resolve it with a reviewed fix "
                "before running again."
            )
        # A resume: the column is right. Rows may have been written since, so the
        # foreign key it is about to get is checked against the data first.
        offending = bind.exec_driver_sql(VIOLATIONS).fetchall()
        if offending:
            listed = ", ".join(row[0] for row in offending[:10])
            raise RuntimeError(
                f"{len(offending)} suite(s) reference a project that does not "
                f"exist in their tenant, so {FK} cannot be created: {listed}. "
                "Resolve them with a reviewed data fix and run this again."
            )
    else:
        _add_column()

    fk = bind.exec_driver_sql(FK_SHAPE).fetchall()
    if fk:
        shape = (fk[0][0], fk[0][1], list(fk[0][2] or []), list(fk[0][3] or []))
        if shape != EXPECTED_FK:
            raise RuntimeError(
                f"{FK} already exists on {TABLE} with a different definition "
                f"({shape!r}; expected {EXPECTED_FK!r}). Something other than this "
                "migration owns that name; resolve it with a reviewed fix before "
                "running again."
            )
        # Present and right: left alone.
    else:
        _add_fk()

    if not bind.exec_driver_sql(INDEX_PRESENT).fetchall():
        _add_index()


def downgrade():
    context = op.get_context()
    if not context.as_sql:
        scoped = op.get_bind().exec_driver_sql(SCOPED).fetchall()
        if scoped:
            listed = ", ".join(row[0] for row in scoped[:10])
            raise RuntimeError(
                f"{len(scoped)} suite(s) belong to a project ({listed}); dropping "
                f"{TABLE}.{COLUMN} would discard that silently and the W5 route would "
                "answer 404 for them. Move or clear them with a reviewed data fix, "
                "then run this again."
            )
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {FK}")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS {COLUMN}")
