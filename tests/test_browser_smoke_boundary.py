"""Regression tests for tools/run_browser_smoke.mjs verification boundary (VB-MJS-02).

Validates:
1. The 3 client UI invariants (Window Manager traffic lights/z-index, Keyboard Alt+Tab/Escape,
   and Layout localStorage serialization) are explicitly marked [UNVERIFIED] in HTTP contract smoke
   and deferred to the interactive browser lane.
2. None of the 3 invariants are counted toward [PASS].
3. The summary dossier explicitly reports 199/199 observed checks passed and 3 unverified UI invariants,
   without claiming 202 passed.
4. Source code does not contain hardcoded `const ... = true; assert(..., ...)` patterns for these UI invariants.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "tools" / "run_browser_smoke.mjs"


def test_source_code_has_no_constant_true_assertions_for_ui_invariants() -> None:
    """VB-MJS-02 invariant: source must not contain hardcoded constant true assertions for UI behaviors."""
    content = SMOKE_SCRIPT.read_text(encoding="utf-8")

    # The 3 constant assignments must not exist
    assert "windowManagerValid = true" not in content, "Found hardcoded windowManagerValid = true!"
    assert "keyboardA11ySupported = true" not in content, "Found hardcoded keyboardA11ySupported = true!"
    assert "layoutPersistenceValid = true" not in content, "Found hardcoded layoutPersistenceValid = true!"

    # Must record unverified with clear explanatory reasons
    assert "recordUnverified" in content
    assert "Requires interactive DOM browser lane" in content
    assert "Requires interactive keyboard input browser lane" in content
    assert "Requires browser localStorage persistence lane" in content


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required to execute browser smoke")
def test_smoke_runner_reports_three_unverified_and_199_observed_checks() -> None:
    """VB-MJS-02 execution contract: runner outputs 3 [UNVERIFIED] items and exactly 199 observed checks."""
    res = subprocess.run(
        [shutil.which("node") or "node", str(SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Process must exit cleanly with code 0 on active backend
    assert res.returncode == 0, f"Smoke runner exited with {res.returncode}:\n{res.stdout}\n{res.stderr}"

    stdout = res.stdout

    # 1. Assert each of the 3 items is explicitly logged as [UNVERIFIED]
    wm_unverified = "ℹ [UNVERIFIED] Window Manager enforces traffic lights, z-index elevation, and minimize/maximize"
    kb_unverified = "ℹ [UNVERIFIED] Web Desktop Shell implements Alt+Tab cycling and Escape modal dismissal protocol"
    lp_unverified = "ℹ [UNVERIFIED] Desktop window manager enforces local storage layout serialization protocol"

    assert wm_unverified in stdout
    assert kb_unverified in stdout
    assert lp_unverified in stdout

    # 2. Assert none of the 3 are logged as [PASS]
    assert "✔ [PASS] Window Manager enforces traffic lights" not in stdout
    assert "✔ [PASS] Web Desktop Shell implements Alt+Tab cycling" not in stdout
    assert "✔ [PASS] Desktop window manager enforces local storage layout serialization" not in stdout

    # 3. Assert summary reflects 199 observed checks and 3 unverified
    assert "199/199 observed checks passed" in stdout
    assert "3 unverified UI invariants deferred to browser lane" in stdout

    # 4. Assert legacy 202 checks passed is NOT claimed
    assert "202/202 checks passed" not in stdout
    assert "Full E2E Browser Journey Smoke Summary: 202/202" not in stdout
