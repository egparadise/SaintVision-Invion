---
doc_id: "HIST-20261104-SUPERVISION-CLAUDE"
title: "SUPERVISION-20261104 Claude 독립 검토와 시험 DB partition 공백 수정"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-11-04T13:40:00+09:00"
updated: "2026-11-04T15:00:00+09:00"
source_of_truth: "Git"
---

# SUPERVISION-20261104 Claude 독립 검토와 시험 DB partition 공백 수정

## Contract

- Task `SUPERVISION-20261104-CLAUDE`, Orca task `task_710152a20196`, dispatch `ctx_0bdc8c734c3f`, Run
  `run_e57ecd84a7bc`. Owner Claude, reviewer Codex.
- Workspace `supervision-claude-20261104`. Base is the integration tip `03e17c31cf535008d39534aaa80d3ae274bd75cc`
  (train 78), re-read with `git fetch origin` at the start.
- Fix branch `agent/claude/s20261104-partition-rollover`, cut from `origin/integration/all-agents-unified` = `03e17c31`.
- Documents read: AGENTS.md, agent-delivery 1.1.0, service-integration 1.0.0, INDEX-PROGRESS-001 1.0.375 (repo) /
  1.0.376 (shared Obsidian, 2026-10-29), WORKBOARD-CLAUDE-001 1.2.117, ROADMAP-VIRTUAL-COMPUTER-001 1.0.0,
  INDEX-VIRTUAL-COMPUTER-001 1.0.0, GOV-CONTINUOUS-001 1.1.0, GOV-CONTINUITY-001 1.0.0, GUIDE-001 1.1.0,
  ADR-INDEX-001 1.37.0, GOV-AGENT-001 1.1.3, GOV-GIT-001 1.1.4.
- Interpreters: Windows CPython 3.14.7 in two places, a scratch venv and the coordinator-provided
  `https-github.com-egparadise-SaintVision-Invion.git/.venv`. Node v24.10.0.

## Exact-head verdicts (re-observed heads; nothing approved by an older review)

| PR | exact head | owner | verdict | basis |
|---|---|---|---|---|
| #402 | `0f8e461d` | Codex | **changes requested** | Hosted Backend `40456817100`: 17 failed / 8379 passed on both 3.12 and 3.14. Root cause is the test fixture: it passes `sys.executable`, which is a symlink on the Linux runner, so `_regular` and `Register-LeafRenewalTask.ps1:15` correctly reject it. Medium findings: (1) a lock or precondition failure writes no receipt; (2) a killed run leaves a stale `O_EXCL` lock that silently blocks the expired alert; (3) no failure latch across the twice-daily triggers. Local Windows: 20 passed. |
| #401 | `589d7967` | Gemini | **changes requested** (feature claim) | No caller passes `trust`. The product node APIs (`/v1/projects/{p}/nodes`, `/v1/nodes`) carry no `certificateNotAfter`; only the loopback `lan_console` publishes it. Probe: no badge, no banner, every node shows "미확인". `unknown` is hidden, and "자동 갱신" claims a renewal scheduler that does not exist. vitest: 54 passed; hosted CI green. |
| #397 | `a44d578a` (delta over `f2936ae5`) | Codex | **source accepted** | Dependency gate: 0 errors at the head vs 18 at train 78; 2/4/42/0. eslint exits 0, including merged with #401. I re-ran the attestation verifier: VERIFIED (head `ad0132b3`, run `40633895766`). Hosted runs at the head are green. |
| #404 | `81a9982f` | Codex | **accepted as documentation** | `check_docs` exit 0, `git diff --check` exit 0. Its base is #397's branch, so landing order matters. |
| #405 code | `925dd669..38d443b7` | Codex | **accepted** | 36 passed. Swapping in the old tool gives 29 failed. Hosted Desktop Browser `41771833216` success. |
| #405 contract | `38d443b7..e97701bf` | Codex | **changes requested** (hosted) | Hosted Frontend `41774468131`: Portal container failed with TS2307, because the canonical schema import sat outside the Docker build context. Backend semantics accepted: 19 passed on real PG; frontend 14 passed; eslint exit 0. Notes: semantics diverge from #400's console; the client rejects clock skew. |
| #405 portal fix | `5a980dba..cd24dcb5` | Codex | **accepted** (source and hosted) | Dockerfile COPY of the schema plus `.dockerignore`. I read back hosted Frontend `41775977367` at `cd24dcb5`: success. Jobs `frontend` `126396304151` and `Portal Container Build & Hardened Runtime Smoke` `126396304451` both succeeded. |
| #402 corrected | `b1e59f85` (code `458c3389`) | Codex | **changes requested** | F1, F2 and F3 are addressed. Hosted Backend `41773055219` shows only the known 42F/9E set; locally 27 passed, 1 skipped. N1: a failure before any mutation latches, and the reset is refused inside the window. Probe `probe402_latch.py`: run 2 rc 2 `recovery-required`, reset raised ValueError. N2: `already-renewed` exits 0 silently when the leaves did not change (probe `probe402_silent.py`). Low: `_lock`'s `finally` can mask the original exception. |
| r5 plan | `4f53b5ab` | Codex | **accepted with conditions** | I verified the plan digest `2614a1b3…c24c039`. Bootstrap source has no diff between `e8606423` and `03e17c31`. Conditions: C1, bind the step 4–5 arrays and resolve the bundle placeholders; C2, the 6-day default and maximum leaf expires about 2026-11-10, with the window opening about 11-08; C3, the admin-password copy widens the secret surface; C4, a clock-bound check. The coordinator relayed that root bound C1–C4. |

