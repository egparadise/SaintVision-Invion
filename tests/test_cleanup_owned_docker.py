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
    monkeypatch.setattr(tool, "_engine_counts", lambda: (_ for _ in ()).throw(RuntimeError("engine unavailable")))
    resources, unavailable, counts = tool._resources()
    assert resources == []
    assert {entry["kind"] for entry in unavailable} == {"inventory", "container", "volume", "network"}
    assert counts == {}


def test_inventory_mismatch_is_unverified_and_delete_aborts(monkeypatch, capsys):
    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake(args):
        if args[:4] == ["docker", "container", "ls", "-a"] and args[-1] == "-q":
            return Result("one\ntwo\n")
        if args[:4] == ["docker", "container", "ls", "-a"] and args[-2:] == ["--format", "{{.ID}}"]:
            return Result("one\n")
        return Result("")

    monkeypatch.setattr(tool, "_run", fake)
    monkeypatch.setattr(tool, "_engine_counts", lambda: {"container": 1, "volume": 0, "network": 0})
    resources, unavailable, counts = tool._resources()
    assert resources == []
    assert any(entry["kind"] == "container" and "count mismatch" in entry["reason"] for entry in unavailable)
    assert counts["container"] == {"enumerated": 2, "independent": 1}

    result = tool.main(["--delete"])
    assert result == 2
    assert '"deleteAborted": "incomplete inventory; no deletion attempted"' in capsys.readouterr().out


def test_container_removal_deletes_image_declared_anonymous_volumes(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(tool, "_run", lambda args: calls.append(args) or Result())
    monkeypatch.setattr(tool, "_inspect", lambda kind, identifier: None)
    ok, reason = tool._remove({"kind": "container", "id": "owned-container"})
    assert ok and reason == "confirmed-removed"
    assert calls == [["docker", "container", "rm", "-f", "-v", "owned-container"]]


def test_symmetric_container_flag_loss_is_detected_by_daemon_count(monkeypatch):
    class Result:
        returncode = 0
        stderr = ""
        stdout = "one\ntwo\nthree\n"

    monkeypatch.setattr(tool, "_run", lambda args: Result())
    monkeypatch.setattr(tool, "_engine_counts", lambda: {"container": 53, "volume": 0, "network": 0})
    resources, unavailable, counts = tool._resources()
    assert resources == []
    assert counts["container"] == {"enumerated": 3, "independent": 53}
    assert any(entry["kind"] == "container" and "count mismatch" in entry["reason"] for entry in unavailable)
