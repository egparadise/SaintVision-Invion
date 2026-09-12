"""Test fixtures.

Tests that need PostgreSQL are marked ``postgres`` and skip with a stated reason
when ``INV_TEST_DATABASE_URL`` is absent. A skipped test is reported as
``not_run``, never as a pass — the DB behaviour under test (RLS, NULLS NOT
DISTINCT, partition routing) has no meaningful substitute.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
import secrets
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_ENV = "INV_TEST_DATABASE_URL"
#: Migration-owned permission group; tests never change its login or password.
APP_ROLE = "inv_app"


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: requires a live PostgreSQL instance")


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get(TEST_DB_ENV)
    if not url:
        pytest.skip(f"{TEST_DB_ENV} is not set; PostgreSQL-backed tests not run")
    return url


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

    os.environ["INV_DATABASE_URL"] = database_url
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    with owner_engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
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
