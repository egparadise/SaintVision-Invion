"""Real PostgreSQL, unique disposable database; never reset an existing schema."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest
from inv.db import Database
from inv.ids import new_id
from inv.runs import RunStore
from inv.leases import LeaseStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_provision import provision_disposable_database  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres():
    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    name = "inv_test_" + uuid4().hex
    role = "inv_app_" + uuid4().hex[:20]
    password = uuid4().hex
    owner = make_conninfo(admin, dbname=name)
    runtime = make_conninfo(owner, user=role, password=password)

    def create_database():
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    def create_role():
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )

    def prepare():
        # Test the real Alembic entry point as well as all SQL functions/constraints.
        from sqlalchemy.engine import URL

        info = psycopg.conninfo.conninfo_to_dict(owner)
        url = URL.create(
            "postgresql+psycopg",
            username=info.get("user"),
            password=info.get("password"),
            host=info.get("host"),
            port=int(info.get("port", 5432)),
            database=name,
        )
        env = {
            **os.environ,
            "INV_MIGRATION_DSN": url.render_as_string(hide_password=False),
            "INV_DATABASE_URL": url.render_as_string(hide_password=False),
        }
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        # Migration errors can contain credentials: never include subprocess output.
        assert result.returncode == 0, "Alembic migration failed (credential-bearing diagnostics suppressed)"
        with psycopg.connect(owner) as conn:
            # Use the production migration's least-privilege group, not a test-only
            # permission recipe which could hide a missing deployment grant.
            conn.execute(sql.SQL("GRANT inv_kernel TO {}").format(sql.Identifier(role)))
        return SimpleNamespace(owner=owner, runtime=runtime)

    def drop_database():
        assert name.startswith("inv_test_") and len(name) == 41  # only this run's unique name
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))

    def drop_role():
        assert role.startswith("inv_app_")
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))

    # Cleanup structure is entered before the first allocation; only resources that were
    # actually created are dropped, each independently (VB-FIX-01).
    yield from provision_disposable_database(
        create_database=create_database, create_role=create_role,
        prepare=prepare, drop_database=drop_database, drop_role=drop_role,
    )


@pytest.fixture
def env(postgres):
    epoch = str(uuid4())
    tenant = str(uuid4())
    other = str(uuid4())
    project = new_id("prj")
    node = new_id("nod")
    resource = new_id("res")
    with psycopg.connect(postgres.owner) as conn:
        conn.execute(
            "INSERT INTO inv.control_epoch(singleton,epoch) VALUES (true,%s) ON CONFLICT(singleton) DO UPDATE SET epoch=excluded.epoch",
            (epoch,),
        )
        conn.execute(
            "INSERT INTO inv.tenants VALUES (%s,'synthetic'),(%s,'other')",
            (tenant, other),
        )
        conn.execute("INSERT INTO inv.projects VALUES (%s,%s)", (tenant, project))
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES (%s,%s,'online',%s,0)",
            (tenant, node, epoch),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES (%s,%s,%s,'cpu',10,10)",
            (tenant, resource, node),
        )
    db = Database(postgres.runtime, recovery_epoch=epoch)
    return SimpleNamespace(
        **vars(postgres),
        db=db,
        epoch=epoch,
        tenant=tenant,
        other=other,
        project=project,
        node=node,
        resource=resource,
        runs=RunStore(db),
        leases=LeaseStore(db),
    )
