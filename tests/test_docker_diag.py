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


def test_run_classifies_a_timeout_instead_of_raising_and_does_not_retry(monkeypatch):
    """A TimeoutExpired must be caught and returned as a classified result -- letting
    it escape is the same unclassified hole this module removes (image-lane finding:
    the runner died on a raw TimeoutExpired out of docker inspect). It is also not
    retried: the attempt already spent the full timeout."""
    import subprocess

    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        raise subprocess.TimeoutExpired(cmd="docker inspect x", timeout=90)
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(docker_diag.time, "sleep", lambda *_: None)
    result = docker_diag.run(["docker", "inspect", "x"], retries=2, timeout=90)
    assert result.returncode == docker_diag.TIMEOUT_RETURNCODE
    assert docker_diag.timed_out(result) is True
    assert calls["n"] == 1  # spent the full timeout once; not retried under the same pressure
    assert docker_diag.is_infrastructure_failure(result) is True


def test_describe_names_a_timeout_as_a_host_condition_not_a_product_result():
    described = docker_diag.describe_failure(docker_diag.TIMEOUT_RETURNCODE,
                                             b"timed out after 90s", is_timeout=True)
    assert "timed out" in described and "not a product assertion result" in described


def test_infrastructure_failure_separates_host_conditions_from_docker_and_product_errors():
    import subprocess

    def _result(rc, timed=False):
        r = subprocess.CompletedProcess(["docker"], rc, stdout="", stderr=b"")
        if timed:
            r.timed_out = True
        return r

    # Host conditions -> unverified, not failed.
    assert docker_diag.is_infrastructure_failure(_result(0xC0000142))          # host-init
    assert docker_diag.is_infrastructure_failure(_result(docker_diag.TIMEOUT_RETURNCODE, timed=True))
    # A real docker error and a clean success are NOT infrastructure failures.
    assert not docker_diag.is_infrastructure_failure(_result(1))               # docker error
    assert not docker_diag.is_infrastructure_failure(_result(125))             # docker run failed
    assert not docker_diag.is_infrastructure_failure(_result(0))               # success
