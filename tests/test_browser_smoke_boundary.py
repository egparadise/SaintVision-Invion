"""Regression tests for tools/run_browser_smoke.mjs verification boundary (VB-MJS-02, MJS02-R1, MJS02-R2).

Validates:
1. All 4 client UI invariants (Desktop switcher, Window Manager traffic lights/z-index,
   Keyboard Alt+Tab/Escape, and Layout localStorage serialization) are explicitly marked [UNVERIFIED]
   in HTTP contract smoke and deferred to the interactive browser lane.
2. None of the 4 invariants are counted toward [PASS].
3. The isolated summary harness verifies exit codes and unverified exclusion without network/backend dependency (MJS02-R1).
4. Source code does not contain hardcoded `const ... = true; assert(..., ...)` patterns for these UI invariants (MJS02-R2).
5. Target reachability probe strictly respects TEST_BACKEND_URL and TEST_BASE_URL environment variables with matching defaults.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO_ROOT / "tools" / "run_browser_smoke.mjs"


def get_smoke_backend_url() -> str:
    return os.environ.get("TEST_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")


def get_smoke_base_url() -> str:
    return os.environ.get("TEST_BASE_URL", "http://localhost:3000").rstrip("/")


def probe_http_target(url: str, timeout: float = 1.0) -> bool:
    """Probe if an HTTP target responds with an HTTP status."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204, 401, 403)
    except Exception:
        return False


def are_smoke_targets_reachable() -> tuple[bool, str]:
    """Check if both backend and frontend targets for run_browser_smoke.mjs are reachable."""
    backend_url = get_smoke_backend_url()
    base_url = get_smoke_base_url()

    backend_ok = probe_http_target(f"{backend_url}/v1/health") or probe_http_target(f"{backend_url}/readyz")
    if not backend_ok:
        return False, f"Backend target unreachable at {backend_url} (probed /v1/health, /readyz)"

    base_ok = probe_http_target(f"{base_url}/") or probe_http_target(f"{base_url}/manifest.json")
    if not base_ok:
        return False, f"Frontend base target unreachable at {base_url} (probed /, /manifest.json)"

    return True, f"All smoke targets reachable (backend: {backend_url}, frontend: {base_url})"


def test_source_code_has_no_constant_true_assertions_for_ui_invariants() -> None:
    """VB-MJS-02 / MJS02-R2 invariant: source must not contain hardcoded constant true assertions for UI behaviors."""
    content = SMOKE_SCRIPT.read_text(encoding="utf-8")

    # All 4 constant assignments must not exist
    assert "hasDesktopShell = true" not in content, "Found hardcoded hasDesktopShell = true!"
    assert "windowManagerValid = true" not in content, "Found hardcoded windowManagerValid = true!"
    assert "keyboardA11ySupported = true" not in content, "Found hardcoded keyboardA11ySupported = true!"
    assert "layoutPersistenceValid = true" not in content, "Found hardcoded layoutPersistenceValid = true!"

    # Must record unverified with clear explanatory reasons
    assert "recordUnverified" in content
    assert "Web Desktop Shell provides bidirectional switcher" in content
    assert "Window Manager enforces traffic lights" in content
    assert "Web Desktop Shell implements Alt+Tab cycling" in content
    assert "Desktop window manager enforces local storage" in content


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for isolated summary harness")
def test_isolated_summary_harness_verifies_exit_codes_and_unverified_exclusion() -> None:
    """MJS02-R1: Isolated Node VM harness verifies summary calculation, unverified count (4), and exit codes offline."""
    harness_js = """
    import fs from 'node:fs';
    import vm from 'node:vm';
    import assert from 'node:assert/strict';

    const scriptPath = process.argv[1] && process.argv[1] !== '[eval]' && process.argv[1] !== '[eval1]' ? process.argv[1] : (process.argv[2] || 'tools/run_browser_smoke.mjs');
    const source = fs.readFileSync(scriptPath, 'utf8');
    const helper = source.slice(source.indexOf('function recordUnverified('), source.indexOf('function base64Url('));
    const tail = source.slice(source.indexOf('    // 6. Web Desktop Viewport'), source.indexOf('  } catch (err)'));

    const seeds = [
      [2, 2, 0],
      [1, 2, 1],
      [0, 0, 1]
    ];

    for (const [passed, total, expectedExit] of seeds) {
      const logs = [];
      let exitCode = 0;
      const ctx = {
        console: { log: (x) => logs.push(x) },
        process: { exit: (x) => { exitCode = x; } }
      };
      vm.createContext(ctx);
      vm.runInContext(`let passed = ${passed}, total = ${total}, unverified = 0;` + helper + tail + '; globalThis.__res = { passed, total, unverified };', ctx);

      assert.equal(ctx.__res.passed, passed);
      assert.equal(ctx.__res.total, total);
      assert.equal(ctx.__res.unverified, 4, 'Expected exactly 4 unverified UI invariants');
      assert.equal(exitCode, expectedExit, `Expected exit code ${expectedExit} for passed=${passed}, total=${total}`);

      assert.equal(logs.filter(x => x.includes('[UNVERIFIED]')).length, 4);
      assert.ok(logs.some(x => x.includes('API Contract Smoke Summary:')));
      assert.ok(!logs.some(x => x.includes('[PASS]') || x.includes('Full E2E')));
      assert.ok(!logs.some(x => x.includes('NaN%')), 'Summary should not produce NaN% when total is 0');
    }

    console.log(JSON.stringify({ status: 'ok', testedSeeds: seeds.length }));
    """

    res = subprocess.run(
        [shutil.which("node") or "node", "--input-type=module", "-e", harness_js, str(SMOKE_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert res.returncode == 0, f"Harness failed with exit {res.returncode}:\n{res.stdout}\n{res.stderr}"
    data = json.loads(res.stdout.strip())
    assert data["status"] == "ok"
    assert data["testedSeeds"] == 3


def test_smoke_targets_reachability_probe_respects_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """MJS02-R1 probe alignment: reachability probe must honor TEST_BACKEND_URL and TEST_BASE_URL overrides."""
    # 1. When pointed to an unallocated port (e.g. 127.0.0.1:1), probe returns False and diagnostic reason
    monkeypatch.setenv("TEST_BACKEND_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("TEST_BASE_URL", "http://127.0.0.1:1")
    reachable, reason = are_smoke_targets_reachable()
    assert not reachable
    assert "127.0.0.1:1" in reason

    # 2. When backend is pointed to an unallocated port but base is not
    monkeypatch.setenv("TEST_BACKEND_URL", "http://127.0.0.1:2")
    monkeypatch.delenv("TEST_BASE_URL", raising=False)
    reachable, reason = are_smoke_targets_reachable()
    assert not reachable
    assert "127.0.0.1:2" in reason
