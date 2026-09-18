"""Provisioning input and CLI failures never echo operator credentials."""

import importlib.util
from pathlib import Path
import sys
import types
import pytest


def module():
    p = Path(__file__).resolve().parents[2] / "tools/provision_credentials.py"
    spec = importlib.util.spec_from_file_location("credential_admin_cli", p)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


@pytest.mark.parametrize(
    "arguments",
    [
        ["register", "--dsn", "postgresql://synthetic-secret"],
        ["secret-action", "--manifest", "x", "--root", "x"],
    ],
)
def test_argument_errors_are_sanitized(monkeypatch, capsys, arguments):
    monkeypatch.setattr(sys, "argv", ["provision"] + arguments)
    with pytest.raises(SystemExit) as raised:
        module().main()
    assert raised.value.code == 2
    output = capsys.readouterr()
    assert "synthetic-secret" not in output.err + output.out
    assert "secret-action" not in output.err + output.out


def test_manifest_error_has_no_input_text():
    tool = module()
    with pytest.raises(tool.ProvisioningDenied) as raised:
        tool.validate_manifest({"secret": "synthetic-private-value"}, "register")
    assert str(raised.value) == "Credential provisioning refused"


def test_missing_connection_configuration_does_not_leak(monkeypatch, capsys):
    monkeypatch.delenv("INV_CREDENTIAL_ADMIN_DSN", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["provision", "register", "--root", "x", "--manifest", "synthetic-private-path"],
    )
    assert module().main() == 2
    output = capsys.readouterr()
    assert "synthetic-private-path" not in output.err + output.out
    assert "credential_provisioning_refused" in output.out


@pytest.mark.parametrize("failure,expected,code", [
    ("denied", "credential_provisioning_refused", 2),
    ("db", "credential_provisioning_database_error", 3),
    ("type", "credential_provisioning_internal_error", 4),
    ("runtime", "credential_provisioning_internal_error", 4),
])
def test_unexpected_failures_keep_category_without_secret(monkeypatch, capsys, tmp_path, failure, expected, code):
    tool = module()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setenv("INV_CREDENTIAL_ADMIN_DSN", "postgresql://synthetic-secret")
    if failure == "denied":
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(tool.ProvisioningDenied()))
    elif failure == "db":
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(tool.ProvisioningDatabaseError("08001")))
    elif failure == "type":
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(TypeError("synthetic-secret")))
    else:
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic-secret")))
    monkeypatch.setattr(sys, "argv", ["provision", "register", "--root", "x", "--manifest", str(manifest), "--check"])
    assert tool.main() == code
    output = capsys.readouterr()
    assert expected in output.out and "synthetic-secret" not in output.out + output.err


def test_provisioning_exit_codes_are_one_to_one_with_labels():
    tool = module()
    assert len({tool.EXIT_REFUSED, tool.EXIT_DATABASE, tool.EXIT_INTERNAL}) == 3


def test_provision_maps_inner_failures_without_secret_text_and_rolls_back(monkeypatch):
    """The transaction boundary preserves categories without trusting the Linux-only test."""
    tool = module()
    secret = "synthetic-private-detail"
    manifest = {"tenant": "tenant", "project": "project", "run": "run", "epoch": "epoch", "credential": "credential", "version": "version", "subject": "subject"}
    monkeypatch.setattr(tool, "validate_manifest", lambda value, action: manifest)

    class FakeDatabaseError(Exception):
        sqlstate = "08001"

    class FakeConnection:
        rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.rolled_back = exc_type is not None
            return False

        def execute(self, *args, **kwargs):
            raise RuntimeError(secret)

    connection = FakeConnection()
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.Error = FakeDatabaseError
    fake_psycopg.connect = lambda *args, **kwargs: connection
    fake_rows = types.ModuleType("psycopg.rows")
    fake_rows.dict_row = object()
    fake_psycopg.rows = fake_rows
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", fake_rows)

    with pytest.raises(tool.ProvisioningInternalError) as raised:
        tool.provision("postgresql://" + secret, "/tmp", manifest, "register")
    assert raised.value.error_type == "RuntimeError"
    assert secret not in str(raised.value)
    assert connection.rolled_back


def test_provision_maps_driver_error_to_database_category(monkeypatch):
    tool = module()
    class FakeDatabaseError(Exception):
        sqlstate = "08001"
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.Error = FakeDatabaseError
    fake_psycopg.connect = lambda *args, **kwargs: (_ for _ in ()).throw(FakeDatabaseError("synthetic-private-detail"))
    fake_rows = types.ModuleType("psycopg.rows")
    fake_rows.dict_row = object()
    fake_psycopg.rows = fake_rows
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", fake_rows)
    monkeypatch.setattr(tool, "validate_manifest", lambda value, action: {})
    with pytest.raises(tool.ProvisioningDatabaseError) as raised:
        tool.provision("postgresql://synthetic-private-detail", "/tmp", {}, "register")
    assert raised.value.sqlstate == "08001"
    assert "synthetic-private-detail" not in str(raised.value)
