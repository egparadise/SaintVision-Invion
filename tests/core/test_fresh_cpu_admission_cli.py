"""Bounded public stdin / explicit apply / secret-safe CLI, no subprocesses."""

import importlib.util
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from inv.errors import DomainError
from inv.fresh_cpu_admission import MAX_REQUEST_BYTES, prepare_request
from test_fresh_cpu_admission import encoded, fresh_db, request_factory, snapshot  # noqa: F401


@pytest.fixture
def cli():
    path = Path(__file__).resolve().parents[2] / "tools/fresh_cpu_admission.py"
    spec = importlib.util.spec_from_file_location("fresh_cpu_admission_cli_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stdin(monkeypatch, cli, raw):
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(buffer=BytesIO(raw)))


@pytest.mark.postgres
def test_cli_default_plan_and_explicit_apply_use_real_db(cli, fresh_db, monkeypatch, capsys):
    db, secret = fresh_db, "SYNTHETIC_CLI_CONNECTION_MARKER"
    calls = []

    def connect(dsn, *, autocommit):
        assert dsn == secret and autocommit is True
        calls.append("db")
        return db.connect()

    monkeypatch.setenv("SV_FRESH_NODE_OPERATOR_DSN", secret)
    monkeypatch.setattr(cli.psycopg, "connect", connect)
    before = snapshot(db)
    stdin(monkeypatch, cli, encoded(db.body))
    assert cli.main([]) == 0
    output = capsys.readouterr()
    plan = json.loads(output.out)
    assert plan["mode"] == "PLAN" and not output.err
    assert snapshot(db) == before
    stdin(monkeypatch, cli, encoded(db.body))
    assert cli.main(["--apply", "--expected-plan-sha256", plan["planSha256"]]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "COMMITTED" and not output.err
    assert secret not in output.out + output.err
    assert calls == ["db", "db"]


@pytest.mark.parametrize("argv", [
    ["--dsn", "SYNTHETIC_ARGV_SECRET"], ["--request-file", "SYNTHETIC_ARGV_SECRET"],
    ["--apply"], ["--expected-plan-sha256", "0" * 64],
    ["--apply", "--expected-plan-sha256", "SYNTHETIC_ARGV_SECRET"],
    ["--dsn-env", "invalid=SYNTHETIC_ARGV_SECRET"],
])
def test_rejected_argv_never_echoes_argument_values(cli, monkeypatch, capsys, argv):
    def forbidden(*args, **kwargs):
        raise AssertionError("must refuse before connect")

    monkeypatch.setattr(cli.psycopg, "connect", forbidden)
    assert cli.main(argv) == 2
    output = capsys.readouterr()
    assert not output.out and "SYNTHETIC_ARGV_SECRET" not in output.err
    assert json.loads(output.err)["code"] == "FRESH-0001"


@pytest.mark.parametrize("stage", ["parse", "connect", "plan", "apply", "forged-domain-code"])
def test_exception_and_request_secrets_never_escape(cli, request_factory, monkeypatch, capsys, stage):
    marker = "SYNTHETIC_EXCEPTION_CREDENTIAL_MARKER"
    body = request_factory()
    raw = encoded(body) if stage != "parse" else ('{"' + marker + '":NaN}').encode()
    monkeypatch.setenv("SV_FRESH_NODE_OPERATOR_DSN", marker)
    stdin(monkeypatch, cli, raw)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def explode(*args, **kwargs):
        raise RuntimeError(marker)

    monkeypatch.setattr(cli.psycopg, "connect", explode if stage == "connect" else lambda *a, **k: Connection())
    monkeypatch.setattr(cli, "plan_admission", explode)
    monkeypatch.setattr(cli, "apply_admission", explode)
    if stage == "forged-domain-code":
        def forged(*args, **kwargs):
            raise DomainError(marker, marker, 500)
        monkeypatch.setattr(cli, "plan_admission", forged)
    argv = []
    if stage == "apply":
        argv = ["--apply", "--expected-plan-sha256", prepare_request(raw).digest()]
    assert cli.main(argv) in (2, 3)
    output = capsys.readouterr()
    assert not output.out and marker not in output.err and "Traceback" not in output.err
    result = json.loads(output.err)
    assert result["automaticRetryAllowed"] is False
    if stage == "apply":
        assert result["status"] == "UNKNOWN_RECONCILE_REQUIRED"


def test_digest_refused_before_connection_and_input_read_is_bounded(cli, request_factory, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not connect")

    monkeypatch.setattr(cli.psycopg, "connect", forbidden)
    stdin(monkeypatch, cli, encoded(request_factory()))
    assert cli.main(["--apply", "--expected-plan-sha256", "0" * 64]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "FRESH-0002"

    class BoundStream:
        def read(self, count):
            assert count == MAX_REQUEST_BYTES + 1
            return b"x" * count

    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(buffer=BoundStream()))
    assert cli.main([]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "FRESH-0001"


def test_missing_selected_environment_is_closed(cli, request_factory, monkeypatch, capsys):
    monkeypatch.delenv("SYNTHETIC_MISSING_DSN", raising=False)
    stdin(monkeypatch, cli, encoded(request_factory()))
    assert cli.main(["--dsn-env", "SYNTHETIC_MISSING_DSN"]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "FRESH-0012"


def test_trusted_operator_driver_profile_is_forwarded_without_rewrite(
    cli, request_factory, monkeypatch, capsys,
):
    """Synthetic strings only: no libpq connection or credential/TLS file access.

    This checks the adapter's pass-through premise, not trust in arbitrary DSNs
    or approval of ambient service/default selection for a real operation.
    """
    marker = "SYNTHETIC_OPERATOR_CREDENTIAL_MARKER"
    dsn = ("host=synthetic.invalid port=6543 dbname=synthetic_db user=synthetic_operator "
           "password=" + marker + " sslmode=verify-full "
           "sslrootcert=/synthetic/approved-ca.pem sslcert=/synthetic/approved-client.pem "
           "sslkey=/synthetic/approved-key.pem")
    driver_environment = {
        "PGSSLROOTCERT": "/synthetic/operator-profile-ca.pem",
        "PGPASSFILE": "/synthetic/operator-approved-passfile",
    }
    monkeypatch.setenv("SYNTHETIC_SELECTED_OPERATOR_DSN", dsn)
    for name, value in driver_environment.items():
        monkeypatch.setenv(name, value)
    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def connect(received, **kwargs):
        assert received == dsn and kwargs == {"autocommit": True}
        assert all(cli.os.environ[name] == value for name, value in driver_environment.items())
        calls.append("synthetic-connection-adapter")
        return Connection()

    monkeypatch.setattr(cli.psycopg, "connect", connect)
    monkeypatch.setattr(cli, "plan_admission", lambda *a: {"mode": "PLAN", "status": "READY"})
    stdin(monkeypatch, cli, encoded(request_factory()))
    assert cli.main(["--dsn-env", "SYNTHETIC_SELECTED_OPERATOR_DSN"]) == 0
    output = capsys.readouterr()
    assert calls == ["synthetic-connection-adapter"] and not output.err
    assert marker not in output.out and "/synthetic/" not in output.out
    assert all(cli.os.environ[name] == value for name, value in driver_environment.items())
