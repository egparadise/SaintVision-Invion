---
doc_id: "HISTORY-C304-SUPERVISION-RELIABILITY-20261104"
title: "Card 304 supervised reliability correction"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-04T13:11:38+09:00"
source_of_truth: "Git"
---

# Card 304 reliability correction

Task SUPERVISION-20261104-CODEX, task_4a4eaf27c548 / ctx_78f45e976cf3.
Coordinator follow-up msg_afb2c8ad7c0e explicitly assigned PR402 F1–F3 corrections.
Owner Codex; independent reviewer Claude (new exact-head review pending).
Branch agent/codex/c304-supervision-reliability; base/current observed PR402
**0f8e461da2bee7e25526a89b2c456c534257e720**. Checkout
`D:/Project/SaintVisionI-Invion/supervision-codex-20261104`, clean at start,
KST 2026-11-04 13:11:38. Only task tooling/tests/README and unique History/Evidence
are edited; no shared board, registry, Obsidian, live state or scheduled task change.

Previously read context: AGENTS.md, agent-delivery 1.1.0, core-reliability 1.0.0,
GUIDE-001 1.1.0, ADR-INDEX-001 1.37.0, GOV-AGENT-001 1.1.3, GOV-GIT-001 1.1.4,
GOV-CONTINUOUS-001 1.1.0, GOV-CONTINUITY-001 1.0.0; Git progress 1.0.375,
Codex board 1.0.337, shared Obsidian progress 1.0.376. Scope follows coordinator's
specific follow-up, not the older board's routine next card. Prior independent
review/r4 prerequisite evidence is separate commit
**a8542f04b5c3bcc8de1c7c0c75d1c9525449d455**, branch
`agent/codex/supervision-20261104-review`; it is not this correction's product source.
Audit Docs/Ontology/diff gates exited 0. Isolated Obsidian preflight exited 0,
2086 pending / 0 conflicts / no writes; no shared export is claimed.

## Reproduction and resulting behavior

- **F1:** hosted old-head Backend run **40456817100** tested PR merge
  **db99637795a096350907d2947b96462d31abd8d1**, Python 3.12.15 / 3.14.8.
  Both lanes had **17 failed / 8379 passed / 75 skipped / 2 deselected** (exit 1),
  chiefly canonical Linux executable symlinks rejected by correct regular-file pins.
  Fixtures now pass `Path(sys.executable).resolve()` both to command pins and registrar.
  `_regular` and registrar symlink rejection are preserved. An explicit executable
  symlink witness exercises successful canonical invocation and refusal of the link.
  The registrar also avoids assigning PowerShell's read-only automatic IsWindows
  variable by using a task-specific variable name.
- **F2:** a state-local kernel guard is held across every gate and protects a durable
  exact owner record. Receipt/status failures before any gate remain fail-closed.
  Missing, future-valid or wrong-count leaves and lock contention now write receipts;
  expired alerts are observed even with busy/stale ownership. The task limit is four
  hours rather than one, covering fourteen 900-second gate limits plus overhead.
  Explicit stale-lock maintenance requires the same exclusive kernel guard and exact
  owner metadata digest/schema/state/token, archives the record, and never clears
  uncertain attempts. No wall-clock/PID inference authorizes recovery. Legacy locks
  are preserved for manual ownership disposition.
- **F3:** an atomic state-local attempt latch and initial receipt precede all commands;
  per-gate intent is flushed before each subprocess. A failed/interrupted attempt
  blocks subsequent triggers even with another plan/status path. Completed leaf
  generations are not replayed. Explicit latch reset requires an exact prior digest
  and a separately reviewed, changed, valid CP/all-Node generation outside the window;
  it archives the prior record and runs no gate. Ordinary recovery still requires
  independent review of actual Node/channel/journal/issuer state.

The killed-supervisor test deliberately leaves its child alive while proving that a
new executor refuses kernel contention, requires exact stale-lock recovery, continues
expiry alerts, and then still refuses to replay the uncertain sequence. Test cleanup
terminates only the fixture-owned child. Normal execution, every one of fourteen
failure points, all later-trigger refusals, missing/future/count preflights, reset
digest/freshness bounds, cross-state copied-owner refusal and receipt-storage failure
have behavioral tests. No live certificate or Node is involved.

## Validation and handoff

Runtime is `D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe`, Windows CPython
3.14.7, pytest 9.1.1, cryptography 50.0.1. Direct expanded command:
`python -X utf8 -m pytest tests/test_scheduled_leaf_renewal.py -q --junitxml=.work/supervision-codex-audit/c304-reliability.xml`.
At KST 13:16:07–13:16:30 the intermediate suite exited **0**, **25 passed / 1 skipped**;
the skip is executable-symlink creation unavailable on this Windows runner and must
run on hosted Linux. Additional witnesses were added after that run; final results
and exact code/evidence/CI heads are recorded in the follow-up below.

Next executable action/owner: Codex runs final focused and document gates, commits and
pushes this isolated correction as a fast-forward of the reobserved PR402 head, then
collects exact-head Backend/Core/Docs and supplies Claude's new exact review target
through the coordinator. Coordinator owns integration and the independent Docker
browser harness repair. No operational recovery, schedule install or broad task
completion is implied; original 48-task status remains 2 done / 4 blocked / 42 planned /
0 ready. Shared Obsidian export is deferred to coordinator by explicit task scope.


