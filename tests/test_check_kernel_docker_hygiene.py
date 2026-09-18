"""Kernel-docker test-harness hygiene (VF-CL-R-001 remediation).

check_kernel_docker.py leaked stopped containers without bound and suppressed
docker diagnostics, so a separate image lane timed out on a resource-exhausted
host and the failure could only be guessed at. These cover the three fixes:
a masked-but-present diagnostic, a start-of-run prune of exited residue, and (by
inspection, since it needs a full run) a best-effort finally.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_kernel_docker as ckd  # noqa: E402

_HAS_DOCKER = shutil.which("docker") is not None


def test_checked_raises_with_a_masked_diagnostic_not_a_blank_message():
    # A guaranteed-failing docker-ish command; the message must carry the kind.
    with pytest.raises(RuntimeError) as exc:
        ckd.checked([sys.executable, "-c", "import sys; sys.stderr.write('boom-detail'); sys.exit(3)"])
    assert "exit 3" in str(exc.value)
    assert "boom-detail" in str(exc.value)       # diagnostic no longer suppressed


import time


def test_tools_dependencies_are_packaged_for_the_isolated_build():
    """VF-CL-R5-02: every tools/ module the orchestrator imports must be in the
    isolated build's source manifest, or the snapshot ModuleNotFounds it (the host
    build hides this because the original repo is on sys.path, so the host-based
    suites pass regardless). docker_diag.py was the omission. This catches it and any
    future one by walking check_kernel_docker's own imports."""
    import ast

    source = Path(ckd.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    tools_dir = Path(ckd.__file__).parent
    local_tool_deps = {"tools/%s.py" % name for name in imported if (tools_dir / (name + ".py")).exists()}
    assert local_tool_deps, "expected at least docker_diag among the orchestrator's tools imports"
    missing = local_tool_deps - set(ckd.EXACT_SOURCE_FILES)
    assert not missing, "tools modules imported by check_kernel_docker but absent from the isolated source manifest: " + ", ".join(sorted(missing))
    assert "tools/docker_diag.py" in ckd.EXACT_SOURCE_FILES


def test_run_on_timeout_stays_bytes_so_decode_sites_do_not_crash(monkeypatch):
    """check_kernel_docker calls run() without text= and .decode()s the result. A
    timeout must therefore return bytes, not str, or every decode site (and the build-
    log write_bytes) raises the moment host pressure causes a timeout -- the exact
    AttributeError that a best-effort wrapper then silently swallowed (VF-CL-R-001
    masking one layer down)."""
    def timeout(argv, **k):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
    monkeypatch.setattr(subprocess, "run", timeout)
    result = ckd.run(["docker", "ps", "-aq"], timeout=1)          # the prune's own call shape
    assert isinstance(result.stdout, bytes) and isinstance(result.stderr, bytes)
    assert result.stdout.decode("utf-8", "replace").split() == []  # would have AttributeError'd


def test_checked_on_timeout_raises_a_classified_error_not_an_attributeerror(monkeypatch):
    def timeout(argv, **k):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError) as exc:
        ckd.checked(["docker", "inspect", "x"], timeout=1)
    assert "timed out" in str(exc.value)      # named, not a raw AttributeError


def _present(name):
    return subprocess.run(["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
                          capture_output=True, text=True, timeout=30).stdout.strip()


def _running(name):
    return subprocess.run(["docker", "ps", "-q", "--filter", f"name=^{name}$"],
                          capture_output=True, text=True, timeout=30).stdout.strip()


@pytest.mark.skipif(not _HAS_DOCKER, reason="docker CLI is required")
def test_prune_removes_old_exited_residue_but_spares_a_recent_one():
    """Age gate (VF-CL-R2-01): a just-exited container may belong to a concurrent
    run, so it is spared; only residue older than the threshold is removed."""
    label = "ai.saintvision.kernel-test"
    recent = f"ckd-hyg-{uuid.uuid4().hex[:8]}"
    try:
        subprocess.run(["docker", "run", "-d", "--name", recent, "--label", f"{label}=probe",
                        "alpine:3", "true"], capture_output=True, timeout=60)
        time.sleep(1)  # now exited, age ~1s

        # A large min-age protects the recent container -- it might be a concurrent run's.
        ckd.prune_stale_kernel_test_residue(min_age_seconds=9999)
        assert _present(recent) != "", "prune removed a recent exited container (concurrent-run race)"

        # With the age gate lowered, the same residue is genuine and removed.
        ckd.prune_stale_kernel_test_residue(min_age_seconds=0)
        assert _present(recent) == "", "prune did not remove old exited residue"
    finally:
        subprocess.run(["docker", "rm", "-f", recent], capture_output=True, timeout=60)


@pytest.mark.skipif(not _HAS_DOCKER, reason="docker CLI is required")
def test_prune_never_force_removes_a_running_concurrent_container():
    """VF-CL-R2-01: a concurrent run's *running* kernel-test container must survive
    prune even with the age gate off, because prune uses a non-force rm."""
    concurrent = f"ckd-hyg-run-{uuid.uuid4().hex[:8]}"
    other_label = f"ckd-hyg-other-{uuid.uuid4().hex[:8]}"
    try:
        # Same kernel-test label as prune targets, but running (a concurrent run).
        subprocess.run(["docker", "run", "-d", "--name", concurrent,
                        "--label", "ai.saintvision.kernel-test=concurrent-run",
                        "alpine:3", "sleep", "120"], capture_output=True, timeout=60)
        # And a running container under a different label.
        subprocess.run(["docker", "run", "-d", "--name", other_label,
                        "--label", "ai.saintvision.configured=keep",
                        "alpine:3", "sleep", "120"], capture_output=True, timeout=60)
        time.sleep(1)

        ckd.prune_stale_kernel_test_residue(min_age_seconds=0)  # age gate off, most aggressive

        assert _running(concurrent) != "", "prune force-removed a running concurrent kernel-test container"
        assert _running(other_label) != "", "prune removed a running, differently-labelled container"
    finally:
        subprocess.run(["docker", "rm", "-f", concurrent, other_label], capture_output=True, timeout=60)
