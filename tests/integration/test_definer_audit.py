"""Actual PostgreSQL catalogue mutations must never produce an audit pass."""

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "definer_audit", ROOT / "tools/check_definer_functions.py"
)
audit_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_tool)
SUBJECT = "public.subject_kernel_link(uuid,character)"


def problems(dsn):
    return {p for finding in audit_tool.audit(dsn) for p in finding["problems"]}


@contextmanager
def mutated(postgres, change, undo):
    assert not problems(postgres.owner)
    with psycopg.connect(postgres.owner, autocommit=True) as conn:
        conn.execute(change)
    try:
        yield
    finally:
        with psycopg.connect(postgres.owner, autocommit=True) as conn:
            conn.execute(undo)
        assert not problems(postgres.owner)


def test_current_catalogue_matches_complete_policy(postgres):
    findings = audit_tool.audit(postgres.owner)
    assert len(findings) == 9
    assert not problems(postgres.owner)
    assert sum(f["policyKind"] == "retired" for f in findings) == 2
    result = subprocess.run(
        [sys.executable, "tools/check_definer_functions.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "INV_AUDIT_DSN": postgres.owner},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "matches_reviewed_policy"


@pytest.mark.parametrize(
    "signature,setup,cleanup",
    [
        ("public.cx01_no_args()", "", ""),
        ("public.node_by_certificate()", "", ""),
        (
            "audit_untrusted.node_by_certificate()",
            "CREATE SCHEMA audit_untrusted;",
            "DROP SCHEMA audit_untrusted;",
        ),
        # SQL LIKE 'pg_%' accidentally excludes this non-system schema.
        ("pgx.node_by_certificate()", "CREATE SCHEMA pgx;", "DROP SCHEMA pgx;"),
    ],
)
def test_unrecognized_function_and_certificate_overloads_are_rejected(
    postgres, signature, setup, cleanup
):
    change = setup + f"""
        CREATE FUNCTION {signature} RETURNS SETOF uuid LANGUAGE sql SECURITY DEFINER
        SET search_path=pg_catalog AS $$ SELECT tenant_id FROM public.tenants $$;
    """
    with mutated(postgres, change, f"DROP FUNCTION {signature};" + cleanup):
        assert "unrecognized_privileged_function" in problems(postgres.owner)


@pytest.mark.parametrize(
    "body",
    [
        "SELECT true /* current_setting('inv.tenant_id') */",
        "WITH ignored AS (SELECT current_setting('inv.tenant_id',true)) SELECT true",
    ],
)
def test_setting_text_or_unused_lookup_does_not_prove_binding(postgres, body):
    with psycopg.connect(postgres.owner) as conn:
        original = conn.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)", (SUBJECT,)
        ).fetchone()[0]
    change = f"""CREATE OR REPLACE FUNCTION public.subject_kernel_link(p_tenant_id uuid,p_user_id character)
        RETURNS TABLE(registered boolean) LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog AS $$ {body} $$"""
    with mutated(postgres, change, original):
        assert "definition_differs_from_policy" in problems(postgres.owner)


