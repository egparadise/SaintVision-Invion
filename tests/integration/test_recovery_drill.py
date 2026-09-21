"""Real pg_dump/pg_restore and database mutations, exclusively in disposable DBs."""

import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest
from recovery_drill_prerequisites import resolve_owned_postgres_container
from raises_no_skip import raises_without_skip

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "tools" / "definer-policy.json").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location(
    "recovery_drill_test", ROOT / "tools/recovery_drill.py"
)
drill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drill)


@pytest.fixture
def args(postgres):
    admin = os.environ["INV_TEST_ADMIN_DSN"]
    container = resolve_owned_postgres_container()
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


def _cleanup_owned_docker_resource(kind, name, label_key, label_value):
    """Best-effort cleanup that never hides the test body's exception."""
    inspect_cmd = ["docker", kind, "inspect", name]
    try:
        inspected = subprocess.run(inspect_cmd, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "query-error"
    if inspected.returncode != 0:
        return "confirmed-absent"
    try:
        current = json.loads(inspected.stdout)[0]
        labels = current.get("Config", {}).get("Labels", {}) if kind == "container" else current.get("Labels", {})
        if labels.get(label_key) != label_value:
            return "ownership-mismatch"
    except (ValueError, KeyError, IndexError, TypeError):
        return "query-error"
    remove_cmd = ["docker", "rm", "-f", "-v", name] if kind == "container" else ["docker", "network", "rm", name]
    try:
        removed = subprocess.run(remove_cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "remove-error"
    if removed.returncode != 0:
        return "remove-error"
    try:
        confirmed = subprocess.run(inspect_cmd, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return "query-error"
    return "confirmed-removed" if confirmed.returncode != 0 else "remove-error"


def _classify_archiver_connection_failure(name, run=subprocess.run):
    """Distinguish archiver startup failure from host access to an internal network."""
    try:
        inspected = run(["docker", "inspect", name], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssertionError(
            "Cannot classify owned archiver readiness: docker inspect failed "
            f"({type(exc).__name__})"
        ) from None
    if inspected.returncode != 0:
        raise AssertionError(
            "Cannot classify owned archiver readiness: docker inspect returned "
            f"{inspected.returncode}"
        )
    try:
        container = json.loads(inspected.stdout)[0]
        labels = container["Config"]["Labels"]
        state = container["State"]
        if labels.get("ai.saintvision.rpo-test") != name:
            raise AssertionError("Owned archiver readiness inspect found an ownership mismatch")
        status = state["Status"]
        running = state["Running"]
        restarting = state["Restarting"]
        exit_code = state["ExitCode"]
        restart_count = container["RestartCount"]
        port_bindings = container.get("HostConfig", {}).get("PortBindings") or {}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AssertionError(
            "Cannot classify owned archiver readiness: malformed docker inspect "
            f"({type(exc).__name__})"
        ) from None

    try:
        logs = run(["docker", "logs", "--tail", "200", name], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssertionError(
            "Cannot classify owned archiver startup: docker logs failed "
            f"({type(exc).__name__})"
        ) from None
    if logs.returncode != 0:
        raise AssertionError(
            "Cannot classify owned archiver startup: docker logs returned "
            f"{logs.returncode}"
        )

    log_text = (logs.stdout or b"").decode("utf-8", errors="replace")
    log_text += "\n" + (logs.stderr or b"").decode("utf-8", errors="replace")
    diagnostic = next(
        (
            line.strip()
            for line in reversed(log_text.splitlines())
            if re.search(r"\b(FATAL|PANIC|ERROR)\b", line, re.IGNORECASE)
        ),
        None,
    )
    if diagnostic:
        # Keep useful startup context while suppressing credential-like values.
        diagnostic = re.sub(r"(?i)(password\s*[=:]\s*)\S+", r"\1<redacted>", diagnostic)
        diagnostic = re.sub(
            r"(?i)(postgres(?:ql)?://)[^/@\s]+:[^/@\s]+@",
            r"\1<redacted>@",
            diagnostic,
        )
        diagnostic = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "<redacted-key>", diagnostic)
        diagnostic = diagnostic[:500]

    if status != "running" or not running or restarting or restart_count:
        if diagnostic:
            detail = "; startupLog=" + diagnostic
        elif re.search(r"database system is ready to accept connections", log_text, re.IGNORECASE):
            detail = "; PostgreSQL-ready marker present"
        else:
            detail = "; PostgreSQL-ready marker absent"
        raise AssertionError(
            "Owned archiver startup failed: "
            f"status={status}, running={running}, restarting={restarting}, "
            f"restartCount={restart_count}, exitCode={exit_code}{detail}"
        )

    ready = re.search(r"database system is ready to accept connections", log_text, re.IGNORECASE)
    if diagnostic:
        raise AssertionError(
            "Owned archiver PostgreSQL startup reported an error: " + diagnostic
        )
    if ready and not any(port_bindings.values()):
        pytest.skip(
            "Docker inspect state confirms status=running, running=True, "
            f"restarting=False, restartCount={restart_count}, exitCode={exit_code}; "
            "PostgreSQL-ready log marker is present; "
            "hostPortPublished=False. This test's Docker internal network has no "
            "published host port, so host pytest cannot reach the container by "
            "Docker-only name"
        )
    if ready and any(port_bindings.values()):
        raise AssertionError(
            "Owned archiver is running and PostgreSQL reports ready with a published "
            "host port, but host connection still failed"
        )

    raise AssertionError(
        "Cannot classify owned archiver readiness: container is running, but logs "
        "contain neither PostgreSQL-ready nor a startup-error marker"
    )


def test_cleanup_preserves_unowned_resource_and_confirms_owned_removal(monkeypatch):
    calls = []

    def mismatch(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b'[{"Config":{"Labels":{"other":"run"}}}]', b"")

    monkeypatch.setattr(subprocess, "run", mismatch)
    assert _cleanup_owned_docker_resource("container", "foreign", "owned", "this-run") == "ownership-mismatch"
    assert len(calls) == 1

    calls.clear()
    responses = [
        subprocess.CompletedProcess([], 0, b'[{"Config":{"Labels":{"owned":"this-run"}}}]', b""),
        subprocess.CompletedProcess([], 0, b"", b""),
        subprocess.CompletedProcess([], 1, b"[]", b"not found"),
    ]

    def owned(cmd, **kwargs):
        calls.append(cmd)
        return responses.pop(0)

    monkeypatch.setattr(subprocess, "run", owned)
    assert _cleanup_owned_docker_resource("container", "this-run", "owned", "this-run") == "confirmed-removed"
    assert len(calls) == 3


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
    assert report["definerFunctions"]["checked"] == len(POLICY["functions"])
    assert set(report["definerFunctions"]["catalogueFunctions"]) == set(POLICY["functions"])
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
    if sys.platform != "linux":
        pytest.skip("Linux private backup path required for saved archive verification")
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
            "SELECT outcome,measured_rpo_seconds,met_targets,notes FROM public.recovery_drills WHERE drill_id=%s",
            (record_id,),
        ).fetchone()
    assert row[:3] == ("passed", 901, False)
    assert row[3]["scope"] == "database_rehearsal"
    assert row[3]["operationalRecoveryVerified"] is False
    assert row[3]["notVerified"] == report["notVerified"]


def test_failed_integrity_drill_is_recorded_without_measurements(args):
    """An unsuccessful restore must not leave plausible RPO/RTO numbers in the ledger."""
    from saintvision.ids import new_id

    args.tenant, args.user = str(uuid4()), new_id("user")
    with psycopg.connect(args.source) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES (%s,%s,'failed recovery test')",
            (args.tenant, "failed-recovery-" + args.tenant),
        )
        conn.execute(
            "INSERT INTO public.users(user_id,tenant_id,external_subject,display_name) "
            "VALUES (%s,%s,%s,'test operator')",
            (args.user, args.tenant, "failed-recovery-" + args.tenant),
        )

    report = {
        "restoreExitCode": 0,
        "measuredRpoSeconds": 6,
        "measuredRtoSeconds": 9,
        "fencingVerified": True,
        "fencingNote": "synthetic test result",
        "integrityVerified": False,
        "backupSha256": "a" * 64,
        "backupBytes": 1024,
        "scope": "database_rehearsal",
        "notVerified": [],
        "tablesWithDifferentCounts": ["synthetic_mismatch"],
        "tablesWithDifferentContent": [],
        "fencingAdvanceRequired": 0,
        "recoveryCapability": {"operationalRpoVerified": False},
    }
    drill_id = drill.record(report, args)

    with psycopg.connect(args.source) as conn:
        row = conn.execute(
            "SELECT outcome, measured_rpo_seconds, measured_rto_seconds, integrity_verified "
            "FROM public.recovery_drills WHERE drill_id=%s",
            (drill_id,),
        ).fetchone()
    assert not drill._passed(report)
    assert row == ("failed", None, None, False)


def test_cli_and_database_record_refuse_unverified_operational_target(args):
    from saintvision.ids import new_id

    args.tenant, args.user = str(uuid4()), new_id("user")
    with psycopg.connect(args.source) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'RPO test')",
            (args.tenant, "rpo-" + args.tenant),
        )
        conn.execute(
            "INSERT INTO public.users(user_id,tenant_id,external_subject,display_name) VALUES(%s,%s,%s,'RPO operator')",
            (args.user, args.tenant, "rpo-" + args.tenant),
        )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/recovery_drill.py"),
            "--json",
            "--docker",
            args.docker,
            "--tenant",
            args.tenant,
            "--user",
            args.user,
            "--require-operational-rpo",
            "900",
        ],
        env={
            **os.environ,
            "INV_RECOVERY_SOURCE_DSN": args.source,
            "INV_RECOVERY_ADMIN_DSN": args.admin,
            "INV_RECOVERY_RECORD_DSN": args.source,
            "INV_RECOVERY_CONTAINER_DSN": args.container_dsn,
        },
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 1, "Operational acceptance must be refused"
    report = json.loads(result.stdout)
    assert report["acceptance"] == dict(
        functionalDrillPassed=True,
        requiredOperationalRpoSeconds=900,
        operationalRpoRequirementMet=False,
        passed=False,
    )
    with psycopg.connect(args.source) as conn:
        outcome, met, notes = conn.execute(
            "SELECT outcome,met_targets,notes FROM public.recovery_drills WHERE drill_id=%s",
            (report["drillId"],),
        ).fetchone()
    assert outcome == "failed" and met is False
    assert notes["functionalDrillPassed"] is True
    assert notes["requiredOperationalRpoSeconds"] == 900
    assert notes["operationalRpoRequirementMet"] is False
    assert notes["operationalRpoVerified"] is False
    assert args.source not in result.stdout + result.stderr


