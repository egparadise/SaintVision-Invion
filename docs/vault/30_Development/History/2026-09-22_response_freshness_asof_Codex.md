---
doc_id: "CODEX-RESPONSE-FRESHNESS-ASOF-001"
title: "Run, shard, artifact, and log truth-time audit and contract update"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "pending"
base_sha: "94fbf7e8fc6d35e87731ec4d52e6509fccaf6f1a"
updated: "2026-09-22T01:11:58+09:00"
source_of_truth: "Git"
tags: ["freshness", "timestamps", "contracts", "postgresql"]
---

# Response freshness: persisted time versus read time

## Source audit and field decisions

| Response | Source state | Contract field | Exact meaning |
|---|---|---|---|
| `RunResultView` (live run status) | `inv.runs.updated_at` is set by the `inv.guard_run` trigger on insert/update; `ResultView.result()` already loads the run row but omitted the timestamp. | `stateUpdatedAt` (required `Timestamp`) | Durable last update to this Run's state row. It is not the HTTP read time. Existing `completedAt` remains the attempt-result commit time and is null if no result completion exists. |
| `ShardObservation` | Parent and shard `inv.runs.updated_at` values are stored and available in the status queries, but were not selected. | `stateAsOf` (nullable `Timestamp`) | Latest durable `updated_at` among the parent and member Run rows represented in the response. It is not a query timestamp or one consistent snapshot time, and does not date linked delivery, receipt, or storage-object rows. Null only if no Run row is represented. |
| `RunArtifactList` | `_current()` already selects `inv.result_completions.completed_at`. | `completedAt` (nullable `Timestamp`) | Attempt result commit time. It is not the time artifact bytes were fetched. Null when no result completion is present. |
| `RunLogView` | Same persisted completion row as `RunArtifactList`; no separate log-capture timestamp is stored. | `completedAt` (nullable `Timestamp`) | Same attempt result commit time; it dates the committed output from which logs are projected, not log rendering or redaction time. Null when no result completion is present. |

The artifact and log endpoints do not persist an independent log-captured-at time. The truthful value they can expose is the result completion time they already read. No response field uses a screen or HTTP request time as if it were a data truth-time. The schema descriptions record these meanings. `tools/check_response_freshness.py` now checks the four responses and the existing node, replica, model-commit, and storage time fields against its independent pinned map.

## Execution evidence

The initial PG checks ran on the dirty author worktree based on `afe8b71ee9c9ecd9de4094a1bbcc97b90ee94b7a`, before the later docs/tool-only commits. A second PG run below used the current integration base `bbfb42b6c898a9bb5e25909eb5baa716f21f26a9` plus the listed local changes. These are local author executions, not independent review. The worktree was dirty for every test that included this change.