@pytest.mark.parametrize(
    "change,undo,expected",
    [
        (
            f"ALTER FUNCTION {SUBJECT} SET search_path=public,pg_catalog",
            f"ALTER FUNCTION {SUBJECT} SET search_path=pg_catalog",
            "definition_differs_from_policy",
        ),
        (
            f"ALTER FUNCTION {SUBJECT} RESET search_path",
            f"ALTER FUNCTION {SUBJECT} SET search_path=pg_catalog",
            "definition_differs_from_policy",
        ),
        (
            f"ALTER FUNCTION {SUBJECT} SECURITY INVOKER",
            f"ALTER FUNCTION {SUBJECT} SECURITY DEFINER",
            "expected_privileged_function_missing",
        ),
        (
            f"GRANT EXECUTE ON FUNCTION {SUBJECT} TO PUBLIC",
            f"REVOKE EXECUTE ON FUNCTION {SUBJECT} FROM PUBLIC",
            "execute_grants_differ_from_policy",
        ),
        (
            f"GRANT EXECUTE ON FUNCTION {SUBJECT} TO inv_app WITH GRANT OPTION",
            f"REVOKE GRANT OPTION FOR EXECUTE ON FUNCTION {SUBJECT} FROM inv_app",
            "execute_grants_differ_from_policy",
        ),
        (
            "GRANT EXECUTE ON FUNCTION public.run_committed_outputs(uuid,text) TO inv_app",
            "REVOKE EXECUTE ON FUNCTION public.run_committed_outputs(uuid,text) FROM inv_app",
            "execute_grants_differ_from_policy",
        ),
        (
            "GRANT EXECUTE ON FUNCTION public.apply_resource_offer(uuid,character,text,bigint) TO inv_app",
            "REVOKE EXECUTE ON FUNCTION public.apply_resource_offer(uuid,character,text,bigint) FROM inv_app",
            "execute_grants_differ_from_policy",
        ),
        (
            "GRANT CREATE ON SCHEMA public TO inv_app",
            "REVOKE CREATE ON SCHEMA public FROM inv_app",
            "runtime_can_create_in_trusted_schema",
        ),
        (
            "GRANT CREATE ON SCHEMA inv TO inv_kernel",
            "REVOKE CREATE ON SCHEMA inv FROM inv_kernel",
            "runtime_can_create_in_trusted_schema",
        ),
        (
            "ALTER ROLE inv_app BYPASSRLS",
            "ALTER ROLE inv_app NOBYPASSRLS",
            "runtime_role_bypasses_rls",
        ),
        (
            "UPDATE public.alembic_version SET version_num='unknown'",
            "UPDATE public.alembic_version SET version_num='0038_approval_review_snapshot'",
            "migration_revision_mismatch",
        ),
    ],
)
def test_definition_grants_roles_and_revision_changes_fail_closed(postgres, change, undo, expected):
    with mutated(postgres, change, undo):
        assert expected in problems(postgres.owner)


def test_missing_function_is_not_an_empty_success(postgres):
    with psycopg.connect(postgres.owner) as conn:
        original = conn.execute(
            "SELECT pg_get_functiondef(%s::regprocedure)", (SUBJECT,)
        ).fetchone()[0]
    undo = (
        original
        + f"; REVOKE ALL ON FUNCTION {SUBJECT} FROM PUBLIC; GRANT EXECUTE ON FUNCTION {SUBJECT} TO inv_app;"
    )
    with mutated(postgres, f"DROP FUNCTION {SUBJECT}", undo):
        assert "expected_privileged_function_missing" in problems(postgres.owner)


def test_runtime_must_not_assume_function_owner(postgres):
    with psycopg.connect(postgres.owner) as conn:
        owner = conn.execute("SELECT current_user").fetchone()[0]
    with mutated(
        postgres,
        sql.SQL("GRANT {} TO inv_app").format(sql.Identifier(owner)),
        sql.SQL("REVOKE {} FROM inv_app").format(sql.Identifier(owner)),
    ):
        assert "runtime_can_assume_function_owner" in problems(postgres.owner)


def test_empty_database_audit_is_unavailable_not_pass(postgres):
    name = "inv_audit_empty_" + uuid4().hex
    with psycopg.connect(os.environ["INV_TEST_ADMIN_DSN"], autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        result = subprocess.run(
            [sys.executable, "tools/check_definer_functions.py", "--json"],
            cwd=ROOT,
            env={**os.environ, "INV_AUDIT_DSN": make_conninfo(postgres.owner, dbname=name)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 2
        assert json.loads(result.stdout) == {
            "status": "unavailable",
            "error": "catalog_observation_failed",
            "unsafe": None,
        }
        assert not result.stderr
    finally:
        with psycopg.connect(os.environ["INV_TEST_ADMIN_DSN"], autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_project_lookup_denies_other_unset_and_empty_scope_with_real_login(env):
    role = "inv_audit_" + uuid4().hex[:20]
    password = uuid4().hex
    with psycopg.connect(env.owner, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'audit')",
            (env.tenant, uuid4().hex),
        )
        conn.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'audit','audit')",
            (env.tenant, env.project),
        )
        conn.execute(
            "INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)",
            (env.tenant, env.project),
        )
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        conn.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
    try:
        runtime = make_conninfo(env.owner, user=role, password=password)
        for scope, expected in [(env.tenant, True), (env.other, False), (None, False), ("", False)]:
            with psycopg.connect(runtime) as conn:
                assert conn.execute(
                    "SELECT current_user=session_user AND NOT rolsuper AND NOT rolbypassrls FROM pg_roles WHERE rolname=current_user"
                ).fetchone()[0]
                if scope is not None:
                    conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (scope,))
                assert conn.execute(
                    "SELECT linked,enabled FROM public.project_kernel_link(%s,%s)",
                    (env.tenant, env.project),
                ).fetchone() == (expected, expected)
    finally:
        with psycopg.connect(env.owner, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
