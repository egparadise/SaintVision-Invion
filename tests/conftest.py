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


@pytest.fixture(scope="session")
def app_engine(migrated, database_url, owner_engine):
    """Engine connected as ``inv_app``: a non-owner, NOBYPASSRLS role.

    Tests must run as this role. Running them as the owner would pass even with
    RLS misconfigured, which is the exact failure this suite exists to catch.
    """
    with owner_engine.begin() as connection:
        connection.execute(text(f"ALTER ROLE {APP_ROLE} LOGIN PASSWORD 'apptestonly'"))

    # Swap the credentials in the URL, keeping host/port/database.
    from sqlalchemy.engine import make_url

    url = make_url(database_url).set(username=APP_ROLE, password="apptestonly")
    engine = create_engine(url, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_tables(app_engine, owner_engine):
    """Empty every table between tests, as the owner (RLS would block the app)."""
    tables = (
        "audit_events",
        "idempotency_records",
        "data_locations",
        "storage_contributions",
        "resource_snapshots",
        "resource_offers",
        "node_capabilities",
        "node_bootstrap_tokens",
        "nodes",
        "project_members",
        "projects",
        "user_roles",
        "roles",
        "users",
        "tenants",
    )
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
