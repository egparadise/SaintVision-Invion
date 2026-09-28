"""The digest index migration: its shape, and why the drop comes first.

The index itself is a one-line ``CREATE``; what is worth a test is the two
decisions around it. It runs ``CONCURRENTLY`` so registering a dataset is not
blocked for the duration, and the upgrade drops before it creates, because a
``CREATE INDEX CONCURRENTLY`` that fails part way leaves an INVALID index behind
that the planner will not use but that holds the name and still costs on every
write -- so a retry without the drop cannot succeed.

The retry itself is exercised against a real database in
``tests/integration/test_lineage_digest_index_real_pg.py``.
"""

from __future__ import annotations

from pathlib import Path

INDEX = "ix_dataset_versions_tenant_id_content_sha256"
MIGRATION = Path(__file__).resolve().parents[2] / (
    "migrations/versions/0050_dataset_digest_lookup.py"
)


def test_the_index_is_created_concurrently_and_the_retry_is_cleared_first():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "autocommit_block()" in source, "CONCURRENTLY cannot run in a transaction"
    assert source.count("DROP INDEX CONCURRENTLY IF EXISTS") == 2, "upgrade and downgrade"
    assert "CREATE INDEX CONCURRENTLY IF NOT EXISTS" in source

    upgrade = source[source.index("def upgrade") : source.index("def downgrade")]
    # Read the statements, not the prose that explains them.
    assert upgrade.index("DROP INDEX CONCURRENTLY") < upgrade.index(
        "CREATE INDEX CONCURRENTLY"
    ), "a retry meets the invalid index unless the drop comes first"
    assert "UNIQUE INDEX" not in upgrade.upper(), (
        "the same bytes may be registered as more than one dataset version"
    )

    downgrade = source[source.index("def downgrade") :]
    assert "DROP INDEX CONCURRENTLY" in downgrade, "concurrent on the way out too"


def test_the_migration_sits_on_the_fixed_order_and_is_reversible():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0050_dataset_digest_lookup"' in source
    # The coordinator fixed one order for the open migrations: audit isolation,
    # object store locator, MLflow mirror, then this. Pinned so a renumber does
    # not silently fork the graph.
    assert 'down_revision = "0049_mlflow_mirror"' in source


def test_the_model_declares_the_index_the_migration_creates():
    """Otherwise the model and the database disagree about the schema."""
    from saintvision.db.models.lineage import DatasetVersion

    declared = {index.name: index for index in DatasetVersion.__table__.indexes}
    assert INDEX in declared
    index = declared[INDEX]
    assert [column.name for column in index.columns] == ["tenant_id", "content_sha256"]
    # tenant_id leads because every read is inside an RLS tenant scope, so the
    # index and the policy predicate point the same way.
    assert index.unique is False


def test_the_real_pg_node_points_at_a_migration_that_exists():
    """The path in the PostgreSQL node, checked without PostgreSQL.

    That node reads the migration source to run its own statements, and the path
    it read was the pre-renumber one: collection succeeded and the body raised
    FileNotFoundError, so the retry it exists to prove never ran. A path is
    checkable here, so it is checked here.
    """
    import re

    node = Path(__file__).resolve().parents[1] / (
        "integration/test_lineage_digest_index_real_pg.py"
    )
    source = node.read_text(encoding="utf-8")
    referenced = re.findall(r'"(migrations/versions/[^"]+\.py)"', source)
    assert referenced, "the node no longer names a migration; this guard is stale"
    root = Path(__file__).resolve().parents[2]
    for relative in referenced:
        assert (root / relative).exists(), relative
    assert MIGRATION.name in referenced[0]
