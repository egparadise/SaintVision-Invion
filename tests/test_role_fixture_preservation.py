"""The legacy worktree must not reactivate a cluster-wide application login."""
import pytest
from sqlalchemy import text
from conftest import application_test_engine

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize('fail_body', [False, True])
def test_application_fixture_preserves_group_and_cleans_temporary_login(migrated, database_url, owner_engine, fail_body):
    def snapshot():
        with owner_engine.connect() as c:
            flags = tuple(c.execute(text("SELECT rolcanlogin,rolpassword IS NOT NULL FROM pg_authid WHERE rolname='inv_app'")).one())
            roles = set(c.execute(text("SELECT rolname FROM pg_roles WHERE rolname LIKE 'inv_backend_login_%'")).scalars())
            return flags, roles
    before = snapshot()
    caught = False
    try:
        with application_test_engine(database_url, owner_engine) as engine:
            with engine.connect() as c:
                username = c.execute(text('SELECT current_user')).scalar_one()
            assert username != 'inv_app' and username.startswith('inv_backend_login_')
            assert snapshot()[0] == before[0]
            if fail_body:
                raise RuntimeError('synthetic-body-failure')
    except RuntimeError:
        caught = True
    assert caught is fail_body
    assert snapshot() == before
