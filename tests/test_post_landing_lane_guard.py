# -*- coding: utf-8 -*-
"""Executable regressions for tools/post_landing_lane_guard.sh (#320 r2).

The runbook's gates used to be prose plus an ``echo``: a case pattern that only looked at eight
characters of ``$LAND``, a printed run state nobody asserted, and a comment where the wait for
the two AC-11 producers should have been.  Each test below drives the guard with a **fake gh**
on PATH and pins one refusal, so an edit that turns a gate back into an echo fails here instead
of during a landing.

The fake gh records every invocation, which is how the ordering tests can state the thing that
matters: when a producer is still running, failed, or ran at another head, ``ac11-aggregate.yml``
is dispatched **zero** times.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "post_landing_lane_guard.sh"
LAND = "a" * 40
OTHER = "b" * 40

def _real_bash() -> str | None:
    """A bash that is really bash.

    Measured on this PC: the first ``bash`` on PATH is a BusyBox applet, which runs a script but
    is not the shell the runbook's blocks are written for (``[[ =~ ]]``, ``local``).  A candidate
    is accepted only when it reports a ``$BASH_VERSION``; BusyBox prints nothing.

    The candidate paths use forward slashes on purpose: the Windows path written with backslashes
    in a non-raw string turned backslash-b into a backspace character, so this helper found
    nothing and every test skipped silently (#320 r2 F1 -- and the sentence describing it carried
    the same byte until r3).  Windows accepts forward slashes, so there is nothing to escape, and
    ``test_this_file_carries_no_stray_control_bytes`` keeps it that way.
    """

    seen = []
    for candidate in (
        os.environ.get("GUARD_TEST_BASH"),
        shutil.which("bash"),
        "C:/Program Files/Git/bin/bash.exe",
        "C:/Program Files/Git/usr/bin/bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ):
        if not candidate or candidate in seen:
            continue
        seen.append(candidate)
        try:
            probe = subprocess.run(
                [candidate, "-c", "echo $BASH_VERSION"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0 and probe.stdout.strip():
            return candidate
    return None


BASH = _real_bash()


def test_this_file_carries_no_stray_control_bytes():
    """A path written with ``\b`` in a non-raw string is a backspace, and it hides in review.

    That is exactly how the Windows bash candidate became an unreachable path (#320 r2 F1), and
    the sentence explaining it carried the same byte afterwards.  Only tab, newline and carriage
    return are text here; anything else is a mistake no diff shows.
    """

    for path in (
        Path(__file__),
        ROOT / "tools" / "post_landing_lane_guard.sh",
        ROOT / "tools" / "post_landing_select_run.py",
    ):
        raw = path.read_bytes()
        stray = sorted({byte for byte in raw if byte < 32 and byte not in (9, 10, 13)})
        assert stray == [], f"{path.name} carries control bytes {stray}"


def test_a_real_bash_is_available_to_run_these_gates():
    """No bash is a failure, not a skip: a silent skip is how F1 survived a review round.

    The gates are shell functions, so a run that cannot find bash has measured nothing -- and
    saying so out loud is the only way a green run means what it looks like.  Point
    ``GUARD_TEST_BASH`` at one if it lives somewhere unusual.
    """

    assert BASH is not None, (
        "no real bash found (tried GUARD_TEST_BASH, PATH, Git for Windows, /bin, /usr/bin); "
        "the post-landing gate tests cannot run without one"
    )


FAKE_GH = """#!/usr/bin/env bash
# Log every call, then answer it from $GUARD_FAKE_STATE.
printf '%s\\n' "$*" >> "$GUARD_FAKE_LOG"
exec python "$GUARD_FAKE_PY" "$@"
"""

FAKE_GH_PY = '''# -*- coding: utf-8 -*-
"""A gh that answers only the four calls the guard makes, from a JSON state file."""
import json
import os
import sys

state = json.load(open(os.environ["GUARD_FAKE_STATE"], encoding="utf-8"))
argv = sys.argv[1:]


def flag(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


if argv[:2] == ["run", "list"]:
    print(json.dumps(state.get("runs", {}).get(flag("--workflow"), [])))
elif argv[:2] == ["run", "watch"]:
    sys.exit(int(state.get("watch", {}).get(argv[2], 0)))
elif argv[:2] == ["run", "view"]:
    row = state["view"][argv[2]]
    print("\\t".join([row["status"], row["conclusion"], row["headSha"]]))
elif argv[:2] == ["workflow", "run"]:
    sys.exit(int(state.get("dispatch", {}).get(argv[2], 0)))
else:
    sys.stderr.write("fake gh: unexpected %s\\n" % " ".join(argv))
    sys.exit(90)
'''

FAKE_AC11_ORCHESTRATOR = '''# -*- coding: utf-8 -*-
import json
import os
import pathlib
import sys

args = sys.argv[1:]
pathlib.Path(os.environ["GUARD_AC11_LOG"]).write_text(
    json.dumps(args), encoding="utf-8"
)
if os.environ.get("GUARD_AC11_EXIT"):
    raise SystemExit(int(os.environ["GUARD_AC11_EXIT"]))
output = pathlib.Path(args[args.index("--output") + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text('{"schemaVersion":"fake-ac11-receipt:1"}\\n', encoding="utf-8")
print(output.read_text(encoding="utf-8"), end="")
'''


def run_guard(
    tmp_path: Path,
    script: str,
    state: dict,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a snippet with the guard sourced and a fake gh first on PATH."""

    if BASH is None:  # the test above already failed; do not add two dozen more
        pytest.skip("no real bash; see test_a_real_bash_is_available_to_run_these_gates")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    fake_py = tmp_path / "fake_gh.py"
    fake_py.write_text(FAKE_GH_PY, encoding="utf-8", newline="\n")
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    log = tmp_path / "gh.log"
    log.write_text("", encoding="utf-8")
    body = tmp_path / "body.sh"
    body.write_text(
        "set -uo pipefail\n"
        f'source "{GUARD.as_posix()}"\n'
        f"{script}\n",
        encoding="utf-8",
        newline="\n",
    )
    environment = dict(os.environ)
    environment.update(
        PATH=str(bin_dir) + os.pathsep + environment["PATH"],
        GUARD_FAKE_STATE=str(state_file),
        GUARD_FAKE_PY=str(fake_py),
        GUARD_FAKE_LOG=str(log),
        GUARD_LIST_ATTEMPTS="1",
        GUARD_LIST_SLEEP="0",
        GUARD_DISPATCH_REF="integration/all-agents-unified",
    )
    if extra_env:
        environment.update(extra_env)
    # ``as_posix`` because Git Bash on Windows would eat the backslashes of a native path.
    result = subprocess.run(
        [BASH, body.as_posix()], capture_output=True, text=True, env=environment, timeout=120
    )
    result.log = log.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    return result


def listed(workflow: str, *, run_id: int = 11, sha: str = LAND, event: str = "workflow_dispatch",
           title: str | None = None, extra: list[dict] | None = None) -> dict:
    rows = [{"databaseId": run_id, "headSha": sha, "event": event,
             "displayTitle": title or f"post-landing-{workflow}-{LAND}"}]
    rows.extend(extra or [])
    return {workflow: rows}


# ---------------------------------------------------------------- F1: the SHA is 40 characters


@pytest.mark.parametrize(
    "value",
    ["deadbeef", "deadbeefZZ", "a" * 39, "a" * 41, "A" * 40, "g" * 40, "", "a" * 40 + "x"],
)
def test_a_value_that_is_not_an_exact_40_hex_sha_is_refused(tmp_path, value):
    """#320 r2 F1: the old ``case`` pattern accepted all of these.

    It was eight ``[0-9a-f]`` followed by ``*``, so an eight-character prefix, a prefix with
    junk after it, and anything longer than 40 characters all passed as a landing SHA -- and
    every later command was bound to that value.
    """

    result = run_guard(tmp_path, f'require_sha LAND "{value}"', {})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "not a 40-character lowercase Git SHA" in result.stderr


def test_a_refused_value_is_never_printed_back(tmp_path):
    """A mis-paste must not become a logged secret (#320 r2 F2).

    The value an operator pastes here may be a token rather than a SHA, so the refusal says the
    length and the failing property and stops.  Each candidate below is a distinct string that
    must not appear anywhere in the output.
    """

    for secret in ("ghp_averyrealtokenvalue12345678901234567890", "Deadbeef" * 5, "not-a-sha"):
        result = run_guard(tmp_path, f'require_sha LAND "{secret}"', {})
        assert result.returncode == 2
        assert secret not in result.stderr + result.stdout
        assert "the value is not printed" in result.stderr
        assert f"length {len(secret)}" in result.stderr or "upper-case" in result.stderr             or "outside 0-9a-f" in result.stderr


def test_the_landing_sha_itself_is_accepted(tmp_path):
    assert run_guard(tmp_path, f'require_sha LAND "{LAND}"', {}).returncode == 0


# ---------------------------------------------------------------- F2: the run is asserted


def test_exactly_one_matching_run_is_required(tmp_path):
    """Two runs sharing a correlation id is a refusal, not a ``[0]`` pick.

    The runbook retried the same deterministic correlation id, so a second dispatch could leave
    two candidates and the old command would silently record one of them.
    """

    workflow = "s12-acceptance-evidence.yml"
    title = f"post-landing-vfcl-{LAND}"
    twin = {"databaseId": 12, "headSha": LAND, "event": "workflow_dispatch",
            "displayTitle": title}
    state = {"runs": listed(workflow, run_id=11, title=title, extra=[twin])}
    result = run_guard(
        tmp_path, f'select_unique_run {workflow} "{LAND}" workflow_dispatch "{title}"', state
    )
    assert result.returncode == 3
    assert "found 2" in result.stderr


def test_no_matching_run_is_refused(tmp_path):
    workflow = "s12-acceptance-evidence.yml"
    result = run_guard(
        tmp_path,
        f'select_unique_run {workflow} "{LAND}" workflow_dispatch "post-landing-vfcl-{LAND}"',
        {"runs": {workflow: []}},
    )
    assert result.returncode == 3 and "found 0" in result.stderr


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ({"event": "pull_request"}, "event"),
        ({"sha": OTHER}, "head"),
    ],
)
def test_a_run_of_another_event_or_head_does_not_match(tmp_path, row, reason):
    """A PR-triggered run or a run at another head is not this record's basis.

    The attestation job only gets its signing token on ``workflow_dispatch``, and a run at
    another head says nothing about the landed tree -- the old block printed both and continued.
    """

    workflow = "s12-acceptance-evidence.yml"
    title = f"post-landing-vfcl-{LAND}"
    state = {"runs": listed(workflow, title=title, **row)}
    result = run_guard(
        tmp_path, f'select_unique_run {workflow} "{LAND}" workflow_dispatch "{title}"', state
    )
    assert result.returncode == 3, reason


