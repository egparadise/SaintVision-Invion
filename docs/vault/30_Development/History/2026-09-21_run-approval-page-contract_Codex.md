# Run/approval page response contract slice — Codex

## Scope and decision

Bound the `runApprovalObservation.ts` run-list and approval-list response envelopes to canonical contracts and shared fixtures. These endpoints feed visible run and pending-approval queues; an unannounced wire-shape change could hide a run or approval without an adapter contract failure.

Owner: Codex. Independent reviewer: Claude pending. Base: integration `686eecff924a5527e537c26228e2db87c00106ff`. Branch: `agent/codex/run-approval-observation-contract`.

## Change

- Added canonical `ControlRunPage` to `contracts/v1alpha1/core.schema.json`, requiring `items` and `nextCursor` and validating rows as `ControlRunView`.
- Reused canonical `ApprovalPage`; both `Control.list_runs` and `Control.list_approvals` validate provider output before returning it.
- Regenerated Pydantic, TypeScript, Go, and node-agent schema artifacts from the canonical core schema.
- Added shared run-page and approval-page fixtures. Python provider tests validate each fixture against the runtime schema and generated model, compare provider serialization to the same fixture, and reject a missing cursor. Frontend tests read those exact files, validate them against the canonical schema, pass them through the adapters, and reject malformed envelopes.
- Updated older adapter mocks to include the now-required `nextCursor` field. The first full Vitest run exposed three stale mocks; they were corrected, then the full suite passed.

## Provenance and verification

Checks ran on dirty implementation/docs source based on the stated integration SHA; no positive result below is represented as a clean committed-SHA run. Commands were wrapped with `tools/provenance.py --executor Codex -- <command>` (direct exit code, no shell pipeline). Python used `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6; Node was v24.17.0. PostgreSQL DSN was absent, Docker and Node were present. The task worktree has a `node_modules` junction to the main checkout for local frontend tests; it is ignored and not a repository change. The following fixed-base evidence was collected at 17:36 KST on 2026-09-21, Windows 11, branch `agent/codex/run-approval-observation-contract`, HEAD `686eecff924a5527e537c26228e2db87c00106ff`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-run-approval-observation-contract`, `git status --porcelain` dirty and `git diff --quiet HEAD` false. Executor: Codex.

- At 17:36:06 KST, `.venv/Scripts/python.exe -m pytest -q tests/core/test_run_approval_observation_contract.py`: 7 passed, 0 skipped, 0 failed (exit 0).
- At 17:36:35 KST, from `apps/web`, `node node_modules/vitest/vitest.mjs run`: 41 files / 381 passed, 0 failed (exit 0); `node node_modules/typescript/bin/tsc -b`: exit 0; Vite build: exit 0, 11.65 seconds, JS bundle 618.67 kB.
- At 17:36:06 KST, `tools/export_schemas.py --check`: 32 schemas current (exit 0); `node apps/web/scripts/api-response-contracts.mjs --check`: 9 response types current (exit 0); `tools/generate_contracts.py`: generated Python, TypeScript, Go and packaged validation schema (exit 0).
- At 17:36:06 KST, `tools/check_docs.py`: 614 versioned documents, 48 tasks, 12 outcomes (exit 0); `tools/check_ontology.py`: RDF/SHACL and four rejected invalid fixtures passed (exit 0).
- At 17:36:06 KST, the read-only `tools/sync_obsidian.py --check` reported 1407 managed files / 5 pending exports / 0 conflicts (exit 0). This is a pre-final-doc snapshot; the paired final sync result follows in the completion entry.
- The Core workflow YAML was structurally inspected on integration-derived content and has six intended ignored paths, including both image-opt-in test files.
- Fixture negative control: removing `nextCursor` made backend pytest and frontend Vitest fail; original fixture bytes were restored.
- Schema negative control: temporarily removing `ControlRunPage.required.nextCursor` and regenerating changed the Pydantic, TypeScript, Go, packaged schema outputs; all snapshots were restored and generation rerun.
- Initial PowerShell invocations that used `.venv\Scripts\python.exe` as a bare command failed before launching the checker (shell exit 1); the corrected absolute-path provenance invocations above are the test evidence. One Vitest and `tsc` attempt from the worktree root also failed to resolve app-local `node_modules`; rerunning from `apps/web` passed. These invocation failures are recorded as environment/cwd errors, not product test failures.

No PostgreSQL-backed integration, hosted Actions, live HTTP, browser acceptance, or Go compilation is claimed. Go was not available. The provider contract test uses an in-memory fake database and verifies serialization/validation, not SQL against PostgreSQL.

## Remaining boundary

The run/approval list page envelope is now bound. Claude's incoming `5914f04` independently adds canonical backend schema/fixtures for run-result and artifact-list responses; frontend-generated types and shared-fixture tests remain Gemini's pending handoff, and artifact-content is still unbound. Next after Claude fixed-SHA review: placement preview/pool/mutation, selected by user-visible control impact. Storage resolve/replica/model, shard and node observations also remain. CI billing, PostgreSQL integration, and browser/operational acceptance remain external gates.

## Rebased fixed-SHA verification

The code commit `e7fc7a8` and docs commit `7c3b1d3` were rebased onto Claude's integration commit `5914f04`, which adds run-result/artifact provider fixtures. Final task HEAD is `7c3b1d30374761f663765574fc5ef06f24a2c6ea`, branch `agent/codex/run-approval-observation-contract`, clean worktree `C:/Project/SaintVision-Invion/.worktrees/codex-run-approval-observation-contract`. Provenance-wrapped checks at 17:42:43 KST on 2026-09-21 (Windows 11; Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6; Node v24.17.0; PostgreSQL DSN absent; Docker present; Go absent; executor Codex) passed: run/approval provider pytest 7, run-result provider pytest 4, schema export 32, frontend API response type check 9, full Vitest 41 files/381 tests, `tsc -b`, `check_docs.py` (615 versioned documents), `check_ontology.py`, and core contract generation. All direct exit codes were 0. Re-running core contract generation changed only a generated file's working-copy line endings; `git diff --quiet HEAD` confirmed no content change and the committed bytes were restored before this clean fixed-SHA verification.

At the same SHA, read-only Obsidian check at 17:42:43 reported 1408 managed / 2 pending / 0 conflicts. The final committed docs update is synchronized in the paired apply/check recorded below. CI, PostgreSQL integration, live HTTP, browser acceptance, and Go compilation remain unverified.

After the workboard/map updates, `check_docs.py` and `check_ontology.py` passed at 17:45:16 KST. The authorized sync at 17:45:23 exported 6 pages and matched all 1408 destination hashes; paired read-only check at 17:45:28 was 1408 managed / 0 pending / 0 conflicts, exit 0. This final evidence append is synchronized in the next paired update.

The final one-page correction was applied at 17:46:05 (all 1408 destination hashes matched), with paired `--check` at 17:46:09 reporting 1408 managed / 0 pending / 0 conflicts, exit 0. This sentence is synchronized in the next paired update.
