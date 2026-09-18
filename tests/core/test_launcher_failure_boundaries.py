"""Behavioral launcher failure tests with an isolated native-command shim."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_live_console_docker_start_failure_stops_before_listeners(tmp_path: Path):
    """A real shim failure must be observed; an uncalled shim is an invalid test premise."""
    powershell = shutil.which("powershell.exe")
    csc = shutil.which("csc.exe") or r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if not powershell or not Path(csc).exists():
        pytest.skip("Windows PowerShell and csc.exe are required")

    missing_prerequisites = [
        path for path in (
            ROOT / ".venv" / "Scripts" / "python.exe",
            ROOT / "apps" / "web" / "node_modules" / "vite" / "bin" / "vite.js",
        )
        if not path.is_file()
    ]
    if missing_prerequisites:
        pytest.skip(
            "launcher prerequisites absent; Docker shim injection is not reached: "
            + ", ".join(str(path) for path in missing_prerequisites)
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
