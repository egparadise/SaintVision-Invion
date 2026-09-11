"""Agent CLIs behind the provider contract.

The machinery is driven with a fake command rather than with Claude Code, Codex
or Gemini. Those must not be a prerequisite for the suite — a test that only
runs on a workstation where four tools happen to be installed and signed in is
a test that stops running, and nobody notices.

The one place the real tools appear is
``test_the_tool_definitions_match_what_the_tools_actually_offer``, which is
skipped when a tool is absent and which exists to catch the thing a fake cannot:
a status command that was renamed upstream, leaving the platform confidently
reporting on an invocation that no longer exists.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

from saintvision.adapters import agents
from saintvision.adapters.cli import CliAdapter, CliTool, LoginState
from saintvision.adapters.contract import (
    AttestationResult,
    CancelOutcome,
    Capability,
    ProviderAdapter,
)


def _fake_cli(tmp_path: pathlib.Path, body: str, name: str = "faketool") -> pathlib.Path:
    """A real executable that behaves exactly as the test needs.

    A real subprocess, not a mock: the properties under test — a closed stdin, a
    bounded read, a terminate that may not land — are properties of process
    handling, and a mock would assert that the code calls the functions the code
    calls.
    """
    script = tmp_path / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = tmp_path / (f"{name}.cmd" if sys.platform == "win32" else name)
    if sys.platform == "win32":
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8"
        )
        launcher.chmod(0o755)
    return launcher


def _tool(**kwargs) -> CliTool:
    defaults = dict(name="faketool", executable="faketool", prompt_args=("-p",))
    defaults.update(kwargs)
    return CliTool(**defaults)


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------


def test_a_cli_adapter_satisfies_the_provider_contract():
    """The point of routing these through the same contract as a hosted model.

    An orchestrator that can drive one should not need to know which it has.
    """
    adapter = CliAdapter(_tool())
    assert isinstance(adapter, ProviderAdapter)
    for member in (
        "probe", "install", "authenticate", "run", "cancel", "collect",
        "redact", "attest",
    ):
        assert callable(getattr(adapter, member)), member


# --------------------------------------------------------------------------
# Install: reported, never performed
# --------------------------------------------------------------------------


def test_install_never_installs_anything(tmp_path, monkeypatch):
    """Fetching software during a Run is an unreviewed change to a machine."""
    monkeypatch.setenv("PATH", str(tmp_path))
    report = CliAdapter(_tool()).install()
    assert not report.ready
    assert "does not install it" in report.instructions
    # And nothing appeared.
    assert list(tmp_path.iterdir()) == []


def test_installed_but_not_on_path_is_a_different_answer(tmp_path, monkeypatch):
    """The case that looks identical to "absent" and needs opposite advice.

    Telling someone to reinstall a tool they already have costs them time and
    does not fix the problem, which is the PATH.
    """
    elsewhere = tmp_path / "Programs" / "faketool.exe"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("binary", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    adapter = CliAdapter(_tool(install_paths=(str(elsewhere),)))
    report = adapter.install()
    assert not report.ready
    assert report.missing == ("faketool on PATH",)
    assert "is not on PATH" in report.instructions
    assert "rather than installing it again" in report.instructions


# --------------------------------------------------------------------------
# Login: observed, free, and honestly unknown when it is
# --------------------------------------------------------------------------


def test_a_json_status_command_is_read_rather_than_guessed(tmp_path, monkeypatch):
    body = '''
        import json, sys
        if sys.argv[1:] == ["auth", "status", "--json"]:
            print(json.dumps({"loggedIn": True, "authMethod": "oauth",
                              "email": "someone@example.com"}))
        else:
            print("0.1.0")
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(
        _tool(login_args=("auth", "status", "--json"), login_json_key="loggedIn")
    )
    state, detail = adapter.login_state()
    assert state == LoginState.LOGGED_IN
    assert detail["method"] == "oauth"
    # The account is somebody's personal data and is not carried further. A
    # status screen needs to know how it is signed in, not whose it is.
    assert "someone@example.com" not in json.dumps(detail)


def test_a_logged_out_tool_says_so(tmp_path, monkeypatch):
    body = '''
        import json, sys
        print(json.dumps({"loggedIn": False}) if sys.argv[1:2] == ["auth"] else "0.1.0")
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(
        _tool(login_args=("auth", "status", "--json"), login_json_key="loggedIn")
    )
    assert adapter.login_state()[0] == LoginState.LOGGED_OUT
    assert not adapter.authenticate().authenticated


def test_a_tool_with_no_free_way_to_ask_is_unknown_not_assumed(tmp_path, monkeypatch):
    """"Unknown" is a real answer and a more useful one than a guess.

    The alternative — send a trivial prompt and see whether it errors — makes a
    billable request every time a status screen refreshes.
    """
    _fake_cli(tmp_path, "print('0.1.0')")
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool(login_args=None, credential_paths=()))
    state, detail = adapter.login_state()
    assert state == LoginState.UNKNOWN
    assert "no free way" in detail["reason"]


def test_a_credential_file_is_reported_as_evidence_not_proof(
    tmp_path, monkeypatch
):
    """A credential file outlives a session revoked on the server."""
    _fake_cli(tmp_path, "print('0.1.0')")
    home = tmp_path / "home"
    (home / ".faketool").mkdir(parents=True)
    (home / ".faketool" / "creds.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(pathlib.Path, "expanduser", lambda self: self)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    import saintvision.adapters.cli as cli_module

    monkeypatch.setattr(cli_module, "_home", lambda: home)
    adapter = CliAdapter(_tool(credential_paths=(".faketool/creds.json",)))
    state, detail = adapter.login_state()
    assert state == LoginState.LOGGED_IN
    assert detail["basis"] == "credential file present"


def test_checking_login_does_not_send_a_prompt(tmp_path, monkeypatch):
    """The whole reason the status path is separate from the run path.

    The fake records every invocation; a login check must never appear with the
    prompt flag.
    """
    log = tmp_path / "calls.log"
    body = f'''
        import sys, pathlib
        pathlib.Path(r"{log}").open("a", encoding="utf-8").write(
            " ".join(sys.argv[1:]) + "\\n")
        print("0.1.0")
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool(login_args=("status",), login_text_marker="ok"))
    adapter.login_state()
    adapter.probe()
    recorded = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "-p" not in recorded


# --------------------------------------------------------------------------
# Running, cancelling, collecting
# --------------------------------------------------------------------------


def test_output_is_collected_and_the_run_completes(tmp_path, monkeypatch):
    body = '''
        import sys
        print("hello " + sys.argv[-1])
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "world"})
    result = adapter.collect(handle)
    assert result.completed
    assert "hello world" in result.content
    assert result.stop_reason == "exit:0"


def test_a_nonzero_exit_is_not_a_completed_run(tmp_path, monkeypatch):
    body = '''
        import sys
        sys.stderr.write("it failed\\n")
        sys.exit(3)
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    result = CliAdapter(_tool()).collect(CliAdapter(_tool()).run({"input": "x"}))
    # A different adapter instance has no handle for it.
    assert result.error_code == "RES-RUN-NOT-FOUND"

    adapter = CliAdapter(_tool())
    result = adapter.collect(adapter.run({"input": "x"}))
    assert not result.completed
    assert result.error_code == "RUN-EXIT-3"


def test_cancelling_reports_unknown_rather_than_stopped(tmp_path, monkeypatch):
    """The judgement that matters most in this module.

    Terminating the process says the process is gone. It says nothing about what
    the agent did before it went — files edited, a commit made, a request the far
    side is still working on and still billing. STOPPED would be a claim about
    the provider's state made from the wrong side of a process boundary, and it
    is the claim that lets an orchestrator retry work that is still running.
    """
    body = '''
        import time
        time.sleep(30)
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "x"})
    assert adapter.cancel(handle) is CancelOutcome.UNKNOWN


def test_cancelling_something_already_finished_is_knowable(tmp_path, monkeypatch):
    """The one case that genuinely is knowable, and is reported distinctly."""
    _fake_cli(tmp_path, "print('done')")
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "x"})
    adapter.collect(handle)
    assert adapter.cancel(handle) is CancelOutcome.ALREADY_FINISHED


def test_a_cancelled_run_is_not_a_successful_empty_one(tmp_path, monkeypatch):
    """The reading that turns a cancellation into a result nobody questions."""
    body = '''
        import time
        time.sleep(30)
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "x"})
    adapter.cancel(handle)
    result = adapter.collect(handle)
    assert not result.completed
    assert result.error_code == "RUN-CANCELLED"
    assert result.stop_reason == "cancelled"


def test_a_secret_in_the_output_is_redacted(tmp_path, monkeypatch):
    """An agent CLI echoes the commands it ran, which is where a token lands."""
    body = '''
        print("running: curl -H 'Authorization: Bearer abc123def456ghi789'")
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    result = adapter.collect(adapter.run({"input": "x"}))
    assert "abc123def456ghi789" not in result.content
    assert result.redacted


def test_output_is_bounded(tmp_path, monkeypatch):
    """A control plane that runs out of memory takes every other run with it."""
    import saintvision.adapters.cli as cli_module

    monkeypatch.setattr(cli_module, "MAX_OUTPUT_BYTES", 256)
    body = '''
        print("x" * 50000)
    '''
    _fake_cli(tmp_path, body)
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "x"})
    result = adapter.collect(handle)
    assert len(result.content) <= 256
    # The truncation is recorded rather than hidden.
    assert adapter.attest(handle).provider_claims["truncatedOutput"]


def test_a_tool_with_no_headless_mode_is_refused_rather_than_guessed(
    tmp_path, monkeypatch
):
    """A guessed invocation opens a window on someone's machine and waits."""
    _fake_cli(tmp_path, "print('0.1.0')")
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool(prompt_args=None))
    with pytest.raises(RuntimeError, match="no non-interactive mode"):
        adapter.run({"input": "x"})


