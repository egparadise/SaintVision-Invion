"""cleanup_owned must never let cleanup replace a test's real outcome (VF-CL-R5-01).

The bug: the container test's finally reused docker(), which raises pytest.skip on an
infrastructure failure. Skipped is a BaseException, not an Exception, so it escaped an
`except Exception` and could turn a real product failure into an "unverified" skip --
the inverse of the VF-CL-R-001 masking -- and skip the remaining removals. These pin
that cleanup is result-based: it records, never raises a pytest outcome, attempts
every resource, and still lets a genuine BaseException (KeyboardInterrupt) through.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vf_docker  # noqa: E402
from vf_docker import cleanup_owned  # noqa: E402


def _cp(argv, rc, out="", err=""):
    return subprocess.CompletedProcess(argv, rc, stdout=out, stderr=err)


def _timeout(argv, **k):
    text = bool(k.get("text"))
    r = _cp(argv, vf_docker.docker_diag.TIMEOUT_RETURNCODE,
            out=("" if text else b""), err=("timed out after 90s" if text else b"timed out after 90s"))
    r.timed_out = True
    return r


_RES = [("container", ("inspect", "c"), ("rm", "-f", "c")),
        ("config-volume", ("volume", "inspect", "v"), ("volume", "rm", "v")),
        ("working-volume", ("volume", "inspect", "w"), ("volume", "rm", "w"))]


def test_skip_outcome_is_baseexception_not_exception():
    # The exact trap: `except Exception` in a finally does NOT catch pytest.skip.
    assert issubclass(pytest.skip.Exception, BaseException)
    assert not issubclass(pytest.skip.Exception, Exception)


def test_cleanup_under_host_pressure_records_every_resource_and_never_raises(monkeypatch):
    monkeypatch.setattr(vf_docker.docker_diag, "run", _timeout)
    incomplete = cleanup_owned("this-run", _RES)          # must not raise
    assert [label for label, _ in incomplete] == ["container", "config-volume", "working-volume"]
    assert all("timed out" in why for _, why in incomplete)  # every resource attempted, recorded


def test_body_failure_survives_a_cleanup_that_cannot_run(monkeypatch):
    """The core inversion: a real body failure must NOT be replaced by cleanup's
    inability to run. cleanup_owned returns (records) instead of raising a skip."""
    monkeypatch.setattr(vf_docker.docker_diag, "run", _timeout)
    recorded = {}

    def body():
        try:
            raise AssertionError("real product assertion failed")
        finally:
            recorded["incomplete"] = cleanup_owned("this-run", _RES)

    with pytest.raises(AssertionError, match="real product assertion failed"):
        body()
    assert len(recorded["incomplete"]) == 3               # cleanup still attempted everything


def test_owned_removed_foreign_preserved_and_rm_failure_recorded(monkeypatch):
    seen = {}
    def fake(argv, **k):
        if "inspect" in argv:
            if argv[-1] in ("c", "w"):
                seen[argv[-1]] = seen.get(argv[-1], 0) + 1
                if seen[argv[-1]] == 2:
                    return _cp(argv, 1, out="", err="not found")
            # container is ours; config-volume belongs to another run; working is ours
            owner = {"c": "this-run", "v": "another-run", "w": "this-run"}[argv[-1]]
            return _cp(argv, 0, out=owner)
        # rm: the working-volume removal fails, the container removal succeeds
        return _cp(argv, 1 if argv[-1] == "w" else 0, err="volume is in use")
    monkeypatch.setattr(vf_docker.docker_diag, "run", fake)
    incomplete = cleanup_owned("this-run", _RES)
    labels = [label for label, _ in incomplete]
    assert labels == ["working-volume"]                    # foreign skipped, owned rm-fail recorded
    assert "in use" in incomplete[0][1]


def test_cleanup_does_not_swallow_baseexception(monkeypatch):
    def interrupt(argv, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(vf_docker.docker_diag, "run", interrupt)
    with pytest.raises(KeyboardInterrupt):                  # NOT swallowed by except Exception
        cleanup_owned("this-run", _RES)


def test_cleanup_records_successful_rm_without_confirmed_absence(monkeypatch):
    def fake(argv, **k):
        if "inspect" in argv:
            return _cp(argv, 0, out="this-run")
        return _cp(argv, 0)
    monkeypatch.setattr(vf_docker.docker_diag, "run", fake)
    incomplete = cleanup_owned("this-run", [("container", ("inspect", "c"), ("rm", "-f", "c"))])
    assert incomplete == [("container", "removal not confirmed; resource preserved")]


def test_cleanup_records_an_oserror_and_continues(monkeypatch):
    calls = {"n": 0}

    def fake(argv, **k):
        calls["n"] += 1
        if "inspect" in argv and argv[-1] == "c":
            raise OSError("cannot spawn docker: password=secret")  # operational, per-resource
        return _cp(argv, 0, out="this-run") if "inspect" in argv else _cp(argv, 0)
    monkeypatch.setattr(vf_docker.docker_diag, "run", fake)
    incomplete = cleanup_owned("this-run", _RES)
    assert incomplete[0][0] == "container" and "secret" not in incomplete[0][1]  # masked
    assert calls["n"] > 1                                   # continued to the other resources
