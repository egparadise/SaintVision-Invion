"""0054 against a real PostgreSQL: what only the database can say.

The migration has run (``migrated`` upgrades to head). Checked here: the
kernel table's whole shape as the migration reads it and the reader's
rendered definition are exactly what the migration expects (so the pinned
policy hash is the hash of what exists); that ``verified_at`` cannot be set
without a measurement nor a measurement id without ``verified_at`` (the
CHECK), nor an id that is not a measurement (the key); that the application
role cannot name the kernel table at all -- not to write, not to read -- and
sees exactly its tenant's row through the tenant-bound reader; that the owner
cannot rewrite or delete a measurement (the immutable trigger); that the
service binds both columns in one transaction and refuses a measurement of
another version, of another digest, of another size (including a registered
size of 0, Codex #213 F2) or a second measurement after the first; and that
an interrupted run resumes through the real Alembic machinery to the same
end state, stops on a verified row nothing can bind, and stops on a
same-named kernel table whose security or constraint shape was tampered with
in any of the ways Codex #213 F1 lists -- before the public side is touched.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import uuid
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

CURRENT_HEAD = "0058_release_acceptance_resolver"

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


def _version(connection, *, tenant_id, model, now, digest=DIGEST, version="1", byte_size=1):
    version_id = new_id("model_version")
    _insert(
        connection, "model_versions",
        model_version_id=version_id, tenant_id=tenant_id, model_id=model["model_id"], version=version,
        stage="draft", content_sha256=digest, byte_size=byte_size, uri=f"inv://models/{model['name']}@{version}",
        created_at=now,
    )
    return version_id


@pytest.fixture
def draft(owner_engine, two_tenants, frozen_now, clean_tables):
    """Tenant A: one draft version of 1 byte; tenant B: nothing. Returns the ids."""
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


def _assert_catalogue_is_whole(owner_engine):
    with owner_engine.begin() as connection:
        assert connection.exec_driver_sql(M.MEASUREMENTS_PRESENT).fetchall()
        shape = M.kernel_shape(connection)
        reader = connection.exec_driver_sql(M.READER_PRESENT).fetchall()
        column = connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
        fk = connection.exec_driver_sql(M.FK_SHAPE).fetchall()
        check = connection.exec_driver_sql(M.CHECK_SHAPE).fetchall()
    for part, expected in M.EXPECTED_KERNEL_SHAPE.items():
        assert shape[part] == expected, part
    assert [r[0] for r in reader] == [M.reader_definition()]
    assert [tuple(column[0])] == [M.EXPECTED_COLUMN]
    r = fk[0]
    assert (r[0], r[1], list(r[2]), list(r[3]), r[4], r[5], r[6], bool(r[7]), bool(r[8]), bool(r[9])) == M.EXPECTED_FK
    c = check[0]
    assert (c[0], c[1], bool(c[2])) == M.EXPECTED_CHECK


# ---------------------------------------------------------------- the catalogue


def test_the_catalogue_shape_the_migration_reads_matches_what_it_expects(owner_engine, migrated):
    _assert_catalogue_is_whole(owner_engine)


def test_the_check_carries_the_single_convention_name(owner_engine, migrated):
    with owner_engine.begin() as connection:
        names = connection.execute(text(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'public.model_versions'::regclass AND conname LIKE '%verified_iff%'"
        )).scalars().all()
    assert names == [M.CHECK]


def test_the_reader_is_the_pinned_definition_executable_by_the_application_only(owner_engine, migrated):
    import hashlib
    import json

    with owner_engine.begin() as connection:
        definition = connection.execute(text("SELECT pg_get_functiondef('public.model_version_measurement(text)'::regprocedure)")).scalar_one()
        app = connection.execute(text("SELECT has_function_privilege('inv_app', 'public.model_version_measurement(text)', 'EXECUTE')")).scalar_one()
        kernel = connection.execute(text("SELECT has_function_privilege('inv_kernel', 'public.model_version_measurement(text)', 'EXECUTE')")).scalar_one()
        public = connection.execute(text("SELECT has_function_privilege(0, 'public.model_version_measurement(text)'::regprocedure, 'EXECUTE')")).scalar_one()
    policy = json.loads((Path(__file__).resolve().parents[2] / "tools/definer-policy.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(definition.encode()).hexdigest() == policy["functions"]["public.model_version_measurement(text)"]["definitionSHA256"]
    assert definition == M.reader_definition()
    assert app is True and kernel is False and public is False


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
    request_id = uuid.uuid4()
    record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, request_id=request_id)
    with pytest.raises(IntegrityError):
        record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, request_id=request_id)


# ---------------------------------------------------------------- who may do what to a measurement


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT measurement_id FROM inv.model_version_measurements WHERE measurement_id = :i",
        "INSERT INTO inv.model_version_measurements (tenant_id, measurement_id) VALUES (:t, :i)",
        "UPDATE inv.model_version_measurements SET byte_size = 9 WHERE measurement_id = :i",
        "DELETE FROM inv.model_version_measurements WHERE measurement_id = :i",
    ],
    ids=["select", "insert", "update", "delete"],
)
def test_the_application_role_cannot_name_the_kernel_table_at_all(app_sessionmaker, owner_engine, draft, statement):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    with pytest.raises(ProgrammingError, match="permission denied"):
        with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
            session.execute(text(statement), {"t": draft["tenant_a"], "i": measurement_id})


def test_the_application_role_reads_only_its_tenants_measurement_through_the_reader(app_sessionmaker, owner_engine, draft):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
    query = text("SELECT model_version_id, sha256, byte_size FROM public.model_version_measurement(:i)")
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        assert session.execute(query, {"i": measurement_id}).one() == (draft["version_id"], DIGEST, 1)
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


def _verify(session, draft, measurement_id, *, content_sha256=DIGEST, version_id=None):
    return lineage_service.verify_model_version(
        session, tenant_id=draft["tenant_a"], model_version_id=version_id or draft["version_id"],
        measurement_id=measurement_id, content_sha256=content_sha256, now=draft["now"],
    )


def test_the_service_binds_both_columns_in_one_transaction(app_sessionmaker, owner_engine, draft):
    measurement_id = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, draft["tenant_a"]):
        row = _verify(session, draft, measurement_id)
        assert row.verified_at == draft["now"] and row.verified_measurement_id == measurement_id
    assert _row(owner_engine, draft["version_id"]) == (draft["now"], measurement_id)


def test_the_same_measurement_again_is_a_no_op_and_another_is_refused(app_sessionmaker, owner_engine, draft):
    first = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
    second = record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
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
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=other, sha256=OTHER, byte_size=1)
    elif case == "other-digest":
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=OTHER, byte_size=1)
    elif case == "other-size":
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=DIGEST, byte_size=2)
    else:
        measurement_id = record_measurement(owner_engine, tenant_id=tenant, model_version_id=draft["version_id"], sha256=DIGEST, byte_size=1)
        claimed = OTHER
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        with pytest.raises(InvError):
            _verify(session, draft, measurement_id, content_sha256=claimed)
    assert _row(owner_engine, draft["version_id"]) == (None, None)


def test_a_registered_size_of_zero_is_a_size_and_only_a_zero_byte_measurement_proves_it(app_sessionmaker, owner_engine, draft):
    """Codex #213 F2: 0 is not an "unknown" sentinel that skips the comparison."""
    tenant = draft["tenant_a"]
    with owner_engine.begin() as connection:
        zero = _version(connection, tenant_id=tenant, model=draft["model"], now=draft["now"], digest=OTHER, version="0", byte_size=0)
    one_byte = record_measurement(owner_engine, tenant_id=tenant, model_version_id=zero, sha256=OTHER, byte_size=1)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        with pytest.raises(InvError, match="size"):
            _verify(session, draft, one_byte, content_sha256=OTHER, version_id=zero)
    assert _row(owner_engine, zero) == (None, None)
    zero_bytes = record_measurement(owner_engine, tenant_id=tenant, model_version_id=zero, sha256=OTHER, byte_size=0)
    with app_sessionmaker() as session, session.begin(), tenant_scope(session, tenant):
        _verify(session, draft, zero_bytes, content_sha256=OTHER, version_id=zero)
    assert _row(owner_engine, zero) == (draft["now"], zero_bytes)


