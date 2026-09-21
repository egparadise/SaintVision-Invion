---
doc_id: "API-RESPONSE-CONTRACT-MAP-001"
title: "Frontend response contract map and workspace slice"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude (pending)"
updated: "2026-09-21T16:01:00+09:00"
source_of_truth: "Git"
---

# Frontend response contract map and workspace slice

## Inventory and counting boundary

Inventory scope is `apps/web/src/shared/api` excluding the common transport `client.ts`, plus the feature-owned API facade `features/desktop/fabricControlApi.ts`: eight functional adapter modules. Direct `apiClient` calls inside screens are listed separately because they do not have a shared adapter module. “Bound” means backend Pydantic response → exported JSON Schema → generated TypeScript → repository-owned fixture shared with provider and frontend tests. A typed `apiClient<T>` or a route-coverage result alone does not count as response-contract coverage.

| Priority / adapter | User-facing surface | Bound response groups | Still unbound and what can quietly break |
|---|---|---|---|
| P1 `projectObservation.ts` | App project selection; DeveloperStudio workspace picker | Workspace list and execution-readiness responses are bound in this slice | Project list still accepts two historical envelopes (`projects` and `items`). If a producer silently changes either shape, App can lose the selectable project list or fall back to ID-only names. Keep the two variants distinct until their backend ownership is resolved. |
| P1 `approvalReview.ts` | ApprovalReviewPanel before a person approves an action | None | A changed workload, action digest, policy digest, expiry, or status shape can prevent review or misrepresent what the approval is bound to. Existing runtime identity checks fail closed, but mocks are not pinned to a shared provider fixture. |
| P1 `kernelMutations.ts` | Approval challenge/decision and run-version writes | None | Changed nonce/version/result envelopes can strand a legitimate two-person approval or cause a UI to report an outdated action result. This is a control boundary, so preserve fail-closed runtime checks while adding shared fixtures. |
| P1 direct screen consumers (not counted as modules) | DeveloperStudio, RunDetail, EvidenceViewer | None beyond the separate discovery/storage/workspace slices | Run result, artifacts, artifact content, and run creation use screen-local response types or `any`. A response change can hide output, attach the wrong artifact, or let a success-shaped fallback look like verified evidence. UI-FB-03 separately remains pending component transition tests. |
| P2 `runApprovalObservation.ts` | App run list and approval queue | None | Missing or renamed run/approval fields can empty the queue or suppress actions. The adapter has runtime checks, but mocks do not share a backend-derived contract. |
| P2 `fabricControlApi.ts` | ResourceExplorer and PlacementSimulator | Discovery candidates; storage contribution and location lists | Pool capacity, placement preview, plans, nodes, and mutation responses remain handwritten. A changed candidate capacity/eligibility shape can show misleading placement choices or lose capacity context. |
| P2 `fabricObservation.ts` | Storage/model observation surfaces | Storage locations | Resolve, replica status, and model commitment remain handwritten. A shape drift can make a location appear unresolved, make replica state unknown, or omit the model commitment cue. |
| P2 `shardObservation.ts` | RunDetail distributed shard section | None | A renamed shard state/evidence field can render incomplete progress or omit stopped/evidence status. Runtime parent-run checks remain, but fixture/provider parity is absent. |
| P2 `nodeObservation.ts` | App node list, NodeList, NodeDetail, capacity surfaces | None | It accepts `Record<string, unknown>` and maps invalid measurements to unavailable/non-schedulable, which is fail-safe, but producer drift can silently erase telemetry and capacity from screens. |

`client.ts` is shared HTTP transport rather than an endpoint response adapter. In addition to the eight modules, screen-local endpoints include PlacementSimulator pool/candidate/preview reads, DeveloperStudio run/result/artifact/readiness calls, RunDetail result calls, EvidenceViewer results, WebTerminal ticket issuance, and Monaco run dispatch. Those paths remain visible follow-up scope rather than being silently counted as covered.

## Selection and implementation

Selected the workspace list plus execution-readiness response, the first ranked user flow. The list populates DeveloperStudio's workspace choice; readiness explains whether a run can proceed and who resolves each missing precondition. Shape drift can remove a user's workspace or change the visible execution gate.

- `ProjectWorkspacesResponse` now strictly models `projectId`, `workspaces`, and `count`; each row carries IDs, lifecycle status, node/tool selections, creation time, and allowed next transitions.
- `WorkspaceExecutionReadinessResponse` fixes the false/non-admission semantics as literals (`executable: false`, readiness `unknown`, admission required) and types the per-check remediation/input fields. The route uses `response_model_exclude_unset=True` to retain the existing distinction between absent optional fields and explicit null values.
- Both routes share exact JSON fixtures with FastAPI provider serialization tests and Vitest/Ajv tests. TypeScript consumers use generated models instead of their local workspace/readiness copies. Two additional response schemas are exported with the existing Pydantic schema inventory; the TypeScript generator checks all generated API response types together.
- Database-backed route logic was not exercised. Provider serialization was exercised in an isolated FastAPI app with service returns replaced by the shared fixtures; this validates serialization and schema binding, not database semantics or live HTTP deployment.

