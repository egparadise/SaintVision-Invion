---
doc_id: "DISCOVERY-CANDIDATES-RESPONSE-CONTRACT-20260921-CODEX"
title: "Discovery candidates provider-consumer response contract first slice"
version: "1.0.4"
status: "review"
author: "Codex"
reviewer: "Claude pending"
base_commit: "a39fc13ed0320a26869fa424b55fc224d51f3fe2"
implementation_commit: "8532f705ecd2a53b0688f6bada6895b1efe403d5"
branch: "agent/codex/discovery-candidates-contract"
updated: "2026-09-21T13:04:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["api-contract", "discovery", "json-schema", "typescript", "verification-boundary"]
---

# Discovery candidates provider-consumer response contract first slice

## Scope and owner

First slice is only `GET /v1/discovery/candidates`. Owner: Codex (backend/API contract and cross-language contract gate); independent reviewer: Claude pending. Gemini remains owner of UI behavior. This change supplies the API wire contract and its shared fixture, not UI-FB-03 behavior or browser acceptance.

The source checkout at implementation start was `f6841b6b912035f6ed753acf8ddc8704817f2d56`. Before branch publication, Codex fetched origin and found integration advanced to `a39fc13ed0320a26869fa424b55fc224d51f3fe2` with two commits containing only JUnit/manifest/history evidence and no overlapping source paths. The task branch `agent/codex/discovery-candidates-contract` was created from `a39fc13`; frontend source and tests were unchanged from the already-tested source snapshot, and the final Python contract/route suite was rerun on the new branch base.

Plan and pass/fail self-check were written before implementation in the task conversation: begin with one endpoint; need no live backend/DB; make model/schema/generated type/fixture drift fail in both directions; keep route coverage path-only and avoid a second payload checker there.

## Implemented contract flow

1. `DiscoveryCandidateResponse` and `DiscoveryCandidatesResponse` are strict Pydantic wire models in `src/saintvision/api/schemas.py`. Extra fields are forbidden. Candidate wire state is `candidate` and `verified` is literal `false`; fields are explicitly named as claims, with source IP and observation timestamps represented separately.
2. `/v1/discovery/candidates` declares the response model. The provider service includes its current candidate `state`; FastAPI validates and serializes the response against the model.
3. `tools/export_schemas.py` produces the JSON Schema in `contracts/`. Existing model/schema CI drift checking remains authoritative for the provider contract.
4. `apps/web/scripts/discovery-contracts.mjs` generates the frontend TypeScript wire type from `contracts/discovery-candidates-response.schema.json`; `npm run contracts:check` fails if the checked-in generated type differs. `fabricControlApi.ts` consumes the generated type rather than maintaining an independent wire interface.
5. One checked-in JSON fixture under `contracts/fixtures/` is read by the backend contract test and frontend Vitest mock. Pydantic exact-key/strict checks and Ajv JSON Schema validation reject fixture drift. The UI's post-admission states are a separate, wider UI type; they are not incorrectly added to the GET wire contract.
6. `tests/test_route_coverage.py` no longer inspects response fields through source-string matching. `route_coverage.py` continues to validate path shapes only. Method and payload shape are the responsibility of typed endpoint tests and the schema/fixture gates above.

## Pass/fail and drift behavior

- Pydantic fixture tests check exact top-level and item key sets and validate the shared fixture. Missing or extra fields, `verified: true`, and non-candidate wire state are rejected.
- A database-free FastAPI `TestClient` mounts the real pools router, overrides auth/session/time dependencies, and substitutes only the discovery service result. It asserts the actual HTTP status and serialized body and exercises both `includeStale` values. This is provider routing/serialization evidence, not a live service/backend test.
- Frontend test validates the exact shared fixture against the generated response JSON Schema. The adapter mock now uses that fixture.
- The backend schema exporter checks Pydantic model → checked-in schema drift. The frontend type generator check checks schema → generated TypeScript drift. Shared fixture validation checks model/schema ↔ mock payload drift. Each direction has a concrete failure path rather than matching hand-written strings.
- Route coverage stays independent: it catches route path changes or unserved paths but does not duplicate method/payload assertions.

## Commands and results (Codex execution, KST 12:49–12:52)

