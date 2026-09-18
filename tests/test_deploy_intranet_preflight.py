"""Regression tests for tools/deploy_intranet.ps1 preflight launcher (VB-LAUNCH-01).

Asserts that:
1. When TLS certificate generation fails (native exit code 23), the script halts immediately
   at Step 1 with exit code 1 and never proceeds to Step 2 (Vitest).
2. When TLS certificate generation exits with 0 but leaves certificate files missing or empty (0 bytes),
   the script halts at Step 1 with exit code 1.
3. When production build fails to generate apps/web/dist/index.html, the script halts at Step 3
   with exit code 1 and never proceeds to Step 4 (E2E browser smoke).
4. Summary banner contains honest scope assertions distinguishing local preflight from physical
   5-node hardware acceptance.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = REPO_ROOT / "tools" / "deploy_intranet.ps1"


def get_powershell_executable() -> str | None:
    return shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")


pytestmark = pytest.mark.skipif(
    get_powershell_executable() is None,
    reason="PowerShell is required to test tools/deploy_intranet.ps1",
)


def run_ps1_in_dir(script_content: str, working_dir: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    ps_exe = get_powershell_executable()
    assert ps_exe is not None

    script_path = working_dir / "deploy_intranet.ps1"
    script_path.write_text(script_content, encoding="utf-8")

    return subprocess.run(
        [ps_exe, "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        cwd=working_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_cert_generation_native_failure_halts_immediately(tmp_path: Path) -> None:
    """VB-LAUNCH-01 negative control: native python nonzero exit (23) must halt at Step 1 with exit 1."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # Injected synthetic cert generator that fails with native exit code 23
    mock_generator = tools_dir / "generate_tls_cert.py"
    mock_generator.write_text("import sys\nsys.stderr.write('synthetic cert generation failure')\nsys.exit(23)\n", encoding="utf-8")

    # Marker file to detect if Step 2 was erroneously reached
    step2_marker = tmp_path / "step2_executed.marker"

    # Copy deploy_intranet.ps1 content, but ensure any step 2 invocation records the marker
    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Inject marker creation into Step 2 to verify Step 2 never executes
    content_with_marker = orig_content.replace(
        "[2/5] Running Frontend & Protocol Automated Tests",
        f"New-Item -ItemType File -Force '{step2_marker.as_posix()}'; [2/5] Running Frontend & Protocol Automated Tests",
    )

    res = run_ps1_in_dir(content_with_marker, tmp_path)

    # Must fail with exit code 1
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"

    # Verify Step 1 failure is reported
    assert "TLS certificate generation failed with exit code 23" in res.stdout or "TLS certificate generation failed with exit code 23" in res.stderr

    # Verify Step 2 was NEVER executed
    assert not step2_marker.exists(), "Step 2 executed despite Step 1 native failure!"
    assert "[2/5] Running Frontend & Protocol Automated Tests" not in res.stdout
    assert "Preflight Deployment Pipeline Completed with ZERO Errors" not in res.stdout
    assert "[2/5] Frontend & Protocol Tests: VERIFIED" not in res.stdout


def test_cert_generation_empty_file_halts_immediately(tmp_path: Path) -> None:
    """VB-LAUNCH-01 negative control: 0-byte cert or key files must halt at Step 1 with exit 1."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic cert generator that exits 0 but creates empty 0-byte files
    mock_generator = tools_dir / "generate_tls_cert.py"
    mock_generator.write_text(
        textwrap.dedent("""
            from pathlib import Path
            p = Path("deploy/certs")
            p.mkdir(parents=True, exist_ok=True)
            (p / "saintvision.crt").write_bytes(b"")
            (p / "saintvision.key").write_bytes(b"")
        """),
        encoding="utf-8",
    )

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    res = run_ps1_in_dir(orig_content, tmp_path)

    assert res.returncode == 1
    assert "must be non-empty (>0 bytes)" in res.stdout or "must be non-empty (>0 bytes)" in res.stderr
    assert "[2/5] Running Frontend & Protocol Automated Tests" not in res.stdout


def test_missing_cert_file_after_generation_halts_immediately(tmp_path: Path) -> None:
    """VB-LAUNCH-01 negative control: missing cert files after exit 0 must halt at Step 1 with exit 1."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic cert generator that exits 0 but writes nothing
    mock_generator = tools_dir / "generate_tls_cert.py"
    mock_generator.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    res = run_ps1_in_dir(orig_content, tmp_path)

    assert res.returncode == 1
    assert "do not exist after generation step" in res.stdout or "do not exist after generation step" in res.stderr
    assert "[2/5] Running Frontend & Protocol Automated Tests" not in res.stdout


def test_missing_build_dist_index_halts_at_step3(tmp_path: Path) -> None:
    """Negative control: missing dist/index.html after npm run build halts at Step 3 with exit 1."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    web_dir = tmp_path / "apps" / "web"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)

    # Valid non-empty certs already exist
    (certs_dir / "saintvision.crt").write_bytes(b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")
    (certs_dir / "saintvision.key").write_bytes(b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")

    step4_marker = tmp_path / "step4_executed.marker"

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Stub out npm calls to exit 0 without generating dist/index.html
    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "Write-Host 'mock build pass without dist'; $global:LASTEXITCODE = 0",
    ).replace(
        "[4/5] Running E2E Smoke",
        f"New-Item -ItemType File -Force '{step4_marker.as_posix()}'; [4/5] Running E2E Smoke",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 1
    assert "Production build artifact 'apps/web/dist/index.html' does not exist" in res.stdout
    assert not step4_marker.exists(), "Step 4 executed despite missing dist/index.html!"
    assert "[4/5] Running E2E Smoke" not in res.stdout


def test_honest_summary_table_format(tmp_path: Path) -> None:
    """Verifies that on successful preflight, the summary table reflects honest step status and scope boundary."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    (certs_dir / "saintvision.crt").write_bytes(b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")
    (certs_dir / "saintvision.key").write_bytes(b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")
    (dist_dir / "index.html").write_bytes(b"<!doctype html><html><body>SaintVision</body></html>")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "Write-Host 'mock build pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "node tools/run_browser_smoke.mjs",
        "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "docker compose -f docker-compose.prod.yml config --quiet",
        "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 0, f"Unexpected failure: {res.stdout}\n{res.stderr}"
    assert "[1/5] TLS 1.3 Certificates:        VERIFIED" in res.stdout
    assert "[2/5] Frontend & Protocol Tests:    VERIFIED" in res.stdout
    assert "[3/5] Production Asset Build:       VERIFIED" in res.stdout
    assert "[4/5] E2E Browser Smoke Suite:      VERIFIED" in res.stdout
    assert "[5/5] Compose Production Graph:" in res.stdout
    assert "[OPT] Live Gateway Probe:" in res.stdout
    assert "Scope Assurance Boundary:" in res.stdout
    assert "It does NOT constitute physical 5-node hardware acceptance or bare-metal container cluster deployment." in res.stdout
    assert "ZERO Errors (All Exit Codes 0)!" not in res.stdout

