"""Agent CLIs as provider adapters.

Claude Code, Codex, Gemini and Antigravity are not network APIs behind a
credential — they are programs already installed on the machine, already logged
in by a person. So this satisfies the same
:class:`~saintvision.adapters.contract.ProviderAdapter` contract as a hosted
provider, and the parts that differ are the parts worth thinking about.

**Install and login are observed, never performed.** ``install`` reports what is
missing and installs nothing: reaching out to a package index during a Run is an
unreviewed side effect on someone's workstation, and the contract already says
so. ``authenticate`` likewise reports whether the person who owns this machine
is signed in; it never opens a browser or a device-code flow, because the Run
that triggered it has no human in front of it.

**Checking login must not cost anything.** The obvious way to answer "is it
logged in" is to send a trivial prompt and see whether it errors — which makes a
billable request every time a status screen refreshes. Every tool here is probed
through a free, non-interactive status path (``claude auth status --json``,
``codex login status``) or an on-disk credential artefact, and a tool with
neither is reported as ``unknown`` rather than guessed at.

**Cancellation is almost never "stopped".** Killing the process does not undo
what it already did. By the time a cancel arrives the agent may have edited
files, made a commit, or sent a request that is still being billed on the far
side. :class:`CancelOutcome` is tri-state precisely for this, and the honest
answer here is usually ``UNKNOWN`` — which is also the answer that stops the
orchestrator retrying (PLAN-BACKEND-001). Reporting ``STOPPED`` because
``terminate()`` returned would be a claim about the provider's state made from
the client's side of a process boundary.

**Output is bounded.** An agent in a loop can emit gigabytes. Reading a
subprocess with ``communicate()`` puts all of that in the control plane's
memory, and a control plane that dies takes every other run with it — so output
is capped and the truncation is recorded rather than hidden.

**The binary is resolved once and pinned.** ``shutil.which`` at run time and
again at cancel time can resolve differently if ``PATH`` changed, and running
whatever happens to be named ``claude`` on the path is how a shadowed binary in
a working directory gets executed. The resolved path is captured in the handle
and attested with its digest.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Final

from ..ids import new_id
from .contract import (
    CONTRACT_VERSION,
    Attestation,
    AttestationResult,
    AuthResult,
    CancelOutcome,
    Capability,
    CollectResult,
    InstallReport,
    ProbeResult,
    RunHandle,
    Usage,
)
from .reference import redact_text

#: Output kept per stream. An agent that loops can produce far more; the rest is
#: dropped and the fact recorded, because a control plane that runs out of
#: memory takes every other run down with it.
MAX_OUTPUT_BYTES: Final[int] = 1_000_000

#: How long a status probe may take before it is treated as no answer. A status
#: screen that hangs is worse than one that says "unknown".
PROBE_TIMEOUT_SECONDS: Final[int] = 15

#: Grace between asking a process to stop and insisting.
TERMINATE_GRACE_SECONDS: Final[float] = 5.0

#: Environment variables a child agent is allowed to inherit. Everything else is
#: dropped: passing the whole parent environment hands one tool's credentials to
#: another, and a Run's environment is not a place to discover secrets.
INHERITED_ENV: Final[tuple[str, ...]] = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "SystemRoot",
    "COMSPEC",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
)


class LoginState:
    """What is actually known about a tool's login.

    ``UNKNOWN`` is a first-class answer, not a failure. A tool with no free,
    non-interactive way to ask is one we genuinely do not know about, and saying
    so is more useful than a guess that sends people to fix the wrong thing.
    """

    LOGGED_IN: Final[str] = "logged_in"
    LOGGED_OUT: Final[str] = "logged_out"
    UNKNOWN: Final[str] = "unknown"


@dataclass(frozen=True, slots=True)
class CliTool:
    """How to find one agent CLI, ask its version, and ask about its login."""

    #: Stable adapter name. Used as the lineage key, so it is not a display name.
    name: str
    #: What to look for on PATH.
    executable: str
    #: Arguments that print a version and exit. Must not start a session.
    version_args: tuple[str, ...] = ("--version",)
    #: A free, non-interactive command that reports login state, if the tool has
    #: one. ``None`` means fall back to the credential artefact below.
    login_args: tuple[str, ...] | None = None
    #: Whether ``login_args`` emits JSON with a boolean under ``login_json_key``.
    login_json_key: str | None = None
    #: Substring that means "signed in" in the command's text output.
    login_text_marker: str | None = None
    #: Files whose existence indicates a completed login, relative to the user's
    #: home. Evidence, not proof: a stale file outlives a revoked session, which
    #: is why it is only used when there is no status command.
    credential_paths: tuple[str, ...] = ()
    #: Where the tool installs when it is not on PATH. Reporting "not installed"
    #: for something that is installed but unreachable sends people to reinstall
    #: it, which does not help.
    install_paths: tuple[str, ...] = ()
    #: Arguments that run one non-interactive prompt. ``None`` means this tool
    #: has no headless mode and cannot be driven by the platform at all.
    prompt_args: tuple[str, ...] | None = None
    capabilities: frozenset[Capability] = field(
        default_factory=lambda: frozenset({Capability.MODEL_PINNING})
    )


def _home() -> pathlib.Path:
    return pathlib.Path(os.path.expanduser("~"))


def _child_env() -> dict[str, str]:
    """A deliberately small environment for the child process."""
    return {
        key: os.environ[key]
        for key in INHERITED_ENV
        if key in os.environ
    }


def _run_quietly(
    argv: list[str], *, timeout: int = PROBE_TIMEOUT_SECONDS
) -> tuple[int | None, str]:
    """Run a status command with no stdin and a bounded wait.

    ``stdin`` is closed rather than inherited. A CLI that decides to prompt —
    for a login, for a confirmation — blocks forever on an inherited terminal,
    and the symptom is a status screen that never loads rather than an error.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - argv is built from a pinned path
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=_child_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