def test_another_tenants_measurement_is_not_found_through_the_seam(app_sessionmaker, owner_engine, draft):
    with owner_engine.begin() as connection:
        model_b = _project_with_model(connection, tenant_id=draft["tenant_b"], now=draft["now"], label="seam-b")
        version_b = _version(connection, tenant_id=draft["tenant_b"], model=model_b, now=draft["now"])
    foreign = record_measurement(owner_engine, tenant_id=draft["tenant_b"], model_version_id=version_b, sha256=DIGEST, byte_size=1)
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
        command.upgrade(config, "0054_model_version_measurements")


def _interrupt_after_the_table(owner_engine):
    """Table and reader present, the public side gone, revision back at 0053."""
    with owner_engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS {M.CHECK}"))
        connection.execute(text(f"ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS {M.FK}"))
        connection.execute(text("ALTER TABLE model_versions DROP COLUMN IF EXISTS verified_measurement_id"))
        connection.execute(text("UPDATE alembic_version SET version_num = '0053_eval_suite_project_scope'"))


def _recorded(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _restore_head(owner_engine):
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE alembic_version SET version_num = :head"),
            {"head": CURRENT_HEAD},
        )


def test_a_run_interrupted_after_the_table_resumes_and_converges(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    _interrupt_after_the_table(owner_engine)
    try:
        _rerun(database_url, monkeypatch)
        assert _recorded(owner_engine) == "0054_model_version_measurements"
    finally:
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)
    assert _recorded(owner_engine) == CURRENT_HEAD


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
        assert _recorded(owner_engine) == "0054_model_version_measurements"
    finally:
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)