## Demonstrated gap fixed here: the test DB's 2026-10 partition gap

- Measurement: the post-landing integration push runs, Backend `41765284237` and Core `41765284130`, each ended
  `42 failed, 9 errors`. Causes:
  - 40 failures and the 9 errors: `no partition of relation ... found for row`;
  - 1 failure: the AC-11 fixture, fixed by #397 `751ea725`;
  - 1 failure: VF-CL registry rule 8.
- Root cause: `tests/conftest.py` provisioned only FROZEN_NOW's month (2026-09), and the migration provisions from the
  wall-clock month (2026-11) onward. Module clocks pinned to 2026-10 (14 modules) became unroutable on 2026-11-01.
- Fix (test setup only): `tests/frozen_clock.py` holds `FROZEN_NOW` and `frozen_clock_span_months()`.
  `migrated` provisions FROZEN_NOW's month through the wall-clock month. No change to production migrations, the
  no-DEFAULT rule (CR-06), or retention.
  - New regression test: `test_every_month_from_the_frozen_clock_to_now_is_routable`.
  - New span unit test: `test_frozen_clock_span_is_whole_months_and_never_negative`.
- Real PostgreSQL: disposable container `claude-s20261104-pg` (postgres 16.15, tmpfs, 127.0.0.1:55493). Results:

| step | command | result |
|---|---|---|
| before, 13:20:29 KST, tree `03e17c31` | `pytest -q tests/integration/test_release_acceptance_write_real_pg.py` | 15 failed, 22 passed, exit 1 |
| after, 13:20:59 KST | `pytest -q tests/test_database.py` plus the five named real-PG modules | 115 passed, 0 skipped, exit 0 |
| mutation | restore the old conftest, run the new tests | 1 failed, exit 1 |
| full suite, 13:21:54–13:31:35 KST | `pytest -q tests/integration tests/test_database.py` | 4 failed, 935 passed, 466 skipped, exit 1 (see the failure breakdown below) |
| rerun, 13:32 KST | `pytest -q tests/integration/test_build_product_runtime_real_pg.py` | 13 passed, exit 0 |

None of the four full-suite failures is in the hosted failure set, and none is a partition error:
- 3 × `test_s3_object_store_postgres.py`: the tests assert the hosted MinIO lane's `INV_OBJECT_STORE_*`, which are
  not configured locally. This is a missing environment input, not a pass.
- 1 × `test_promotion_order_reaches_healthy_row_beyond_one_tick_budget`: WinError 10048 (local ephemeral port
  exhaustion). It passes on rerun, as the row above shows.

Skips (466) are Linux-only or opt-in Docker cases; all have stated reasons. Hosted Linux CI is the
authority for those.

