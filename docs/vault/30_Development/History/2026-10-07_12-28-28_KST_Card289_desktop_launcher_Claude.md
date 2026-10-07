---
doc_id: "HIST-20261007-CARD289-CLAUDE"
title: "Card 289 desktop launcher formalization"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-10-07T12:28:28+09:00"
updated: "2026-10-07T13:45:31+09:00"
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


## Reviewer r1 remediation (Codex F1-F6)

Codex asked for six changes on PR #386. Every boundary below is now driven by a test, and each
test was proved to be a witness by reintroducing the defect and watching exactly that test fail.

`deploy/lan/SvLauncherInput.ps1` is new: it holds the input grammar and command-line parsing
that both the launcher and the registrar share, so the two entry points cannot drift and so a
regression test can drive each rule directly instead of only reading the source.

**F1 - operator inputs reach `ssh.exe` as data, not as options.** The previous version only
refused quotes and newlines. A native argument list is flattened by the Windows runtime, so a
single string such as `operator.example.test -o ProxyCommand=calc.exe` could arrive as several
arguments. Both inputs are now held to an anchored grammar rather than filtered: the tunnel
target must match `user@host` exactly, with IPv4 octet range and leading-zero rejection or
per-label hostname validation, and the key path must not begin with `-`, must contain no quote
or control character, and must resolve to an existing file. The ssh invocation fixes every
option before `--`, so a validated target can only ever be read as the destination. The
registrar applies the identical assertions, so a value the launcher would refuse cannot be
baked into an unattended shortcut. Rejected values are never echoed: they carry an account and
a host.

**F2 - ownership is decided by tokens, not by `Contains`.** `C:/pilot/r2` is a substring of
`C:/pilot/r2-x`, so the substring test could accept a console serving a neighbouring state -
the same class of defect this card set out to fix. `Get-SvArgv` implements the documented Win32
CRT tokenizer (whitespace outside quotes separates, a backslash run escapes a following quote,
doubled quotes inside a quoted argument produce one literal quote), and ownership now requires
the normalized path after an exact `--state` token to equal the target state.

**F3 - the external forward is identified, not assumed.** Treating *any* listener on `dbPort`
as the tunnel would point the console at whatever happened to be listening. Reuse now requires
every listener on that port to be bound to a loopback address *and* an owning process that is
`ssh.exe` whose command line carries exactly `-L 127.0.0.1:<dbPort>:127.0.0.1:<dbPort>` and,
when a target was supplied, exactly that target. Anything else fails closed before a listener
starts. The port is parsed with `[int]::TryParse` and range-checked, so a non-numeric `dbPort`
cannot cast to `0` and be forwarded.

**F4 - only a genuinely absent `databaseMode` means legacy local.** `tools/lan_pilot.py` uses
`setdefault`, which substitutes the default only when the key is missing; a present but wrong
value is refused there. The launcher matched that by truthiness, so `null`, an empty string and
`0` all became "legacy local" and then demanded a container an external state does not have.
The mode is now decided by a property-existence check, and a declared value outside the two
contract strings fails closed before any Docker call.

**F5 - each boundary has a witness.** The suite was 1 test before this card and is **21 now**
(21 passed, 0 skipped on this host). Eight mutations, each reverting one boundary:

| Mutation | Test that failed |
|---|---|
| tunnel target grammar always accepts | `test_tunnel_target_grammar_refuses_option_and_whitespace_injection` |
| key path no longer refuses a leading dash | `test_ssh_key_path_refuses_option_syntax_before_resolving_it` |
| state compared as a substring again | `test_argv_tokenizer_refuses_a_prefix_state_path` |
| non-loopback bind accepted as the tunnel | `test_external_state_refuses_a_non_loopback_listener_on_the_database_port` |
| any loopback listener counts as the tunnel | `test_external_state_refuses_a_loopback_listener_it_cannot_identify` |
| falsey `databaseMode` treated as legacy | `test_a_declared_but_invalid_database_mode_fails_closed` `[None]` `[]` `[0]` |
| shortcut ownership rule disabled | `test_desktop_registrar_preserves_a_shortcut_owned_by_another_setup` |
| vite bound to `0.0.0.0` again | `test_live_console_binds_the_web_listener_to_loopback_only` |

Both files were restored from file backups and byte-compared against the pristine copies after
the run, and the suite returned to 21 passed. An earlier mutation run used `git checkout --` to
revert and **destroyed work**: the new helper was untracked so the restore silently failed and
mutations accumulated, and the launcher's index copy was the pre-card original so the checkout
reverted the whole remediation to 152 lines. Mutation harnesses here back up to files.

Two of those tests exist because the first remediation pass was wrong and measurement said so:

- **The key-path rule had no witness.** The first mutation run caught seven of eight; removing
  the leading-dash rule failed nothing, because only the tunnel target had a grammar test. The
  dash case is now driven against a file that really exists under the name
  `-oProxyCommand=calc.exe`, so with the rule removed the value resolves and is **accepted**.
  The quote and control-character rule cannot be witnessed the same way - Windows filenames
  cannot contain those bytes at all - and that limit is written in the test rather than implied.
- **`Get-SvListeners` returning an `@(...)` array silently reintroduced F3.** PowerShell unrolls
  an array on return, so a single listener arrived as a scalar whose `.Count` is null, making
  `Count -gt 0` false and skipping the loopback and ownership loops entirely. The first fix,
  returning a comma-wrapped array, broke the opposite case: the empty result arrived as one
  element holding an empty array, whose `LocalAddress` is null and therefore read as a
  non-loopback bind. The function now emits the objects and **every one of its six call sites
  wraps with `@()`**. A test caught this, not a reading of the source.

The shortcut ownership rule moved out of the registrar into `Assert-SvOwnedShortcut` for the
same reason: the invariant was described in source but never executed. The test writes a link
owned by another setup and asserts it is preserved, then writes one carrying this setup's marker
and asserts it is accepted. An earlier attempt to test this by redirecting the home directory
does not work, because `[Environment]::GetFolderPath('Desktop')` does not read it.

**F6 - the skip map is measured, not guessed.** Collecting the suite and joining each item to
its own `skipif` reason gives `PowerShell and csc.exe shim require Windows` = 9,
`PowerShell parser requires Windows` = 1, `PowerShell required` = 4, and 7 items that always
run. Both `backend.yml` and `core.yml` carry those exact counts.

A self-check test forbids control bytes in this test file and in the three PowerShell files: an
earlier shell-escaping slip wrote four literal U+0008 bytes where an escape was meant, which had
made two IPv4 assertions vacuous.

### Remediation residual

- The live r2 pilot was still not touched: no private state file was opened, and no rotation or
  forward was run against it.
- The character-loop half of the key-path rule is asserted but not mutation-proved, for the
  filesystem reason stated above.
- PR base moved to `coord/train66c-ci-1336` (`5d0c9e6224f2c2d3cd1cd5cc06e6bbdcd5ad58c6`); the branch point is
  unchanged, so this is a merge-target change rather than a rebase.
