"""The four agent CLIs, described rather than guessed at.

Every field below was checked against the tool on a real machine, because the
alternative is a status screen that reports confidently about a command that
does not exist. Where a tool has no free way to answer a question, the entry
says so and the adapter reports ``unknown`` — which is a worse-looking screen
and a more useful one.

What was found, and why each entry looks the way it does:

``claude``
    ``claude auth status --json`` prints ``{"loggedIn": true, "authMethod":
    ...}`` and exits 0. Free, non-interactive, no model call. It also prints the
    signed-in email and organisation, which the adapter deliberately drops —
    a status screen needs to know *how* it is signed in, not whose account it
    is.

``codex``
    ``codex login status`` prints "Logged in using ChatGPT" and exits 0. Text,
    not JSON, so the entry matches on the marker and the exit code together.

``gemini``
    No status subcommand exists. Its ``--help`` offers only interactive mode and
    ``-p/--prompt``, and using a prompt to test the login would make a billable
    call every time a screen refreshed. So login is inferred from
    ``~/.gemini/google_accounts.json``, and the adapter reports that basis
    rather than presenting a file's existence as a verified session.

``antigravity``
    Installed as a desktop application, not a command. On the machine this was
    written against it exists at
    ``%LOCALAPPDATA%/Programs/antigravity/Antigravity.exe`` and is **not on
    PATH** — which is exactly the case that looks identical to "not installed"
    to anything that only checks ``which``, and needs the opposite advice. It
    has no documented headless mode, so ``prompt_args`` is ``None`` and the
    platform reports that it cannot drive it. That is a real limitation stated
    plainly, not a gap to paper over with a guess at an invocation.
"""

from __future__ import annotations

from typing import Final

from .cli import CliAdapter, CliTool
from .contract import Capability

CLAUDE = CliTool(
    name="claude-code",
    executable="claude",
    version_args=("--version",),
    login_args=("auth", "status", "--json"),
    login_json_key="loggedIn",
    credential_paths=(".claude/.credentials.json",),
    prompt_args=("-p",),
    capabilities=frozenset({Capability.MODEL_PINNING, Capability.TOOL_USE}),
)

CODEX = CliTool(
    name="codex-cli",
    executable="codex",
    version_args=("--version",),
    login_args=("login", "status"),
    login_text_marker="logged in",
    prompt_args=("exec",),
    capabilities=frozenset({Capability.TOOL_USE}),
)

GEMINI = CliTool(
    name="gemini-cli",
    executable="gemini",
    version_args=("--version",),
    # No status command exists; the credential artefact is the only free signal.
    login_args=None,
    credential_paths=(".gemini/google_accounts.json",),
    prompt_args=("-p",),
    capabilities=frozenset({Capability.TOOL_USE}),
)

ANTIGRAVITY = CliTool(
    name="antigravity",
    executable="antigravity",
    version_args=("--version",),
    login_args=None,
    credential_paths=(".gemini/antigravity-cli",),
    install_paths=(
        "%LOCALAPPDATA%/Programs/antigravity/Antigravity.exe",
        "~/AppData/Local/Programs/antigravity/Antigravity.exe",
        "/Applications/Antigravity.app",
    ),
    # A desktop application with no documented headless invocation. Left as None
    # rather than guessed at: a wrong guess launches a window on someone's
    # machine and then waits for it forever.
    prompt_args=None,
    capabilities=frozenset(),
)

#: Every tool the platform knows how to ask about, in a stable order so a status
#: screen does not reshuffle between refreshes.
TOOLS: Final[tuple[CliTool, ...]] = (CLAUDE, CODEX, GEMINI, ANTIGRAVITY)

BY_NAME: Final[dict[str, CliTool]] = {tool.name: tool for tool in TOOLS}


def adapter_for(name: str) -> CliAdapter:
    tool = BY_NAME.get(name)
    if tool is None:
        raise KeyError(name)
    return CliAdapter(tool)


def readiness() -> list[dict]:
    """Install and login state for every tool, in one sweep.

    Each tool is asked independently and a failure in one is reported as that
    tool's state rather than raising: a screen that shows nothing because one
    of four tools is broken is less useful than one that shows three answers
    and a problem.
    """
    out = []
    for tool in TOOLS:
        adapter = CliAdapter(tool)
        try:
            out.append(adapter.readiness())
        except Exception as error:  # noqa: BLE001 - one tool must not hide the rest
            out.append(
                {
                    "adapter": tool.name,
                    "executable": tool.executable,
                    "installed": False,
                    "loginState": "unknown",
                    "error": type(error).__name__,
                }
            )
    return out
