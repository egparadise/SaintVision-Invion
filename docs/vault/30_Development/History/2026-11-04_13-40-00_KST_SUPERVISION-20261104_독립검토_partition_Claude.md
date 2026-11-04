---
doc_id: "HIST-20261104-SUPERVISION-CLAUDE"
title: "SUPERVISION-20261104 Claude 독립 검토와 시험 DB partition 공백 수정"
version: "1.18.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-11-04T13:40:00+09:00"
updated: "2026-11-04T20:35:00+09:00"
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
| `b5b8ca68` | **source accepted** | The post-check now also requires the identical member key set and that every original member's digest changed. `_leaf_set` serializes byte-identically to `5933`; I checked that on a fixture, so existing latches stay comparable. Local: 35 passed, 1 skipped. My member probe now raises. Removing both new clauses gives 2 failed; removing only the key-set clause fails only the path-drift case. Hosted: Docs `41779908269` and Portal `41779908380` success; Desktop `41779908545` failed with the known `KeyError: 'IPAddress'`; Read back after both finished: Backend `41779908473` and Core `41779908364` each ended with 42 failed and 9 errors. That is the base `03e17c31` set (by file: release-acceptance write/resolver, model deployment, replica-repair route and storage project scope real-PG; AC-11 migration rehearsal; VF-CL registry), attributed to the partition gap, the AC-11 fixture and the VF-CL drift. None is in `test_scheduled_leaf_renewal`. |

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

## PR #406 final UI (`deef98ad`, F5 delta over `789999d8`): source accepted, one Low

Scope: `App.tsx`, `ResourceExplorer.tsx`, `nodeCertificateObservation.ts` and three tests. Owner Codex retry
`ctx_bb8984a92eb7`; Gemini is credited for F1–F4.

- **Wiring:** `clusterTrust` is derived only from the retained, validated observation and the active project. It is
  passed at `App.tsx:558` (DesktopShell) and `:780` (ResourceExplorer). This closes my #401 finding that no caller
  passed `trust`. Per-node `certificateNotAfter` comes only from a current canonical observation, and the NodePage
  fallback `2099-01-01` is excluded by a test.
- **Local runs:**
  - full web vitest suite: 102 files, 1,217 passed;
  - the four focused files: 62 passed;
  - `eslint`: exit 0; `tsc --noEmit`: exit 0.
- **Negatives covered by the new suite:**
  - pending-node and pending-certificate turn unknown at exactly 60 s + 1 ms, with no flicker;
  - near-expiry → expired, and the renewal boundary, while polls stay pending;
  - reject and missing-item clear the per-node values;
  - late responses after a project switch-back and after re-authentication are ignored.
- **Mutations**, each caught on the 8-case file:
  - removing the 60 s bound: 2 failed;
  - making the transition timer a no-op: 3 failed;
  - letting per-node values ignore freshness: 2 failed.
- **Low, synthetic probe:** once the observation is stale, `nextNodeCertificateTransition` still returns the
  renewal-start and expiry boundaries.
  - With a 90-day leaf, the app schedules `setTimeout` with a delay of 7,603,138,900 ms, beyond 2^31−1. Under real
    timers Node logged `TimeoutOverflowWarning` (clamped to 1 ms).
  - Browsers store the delay as int32 too, so they very likely re-render and reschedule continuously while stale.
  - The loop itself was not reproduced: happy-dom measured 1 extra call in 1 s.
  - Displayed trust stays `신뢰 미확인`, and 6-day pilot leaves do not trigger it.
  - Fix: return `null` once `now >= observedAt + 60000`, and clamp the delay.
  - Probes are kept outside the repository (scratchpad `zz-claude-probe-*.tsx`).

## S04/S07 legacy harness forward port (`d44d7a08`, report `66975f00`): source accepted, two Low

Reviewer role: Claude is the reviewer the S07 spec names.

- **Byte identity:** the eight scoped files have the same blobs at `d44d7a08` and candidate `c71fb324`. I ran at
  `c71fb324` against the disposable PG on 55493.