## Not executable by Claude alone, with the next action

- **VF-CL registry rule 8**: corrected; see the section below. It is no longer a non-executable item.
- **All twelve Claude-owned 48-task cards** are `planned`/`blocked` and depend transitively on S01-BE (U2 IdP,
  U3 CA chain, U4 DNS) and S01-ST (U1 topology, U5 five-PC inventory/NTP, U6 storage product/credentials).
  - Next: the user supplies those inputs ([[2026-09-22_S01-BE_S01-ST_잔여_합격조건표_Claude]]).
  - Nothing is ready, and no ready state was invented.
- **r4 operation.** Codex worker's read-only observation (relayed): all leaves are expired and no listener is up.
  The supported recovery is a fresh isolated bootstrap, which is a live decision for the coordinator and user.
  - Claude did not touch live pilot state.
  - Starting Docker Desktop for the disposable PG auto-restarted the pre-existing container
    `saintvision-lan-db-319ce67f` through its own restart policy. It was not modified and was reported to the
    coordinator.

## PR #403 correction (own branch)

`docs/claude/c305-rescore-v1-21` `f42c4259` keeps the 11:04 KST record and adds what happened after it:
- the 12:08:42 KST landing of `03e17c31`;
- the red post-landing runs and their three attributed causes;
- no score promotion;
- the fresh-bootstrap next action.

`check_docs` exit 0, ratchet exit 0, `git diff --check` exit 0.

## PR #407 hosted readback

Hosted Backend `41774047968` at `5dd3f83b` concluded failure, with 2 failed and 8,376 passed on each interpreter. Both
failures are known and attributed:
- `test_the_shipped_registry_agrees_with_this_tree` is the VF-CL rule 8 failure corrected below;
- `test_main_reads_zip_and_github_metadata_files` is the AC-11 fixture failure that #397 `751ea725` fixes.

No partition error remains: the run had 42 failed and 9 errors before this branch. I am not calling the red run
green. The two remaining failures belong to the other two fixes.

## VF-CL landed-tree provenance correction (branch `agent/claude/s20261104-vfcl-landed-provenance`)

Base is `d8af53c2`, root's integration of #405 + #407 + #403. That candidate already carries #397's VF-CL-04
attestation edit, so I based on it to avoid conflicting with it.

- The defect: `verifiedAgainst` named the train 63 candidate `51788009` with `candidate: true`. That tree landed, so
  rule 8 failed on every branch.
- Re-measured at the landed tree `03e17c31` (detached checkout, 2026-11-04 13:58–13:59 KST, Python 3.14.7, Docker
  hidden from PATH, disposable PG on 55493). Each card is equal to Card 285:
  - VF-CL-01: 90 passed;
  - VF-CL-02: 212 passed, 1 skipped (Windows symlink privilege);
  - VF-CL-03: 124 passed;
  - VF-CL-04: 195 passed, 31 skipped (Linux boundaries and CX01).
- `git diff` confirms that no attributed test file changed between `51788009` and `03e17c31`, or between
  `03e17c31` and `d8af53c2`. No VF-CL module changed either; the only VF-CL difference is #397's attestation.
- `check_vf_cl_registry.py` at `03e17c31` reported exactly one finding: the rule-8 drift.
- Hosted evidence: Core `40451334923`.
  - Read back: headSha `03e17c31…`, `workflow_dispatch` on `coord/train78a-ci-1343`, attempt 1, success,
    2026-10-27 13:43 KST.
  - The owned CX01 steps succeeded, and the log shows `20 passed in 36.81s`.
  - `core.yml` at that tree asserts `skips == Counter()` and `passed == 20`.
  - This is a pre-landing run of the same source, recorded as exactly that. No new CI was invented.
  - Other runs: Backend `40451332159` and Docs `40451343361`, both success.
- The post-landing red push runs and their causes are recorded in `postLandingRuns`: Backend `41765284237`, Core
  `41765284130` and Desktop `41765284319`.
