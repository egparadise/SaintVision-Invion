import importlib.util
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "tools" / "cleanup_owned_docker.py"
spec = importlib.util.spec_from_file_location("cleanup_owned_docker", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def test_volume_created_at_is_aged_and_evidence_policy_is_longer():
    value = {
        "kind": "volume",
        "name": "sv-remote-workspace-old-node-state",
        "created": "2020-01-01T00:00:00Z",
        "owner": ("ai.saintvision.remote-test", "run"),
        "running": False,
        "networkContainers": False,
    }
    assert tool._eligible(value, 30) == (True, "eligible")
    recent = dict(value, created="2999-01-01T00:00:00Z")
    eligible, reason = tool._eligible(recent, 30)
    assert not eligible and "intentional evidence retention" in reason


def test_inventory_failure_is_reported_not_as_empty_success(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "volume inventory unavailable"

    monkeypatch.setattr(tool, "_run", lambda args: Result())
    resources, unavailable = tool._resources()
    assert resources == []
    assert {entry["kind"] for entry in unavailable} == {"container", "volume", "network"}
