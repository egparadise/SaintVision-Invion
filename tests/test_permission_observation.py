"""Actual PostgreSQL permission observations: project scope, ordering and rollback."""

import concurrent.futures
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy.engine import make_url
from test_operational_readiness import prepared

SPEC = importlib.util.spec_from_file_location(
    "permission_observation", Path(__file__).resolve().parents[1] / "tools/operational_readiness.py"
)
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


def args_for(ids, **values):
    return SimpleNamespace(
        dsn=ids["dsn"],
        tenant=ids["tenant"],
        project=ids["project"],
        user=ids["user"],
        snapshot=True,
        **values,
    )


def count(ids):
    with psycopg.connect(ids["dsn"]) as c:
        return c.execute(
            "SELECT count(*) FROM public.permission_snapshots WHERE tenant_id=%s", (ids["tenant"],)
        ).fetchone()[0]


def test_read_only_observation_writes_nothing(prepared):
    args = args_for(prepared)
    args.snapshot = False
    result = readiness.report(args)
    assert count(prepared) == 0
    assert "permissionSnapshot" not in result
    assert result["grants"]["mayApproveAsOperator"] is None


def test_previous_snapshot_is_scoped_to_project(prepared):
    from saintvision.ids import new_id

    second = new_id("project")
    with psycopg.connect(prepared["dsn"]) as c:
        c.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'second','second')",
            (prepared["tenant"], second),
        )
    args = args_for(prepared)
    first = readiness.report(args)["permissionSnapshot"]
    args.project = second
    other = readiness.report(args)["permissionSnapshot"]
    args.project = prepared["project"]
    same = readiness.report(args)["permissionSnapshot"]
    assert [r["changed"] for r in (first, other, same)] == [None, None, False]
    assert same["previousSnapshotId"] == first["snapshotId"]
    assert other["previousSnapshotId"] is None


def test_disabled_operator_is_observed_without_authorizing(prepared):
    args = args_for(prepared)
    before = readiness.report(args)
    with psycopg.connect(prepared["dsn"]) as c:
        c.execute(
            "UPDATE inv.operator_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (prepared["tenant"], prepared["subject"]),
        )
    after = readiness.report(args)
    assert before["grants"]["observedOperatorApprovalCapability"] is True
    assert after["grants"]["observedOperatorApprovalCapability"] is False
    assert after["grants"]["mayApproveAsOperator"] is None
    assert after["permissionSnapshot"]["changed"] is True


def test_concurrent_collectors_have_one_initial_snapshot(prepared):
    gate = threading.Barrier(2)

    def run():
        gate.wait(timeout=5)
        return readiness.report(args_for(prepared))["permissionSnapshot"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: run(), range(2)))
    first = next(r for r in rows if r["changed"] is None)
    second = next(r for r in rows if r["changed"] is False)
    assert second["previousSnapshotId"] == first["snapshotId"]
    assert second["observedAt"] > first["observedAt"]
    assert count(prepared) == 2


def test_grant_change_during_collection_is_a_later_observation(prepared, monkeypatch):
    original = readiness.inputs
    changed = False

    def change(conn, tenant):
        nonlocal changed
        result = original(conn, tenant)
        if not changed:
            changed = True
            with psycopg.connect(prepared["dsn"]) as c:
                c.execute(
                    "UPDATE inv.operator_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
                    (tenant, prepared["subject"]),
                )
        return result

    monkeypatch.setattr(readiness, "inputs", change)
    first = readiness.report(args_for(prepared))
    second = readiness.report(args_for(prepared))
    assert first["grants"]["observedOperatorApprovalCapability"] is True
    assert second["grants"]["observedOperatorApprovalCapability"] is False
    assert second["permissionSnapshot"]["changed"] is True
    with psycopg.connect(prepared["dsn"]) as c:
        stamp = c.execute(
            "SELECT taken_at FROM public.permission_snapshots WHERE snapshot_id=%s",
            (first["permissionSnapshot"]["snapshotId"],),
        ).fetchone()[0]
    assert stamp.isoformat() == first["observedAt"]


def test_failure_rolls_back_and_releases_lock(prepared, monkeypatch):
    from saintvision.services import pilot

    original = pilot.take_permission_snapshot

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after flush")

    monkeypatch.setattr(pilot, "take_permission_snapshot", fail)
    with pytest.raises(RuntimeError, match="after flush"):
        readiness.report(args_for(prepared))
    assert count(prepared) == 0
    monkeypatch.setattr(pilot, "take_permission_snapshot", original)
    assert readiness.report(args_for(prepared))["permissionSnapshot"]["changed"] is None


def test_runtime_role_and_cross_tenant_subject_cannot_record(prepared):
    from saintvision.ids import new_id

    # Dedicated restricted login in this disposable cluster, never an operational role.
    role = "snapshot_reader_" + uuid4().hex
    password = uuid4().hex
    from psycopg import sql

    with psycopg.connect(prepared["dsn"], autocommit=True) as c:
        c.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
    try:
        args = args_for(prepared)
        args.dsn = (
            make_url(prepared["dsn"])
            .set(username=role, password=password)
            .render_as_string(hide_password=False)
        )
        with pytest.raises(PermissionError):
            readiness.report(args)
    finally:
        with psycopg.connect(prepared["dsn"], autocommit=True) as c:
            c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
    args = args_for(prepared)
    args.tenant = str(uuid4())
    with pytest.raises(ValueError, match="absent in tenant"):
        readiness.report(args)
    assert count(prepared) == 0


def test_clock_rollback_is_rejected_without_reordering(prepared, monkeypatch):
    from datetime import datetime, timedelta

    first = readiness.report(args_for(prepared))
    original = readiness._collect

    def older(conn, args):
        result = original(conn, args)
        result["observedAt"] = (
            datetime.fromisoformat(first["observedAt"]) - timedelta(seconds=1)
        ).isoformat()
        return result

    monkeypatch.setattr(readiness, "_collect", older)
    with pytest.raises(ValueError, match="clock"):
        readiness.report(args_for(prepared))
    assert count(prepared) == 1


@pytest.mark.parametrize("as_json", [False, True])
def test_cli_snapshot_and_acceptance_report_share_exit_and_commit(prepared, as_json):
    import json, os, subprocess, sys

    command = [
        sys.executable,
        str(Path(readiness.__file__)),
        "--tenant",
        prepared["tenant"],
        "--project",
        prepared["project"],
        "--user",
        prepared["user"],
        "--snapshot",
        "--acceptance-evidence",
    ]
    if as_json:
        command.append("--json")
    result = subprocess.run(
        command,
        env={**os.environ, "INV_READINESS_DSN": prepared["dsn"]},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1
    assert count(prepared) == 1
    assert prepared["dsn"] not in result.stdout + result.stderr
    if as_json:
        value = json.loads(result.stdout)
        assert value["acceptanceEvidence"]["acceptanceAssessed"] is False
        assert value["acceptanceEvidence"]["evidenceComplete"] is False
        assert value["permissionSnapshot"]["changed"] is None
    else:
        assert "operating acceptance: not assessed" in result.stdout


def test_catalog_read_is_readonly_and_does_not_record_snapshot(prepared, monkeypatch):
    original = readiness._collect

    def verify(conn, args):
        assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        assert conn.execute("SHOW transaction_isolation").fetchone()[0] == "repeatable read"
        return original(conn, args)

    monkeypatch.setattr(readiness, "_collect", verify)
    args = args_for(prepared, acceptance_evidence=True)
    args.snapshot = False
    result = readiness.report(args)
    assert result["acceptanceEvidence"]["evidenceComplete"] is False
    assert count(prepared) == 0
