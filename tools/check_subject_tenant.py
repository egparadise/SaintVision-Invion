"""Reproduce the historical leak and verify applied guards in a disposable DB.

Never accepts an existing database as its test target. All observations use a
separate LOGIN role inheriting only inv_app, not an owner or SET ROLE session.
Only synthetic booleans, revision IDs and function hashes are public evidence.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL


def verify():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from saintvision.ids import new_id
    from migration_graph import chain

    admin = os.environ["INV_TEST_ADMIN_DSN"]
    name = "inv_subject_test_" + uuid4().hex
    role, password = "inv_subject_" + uuid4().hex[:20], uuid4().hex
    owner = make_conninfo(admin, dbname=name)
    runtime = make_conninfo(owner, user=role, password=password)
    info = conninfo_to_dict(owner)
    url = URL.create(
        "postgresql+psycopg",
        username=info.get("user"),
        password=info.get("password"),
        host=info.get("host"),
        port=int(info.get("port", 5432)),
        database=name,
    )
    environment = {**os.environ, "INV_MIGRATION_DSN": url.render_as_string(hide_password=False)}
    tenant, other = uuid4(), uuid4()
    user, subject = new_id("user"), "oidc:" + uuid4().hex + uuid4().hex
    rows = []
    expected_head = chain()[-1].revision

    def upgrade(target):
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", target],
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=90,
        )
        if r.returncode:
            raise RuntimeError("Disposable subject migration failed at " + target)

    def observe(scope, asked_tenant=tenant):
        with psycopg.connect(runtime) as c:
            restricted = c.execute(
                """SELECT NOT rolsuper AND NOT rolbypassrls
                AND pg_has_role(current_user,'inv_app','MEMBER')
                AND NOT pg_has_role(current_user,'inv_kernel','MEMBER')
                AND current_user=session_user FROM pg_roles WHERE rolname=current_user"""
            ).fetchone()[0]
            assert restricted
            if scope is not None:
                c.execute("SELECT set_config('inv.tenant_id',%s,true)", (str(scope),))
            return c.execute(
                "SELECT registered FROM public.subject_kernel_link(%s,%s)", (asked_tenant, user)
            ).fetchone()[0]

    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        c.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
    try:
        stages = [
            "0026_subject_kernel_link",
            "0028_result_readiness_merge",
            "0030_provisioning_integrity",
            "0031_resource_offer_integrity",
            "head",
        ]
        for index, target in enumerate(stages):
            upgrade(target)
            if index == 0:
                with psycopg.connect(owner) as c:
                    c.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
                    c.execute(
                        "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'scope A'),(%s,%s,'scope B')",
                        (tenant, uuid4().hex, other, uuid4().hex),
                    )
                    c.execute(
                        "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'subject probe')",
                        (tenant, user, subject),
                    )
                    c.execute(
                        "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                        (tenant, subject, user),
                    )
            with psycopg.connect(owner) as c:
                definition, security_definer, config = c.execute(
                    """SELECT pg_get_functiondef(p.oid),p.prosecdef,p.proconfig
                    FROM pg_proc p WHERE p.oid='public.subject_kernel_link(uuid,character)'::regprocedure"""
                ).fetchone()
                heads = sorted(r[0] for r in c.execute("SELECT version_num FROM alembic_version"))
            same, cross, unset, empty = observe(tenant), observe(other), observe(None), observe("")
            vulnerable = index == 0
            assert (same, cross, unset, empty) == (True, vulnerable, vulnerable, vulnerable)
            assert security_definer and any(s.startswith("search_path=") for s in config)
            rows.append(
                dict(
                    requestedRevision=target,
                    appliedRevisions=heads,
                    functionSHA256=hashlib.sha256(definition.encode()).hexdigest(),
                    sameTenant=same,
                    crossTenant=cross,
                    unsetScope=unset,
                    emptyScope=empty,
                    historicalLeakExpected=vulnerable,
                    restrictedLogin=True,
                )
            )
        assert heads == [expected_head]
        for change in ("suspended", "subject-mismatch", "disabled"):
            with psycopg.connect(owner) as c:
                c.execute(
                    "UPDATE public.users SET status=%s,external_subject=%s WHERE tenant_id=%s AND user_id=%s",
                    (
                        "suspended" if change == "suspended" else "active",
                        "oidc:" + "f" * 64 if change == "subject-mismatch" else subject,
                        tenant,
                        user,
                    ),
                )
                c.execute(
                    "UPDATE inv.business_subjects SET enabled=%s WHERE tenant_id=%s AND user_id=%s",
                    (change != "disabled", tenant, user),
                )
            assert observe(tenant) is False
        # A no-op upgrade must not restore the historical function.
        upgrade("head")
        assert observe(other) is False
        return dict(
            expectedHead=expected_head,
            stages=rows,
            currentAccountChecks=True,
            scope="disposable-postgresql-restricted-business-login-not-production",
        )
    finally:
        assert name.startswith("inv_subject_test_") and len(name) == 49
        with psycopg.connect(admin, autocommit=True) as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), sort_keys=True))
    except Exception:
        raise SystemExit(
            "Subject boundary validation failed; private diagnostics suppressed"
        ) from None
