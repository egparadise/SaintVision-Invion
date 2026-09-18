"""Regression tests for tools/deploy_intranet.ps1 preflight launcher.

Validates:
1. VB-LAUNCH-01 negative control: native Python cert generator nonzero exit (23) halts immediately
   at Step 1 with exit 1 and never proceeds to Step 2 (Vitest).
2. 0-byte or missing certificate files after generation halt at Step 1 with exit 1.
3. Missing apps/web/dist/index.html halts at Step 3 with exit 1 and never proceeds to Step 4 (Smoke).
4. Prior dist/ output is cleaned before npm run build to guarantee freshness of generated artifacts.
5. Non-empty certificates without TLS handshake verification report 'PRESENT & NON-EMPTY' with
   explicit disclaimer that cryptographic validity & TLS negotiation are unverified.
6. Smoke exit 0 reports 'PROCESS EXITED 0' with disclaimer that browser/physical-node acceptance
   is unverified, without emitting unverified hardcoded check constants (e.g. 202).
7. Missing Docker CLI reports Compose Production Graph SKIPPED honestly.
8. Failed/offline gateway probe reports OFFLINE / NOT RUNNING as an optional dev probe without failing.
9. Overall preflight summary table format and Scope Assurance Boundary.
"""

from __future__ import annotations

import shutil
import subprocess
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

    mock_generator = tools_dir / "generate_tls_cert.py"
    mock_generator.write_text("import sys\nsys.stderr.write('synthetic cert generation failure')\nsys.exit(23)\n", encoding="utf-8")

    step2_marker = tmp_path / "step2_executed.marker"
    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    content_with_marker = orig_content.replace(
        "[2/5] Running Frontend & Protocol Automated Tests",
        f"New-Item -ItemType File -Force '{step2_marker.as_posix()}'; [2/5] Running Frontend & Protocol Automated Tests",
    )

    res = run_ps1_in_dir(content_with_marker, tmp_path)

    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
    assert "TLS certificate generation failed with exit code 23" in res.stdout or "TLS certificate generation failed with exit code 23" in res.stderr
    assert not step2_marker.exists(), "Step 2 executed despite Step 1 native failure!"
    assert "[2/5] Running Frontend & Protocol Automated Tests" not in res.stdout
    assert "Preflight Deployment Pipeline Completed with ZERO Errors" not in res.stdout


