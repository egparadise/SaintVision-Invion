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


def test_live_console_compares_the_state_by_token_not_substring():
    """Codex r1 F2: the previous version pinned the weak Contains implementation in a string."""
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    assert "Test-SvOwnedByState" in text
    assert ".Contains($StatePath)" not in text
    assert "ReplaceForeignStateListener" in text
    # Replacement is opt-in, so the default behaviour cannot silently stop another process.
    assert "[switch]$ReplaceForeignStateListener" in text


def test_live_console_only_requires_docker_for_the_local_database_mode():
    """A remote hardened database has no local container; requiring docker made it fail."""
    text = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    assert "managed-local-docker" in text and "ssh-tunnel-external" in text
    local = text.split("if ($svDatabaseMode -eq 'managed-local-docker') {", 1)[1]
    local = local.split("} elseif ($svDatabaseMode -eq 'ssh-tunnel-external') {", 1)[0]
    external = text.split("} elseif ($svDatabaseMode -eq 'ssh-tunnel-external') {", 1)[1]
    external = external.split("Unknown pilot database mode", 1)[0]

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
    assert "[int]::TryParse([string]$svState.dbPort" in text
    assert "-DatabaseTunnelTarget" in text
    assert "ExitOnForwardFailure=yes" in text and "BatchMode=yes" in text
    # No pilot host, account or port literal may be embedded in the repository.
    # The loopback literal is required by the bind fix; any other address would be a
    # hardcoded pilot host, which must come from an argument instead.
    addresses = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text))
    assert addresses <= {"127.0.0.1"}, addresses
    assert "55448" not in text
    assert "saintvision-invion@" not in text


