"""Real Alembic guard tests own their entire Docker cluster, never an ambient DSN."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from sqlalchemy.engine import URL
import pytest

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, env=None):
    result = subprocess.run(['docker', *args], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, 'Isolated Docker operation failed (diagnostics suppressed)'
    return result.stdout.strip()


@pytest.fixture(scope='module')
def isolated_cluster():
    image = os.environ.get('INV_TEST_ROLE_GUARD_IMAGE')
    if not image:
        pytest.skip('Explicit local PostgreSQL image required; ambient databases are never used')
    name = 'sv-role-guard-' + uuid4().hex
    password = secrets.token_urlsafe(32)
    container = docker('run', '-d', '--name', name, '--label', 'ai.saintvision.guard=' + name,
                       '--memory', '512m', '--cpus', '1', '--pids-limit', '128',
                       '--tmpfs', '/var/lib/postgresql/data', '--publish', '127.0.0.1::5432',
                       '--env', 'POSTGRES_PASSWORD', image,
                       env={**os.environ, 'POSTGRES_PASSWORD': password})
    try:
        port = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', container))['5432/tcp'][0]['HostPort']
        dsn = make_conninfo(host='127.0.0.1', port=port, user='postgres', password=password,
                           dbname='postgres', connect_timeout=2)
        for _ in range(100):
            try:
                with psycopg.connect(dsn) as conn:
                    conn.execute('SELECT 1')
                break
            except psycopg.OperationalError:
                time.sleep(.1)
        else:
            pytest.fail('Owned test PostgreSQL unavailable')
        yield dsn
    finally:
        assert docker('inspect', '--format', '{{index .Config.Labels "ai.saintvision.guard"}}', container) == name
        docker('rm', '-f', container)


@pytest.fixture
def guard_database(isolated_cluster):
    name = 'guard_' + uuid4().hex
    with psycopg.connect(isolated_cluster, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(isolated_cluster, dbname=name)
    try:
        yield dsn
    finally:
        with psycopg.connect(isolated_cluster, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            # These names exist only in the cluster created above for this module.
            conn.execute('DROP ROLE IF EXISTS inv_app')
            conn.execute('DROP ROLE IF EXISTS inv_kernel')


def upgrade(dsn):
    info = conninfo_to_dict(dsn)
    url = URL.create('postgresql+psycopg', username=info['user'], password=info['password'],
                     host=info['host'], port=int(info['port']), database=info['dbname'])
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
                            env={**os.environ, 'INV_MIGRATION_DSN': url.render_as_string(hide_password=False)},
                            capture_output=True, text=True, timeout=60)
    return result.returncode, 'Unsafe migration permission group' in result.stderr


@pytest.mark.parametrize('role', ['inv_app', 'inv_kernel'])
@pytest.mark.parametrize('flag', ['LOGIN', 'SUPERUSER', 'BYPASSRLS', 'CREATEDB', 'CREATEROLE', 'REPLICATION'])
def test_unsafe_predecessor_refused_before_schema_write(guard_database, role, flag):
    with psycopg.connect(guard_database) as conn:
        conn.execute(sql.SQL('CREATE ROLE {} {}').format(sql.Identifier(role), sql.SQL(flag)))
        before = conn.execute('SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
    code, guard = upgrade(guard_database)
    assert code != 0 and guard
    with psycopg.connect(guard_database) as conn:
        assert conn.execute("SELECT to_regclass('public.alembic_version'),to_regnamespace('inv')").fetchone() == (None, None)
        assert conn.execute('SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s', (role,)).fetchone() == before


def test_absent_then_safe_groups_allow_real_upgrade_and_replay(guard_database):
    assert upgrade(guard_database) == (0, False)
    assert upgrade(guard_database) == (0, False)
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    current_head = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
    with psycopg.connect(guard_database) as conn:
        assert conn.execute('SELECT version_num FROM public.alembic_version').fetchone() == (current_head,)
        assert conn.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('inv_app','inv_kernel') AND NOT (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)").fetchone() == (2,)
