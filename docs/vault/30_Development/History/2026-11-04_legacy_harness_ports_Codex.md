---
doc_id: "HIST-20261104-LEGACY-HARNESS-PORTS-CODEX"
title: "Legacy PR118 and PR119 narrow harness forward ports"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-11-04T14:20:00+09:00"
updated: "2026-11-04T14:33:00+09:00"
source_of_truth: "Git"
task_id: "task_2944648d1e21"
---

# Legacy harness forward ports

The two source gaps identified by the thirteen-head audit are implemented as narrow harness
changes. S04 executes one HTTP/PostgreSQL case containing four measured subcases and verifies
both JSON and executable JUnit. S07 adds an explicit read-only registration adapter while
retaining the default synthetic measurement path. Physical delivery/recovery remains UNMEASURED.

## Scope and provenance

- Orca task `task_2944648d1e21`, dispatch `ctx_8fe0598e2b57`, run `run_e57ecd84a7bc`.
- Coordinator assignment: `msg_3b55e3c9c37f`. Owner/executor Codex; root/Claude independent
  exact-head review pending. No subagents were used.
- Source base `03e17c31cf535008d39534aaa80d3ae274bd75cc`; branch
  `agent/codex/legacy-harness-ports-20261104`; checkout
  `D:/Project/SaintVisionI-Invion/legacy-pr-audit-20261104`.
- Separate source commit: `d44d7a0800996a1e7f282e0a16ae4c7c40b1592f` (eight necessary paths).
- Original reviewed heads: PR118 `c149f8dff4df36aa8918ea8d2bb45fb200cc0d03`,
  PR119 `367ac3398dee3f832e6f76cd18def715e8a5362c`.
- The thirteen-row report is already separately committed/pushed as
  `36a53b9df1d4cd023b3098e50368f67373e54a45`; it is not inherited by this source branch.
- Guidance refreshed: INDEX-PROGRESS-001 v1.0.375, WORKBOARD-CODEX-001 v1.0.337;
  previously read GUIDE/ADR/roles/Git/continuity/continuous execution/roadmap and backend/DB/storage
  plans apply. Skills: agent-delivery v1.1.0, core-reliability v1.0.0 and version-matched Orca
  orchestration guide. Coordinator owns shared board/registry aggregation and vault export.

Only the necessary runner/adapter/tests and these unique History/Evidence artifacts change.
No product policy, public schema, migrations, shared boards, credentials, real Node, pilot namespace,
or schedule was changed. All existing volumes, including the 69 preserved anonymous volumes,
remain untouched. The PostgreSQL checks use a new random-name labeled container with a tmpfs data
mount and loopback-only random port; only its exact verified owned ID is removed afterwards.

## Implementation

| Area | Necessary paths | Behavior |
|---|---|---|
| S04 | `tools/run_s04_db_evidence.py`, `tests/core/test_s04_db_runner.py`, `tests/integration/s04_db_runner_case.py` | HTTP create/cancel replay, quorum/immutable expiry, publisher crash/republication, transactional consumer rollback/dedup; no physical delivery claim |
| S07 | `tools/measure_s07_recovery.py`, `tools/five_node_lab_preflight.py`, `tests/core/test_s07_recovery_measurement.py`, `tests/integration/test_five_node_lab_preflight.py` | Explicit five-node-lab dry-run through the existing strict inventory/READ ONLY helper; CP-colocated Node excluded from disruption plan; current registration-only test retained alongside S07 projection test |
| Existing synthetic defect | `tests/integration/s07_recovery_measurement_case.py` | Three-line forward propagation of the seeded project ID fixes an observed NameError in the unchanged synthetic path |

The PR119 version of the common helper would remove the newer `validate_five_node_inventory`
entry point. That deletion is excluded: the helper receives only its three-line optional
transform seam, preserving the current shared validator and callers.

Compared with the old PR118 runner, duplicate/malformed inventories, operational acceptance
claims, missing/wrong/empty/skipped/failed JUnit and failed pytest completion are rejected. A
failed invocation removes its positive JSON. Missing DSN removes stale green JSON/JUnit and
returns exit 2 with BLOCKED/UNMEASURED. The expiry case waits for the immutable deadline rather
than updating approval authority. Its consumer callback performs a real SQL outbox effect on the
same transaction; rollback leaves both effect and inbox at zero, then exact replay leaves one each.