def test_cert_generation_empty_file_halts_immediately(tmp_path: Path) -> None:
    """VB-LAUNCH-01 negative control: 0-byte cert or key files must halt at Step 1 with exit 1."""
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

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

    (certs_dir / "saintvision.crt").write_bytes(b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")
    (certs_dir / "saintvision.key").write_bytes(b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")

    step4_marker = tmp_path / "step4_executed.marker"
    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "Write-Host 'mock build pass without dist'; $global:LASTEXITCODE = 0",
    ).replace(
        "[4/5] Running API Contract Smoke Suite",
        f"New-Item -ItemType File -Force '{step4_marker.as_posix()}'; [4/5] Running API Contract Smoke Suite",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 1
    assert "Production build artifact 'apps/web/dist/index.html' does not exist" in res.stdout
    assert not step4_marker.exists(), "Step 4 executed despite missing dist/index.html!"
    assert "[4/5] Running API Contract Smoke Suite" not in res.stdout


def test_build_cleans_prior_dist_for_freshness(tmp_path: Path) -> None:
    """Freshness guarantee: pre-existing dist/ directory is wiped prior to npm run build."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    (certs_dir / "saintvision.crt").write_bytes(b"cert-bytes")
    (certs_dir / "saintvision.key").write_bytes(b"key-bytes")

    stale_file = dist_dir / "stale_from_prior_run.txt"
    stale_file.write_text("old stale artifact", encoding="utf-8")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Mock build script creates index.html but does not recreate stale_from_prior_run.txt
    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
    ).replace(
        "node tools/run_browser_smoke.mjs",
        "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "docker compose -f docker-compose.prod.yml config --quiet",
        "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 0
    assert not stale_file.exists(), "Prior dist/stale file was not wiped before build!"
    assert (dist_dir / "index.html").exists(), "Fresh dist/index.html was not created!"
    assert "FRESH DIST GENERATED (apps/web/dist/index.html rebuilt cleanly" in res.stdout


def test_invalid_nonempty_cert_scope_label(tmp_path: Path) -> None:
    """Honest TLS scope: non-empty certificates report PRESENT & NON-EMPTY without claiming TLS 1.3 verification."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Injected arbitrary non-empty bytes (not cryptographically valid X.509)
    (certs_dir / "saintvision.crt").write_bytes(b"INVALID_NONEMPTY_SYNTHETIC_CERT_BYTES")
    (certs_dir / "saintvision.key").write_bytes(b"INVALID_NONEMPTY_SYNTHETIC_KEY_BYTES")
    (dist_dir / "index.html").write_bytes(b"<!doctype html><html><body>SaintVision</body></html>")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
    ).replace(
        "node tools/run_browser_smoke.mjs",
        "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "docker compose -f docker-compose.prod.yml config --quiet",
        "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 0
    # Must report PRESENT & NON-EMPTY with explicit unverified caveat
    assert "[1/5] TLS Certificate Files:       PRESENT & NON-EMPTY" in res.stdout
    assert "cryptographic validity & TLS negotiation unverified" in res.stdout
    # Must NOT claim verified TLS 1.3
    assert "TLS 1.3 Certificates:        VERIFIED" not in res.stdout


def test_smoke_exit_zero_summary_label_without_hardcoded_count(tmp_path: Path) -> None:
    """Honest smoke scope: child exit 0 reports PROCESS EXITED 0 without hardcoded check count."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    (certs_dir / "saintvision.crt").write_bytes(b"cert")
    (certs_dir / "saintvision.key").write_bytes(b"key")
    (dist_dir / "index.html").write_bytes(b"<html>index</html>")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    stubbed_content = orig_content.replace(
        "npm test -- --run",
        "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "npm run build",
        "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
    ).replace(
        "node tools/run_browser_smoke.mjs",
        "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "docker compose -f docker-compose.prod.yml config --quiet",
        "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 0
    assert "[4/5] API Contract Smoke Suite:    PROCESS EXITED 0 (browser/physical-node acceptance unverified)" in res.stdout
    assert "202 checks passed" not in res.stdout
    assert "E2E Browser Smoke Suite:      VERIFIED" not in res.stdout


def test_docker_absent_summary_label(tmp_path: Path) -> None:
    """Docker CLI absent: reports SKIPPED cleanly without failing preflight or claiming verification."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    (certs_dir / "saintvision.crt").write_bytes(b"cert")
    (certs_dir / "saintvision.key").write_bytes(b"key")
    (dist_dir / "index.html").write_bytes(b"<html>index</html>")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Prepend mock Get-Command that hides docker CLI
    no_docker_content = (
        "function Get-Command { param($Name) if ($Name -eq 'docker') { return $null } else { Microsoft.PowerShell.Core\\Get-Command @PSBoundParameters } }\n"
        + orig_content.replace(
            "npm test -- --run",
            "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
        ).replace(
            "npm run build",
            "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
        ).replace(
            "node tools/run_browser_smoke.mjs",
            "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
        )
    )

    res = run_ps1_in_dir(no_docker_content, tmp_path)

    assert res.returncode == 0
    assert "[5/5] Compose Production Graph:     SKIPPED (Docker CLI not detected on host)" in res.stdout
    assert "SYNTAX & GRAPH VALIDATED" not in res.stdout


def test_gateway_offline_summary_label(tmp_path: Path) -> None:
    """Live Gateway offline: reports OFFLINE / NOT RUNNING as optional probe without failing."""
    tools_dir = tmp_path / "tools"
    certs_dir = tmp_path / "deploy" / "certs"
    dist_dir = tmp_path / "apps" / "web" / "dist"
    certs_dir.mkdir(parents=True, exist_ok=True)
    tools_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    (certs_dir / "saintvision.crt").write_bytes(b"cert")
    (certs_dir / "saintvision.key").write_bytes(b"key")
    (dist_dir / "index.html").write_bytes(b"<html>index</html>")

    orig_content = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # Prepend mock Invoke-WebRequest that throws (simulating offline gateway)
    offline_gw_content = (
        "function Invoke-WebRequest { throw 'Connection refused to 127.0.0.1:8080' }\n"
        + orig_content.replace(
            "npm test -- --run",
            "Write-Host 'mock vitest pass'; $global:LASTEXITCODE = 0",
        ).replace(
            "npm run build",
            "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
        ).replace(
            "node tools/run_browser_smoke.mjs",
            "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
        ).replace(
            "docker compose -f docker-compose.prod.yml config --quiet",
            "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
        )
    )

    res = run_ps1_in_dir(offline_gw_content, tmp_path)

    assert res.returncode == 0
    assert "[OPT] Live Gateway Probe:           OFFLINE / NOT RUNNING (Optional dev probe)" in res.stdout
    assert "Live Control Plane Gateway is HEALTHY" not in res.stdout


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
        "New-Item -ItemType Directory -Force dist | Out-Null; Set-Content -Path dist/index.html -Value '<html>fresh</html>'; $global:LASTEXITCODE = 0",
    ).replace(
        "node tools/run_browser_smoke.mjs",
        "Write-Host 'mock smoke pass'; $global:LASTEXITCODE = 0",
    ).replace(
        "docker compose -f docker-compose.prod.yml config --quiet",
        "Write-Host 'mock docker pass'; $global:LASTEXITCODE = 0",
    )

    res = run_ps1_in_dir(stubbed_content, tmp_path)

    assert res.returncode == 0, f"Unexpected failure: {res.stdout}\n{res.stderr}"
    assert "[1/5] TLS Certificate Files:       PRESENT & NON-EMPTY" in res.stdout
    assert "[2/5] Frontend & Protocol Tests:    VERIFIED" in res.stdout
    assert "[3/5] Production Asset Build:       FRESH DIST GENERATED" in res.stdout
    assert "[4/5] API Contract Smoke Suite:    PROCESS EXITED 0" in res.stdout
    assert "[5/5] Compose Production Graph:" in res.stdout
    assert "[OPT] Live Gateway Probe:" in res.stdout
    assert "Scope Assurance Boundary:" in res.stdout
    assert "Overall: This is a local developer/CI preflight check, NOT physical 5-node hardware acceptance or bare-metal deployment." in res.stdout
    assert "ZERO Errors (All Exit Codes 0)!" not in res.stdout
    assert "202 checks passed" not in res.stdout