Python interpreter for every Python command below: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`.

| Command | Result |
|---|---|
| `.venv\Scripts\python.exe tools\export_schemas.py` | exit 0; wrote 22 schema files, including the new candidate response schemas |
| `.venv\Scripts\python.exe tools\export_schemas.py --check` | exit 0; all 22 contract schemas match the Pydantic models |
| `.venv\Scripts\python.exe -m pytest -q tests/core/test_discovery_response_contract.py` | exit 0; 8 passed |
| `.venv\Scripts\python.exe -m pytest -q tests/core/test_discovery_response_contract.py tests/test_route_coverage.py` | exit 0; 36 passed |
| `npm run contracts:generate` then `npm run contracts:check` in `apps/web` | exit 0; generated type written and schema/type match |
| `npm test -- --run tests/discovery-candidates-contract.test.ts tests/fabric-control-plane.test.tsx` in `apps/web` | exit 0; 2 files, 28 passed |
| `npm run build` in `apps/web` | exit 0; TypeScript check and Vite production build completed (3.46 s) |
| Generated TypeScript appended-comment mutation + `npm run contracts:check` | expected exit 1; stale generated type rejected; original bytes restored |
| Shared fixture with required `state` removed + focused Vitest | expected exit 1; Ajv reports missing `state`; original bytes restored |
| Schema adds a required synthetic field without regenerating type/fixture | expected exit 1 from both `npm run contracts:check` and the Ajv fixture test; schema bytes restored |

The fixture tests also include explicit negative model-validation cases for missing/extra keys, `verified: true`, and wrong state. One initial fixture mutation probe used an unmatched newline replacement and changed no bytes; it was discarded and rerun using a verified regex replacement. The successful mutation result above is the latter run.

Final local gates at KST 12:54–12:58: `npm test` in `apps/web` → 34 files / 332 passed / exit 0; `npm run contracts:check` → exit 0; `npm run build` → TypeScript plus Vite production build / exit 0 (3.32 s); `.venv\Scripts\python.exe tools/check_docs.py` → exit 0 (595 versioned documents, 48 tasks); `.venv\Scripts\python.exe tools/check_ontology.py` → exit 0 (48 task mappings); `git diff --check` → exit 0. Initial `tools/sync_obsidian.py --check` → exit 0, 1374 managed / 8 pending / 0 conflicts / no writes. Codex then ran `tools/sync_obsidian.py --apply` at KST 12:55: exit 0, 8 files exported and all 1374 destination hashes matched. A post-apply `--check` at KST 12:55 → exit 0, 1374 managed / 0 pending / 0 conflicts. Later test precision and progress-document corrections were exported in follow-up batches; final read-only `--check` remained 1374 / 0 / 0. The earlier user-applied 6-file set is a separate preceding sync event.

The first frontend build after replacing the hand-written candidate type found an important type boundary: backend GET data can only have `state: candidate`, while the UI locally uses `admitted` and `declined` after operator actions. The code now keeps a narrow generated API response and a separate UI state type; the final build passes. This prevented incorrectly widening the backend wire contract to match local UI transitions.

## Not established

- No GitHub Actions job was run; frontend CI is configured to run the generated-type check when `contracts/**` changes, but billing/CI availability was not tested here.
- No PostgreSQL, live API backend, browser, desktop lane, or physical node was used. The FastAPI test isolates dependencies and validates provider serialization only.
- This does not approve UI-FB-03. Gemini still owns the required component tests: 401/403/5xx/malformed JSON/network failure must not call artifacts and must expose error with no verified artifact; only route-only 404 can fallback and it must remain UNVERIFIED. Browser acceptance is separate.
- The npm install output reported 2 moderate audit findings. They were not investigated or auto-fixed in this scoped work.

## User-reported Obsidian final status

The user reports both checkouts at the same `b5ea2a5` snapshot returned 1373 managed / 6 pending / 0 conflicts. User then applied the 6 pending files, exit 0, with all 1373 destination hashes matching. Post-apply check returned 1373 / 0 / 0 and the vault had 1,384 files at that point. Earlier 6-vs-5 pending checks were intermediate observations over different document snapshots, not evidence of a remaining state split. The latest user execution's precise interpreter and wall-clock time were not supplied, so they are intentionally not invented.

After fetching remote tip `a39fc13`, 14 additional Claude regression evidence files were present in `docs/vault`; together with four changed Codex documents, `--check` reported 1388 managed / 18 pending / 0 conflicts. Codex ran `tools/sync_obsidian.py --apply` (exit 0, 18 files exported, all 1388 destination hashes matched), then `--check` (exit 0, 1388 managed / 0 pending / 0 conflicts). A separate unfiltered recursive file count of the vault returned 1,399. This filesystem count includes files outside the sync tool's managed set and is not directly interchangeable with its 1,388 managed count.

## Next handoff

- Implementation is committed as `8532f705ecd2a53b0688f6bada6895b1efe403d5` and pushed to `origin/agent/codex/discovery-candidates-contract`.
- Claude: independently review this fixed code diff and focused evidence; do not treat this as UI or live-backend acceptance.
- Gemini: continue UI-FB-03 component error-to-render and artifact fallback regressions under its own owner contract.
- Codex: add another endpoint only after review of this first slice; retain the route-coverage/payload-contract separation.