- Registry 1.6.2 → 1.6.3:
  - `tree` is `03e17c31` and `ref` is `integration/all-agents-unified`;
  - the `candidate` and `reverifyAt` markers are removed, after the re-measurement above;
  - VF-CL-04's `measuredIn` now names `40451334923`;
  - `scope` states that this is not operational acceptance, and `acceptedCards` stays 0.
- Test change: `test_the_shipped_registry_marks_its_tree_as_a_pre_landing_candidate` became
  `test_the_shipped_registry_names_its_provenance_state`. It accepts exactly two states:
  - an unlanded `coord/*` candidate with both markers;
  - an integration ref with neither marker, where the tree must be an ancestor of `origin/integration` in this clone.

  The negative rule-8 tests and the exact-head `hostedRun` test are unchanged.
- Mutation of the new test against five registry variants:

| variant | new test |
|---|---|
| shipped (landed) | pass |
| unlanded candidate with both markers | pass |
| `coord/*` ref with no marker | rejected |
| integration ref with the marker | rejected |
| landed claim on unlanded tree `d8af53c2` | rejected |

- Results: `check_vf_cl_registry.py` exit 0; `tests/core/test_check_vf_cl_registry.py` 215 passed, exit 0;
  `check_docs` exit 0; `git diff --check` exit 0.

## PR #408 hosted readback (`87cdf206`)

- Core `41777150275` (workflow_dispatch, full history): `tests/core/test_check_vf_cl_registry.py` passed in full,
  and the owned CX01 steps (create, drill, require, cleanup) all succeeded.
- Backend `41777076227`: no VF-CL failure.
- Both runs ended with exactly **1 failed** test. It is not from this delta:
  `test_import_ac11_security_scan.py::test_the_reviewed_security_allowlist_exactly_describes_this_tree`.
  - Base `d8af53c2` Backend `41776276009` fails that test and the VF-CL drift, so #408 removes one of the two base
    failures.
  - Cause: #405 `38d443b7` moved `tools/run_vf_security_tests.py` from `d9a40a03` to `df9a3f96` without moving the
    reviewed pin. I reproduced it locally (1 failed) and reported it to the coordinator.
  - The coordinator then assigned the pin correction to me (section below).
- Codex root independently accepted `87cdf206` and merged it into candidate `42bc8a10`.

## PR #402 later heads (Codex)