def test_desktop_shortcut_registrar_owns_its_link_and_embeds_no_tunnel_literal():
    text = (ROOT / "deploy/lan/Register-DesktopShortcut.ps1").read_text(encoding="utf-8")
    startup = (ROOT / "deploy/studio/Register-EnvironmentStartup.ps1").read_text(encoding="utf-8")
    # Same ownership marker pattern as the existing startup registrar.
    helper = (ROOT / "deploy/lan/SvLauncherInput.ps1").read_text(encoding="utf-8")
    assert "SaintVision owned desktop launcher v1; no workload dispatch" in helper
    assert "belongs to another setup; preserved." in helper
    assert "Assert-SvOwnedShortcut" in text
    assert "$svMarker" in startup and "belongs to another setup; preserved." in startup
    assert "GetFolderPath('Desktop')" in text
    assert "-Remove" in text or "[switch]$Remove" in text
    assert not re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text), "an address is embedded"
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

    # Pick a port that is genuinely free right now: a hardcoded one can be in use, and the
    # launcher would then (correctly) report a foreign bind instead of a missing tunnel.
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()
    (state_dir / "private-state.json").write_text(
        json.dumps({
            "databaseMode": "ssh-tunnel-external",
            "container": None,
            "epoch": "epoch-shim",
            "dbPort": free_port,
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


# --- Card 289 r2: behavioural boundaries (Codex r1 F1-F5) ------------------------------


def _powershell() -> str:
    found = shutil.which("powershell.exe")
    if not found:
        pytest.skip("Windows PowerShell is required")
    return found


def _run_powershell(body: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a snippet that dot-sources the shared input helper."""
    script = (
        "$ErrorActionPreference='Stop'; . '"
        + (ROOT / "deploy/lan/SvLauncherInput.ps1").as_posix()
        + "'\n"
        + body
    )
    return subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=timeout,
    )


def test_no_test_source_line_carries_a_control_byte():
    """A shell-escaping slip once wrote U+0008 where \\b was meant, voiding two regexes."""
    for path in (
        Path(__file__),
        ROOT / "deploy/lan/Start-LiveConsole.ps1",
        ROOT / "deploy/lan/Register-DesktopShortcut.ps1",
        ROOT / "deploy/lan/SvLauncherInput.ps1",
    ):
        text = path.read_text(encoding="utf-8")
        offenders = sorted({c for c in text if ord(c) < 32 and c not in "\n\t"})
        assert not offenders, (path.name, [hex(ord(c)) for c in offenders])


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell required")
def test_tunnel_target_grammar_refuses_option_and_whitespace_injection():
    """A single string must not be able to reach ssh.exe as several arguments."""
    accepted = ["operator@192.168.45.143", "op.rator@host.example", "a_b-c@h", "user@10.0.0.1"]
    refused = [
        "operator.example.test -o ProxyCommand=calc.exe",
        "-oProxyCommand=calc@h",
        "user@host -o X=1",
        "us er@host",
        'user@host"',
        "user@999.1.1.1",
        "user@",
        "@host",
        "user@host.",
        "user@-bad.example",
    ]
    body = "\n".join(
        ["$ok=$true"]
        + ["if (-not (Test-SvTunnelTarget '%s')) { $ok=$false; Write-Output 'MISSED-ACCEPT %s' }" % (v, v)
           for v in accepted]
        + ["if (Test-SvTunnelTarget '%s') { $ok=$false; Write-Output 'MISSED-REFUSE %s' }" % (v.replace("'", "''"), v.replace("'", "''"))
           for v in refused]
        + ["if ($ok) { Write-Output 'GRAMMAR-OK' }"]
    )
    result = _run_powershell(body)
    combined = result.stdout + result.stderr
    assert "GRAMMAR-OK" in combined, combined


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell required")
def test_argv_tokenizer_refuses_a_prefix_state_path():
    """'C:/pilot/r2' must not be satisfied by a process running 'C:/pilot/r2-x'."""
    body = "\n".join([
        "$script='C:/repo/tools/lan_console.py'",
        "$prefix='py.exe -u C:/repo/tools/lan_console.py --state C:/pilot/r2-x'",
        "$exact='py.exe -u C:/repo/tools/lan_console.py --state C:/pilot/r2'",
        "$spaced='py.exe -u \"C:/repo/tools/lan_console.py\" --state \"C:/my pilot/r2\"'",
        "if (Test-SvOwnedByState -CommandLine $prefix -ScriptPath $script -StatePath 'C:/pilot/r2') { Write-Output 'PREFIX-ACCEPTED' }",
        "if (-not (Test-SvOwnedByState -CommandLine $exact -ScriptPath $script -StatePath 'C:/pilot/r2')) { Write-Output 'EXACT-REFUSED' }",
        "if (-not (Test-SvOwnedByState -CommandLine $spaced -ScriptPath $script -StatePath 'C:/my pilot/r2')) { Write-Output 'SPACED-REFUSED' }",
        "Write-Output 'TOKENIZER-DONE'",
    ])
    result = _run_powershell(body)
    combined = result.stdout + result.stderr
    assert "TOKENIZER-DONE" in combined, combined
    assert "PREFIX-ACCEPTED" not in combined, combined
    assert "EXACT-REFUSED" not in combined, combined
    assert "SPACED-REFUSED" not in combined, combined


def _external_state(state_dir: Path, port: int, mode="ssh-tunnel-external") -> None:
    payload = {"container": None, "epoch": "epoch-shim", "dbPort": port}
    if mode is not Ellipsis:
        payload["databaseMode"] = mode
    (state_dir / "private-state.json").write_text(json.dumps(payload), encoding="utf-8")


def _docker_shim(tmp_path: Path) -> tuple[Path, Path]:
    """A docker.exe that records every call, so 'never consulted' is observable."""
    csc = shutil.which("csc.exe") or r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    if not Path(csc).exists():
        pytest.skip("csc.exe is required")
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir(exist_ok=True)
    marker = tmp_path / "docker-calls.log"
    source = shim_dir / "docker-shim.cs"
    source.write_text(
        "using System;\nusing System.IO;\nclass DockerShim {\n"
        "  static int Main(string[] args) {\n"
        "    File.AppendAllText(Environment.GetEnvironmentVariable(\"SV_SHIM_MARKER\"),\n"
        "                       String.Join(\" \", args) + \"\\n\");\n"
        "    return 0;\n  }\n}\n",
        encoding="utf-8",
    )
    built = subprocess.run(
        [csc, "/nologo", "/target:exe", f"/out:{shim_dir / 'docker.exe'}", str(source)],
        capture_output=True, text=True, errors="replace", timeout=60,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return shim_dir, marker


def _launch(state_dir: Path, shim_dir: Path, marker: Path, *extra: str):
    env = os.environ.copy()
    env["PATH"] = f"{shim_dir};{env['PATH']}"
    env["SV_SHIM_MARKER"] = str(marker)
    return subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "deploy/lan/Start-LiveConsole.ps1"), "-StatePath", str(state_dir), *extra],
        cwd=ROOT, env=env, capture_output=True, text=True, errors="replace", timeout=180,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_external_state_refuses_a_non_loopback_listener_on_the_database_port(tmp_path: Path):
    """Any listener is not a tunnel: a 0.0.0.0 bind must not satisfy the forward."""
    if _launcher_prerequisites():
        pytest.skip("launcher prerequisites absent: " + ", ".join(_launcher_prerequisites()))
    import socket

    shim_dir, marker = _docker_shim(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("0.0.0.0", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        _external_state(state_dir, port)
        result = _launch(state_dir, shim_dir, marker)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, combined
        assert "non-loopback" in combined, combined
        assert not (state_dir / "live-console-processes.json").exists()
        calls = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
        assert calls == [], calls
    finally:
        listener.close()


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_external_state_refuses_a_loopback_listener_it_cannot_identify(tmp_path: Path):
    """A loopback listener owned by something other than the ssh client is not the tunnel."""
    if _launcher_prerequisites():
        pytest.skip("launcher prerequisites absent: " + ", ".join(_launcher_prerequisites()))
    import socket

    shim_dir, marker = _docker_shim(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        _external_state(state_dir, port)
        result = _launch(state_dir, shim_dir, marker)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, combined
        assert "cannot identify" in combined, combined
        assert not (state_dir / "live-console-processes.json").exists()
        assert (marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []) == []
    finally:
        listener.close()


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
@pytest.mark.parametrize("mode", [None, "", "managed-local", 0])
def test_a_declared_but_invalid_database_mode_fails_closed(tmp_path: Path, mode):
    """lan_pilot.py only defaults a genuinely absent key; a present wrong value is refused."""
    if _launcher_prerequisites():
        pytest.skip("launcher prerequisites absent: " + ", ".join(_launcher_prerequisites()))
    shim_dir, marker = _docker_shim(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _external_state(state_dir, 59371, mode=mode)
    result = _launch(state_dir, shim_dir, marker)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "Database mode differs" in combined, combined
    assert not (state_dir / "live-console-processes.json").exists()
    calls = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
    assert calls == [], f"docker was consulted for an invalid database mode: {calls}"


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell and csc.exe shim require Windows")
def test_an_invalid_tunnel_target_is_refused_before_anything_starts(tmp_path: Path):
    if _launcher_prerequisites():
        pytest.skip("launcher prerequisites absent: " + ", ".join(_launcher_prerequisites()))
    shim_dir, marker = _docker_shim(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    _external_state(state_dir, 59372)
    result = _launch(
        state_dir, shim_dir, marker,
        "-DatabaseTunnelTarget", "operator.example.test -o ProxyCommand=calc.exe",
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "exactly user@host" in combined, combined
    assert not (state_dir / "live-console-processes.json").exists()
    assert (marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []) == []


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell required")
def test_desktop_registrar_preserves_a_shortcut_owned_by_another_setup(tmp_path: Path):
    """Codex r1 F5: the ownership invariant was described in source but never executed."""
    link = (tmp_path / "SaintVision Invion.lnk").as_posix().replace("/", "\\")
    body = "\n".join([
        "$link = '" + link + "'",
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($link)",
        "$s.TargetPath='C:\\Windows\\System32\\cmd.exe'",
        "$s.Description='someone else owns this'",
        "$s.Save()",
        "try { $null = Assert-SvOwnedShortcut -LinkPath $link; Write-Output 'FOREIGN-ACCEPTED' }",
        "catch { Write-Output ('REFUSED: ' + $_.Exception.Message) }",
        "$own=(New-Object -ComObject WScript.Shell).CreateShortcut($link)",
        "$own.TargetPath='C:\\Windows\\System32\\cmd.exe'",
        "$own.Description=(Get-SvShortcutMarker)",
        "$own.Save()",
        "try { $null = Assert-SvOwnedShortcut -LinkPath $link; Write-Output 'OWN-ACCEPTED' }",
        "catch { Write-Output ('OWN-REFUSED: ' + $_.Exception.Message) }",
        "try { $null = Assert-SvOwnedShortcut -LinkPath ($link + '.absent'); Write-Output 'ABSENT-ACCEPTED' }",
        "catch { Write-Output 'ABSENT-REFUSED' }",
    ])
    result = _run_powershell(body)
    combined = result.stdout + result.stderr
    assert "FOREIGN-ACCEPTED" not in combined, combined
    assert "belongs to another setup; preserved." in combined, combined
    assert "OWN-ACCEPTED" in combined, combined
    assert "ABSENT-ACCEPTED" in combined, combined
    # The registrar must route through that rule rather than carrying its own copy.
    registrar = (ROOT / "deploy/lan/Register-DesktopShortcut.ps1").read_text(encoding="utf-8")
    assert "Assert-SvOwnedShortcut" in registrar
@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell required")
def test_ssh_key_path_refuses_option_syntax_before_resolving_it(tmp_path: Path):
    """Codex r1 F1 covers SshKeyPath as well, and only the tunnel target had a test.

    The dash rule is driven against a file that really exists under a leading-dash name:
    with the rule removed the value resolves and is accepted, so this is a true witness.
    The quote and control-character rule cannot be witnessed the same way because Windows
    filenames cannot contain those bytes at all -- those cases are refused here by the
    grammar rule and by the resolve step together, and they guard the shortcut Arguments
    string the registrar builds rather than the filesystem.
    """
    (tmp_path / "id_ed25519").write_text("not-a-key", encoding="utf-8")
    (tmp_path / "-oProxyCommand=calc.exe").write_text("not-a-key", encoding="utf-8")
    (tmp_path / "keys").mkdir()
    body = "\n".join([
        "Set-Location -LiteralPath '" + tmp_path.as_posix() + "'",
        "function Invoke-SvKeyProbe($label, $value) {",
        "  try { $null = Assert-SvKeyPath $value; Write-Output ('ACCEPTED ' + $label) }",
        "  catch { Write-Output ('REFUSED ' + $label) }",
        "}",
        "Invoke-SvKeyProbe 'real' 'id_ed25519'",
        "Invoke-SvKeyProbe 'dash' '-oProxyCommand=calc.exe'",
        "Invoke-SvKeyProbe 'quote' ('id' + [char]34 + '_ed25519')",
        "Invoke-SvKeyProbe 'newline' ('id_ed25519' + [char]10 + 'X')",
        "Invoke-SvKeyProbe 'directory' 'keys'",
        "Invoke-SvKeyProbe 'absent' 'id_absent'",
        "Invoke-SvKeyProbe 'empty' ''",
    ])
    result = _run_powershell(body)
    combined = result.stdout + result.stderr
    assert "ACCEPTED real" in combined, combined
    for label in ("dash", "quote", "newline", "directory", "absent", "empty"):
        assert "REFUSED " + label in combined, combined
        assert "ACCEPTED " + label not in combined, combined
    # Both entry points must route through that one rule, not carry their own copy.
    for name in ("Start-LiveConsole.ps1", "Register-DesktopShortcut.ps1"):
        assert "Assert-SvKeyPath" in (ROOT / "deploy/lan" / name).read_text(encoding="utf-8")
