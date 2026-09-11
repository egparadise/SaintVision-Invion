"""Real pg_dump/pg_restore and database mutations, exclusively in disposable DBs."""

import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "recovery_drill_test", ROOT / "tools/recovery_drill.py"
)
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


@pytest.fixture
def args(postgres):
    admin = os.environ["INV_TEST_ADMIN_DSN"]
    container = os.getenv("CX01_CONTAINER") or conninfo_to_dict(admin)["host"]
    inspect = subprocess.run(["docker", "inspect", container], capture_output=True, timeout=20)
    assert inspect.returncode == 0, "Disposable PostgreSQL container unavailable"
    labels = json.loads(inspect.stdout)[0]["Config"]["Labels"]
    assert labels.get("ai.saintvision.cx01") or labels.get("ai.saintvision.kernel-test")
    source_name = conninfo_to_dict(postgres.owner)["dbname"]
    assert source_name.startswith("inv_test_")
    yield SimpleNamespace(
        source=postgres.owner,
        admin=admin,
        docker=container,
        container_dsn=make_conninfo(admin, host="127.0.0.1", port=5432, dbname=source_name),
        app_role="inv_app",
        kernel_role="inv_kernel",
        from_backup=None,
        backup_taken_at=None,
        save_backup=None,
        keep=False,
        record_dsn=None,
        tenant=None,
        user=None,
    )
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM pg_database WHERE datname LIKE 'inv_drill_%'"
            ).fetchone()[0]
            == 0
        )


def mutate_restored(monkeypatch, args, mutation):
    original = drill.Postgres.run

    def run(self, program, argv, **kwargs):
        result = original(self, program, argv, **kwargs)
        if program == "pg_restore" and "--dbname" in argv and result.returncode == 0:
            name = conninfo_to_dict(argv[argv.index("--dbname") + 1])["dbname"]
            assert name.startswith("inv_drill_") and len(name) == 42
            with psycopg.connect(make_conninfo(args.admin, dbname=name), autocommit=True) as conn:
                conn.execute(mutation)
        return result

    monkeypatch.setattr(drill.Postgres, "run", run)


def test_real_backup_restore_verifies_both_schemas_without_seed_residue(args, monkeypatch):
    before = drill._table_counts(args.source)
    original = drill._service_resumption

    def delayed(*values):
        time.sleep(0.15)
        return original(*values)

    monkeypatch.setattr(drill, "_service_resumption", delayed)
    report = drill.rehearse(args)
    assert report["restoreExitCode"] == 0
    assert drill._passed(report)
    assert report["sourceCounts"] == report["targetCounts"] == before
    assert len(report["targetCounts"]) > 100
    assert report["definerFunctions"]["checked"] == 9
    assert report["serviceResumption"]["publicRlsScopes"]
    assert report["serviceResumption"]["kernelRlsScopes"]
    assert report["measuredRtoSeconds"] >= 0.15
    assert report["operationalRecoveryVerified"] is False
    assert drill._table_counts(args.source) == before


def test_corrupt_backup_cannot_pass_or_leave_target(args, tmp_path):
    backup = tmp_path / "corrupt.dump"
    backup.write_bytes(b"synthetic invalid PostgreSQL archive")
    args.from_backup = str(backup)
    args.backup_taken_at = dt.datetime.now(dt.timezone.utc).isoformat()
    report = drill.rehearse(args)
    assert report["restoreExitCode"] != 0
    assert not report["integrityVerified"]
    assert not report["fencingVerified"]
    assert not drill._passed(report)


