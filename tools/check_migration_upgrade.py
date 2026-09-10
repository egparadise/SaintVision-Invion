"""Verify both published heads upgrade in newly allocated disposable databases."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL


def main():
    admin = os.environ["INV_TEST_ADMIN_DSN"]
    root = Path(__file__).resolve().parents[1]
    for prior in (
        "0018_workspace_resume",
        "0010_canonical_resource_units",
        "0019_workspace_api_integration",
        "0020_shard_recovery",
        "0021_business_kernel",
        "0022_node_containment",
    ):
        name = "inv_upgrade_test_" + uuid4().hex
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            info = conninfo_to_dict(admin)
            url = URL.create(
                "postgresql+psycopg",
                username=info.get("user"),
                password=info.get("password"),
                host=info.get("host"),
                port=int(info.get("port", 5432)),
                database=name,
            )
            env = {**os.environ, "INV_MIGRATION_DSN": url.render_as_string(hide_password=False)}
            for target in (prior, "head", "head"):
                result = subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", target],
                    cwd=root,
                    env=env,
                    capture_output=True,
                )
                if result.returncode:
                    raise RuntimeError("Migration path failed: " + prior + " -> " + target)
            with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [
                    ("0023_containment_approvals",)
                ]
                assert conn.execute(
                    "SELECT rolsuper,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname='inv_kernel'"
                ).fetchone() == (False, False, False)
                assert conn.execute(
                    "SELECT has_column_privilege('inv_kernel','inv.control_epoch','epoch','UPDATE')"
                ).fetchone() == (False,)
                assert conn.execute(
                    "SELECT has_column_privilege('inv_kernel','inv.project_grants','enabled','UPDATE')"
                ).fetchone() == (False,)
            print("PASS: " + prior + " -> integrated head, replay, restricted runtime grants")
        finally:
            assert name.startswith("inv_upgrade_test_") and len(name) == 49
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Disposable migration validation failed; credential-bearing diagnostics suppressed"
        ) from None