Final pre-commit combined run, KST 13:19:12 to 13:20:05, Windows runtime above:
`python -X utf8 -m pytest tests/test_scheduled_leaf_renewal.py tests/test_lan_leaf_rotation.py tests/test_lan_leaf_rotation_standalone_runtime.py tests/core/test_lan_pki.py -q --junitxml=.work/supervision-codex-audit/c304-final.xml`
exit **0**, **108 passed / 7 skipped / 0 failed / 0 errors / 0 deselected**.
Seven skips are the new executable-symlink witness and six pre-existing standalone
symlink boundaries unavailable on Windows. Input was base 0f8e461d plus the four
modified tool/test/README paths and this untracked History (explicitly dirty,
not an unchanged-source claim). Docs, ontology and diff gates exited 0.
Isolated Obsidian check: 2075 pending / 0 conflicts, exit 0, no writes.


## Exact code verification and further read-only equipment evidence

Code commit **458c3389e30c6fdedfe8f63623c4a032fa9234fa** was tested directly
with a clean tracked worktree at KST **13:21:22 to 13:21:46** using the same Windows
CPython 3.14.7 runtime. Command `python -X utf8 -m pytest tests/test_scheduled_leaf_renewal.py -q --junitxml=.work/supervision-codex-audit/c304-exact-code.xml`
exited **0**, **27 passed / 1 skipped / 0 failed / 0 errors / 0 deselected**.
The sole executable-symlink capability skip remains assigned to hosted Linux.
JUnit and combined dirty-tree evidence are under
`docs/vault/30_Development/Evidence/c304-supervision-reliability/`; the report-only
follow-up does not change these tested code inputs. Backend/Core/Docs and Claude
review are pending at this report checkpoint; no green CI is inferred from push.

Further read-only audit at KST **13:22**: the remaining known inventory worker's
SSH attempt using the previously documented account/key was refused (SSH **255**,
permission-denied); no key or authorized_keys change was attempted. Local CP Docker
server reports **API 1.41**, exit **0**, still below co-located installer minimum
1.45. Thus the CP slot is an actual measured compatibility blocker, not a missing
topology decision. MinIO's readiness endpoint on its known inventory host returns
**HTTP 200 through pinned TLS with hostname validation** when connected to the known
address; other two bounded candidates timed out. Local hostname resolution is still
missing and no object roundtrip, credential mutation or PITR operation ran. This
updates the earlier audit: the storage service is reachable using already known
data, while fresh attested read/write/cleanup acceptance remains unexecuted.
Protected credentials and host identities remain unprinted and outside Git.


## Independent b1 review corrections N1/N2

Coordinator msg_b46b1f38a68a relayed Claude changes requested on exact b1e59f85.
N1 identified that latching read-only current-status/runtime preflight failures
would disable the remaining 48-hour window after a transient failure. The latch
now begins immediately before the first mutating `prepare`; read-only preflight
failures still write receipts and stop the current attempt, but a later trigger
can safely retry them. All mutating failures/uncertain effects remain latched.
This supersedes the earlier intermediate b1 all-failure latch description above.

N2 identified that successful commands/observations alone did not prove actual
certificate replacement. After finalObserve the executor now rereads CP/all Node
leaves and requires a changed public generation, exact Node count and a valid
earliest expiry outside the renewal window before writing renewed/completed.
The unchanged-generation already-renewed success path was removed. Behavioral
fixtures now really publish a new six-day public generation; unchanged and
changed-but-still-in-window variants fail after mutation and stay latched.

The low-severity cleanup finding is also corrected: a changed/missing lock record
cannot mask the primary gate exception; foreign metadata remains preserved.
New same-plan transient recovery witnesses cover all three read-only preflight
gates without operator reset. Local N1/N2 focused suite exited **0**, **33 passed /
1 skipped** (Windows executable-symlink capability), JUnit in the unique Evidence
directory. No live scheduler was installed or invoked. New exact-head review and
CI remain required; older b1 review is not promoted to approval of this revision.

## All-member renewal proof correction

Coordinator msg_6c5dcbd65b3d relayed Claude's exact-head 5933a824 finding:
an aggregate digest plus a fresh earliest expiry still allowed a later-due Node
leaf to remain unchanged, or a Node member path to be replaced at the same count.
At KST 14:27, both added regression cases against unchanged 5933 production
code failed with pytest **exit 1**, **2 failed / 34 deselected** (DID NOT RAISE).
This is reproduced defective behavior, not a passing verification lane.

The executor now retains the in-memory map of relative public CP/all-Node leaf
paths to SHA-256 before the attempt. After finalObserve it requires the identical
path set and a changed digest for every member, in addition to count, validity,
outside-window and aggregate-change gates. Durable latch schema is unchanged.
The two new behavioral cases retain two Nodes, reach post-renewal-certificates,
fail there, retain the failed mutation latch and refuse every command on the
next trigger with recovery-required. No live certificate or scheduler is used.

Windows Python 3.14.7 focused run on 5933 plus this explicit dirty correction:
`python -m pytest tests/test_scheduled_leaf_renewal.py -q --junitxml=.work/supervision-codex-audit/c304-member-correction.xml`
exited **0**, **35 passed / 1 skipped / 0 failed / 0 errors** at KST 14:29.
The sole executable-symlink capability skip still requires hosted Linux evidence.
Before/after JUnit is preserved in the unique Evidence directory. New exact source
head, CI and Claude review remain required before any schedule registration.
