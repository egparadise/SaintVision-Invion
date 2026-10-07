"""Behavioral launcher failure tests with an isolated native-command shim."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _launcher_prerequisites() -> list[str]:
    """Resolve the prerequisites the way Start-LiveConsole.ps1 does.

    The script takes its interpreter from the repository that owns this checkout
    (``git rev-parse --git-common-dir``), not from the checkout itself, so a guard that
    looked under the worktree skipped these tests in every worktree.
    """
    common = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, errors="replace", timeout=30,
    )
    if common.returncode != 0:
        return ["git workspace unavailable"]
    git_dir = Path(common.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    repository = git_dir.resolve().parent
    return [
        str(path)
        for path in (
            repository / ".venv" / "Scripts" / "python.exe",
            ROOT / "apps" / "web" / "node_modules" / "vite" / "bin" / "vite.js",
        )
        if not path.is_file()
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_live_console_docker_start_failure_stops_before_listeners(tmp_path: Path):
    """A real shim failure must be observed; an uncalled shim is an invalid test premise."""
    powershell = shutil.which("powershell.exe")
    csc = shutil.which("csc.exe") or r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if not powershell or not Path(csc).exists():
        pytest.skip("Windows PowerShell and csc.exe are required")

    missing_prerequisites = _launcher_prerequisites()
    if missing_prerequisites:
        pytest.skip(
            "launcher prerequisites absent; Docker shim injection is not reached: "
            + ", ".join(missing_prerequisites)
        )

    shim_dir = tmp_path / "shim"
    state_dir = tmp_path / "state"
    shim_dir.mkdir()
    state_dir.mkdir()
    marker = state_dir / "shim-calls.log"
    shim_source = shim_dir / "docker-shim.cs"
    shim_source.write_text(
        """
using System;
using System.IO;
class DockerShim {
  static int Main(string[] args) {
    var marker = Environment.GetEnvironmentVariable("SV_SHIM_MARKER");
    File.AppendAllText(marker, String.Join(" ", args) + "\\n");
    if (Array.IndexOf(args, "inspect") >= 0) {
      Console.Write("[{\\\"Config\\\":{\\\"Labels\\\":{\\\"ai.saintvision.pilot\\\":\\\"epoch-shim\\\"}},\\\"State\\\":{\\\"Running\\\":false}}]");
      return 0;
    }
    if (Array.IndexOf(args, "start") >= 0) { Console.Error.WriteLine("synthetic start failure"); return 7; }
    return 9;
  }
}
""",
        encoding="utf-8",
    )
    compile = subprocess.run(
        [csc, "/nologo", "/target:exe", f"/out:{shim_dir / 'docker.exe'}", str(shim_source)],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    assert compile.returncode == 0, compile.stdout + compile.stderr

    (state_dir / "private-state.json").write_text(
        json.dumps({"container": "synthetic-pilot", "epoch": "epoch-shim"}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{shim_dir};{env['PATH']}"
    env["SV_SHIM_MARKER"] = str(marker)
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "deploy/lan/Start-LiveConsole.ps1"), "-StatePath", str(state_dir)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )

    calls = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
    if not any("inspect" in call for call in calls):
        pytest.fail("ASSERT-FAIL: docker shim was not invoked; failure injection did not reach the launcher")
    if not any("start" in call for call in calls):
        pytest.fail("ASSERT-FAIL: docker start was not invoked; stopped-state premise was not exercised")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Docker start failed for the owned pilot database" in combined
    assert "No listeners were started" in combined


# --- Card 289: desktop launcher formalization -----------------------------------------

DEPLOY_SCRIPTS = sorted((ROOT / "deploy").rglob("*.ps1"))


def test_no_deploy_script_defaults_to_a_hardcoded_drive_path():
    """The old defaults named C:/Project/SaintVision-Invion, which is not this repository."""
    assert DEPLOY_SCRIPTS, "no PowerShell scripts were discovered under deploy/"
    offenders = {}
    for script in DEPLOY_SCRIPTS:
        text = script.read_text(encoding="utf-8")
        hits = [
            line.strip()
            for line in text.splitlines()
            if "C:/Project" in line or "C:\\Project" in line
        ]
        if hits:
            offenders[script.relative_to(ROOT).as_posix()] = hits
    assert not offenders, offenders


def test_live_console_binds_the_web_listener_to_loopback_only():
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    assert "'--host','127.0.0.1'" in text.replace(" ", "")
    assert "0.0.0.0" not in text


def test_live_console_requires_the_state_before_reusing_a_listener():
    """Reusing a listener that serves another state showed another state's data as this one."""
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    compact = text.replace(" ", "")
    # Both owned listeners pass the resolved state path as a required command-line substring.
    assert "@(\"$svCheckout/tools/lan_console.py\",$StatePath)" in compact
    assert "$svForeign=@($Required|Where-Object{-not$svCommand.Contains($_)})" in compact
    assert "ReplaceForeignStateListener" in text
    # Replacement is opt-in, so the default behaviour cannot silently stop another process.
    assert "[switch]$ReplaceForeignStateListener" in text


