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


Final pre-commit combined run, KST 13:19:12?13:20:05, Windows runtime above:
`python -X utf8 -m pytest tests/test_scheduled_leaf_renewal.py tests/test_lan_leaf_rotation.py tests/test_lan_leaf_rotation_standalone_runtime.py tests/core/test_lan_pki.py -q --junitxml=.work/supervision-codex-audit/c304-final.xml`
exit **0**, **108 passed / 7 skipped / 0 failed / 0 errors / 0 deselected**.
Seven skips are the new executable-symlink witness and six pre-existing standalone
symlink boundaries unavailable on Windows. Input was base 0f8e461d plus the four
modified tool/test/README paths and this untracked History (explicitly dirty,
not an unchanged-source claim). Docs, ontology and diff gates exited 0.
Isolated Obsidian check: 2075 pending / 0 conflicts, exit 0, no writes.