@pytest.mark.parametrize("archive_command", ["/bin/true", "/bin/false"])
def test_live_archiver_configuration_cannot_certify_operational_rpo(args, archive_command):
    """A separate owned PG server, no published ports or production changes."""
    name = "sv-rpo-" + uuid4().hex[:12]
    base = json.loads(subprocess.check_output(["docker", "inspect", args.docker]))[0]
    network = "sv-rpo-net-" + uuid4().hex[:12]
    label = "ai.saintvision.rpo-test"
    network_label = "ai.saintvision.rpo-network"
    network_created = subprocess.run(
        ["docker", "network", "create", "--internal", "--label", network_label + "=" + network, network],
        capture_output=True,
        timeout=20,
    )
    if network_created.returncode != 0:
        pytest.skip("Docker could not create the owned internal network for archiver isolation")
    try:
        net = json.loads(subprocess.check_output(["docker", "network", "inspect", network]))[0]
        assert net.get("Internal") is True, "Owned archiver network is not isolated"
        created = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--label",
                label + "=" + name,
                "--network",
                network,
                "--tmpfs",
                "/var/lib/postgresql/data:rw",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                base["Image"],
                "-c",
                "archive_mode=on",
                "-c",
                "archive_command=" + archive_command,
                "-c",
                "archive_timeout=300",
            ],
            capture_output=True,
            timeout=30,
        )
        assert created.returncode == 0, "Owned archiver fixture could not start"
        dsn = "postgresql://postgres@" + name + ":5432/postgres"
        deadline = time.monotonic() + 30
        while True:
            try:
                with psycopg.connect(dsn, connect_timeout=1) as conn:
                    conn.execute("SELECT 1")
                break
            except psycopg.OperationalError:
                if time.monotonic() > deadline:
                    _classify_archiver_connection_failure(name)
                time.sleep(0.1)
        capability = drill._recovery_capability(dsn)
        assert capability["archivingConfigured"] is True
        assert capability["archiveSwitchTimeoutSeconds"] == 300
        assert capability["settings"]["archive_command"] == "configured"
        assert archive_command not in json.dumps(capability)
        assert capability["operationalRpoBoundSeconds"] is None
        assert capability["operationalRpoVerified"] is False
        assert not drill._meets_operational_rpo({"recoveryCapability": capability}, 900)
        # Even actual archiver exit-success is not proof of retained bytes.
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("CREATE TABLE archive_probe(value text)")
            conn.execute("INSERT INTO archive_probe VALUES('synthetic-marker')")
            conn.execute("SELECT pg_switch_wal()")
            deadline = time.monotonic() + 15
            while True:
                conn.execute("SELECT pg_stat_clear_snapshot()")
                archived, failed = conn.execute(
                    "SELECT archived_count,failed_count FROM pg_stat_archiver"
                ).fetchone()
                if (archived if archive_command == "/bin/true" else failed) > 0:
                    break
                if time.monotonic() > deadline:
                    raise AssertionError("Expected archive outcome not observed")
                time.sleep(0.1)
        assert not drill._meets_operational_rpo(
            {"recoveryCapability": drill._recovery_capability(dsn)}, 900
        )
    finally:
        cleanup = {
            "container": _cleanup_owned_docker_resource("container", name, label, name),
            "network": _cleanup_owned_docker_resource("network", network, network_label, network),
        }
        if any(value not in {"confirmed-removed", "confirmed-absent"} for value in cleanup.values()):
            print("archiver cleanup: " + json.dumps(cleanup, sort_keys=True), file=sys.stderr)
            if sys.exc_info()[0] is None:
                pytest.fail("Owned archiver cleanup incomplete: " + json.dumps(cleanup, sort_keys=True))