def test_live_console_only_requires_docker_for_the_local_database_mode():
    """A remote hardened database has no local container; requiring docker made it fail."""
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    assert "managed-local-docker" in text and "ssh-tunnel-external" in text
    local = text.split("'managed-local-docker'", 1)[1].split("'ssh-tunnel-external'", 1)[0]
    external = text.split("'ssh-tunnel-external'", 1)[1].split("Unknown pilot database mode", 1)[0]

    def code_only(block: str) -> str:
        """A comment may name docker; only an invocation in that branch is the defect."""
        kept = [
            line for line in block.splitlines() if not line.lstrip().startswith("#")
        ]
        return chr(10).join(kept)

    assert "docker.exe" in code_only(local)
    assert "docker" not in code_only(external)
    # An unknown mode must not fall through to starting listeners.
    assert "Unknown pilot database mode" in text


def test_live_console_reads_the_tunnel_port_from_state_and_never_hardcodes_a_target():
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    assert "[int]$svState.dbPort" in text
    assert "-DatabaseTunnelTarget" in text
    assert "ExitOnForwardFailure=yes" in text and "BatchMode=yes" in text
    # No pilot host, account or port literal may be embedded in the repository.
    # The loopback literal is required by the bind fix; any other address would be a
    # hardcoded pilot host, which must come from an argument instead.
    addresses = set(re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", text))
    assert addresses <= {"127.0.0.1"}, addresses
    assert "55448" not in text
    assert "saintvision-invion@" not in text


def test_desktop_shortcut_registrar_owns_its_link_and_embeds_no_tunnel_literal():
    text = (ROOT / "deploy/lan/Register-DesktopShortcut.ps1").read_text(encoding="utf-8")
    startup = (ROOT / "deploy/studio/Register-EnvironmentStartup.ps1").read_text(encoding="utf-8")
    # Same ownership marker pattern as the existing startup registrar.
    assert "$svMarker = 'SaintVision owned desktop launcher v1; no workload dispatch'" in text
    assert "belongs to another setup; preserved." in text
    assert "$svMarker" in startup and "belongs to another setup; preserved." in startup
    assert "GetFolderPath('Desktop')" in text
    assert "-Remove" in text or "[switch]$Remove" in text
    assert not re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", text), "an address is embedded"
    assert "55448" not in text and "saintvision-invion@" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell parser requires Windows")
def test_every_deploy_powershell_script_parses():
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell is required")
    listing = ";".join(
        "'" + script.as_posix().replace("'", "''") + "'" for script in DEPLOY_SCRIPTS
    )
    script = (
        "$bad=@(); foreach ($f in @(" + listing + ")) { $e=$null; "
        "$null=[System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$null,[ref]$e); "
        "if ($e -and $e.Count -gt 0) { $bad += ($f + ': ' + $e[0].Message) } } "
        "if ($bad.Count -gt 0) { $bad -join \"`n\"; exit 1 } else { 'ALL-PARSE-OK' }"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, errors="replace", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL-PARSE-OK" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_external_database_state_never_invokes_docker_and_fails_closed(tmp_path: Path):
    """The remote hardened state must assure a tunnel, not inspect a container that cannot exist."""
    powershell = shutil.which("powershell.exe")
    csc = shutil.which("csc.exe") or r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if not powershell or not Path(csc).exists():
        pytest.skip("Windows PowerShell and csc.exe are required")
    missing = _launcher_prerequisites()
    if missing:
        pytest.skip("launcher prerequisites absent: " + ", ".join(missing))

    shim_dir = tmp_path / "shim"
    state_dir = tmp_path / "state"
    shim_dir.mkdir()
    state_dir.mkdir()
    marker = state_dir / "shim-calls.log"
    source = shim_dir / "docker-shim.cs"
    source.write_text(
        """
using System;
using System.IO;
class DockerShim {
  static int Main(string[] args) {
    File.AppendAllText(Environment.GetEnvironmentVariable("SV_SHIM_MARKER"),
                       String.Join(" ", args) + "\\n");
    return 0;
  }
}
""",
        encoding="utf-8",
    )
    compile_result = subprocess.run(
        [csc, "/nologo", "/target:exe", f"/out:{shim_dir / 'docker.exe'}", str(source)],
        capture_output=True, text=True, errors="replace", timeout=30,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr

    # A port that is closed on purpose: the tunnel cannot be open, and no target is supplied.
    (state_dir / "private-state.json").write_text(
        json.dumps({
            "databaseMode": "ssh-tunnel-external",
            "container": None,
            "epoch": "epoch-shim",
            "dbPort": 59371,
        }),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{shim_dir};{env['PATH']}"
    env["SV_SHIM_MARKER"] = str(marker)
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "deploy/lan/Start-LiveConsole.ps1"), "-StatePath", str(state_dir)],
        cwd=ROOT, env=env, capture_output=True, text=True, errors="replace", timeout=120,
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "tunnel" in combined and "DatabaseTunnelTarget" in combined
    # The point of the fix: the external mode must not reach Docker at all.
    calls = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
    assert calls == [], f"docker was invoked for an external database state: {calls}"
    assert not (state_dir / "live-console-processes.json").exists()
