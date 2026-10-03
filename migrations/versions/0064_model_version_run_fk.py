"""Bind a model version's producing run at the database level (0064, card 261).

The column has existed since 0004 and carried **no foreign key**, which the
registration route's own docstring named as the reason it refused to accept the
field: an unbound value attaches a version to a run in another project, and that
is a false provenance claim. Card 257's design closes it in two places, and this
is the database half -- a composite key, so a value can only name a run of the
**same tenant**:

    (tenant_id, produced_by_run_id) -> runs(tenant_id, run_id)

``runs`` already carries ``uq_runs_tenant_id_run_id`` and five other tables
reference that pair the same way, so nothing new is required of the parent.

The column stays **nullable**. A version that did not come out of a run -- an
imported weight file -- claims nothing, and NULL is how it says so.

**Project membership is not what this enforces.** The key proves the run exists
inside the tenant; the route proves the run belongs to the path's project
(``project_scope.run_in_project``, through the workload). Both stay: the key
cannot express the project, and the route cannot stop a direct SQL writer.

Existing rows are measured before the key is added. A value that no run matches
would make ``ADD CONSTRAINT`` fail with PostgreSQL's own message, which says
nothing about which rows are at fault, so the upgrade reads them first and
**refuses with their identities** instead. It does not repair them: a recorded
provenance claim is someone's assertion, and discarding it is a reviewed data
fix, not a migration's business.
"""

from __future__ import annotations

from alembic import op

revision = "0064_model_version_run_fk"
down_revision = "0063_build_policy_budgets"
branch_labels = None
depends_on = None

TABLE = "model_versions"
COLUMN = "produced_by_run_id"
RUN_FK = "fk_model_versions_tenant_id_produced_by_run_id"

#: The rows the key would reject, with the identities an operator needs. Ten is
#: enough to act on and short enough to read; the operator runs the same query
#: without the limit to see the rest.
DANGLING = f"""
SELECT mv.model_version_id, mv.{COLUMN}
  FROM {TABLE} mv
  LEFT JOIN runs r
    ON r.tenant_id = mv.tenant_id AND r.run_id = mv.{COLUMN}
 WHERE mv.{COLUMN} IS NOT NULL
   AND r.run_id IS NULL
 ORDER BY mv.model_version_id
 LIMIT 10
"""


def upgrade() -> None:
    context = op.get_context()
    if not context.as_sql:
        dangling = op.get_bind().exec_driver_sql(DANGLING).fetchall()
        if dangling:
            listed = ", ".join(f"{row[0]}@{row[1]}" for row in dangling)
            raise RuntimeError(
                f"{len(dangling)} model version(s) name a run that does not exist in their "
                f"tenant ({listed}); this migration does not clear a recorded provenance "
                "claim. Read them with the same LEFT JOIN, correct the wrong ones to NULL "
                "with a reviewed data fix, then run this again."
            )
    op.create_foreign_key(
        RUN_FK,
        TABLE,
        "runs",
        ["tenant_id", COLUMN],
        ["tenant_id", "run_id"],
    )


def downgrade() -> None:
    # Only the key goes. The column and every value stay, so nothing is lost and
    # there is nothing to refuse -- unlike 0062 and 0063, whose downgrades drop
    # data-bearing structures and therefore guard first.
    op.drop_constraint(RUN_FK, TABLE, type_="foreignkey")
