"""The shared docker/host classifier (VF-CL-R-001 root cause: STATUS_DLL_INIT_FAILED).

The true root cause was not a docker error but a Windows host process-creation
failure (0xC0000142) under handle/RAM pressure. These pin the distinction the
classifier must make and the retry that only that failure warrants.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import docker_diag  # noqa: E402


def test_ntstatus_error_severity_is_a_host_init_failure_not_a_docker_error():
    assert docker_diag.is_host_process_init_failure(3221225794)   # 0xC0000142 unsigned
    assert docker_diag.is_host_process_init_failure(-1073741502)  # same, signed
    # Normal docker exit codes are never host-init failures.
    for code in (0, 1, 2, 125, 126, 127, 137):
        assert not docker_diag.is_host_process_init_failure(code)


def test_describe_names_the_ntstatus_and_masks_a_credential():
    host = docker_diag.describe_failure(3221225794)
    assert "0xC0000142" in host and "host process-creation" in host
    dock = docker_diag.describe_failure(1, b"pull denied postgresql://u:secretpw@h/db timeout")
    assert dock.startswith("docker exit 1")
    assert "secretpw" not in dock and "***" in dock and "timeout" in dock


def test_run_retries_only_a_host_init_failure(monkeypatch):
    import subprocess

    calls = {"n": 0}

    class _R:
        def __init__(self, rc): self.returncode = rc; self.stdout = ""; self.stderr = b""

    # First a host-init failure, then success: run() must retry and succeed.
    seq = iter([_R(0xC0000142), _R(0)])
    def fake(*a, **k):
        calls["n"] += 1
        return next(seq)
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(docker_diag.time, "sleep", lambda *_: None)
    result = docker_diag.run(["docker", "inspect", "x"], retries=2)
    assert result.returncode == 0 and calls["n"] == 2


def test_run_does_not_retry_a_docker_error(monkeypatch):
    import subprocess

    calls = {"n": 0}

    class _R:
        def __init__(self, rc): self.returncode = rc; self.stdout = ""; self.stderr = b"no such object"

    def fake(*a, **k):
        calls["n"] += 1
        return _R(1)  # a real docker error
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(docker_diag.time, "sleep", lambda *_: None)
    result = docker_diag.run(["docker", "inspect", "x"], retries=2)
    assert result.returncode == 1 and calls["n"] == 1  # ran once, no retry
