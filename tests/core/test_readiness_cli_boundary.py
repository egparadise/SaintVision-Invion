"""Readiness diagnostics cannot expose operator connection secrets."""

import importlib.util
from pathlib import Path
import sys

import pytest


def _tool():
    path = Path(__file__).resolve().parents[2] / "tools" / "operational_readiness.py"
    spec = importlib.util.spec_from_file_location("readiness_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_dsn_argument_is_rejected_without_echo(monkeypatch, capsys):
    secret = "postgresql://operator:synthetic-password@localhost/database"
    monkeypatch.setattr(sys, "argv", ["readiness", "--dsn", secret, "--tenant", "tenant"])
    with pytest.raises(SystemExit) as raised:
        _tool().main()
    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert "synthetic-password" not in captured.out + captured.err


def test_connection_failure_is_sanitized(monkeypatch, capsys):
    tool = _tool()
    secret = "synthetic-readiness-password"
    monkeypatch.setenv("INV_READINESS_DSN", secret)
    monkeypatch.setattr(sys, "argv", ["readiness", "--tenant", "tenant", "--json"])

    def fail(args):
        raise RuntimeError(secret)

    monkeypatch.setattr(tool, "report", fail)
    assert tool.main() == 2
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert "operational_readiness_unavailable" in captured.out


def test_report_uses_read_only_repeatable_snapshot(monkeypatch):
    import argparse
    import psycopg

    tool = _tool()
    commands = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, *args):
            commands.append(query)

    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: Connection())
    monkeypatch.setattr(tool, "inputs", lambda *a: {})
    monkeypatch.setattr(tool, "offers", lambda *a: {})
    monkeypatch.setattr(tool, "admission", lambda *a: {})
    tool.report(argparse.Namespace(dsn="synthetic", tenant="tenant", project=None, user=None))
    assert commands[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert "set_config('inv.tenant_id', %s, true)" in commands[1]