## Required rollback/mutation checks

Both contract directions were exercised on 2026-09-21. At 16:01:34 KST, a temporary required `contractProbe` field was added to `ProjectWorkspacesResponse`: provenance-wrapped `.venv/Scripts/python.exe -m pytest -q --tb=short tests/core/test_workspace_response_contract.py -k shared_workspace_fixture` exited 1 (1 failed, 1 passed, 10 deselected), and `tools/export_schemas.py --check` exited 1, naming `project-workspaces-response.schema.json` as stale. The model mutation was reverted. At 16:00:48 KST, `allowedNext` was temporarily removed from the shared project-workspaces fixture: the same Python selection exited 1 (1 failed, 1 passed, 10 deselected); Vitest `run tests/workspace-response-contract.test.ts` exited 1 as well. The fixture was restored. These are mutation observations, not positive pass counts.

Do not call browser acceptance from Vitest or offline provider serialization. The fixture mutation verifies the Python provider test and frontend consumer read the same repository fixture; it does not exercise a deployed backend.

## Provenance and verification

Initial environment and test diagnosis was run with the project interpreter and the provenance wrapper. The test's first collection error was caused by a missing `schemas` import in the new test path; the follow-up exposed the route module's missing schema import. Both were fixed before passing results. One initial frontend test attempt pointed one parent directory too shallow from `tests/fixtures`; corrected to the repository-root fixture. These were implementation/invocation issues, not passing test evidence.

Latest local check set ran from base SHA `512daf7924e4...` on branch `integration/all-agents-unified`, checkout `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`; the worktree was dirty with this contract slice and its records. Invocations used `tools/provenance.py --executor Codex`; Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6 and Node `C:/Program Files/nodejs/node.exe` v24.17.0; PostgreSQL DSN absent, Docker present. At 16:03:39 KST (run set completed by 16:03:51), provider pytest exited 0 (12 passed, 2 warnings); full Vitest exited 0 (36 files, 340 passed); schema export check exited 0 (28 schemas match); TypeScript response contract generator exited 0 (7 types match); `tsc -b`, `check_docs.py`, `check_ontology.py`, and Vite production build all exited 0. Prior focused Vitest was 2 files/29 passed. Before that, `sync_obsidian.py --check` reported 1402 managed/7 pending/0 conflicts; authorized `--apply` exported 7 files with all 1402 destination hashes matching. No DB integration, CI, browser acceptance, live HTTP, or independent review is claimed. The exact full SHA and clean-tree status are established only after this source is committed; these current checks ran on dirty source based on the stated SHA.

After the final workboard and map update, provenance-wrapped `check_docs.py` and `check_ontology.py` both exited 0 at 16:04:57 KST. The read-only Obsidian check at that point found 1402 managed files / 5 pending / 0 conflicts. The following authorized apply and paired post-check are recorded after execution below.

The authorized provenance-wrapped apply at 16:05:21 KST exported 5 updated pages with all 1402 destination hashes matching (exit 0); post-apply `--check` at 16:05:25 KST reported 1402 managed / 0 pending / 0 conflicts (exit 0).

Recording that result itself changed this History page: the final apply at 16:05:41 KST exported 1 page (all 1402 hashes match, exit 0), and the 16:05:46 paired check was 1402 managed / 0 pending / 0 conflicts (exit 0).

## Committed-source verification and handoff

Implementation and the map were committed as `e460296eaa4cc6da7349fe50cd0cf452ddaa31d3` on `agent/codex/workspace-response-contract-map` and pushed to `origin` at 16:06 KST. The post-commit commands were provenance-wrapped from the clean worktree at that exact SHA (Windows 11; Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6; Node `C:/Program Files/nodejs/node.exe` v24.17.0; `INV_TEST_ADMIN_DSN` absent). At 16:07:06 KST the workspace contract pytest passed 12 with 2 warnings and no skips; all Vitest passed 340 across 36 files; schema export (28), TS contract generation (7), `tsc -b`, `check_docs.py`, `check_ontology.py`, Vite production build, and `sync_obsidian.py --check` all exited 0. Sync state was 1402 managed / 0 pending / 0 conflicts. The source commit is locally verified and pushed; Claude independent fixed-SHA review, CI, PostgreSQL integration, deployed HTTP, and browser acceptance remain pending/not run. The reporting entry is appended after these checks and changes documentation only.

## Review and next actions

Owner Codex; independent reviewer Claude pending. The map covers eight functional shared adapter modules, plus separately listed screen-local API consumers; it is an inventory and priority proposal, not a claim that every endpoint shape is now covered. Next slices, by visible/control impact: approval review and kernel mutation responses; run-result/artifact responses (coordinate with Gemini UI-FB-03); dual-envelope project list; run/approval queues; placement/storage adjuncts; shard/node observations. PostgreSQL DSN absence leaves database-backed integration outside this verification. No CI, browser/operational acceptance, or independent review is claimed.
