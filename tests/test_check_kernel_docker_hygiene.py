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


def test_masked_keeps_the_error_kind_and_hides_the_credential():
    stderr = (b"Error: postgresql://postgres:supersecret123@db:5432/postgres "
              b"context deadline exceeded")
    out = ckd._masked(stderr)
    assert "supersecret123" not in out          # credential value masked
    assert "***" in out
    assert "context deadline exceeded" in out    # error kind preserved


def test_masked_handles_empty_stderr():
    assert ckd._masked(b"") == "(no stderr)"
    assert ckd._masked(None) == "(no stderr)"


def test_checked_raises_with_a_masked_diagnostic_not_a_blank_message():
    # A guaranteed-failing docker-ish command; the message must carry the kind.
    with pytest.raises(RuntimeError) as exc:
        ckd.checked([sys.executable, "-c", "import sys; sys.stderr.write('boom-detail'); sys.exit(3)"])
    assert "exit 3" in str(exc.value)
    assert "boom-detail" in str(exc.value)       # diagnostic no longer suppressed


@pytest.mark.skipif(not _HAS_DOCKER, reason="docker CLI is required")
def test_prune_removes_exited_kernel_test_residue_and_spares_running_others():
    label = "ai.saintvision.kernel-test"
    exited = [f"ckd-hyg-{uuid.uuid4().hex[:8]}" for _ in range(2)]
    survivor = f"ckd-hyg-run-{uuid.uuid4().hex[:8]}"
    try:
        for name in exited:
            subprocess.run(["docker", "run", "-d", "--name", name, "--label", f"{label}=probe",
                            "alpine:3", "true"], capture_output=True, timeout=60)
        # A running container under a DIFFERENT label must never be touched.
        subprocess.run(["docker", "run", "-d", "--name", survivor,
                        "--label", "ai.saintvision.configured=keep", "alpine:3", "sleep", "120"],
                       capture_output=True, timeout=60)
        import time
        time.sleep(1)

        ckd.prune_stale_kernel_test_residue()

        for name in exited:
            gone = subprocess.run(["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
                                  capture_output=True, text=True, timeout=30).stdout.strip()
            assert gone == "", f"exited kernel-test residue {name} was not pruned"
        alive = subprocess.run(["docker", "ps", "-q", "--filter", f"name=^{survivor}$"],
                              capture_output=True, text=True, timeout=30).stdout.strip()
        assert alive != "", "a running, differently-labelled container was wrongly removed"
    finally:
        subprocess.run(["docker", "rm", "-f", survivor, *exited], capture_output=True, timeout=60)
