"""Static launcher guards for failure paths that cannot run in CI safely."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_live_console_checks_docker_start_before_starting_listeners():
    source = (ROOT / "deploy/lan/Start-LiveConsole.ps1").read_text(encoding="utf-8")
    start = source.index("& docker.exe start $svState.container")
    tail = source[start : start + 300]
    assert "$LASTEXITCODE -ne 0" in tail
    assert "No listeners were started" in tail


def test_agent_shell_marks_noexit_as_interactive_not_a_completion_result():
    source = (ROOT / "deploy/studio/Open-Tool.ps1").read_text(encoding="utf-8")
    assert "'-NoProfile','-NoExit'" in source
    assert "Start-Process -FilePath powershell.exe" in source
    assert "exit code" not in source.lower()