@pytest.mark.parametrize("changed", [False, True])
def test_saved_backup_is_linked_and_rechecked_before_record(args, tmp_path, changed):
    if sys.platform != "linux":
        pytest.skip("Linux private backup path required for saved archive verification")
    from saintvision.ids import new_id

    args.save_backup = str(tmp_path / "saved.dump")
    report = drill.rehearse(args)
    assert drill._passed(report)
    assert report["savedBackupIntact"] is True
    args.tenant, args.user = str(uuid4()), new_id("user")
    with psycopg.connect(args.source) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'backup test')",
            (args.tenant, "b-" + args.tenant),
        )
        conn.execute(
            "INSERT INTO public.users(user_id,tenant_id,external_subject,display_name) VALUES(%s,%s,%s,'backup operator')",
            (args.user, args.tenant, "b-" + args.tenant),
        )
    if changed:
        Path(args.save_backup).write_bytes(b"post-restore corruption")
    key = drill.record(report, args)
    with psycopg.connect(args.source) as conn:
        row = conn.execute(
            """SELECT d.outcome,d.met_targets,d.backup_id,b.verified,b.kind,b.off_site,b.checksum_sha256,d.notes
            FROM public.recovery_drills d JOIN public.backup_records b USING(backup_id)
            WHERE d.drill_id=%s""",
            (key,),
        ).fetchone()
    assert row[0] == ("failed" if changed else "passed")
    assert row[1] is (not changed)
    assert row[2] == report["backupId"]
    assert row[3] is (not changed)
    assert row[4:6] == ("logical", False)
    assert row[6] == (None if changed else report["backupSha256"])
    assert row[7]["savedBackupIntact"] is (not changed)
    assert report["backupVerified"] is (not changed)
    assert drill._accepted(report, args) is (not changed)


