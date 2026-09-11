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
        "0023_containment_approvals",
        "0025_workspace_start",
        "0025_workspace_tool_choice",
        "0026_subject_kernel_link",
        "0027_business_api_guards",
    ):
        name = "inv_upgrade_test_" + uuid4().hex
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            sentinel = uuid4()
            preserved_workspace = None
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
                if target == prior and prior in {"0023_containment_approvals", "0025_workspace_start", "0025_workspace_tool_choice"}:
                    with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                        conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'preserve-me')",
                                     (sentinel, 'upgrade-'+sentinel.hex))
                        if prior == "0025_workspace_tool_choice":
                            from saintvision.ids import new_id
                            user, project, preserved_workspace = new_id('user'), new_id('project'), new_id('workspace')
                            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,'synthetic','preserve')",(sentinel,user))
                            conn.execute("INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'preserve','preserve')",(sentinel,project))
                            conn.execute("INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,created_by_user_id,tool_name) VALUES(%s,%s,%s,'preserve',%s,'codex-cli')",(sentinel,project,preserved_workspace,user))
            with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [
                    ("0028_result_readiness_merge",)
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
                assert conn.execute("""SELECT
                    has_table_privilege('inv_app','inv.business_admin_grants','INSERT'),
                    has_table_privilege('inv_app','inv.business_admin_grants','SELECT'),
                    has_table_privilege('inv_kernel','inv.business_admin_grants','UPDATE')""").fetchone() == (False,False,False)
                if prior in {"0023_containment_approvals", "0025_workspace_start", "0025_workspace_tool_choice"}:
                    assert conn.execute("SELECT display_name FROM public.tenants WHERE tenant_id=%s",(sentinel,)).fetchone()==('preserve-me',)
                if preserved_workspace:
                    assert conn.execute("SELECT tool_name FROM public.workspaces WHERE workspace_id=%s",(preserved_workspace,)).fetchone()==('codex-cli',)
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
