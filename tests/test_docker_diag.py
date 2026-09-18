"""The shared docker/host classifier (VF-CL-R-001 root cause: STATUS_DLL_INIT_FAILED).

The true root cause was not a docker error but a Windows host process-creation
failure (0xC0000142) under handle/RAM pressure. These pin the distinctions the
classifier must make -- loader-stage init failure vs running-process crash vs POSIX
signal vs timeout vs plain docker error -- the retry that only a *safe* failure
warrants, and the credential masking that must cover every DSN form (Codex R3-01 /
R2-03, 2026-09-18).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import docker_diag  # noqa: E402


def _result(rc, *, timed=False, stderr=b""):
    r = subprocess.CompletedProcess(["docker"], rc, stdout="", stderr=stderr)
    if timed:
        r.timed_out = True
    return r


def test_only_loader_stage_ntstatus_is_a_host_init_failure_and_it_is_platform_gated():
    # Loader-stage failures (before the entry point): the process never ran -> retryable.
    for code in (3221225794, -1073741502):        # 0xC0000142 unsigned / signed
        assert docker_diag.is_host_process_init_failure(code, windows=True)
    assert docker_diag.is_host_process_init_failure(0xC0000135, windows=True)  # DLL_NOT_FOUND
    # A running-process crash and a POSIX signal are NOT init failures: they ran.
    assert not docker_diag.is_host_process_init_failure(0xC0000005, windows=True)  # access violation
    assert not docker_diag.is_host_process_init_failure(-9, windows=True)          # SIGKILL, not NTSTATUS
    assert not docker_diag.is_host_process_init_failure(-9, windows=False)
    # An NTSTATUS is meaningless off Windows -- never read a POSIX code as one.
    assert not docker_diag.is_host_process_init_failure(3221225794, windows=False)
    # Normal docker exit codes are never host-init failures, on any platform.
    for code in (0, 1, 2, 124, 125, 126, 127, 137):
        assert not docker_diag.is_host_process_init_failure(code, windows=True)


def test_describe_separates_init_failure_crash_signal_timeout_and_docker_error():
    init = docker_diag.describe_failure(3221225794, windows=True)
    assert "0xC0000142" in init and "host process-creation" in init
    crash = docker_diag.describe_failure(0xC0000005, windows=True)
    assert "crashed after starting" in crash and "not retried" in crash
    signal = docker_diag.describe_failure(-9, windows=False)
    assert "signal 9" in signal and "not retried" in signal
    timeout = docker_diag.describe_failure(docker_diag.TIMEOUT_RETURNCODE,
                                           b"timed out after 90s", is_timeout=True)
    assert "timed out" in timeout and "not a product assertion result" in timeout
    dock = docker_diag.describe_failure(1, b"no such object", windows=True)
    assert dock.startswith("docker exit 1") and "no such object" in dock


def test_masks_url_libpq_and_quoted_credentials_but_keeps_the_error():
    raw = (b"connect failed: postgresql://u:urlsecret@h/db ; "
           b"host=h password=libqsecret dbname=d ; password='quoted secret'")
    out = docker_diag.masked_stderr(raw)
    for secret in (b"urlsecret", b"libqsecret", b"quoted secret"):
        assert secret.decode() not in out
    assert out.count("***") >= 3
    assert "connect failed" in out   # the error kind is preserved
    assert "dbname=d" in out         # non-secret keywords survive


def test_infrastructure_failure_separates_host_conditions_from_crash_and_docker_error(monkeypatch):
    monkeypatch.setattr(docker_diag, "_on_windows", lambda: True)
    assert docker_diag.is_infrastructure_failure(_result(0xC0000142))                    # loader init
    assert docker_diag.is_infrastructure_failure(_result(docker_diag.TIMEOUT_RETURNCODE, timed=True))
    # A crash, a real docker error and a clean success are NOT infrastructure failures.
    assert not docker_diag.is_infrastructure_failure(_result(0xC0000005))                # crash: ran
    assert not docker_diag.is_infrastructure_failure(_result(1))                         # docker error
    assert not docker_diag.is_infrastructure_failure(_result(125))                       # docker run failed
    assert not docker_diag.is_infrastructure_failure(_result(0))                         # success


def test_run_retries_only_a_loader_init_failure_and_preserves_each_attempt(monkeypatch):
    monkeypatch.setattr(docker_diag, "_on_windows", lambda: True)
    attempts = []

    class _R:
        def __init__(self, rc): self.returncode = rc; self.stdout = ""; self.stderr = b""

    # A loader init failure then success: retry once and surface the second attempt.
    seq = iter([_R(0xC0000142), _R(0)])

    def fake(*a, **k):
        r = next(seq)
        attempts.append(r.returncode)
        return r
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(docker_diag.time, "sleep", lambda *_: None)
    result = docker_diag.run(["docker", "inspect", "x"], retries=2)
    assert result.returncode == 0
    assert attempts == [0xC0000142, 0]           # each attempt's result is preserved, in order


def test_run_does_not_retry_a_mutating_command_that_crashed_after_running(monkeypatch):
    """R3-01: a mutating command (``docker volume create``) that returns a running
    crash code (0xC0000005 access violation) may already have created the resource, so
    it must be attempted exactly once -- retrying would duplicate it."""
    monkeypatch.setattr(docker_diag, "_on_windows", lambda: True)
    calls = {"n": 0}

    class _R:
        def __init__(self, rc): self.returncode = rc; self.stdout = ""; self.stderr = b"access violation"

    def fake(*a, **k):
        calls["n"] += 1
        return _R(0xC0000005)
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(docker_diag.time, "sleep", lambda *_: None)
    result = docker_diag.run(["docker", "volume", "create", "x"], retries=2)
    assert result.returncode == 0xC0000005 and calls["n"] == 1   # ran once, not retried


def test_run_does_not_retry_a_docker_error(monkeypatch):
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
    it escape is the same unclassified hole this module removes (the runner died on a
    raw TimeoutExpired out of docker inspect). It is also not retried: the attempt
    already spent the full timeout."""
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


def test_run_default_retry_is_a_single_transient_cushion():
    import inspect
    assert inspect.signature(docker_diag.run).parameters["retries"].default == 1