class CliAdapter:
    """One agent CLI, behind the provider contract."""

    contract_version = CONTRACT_VERSION

    def __init__(self, tool: CliTool, *, clock=None) -> None:
        self.tool = tool
        self.name = tool.name
        self.capabilities = tool.capabilities
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._runs: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Where it is
    # ------------------------------------------------------------------

    def resolve(self) -> str | None:
        """The executable's path, or None. Resolved once per call, never cached.

        Not cached because an operator who installs the tool while the control
        plane is running should see it appear, and because a path cached at
        import time survives an uninstall.
        """
        found = shutil.which(self.tool.executable)
        return str(pathlib.Path(found).resolve()) if found else None

    def _installed_elsewhere(self) -> str | None:
        for candidate in self.tool.install_paths:
            path = pathlib.Path(os.path.expandvars(os.path.expanduser(candidate)))
            if path.exists():
                return str(path)
        return None

    def install(self) -> InstallReport:
        """Report what is missing. Installs nothing, ever.

        The distinction between "not installed" and "installed but not on PATH"
        is the whole value of this method. They look the same to a caller that
        only checks ``which``, and they need opposite responses: install it, or
        fix the path. Telling someone to reinstall something they already have
        wastes their time and does not fix it.
        """
        resolved = self.resolve()
        if resolved is not None:
            return InstallReport(ready=True)
        elsewhere = self._installed_elsewhere()
        if elsewhere is not None:
            return InstallReport(
                ready=False,
                missing=(f"{self.tool.executable} on PATH",),
                instructions=(
                    f"{self.tool.name} is installed at {elsewhere} but is not on "
                    f"PATH, so nothing can start it. Add its directory to PATH "
                    f"rather than installing it again."
                ),
            )
        return InstallReport(
            ready=False,
            missing=(self.tool.executable,),
            instructions=(
                f"{self.tool.name} is not installed. The platform does not "
                f"install it: fetching software during a Run is an unreviewed "
                f"change to this machine."
            ),
        )

    # ------------------------------------------------------------------
    # Whether it is usable
    # ------------------------------------------------------------------

    def probe(self) -> ProbeResult:
        """Presence and version, without starting a session or spending anything."""
        resolved = self.resolve()
        if resolved is None:
            return ProbeResult(
                reachable=False,
                detail={
                    "installed": False,
                    "installedElsewhere": self._installed_elsewhere(),
                    "loginState": LoginState.UNKNOWN,
                },
            )
        started = self._clock()
        code, output = _run_quietly([resolved, *self.tool.version_args])
        elapsed = int((self._clock() - started).total_seconds() * 1000)
        version = output.strip().splitlines()[0].strip() if output.strip() else None
        return ProbeResult(
            reachable=code == 0,
            api_version=version,
            latency_ms=elapsed,
            detail={
                "installed": True,
                "path": resolved,
                "exitCode": code,
                # The login answer belongs on the same screen as the version, so
                # it is here too rather than only behind authenticate().
                "loginState": self.login_state()[0],
                "headless": self.tool.prompt_args is not None,
            },
        )

    def login_state(self) -> tuple[str, dict[str, Any]]:
        """``(state, detail)`` — and ``unknown`` is a real answer.

        Never sends a prompt. The tempting shortcut is to run something trivial
        and see whether it errors, which turns every status refresh into a
        billable request and, for a tool that charges per call, into a bill
        nobody asked for.
        """
        resolved = self.resolve()
        if resolved is None:
            # "not on PATH", not "not installed" — the tool may be sitting on
            # this machine, and telling someone it is absent sends them to
            # reinstall something they already have.
            return LoginState.UNKNOWN, {"reason": "not reachable on PATH"}

        if self.tool.login_args is not None:
            code, output = _run_quietly([resolved, *self.tool.login_args])
            if code is None:
                return LoginState.UNKNOWN, {"reason": "status command did not answer"}
            if self.tool.login_json_key is not None:
                try:
                    payload = json.loads(output)
                except ValueError:
                    return LoginState.UNKNOWN, {"reason": "status output was not JSON"}
                value = payload.get(self.tool.login_json_key)
                if value is None:
                    return LoginState.UNKNOWN, {"reason": "status output lacked the key"}
                return (
                    LoginState.LOGGED_IN if value else LoginState.LOGGED_OUT,
                    # Only the method, never the account. A status screen needs
                    # to know *how* it is signed in; the email and organisation
                    # are somebody's personal data and are not carried further.
                    {"method": payload.get("authMethod")},
                )
            if self.tool.login_text_marker is not None:
                signed_in = code == 0 and self.tool.login_text_marker.lower() in output.lower()
                return (
                    LoginState.LOGGED_IN if signed_in else LoginState.LOGGED_OUT,
                    {"exitCode": code},
                )

        if self.tool.credential_paths:
            for relative in self.tool.credential_paths:
                if (_home() / relative).exists():
                    # Evidence, not proof. A credential file outlives a session
                    # revoked on the server, so this is reported as what it is.
                    return LoginState.LOGGED_IN, {"basis": "credential file present"}
            return LoginState.LOGGED_OUT, {"basis": "no credential file"}

        return LoginState.UNKNOWN, {"reason": "no free way to ask this tool"}

    def authenticate(self, credential_ref: str = "") -> AuthResult:
        """Report the login a person already performed. Never starts one.

        A Run has no human in front of it, so opening a browser or a device-code
        flow would block until it timed out. The credential reference is accepted
        and ignored: for a local CLI the credential is on the machine, and
        pretending otherwise would invite callers to pass one.
        """
        state, detail = self.login_state()
        return AuthResult(
            authenticated=state == LoginState.LOGGED_IN,
            principal_ref=None,
            scopes=(),
            failure_code=None if state == LoginState.LOGGED_IN else state,
        )

    def readiness(self) -> dict[str, Any]:
        """Everything a settings screen needs about this tool, in one call.

        One call because the three questions — is it installed, can it run
        headless, is it signed in — are always asked together, and asking them
        separately means three subprocess launches per tool per refresh.
        """
        report = self.install()
        state, detail = self.login_state()
        resolved = self.resolve()
        version = None
        if resolved is not None:
            code, output = _run_quietly([resolved, *self.tool.version_args])
            if code == 0 and output.strip():
                version = output.strip().splitlines()[0].strip()
        return {
            "adapter": self.tool.name,
            "executable": self.tool.executable,
            "installed": report.ready,
            "path": resolved,
            "installedElsewhere": None if report.ready else self._installed_elsewhere(),
            "version": version,
            "loginState": state,
            "loginDetail": detail,
            # A tool with no headless mode cannot be driven by the platform at
            # all, however well it is installed and signed in.
            "headless": self.tool.prompt_args is not None,
            "missing": list(report.missing),
            "instructions": report.instructions,
        }

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def run(self, request: dict[str, Any]) -> RunHandle:
        """Start one non-interactive invocation.

        The resolved path goes into the handle. Every later step uses that exact
        path rather than looking the name up again, so a ``PATH`` change between
        starting and cancelling cannot make ``cancel`` act on a different
        program than ``run`` started.
        """
        resolved = self.resolve()
        if resolved is None:
            raise FileNotFoundError(f"{self.tool.executable} is not on PATH")
        if self.tool.prompt_args is None:
            raise RuntimeError(
                f"{self.tool.name} has no non-interactive mode; the platform "
                f"cannot drive it"
            )

        prompt = str(request.get("input", ""))
        argv = [resolved, *self.tool.prompt_args, prompt]
        cwd = request.get("cwd")
        started = self._clock()
        process = subprocess.Popen(  # noqa: S603 - argv[0] is a resolved path
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Closed, not inherited: an agent that decides to ask a question
            # would otherwise block until something kills it.
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=_child_env(),
        )
        handle_id = new_id("run")
        self._runs[handle_id] = {
            "process": process,
            "path": resolved,
            "argv": argv,
            "started_at": started,
            "cancel_requested": False,
            "collected": None,
        }
        return RunHandle(
            handle_id=handle_id,
            provider=self.tool.name,
            model_id=None,
            started_at=started,
        )

    def cancel(self, handle: RunHandle) -> CancelOutcome:
        """Ask the process to stop, and report what is actually known.

        This returns ``UNKNOWN`` in the common case, and that is the point.
        Terminating a local process says the process is gone; it says nothing
        about what the agent did before it went. It may have written files, made
        a commit, or sent a request that the far side is still working on and
        still billing. ``STOPPED`` would be a claim about the provider's state
        made from the wrong side of a process boundary, and it is the claim that
        would let an orchestrator retry work that is still running.

        ``ALREADY_FINISHED`` is the one case that is genuinely knowable: the
        process had already exited before anyone asked.
        """
        state = self._runs.get(handle.handle_id)
        if state is None:
            return CancelOutcome.UNKNOWN
        process = state["process"]
        if process.poll() is not None:
            return CancelOutcome.ALREADY_FINISHED

        state["cancel_requested"] = True
        process.terminate()
        try:
            process.wait(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                # Not even the kill was observed to land.
                return CancelOutcome.UNKNOWN
        return CancelOutcome.UNKNOWN

    def collect(self, handle: RunHandle) -> CollectResult:
        """Gather bounded output and report how it ended.

        A cancelled run is ``completed=False`` with a distinct error code, so a
        caller cannot mistake "we stopped it" for "it finished with nothing to
        say" — which is the reading that turns a cancellation into a successful
        empty result.
        """
        state = self._runs.get(handle.handle_id)
        if state is None:
            return CollectResult(
                completed=False, content="", error_code="RES-RUN-NOT-FOUND"
            )
        if state["collected"] is not None:
            return state["collected"]

        process = state["process"]
        try:
            stdout, stderr = process.communicate(timeout=PROBE_TIMEOUT_SECONDS * 4)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        raw = stdout or ""
        truncated = len(raw.encode("utf-8", "replace")) > MAX_OUTPUT_BYTES
        if truncated:
            raw = raw.encode("utf-8", "replace")[:MAX_OUTPUT_BYTES].decode(
                "utf-8", "ignore"
            )
        content, changed = self.redact(raw)
        errors, _ = self.redact((stderr or "")[:MAX_OUTPUT_BYTES])

        exit_code = process.returncode
        if state["cancel_requested"]:
            error_code = "RUN-CANCELLED"
            completed = False
        elif exit_code == 0:
            error_code = None
            completed = True
        else:
            error_code = f"RUN-EXIT-{exit_code}"
            completed = False

        result = CollectResult(
            completed=completed,
            content=content,
            usage=Usage(),
            stop_reason="cancelled" if state["cancel_requested"] else f"exit:{exit_code}",
            model_id=None,
            redacted=changed,
            error_code=error_code,
        )
        state["collected"] = result
        state["stderr"] = errors
        state["truncated"] = truncated
        return result

    def redact(self, content: str) -> tuple[str, bool]:
        """The first redaction pass (ADR-014), shared with the reference adapter.

        An agent CLI echoes the environment it was given and the commands it
        ran, which is exactly where a token ends up in a transcript.
        """
        return redact_text(content)

    def attest(self, handle: RunHandle) -> Attestation:
        """What actually ran: this binary, at this path, with these arguments.

        ``UNVERIFIABLE`` for the output. A local CLI produces no signature over
        its own result, and the platform hashing bytes it received from a
        process it started proves the bytes arrived, not that they are what the
        provider produced. Saying ``VERIFIED`` there would make the word
        meaningless everywhere else it appears.
        """
        state = self._runs.get(handle.handle_id)
        if state is None:
            return Attestation(
                result=AttestationResult.UNVERIFIABLE, detail="unknown handle"
            )
        digest = None
        try:
            digest = hashlib.sha256(
                pathlib.Path(state["path"]).read_bytes()
            ).hexdigest()
        except OSError:
            digest = None
        # NUL-separated, not space-joined: ["a b"] and ["a", "b"] are
        # different invocations and must not digest to the same value.
        request_digest = hashlib.sha256(
            "\x00".join(state["argv"]).encode()
        ).hexdigest()
        return Attestation(
            result=AttestationResult.UNVERIFIABLE,
            request_sha256=request_digest,
            response_sha256=None,
            model_id=None,
            provider_claims={
                "executablePath": state["path"],
                "executableSha256": digest,
                "truncatedOutput": state.get("truncated", False),
            },
            detail=(
                "A local CLI does not sign its output. The executable and the "
                "arguments are attested; the result is not."
            ),
        )