T = "inv.model_version_measurements"
POLICY = (
    f"CREATE POLICY tenant_isolation ON {T} "
    "USING (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid) "
    "WITH CHECK (tenant_id = nullif(current_setting('inv.tenant_id', true), '')::uuid)"
)
TRIGGER = f"CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON {T} FOR EACH ROW EXECUTE FUNCTION inv.immutable_record()"

#: Codex #213 F1: each tampering, and how to undo it. Every one must stop the
#: re-run before the public side is touched.
TAMPERINGS = {
    "rls-not-forced": ([f"ALTER TABLE {T} NO FORCE ROW LEVEL SECURITY"], [f"ALTER TABLE {T} FORCE ROW LEVEL SECURITY"]),
    "rls-disabled": ([f"ALTER TABLE {T} DISABLE ROW LEVEL SECURITY"], [f"ALTER TABLE {T} ENABLE ROW LEVEL SECURITY"]),
    "policy-true": (
        [f"DROP POLICY tenant_isolation ON {T}", f"CREATE POLICY tenant_isolation ON {T} USING (true) WITH CHECK (true)"],
        [f"DROP POLICY tenant_isolation ON {T}", POLICY],
    ),
    "policy-missing": ([f"DROP POLICY tenant_isolation ON {T}"], [POLICY]),
    # (a raw DISABLE TRIGGER is forbidden outside the integrity helper by
    # tests/test_db_integrity_static.py; the disabled state is covered by the
    # PG-free stand-in, the dropped trigger here)
    "trigger-dropped": ([f"DROP TRIGGER immutable ON {T}"], [TRIGGER]),
    "app-insert": ([f"GRANT INSERT ON {T} TO inv_app"], [f"REVOKE INSERT ON {T} FROM inv_app"]),
    "app-select": ([f"GRANT SELECT ON {T} TO inv_app"], [f"REVOKE SELECT ON {T} FROM inv_app"]),
    "public-select": ([f"GRANT SELECT ON {T} TO PUBLIC"], [f"REVOKE SELECT ON {T} FROM PUBLIC"]),
    "kernel-update": ([f"GRANT UPDATE ON {T} TO inv_kernel"], [f"REVOKE UPDATE ON {T} FROM inv_kernel"]),
    "request-unique-dropped": (
        [f"ALTER TABLE {T} DROP CONSTRAINT model_version_measurements_tenant_id_request_id_key"],
        [f"ALTER TABLE {T} ADD CONSTRAINT model_version_measurements_tenant_id_request_id_key UNIQUE (tenant_id, request_id)"],
    ),
    "byte-size-integer": ([f"ALTER TABLE {T} ALTER COLUMN byte_size TYPE integer"], [f"ALTER TABLE {T} ALTER COLUMN byte_size TYPE bigint"]),
    "digest-check-dropped": (
        [f"ALTER TABLE {T} DROP CONSTRAINT model_version_measurements_sha256_check"],
        [f"ALTER TABLE {T} ADD CONSTRAINT model_version_measurements_sha256_check CHECK (sha256 ~ '^[0-9a-f]{{64}}$')"],
    ),
}


@pytest.mark.parametrize("case", sorted(TAMPERINGS), ids=sorted(TAMPERINGS))
def test_a_tampered_kernel_table_of_that_name_is_refused_on_resume_before_the_public_side(
    owner_engine, database_url, migrated, clean_tables, monkeypatch, case
):
    tamper, restore = TAMPERINGS[case]
    _interrupt_after_the_table(owner_engine)
    with owner_engine.begin() as connection:
        for statement in tamper:
            connection.execute(text(statement))
    try:
        with pytest.raises(RuntimeError, match="different definition"):
            _rerun(database_url, monkeypatch)
        assert _recorded(owner_engine) == "0053_eval_suite_project_scope"
        with owner_engine.begin() as connection:
            assert not connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()      # nothing on the public side
    finally:
        with owner_engine.begin() as connection:
            for statement in restore:
                connection.execute(text(statement))
        _rerun(database_url, monkeypatch)
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)


def _owner_of(owner_engine, relation: str) -> str:
    with owner_engine.begin() as connection:
        return connection.execute(text(f"SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = '{relation}'::regclass")).scalar_one()