- **Results:**
  - S04/S07 unit tests: 38 passed (my file set; the author's 54 was not re-derived);
  - `test_five_node_lab_preflight.py`: 2 passed (registration and s07 adapters; DB state unchanged, READ ONLY
    verified);
  - `run_s04_db_evidence.py`: exit 0, 4/4 PASS, physical delivery `UNMEASURED`, no operational-acceptance claim;
  - S07 synthetic (3 nodes, 2 repetitions): exit 0.
- **Negatives:**
  - S04 without a DSN exits 2 `BLOCKED` and removes the stale outputs;
  - five-node-lab without `--inventory`, or with `--nodes`, is refused.
- **The S07 `NameError` was real:** at `03e17c31` the test body uses `project_id`, which only `_seed_round` defines.
- **Low 1:** after a validation failure, S04 deletes the JSON but leaves a green JUnit.
- **Low 2:** a five-node-lab `BLOCKED` preflight exits 0, and a transform `KeyError` escapes the
  `ValueError`/`RuntimeError` catch.

## Finishing checks before freeze

- **PR #406 `af3a94ed` (delta over `deef98ad`): source accepted.** This closes my Low.
  - Once `now > observedAt + 60000`, `nextNodeCertificateTransition` returns `null`, and the delay is clamped to
    2147483647.
  - My original probes re-run at the new head:
    - fake clock, 90-day leaf: 0 calls after the observation goes stale;
    - real timers, 90-day leaf: 0 calls and no `TimeoutOverflowWarning`.
  - Removing the guard makes exactly the new 90-day test fail.
  - Local: 63 focused and 1,218 full web tests passed; `eslint` and `tsc` exit 0.
- **happy-dom `21.0.4` (root's dev-dependency bump):**
  - I ran it uncommitted (`--no-save`) in my scratch checkout of `af3a94ed`: 102 files, 1,218 passed.
  - I did not re-verify the advisory or the engines myself.
- **S04 JUnit fix (root working tree; applied as a patch to my scratch copy only):**
  - `test_s04_db_runner.py`: 27 passed.
  - Reverting the runner hunk fails the 3 new cases.
  - This closes my Low 1.
- **Factual review of the docs (read-only; I edited nothing):**
  - S07 spec 1.1.1: the facts are correct, but the "Claude review is separate" sentence is out of date.
  - Catalog 1.6.0: the S04 row is correct together with the JUnit fix, and the S07 row correctly states that exit 0
    can carry `BLOCKED`. I suggested keeping the original author attribution.
  - Orca board 1.0.2: two "pending Claude" cells are out of date. I did not re-measure the r5 expiry myself.
- **Shared stash:** a temporary entry I created during a mutation run, `claude-s04-mut`, was dropped by its tag.
  Nobody else's stash entry was touched.

## Exact-commit binding of the finishing checks

The checks in the previous section ran on scratch copies. They are now bound to root's commits.

- **`c79c297c81767b03a8f8191532ca414713779533` (S04 JUnit fix): source accepted.**
  - Its diff is byte-identical to the patch I reviewed.
  - `tests/core/test_s04_db_runner.py`: 27 passed. The 3 new cases fail without the runner hunk.
- **`b015019fe6d7d4f3cf53d05945e2fe614a20d4b4` (happy-dom bump): source accepted.**
  - It changes only `apps/web/package.json` and `package-lock.json`: happy-dom `20.14.6` to `21.0.4`, with integrity.
  - Measured in a clean scratch worktree at `b015019f` after `npm ci`:
    - happy-dom `21.0.4` installed;
    - vitest: 102 files, 1,218 passed;
    - `eslint`: exit 0; `tsc --noEmit`: exit 0;
    - `npm audit --omit=dev`: 0 vulnerabilities.
- The coordinator froze the combined head `fd1530d9` at `coord/train79a-ci-20261104-1548` for the final hosted CI. I
  did not read back those hosted lanes, and I record no result for them here.

## r5 renewal and IdP plan (`52e23649`, private packet): source accepted as a non-executed plan

Read-only review. I registered no task, applied nothing and prepared no node.

### Verified

- **Packet integrity.** Every private copy matches its packet digest:
  - gate script `a83e32bd`; transition `51b02052`; IdP apply `f3af8c41`; guard suite `8de722a6`;
  - config `4fb067d0`; bindings `a67edb51`;
  - preparation `1e5af979`; registration `d79184ed`; run-context probes `8430c453`; IdP plan `228403ff`;
  - the four node stdin scripts match their pins.
- **Gate order and fail-closed preparation.**
  - The plan has 14 gates.
  - Only `currentStatus` and the two `runtimePreflight` gates run before the durable latch. The latch is written
    before `prepare`.
  - Scheduler `_run` checks the executable digest, every input pin and the working directory before each gate.
  - Registration is `-PlanOnly` only.
  - The preparation arrays create only new r5 directories: they assert the directory is absent and use `mkdir 0700`.
    They use pinned interpreters and files, leave node identity untouched, and are marked `executed=false`.
- **IdP repair scope.**
  - All five sources and the existing TLS CA still have their planned hashes, and the target and backup directories
    are absent.
  - The candidate profile's tenant, issuer and `jwks_file` point only at the new `r5-f8923863\identity` directory.
  - The plan changes no service switch, global trust or DNS setting.
- **Guard suite.** 15 passed. I ran it from my scratch venv with no bytecode or cache, and no file was written into
  the packet.
- **Two hypotheses I tested and dropped:**
  - A detached child started by the launcher keeps the gate's captured stdout open and hangs the transition gate. A
    synthetic Windows PowerShell 5.1 probe returned in under 1 s, both with and without redirection.
  - The launcher picks a different interpreter. The reviewed source is a standalone clone, so the launcher resolves
    to its own pinned `.venv`.

### Conditions (none blocks landing; C1 must be met before live registration)

- **C1 Medium: the run context is unmeasured.**
  - All three read-only probes are `executedInS4U=false`. They must run once in the real S4U task context: expect
    `currentStatus` exit 0, and both preflights exit 0 after preparation.
  - `transition` also runs under S4U. `Start-LiveConsole` restarts the observer, and possibly the tunnel and serve,
    in a non-interactive S4U session. No probe shows those processes survive the end of the task and the 4-hour
    limit.
  - Add a transition-context probe, or make the first transition attended.
  - If the launcher fails after `Stop-Process`, the observer stays down and the latch reads recovery-required. That
    is fail-closed, but the service is degraded.
- **C2 Low: IdP apply leaves the backup directory's parent unchecked.**
  - `.work\intranet\backups` does not exist today.
  - `New-Item -ItemType Directory` silently creates missing intermediate directories; I measured this in scratch.
  - The reparse check covers only `.work\intranet`.
  - Fix: pre-create that directory and check it, or create it explicitly with the non-reparse check.
- **C3 Low:** the `lan_pilot` gates run with `-B` but without `-I`, and the scheduler inherits the S4U user
  environment, so `PYTHONPATH` and `PYTHONHOME` would be honored. Sanitize the environment or document it.
- **C4 Low:**
  - The remote install script calls `bash` through `PATH`; the script itself is hash-pinned.
  - Node 2 uses `python3.12` while node 1 uses `3.14`. The install preflight must prove the worker runs on 3.12.
- **Info:**
  - The IdP candidate bundle expires on 2026-11-11 at 15:11:35 KST, about one day after the CP leaf expiry, so it
    needs a weekly refresh.
  - The repair restores no running service by itself (`serviceSwitchIncluded=false`).
  - `transition.ps1` does not check the source HEAD itself. Gate 0 checks the HEAD and a clean tree, and the gate pins
    cover `Start-LiveConsole.ps1`, `SvLauncherInput.ps1` and `lan_pilot.py`.

### Time stamps

The `updated` values of revisions 1.3.0 (15:45) and 1.4.0 (16:05) were ahead of the system clock. This revision
records the measured time, 15:58 KST.

## Train 79 landing script, and the r5 live-console loss and restoration

### Landing script `merge-land-train3-79-fd1530d9.sh.pending` (sha256 `65f19bf4`): accepted, one Low

- The script runs only a normal fast-forward from `03e17c31`.
- Before that, it requires:
  - the exact `HEAD` and a clean tree;
  - a prelanding receipt with `PASS`, the exact `codeSha`, the source binding, and ten `MEASURED_PASS` items;
  - the integration tip still at `03e17c31`;
  - `03e17c31` as an ancestor of `fd1530d9`.
- The push is not forced, and the script reads the ref back afterwards.
- Low: the header said I had reviewed the exact head `fd1530d9`. I reviewed only its constituent commits. Root fixed
  the wording.
- The coordinator reports that train 79 landed. I did not read that back myself.

### Live console loss at 15:52 KST: cause not proven

- The observer logged every ~7.5 s until 15:52:14.8 KST and missed the ~15:52:22 tick. At 16:08 root found no
  listener on 3000, 18082 or 55448.
- My session is ruled out:
  - my only action in that window was a scratchpad file write;
  - the `taskkill` filter (`WINDOWTITLE eq none`) in my earlier synthetic probe matches no process on this host.
- What I measured:
  - A process started from the Orca → agent → shell chain is in a job.
  - Its `Start-Process` children stay in that job (`inJob=True`). A `CREATE_BREAKAWAY_FROM_JOB` child leaves it
    (`inJob=False`).
  - The source-03 launcher starts its helpers with `Start-Process`.
- So "the helpers died with the launching agent's job" fits the facts but is not proven, because the job of the 14:26
  launching agent can no longer be inspected.

### Recovery artifact (plan `d1c0b05e`, controller `bb464028`, helper `af53251b`): accepted for one-shot invocation

- The artifact checks:
  - the plan, pins, SID, bindings, executables, state and known-hosts digests;
  - the source-03 `HEAD` and a clean tree.
- It does nothing else:
  - it reuses a tunnel only through `Assert-SvOwnedTunnelListeners`;
  - it uses no new credentials, writes no task, certificate or config, and runs the canonical launcher.
- I ran the same WMI shape synthetically (`Win32_Process.Create`, `CreateFlags` 16777216, `ShowWindow` 0). The
  process came back with return value 0, `WmiPrvSE` as its parent, `inJob=False`, session 1 and the same user.
- Low: `ssh` reads the default user config because no `-F` is given.

### Restoration process proof (follow-up folder, measured live 16:28–16:30 KST): not terminal-owned

- My own readback:
  - the overview reported `live-postgresql-mtls` with 2/2 nodes online and fresh, the kill switch on, 0 runs, and the
    web page returned HTTP 200 (3 samples, 8 s apart);
  - the observer log was still advancing;
  - the helper and caller processes had exited.
- Process tree, measured with `IsProcessInJob` on each PID:
  - every process the helper started directly is job-free: `ssh` and the three venv redirectors;
  - the real interpreters under the redirectors are in a job: observer, serve and console;
  - node (vite) and its esbuild child are in a job.
- Core's "all roles job-free" gate compared redirector PIDs for observer and serve but the interpreter PID for the
  console. Measured consistently, all three behave the same way.
- Synthetic mechanism checks:
  - The venv redirector puts the real interpreter in its own job. Killing the redirector killed the interpreter.
  - `node` started outside any job stays job-free until it spawns a child. After that, both node and the child are
    in a job (`node` v24.10.0).
  - Both are jobs internal to the runtime, not the terminal's job.
- Verdict:
  - The literal all-roles job-free gate stays failed, and it cannot pass by design.
  - The functional criterion I proposed:
    - every process the helper started directly is job-free;
    - every process in a job is a pinned runtime child;
    - the port owners and command lines match source 03 and the state;
    - persistence is re-measured after the restoring worker sends `worker_done` and its terminal is reopened.
  - Persistence is not measured yet.

## VF-CL-04 landed attestation, r5 C1–C4 delta, and the AC-11 PostgreSQL 16 client fix

### VF-CL-04 attestation recording (report worktree, four data files): accepted, one required text fix

- What I checked independently:
  - Run 41792498330: `workflow_dispatch` on `integration/all-agents-unified` at `fd1530d9`, success.
  - Its artifact id, digest and expiry equal the recorded fields.
  - I downloaded the artifacts myself. The receipt and bundle are byte-identical to the recorded files.
  - The verifier returns `VERIFIED` at `fd1530d9`; the old head `ad0132b3` is refused with exit 2.
  - The registry checker exits 0 with `acceptedCards` 0.
- Required fix: the card's `ciVerifiedNote` still named the old run and head. Root is correcting it.

### r5 C1–C4 delta (manifest `af73684d`, 17 inputs re-hashed): C2, C3 and C4 accepted, one new release condition

- **Guard suite:** 27 passed.
- **C2:** the IdP path guards check every directory from the trusted root to the scope. Only the exact immediate
  `backups` directory may be created, and it is re-checked after creation.
- **C3:**
  - every `lan_pilot` gate runs with `-E`;
  - the gate wrapper's children run without `PYTHONPATH`/`PYTHONHOME`;
  - status runs with `-E`.
- **C4:** node 2 pins `bash` and Python 3.12, and runs the real worker preflight after preparation.
- **New condition (Medium):**
  - The attended transition relaunches the helpers with plain `Start-Process`, so they inherit the caller's job.
  - Before the first attended cycle, it must run from a context proven to be outside any job, or check
    `IsProcessInJob` on every new helper root.
- **Residual:** the scheduled `transition` gate still pins the old script. That path is not released.

### AC-11 migration rehearsal: PostgreSQL 16 client fix (branch `agent/claude/ac11-pg16-client-20261104` @ `38a1bede`)

- **Cause, measured:**
  - The failing run 41793552539 used the `ubuntu-26.04` image (PostgreSQL 18.6 client).
  - The last green run, 37093057306, used `ubuntu-24.04` (PostgreSQL 16.15).
  - The 18 `pg_dump` writes `SET transaction_timeout`, which the 16.15 service rejects.
- **Fix:**
  - The workflow pins `ubuntu-24.04` and selects `/usr/lib/postgresql/16/bin` explicitly, after checking both tools
    report 16.x.
  - Before creating any database, the runner refuses unless both client majors equal the server major. It records the
    client versions in the report.
  - No SQL filtering, no tolerated restore errors, and no change to the migrations, the database or the acceptance
    criteria.
- **Tests:**
  - 207 passed, including 11 new cases.
  - A mutant without the preflight fails the new test.
- **Real rehearsal** against a disposable PostgreSQL 16.15 server:

  | Runner | Client | Result |
  | --- | --- | --- |
  | old `fd1530d9` | 18 | fails on `transaction_timeout`; same server error as CI |
  | new `38a1bede` | 18 | refused before any database is created |
  | old `fd1530d9` | 16 | `MEASURED_PASS` |
  | new `38a1bede` | 16 | `MEASURED_PASS`; JUnit 7 tests, 0 failures, 1 skipped; residue 0 |

- **Not measured:**
  - whether the hosted image provides the PostgreSQL 16 tools today (the workflow step fails closed if it does not);
  - root's independent review.

## Closing the source review phase

The items below were reported by root or core on Orca. I did not measure them myself.

- **AC-11 fix `38a1bede`:** root independently accepted the source.
  - Root read the three-file diff and ran 207 tests: exit 0, 0 skipped.
  - The hosted `ubuntu-24.04` PostgreSQL 16 path is still pending actual CI.
- **VF-CL-04 note:** root fixed the required `ciVerifiedNote` text in `f0536e95`. The signature CLI and checker exit 0.
- **r5 persistence:**
  - Core reports a measurement after a fresh worker reopen at 16:50–16:52, and root reports one at 16:56–16:57.
  - Both found the same five PIDs, sources, owners and listeners, two advancing intervals, 2 nodes online and fresh,
    and HTTP 200.
  - The literal "all roles outside any job" gate stays failed and retired.
- **Runtime preparation:** passed on Python 3.12 and 3.14.
- **IdP:** the new profile was applied, and the five originals are unchanged.
- **S4U probe registration:** `Register-ScheduledTask` was denied with `0x80070005`, once, with no fallback. C1 is
  therefore still open for the S4U run context, and no renewal task is registered.
- **Still open from my verdicts:**
  - the attended-transition job condition (Medium). Core will reopen a new attended WMI context for separate review;
  - the scheduled `transition` gate still pins the old script, and that path is not released.
- Claude's source review phase for task `task_710152a20196` is closed. I did no source cleanup, because root owns the
  integration workspaces.

## r5 WMI cycle packet review (task `task_e230ea589f7d`): changes required, one High

Scope:
- Core commit `9f5191eb` and the private packet `.work/r5-persistence-c50115dce654`.
- Manifest `0e51a7c7`. I re-hashed all nine inputs, and they equal the manifest.
- Plan pins: 105 and 103, with 0 mismatches.
- Guard suite: 15 passed, and no file was written.
- Read-only. Nothing was executed against the pilot.

- **H1 High (measured):**
  - In the attended cycle config `2a907e4b` and the scheduled proposal `9b96bb4a`, the `transition` gate keeps the venv
    `python.exe` as its executable, but its arguments are now PowerShell arguments.
  - I ran that `python.exe` with those arguments: `Unknown option: -N`, exit 2.
  - So every released cycle would fail at gate 10, after `commit` and under the durable latch.
  - The build script never sets the executable, and the guards check only the arguments.
  - Fix: use the pinned `powershell.exe` with its hash, add a guard on the executable, then re-seal.
- **M2 Medium:**
  - `schedulerPath` (`source-b5b8/tools/scheduled_leaf_renewal.py`) is not among the plan pins.
  - The scheduler itself checks only `git HEAD`, not a clean tree or the file's bytes.
  - The file is byte-identical to the b5b8 blob today.
- **Accepted rules:**
  - Command, owner and pins: hashed plan, allowed operations, guards hash, ordinary non-reparse pins, an exact record
    root, and the owner SID.
  - One-shot records: intent/launch/result written with `CreateNew` + `Move`; no retry or fallback.
  - Context: the job-free entry is asserted again inside the child. The ContextOnly receipt shows session 1,
    interactive, `inJob` false, `WinSta0\Default`; the helper exited and nothing was relaunched.
  - Before any stop: the status guard runs first. Each stop re-checks PID reuse (creation time, command line, owner
    SID), stops leaves before the root, and refuses multiple independent roots.
  - Primary failure: observer fallback, then a real 2/2 observation, then a `CreateNew` receipt, then a throw.
  - Observer recovery is a separate operation. The Python environment variables are cleared and restored.
  - For the WMI path, this closes my earlier attended-transition Medium.
- **Scheduled proposal:**
  - Replacing `51b02052` with the WMI controller in Scheduled mode closes my residual in source, but H1 applies to it
    too.
  - S4U is not accepted: the S4U-to-WMI desktop path is unmeasured, and actual registration was denied
    (`0x80070005`).
  - Low: the proposal shares its status/log paths with the attended cycle and has notifications disabled.
- **Outside-window no-op proof: safe only with a fresh RunId.**
  - At b5b8, `--window-only` only reads the config and the state. It writes no lock, latch, status or log, stops no
    observer and changes no certificate. The entry returns refusal exit 4 with `cycleExecuted` false.
  - The proof must not use the sealed RunId `20261104T082522Z-c50115dce654`. That is the first-cycle command's RunId,
    and its one-shot guard would then refuse.
- **Low:** the controller waits only 3 minutes for a Transition receipt, so a slow launch fails closed with completion
  unknown.

## r5 packet fix and eff93191 test-expectation review (task `task_0f5b922ea663`)

### r5 packet fix `.work/r5-packet-fix-5babae638fde`: H1 and M2 closed, release conditions below

Scope:
- Manifest `993febe8`. All nine inputs re-hashed and equal to the manifest.
- Attended config `5168c560`, scheduled proposal `8fbdbb6a`, cycle plan `3ffaa00a`.
- Read-only. No cycle, transition, observer stop, certificate change or S4U attempt.

What I checked:
- Structural JSON diff against `r5-persistence-c50115dce654`:
  - In both configs only the `transition` gate changed: executable, hash, packet paths and the plan hash.
  - The other gates are byte-equal.
  - The scheduled proposal also changed its log/status paths and `notificationsEnabled`.
- **H1 closed (measured):**
  - The gate executable is `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe`. Its actual SHA-256 equals
    the pinned `60c9b298…`.
  - I ran the exact gate-10 argv of both configs with a fresh RunId and `-PlanOnly`: exit 0, operations `Transition`
    and `ScheduledTransition`, `executed` false.
  - `wmi-runtime` was unchanged after the run.
- **M2 closed:**
  - The cycle plan now has `schedulerSHA256` `d4284248…` and exactly one matching pin. That equals the file and the
    `b5b8ca68` blob `8d9f030d`.
  - The scheduler imports no sibling repo module, only the standard library and `cryptography`.
  - `Assert-SvPinnedScheduler` runs immediately before both scheduler invocations in the entry script. The controller's
    pin check also covers it.
  - The cycle argv with a fresh RunId and `-PlanOnly` exits 0.
- **Lows closed:**
  - The scheduled proposal has its own status and log files and notifications on, with all other gates equal.
  - A receipt timeout now writes a `CreateNew` `completion-unknown` record (exit 124, no retry) and keeps the intent.
    The one-shot check includes that record.
- **Guard suite:** 30 passed on Python 3.14. No packet file was written.
- **RunIds:** the ContextOnly, Cycle, ObserverRecovery and ScheduledTransition RunIds are distinct. None equals the old
  sealed `20261104T082522Z-c50115dce654`. Only ContextOnly records exist.
- **ContextOnly 17:58:40 receipt (read, not re-run):** helper 41708, owner matched, session 1, interactive, `inJob`
  false, `WinSta0\Default`. The helper has exited.
- **Read-only `--window-only` at 18:23 KST:** exit 0. `inWindow` false, `expired` false.
  - `renewAt` is 2026-11-08 14:15:35 KST and `earliestNotAfter` is 2026-11-10 14:15:35 KST.
  - The state tree and `wmi-runtime` were unchanged.
- **Residual Low:**
  - The controller still waits only 3 minutes for a `Transition` receipt, inside a 900-second scheduler gate.
  - A slow but successful transition would therefore fail closed after `commit`, under the latch, and need manual
    recovery.
  - Measure the transition duration or raise the wait below 900 s before release.

Outside-window no-op proof:
- It is safe only as a `Cycle` with a new RunId that is not the sealed first-cycle RunId `20261104T090054Z-ccda46e61cd5`.
- Run the standalone `--window-only` immediately before it, and run it only while that check shows `inWindow` false
  with a wide margin before 2026-11-08 14:15:35 KST.
- The proof is not structurally a no-op. If the window were open, the same command would run the real cycle.
- The controller exits non-zero on the expected exit-4 refusal. That is the pass condition, not a failure to hide.

Orca one-off on Nov 8, as the current-user alternative to S4U:
- This is feasible as a supervised attended cycle.
  - The WMI helper launch already proved a job-free session-1 context from an Orca-run caller.
  - The window refusal is enforced inside the helper, so neither Orca "run now" nor a precheck bypass can force the
    window.
- It needs root's release, the user logged on in session 1 with Orca running, and the PC awake.
- It must run the sealed first-cycle argv exactly once. On any failure the latch is preserved and the agent does not
  retry.
- Fallback slots are needed before the 2026-11-10 14:15:35 KST expiry.
- `orca automations` triggers are recurring (preset, cron or RRULE). I did not create one, and a one-shot RRULE is
  untested.
- This does not accept S4U or unattended renewal, and C1 stays open.

### eff93191 test-only correction (root uncommitted patch, diff SHA-256 `e5a70403…`)

- **The change:** one test file only. The VF-CL-04 assertion no longer freezes run `40633895766`. Instead it binds the
  registry's `runId`, `headRef` and artifact id/digest/expiry to the committed receipt.
  - The `headSha`, receipt-path and bundle-path checks against the manifest are kept.
  - No checker, criterion or product file changed.
- **What I ran**, in a temporary detached checkout of `eff93191` (since removed):
  - Before the patch, the selected case fails: `40633895766` against `41792498330`.
  - After applying root's exact patch, both full files pass: `tests/core/test_check_vf_cl_registry.py` and
    `tests/test_vf_cl_ci_attestation.py` give 244 passed, 0 skipped, exit 0.
  - The registry checker exits 0 with `acceptedCards` 0.
  - `verify_vf_cl_ci_attestation.py` against the committed receipt and bundle (head `fd1530d9`,
    `refs/heads/integration/all-agents-unified`) returns `VERIFIED`, run `41792498330`.
- **Mutants:** registry `runId` changed to `41792498331` fails; registry artifact digest changed fails.
- **My earlier gap:** my VF-CL-04 recording review did not run this test file either.
- **Opinion: land it.**
  - It is defensible to land the test-only correction after this full two-file run, the real verification and Docs CI.
  - All 8 required post-landing workflows must still pass at the exact landed head.
  - Keep the `eff93191` FAILED record, and make no pre-8 pass claim.
- **Text drift, not a test failure:**
  - `docs/vf-cl-registry-manifest.json` `whyCiVerified` and the registry `note` still name run `40633895766`. A test
    asserts the manifest text.
  - Changing it is a criterion edit and needs its own review.

## Root `59f0a3c2` CI-text correction review (task `task_169f7a385e7c`): accepted

Diff `eff93191..59f0a3c2`, 3 files, one commit:
- **Manifest:** only VF-CL-04 `whyCiVerified` changed.
  - It now names `Run 41792498330` and the receipt named by `ciVerifiedAttestation`.
  - It keeps the OIDC, Sigstore, re-checkable and expiry boundaries, and adds "does not grant operational acceptance".
- **Registry:** only `version` (1.6.4 → 1.6.5) and the last sentence of `verifiedAgainst.note` changed.
  - The 03e17c31 local re-verification facts are kept.
  - The tree/ref/landedNote/hostedRun/reverification fields, and all machine-check, implies, receipt, bundle and
    attestation fields, are unchanged.
- **Test file:**
  - The earlier `runId`/`headRef`/artifact binding is kept.
  - `test_the_shipped_manifest_keeps_the_reason_the_last_edit_wrote` now requires `Run {runId}` from the committed
    receipt, instead of the old constant, and keeps the OIDC and re-check anchors.

What I found and ran:
- **Root's first text edit broke a second test.** That edit made `whyCiVerified` generic, which broke this second
  hard-coded `406` assertion.
  - Root's `.work/source80-rationale-full.log` showed 1 failed, 243 passed, and I reproduced it.
  - Root then named the current run and derived it in the test. That keeps the protection, so the old constant is not
    simply weakened.
- **At `59f0a3c2`, in a temporary detached checkout (since removed):**
  - both full files: 244 passed, 0 skipped, exit 0;
  - registry checker exit 0, `acceptedCards` 0;
  - `check_docs` exit 0;
  - the real verifier returns `VERIFIED` for run `41792498330`.
- **Mutants:** the old `Run 40633895766` text and an unnamed-run text both fail the new assertion.
- **One unexplained failure (not reproduced):** one full run of my scratch variant (before `59f0a3c2`) failed
  `test_the_shipped_registry_agrees_with_this_tree` once.
  - It passed alone and in the full rerun, and I did not capture the assertion.
  - That test calls git against the live repository, so if it recurs in CI, treat it as a finding.
- **Opinion:**
  - Commit `59f0a3c2`, run Docs CI, land by the targeted plan, then require all 8 workflows at the exact landed head.
  - Keep the `eff93191` FAILED record, with no pre-8 pass claim.

## Train 80b landing script review (task `task_bf87ab92d622`): accepted, read-only

Script: `merge-land-train3-80-59f0a3c2.sh.pending`, SHA-256 `2da6ef1a…`, 60 lines. `bash -n` exits 0. I did not execute
it.

Gates:
- **Source:**
  - It requires the exact head `59f0a3c2` and a clean tree. Both held at 18:56 KST.
  - The `eff93191..59f0a3c2` path set must be exactly the three files.
- **Strict JSON deep compares:**
  - The manifest may differ only in VF-CL-04 `whyCiVerified`.
  - The registry may differ only in `version` (1.6.4 → 1.6.5) and `verifiedAgainst.note`.
- **Local test record:** the local JUnit must have 244 testcases with no failure, error or skip.
  - Read now: 215 core plus 29 attestation testcases, all passing.
- **Prior FAIL record:** the `eff93191` prelanding JSON must still read `FAIL`.
- **Docs CI:** run 41810435583 is re-read and must be completed and successful, with the same head, branch,
  `workflow_dispatch` and title.
  - Read now: completed, success, workflow `Documentation Build`, job `docs` success.
- **Signature:** real Sigstore verification of the FD receipt runs through `verify()`, which raises on any mismatch.
- **Landing:**
  - It requires the integration tip to equal `fd1530d9` (read now: `fd1530d9`) and `fd1530d9` to be an ancestor of
    the landing commit.
  - It pushes normally, without force, so a non-fast-forward is rejected.
  - It reads the remote head back after the push.

Lows, none blocking:
- The JUnit timestamp (18:39:56) is earlier than the `59f0a3c2` commit time (18:44:07), and the file names no commit.
  My exact-head 244 run and Docs CI cover the gap.
- The Docs CI check does not pin `workflowName`; the title pins it in practice.
- `json.loads` collapses duplicate keys. The strict-load test among the 244 covers the shipped files.
- The prior FAIL JSON is checked by fields, not by a hash.

The `eff93191` script (`99353908…`) is still `.pending` and separate. Nothing in this script claims a pre-8 pass for
`59f0a3c2`. All 8 workflows at the exact landed head remain required.

## Post-landing S12 attestation at `59f0a3c2` (task `task_bf87ab92d622` follow-up `task_9285e19358a2`): VERIFIED

- **Remote:** `integration/all-agents-unified` reads `59f0a3c2` (`git ls-remote`).
- **Run 41811861496**, "S12 Acceptance Evidence", read from the GitHub API:
  - `workflow_dispatch`, path `.github/workflows/s12-acceptance-evidence.yml`;
  - head `59f0a3c2`, branch `integration/all-agents-unified`, attempt 1;
  - title `supervision-train80-s12-59f0a3c2-20261104`;
  - jobs `s12-acceptance-evidence` and `attest-vf-cl-ci-receipt` both succeeded.
- **I downloaded both artifacts myself** into a new empty directory:
  - `vf-cl-ci-attestation-59f0…`: id 13312139106, zip SHA-256 `4c7ce04d…`, which equals the API digest.
  - `s12-acceptance-59f0…`: id 13312408285, zip `e4959ab8…`, which equals the API digest. The receipt names this same
    id, digest and expiry (2026-12-04T10:06:19Z).
  - My receipt (`73bfbced…`), bundle (`8081d55c…`) and workflow `verification.json` (`64ac10c2…`) are byte-equal to
    root's `.work/post-landing/59f0…/vfcl` copies.
- **Real verification:** I ran the verifier from `59f0a3c2` source, with the module extracted by `git show`.
  - Result: `VERIFIED`, run `41811861496`, `receiptSha256` `3b57a4b4…`.
  - The verified certificate names the `s12-acceptance-evidence.yml@refs/heads/integration/all-agents-unified`
    signer, source digest `59f0a3c2`, a GitHub-hosted runner and a `workflow_dispatch` trigger.
  - The signed subject digest equals the receipt bytes.
- **Negatives, all refused with exit 2:**
  - old head `fd1530d9`;
  - wrong ref (the agent branch);
  - wrong workflow;
  - wrong repository;
  - one appended byte in the receipt (refused by the GitHub signature/identity check itself).
- **S12 evidence:** the 17 items are identical to the `fd1530d9` run. Only `codeSha`, `inputs`, `note` and
  `provenance` differ.
  - `verdict` FAIL and `acceptanceClaim` false are the expected non-acceptance, unchanged.
  - `pitr-configuration-possible` stays absent, and `pitr-rehearsal-dry-run-observed` stays observed.
- This proves the hosted CI derivation at the landed head only. It is not operational acceptance and does not change the
  48-task score. Backend and Core post-landing lanes were still running per root, and I did not read them.

## Final report checkpoint `5ac8e315` review (task `task_ce352123553b`): no overstatement, two wording Lows

Scope:
- Branch `agent/codex/supervision-delivery-report-20261104` at `5ac8e315`, fetched. It descends from `59f0a3c2`.
- 65 paths, all under `docs/`. No product, tool or test file changed.
- The report worktree is read-only to me and stayed clean.

Public-repo hygiene:
- The diff adds `*.private.ps1` packet scripts and evidence JSON.
- I scanned the added lines and found no key material, token, DSN password, owner SID, LAN IP, local username or email.
- The plans and configs that hold the SID and local paths were not committed.

Signed CI metadata:
- **Receipt and bundle:** the committed files are byte-equal to my own downloads, `73bfbced…` and `8081d55c…`.
- **Manifest:** only VF-CL-04 `whyCiVerified` changed (now naming `Run 41811861496`) and `ciVerifiedAttestation.headSha`
  (`fd1530d9` → `59f0a3c2`).
- **Registry 1.6.6:** only `version`, the VF-CL-04 `ciVerifiedNote` and `ciVerifiedAttestation`
  run/head/artifact changed.
  - `verifiedAgainst` stays tree `03e17c31` with the generic pointer.
  - `acceptedCards` stays 0.
- **At `5ac8e315`, in a temporary detached checkout (since removed):**
  - both full files: 244 passed, 0 skipped;
  - registry checker exit 0, `acceptedCards` 0;
  - `check_docs` exit 0 (1207 documents);
  - the committed pair verifies `VERIFIED` against head `59f0a3c2`.

Report claims checked against GitHub at 19:2x KST:
- **Post-landing lanes:**
  - Frontend, Desktop, Docs, Portal, Security and Accessibility (41811280240–41811322547) are completed/success at
    `59f0a3c2`.
  - Backend 41811262312 and Core 41811272283 are still `in_progress`. The report says they were running "when this
    section was written", which is accurate.
- **S12:** run 41811861496 matches my independent verification.
- **Docs CI:** runs 41810435583 (`59f0a3c2`) and 41813149485 (`5ac8e315`) succeeded.
- **AC-11:**
  - Migration 41812142359 and aggregate 41812412476 succeeded.
  - I downloaded aggregate artifact 13312648361 myself; its zip equals digest `c7ed5e8f…`.
  - `ac11-aggregate-result.json` says `INVALID_RUN`, `done` false. Axes: reversible `NOT_APPLICABLE`, restore-forward
    and security `MEASURED_PASS`, accessibility `MEASURED_FAIL`. Four required axes are missing.
  - The report states exactly that and does not turn the measurement into acceptance.
- **Kept separate in the report:**
  - `eff93191` pre-8 FAIL;
  - `59f0a3c2` pre-landing 244 tests plus Docs, with no claim that all 8 passed before landing;
  - the 6-of-8 post-landing state;
  - the AC-11 result.
- **Unchanged:** the original 48 tasks and criteria, and `0/5` acceptance.

Lows (wording only):
- The `ciVerifiedNote` says "His receipt, bundle and verification bytes…". It should read "Claude's".
- The report calls core's Transition-wait change "the proposal that resolved the 3-minute fail-closed risk". I have not
  reviewed that proposal, so it should say "proposed fix, pending Claude review".
- Backend and Core results must be appended when they complete, before any final 8-of-8 statement.

## Orca supervised pilot packet `r5-orca-supervised-288670efba3d` (task `task_2ae5dd31f68d`): SOURCE_ACCEPTED with one Medium to fix before release

Scope:
- Read-only.
- All seven declared hashes match: manifest `4f1f1ea8`, controller `c9fad676`, cycle plan `3d278293`, Transition plan
  `f51623da`, manual config `01237ed5`, `pilot_guard.py` `c653b741`, wrapper config `c52c0fb0`.
- No WMI launch, Cycle, Transition, Recovery, claim or Orca metadata action.

What I checked:
- **The 720-second packet** compared with the reviewed `5babae638fde` packet:
  - Guards, entry and the transition core are byte-identical.
  - The controller differs in one line: `Transition` waits 720 s, `Cycle` 4 h, and every other operation 180 s.
  - Configs and plans differ only in packet paths, the controller and plan hashes, and fresh RunIds. The four
    RunIds are distinct and none has a record yet.
- **The manifest** binds the preserved `993febe8` baseline.
- **Real `-PlanOnly` runs, all exit 0, `wmi-runtime` unchanged:**
  - the gate-10 argv of both configs (`Transition` and `ScheduledTransition`);
  - `ContextOnly`;
  - the `Cycle` command, each with a fresh RunId.
- **Wrapper read-only actions:** `describe` exits 0 for all three slots, with `claimExists` false. The not-due
  precheck refuses with exit 20 (`outside-2026-slot`) and takes no claim.
- **Tests:** the 48 isolated tests pass on Python 3.14. The packet and `run-state` were not written.
- **Precheck budget:** the precheck hashes 133 pinned files (103 MB) in 0.19 s, well under its 60 s timeout.
- **Pilot state:** the live `private-state.json` equals the pinned `7d62c49a`, unchanged since 14:17. The prepare,
  stage, commit and observe commands do not call `save()`. No lock, latch or lock-guard file exists.
- **Orca:** the installed `app.asar` SHA-256 equals the packet identity `c0446919`. I re-ran the replay and got the
  same result:
  - The packaged parser drops `COUNT=1` and the month/day fields of an RRULE, so it would recur daily.
  - Annual cron fires on 2026-11-08 05:20Z, 11-09 03:15Z and 11-09 23:00Z, then again in 2027.
  - The guard's absolute 2026 slot plus 10-minute grace refuses the 2027 occurrences and any "run now" outside the
    slot.

Accepted rules:
- **Pins:** every plan, packet, executable, scheduler and source pin is checked, with clean `HEAD` for both sources.
- **Leaf paths:** only state-relative paths are accepted, with containment and ordinary/reparse checks. This closes
  root's High.
- **Shared claim:** a single exclusive claim (`xb`) per run, after which every guard runs again; no reclaim.
- **Waits:** 720 s fits under the 900 s gate. The wrapper waits at most 14520 s, then records unknown/124 without
  killing the child or retrying.
- **Window and margin:** a margin of at least 4 hours is required.
- **Prior attempts:** a prior latch, lock, completion-unknown record, or intent without a result blocks the run. A safe
  exit-4 refusal does not.
- **Prompts:** they separate the current-user supervised pilot from S4U/production. The three automations are
  disable-after-claim.

Findings:
- **M1 Medium (measured with fakes):** after a real invocation, `execute()` calls `post_facts()`, which re-runs
  `facts()`. That includes `validate_release()` and every drift check. Any `Skip` raised there falls into the outer
  `except Skip` branch.
  - My probe: one invocation that returned renewed, then a post-readback `Skip('release-not-current')`.
  - The wrapper reported `exit 20, outcome "skip"` with `claimTaken` true, and wrote no per-run result.
  - This case is reachable. The fallback2 slot starts at 23:00–23:10Z, the release `validUntil` must be no later than
    01:15:35Z, and the cycle may run up to 4 h.
  - Safety holds through the claim, but an executed renewal would be reported as a skip.
  - Fix before release:
    - Do not re-validate the release after invocation.
    - Classify any exception after `invoke()` as `postcondition-unverified` (exit 1, or 124), keep the child result,
      and write the per-run result file.
    - Add a fake test for this case.
- **L1:** `validate_release()` accepts any 8 or more unique green checks. It should pin the exact eight workflow
  paths/names and the expected ref.
- **L2:** the prompt says "exact pinned993 Cycle", but the run uses the 720 packet; 993 is the bound baseline.
- **L3:** the direct-transition test plan says "verify993" and "measure … vs180". It should name the 720 packet and
  measure against 720.
- `ScheduledTransition` and `ObserverRecovery` keep 180 s. That is acceptable while they are unreleased.

The 3-minute Low:
- Structurally, 720 s inside the 900 s gate closes it in source.
- Closing it empirically requires one measured `Transition` with these conditions:
  - elapsed comfortably below 720 s (I suggest half of it or less);
  - all postconditions held: same public leaves and SPKI, two fresh nodes, an owned observer, a `CreateNew` receipt.
- My opinion: one standalone `Transition` before Nov 8 is worth releasing.
  - Conditions: a separate exact-plan review (fixing L3), root release, a fresh unused RunId
    (`20261104T102449Z-d02f35d04547` currently has no record), and ObserverRecovery reviewed in advance.
  - It is the only pre-cycle measurement of the live relaunch path. Without it, the first cycle's gate 10 is the
    measurement, and a slow result there fails after `commit` under the latch.
- Not S4U and not operational acceptance.

## Standalone Transition contract, ObserverRecovery contract and M1 wrapper delta (task `task_18ed92bf40ff`)

Scope:
- Read-only, under `.work/r5-orca-supervised-288670efba3d`.
- No WMI launch, Transition, ObserverRecovery, Cycle, claim or Orca metadata action.
- Hashes read back at 19:57–20:00 KST:
  - plan `643baaec`; Transition contract `e557f909`; ObserverRecovery contract `4b666847`;
  - `pilot_guard.py` `98142111`, config `f868eaef`, prompt template `2dbaf609`, disabled CLI plans `a462506e`;
  - all nine pins of both contracts equal the packet files: guards `e50c7f82`, controller `c9fad676`, entry
    `a4d64539`, core `b0963259`, Transition plan `f51623da`, cycle plan `3d278293`, attended config `01237ed5`,
    scheduled config `9b6a4bfb`, commands `b445b8fe`.
- `wmi-runtime` and `run-state` are empty, and no file names either RunId. Live `private-state.json` is `7d62c49a`.

### Transition measurement: exact plan ACCEPTED for ONE root-released call, with conditions

What the call does (read in source, not measured):
- The argv runs only the 720-packet controller with plan `f51623da`, `-Operation Transition` and RunId
  `20261104T104550Z-a906a2b3fc0a`. The controller's watchdog is 720 s for `Transition`.
- The core (`b0963259`):
  1. runs the `currentStatus` gate;
  2. refuses if `transition-core-<RunId>.json` already exists;
  3. stops only the exact owner/creation/command-line-checked observer group, children first;
  4. runs `Start-LiveConsole.ps1` without `-ReplaceForeignStateListener`;
  5. asserts a real two-member mTLS observation, with snapshots at most 20 s old;
  6. writes a `CreateNew` receipt.
  On launcher failure it starts an observer, records the error class, writes the receipt and still throws.
- `Start-LiveConsole.ps1` (`03e17c31`) reuses the owned SSH tunnel, `serve`, console (18082) and web (3000) when they
  belong to the same state. So only the observer is relaunched.
- Scope limit: the console keeps its in-memory TLS material. The test measures the observer relaunch and gate-10 cost,
  not a certificate reload.
- Live helpers at 19:5x KST (all created 16:20:1x, owned by the same parent):
  - observer 34380/33812; `serve` 40748/52720; console 3756/54216;
  - vite 25608; SSH tunnel 15408 (`55448`).

Release conditions:
- **Before the call:**
  - A separate root release names this contract and this RunId.
  - Only the RunId may be replaced, by a fresh, unused normal-clock value. Every executable, file and plan hash stays
    fixed.
  - The operation is `Transition`. `ScheduledTransition` and `Cycle` are excluded by name.
  - The 993 baseline, the nine 720 inputs and all pins match. `--window-only` shows `expired` false and `inWindow`
    false.
  - No lock, latch or lock-guard file exists, and there is no intent without a result and no completion-unknown
    record.
  - Saved: the three member paths with their PEM SHA, SPKI and notAfter, plus the state hashes. No private material is
    saved.
  - Kill is true, workload submission false, and runs and offers are 0. Two members are fresh and advancing.
  - Saved: the PIDs and creation times of the observer, `serve`, console, web and tunnel, and their listeners. Add
    `serve` to the contract's "same PIDs" list.
  - Owner SID, Session 1, interactive, and a job-free WMI child.
- **After the call:**
  - Identical member paths, PEM, SPKI, notAfter and protected-state hashes; three valid leaves.
  - A new owned observer group, while every other helper PID and listener is unchanged.
  - HTTP 200 from overview and `live-postgresql-mtls`; two fresh, advancing members; runs and offers 0; flags
    unchanged.
  - Intent, launch and result records, plus the `transition-core` receipt, all with this RunId and plan. Exit 0,
    `primaryLauncherSucceeded` true, and the real owner/session context with `inJob` false.
- **Duration:**
  - Measured as monotonic elapsed time, both intent→result and outside wall clock.
  - The 3-minute Low closes only if elapsed is at most about half of 720 s (360 s) and every postcondition held. One
    sample is not a worst-case bound, and the contract says so.
- **Any other outcome**, including `primaryLauncherSucceeded` false, exit 124 or an unknown record:
  - It is recorded as a failure. No retry and no automatic ObserverRecovery.
  - The Nov 8 cycle needs a new decision.

### ObserverRecovery contract: approved only as a separate decision

- Its argv uses the same controller and plan, `-Operation ObserverRecovery` and its own RunId
  `20261104T105008Z-f3999067b773`.
- The 180 s watchdog fits the branch, which does only three things: the `currentStatus` gate, starting the observer if
  it is absent, and `observe --once`. It never stops an observer, never touches certificate material and writes no
  core receipt.
- **Release conditions:**
  - A separate root release names the contract, the RunId and the hashes of the failure or unknown record.
  - A diagnosed loss of a known observer.
  - Every earlier writer has provably exited; silence or a reused PID is not proof.
  - No live child and no foreign observer or listener.
  - The original failure stays nonzero and is never relabelled PASS.
- **Postconditions:** the same as for the Transition, apart from the observer.

### M1 wrapper delta (`98142111`): M1, L1, L2 and L3 fixed; one new Medium, so do not arm yet

Fixed:
- **M1:** `post_facts` uses `revalidate_release=False` and requires the release check from entry, so an expiry after
  release cannot become a skip. Any post-invocation exception becomes `postcondition-unverified` exit 1, with
  `childResult` kept and the per-run result written. An outer `Skip` after invocation is now exit 1, not 20.
- **L1:** exactly eight checks, unique IDs, the fixed name set, `workflowPath`
  `.github/workflows/<file>` and the fixed ref. All eight workflow files exist on
  `origin/integration/all-agents-unified`.
- **L2 and L3:** the prompt says preserved993/execution720, and the plan names the 720 packet and 720/900.
- **Handoff:** one internal `orca orchestration send --to run:run_e57ecd84a7bc --type status`, with no `worker_done`,
  no old IDs and no external send. The CLI plans keep all three automations `--disabled`.
- **Tests:** 56 passed in 2.73 s, exit 0, on Python 3.14, with `-B` and basetemp in scratch. The packet file list
  was unchanged.

New Medium (M1b), reproduced with fakes:
- The probe is `probe_persistfail.py` in scratch. It makes `atomic_status` raise `PermissionError` for the
  result/status files after one real invocation; on Windows, `os.replace` fails like this when a reader holds the file
  open.
- The exception escapes `execute()` from line 252, and the handler's own write at line 261 fails again. `main()` line
  279 then reports `exit 20, outcome "skip", claimTaken false`.
- Meanwhile the claim exists, one invocation happened, and only the history file was written.
- The claim still blocks any retry, but an attempted invocation is reported as a no-claim skip.
- Narrow fix:
  - Make per-run and latest-status persistence best-effort inside `execute()`: on failure, return the in-memory
    result with `resultPersisted` false and its error class, and never re-raise.
  - In `main()`, a caught exception reports exit 124, `completion-unknown`, when the claim file exists. It never
    reports `claimTaken` false.
  - Add one fake test.

Lows:
- A `Skip` raised inside `invoke()` after the child started (for example a duplicate-key result) is reported as exit 1
  `postcondition-unverified` rather than 124. It is safe but less exact.
- `REQUIRED_REF` is `refs/heads/integration/all-agents-unified`. GitHub run `head_branch` has no `refs/heads/` prefix,
  so whoever builds the receipt must write this exact form.

Decision on the automatic wrapper: not armable until M1b is fixed and reviewed. Both contracts stay unreleased.

Not S4U and not operational acceptance.

## Measured standalone Transition and final M1b wrapper (task `task_6d2564cdd29b`)

Scope:
- Read-only, at 20:20–20:24 KST. No live operation, no precheck/entry/run, no Orca metadata change.
- I read the files and live processes myself. The automation drafts were read only with `orca automations show/runs`.

### The one released Transition (`20261104T104550Z-a906a2b3fc0a`): 3-minute Low closed empirically

Records (all present, one per kind):
- **Claim:** written 11:12:41Z (`CreateNew`), with release message `msg_2e6f7840251e`.
- **Intent and launch:** intent 11:12:42.25Z; launch `returnValue` 0, helper PID 36884.
- **Child result:** exit 0, plan `f51623da`, `transitionExecuted` true, `cycleExecuted` false. Context: session 1,
  `ownerMatched`, `userInteractive`, `jobQuerySucceeded`, `inJob` false, `WinSta0\Default`.
- **`transition-core` receipt** at 11:13:00.51Z: `primaryLauncherSucceeded` true, `observerRecovered` false, state
  `7d62c49a`, source `03e17c31`.
- **Duration result:** `cc168aa7`, elapsed 19.203 s, `controllerExit` 0, no observer-ceiling unknown, no child
  termination, no retry.
- **Absent:** no completion-unknown record, latch, lock or lock-guard file, and `run-state` is empty.

Before/after snapshots, compared field by field:
- **Unchanged:** member/PEM/SPKI/notAfter material and the state/local-key file digests. This holds in `before`,
  `after` and all three after-samples.
- **Window:** unchanged, `expired` false and `inWindow` false.
- **Program:** HTTP 200/200, `live-postgresql-mtls`, kill true, workload false, runs and offers 0, `onlineFresh` 2.
- **Ticks:** 11:12:35 before, then 11:12:59, 11:13:04 and 11:13:19 after. They advance; the gap during the observer
  restart is about 24 s.
- **Processes:** the only real changes are the observer pair, 34380/33812 → 49276/11276, and the snapshot helper's own
  PID. `serve`, the console, vite with its esbuild child, and the SSH tunnel keep their PID, creation time and command
  hash.

My own live readback at 20:2x KST:
- 49276/11276 run `observe` for this state under the expected SID in session 1; their parent 36884 has exited.
- Every other helper is unchanged, with listeners 55448→15408, 18082→54216 and 3000→25608.
- `private-state.json` is `7d62c49a`.
- Overview: `live-postgresql-mtls`, both members online/fresh (heartbeat 3.4 s old), runs and offers 0. Web returns
  200.
- Job membership:
  - The observer root 49276 is not in a job.
  - Its child 11276 is in a job, and so is the console child 54216 from the original 16:20 launch. This is the
    virtualenv redirector's own child job, not the caller's job, which was broken away from at 36884.

Decision:
- 19.2 s is far below my 360 s threshold and the 720/900 budgets, and every postcondition held.
- The 3-minute Transition-wait Low is closed empirically for this path. It is one sample, not a worst-case bound.
- With the wrapper's prior-attempt check on the final config, these records give `(earlier=False, unknown=False)`,
  so the measurement does not block the cycle.

### M1b final source (`pilot_guard.py` `acf8b4f6`): ACCEPTED

Fixed:
- Each result write in `execute()` is now best-effort.
- A write failure keeps the in-memory outcome under `operationResult`. The top level becomes exit 1
  `result-persistence-failed` (or stays 124), with `persistenceErrors` and `resultPublicationComplete` false. Records
  that were written earlier get one correction.
- If the pre-invocation history write fails, the run is refused (exit 1) before anything is invoked.
- `main()` keeps a shared `attempt_state`. After a claim, an escaped exception reports 124 when there is an attempt but
  no child result, otherwise 1 `claimed-result-unverified`. It never reports `claimTaken` false.
- The three earlier semantic classes (post-run expiry, post-check exceptions, outer `Skip` after invocation) are
  preserved.
- `validate_release`, `facts` and `invoke` are unchanged.

Evidence:
- **My probe** (`probe_persistfail.py`) against `acf8b4f6`: `execute()` now returns exit 1
  `result-persistence-failed`. It shows `attempted` true, `claimTaken` true, the child result kept, `operationResult`
  renewed, two `PermissionError` entries and `resultPublicationComplete` false. Before the fix it raised into a
  no-claim skip.
- **Tests:** both files, 62 passed in 3.45 s, exit 0, with the packet file list unchanged.
- **Config `ca684b45`:** its two `inputFiles` pins (`acf8b4f6` and prompt `2dbaf609`) match.

Lows (non-blocking):
- A successful run whose publication fails keeps the success fields at the top level next to exit 1. Exit and
  `outcome` are authoritative.
- A `Skip` inside `invoke()` after the child starts is still exit 1, not 124.
- A `KeyboardInterrupt` (BaseException) escapes both handlers and leaves only the claim file.

### Orca drafts: disabled and correct, but stale

- All three IDs show `enabled` false and have no runs:
  - primary `286d975e`;
  - fallback1 `a3a9e396`;
  - fallback2 `3e08faa1`.
- They match the reviewed plan: provider `codex`, the existing workspace, a fresh session, `Asia/Seoul`, grace 10 and
  a 60 s precheck timeout. Triggers and `nextRunAt` are 2026-11-08 05:20Z, 11-09 03:15Z and 11-09 23:00Z.
- Their stored precheck and prompt still bind config `f868eaef`. Against `c1b9e14f` they differ only by that hash.
- So every precheck would refuse with `wrapper-config-drift`, which fails closed. They must be re-edited with the
  `c1b9e14f`/`ca684b45` vectors and read back before enabling.

Not S4U and not operational acceptance of the cycle.

## Final binding and enabled automations, read-only check (task `task_07f2c493c77e`): CONFIRMED

Scope:
- Read-only, at 20:32–20:35 KST.
- Commands used: `orca automations show/runs`, `gh api` GET, and the wrapper's own `validate_release` run on a scratch
  interpreter.
- No precheck, entry, run, edit or test repetition.

Pins:
- Unchanged: `pilot_guard.py` `acf8b4f6`, config `ca684b45`, CLI plans `c1b9e14f`, prompt template `2dbaf609`, 720
  manifest `4f1f1ea8`. `run-state` is empty.

Release binding:
- **`release-parameters.actual.json`** is `d46ddd2a`. It binds:
  - receipt `final-ci-receipt.actual.json` (`2d9ca236`, hash matches);
  - head `59f0a3c2`;
  - the three automation IDs, primary `286d975e` first.
- **Receipt content:** approved `SOURCE_ACCEPTED`, `Cycle`, current-user pilot scope; 993 baseline and 720 execution
  packet; config `ca684b45`; executor `b5b8ca68`, runtime `03e17c31`; validity 2026-11-04 11:27:54Z to
  2026-11-10 01:15:35Z. It also cites my review commit `c24c29ee` and the measured Transition (`cc168aa7`, 19.203 s).
- **CI checks:** eight. Each has the exact workflow path, ref `refs/heads/integration/all-agents-unified`, head
  `59f0a3c2`, and completed/success, with 12 required jobs in all:
  - Backend 3, Core 2, Frontend 2, and 1 each for the other five.
- **GitHub API:** I read all eight runs (41811262312 … 41811322547) and their jobs myself. Every path, branch, head,
  conclusion and job name matches the receipt.
- **`validate_release`:** passes now and at each slot instant (2026-11-08 05:20Z, 11-09 03:15Z, 11-09 23:10Z).

Enabled automations, read back at 20:3x KST (before 20:35):
- **IDs:** primary `286d975e`, fallback1 `a3a9e396`, fallback2 `3e08faa1`.
- **State and schedule:**
  - all `enabled` true; provider `codex`; `reuseSession` false;
  - existing workspace `…/supervision-codex-20261104`; `Asia/Seoul`;
  - `run_once_within_grace` with 10 minutes; precheck timeout 60 s.
- **Next runs:** 2026-11-08 14:20, 11-09 12:15 and 11-10 08:00 KST. These match the guard's slots; the guard refuses
  the 2027 repeats.
- **Prompt and precheck:** for each automation they equal the `c1b9e14f` vector with one change: the
  `<RELEASE_PARAMETERS_SHA256_AFTER_J_GREEN>` placeholder is replaced by `d46ddd2a…`.
  - Each precheck names its own slot, the config and `release-parameters.actual.json`, and is precheck-only.
  - `f868eaef` no longer appears.
- **Runs:** none recorded.
- **Prompt rules:** an internal `run:run_e57ecd84a7bc` status handoff, no `worker_done`, disable-after-attempt, S4U
  not reopened.
- **Disable commands:** `disable-after-attempt.ready.private.json` holds the three exact `--disabled` commands.
- **Root's read-only precheck report:** all three slots exit 20 `outside-2026-slot`, with `attempted` and
  `claimTaken` false.

Low (non-blocking):
- The prompt says "the reviewed disable commands in the final binding" without naming the `.ready` file. The template
  `disable-after-attempt.plan.json` with placeholders still sits next to it.
- The IDs are also bound in the release parameters and `PLAN.md`, and the shared claim blocks a second Cycle anyway.

Scope: current-user supervised development pilot only. S4U stays denied and operational acceptance stays false until
a slot actually runs and is measured.

## State boundaries

- Implemented and locally verified: the partition fixture, the VF-CL landed-tree re-record, and the SEC-VF runner pin
  correction.
- Independent review: root accepted `5dd3f83b`, `f42c4259` and `87cdf206`. Root also accepted the SEC-VF pin
  correction at `402cd283` and merged it into `92856a9c`. Its basis was a Git-object comparison showing that only the
  runner blob, the target `sourceDocument` and the six known pin strings change. Writer `--check` exits 0, and the
  previously failing pin test now passes (1 passed).
- Operational acceptance: not claimed for anything on this page.
- No other owner's code was edited.
- Codex root accepted #407 `5dd3f83b` and #403 `f42c4259`, and integrated both at `d8af53c2`.
- Next first action:
  - Root merges `38a1bede` into the new final integration workspace, freezes the next source, and reads back the
    hosted AC-11 rehearsal on `ubuntu-24.04`.
  - Root lands `59f0a3c2` (keeping the `eff93191` FAILED record) and runs all 8 workflows at the exact landed head.
  - The three automations are enabled and confirmed. The next real event is the primary slot on 2026-11-08 at 14:20
    KST. After any claim, the operator disables all three and sends the internal status. Root then finishes the final
    docs; core finishes the public seal.
  - The Nov 8 cycle is a root-released, supervised attended Orca run of the sealed command.
  - S4U run context (C1) remains open.
  - Operational acceptance stays unmeasured.
