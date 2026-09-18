"""Provisioning input and CLI failures never echo operator credentials."""

import importlib.util
from pathlib import Path
import sys
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
    ("db", "credential_provisioning_database_error", 2),
    ("internal", "credential_provisioning_internal_error", 3),
])
def test_unexpected_failures_keep_category_without_secret(monkeypatch, capsys, tmp_path, failure, expected, code):
    tool = module()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setenv("INV_CREDENTIAL_ADMIN_DSN", "postgresql://synthetic-secret")
    if failure == "db":
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(tool.ProvisioningDatabaseError("08001")))
    else:
        monkeypatch.setattr(tool, "provision", lambda *args, **kwargs: (_ for _ in ()).throw(TypeError("synthetic-secret")))
    monkeypatch.setattr(sys, "argv", ["provision", "register", "--root", "x", "--manifest", str(manifest), "--check"])
    assert tool.main() == code
    output = capsys.readouterr()
    assert expected in output.out and "synthetic-secret" not in output.out + output.err