@pytest.mark.parametrize("how", ["owned-by-app", "app-member-of-owner"])
def test_a_kernel_table_a_runtime_role_owns_or_can_own_is_refused_on_resume(owner_engine, database_url, migrated, clean_tables, monkeypatch, how):
    """Codex #213 R2: the owner is not in the ACL. ``OWNER TO inv_app`` keeps
    inv_kernel's grants exactly as they are and hands the application the
    right to drop the policy, the trigger and the grants."""
    original = _owner_of(owner_engine, MEASUREMENTS)
    assert original not in ("inv_app", "inv_kernel")
    _interrupt_after_the_table(owner_engine)
    with owner_engine.begin() as connection:
        if how == "owned-by-app":
            connection.execute(text(f"ALTER TABLE {MEASUREMENTS} OWNER TO inv_app"))
        else:
            connection.execute(text(f'GRANT "{original}" TO inv_app'))
    try:
        with pytest.raises(RuntimeError, match=r"different definition"):
            _rerun(database_url, monkeypatch)
        assert _recorded(owner_engine) == "0053_eval_suite_project_scope"
        with owner_engine.begin() as connection:
            assert not connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
    finally:
        with owner_engine.begin() as connection:
            if how == "owned-by-app":
                connection.execute(text(f'ALTER TABLE {MEASUREMENTS} OWNER TO "{original}"'))
            else:
                connection.execute(text(f'REVOKE "{original}" FROM inv_app'))
        _rerun(database_url, monkeypatch)
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)


def test_a_reader_a_runtime_role_owns_is_refused_on_resume(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    with owner_engine.begin() as connection:
        original = connection.execute(text("SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = 'public.model_version_measurement(text)'::regprocedure")).scalar_one()
    _interrupt_after_the_table(owner_engine)
    with owner_engine.begin() as connection:
        connection.execute(text("ALTER FUNCTION public.model_version_measurement(text) OWNER TO inv_app"))
    try:
        with pytest.raises(RuntimeError, match=r"model_version_measurement\(text\) \(owner\)"):
            _rerun(database_url, monkeypatch)
        with owner_engine.begin() as connection:
            assert not connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text(f'ALTER FUNCTION public.model_version_measurement(text) OWNER TO "{original}"'))
        _rerun(database_url, monkeypatch)
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)


def test_a_reader_of_that_name_with_another_definition_is_refused_on_resume(owner_engine, database_url, migrated, clean_tables, monkeypatch):
    _interrupt_after_the_table(owner_engine)
    with owner_engine.begin() as connection:
        connection.execute(text("DROP FUNCTION public.model_version_measurement(text)"))
        connection.execute(text(M.READER_DDL.replace("AND m.measurement_id = p_measurement_id", "AND true")))
    try:
        with pytest.raises(RuntimeError, match="model_version_measurement"):
            _rerun(database_url, monkeypatch)
        with owner_engine.begin() as connection:
            assert not connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
    finally:
        with owner_engine.begin() as connection:
            connection.execute(text("DROP FUNCTION public.model_version_measurement(text)"))
        _rerun(database_url, monkeypatch)
        _restore_head(owner_engine)
    _assert_catalogue_is_whole(owner_engine)


def test_a_downgrade_refuses_while_a_measurement_exists(owner_engine, database_url, migrated, draft, monkeypatch):
    from alembic import command
    from alembic.config import Config

    record_measurement(owner_engine, tenant_id=draft["tenant_a"], model_version_id=draft["version_id"], sha256=DIGEST)
    # Preconditions stated, so a database left behind by another test cannot
    # turn this into a no-op downgrade that "did not raise".
    assert _recorded(owner_engine) == CURRENT_HEAD
    with owner_engine.begin() as connection:
        assert connection.exec_driver_sql(M.MEASUREMENT_ROWS).scalar() >= 1
        assert connection.exec_driver_sql(M.COLUMN_SHAPE).fetchall()
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("INV_DATABASE_URL", database_url)
            patch.setenv("INV_MIGRATION_DSN", database_url)
            with pytest.raises(RuntimeError, match="discard"):
                command.downgrade(config, "0053_eval_suite_project_scope")
        # PostgreSQL transactional DDL keeps the complete current head when
        # 0054 refuses; it must not leave the shared test database half-downgraded.
        assert _recorded(owner_engine) == CURRENT_HEAD
    finally:
        with monkeypatch.context() as patch:
            patch.setenv("INV_DATABASE_URL", database_url)
            patch.setenv("INV_MIGRATION_DSN", database_url)
            command.upgrade(config, CURRENT_HEAD)
    _assert_catalogue_is_whole(owner_engine)
