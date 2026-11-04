---
doc_id: "HIST-20261104-SUPERVISION-CLAUDE"
title: "SUPERVISION-20261104 Claude 독립 검토와 시험 DB partition 공백 수정"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-11-04T13:40:00+09:00"
updated: "2026-11-04T13:40:00+09:00"
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

- **VF-CL registry rule 8.** `verifiedAgainst.tree 51788009` reached integration with train 78, so
  `check_vf_cl_registry.py` exits 1 on train 78 and on #397. The shipped-registry tests require a `coord/*`
  candidate (`candidate: true`, `reverifyAt` integration) and a successful hosted Core run at that exact tree.
  03e17c31 has already landed, so it cannot be that candidate.
  - Next: the coordinator names the next train candidate ref and dispatches Core there.
  - Then Claude re-measures each card and re-records.
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

## State boundaries

- Implemented and locally verified: the partition fixture only.
- CI, independent review (Codex), and operational acceptance for this branch are pending.
- No other owner's code was edited.
- Next owner: Codex reviews this branch and PR #403 `f42c4259`; the coordinator integrates.
