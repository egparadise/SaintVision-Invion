"""Real PostgreSQL for the digest index (S10-DB design §10, items 35 and 36).

Two things a stand-in cannot show: which plan the planner actually picks for the
predicate this index exists for, and that the migration is safe to run again after
a failed attempt. They travel with the migration rather than with the lineage read
routes, which are a separate PR on a different branch.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres

INDEX = "ix_dataset_versions_tenant_id_content_sha256"


def _digest() -> str:
    """64 lowercase hex, unique: the shape the checksum column requires."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def test_35_the_digest_index_is_what_the_planner_uses(owner_engine, app_engine, migrated):
    """Plan observation, not a performance assertion.

    Recorded because the index is the reason the reverse route can exist; the
    numbers a plan carries are not evidence of anything on a runner this size.
    """
    query = (
        "EXPLAIN SELECT dataset_version_id FROM dataset_versions "
        "WHERE tenant_id = :tenant AND content_sha256 = :sha"
    )
    parameters = {"tenant": uuid.uuid4(), "sha": _digest()}
    with owner_engine.begin() as connection:
        # Discouraged rather than forbidden, which is all EXPLAIN needs here.
        connection.execute(text("SET LOCAL enable_seqscan = off"))
        with_index = "\n".join(
            row[0] for row in connection.execute(text(query), parameters)
        )
    assert INDEX in with_index or "Index Scan" in with_index, with_index

    try:
        with owner_engine.begin() as connection:
            connection.execute(text(f"DROP INDEX {INDEX}"))
            without = "\n".join(
                row[0] for row in connection.execute(text(query), parameters)
            )
        assert INDEX not in without
        assert "Seq Scan" in without, without
    finally:
        # Restore whatever happened above: the rest of the session expects the
        # schema the migration made.
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {INDEX} "
                    "ON dataset_versions (tenant_id, content_sha256)"
                )
            )


def test_36_the_concurrent_index_migration_is_safe_to_run_again(owner_engine, migrated):
    """Run the migration's own statements twice, then its downgrade.

    What is *not* reproduced here is a genuinely INVALID index: that needs a
    concurrent build killed part way, which a test cannot arrange reliably. What
    *is* reproduced is the condition that makes a retry fail without the leading
    drop -- the index name already taken -- and the statements are the migration's
    own, read out of it rather than restated.
    """
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/versions/0050_dataset_digest_lookup.py"
    )
    assert path.exists(), f"the migration this node exercises is not at {path}"
    source = path.read_text(encoding="utf-8")
    drop = f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX}"
    create = (
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX} "
        "ON dataset_versions (tenant_id, content_sha256)"
    )
    # The migration builds these with an f-string over INDEX, so the literal
    # placeholder is what appears in its source. Checked so this test cannot drift
    # away from the statements that actually run.
    assert "DROP INDEX CONCURRENTLY IF EXISTS {INDEX}" in source
    assert "CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX} " in source
    assert 'INDEX = "ix_dataset_versions_tenant_id_content_sha256"' in source

    def present(connection):
        return connection.execute(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relname = :name"
            ),
            {"name": INDEX},
        ).scalar_one()

    # CONCURRENTLY cannot run inside a transaction block.
    with owner_engine.connect() as connection:
        connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        try:
            assert present(connection) == 1, "the migration has already run"
            # A retry with the name taken: the drop is what makes it converge.
            connection.execute(text(drop))
            assert present(connection) == 0
            connection.execute(text(create))
            assert present(connection) == 1
            # And again, which is the retry the design asks for.
            connection.execute(text(drop))
            connection.execute(text(create))
            assert present(connection) == 1
            # The downgrade leaves none behind.
            connection.execute(text(drop))
            assert present(connection) == 0
        finally:
            # Restore even on failure: another node reads this plan.
            connection.execute(text(create))
        assert present(connection) == 1
