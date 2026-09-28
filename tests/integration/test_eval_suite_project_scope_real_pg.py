"""0053 against a real PostgreSQL: what the column and the foreign key do.

The migration has run by the time these start (the ``migrated`` fixture
upgrades to head). What is checked here is what only the database can say: the
column is nullable, the composite foreign key refuses a project of another
tenant and a project that does not exist, an unscoped suite stays ``NULL``,
and a run interrupted after the column was added resumes through the real
Alembic machinery to the same end state.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from saintvision.ids import new_id
from test_model_version_digest_scope_real_pg import _insert

pytestmark = pytest.mark.postgres

FK = "fk_eval_suites_tenant_id_project_id"
INDEX = "ix_eval_suites_tenant_id_project_id"


def _project(connection, *, tenant_id, now, label):
    project_id = new_id("project")
    _insert(
        connection, "projects",
        project_id=project_id, tenant_id=tenant_id, code=label, display_name=label,
        status="active", created_at=now, version=1,
    )
    return project_id


def _suite(connection, *, tenant_id, now, label, project_id=None):
    suite_id = new_id("eval_suite")
    values = dict(
        suite_id=suite_id, tenant_id=tenant_id, name=f"suite-{label}", version="1",
        case_count=0, definition_sha256="f" * 64, created_at=now,
    )
    if project_id is not None:
        values["project_id"] = project_id
    _insert(connection, "eval_suites", **values)
    return suite_id


def _catalogue(owner_engine):
    with owner_engine.begin() as connection:
        column = connection.execute(
            text("SELECT data_type, character_maximum_length, is_nullable FROM information_schema.columns "
                 "WHERE table_name = 'eval_suites' AND column_name = 'project_id'")
        ).fetchall()
        constraints = {r[0] for r in connection.execute(
            text("SELECT conname FROM pg_constraint WHERE conrelid = 'eval_suites'::regclass")
        ).fetchall()}
        indexes = {r[0] for r in connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'eval_suites'")
        ).fetchall()}
    return column, constraints, indexes


def test_the_catalogue_carries_the_nullable_column_the_foreign_key_and_the_index(owner_engine, migrated):
    column, constraints, indexes = _catalogue(owner_engine)
    assert column == [("character", 30, "YES")]
    assert FK in constraints and INDEX in indexes


def test_an_existing_suite_stays_unscoped_and_a_scoped_one_binds_to_its_project(owner_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        project = _project(connection, tenant_id=tenant, now=frozen_now, label="scope-a")
        legacy = _suite(connection, tenant_id=tenant, now=frozen_now, label="legacy")
        scoped = _suite(connection, tenant_id=tenant, now=frozen_now, label="scoped", project_id=project)
    with owner_engine.begin() as connection:
        rows = dict(connection.execute(
            text("SELECT suite_id, project_id FROM eval_suites WHERE suite_id IN (:a, :b)"), {"a": legacy, "b": scoped}
        ).fetchall())
    assert rows[legacy] is None and rows[scoped] == project


def test_a_project_of_another_tenant_is_refused_by_the_composite_key(owner_engine, two_tenants, frozen_now, clean_tables):
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        theirs = _project(connection, tenant_id=tenant_b, now=frozen_now, label="theirs")
    with pytest.raises(IntegrityError) as raised:
        with owner_engine.begin() as connection:
            _suite(connection, tenant_id=tenant_a, now=frozen_now, label="cross", project_id=theirs)
    assert FK in str(raised.value)


def test_a_project_that_does_not_exist_is_refused(owner_engine, two_tenants, frozen_now, clean_tables):
    tenant, _ = two_tenants
    with pytest.raises(IntegrityError) as raised:
        with owner_engine.begin() as connection:
            _suite(connection, tenant_id=tenant, now=frozen_now, label="ghost", project_id=new_id("project"))
    assert FK in str(raised.value)


def test_a_run_interrupted_after_the_column_resumes_and_converges(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    """The catalogue is put back into the interrupted state -- column present,
    foreign key and index gone, revision still 0052 -- and the migration is
    re-run through the real Alembic machinery. It must add only what is
    missing and record 0053."""
    from alembic import command
    from alembic.config import Config

    with owner_engine.begin() as connection:
        connection.execute(text(f"DROP INDEX IF EXISTS {INDEX}"))
        connection.execute(text(f"ALTER TABLE eval_suites DROP CONSTRAINT IF EXISTS {FK}"))
        connection.execute(text("UPDATE alembic_version SET version_num = '0052_model_version_digest_scope'"))

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("INV_DATABASE_URL", database_url)
            patch.setenv("INV_MIGRATION_DSN", database_url)
            command.upgrade(config, "head")
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0053_eval_suite_project_scope'"))

    column, constraints, indexes = _catalogue(owner_engine)
    assert column == [("character", 30, "YES")] and FK in constraints and INDEX in indexes
    with owner_engine.begin() as connection:
        recorded = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert recorded == "0053_eval_suite_project_scope"


def test_a_resume_with_an_orphan_reference_is_refused_before_the_foreign_key(owner_engine, database_url, migrated, two_tenants, frozen_now, clean_tables, monkeypatch):
    """The data check is real: with the foreign key removed, a suite that points
    at a project of its tenant that is gone makes the re-run stop with the
    suite named, and nothing is re-added."""
    from alembic import command
    from alembic.config import Config

    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE eval_suites DROP CONSTRAINT IF EXISTS {FK}"))
        orphan = _suite(connection, tenant_id=tenant, now=frozen_now, label="orphan", project_id=new_id("project"))
        connection.execute(text("UPDATE alembic_version SET version_num = '0052_model_version_digest_scope'"))

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("INV_DATABASE_URL", database_url)
            patch.setenv("INV_MIGRATION_DSN", database_url)
            with pytest.raises(RuntimeError) as raised:
                command.upgrade(config, "head")
        assert orphan in str(raised.value)
        _, constraints, _ = _catalogue(owner_engine)
        assert FK not in constraints
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text("DELETE FROM eval_suites WHERE suite_id = :s"), {"s": orphan})
            connection.execute(text(f"ALTER TABLE eval_suites ADD CONSTRAINT {FK} FOREIGN KEY (tenant_id, project_id) "
                                    "REFERENCES projects (tenant_id, project_id)"))
            connection.execute(text("UPDATE alembic_version SET version_num = '0053_eval_suite_project_scope'"))
