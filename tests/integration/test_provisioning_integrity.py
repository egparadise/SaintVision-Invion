"""Real PostgreSQL provisioning, current authority, atomic failure and contention."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import json
import os
import subprocess
import threading
import time
from uuid import UUID, uuid4

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import provision_account as provisioning
from saintvision.ids import new_id


@pytest.fixture
def target(env):
    issuer, sub = "https://synthetic.invalid", "account"
    value = provisioning.identity(
        env.tenant, new_id("project"), new_id("user"), issuer, sub, "request"
    )
    with psycopg.connect(env.owner) as c:
        c.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'provision test')",
            (env.tenant, uuid4().hex),
        )
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'test')",
            (env.tenant, value["user"], value["subject"]),
        )
        c.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'test','test')",
            (env.tenant, value["project"]),
        )
        c.execute(
            "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,'owner')",
            (env.tenant, value["project"], value["user"]),
        )
    return value


def apply(env, target):
    with psycopg.connect(env.owner, autocommit=True) as c:
        return provisioning.apply(c, reason="synthetic integration acceptance", **target)


def count(env, target, table):
    assert table in {
        "projects",
        "business_projects",
        "business_subjects",
        "project_grants",
        "account_provisioning_events",
    }
    with psycopg.connect(env.owner) as c:
        return c.execute(
            "SELECT count(*) FROM inv." + table + " WHERE tenant_id=%s", (target["tenant"],)
        ).fetchone()[0]


def test_check_is_read_only_and_apply_is_audited_idempotently(env, target):
    with psycopg.connect(env.owner, autocommit=True) as c:
        before = provisioning.inspect(c, **target)
    assert not before["linked"] and not before["executionReady"] and not before["blockers"]
    assert "projectGrant" in before["missing"]
    assert count(env, target, "business_subjects") == 0
    result = apply(env, target)
    assert result["linked"] and not result["executionReady"] and result["auditId"]
    again = apply(env, target)
    assert again["changed"] == [] and again["auditId"] is None
    assert count(env, target, "account_provisioning_events") == 1
    with psycopg.connect(env.owner) as c:
        assert c.execute("SELECT epoch FROM inv.control_epoch WHERE singleton").fetchone()[
            0
        ] == UUID(before["epoch"])
        assert c.execute(
            "SELECT enabled,can_request,can_approve FROM inv.project_grants WHERE tenant_id=%s AND project_id=%s",
            (target["tenant"], target["project"]),
        ).fetchone() == (True, True, False)
        assert (
            c.execute(
                "SELECT external_subject FROM public.users WHERE user_id=%s", (target["user"],)
            ).fetchone()[0]
            == target["subject"]
        )
        assert c.execute(
            "SELECT has_table_privilege('inv_app','inv.account_provisioning_events','INSERT'),has_table_privilege('inv_kernel','inv.account_provisioning_events','UPDATE'),has_function_privilege('inv_app','public.run_committed_outputs(uuid,text)','EXECUTE')"
        ).fetchone() == (False, False, False)
    # Pin the append-only trigger's message (inv.immutable_record raises 'immutable record'
    # at ERRCODE 23514). The row's other CHECKs (reason length 1-300, grant_scope IN(...),
    # created_links jsonb) are also CheckViolations; match= makes this self-enforcing so a
    # future value that tripped one of those could not pass as immutability enforcement.
    with psycopg.connect(env.owner) as c, pytest.raises(
        psycopg.errors.CheckViolation, match="immutable record"
    ):
        c.execute(
            "UPDATE inv.account_provisioning_events SET reason=%s WHERE tenant_id=%s",
            ("replace history", target["tenant"]),
        )


@pytest.mark.parametrize(
    "grant,expected",
    [("request", (True, False)), ("approve", (False, True)), ("request-and-approve", (True, True))],
)
def test_only_the_explicit_grant_is_inserted(env, target, grant, expected):
    target = {**target, "grant": grant}
    apply(env, target)
    with psycopg.connect(env.owner) as c:
        assert (
            c.execute(
                "SELECT can_request,can_approve FROM inv.project_grants WHERE tenant_id=%s AND project_id=%s",
                (target["tenant"], target["project"]),
            ).fetchone()
            == expected
        )


@pytest.mark.parametrize("table", ["business_projects", "business_subjects", "project_grants"])
def test_repeated_apply_cannot_reenable_disabled_authority(env, target, table):
    apply(env, target)
    with psycopg.connect(env.owner) as c:
        c.execute(
            "UPDATE inv." + table + " SET enabled=false WHERE tenant_id=%s", (target["tenant"],)
        )
    with pytest.raises(provisioning.ProvisioningRefused, match="disabled"):
        apply(env, target)
    assert count(env, target, "account_provisioning_events") == 1
    with psycopg.connect(env.owner) as c:
        assert c.execute(
            "SELECT enabled FROM inv." + table + " WHERE tenant_id=%s", (target["tenant"],)
        ).fetchone() == (False,)


@pytest.mark.parametrize(
    "problem", ["subject", "project", "user", "member", "epoch", "inverse-mapping", "other-tenant"]
)
def test_invalid_current_preconditions_leave_no_partial_links(env, target, problem):
    with psycopg.connect(env.owner) as c:
        if problem == "subject":
            target = {
                **target,
                "subject": provisioning.public_subject("https://synthetic.invalid", "other"),
            }
        elif problem == "project":
            c.execute(
                "UPDATE public.projects SET status='archived' WHERE project_id=%s",
                (target["project"],),
            )
        elif problem == "user":
            c.execute(
                "UPDATE public.users SET status='suspended' WHERE user_id=%s", (target["user"],)
            )
        elif problem == "member":
            c.execute(
                "UPDATE public.project_members SET role_code='viewer' WHERE project_id=%s",
                (target["project"],),
            )
        elif problem == "epoch":
            c.execute("DELETE FROM inv.control_epoch")
        elif problem == "inverse-mapping":
            other = new_id("user")
            c.execute(
                "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,'other','test')",
                (env.tenant, other),
            )
            c.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (env.tenant, target["subject"], other),
            )
        else:
            target = {**target, "tenant": str(env.other)}
    # Per-cause refusal reasons confirmed against real PostgreSQL; pin each so a
    # precondition refused for a different precondition's reason breaks the test.
    expected = {
        "subject": "OIDC subject required",
        "project": "Active business project required",
        "user": "OIDC subject required",
        "member": "does not permit requesting",
        "epoch": "Recovery epoch must already be provisioned",
        "inverse-mapping": "subject mapping conflicts or is disabled",
        "other-tenant": "Business tenant does not exist",
    }
    with pytest.raises(provisioning.ProvisioningRefused, match=expected[problem]):
        apply(env, target)
    assert count(env, target, "business_projects") == 0
    assert count(env, target, "account_provisioning_events") == 0


def test_existing_grant_scope_is_not_silently_expanded(env, target):
    apply(env, target)
    with pytest.raises(provisioning.ProvisioningRefused, match="different scope"):
        apply(env, {**target, "grant": "request-and-approve"})
    assert count(env, target, "account_provisioning_events") == 1


def test_late_database_failure_rolls_back_every_link_and_grant(env, target):
    with psycopg.connect(env.owner, autocommit=True) as c:

        class FailingAudit:
            transaction = c.transaction

            def execute(self, query, params=()):
                if query.startswith("INSERT INTO inv.account_provisioning_events"):
                    return c.execute("SELECT 1/0")
                return c.execute(query, params)

        with pytest.raises(psycopg.errors.DivisionByZero):
            provisioning.apply(FailingAudit(), reason="test failure", **target)
    for table in ("business_projects", "business_subjects", "account_provisioning_events"):
        assert count(env, target, table) == 0
    with psycopg.connect(env.owner) as c:
        assert c.execute(
            "SELECT count(*) FROM inv.project_grants WHERE project_id=%s", (target["project"],)
        ).fetchone() == (0,)


def test_concurrent_identical_invocations_create_one_grant_and_audit(env, target):
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait(timeout=5)
        return apply(env, target)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=10) for f in [pool.submit(worker), pool.submit(worker)]]
    assert all(r["linked"] for r in results)
    assert sum(bool(r["changed"]) for r in results) == 1
    assert count(env, target, "account_provisioning_events") == 1


def test_apply_rechecks_suspension_after_waiting_for_the_account_lock(env, target):
    started = threading.Event()
    pids = []

    def worker():
        with psycopg.connect(env.owner, autocommit=True) as c:
            pids.append(c.info.backend_pid)
            started.set()
            return provisioning.apply(c, reason="race test", **target)

    with psycopg.connect(env.owner) as writer, ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute(
            "UPDATE public.users SET status='suspended' WHERE user_id=%s", (target["user"],)
        )
        future = pool.submit(worker)
        try:
            assert started.wait(3)
            with psycopg.connect(env.owner, autocommit=True) as observer:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if observer.execute(
                        "SELECT cardinality(pg_blocking_pids(%s))", (pids[0],)
                    ).fetchone()[0]:
                        break
                    time.sleep(0.01)
                else:
                    pytest.fail("Provisioning did not wait for the real account lock")
        finally:
            writer.commit()
        with pytest.raises(provisioning.ProvisioningRefused, match="Active account"):
            future.result(timeout=10)
    assert count(env, target, "business_projects") == 0
    assert count(env, target, "account_provisioning_events") == 0


def test_cli_check_apply_and_replay_use_the_real_database(env, target):
    args = [
        sys.executable,
        "tools/provision_account.py",
        "--tenant",
        target["tenant"],
        "--project",
        target["project"],
        "--user",
        target["user"],
        "--issuer",
        "https://synthetic.invalid",
        "--sub",
        "account",
        "--grant",
        "request",
    ]
    environment = {**os.environ, "INV_PROVISION_DSN": env.owner}
    for mode, code in [("--check", 1), ("--apply", 0), ("--check", 0), ("--apply", 0)]:
        command = args + [mode, "--reason", "synthetic CLI test"]
        result = subprocess.run(
            command, env=environment, capture_output=True, text=True, timeout=20
        )
        assert result.returncode == code
        response = json.loads(result.stdout)
        assert response["executionReady"] is False
        assert "postgresql" not in result.stdout + result.stderr
    assert count(env, target, "account_provisioning_events") == 1


def test_runtime_database_role_cannot_provision(env, target, monkeypatch, capsys):
    monkeypatch.setenv("INV_PROVISION_DSN", env.runtime)
    code = provisioning.main(
        [
            "--apply",
            "--tenant",
            target["tenant"],
            "--project",
            target["project"],
            "--user",
            target["user"],
            "--issuer",
            "https://synthetic.invalid",
            "--sub",
            "account",
            "--grant",
            "request",
            "--reason",
            "test",
        ]
    )
    assert code == 2
    response = json.loads(capsys.readouterr().err)
    assert response["sqlstate"] == "42501"
    assert count(env, target, "account_provisioning_events") == 0
    assert count(env, target, "business_projects") == 0


def test_cli_database_error_does_not_print_credentials(env, target, monkeypatch, capsys):
    marker = "private-synthetic-dsn-marker"
    monkeypatch.setenv(
        "INV_PROVISION_DSN", "host=127.0.0.1 port=1 connect_timeout=1 password=" + marker
    )
    code = provisioning.main(
        [
            "--check",
            "--tenant",
            target["tenant"],
            "--project",
            target["project"],
            "--user",
            target["user"],
            "--issuer",
            "https://synthetic.invalid",
            "--sub",
            "account",
            "--grant",
            "request",
        ]
    )
    assert code == 2
    output = capsys.readouterr()
    assert marker not in output.out + output.err
    assert json.loads(output.err)["refused"].startswith("Database operation failed")