@pytest.mark.parametrize(
    ("state", "message"),
    [
        ({"watch": {"11": 1}, "view": {"11": {"status": "completed", "conclusion": "failure",
                                              "headSha": LAND}}},
         "did not finish successfully"),
        ({"watch": {"11": 0}, "view": {"11": {"status": "in_progress", "conclusion": "",
                                             "headSha": LAND}}},
         "required completed/success"),
        ({"watch": {"11": 0}, "view": {"11": {"status": "completed", "conclusion": "success",
                                             "headSha": OTHER}}},
         "required completed/success"),
    ],
)
def test_await_run_refuses_a_failed_unfinished_or_misplaced_run(tmp_path, state, message):
    """``gh run watch --exit-status`` is the wait and the re-read is the gate.

    A watch that returns 0 still has to be about the right commit, and a run that is not
    finished may not be recorded as one that was (#320 r2 F2).
    """

    result = run_guard(tmp_path, f'await_run 11 "{LAND}"', state)
    assert result.returncode == 4
    assert message in result.stderr


def test_await_run_accepts_a_successful_run_at_that_head(tmp_path):
    state = {"watch": {"11": 0},
             "view": {"11": {"status": "completed", "conclusion": "success", "headSha": LAND}}}
    assert run_guard(tmp_path, f'await_run 11 "{LAND}"', state).returncode == 0