| exact head | verdict | basis |
|---|---|---|
| `5933a824` | **changes requested** (one Medium) | Local: 33 passed, 1 skipped (Windows symlink capability). Each mutation is caught: removing the post-renewal certificate check gives 2 failed; moving the latch back before `currentStatus` gives 6 failed; restoring the old lock cleanup gives 1 failed. N1 resolved: my `probe402_latch.py` run 2 now renews after a transient `currentStatus` failure. N2 resolved: unchanged or in-window leaves fail at `post-renewal-certificates` and latch. **Medium (synthetic reproduction):** `probe402_member.py`. CP and node-a are due in 1 day, node-b is already 3 days out, and node-b's leaf is not replaced. The run returns rc 0 `renewed`, because the post-check covers only the aggregate hash and the earliest expiry. The batch contract is all-Node (`lan_pilot.py:2604`), so every member must change. Hosted Backend `41777296911` matched the base's known 42F/9E set, with no `test_scheduled_leaf_renewal` failure. Core `41777296712` was cancelled. Desktop failed on the known Docker API 1.52 `KeyError: 'IPAddress'` (the base lacks #405). |
| `b5b8ca68` | **source accepted** | The post-check now also requires the identical member key set and that every original member's digest changed. `_leaf_set` serializes byte-identically to `5933`; I checked that on a fixture, so existing latches stay comparable. Local: 35 passed, 1 skipped. My member probe now raises. Removing both new clauses gives 2 failed; removing only the key-set clause fails only the path-drift case. Hosted: Docs `41779908269` and Portal `41779908380` success; Desktop `41779908545` failed with the known `KeyError: 'IPAddress'`; Backend `41779908473` and Core `41779908364` were not finished when this was written. |

Low, still open: `currentStatus` and `runtimePreflight` retries are safe only because the reviewed plan's commands are
read-only. `_command` does not enforce that. Scheduler registration and r5 live operation are a separate decision. I
claim no operational acceptance here.

## Freshness inventory (`91efbdbb`, delta over `fe69e300`): source accepted

Scope: only `tools/check_response_freshness.py` and `tests/test_response_freshness.py`.
- Schema: `core.schema.json` `ProjectNodeCertificateObservationResponse` has `observedAt` as a required `Timestamp`.
- Source of the value: `node_certificates.py:46` takes it from `SELECT clock_timestamp()`, emits it (`:68`), and
  derives trust from it (`:31`).
- Pin and negative case: the expected count 10→11 is pinned by hand, and the parametrized removal case keeps the old
  `stateAsOf` case.
- Results: 3 passed; the tool reports 11/11, exit 0. Deleting the new map line makes all 3 tests fail.
- Still report-only, with no workflow or tool consumer.
- Not verified by me: the client-side expiry the comment mentions. I will check it at the corrected UI head.

## SEC-VF runner pin correction (branch `agent/claude/s20261104-sec-vf-runner-repin`, base `7a1348c9`)

Reviewer basis: I independently reviewed `925dd669..38d443b7` and accepted it earlier in this page.
- The runner blob moved only at `38d443b7` (`03e17c31`, `925dd669`: `d9a40a03`; `38d443b7`, `d8af53c2`, `7a1348c9`:
  `df9a3f96`).
- What changed: the delta takes the isolated DB host from `NetworkSettings.Networks.bridge.IPAddress`, validates it as
  IPv4, maps a missing or invalid value to `_HarnessUnavailable`, and adds `--network bridge`.
- What did not change: node IDs, case identities, the `expectedTests` 6/0/0/0 counts, and skip accounting.

Three commits, following the precedent `c8de43ad` → `b1a0fb57` → `69944d33`:
1. `20f11b23` (source):
   - Only `secVf001.runner.blob` moves in the reviewed source.
   - `write_ac11_security_allowlist.py` regenerates the allowlist: blob `f55d49e3`, canonical `35e89ed2…`.
   - The aggregator's `ALLOWLIST_BLOB` and canonical digest take the writer's output.
   - `verifiedAt`, the definer signatures, the RLS dispositions and expiries, the SEC-VF node/case inventory and the
     workflow pin are untouched.
2. `2542f689` (evidence): the security target's `sourceDocument` becomes `{commit 20f11b23, blob f55d49e3}`.
3. `6184961f` (evidence):
   - Registry blob `d53b11f8` goes into the aggregator and all four importers.
   - The accessibility and security importers get `REGISTRY_COMMIT 2542f689`.
   - The security importer blob `231d7b5d` goes into the dependency/SAST allowlist.
   - The aggregator's `SCAN_ALLOWLIST_BLOB` becomes `b5b4265e`.

No old pin remains, by grep. Verification:

| check | result |
|---|---|
| `pytest` on the 14 AC-11/allowlist/threat files | 582 passed, 8 skipped (PG), exit 0 |
| PG-dependent `test_run_ac11_security_threat_reports.py` + `test_ac11_security_scan.py`, disposable PG 55493 | 46 passed, exit 0 |
| `write_ac11_security_allowlist.py --check` | exit 0 |
| Negative: the aggregator `validate_allowlist` on the old allowlist | refused ("does not match the reviewed content") |
| Negative: the old output under `--check` | exit 2 |
| Negative: the old output under the pin test | 1 failed |
| Old → new difference | only `secVf001.runner` |

Envelopes produced against the old allowlist will not be admissible, by design; none was promoted.

## State boundaries

- Implemented and locally verified: the partition fixture, the VF-CL landed-tree re-record, and the SEC-VF runner pin
  correction.
- Independent review: root accepted `5dd3f83b`, `f42c4259` and `87cdf206`. The SEC-VF pin correction is waiting for
  root review.
- Operational acceptance: not claimed for anything on this page.
- No other owner's code was edited.
- Codex root accepted #407 `5dd3f83b` and #403 `f42c4259`, and integrated both at `d8af53c2`.
- Next first action: Codex root reviews `agent/claude/s20261104-sec-vf-runner-repin` at its exact head. The
  coordinator integrates it and then runs the full hosted CI that it deferred until this blocker was fixed.