@pytest.mark.parametrize(
    "mutation,field",
    [
        ("ALTER TABLE public.projects DISABLE ROW LEVEL SECURITY", "serviceResumed"),
        ("ALTER TABLE inv.projects DISABLE ROW LEVEL SECURITY", "serviceResumed"),
        ("REVOKE USAGE ON SCHEMA inv FROM inv_kernel", "serviceResumed"),
        (
            "GRANT EXECUTE ON FUNCTION public.run_committed_outputs(uuid,text) TO inv_app",
            "definerFunctionsSafe",
        ),
        (
            "CREATE FUNCTION public.recovery_unexpected() RETURNS SETOF uuid LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT tenant_id FROM public.tenants $$",
            "definerFunctionsSafe",
        ),
    ],
)
def test_restored_security_corruption_is_rejected(args, monkeypatch, mutation, field):
    mutate_restored(monkeypatch, args, mutation)
    report = drill.rehearse(args)
    assert report["restoreExitCode"] == 0
    assert not report[field]
    assert not report["integrityVerified"]
    assert not drill._passed(report)


def test_table_missing_entirely_from_target_is_reported(args, monkeypatch):
    # This table is deliberately outside the fixed evidence digest list.
    with psycopg.connect(args.source) as conn:
        conn.execute('CREATE TABLE public."recovery quoted table"(id integer)')
    try:
        mutate_restored(monkeypatch, args, 'DROP TABLE public."recovery quoted table"')
        report = drill.rehearse(args)
        assert "public.recovery quoted table" in report["tablesWithDifferentCounts"]
        assert not drill._passed(report)
    finally:
        with psycopg.connect(args.source) as conn:
            conn.execute('DROP TABLE public."recovery quoted table"')


def test_tokens_issued_during_restore_block_stale_sequence(args, monkeypatch):
    original = drill.Postgres.run

    def run(self, program, argv, **kwargs):
        result = original(self, program, argv, **kwargs)
        if program == "pg_restore" and "--dbname" in argv and result.returncode == 0:
            with psycopg.connect(args.source) as conn:
                conn.execute("SELECT nextval('inv.fencing_token_seq') FROM generate_series(1,2)")
        return result

    monkeypatch.setattr(drill.Postgres, "run", run)
    report = drill.rehearse(args)
    assert report["integrityVerified"]
    assert report["fencingAdvanceRequired"] > 0
    assert not drill._passed(report)


def test_future_archive_timestamp_is_not_a_zero_rpo_success(args, tmp_path):
    backup = tmp_path / "actual.dump"
    args.save_backup = str(backup)
    first = drill.rehearse(args)
    assert drill._passed(first)
    args.from_backup = str(backup)
    args.backup_taken_at = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
    second = drill.rehearse(args)
    assert second["integrityVerified"]
    assert second["measuredRpoSeconds"] is None
    assert not drill._passed(second)


@pytest.mark.parametrize("uri", [False, True])
def test_actual_drill_result_can_be_recorded_through_pilot_service(args, uri):
    from saintvision.ids import new_id
    from sqlalchemy.engine import URL

    report = drill.rehearse(args)
    assert drill._passed(report)
    args.tenant, args.user = str(uuid4()), new_id("user")
    with psycopg.connect(args.source) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES (%s,%s,'recovery test')",
            (args.tenant, "recovery-" + args.tenant),
        )
        conn.execute(
            "INSERT INTO public.users(user_id,tenant_id,external_subject,display_name) VALUES (%s,%s,%s,'test operator')",
            (args.user, args.tenant, "recovery-" + args.tenant),
        )
    if uri:
        info = conninfo_to_dict(args.source)
        args.record_dsn = URL.create(
            "postgresql+psycopg",
            username=info["user"],
            password=info["password"],
            host=info["host"],
            port=int(info["port"]),
            database=info["dbname"],
        ).render_as_string(hide_password=False)
    # Crossing the 900s threshold must not round down to a false SLO pass.
    report["measuredRpoSeconds"] = 900.01
    record_id = drill.record(report, args)
    with psycopg.connect(args.source) as conn:
        row = conn.execute(
            "SELECT outcome,measured_rpo_seconds,met_targets FROM public.recovery_drills WHERE drill_id=%s",
            (record_id,),
        ).fetchone()
    assert row == ("passed", 901, False)