# --------------------------------------------------------------------------
# Attestation
# --------------------------------------------------------------------------


def test_a_local_cli_result_is_unverifiable_and_says_so(tmp_path, monkeypatch):
    """Hashing bytes we received proves they arrived, not that they are genuine.

    Calling that VERIFIED would make the word mean nothing everywhere else it
    appears.
    """
    _fake_cli(tmp_path, "print('out')")
    monkeypatch.setenv("PATH", str(tmp_path))
    adapter = CliAdapter(_tool())
    handle = adapter.run({"input": "x"})
    adapter.collect(handle)
    attestation = adapter.attest(handle)
    assert attestation.result is AttestationResult.UNVERIFIABLE
    # What *is* knowable is attested: which binary, at which path, with which
    # arguments.
    assert attestation.provider_claims["executableSha256"]
    assert attestation.request_sha256


# --------------------------------------------------------------------------
# The real tools, when they are here
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tool", agents.TOOLS, ids=lambda t: t.name)
def test_the_tool_definitions_match_what_the_tools_actually_offer(tool):
    """The thing a fake cannot catch: an upstream rename.

    If ``claude auth status --json`` became ``claude status``, every fake-backed
    test here would still pass and the platform would confidently report on an
    invocation that no longer exists. Skipped when the tool is absent, because
    requiring four signed-in CLIs would make the suite unrunnable in CI.
    """
    if shutil.which(tool.executable) is None:
        pytest.skip(f"{tool.executable} is not installed on this machine")
    adapter = CliAdapter(tool)
    probe = adapter.probe()
    assert probe.reachable, f"{tool.executable} did not answer {tool.version_args}"
    assert probe.api_version, "no version reported"
    if tool.login_args is not None:
        state, _ = adapter.login_state()
        assert state != LoginState.UNKNOWN, (
            f"{' '.join(tool.login_args)} no longer answers the way the "
            f"definition expects; the platform is reporting on an invocation "
            f"that may have been renamed"
        )


def test_every_tool_is_listed_once_and_ordered():
    """A status screen must not reshuffle between refreshes."""
    names = [tool.name for tool in agents.TOOLS]
    assert len(names) == len(set(names))
    assert list(agents.BY_NAME) == names


def test_a_tool_that_raises_does_not_hide_the_others(monkeypatch):
    """Three answers and a problem beat an empty screen."""
    import saintvision.adapters.cli as cli_module

    original = cli_module.CliAdapter.readiness

    def explode(self):
        if self.tool.name == "codex-cli":
            raise OSError("broken")
        return original(self)

    monkeypatch.setattr(cli_module.CliAdapter, "readiness", explode)
    rows = agents.readiness()
    assert len(rows) == len(agents.TOOLS)
    broken = [r for r in rows if r["adapter"] == "codex-cli"][0]
    assert broken["error"] == "OSError"
    assert broken["loginState"] == "unknown"
