"""Real login and cleanup without modifying a cluster-wide permission group."""
import pytest
from pathlib import Path
from sqlalchemy import text
from conftest import application_test_engine

pytestmark = pytest.mark.postgres


def group_state(owner_engine):
    with owner_engine.connect() as c:
        return c.execute(text("""SELECT rolcanlogin,rolpassword,rolsuper,rolbypassrls,
            rolcreatedb,rolcreaterole FROM pg_authid WHERE rolname='inv_app'""")).one()


@pytest.mark.parametrize("fail_body", [False, True])
def test_temporary_login_cleanup_and_group_preservation(migrated, database_url, owner_engine, fail_body):
    before = group_state(owner_engine)
    role = None
    try:
        with application_test_engine(database_url, owner_engine) as engine:
            with engine.connect() as c:
                role = c.execute(text("SELECT current_user")).scalar_one()
                assert role.startswith("inv_backend_login_")
                flags = c.execute(text("""SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,
                    pg_has_role(current_user,'inv_app','MEMBER') FROM pg_roles WHERE rolname=current_user""")).one()
                assert tuple(flags) == (False, False, False, False, True)
                assert c.execute(text("SELECT count(*) FROM public.tenants")).scalar_one() == 0
            if fail_body:
                raise RuntimeError("synthetic test-body failure")
    except RuntimeError as error:
        if not fail_body or str(error) != "synthetic test-body failure":
            raise
    with owner_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM pg_roles WHERE rolname=:role"), {"role": role}).scalar_one() == 0
    # Do not expose password hashes in pytest's assertion diagnostics.
    if before != group_state(owner_engine):
        raise AssertionError("Shared inv_app role flags or password changed")


def test_bootstrap_does_not_override_migration_group(migrated, owner_engine):
    before = group_state(owner_engine)
    with owner_engine.begin() as c:
        c.exec_driver_sql((Path(__file__).resolve().parents[1] / "deploy/init-db.sql").read_text())
    if before != group_state(owner_engine):
        raise AssertionError("Bootstrap changed the shared group")