- On 2026-09-22 00:57:00 KST: `.venv/Scripts/python.exe -m pytest tests/integration/test_write_response_contract_real_pg.py::test_resource_offer_write_response_matches_real_postgres_state tests/integration/test_project_observation.py::test_shard_view_and_parent_cancel_use_actual_durable_admission tests/integration/test_project_observation.py::test_run_result_and_empty_views_expose_durable_state_time_not_read_time -q` — exit 0, 4 passed. `INV_TEST_ADMIN_DSN` pointed only to the disposable PostgreSQL 16 instance. `ShardObservation.stateAsOf` equalled the DB maximum `updated_at` of its parent and shard runs; `RunResultView.stateUpdatedAt` equalled its persisted `inv.runs.updated_at`; the no-result artifact/log routes returned null `completedAt`. The parameterized resource-offer test preserved both `appliedToKernel=false` without a kernel resource and `true` with one.
- The applied path seeded a same-tenant `inv.nodes` row and a CPU `inv.resources` row for the business capability. The HTTP response returned `appliedToKernel=true`, the exact kernel resource ID and capacity 16000, and no refusal reason; PostgreSQL then contained `inv.resources.offered=8000`, equal to the response and business offer. This was the success branch missing from the previous evidence. The refusal control still passed.
- PG container: `sv-codex-freshness-pg-20260922`, ID `54dc3ba97ed527dcbca9b7fe52bdc65a312258c7d8449203924b65695e94f75f`, labels `ai.saintvision.owner=codex` and `ai.saintvision.task=response-freshness-tests-20260922`; PostgreSQL 16, data directory on tmpfs, loopback-only dynamic port. Labels and full ID were re-inspected before cleanup; `docker rm -f -v` succeeded and a subsequent inspect confirmed absence. The three running protected project containers remained untouched.
- On 2026-09-22 01:05:51 KST: reran the three PostgreSQL-backed tests above using `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6 and a newly owned PostgreSQL 16 container. `tools/provenance.py --executor Codex -- <pytest command>` recorded base `bbfb42b6c898a9bb5e25909eb5baa716f21f26a9`, branch/worktree, dirty status, interpreter, environment gate (`postgres_dsn=set`), and invocation time. Exit 0, 4 passed, 7 warnings. The container was removed with `docker rm --force --volumes`; a separate inspect returned nonzero/no object, confirming absence. PowerShell surfaced that expected inspect stderr as a native-command error in the cleanup block; the independent absence check confirmed cleanup completed. No other container was targeted.
- On 2026-09-22 01:11:58 KST: provenance-wrapped `npm --prefix apps/web test -- --reporter=json --outputFile=<temporary file>` on base `4fbe99919d8dd0d97a39fb8c3f031f594b71f7bc`, dirty worktree, Node 24.17.0, exit 0; parsed report: 607/607 tests passed, 0 failed, 0 pending. The temporary report was removed. This is component/unit evidence, not browser acceptance. Expected mocked HTTP failure logs appeared; no test failed.
- On 2026-09-22 01:10:54 KST: focused tests, schema export, freshness map, binding, docs and ontology all reran on exact integration base `4fbe99919d8dd0d97a39fb8c3f031f594b71f7bc` with dirty worktree and project Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6. Results: focused tests 18 passed; 46 schemas current; freshness 9/9; 35 fixtures/11 anchors; docs 686 versioned documents/48 tasks/12 outcomes; ontology all exit 0. Full Vitest was rerun on the same base at 01:11:58 above.
- On 2026-09-22 01:10:54 KST: provenance-wrapped `npm --prefix apps/web run build` and `npm --prefix apps/web run contracts:check` both exit 0 on base `4fbe99919d8dd0d97a39fb8c3f031f594b71f7bc`, dirty worktree, Node 24.17.0. Vite built successfully; 16 API response TypeScript types match JSON Schemas.
- On 2026-09-22 01:02:00 KST (dirty worktree, base `94fbf7e8`): focused core contracts/anchors/page tests 29 passed, exit 0, using `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6. This was before the final core-only rerun below.
- At 2026-09-22 01:03 KST (dirty worktree, base `94fbf7e8`): `tools/export_schemas.py --check` exit 0 (46 schemas); `tools/check_response_freshness.py` exit 0 (9/9 curated checks); `tests/test_response_freshness.py` 2 passed; `tools/check_contract_bindings.py` exit 0 (35 fixtures, 11 response anchors). Schema descriptions were regenerated from the canonical schema and exporter check passed again.
- After fast-forwarding `bbfb42b6` and `4fbe9991`, `sync_obsidian.py --check` at 2026-09-22 01:10:54 found 3 pending exports and 0 conflicts. `--apply` at 01:11:37 exported exactly 3 files and matched 1483 destination hashes. The post-apply check at 01:11:47 reported 1483 managed files, 0 pending exports, 0 conflicts, exit 0.
- The result-output positive-completion HTTP test lives in the Linux-only Workspace execution lane. This Windows host did not run that lane. The persisted source field and nullable behavior are source-confirmed, while a non-null `completedAt` from an end-to-end executed process was not newly measured here. The fixture/schema and core conformance are checked; do not upgrade that to a live process result.
- Provenance environment: worktree `C:/Project/SaintVision-Invion/.worktrees/codex-response-freshness`, branch `agent/codex/response-freshness`, Windows 11, executor Codex, interpreter `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node `v24.17.0`. PG commands had `postgres_dsn=set`; static/core commands had it absent. Go compiler was absent, so no Go compile is claimed. No browser or live production HTTP acceptance was run.

## Boundary and handoff

Backend response contracts and durable timestamps are added. Gemini's UI truth-time wiring is already present at integration base `597ef148` and the complete Vitest suite passed in this worktree; that is not independent UI review or browser acceptance. Display `stateAsOf` according to its limited field meaning above; do not label it the instant of a common snapshot. Independent backend review remains pending against the committed integration SHA.
