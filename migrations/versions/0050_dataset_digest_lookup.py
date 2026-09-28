"""Index the dataset content digest, for the reverse lineage lookup.

The reverse question -- which model versions were built from these bytes --
starts by finding ``dataset_versions`` by ``content_sha256``, and that column had
no index: not in the model's ``__table_args__`` and not in any earlier migration.
Without it the first step of the new route is a sequential scan of the table the
route exists to search.

``tenant_id`` leads because every read happens inside an RLS tenant scope, so the
index and the policy predicate point the same way.

Not UNIQUE: the same bytes may legitimately be registered as more than one
dataset version, and a unique constraint would forbid that fact rather than
record it. The API returns a list for the same reason.

Numbered 0050 on top of ``0049_mlflow_mirror`` because the coordinator fixed one
order for the open migrations -- audit isolation, object store locator, MLflow
mirror, then this index -- so the branches arrive at a single head instead of two.
That is also why this is its own change rather than part of the lineage read API
that needs it: the reads sit on a different branch, and the design's rule that the
reverse route must not land without this index is kept by merge order.

``CONCURRENTLY``, and therefore an autocommit block: a plain ``CREATE INDEX``
takes ACCESS EXCLUSIVE on ``dataset_versions`` and blocks dataset registration
for the duration. This is the first concurrent index in this repository, so two
consequences are worth stating rather than discovering:

* inside the autocommit block this migration does not roll back as a
  transaction. The ``IF EXISTS``/``IF NOT EXISTS`` pair is what makes a partial
  failure converge instead of wedging.
* a failed ``CREATE INDEX CONCURRENTLY`` leaves an INVALID index behind. The
  planner will not use it, but it holds the name and still costs on every write,
  so the upgrade drops it first -- which is what makes a retry safe.
"""

from alembic import op

revision = "0050_dataset_digest_lookup"
down_revision = "0049_mlflow_mirror"
branch_labels = None
depends_on = None

INDEX = "ix_dataset_versions_tenant_id_content_sha256"


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX} "
            "ON dataset_versions (tenant_id, content_sha256)"
        )


def downgrade():
    # Concurrent on the way out for the same lock reason.
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX}")
