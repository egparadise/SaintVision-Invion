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

from saintvision.ids import new_id

pytestmark = pytest.mark.postgres

INDEX = "ix_dataset_versions_tenant_id_content_sha256"


def _digest() -> str:
    """64 lowercase hex, unique: the shape the checksum column requires."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def test_35_the_digest_index_is_what_the_planner_uses(
    owner_engine, two_tenants, frozen_now, migrated
):
    """Plan observation: with this index the planner uses it, without it cannot.

    The first version of this asserted the plan on an empty table with
    ``enable_seqscan = off``, and hosted CI showed why that proves nothing: with
    no rows every cost ties, a penalised sequential scan loses to *any* index,
    and the planner picked ``uq_dataset_versions_tenant_id_version_id`` -- an
    unrelated unique index -- whether or not this one existed. So the table is
    populated and analysed first, which is what makes the choice determinate.

    Still not a performance assertion. The claim is only which index serves an
    equality on ``(tenant_id, content_sha256)``; the costs a plan carries are not
    evidence of anything on a runner this size.
    """
    tenant_id, _ = two_tenants
    project_id = new_id("project")
    dataset_id = new_id("dataset")
    user_id = new_id("user")
    wanted = _digest()

    def insert(connection, table_name, **values):
        from saintvision.db.base import Base
        from saintvision.db import models  # noqa: F401  (registers the tables)

        table = Base.metadata.tables[table_name]
        unknown = set(values) - set(table.columns.keys())
        assert not unknown, f"{table_name} has no column(s) {sorted(unknown)}"
        connection.execute(table.insert().values(**values))

    try:
        with owner_engine.begin() as connection:
            insert(
                connection,
                "users",
                user_id=user_id,
                tenant_id=tenant_id,
                external_subject="digest-plan",
                display_name="digest-plan",
                status="active",
                created_at=frozen_now,
                updated_at=frozen_now,
                version=1,
            )
            insert(
                connection,
                "projects",
                project_id=project_id,
                tenant_id=tenant_id,
                code="digest-plan",
                display_name="digest-plan",
                status="active",
                created_at=frozen_now,
                version=1,
            )
            insert(
                connection,
                "datasets",
                dataset_id=dataset_id,
                tenant_id=tenant_id,
                project_id=project_id,
                name="digest-plan",
                created_at=frozen_now,
            )
            # Enough rows that an equality on both columns is clearly more
            # selective than one on tenant_id alone.
            from saintvision.db.base import Base
            from saintvision.db import models  # noqa: F401

            versions = Base.metadata.tables["dataset_versions"]
            connection.execute(
                versions.insert(),
                [
                    {
                        "dataset_version_id": new_id("dataset_version"),
                        "tenant_id": tenant_id,
                        "dataset_id": dataset_id,
                        "version": f"v{index:05d}",
                        "content_sha256": wanted if index == 0 else _digest(),
                        "byte_size": 1,
                        "record_count": 1,
                        "uri": f"inv://datasets/digest-plan@{index}",
                        "created_at": frozen_now,
                    }
                    for index in range(2000)
                ],
            )
            connection.execute(text("ANALYZE dataset_versions"))

        query = (
            "EXPLAIN SELECT dataset_version_id FROM dataset_versions "
            "WHERE tenant_id = :tenant AND content_sha256 = :sha"
        )
        parameters = {"tenant": tenant_id, "sha": wanted}

        with owner_engine.begin() as connection:
            with_index = "\n".join(
                row[0] for row in connection.execute(text(query), parameters)
            )
        assert INDEX in with_index, with_index

        with owner_engine.begin() as connection:
            connection.execute(text(f"DROP INDEX {INDEX}"))
            without = "\n".join(
                row[0] for row in connection.execute(text(query), parameters)
            )
        # What it falls back to is the planner's business; that it can no longer
        # use this index is the observation. The plan is in the message so a
        # future change is readable rather than a bare failure.
        assert INDEX not in without, without
    finally:
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {INDEX} "
                    "ON dataset_versions (tenant_id, content_sha256)"
                )
            )
            # Leave the table as it was found: the rows were only here to give
            # the planner something to weigh.
            connection.execute(
                text("DELETE FROM dataset_versions WHERE dataset_id = :dataset"),
                {"dataset": dataset_id},
            )
            connection.execute(
                text("DELETE FROM datasets WHERE dataset_id = :dataset"),
                {"dataset": dataset_id},
            )
            connection.execute(text("ANALYZE dataset_versions"))


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
