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
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
    owner = make_conninfo(admin, dbname=name)
    runtime = make_conninfo(owner, user=role, password=password)
    try:
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
        }
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        # Migration errors can contain credentials: never include subprocess output.
        assert (
            result.returncode == 0
        ), "Alembic migration failed (credential-bearing diagnostics suppressed)"
        with psycopg.connect(owner) as conn:
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA inv TO {}").format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL(
                    "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA inv TO {}"
                ).format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA inv TO {}").format(
                    sql.Identifier(role)
                )
            )
            conn.execute(
                sql.SQL(
                    "REVOKE INSERT,UPDATE,DELETE ON inv.control_epoch,inv.evidence,inv.checkpoints FROM {}"
                ).format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL("GRANT INSERT ON inv.evidence,inv.checkpoints TO {}").format(
                    sql.Identifier(role)
                )
            )
            # SELECT FOR SHARE needs UPDATE privilege. Only the fixed sentinel may be named;
            # CHECK(singleton) prevents changing it, and epoch itself remains read-only.
            conn.execute(
                sql.SQL("GRANT UPDATE(singleton) ON inv.control_epoch TO {}").format(
                    sql.Identifier(role)
                )
            )
            conn.execute(
                sql.SQL(
                    "REVOKE INSERT,UPDATE,DELETE ON inv.project_grants FROM {}"
                ).format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL(
                    "GRANT UPDATE(lock_sentinel) ON inv.project_grants TO {}"
                ).format(sql.Identifier(role))
            )
            conn.execute(
                sql.SQL(
                    "REVOKE UPDATE,DELETE ON inv.approval_votes,inv.approval_dispatches,inv.approval_audit FROM {}"
                ).format(sql.Identifier(role))
            )
        yield SimpleNamespace(owner=owner, runtime=runtime)
    finally:
        # Only the unique name created above is eligible for teardown.
        assert name.startswith("inv_test_") and len(name) == 41
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


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
        leases=LeaseStore(db)
    )
