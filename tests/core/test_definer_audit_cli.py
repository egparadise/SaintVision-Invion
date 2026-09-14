"""Public diagnostics never expose failed-audit connection strings or SQL."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "definer_audit_cli", Path(__file__).resolve().parents[2] / "tools/check_definer_functions.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


@pytest.mark.parametrize("mode", ["connection", "policy", "missing"])
def test_unavailable_audit_is_nonzero_and_redacted(monkeypatch, capsys, tmp_path, mode):
    monkeypatch.setattr("sys.argv", ["check_definer_functions.py", "--json"])
    monkeypatch.setenv("INV_AUDIT_DSN", "postgresql://operator:must-not-print@localhost/database")
    if mode == "connection":

        def failed(_):
            raise RuntimeError("postgresql://operator:must-not-print@localhost/database SQL secret")

        monkeypatch.setattr(tool, "audit", failed)
    elif mode == "policy":
        empty = tmp_path / "policy.json"
        empty.write_text('{"version":1,"revision":"head","functions":{}}')
        monkeypatch.setattr(tool, "POLICY_PATH", empty)
    else:
        monkeypatch.delenv("INV_AUDIT_DSN")
    assert tool.main() == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "unavailable",
        "error": "catalog_observation_failed",
        "unsafe": None,
    }
    assert not captured.err
