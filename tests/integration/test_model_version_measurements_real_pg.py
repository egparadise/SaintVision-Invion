"""0054 against a real PostgreSQL: what only the database can say.

The migration has run (``migrated`` upgrades to head). Checked here: the
catalogue rows the migration's shape queries return; that ``verified_at``
cannot be set without a measurement nor a measurement id without
``verified_at`` (the CHECK), nor an id that is not a measurement (the key);
that the application role can read but not write the kernel table and sees
only its tenant's rows; that the owner cannot rewrite or delete a
measurement (the immutable trigger); that the service binds both columns in
one transaction and refuses a measurement of another version, of another
digest, or a second measurement after the first; and that an interrupted
run resumes through the real Alembic machinery to the same end state and
stops on a verified row nothing can bind.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from measurement_support import record_measurement
from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import lineage as lineage_service
from test_model_version_digest_scope_real_pg import _insert, _project_with_model

pytestmark = pytest.mark.postgres

MIGRATION = Path(__file__).resolve().parents[2] / "migrations/versions/0054_model_version_measurements.py"
MEASUREMENTS = "inv.model_version_measurements"
DIGEST = "5" * 64
OTHER = "6" * 64


def _module():
    spec = importlib.util.spec_from_file_location("migration_0054", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _module()


def _version(connection, *, tenant_id, model, now, digest=DIGEST, version="1"):
    version_id = new_id("model_version")
    _insert(
        connection, "model_versions",
        model_version_id=version_id, tenant_id=tenant_id, model_id=model["model_id"], version=version,
        stage="draft", content_sha256=digest, byte_size=1, uri=f"inv://models/{model['name']}@{version}",
        created_at=now,
    )
    return version_id


@pytest.fixture
def draft(owner_engine, two_tenants, frozen_now, clean_tables):
    """Tenant A: one draft version; tenant B: nothing. Returns the ids."""
    tenant_a, tenant_b = two_tenants
    with owner_engine.begin() as connection:
        model = _project_with_model(connection, tenant_id=tenant_a, now=frozen_now, label="seam")
        version_id = _version(connection, tenant_id=tenant_a, model=model, now=frozen_now)
    return {"tenant_a": tenant_a, "tenant_b": tenant_b, "model": model, "version_id": version_id, "now": frozen_now}


def _row(owner_engine, version_id):
    with owner_engine.begin() as connection:
        return connection.execute(
            text("SELECT verified_at, verified_measurement_id FROM model_versions WHERE model_version_id = :m"),
            {"m": version_id},
        ).one()


# ---------------------------------------------------------------- the catalogue


def test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated):
    with owner_engine.begin() as connection:
        assert connection.exec_driver_sql(M.MEASUREMENTS_PRESENT).fetchall()
        table = connection.exec_driver_sql(M.MEASUREMENTS_SHAPE).fetchall()
        column = connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
        fk = connection.exec_driver_sql(M.FK_SHAPE).fetchall()
        check = connection.exec_driver_sql(M.CHECK_SHAPE).fetchall()
    assert (sorted(table[0][0]), int(table[0][1])) == (M.EXPECTED_MEASUREMENT_COLUMNS, 1)
    assert [tuple(column[0])] == [M.EXPECTED_COLUMN]
    r = fk[0]
    assert (r[0], r[1], list(r[2]), list(r[3]), r[4], r[5], r[6], bool(r[7]), bool(r[8]), bool(r[9])) == M.EXPECTED_FK
    c = check[0]
    assert (c[0], c[1], bool(c[2])) == M.EXPECTED_CHECK


def test_the_application_role_may_update_the_new_column_and_nothing_else_new(owner_engine, migrated):
    with owner_engine.begin() as connection:
        grants = connection.execute(text(
            "SELECT column_name, privilege_type FROM information_schema.column_privileges "
            "WHERE table_schema = 'public' AND table_name = 'model_versions' AND grantee = 'inv_app' AND privilege_type = 'UPDATE'"
        )).fetchall()
    assert {g[0] for g in grants} == {"stage", "verified_at", "retention_pinned_until", "verified_measurement_id"}


# ---------------------------------------------------------------- the constraints


def test_verified_at_alone_is_refused_by_the_check(owner_engine, draft):
    with pytest.raises(IntegrityError, match=M.CHECK):
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE model_versions SET verified_at = :n WHERE model_version_id = :m"),
                {"n": draft["now"], "m": draft["version_id"]},
            )
    assert _row(owner_engine, draft["version_id"]) == (None, None)


def test_a_measurement_id_alone_is_refused_by_the_check(owner_engine, draft):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    with pytest.raises(IntegrityError, match=M.CHECK):
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE model_versions SET verified_measurement_id = :i WHERE model_version_id = :m"),
                {"i": measurement_id, "m": draft["version_id"]},
            )


def test_an_id_that_is_not_a_measurement_is_refused_by_the_key(owner_engine, draft):
    with pytest.raises(IntegrityError, match=M.FK):
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE model_versions SET verified_at = :n, verified_measurement_id = :i WHERE model_version_id = :m"),
                {"n": draft["now"], "i": new_id("model_measurement"), "m": draft["version_id"]},
            )


def test_a_measurement_of_another_tenant_is_refused_by_the_composite_key(owner_engine, draft):
    """Same id text, other tenant: the key is (tenant_id, measurement_id)."""
    with owner_engine.begin() as connection:
        model_b = _project_with_model(connection, tenant_id=draft["tenant_b"], now=draft["now"], label="seam-b")
        version_b = _version(connection, tenant_id=draft["tenant_b"], model=model_b, now=draft["now"])
    foreign = record_measurement(owner_engine, tenant_id=draft["tenant_b"], model_version_id=version_b, sha256=DIGEST)
    with pytest.raises(IntegrityError, match=M.FK):
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE model_versions SET verified_at = :n, verified_measurement_id = :i WHERE model_version_id = :m"),
                {"n": draft["now"], "i": foreign, "m": draft["version_id"]},
            )


def test_the_request_is_unique_per_tenant(owner_engine, draft):
    import uuid

    request_id = uuid.uuid4()
    record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, request_id=request_id)
    with pytest.raises(IntegrityError):
        record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, request_id=request_id)


# ---------------------------------------------------------------- who may do what to a measurement


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO inv.model_version_measurements (tenant_id, measurement_id) VALUES (:t, :i)",
        "UPDATE inv.model_version_measurements SET byte_size = 9 WHERE measurement_id = :i",
        "DELETE FROM inv.model_version_measurements WHERE measurement_id = :i",
    ],
    ids=["insert", "update", "delete"],
)
def test_the_application_role_cannot_write_a_measurement(app_sessionmaker, owner_engine, draft, statement):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    with pytest.raises(ProgrammingError, match="permission denied"):
        with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
            session.execute(text(statement), {"t": draft["tenant_a"], "i": measurement_id})


def test_the_application_role_reads_only_its_tenants_measurements(app_sessionmaker, owner_engine, draft):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    query = text("SELECT measurement_id FROM inv.model_version_measurements WHERE measurement_id = :i")
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        assert session.execute(query, {"i": measurement_id}).scalar_one() == measurement_id
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_b"]):
        assert session.execute(query, {"i": measurement_id}).fetchall() == []
    with app_sessionmaker() as session, session.begin():                     # no scope at all
        assert session.execute(query, {"i": measurement_id}).fetchall() == []


@pytest.mark.parametrize("verb", ["UPDATE inv.model_version_measurements SET byte_size = 9", "DELETE FROM inv.model_version_measurements"])
def test_even_the_owner_cannot_rewrite_or_delete_a_measurement(owner_engine, draft, verb):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    with pytest.raises(DBAPIError):
        with owner_engine.begin() as connection:
            connection.execute(text("SELECT set_config('inv.tenant_id', :t, true)"), {"t": str(draft["tenant_a"])})
            connection.execute(text(f"{verb} WHERE measurement_id = :i"), {"i": measurement_id})


# ---------------------------------------------------------------- the service through the seam


def _verify(session, draft, measurement_id, *, content_sha256=DIGEST):
    return lineage_service.verify_model_version(
        session, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"],
        measurement_id=measurement_id, content_sha256=content_sha256, now=draft["now"],
    )


def test_the_service_binds_both_columns_in_one_transaction(app_sessionmaker, owner_engine, draft):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        row = _verify(session, draft, measurement_id)
        assert row.verified_at == draft["now"] and row.verified_measurement_id == measurement_id
    assert _row(owner_engine, draft["version_id"]) == (draft["now"], measurement_id)


def test_the_same_measurement_again_is_a_no_op_and_another_is_refused(app_sessionmaker, owner_engine, draft):
    first = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    second = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        _verify(session, draft, first)
        assert _verify(session, draft, first).verified_measurement_id == first
        with pytest.raises(InvError, match="another measurement"):
            _verify(session, draft, second)
    assert _row(owner_engine, draft["version_id"]) == (draft["now"], first)


@pytest.mark.parametrize("case", ["unknown", "other-version", "other-digest", "other-size", "claimed-digest"])
def test_a_measurement_that_does_not_prove_this_version_is_refused_and_nothing_is_bound(app_sessionmaker, owner_engine, draft, case):
    tenant = draft["tenant_a"]
    claimed = DIGEST
    if case == "unknown":
        measurement_id = new_id("model_measurement")
    elif case == "other-version":
        with owner_engine.begin() as connection:
            other = _version(connection, tenant_id=tenant, model=draft["model"], now=draft["now"], digest=OTHER, version="2")
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=other, sha256=OTHER)
    elif case == "other-digest":
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=OTHER)
    elif case == "other-size":
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=DIGEST, byte_size=2)
    else:
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=DIGEST)
        claimed = OTHER
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        with pytest.raises(InvError):
            _verify(session, draft, measurement_id, content_sha256=claimed)
    assert _row(owner_engine, draft["version_id"]) == (None, None)


def test_another_tenants_measurement_is_not_found_through_the_seam(app_sessionmaker, owner_engine, draft):
    with owner_engine.begin() as connection:
        model_b = _project_with_model(connection, tenant_id=draft["tenant_b"], now=draft["now"], label="seam-b")
        version_b = _version(connection, tenant_id=draft["tenant_b"], model=model_b, now=draft["now"])
    foreign = record_measurement(owner_engine, tenant_id=draft["tenant_b"], model_version_id=version_b, sha256=DIGEST)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        with pytest.raises(InvError, match="measurement not found"):
            _verify(session, draft, foreign)


# ---------------------------------------------------------------- resume


def _rerun(database_url, monkeypatch):
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    with monkeypatch.context() as patch:
        patch.setenv("INV_DATABASE_URL", database_url)
        patch.setenv("INV_MIGRATION_DSN", database_url)
        command.upgrade(config, "head")


def _interrupt_after_the_table(owner_engine):
    """Table present, the public side gone, revision back at 0053."""
    with owner_engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS {M.CHECK}"))
        connection.execute(text(f"ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS {M.FK}"))
        connection.execute(text("ALTER TABLE model_versions DROP COLUMN IF EXISTS verified_measurement_id"))
        connection.execute(text("UPDATE alembic_version SET version_num = '0053_eval_suite_project_scope'"))


def _recorded(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_a_run_interrupted_after_the_table_resumes_and_converges(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    _interrupt_after_the_table(owner_engine)
    try:
        _rerun(database_url, monkeypatch)
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0054_model_version_measurements'"))
    test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated)
    assert _recorded(owner_engine) == "0054_model_version_measurements"


def test_a_resume_stops_on_a_verified_version_nothing_can_bind(owner_engine, database_url, migrated, draft, monkeypatch):
    """With the CHECK gone, a version verified the old way (timestamp only) is
    possible; the re-run names it and touches nothing until it is resolved."""
    _interrupt_after_the_table(owner_engine)
    try:
        with owner_engine.begin() as connection:
            connection.execute(
                text("UPDATE model_versions SET verified_at = :n WHERE model_version_id = :m"),
                {"n": draft["now"], "m": draft["version_id"]},
            )
        with pytest.raises(RuntimeError) as raised:
            _rerun(database_url, monkeypatch)
        assert draft["version_id"] in str(raised.value) and "reviewed data fix" in str(raised.value)
        assert _recorded(owner_engine) == "0053_eval_suite_project_scope"
        with owner_engine.begin() as connection:
            assert not connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()      # no DDL happened
            connection.execute(text("UPDATE model_versions SET verified_at = NULL WHERE model_version_id = :m"), {"m": draft["version_id"]})
        _rerun(database_url, monkeypatch)                                          # resolved: converges
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0054_model_version_measurements'"))
    test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated)


def test_a_table_of_that_name_without_the_tenant_policy_is_refused_on_resume(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    _interrupt_after_the_table(owner_engine)
    with owner_engine.begin() as connection:
        connection.execute(text(f"DROP POLICY tenant_isolation ON {MEASUREMENTS}"))
    try:
        with pytest.raises(RuntimeError, match="different definition"):
            _rerun(database_url, monkeypatch)
        assert _recorded(owner_engine) == "0053_eval_suite_project_scope"
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text(
                f"CREATE POLICY tenant_isolation ON {MEASUREMENTS} "
                "USING (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid) "
                "WITH CHECK (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid)"
            ))
        _rerun(database_url, monkeypatch)
        with owner_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0054_model_version_measurements'"))
    test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated)


def test_a_downgrade_refuses_while_a_measurement_exists(owner_engine, database_url, migrated, draft, monkeypatch):
    from alembic import command
    from alembic.config import Config

    record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    with monkeypatch.context() as patch:
        patch.setenv("INV_DATABASE_URL", database_url)
        patch.setenv("INV_MIGRATION_DSN", database_url)
        with pytest.raises(RuntimeError, match="discard"):
            command.downgrade(config, "0053_eval_suite_project_scope")
    assert _recorded(owner_engine) == "0054_model_version_measurements"
    test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated)
