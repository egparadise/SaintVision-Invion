"""Test fixtures.

Tests that need PostgreSQL are marked ``postgres`` and skip with a stated reason
when ``INV_TEST_DATABASE_URL`` is absent. A skipped test is reported as
``not_run``, never as a pass — the DB behaviour under test (RLS, NULLS NOT
DISTINCT, partition routing) has no meaningful substitute.
"""

from __future__ import annotations

import datetime as dt
import os
import secrets
from contextlib import contextmanager
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_ENV = "INV_TEST_DATABASE_URL"
#: The non-owner role the application connects as. Created by the migration.
APP_ROLE = "inv_app"


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: requires a live PostgreSQL instance")


@pytest.fixture(scope="session")
def database_url() -> str:
    # Always allocate our own database. Never DROP SCHEMA in an operator's DB.
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy.engine import URL

    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.environ.get("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN for the combined backend suite")
        pytest.skip("INV_TEST_ADMIN_DSN is absent; PostgreSQL tests not run")
    name = "inv_backend_test_" + uuid.uuid4().hex
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    info = conninfo_to_dict(admin)
    url = URL.create(
        "postgresql+psycopg",
        username=info.get("user"),
        password=info.get("password"),
        host=info.get("host"),
        port=int(info.get("port", 5432)),
        database=name,
    )
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        assert name.startswith("inv_backend_test_") and len(name) == 49
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def owner_engine(database_url):
    """Engine connected as the schema owner. Used only to run migrations."""
    engine = create_engine(database_url, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migrated(owner_engine, database_url):
    """Run the Alembic migration once for the session."""
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("INV_DATABASE_URL", database_url)
        patch.setenv("INV_MIGRATION_DSN", database_url)
        command.upgrade(config, "head")
    return True


@contextmanager
def application_test_engine(database_url, owner_engine):
    """Owned temporary login inherits inv_app; leave cluster-wide groups intact."""
    from psycopg import sql
    from sqlalchemy.engine import make_url

    role = "inv_backend_login_" + uuid.uuid4().hex
    password = secrets.token_urlsafe(32)
    with owner_engine.begin() as connection:
        conn = connection.connection.driver_connection
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} INHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION").format(
            sql.Identifier(role), sql.Literal(password)))
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(APP_ROLE), sql.Identifier(role)))
    engine = None
    try:
        url = make_url(database_url).set(username=role, password=password)
        engine = create_engine(url, future=True)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        assert role.startswith("inv_backend_login_") and len(role) == 50
        with owner_engine.begin() as connection:
            connection.connection.driver_connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.fixture(scope="session")
def app_engine(migrated, database_url, owner_engine):
    """Real non-owner login; actual inherited migration grants and RLS apply."""
    with application_test_engine(database_url, owner_engine) as engine:
        yield engine


@pytest.fixture
def clean_tables(app_engine, owner_engine):
    """Empty every table between tests, as the owner (RLS would block the app).

    The list is derived from the model metadata rather than typed out. A
    hardcoded one went stale the moment S03 and S09 added tables, and the
    symptom was a later test seeing an earlier test's rows — which read as a
    product bug rather than a fixture bug.
    """
    from saintvision.db.base import Base
    from saintvision.db import models  # noqa: F401  (registers the tables)

    tables = [t.name for t in Base.metadata.sorted_tables]
    with owner_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    yield


@pytest.fixture
def app_sessionmaker(app_engine):
    return sessionmaker(bind=app_engine, expire_on_commit=False, future=True)


@pytest.fixture
def two_tenants(owner_engine, clean_tables):
    """Two tenants with one user each, inserted as the owner.

    Seeded outside RLS on purpose: the point of the isolation tests is what the
    *application* role can see, and seeding through it would beg the question.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    now = dt.datetime.now(dt.timezone.utc)
    with owner_engine.begin() as connection:
        for tenant, slug in ((tenant_a, "alpha"), (tenant_b, "beta")):
            connection.execute(
                text(
                    "INSERT INTO tenants (tenant_id, slug, display_name, created_at) "
                    "VALUES (:t, :s, :d, :n)"
                ),
                {"t": tenant, "s": slug, "d": slug.title(), "n": now},
            )
    return tenant_a, tenant_b


@pytest.fixture
def frozen_now() -> dt.datetime:
    """A fixed instant, so ordering assertions do not depend on wall clock."""
    return dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=dt.timezone.utc)