S07 retains default adapter `synthetic`, existing required synthetic knobs/defaults and schema v2
scope `disposable-postgresql-synthetic-measured-nodes`. Explicit `five-node-lab` requires inventory
and `--dry-run`; execution knobs/JUnit are rejected. Missing inventory/DSN returns exit 2 with
BLOCKED/UNMEASURED and clears stale output. Valid read-only observation may exit 0 with
`preflightStatus=BLOCKED`; READY means registration/topology only. `recoveryWaveReady` retains the
proposed preflight meaning and never authorizes disruption: no physical execution path is added,
`physicalRecovery=UNMEASURED`, and `operationalAcceptanceAssessed=false` remains explicit.

## Measured failures and repairs

- Before runner implementation, the ported S04 tests failed collection: import of
  `tools.run_s04_db_evidence` was absent; pytest exit **2**, one collection error.
- Before adapter implementation, the ported S07 tests produced **3 failed, 7 passed**, exit **1**:
  missing `build_five_node_s07_preflight` and `write_registration_mtls_preflight` seam.
- A real PostgreSQL compatibility run then exposed the existing default synthetic NameError at
  `s07_recovery_measurement_case.py:223`: `project_id` was created by `_seed_round` but omitted
  from its return value and caller unpack. It was immediately reported to the coordinator in
  `msg_d13a2259a94a`. Source scope expands only to that necessary harness file; no product fix.
- The first disposable-server attempt stopped before tests because Engine 20.10 reports tmpfs
  in HostConfig rather than Mounts. The evidence driver now verifies the actual tmpfs configuration
  and absence of volume mounts. The exact owned container was removed on that failed attempt.

## Verification

Windows / PowerShell, absolute interpreter
`D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe` (3.14.7), pytest 9.1.1.
The append-only command log records source HEAD, tracked dirty paths, argv, start/end KST, direct
exit and redacted stdout/stderr:
`docs/vault/30_Development/Evidence/2026-11-04_legacy_harness_ports_Codex.jsonl`.
The adjacent `.py` is the reproducible recorder/disposable-server driver; synthetic passwords and
DSNs exist only in process memory/environment and are removed from recorded diagnostics.

| Check | Observed result repeated directly at source commit d44d7a08 |
|---|---|
| Focused unit/compatibility: S04 runner, S07 adapter, existing placement adapter | **54 passed**, exit 0, no skips |
| S04 runner via actual HTTP and disposable PostgreSQL | **1 executable test passed**, four measured subcases, exit 0, no skips; JSON + JUnit |
| Shared registration and S07 preflight via actual disposable PostgreSQL | **2 passed**, exit 0, no skips; before/after rows unchanged and actual READ ONLY helper enforced |
| Default synthetic CLI, 3 synthetic Nodes, one round, 0.05s liveness/0.02s poll/0.5s test limit | **1 passed**, exit 0, no skips; schema v2 explicitly synthetic, physical acceptance false |
| Owned disposable database/login residue | **0 / 0**, followed by exact-ID owned-container removal and absence check |

These are separate processes; four pytest tests across the three PostgreSQL commands are not
four physical Nodes or four S04 JUnit cases. Timings above are test settings, not AC-07 SLO evidence.
No actual inventory, real transport/cleanup, physical byte movement, browser or device acceptance
was measured. Every positive check above was repeated at exact source
`d44d7a0800996a1e7f282e0a16ae4c7c40b1592f`, with no tracked source delta; the dirty files were
only the new History/Evidence. Delivery gates are recorded in the same log. The compact machine
summary and final artifact hashes are in
`docs/vault/30_Development/Evidence/2026-11-04_legacy_harness_ports_Codex.summary.json`.

## Handoff

Final documentation, ontology and sync-check gates each exited **0** at source d44d7a08 with
the final report/evidence inputs: 1,166 versioned documents; RDF/SHACL and mapping checks;
2,082 managed files / 17 pending exports / zero conflicts, no writes. Product-directory diff
against base is empty (exit 0). Only eight harness paths are in the source commit; the uniquely
named report/evidence are a following documentation commit.

Implementation is locally verified and ready for root/Claude review. Hosted CI and
independent review remain pending; no whole-project or operational acceptance is claimed.
No shared Obsidian export is performed; only the required read-only sync check is permitted.
Next owner: root/Claude review the narrow source commit, integrate into the additive candidate,
then run that candidate's required CI lanes. The original PRs must not be blindly merged or their
historical artifacts substituted for the new measurements.