# ------------------------------------------------------- F3: one canonical AC-11 orchestrator


def ac11_environment(tmp_path: Path, *, exit_code: int | None = None) -> tuple[dict[str, str], Path]:
    orchestrator = tmp_path / "fake_ac11_orchestrator.py"
    orchestrator.write_text(FAKE_AC11_ORCHESTRATOR, encoding="utf-8", newline="\n")
    log = tmp_path / "ac11-orchestrator.json"
    environment = {
        "GUARD_AC11_PYTHON": sys.executable.replace("\\", "/"),
        "GUARD_AC11_ORCHESTRATOR": orchestrator.as_posix(),
        "GUARD_AC11_LOG": log.as_posix(),
        "GUARD_REPOSITORY": "egparadise/SaintVision-Invion",
    }
    if exit_code is not None:
        environment["GUARD_AC11_EXIT"] = str(exit_code)
    return environment, log


def test_ac11_guard_delegates_once_to_the_exact_sha_orchestrator(tmp_path: Path) -> None:
    """The shell must not keep a second, incomplete producer list.

    Card 260's Python tool owns the three-producer fake-gh coverage, including migration
    rehearsal, prior failures, duplicate runs, artifact expiry and canonical recomputation.
    This boundary test proves the runbook guard invokes that tool once with the landed SHA,
    branch, repository and durable receipt path, while making no direct ``gh`` call itself.
    """

    environment, log = ac11_environment(tmp_path)
    receipt = tmp_path / "ac11-receipt.json"
    result = run_guard(
        tmp_path,
        f'ac11_dispatch_in_order "{LAND}" "{receipt.as_posix()}"',
        {},
        extra_env=environment,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.log == ""
    assert receipt.is_file()
    assert json.loads(log.read_text(encoding="utf-8")) == [
        "--source-sha", LAND,
        "--ref", "integration/all-agents-unified",
        "--repository", "egparadise/SaintVision-Invion",
        "--output", receipt.as_posix(),
    ]


def test_ac11_orchestrator_refusal_is_preserved_without_legacy_dispatch(tmp_path: Path) -> None:
    environment, _ = ac11_environment(tmp_path, exit_code=2)
    result = run_guard(
        tmp_path,
        f'ac11_dispatch_in_order "{LAND}" "{(tmp_path / "receipt.json").as_posix()}"',
        {},
        extra_env=environment,
    )
    assert result.returncode == 2
    assert result.log == ""


def test_a_prefix_sha_never_reaches_the_ac11_orchestrator(tmp_path: Path) -> None:
    environment, log = ac11_environment(tmp_path)
    result = run_guard(
        tmp_path,
        'ac11_dispatch_in_order "deadbeef"',
        {},
        extra_env=environment,
    )
    assert result.returncode == 2
    assert not log.exists()
    assert result.log == ""
