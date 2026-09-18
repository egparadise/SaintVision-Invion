"""Integration test executing the live tools/run_browser_smoke.mjs against running control plane.

This test is placed in tests/integration/ and requires explicit opt-in via
INV_BROWSER_SMOKE_INTEGRATION=1 to prevent automatic execution during default unit/offline test runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_browser_smoke_boundary import are_smoke_targets_reachable

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "tools" / "run_browser_smoke.mjs"

pytestmark = [
    pytest.mark.skipif(
        os.getenv("INV_BROWSER_SMOKE_INTEGRATION") != "1",
        reason="Explicit browser smoke integration lane required (INV_BROWSER_SMOKE_INTEGRATION=1)",
    ),
    pytest.mark.skipif(
        shutil.which("node") is None,
        reason="Node.js is required to execute browser smoke",
    ),
]


def test_smoke_runner_reports_four_unverified_and_observed_checks_in_integration() -> None:
    """MJS02-R1 execution contract: runner outputs 4 [UNVERIFIED] items and clean exit 0 on active targets."""
    reachable, reason = are_smoke_targets_reachable()
    if not reachable:
        pytest.skip(f"Smoke targets unreachable: {reason}; skipping live integration smoke")

    res = subprocess.run(
        [shutil.which("node") or "node", str(SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=40,
    )

    assert res.returncode == 0, f"Smoke runner exited with {res.returncode}:\n{res.stdout}\n{res.stderr}"
    stdout = res.stdout

    # 1. Assert all 4 UI items are explicitly logged as [UNVERIFIED]
    assert "ℹ [UNVERIFIED] Web Desktop Shell provides bidirectional switcher" in stdout
    assert "ℹ [UNVERIFIED] Window Manager enforces traffic lights" in stdout
    assert "ℹ [UNVERIFIED] Web Desktop Shell implements Alt+Tab cycling" in stdout
    assert "ℹ [UNVERIFIED] Desktop window manager enforces local storage" in stdout

    # 2. Assert none of the 4 are logged as [PASS]
    assert "✔ [PASS] Web Desktop Shell provides bidirectional switcher" not in stdout
    assert "✔ [PASS] Window Manager enforces traffic lights" not in stdout
    assert "✔ [PASS] Web Desktop Shell implements Alt+Tab cycling" not in stdout
    assert "✔ [PASS] Desktop window manager enforces local storage" not in stdout

    # 3. Assert summary reflects 4 unverified UI invariants
    assert "4 unverified UI invariants deferred to browser lane" in stdout
    assert "observed checks passed" in stdout

    # 4. Assert legacy 202 checks passed or Full E2E is NOT claimed
    assert "202/202 checks passed" not in stdout
    assert "Full E2E Browser Journey Smoke Summary" not in stdout
