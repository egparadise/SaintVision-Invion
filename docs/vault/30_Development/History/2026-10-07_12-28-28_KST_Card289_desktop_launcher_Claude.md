---
doc_id: "HIST-20261007-CARD289-CLAUDE"
title: "Card 289 desktop launcher formalization"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-10-07T12:28:28+09:00"
updated: "2026-10-07T12:28:28+09:00"
source_of_truth: "Git"
---

# Card 289 desktop launcher formalization

## Scope

- Base: train 66 candidate `2146a70b0e588654a99030dfc9cee815147d37ba`
  (`coord/train66a-ci-1216`), which contains both `#384` and `#385`.
- Moved the behaviour of the coordinator's temporary launcher
  (`.work/launcher/Start-SaintVision.ps1`) into `deploy/lan`, and fixed the three defects the
  coordinator measured while building it.
- **No database is reset, no workload is dispatched, and no secret is printed or logged.**
  The private pilot state, passfiles and DSNs were not opened, and no rotation was applied.

## The three defects, and what each fix is

**(a) A remote hardened database could not start at all.** `Start-LiveConsole.ps1` called
`docker.exe inspect $svState.container` unconditionally. A `ssh-tunnel-external` state has
`container: null` by construction (`tools/lan_pilot.py` sets it when external DSN files are
supplied), so the launcher failed before starting anything.

The script now reads `databaseMode` from the state and defaults an older state to
`managed-local-docker` **exactly as `lan_pilot.py` does with `setdefault`**, so the existing
local-mode test keeps its premise. The external branch does not consult Docker at all; it
assures a loopback SSH forward instead and fails closed when it cannot.

**(b) A console for another state was silently reused.** The listener-reuse check compared only
the script path, so a `lan_console.py` already serving a *different* `--state` on 18082 was
accepted. The page then showed another state's data as if it were this one. Reuse now requires
the resolved state path in the owner's command line, and additionally requires a loopback
`LocalAddress` for both owned ports.

A listener that fails those checks is **refused, not replaced**, because replacing it stops a
process someone else may be using. `-ReplaceForeignStateListener` makes that an explicit
operator decision. This is the one place where I did not copy the temporary launcher, which
stopped such a process automatically.

**(c) The web server was published on the LAN.** Vite was started with `--host 0.0.0.0`. It is
now `--host 127.0.0.1`, and a pre-existing non-loopback listener is caught by the
`LocalAddress` check rather than reused.

## Tunnel inputs are not hardcoded

The tunnel **port** is read from the state's own `dbPort` — public metadata that
`lan_pilot.py` derives from the external DSN. The **target host and key** are arguments
(`-DatabaseTunnelTarget`, `-SshKeyPath`), and the registrar passes them through into the
shortcut. No pilot address, account or port literal appears in the repository; a test asserts
that the only IPv4 literal in the launcher is `127.0.0.1`, and that neither file contains the
pilot's port or account.

## Desktop shortcut

`deploy/lan/Register-DesktopShortcut.ps1` follows the ownership pattern already used by
`deploy/studio/Register-EnvironmentStartup.ps1`: a marker description identifies the link this
setup owns, a link with any other description is **preserved** rather than overwritten, paths
and the tunnel target are rejected if they contain a quote or newline, and `-Remove` withdraws
only the owned link.

## Stale default paths

Five deployment scripts defaulted to `C:/Project/SaintVision-Workspaces` and
`C:/Project/SaintVision-Invion/.work/lan-pilot`. The second is not even this repository's name
(`SaintVisionI-Invion`), so the default could not have resolved here. All of them now derive
from the checkout that contains the script, so no deployment script assumes a drive letter. A
test asserts no `deploy/**/*.ps1` contains such a literal.

## Tests, and two harness defects found while adding them

`tests/core/test_launcher_failure_boundaries.py` grows from one test to nine.

**Both behavioural tests had been skipping in every worktree, silently.** The skip guard looked
for `.venv/Scripts/python.exe` under the *worktree*, but `Start-LiveConsole.ps1` resolves its
interpreter from the repository that owns the checkout (`git rev-parse --git-common-dir`).
In this worktree both prerequisites were in fact present. The guard now resolves them the way
the script does, which made the pre-existing Docker-start test execute for the first time here —
and immediately exposed a second harness defect: the PowerShell child emits OS-locale bytes, so
`text=True` without `errors=` failed inside the reader thread and handed back `stdout=None`
(`TypeError: can only concatenate str (not "NoneType") to str`). All six subprocess calls now
pass `errors="replace"`.

With both fixed the file is **9 passed, 0 skipped** on this machine.

Each of the three defects was then reintroduced to confirm a test divides fail from pass:

| mutation | result |
|---|---|
| vite bound to `0.0.0.0` again | `test_live_console_binds_the_web_listener_to_loopback_only` **FAILED** |
| listener reuse stops requiring the state | `test_live_console_requires_the_state_before_reusing_a_listener` **FAILED** |
| `docker inspect` unconditional again | `test_external_database_state_never_invokes_docker_and_fails_closed` **FAILED** |

The third is behavioural: it drives the real script against an `ssh-tunnel-external` state with
a compiled `docker.exe` shim on `PATH` and asserts the shim log is **empty**, that the failure
names the tunnel and the missing argument, and that no process record was written.

A static test parses every `deploy/**/*.ps1` with the PowerShell parser; all eight parse.

## Residual

- The behavioural tests still skip where the launcher prerequisites genuinely are absent; that
  is the harness's own premise, reported as a skip rather than a pass.
- `-OpenBrowser` readiness polling and the SSH forward were not exercised against the live
  r2 pilot: the coordinator measured that path (two Nodes online), and this card did not repeat
  it or touch the private state.
- Windows login auto-start remains `deploy/studio/Register-EnvironmentStartup.ps1`; this card
  adds a desktop icon, not a startup change.