def test_ledger_and_drill_rollback_together(args, tmp_path, monkeypatch):
    if sys.platform != "linux":
        pytest.skip("Linux private backup path required for rollback verification")
    from saintvision.ids import new_id
    from saintvision.services import pilot

    args.save_backup = str(tmp_path / "rollback.dump")
    report = drill.rehearse(args)
    args.tenant, args.user = str(uuid4()), new_id("user")
    with psycopg.connect(args.source) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'rollback test')",
            (args.tenant, "b-" + args.tenant),
        )
        conn.execute(
            "INSERT INTO public.users(user_id,tenant_id,external_subject,display_name) VALUES(%s,%s,%s,'backup operator')",
            (args.user, args.tenant, "b-" + args.tenant),
        )
    original = pilot.record_recovery_drill

    def fail(*values, **kwargs):
        original(*values, **kwargs)
        raise RuntimeError("injected after drill flush")

    monkeypatch.setattr(pilot, "record_recovery_drill", fail)
    with raises_without_skip(RuntimeError, match="injected"):
        drill.record(report, args)
    with psycopg.connect(args.source) as conn:
        for table in ("backup_records", "recovery_drills"):
            assert (
                conn.execute(
                    sql.SQL("SELECT count(*) FROM public.{} WHERE tenant_id=%s").format(
                        sql.Identifier(table)
                    ),
                    (args.tenant,),
                ).fetchone()[0]
                == 0
            )
    assert "backupId" not in report and "backupVerified" not in report
    assert Path(args.save_backup).exists(), "Keep the orphan file for operator reconciliation"
