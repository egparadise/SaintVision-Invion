---
doc_id: "INTEGRATION-TIP-VERIFICATION-20260921-CODEX"
title: "Integration tip verification audit"
version: "1.0.0"
status: "complete"
author: "Codex"
updated: "2026-09-21T14:14:13+09:00"
source_of_truth: "Git"
---

# Integration tip verification audit

## Scope and execution identity

All direct checks below ran in `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, branch `integration/all-agents-unified`, HEAD `cb505f6697beffe78a1cbdaee027f415003c55d3`, on Windows PowerShell, during 2026-09-21 14:07-14:12 KST. Python commands used `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (project Python 3.14). Frontend commands ran in `apps/web` with Node v24.17.0 and npm.

The full Python suite started at 14:10:07 KST and finished after 94.81 seconds. Results were captured from direct console output; no JUnit artifact was generated. No command was piped when capturing its exit code; PowerShell `$LASTEXITCODE` was printed immediately after each external command.

## Direct results on this integration tip

| Check | Command | Exit | Direct result |
| --- | --- | ---: | --- |
| Docs and links | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/check_docs.py` | 0 | Passed: 24 original hashes, 602 versioned documents, wiki links, 48 tasks, 12 outcomes. |
| Ontology | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/check_ontology.py` | 0 | RDF, term/equivalence checks, 48 mappings, SHACL and mirror passed. |
| Route coverage | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/route_coverage.py --served src/saintvision --served services/control-plane/src --client apps/web/src --json` | 1 | Static report has one unserved path, `/v1/workspaces`. This is the previously identified false positive: deployment nginx location/upstream text is counted as a client API call. The checker is static path-shape analysis, not live HTTP acceptance. Its regression suite separately passed 28 tests. |
| Route coverage tests | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q tests/test_route_coverage.py` | 0 | 28 passed. |
| Schema export | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/export_schemas.py --check` | 0 | 22 generated schemas match their source models. |
| Frontend contract types | `npm run contracts:check` in `apps/web` | 1, then 0 | First invocation could not resolve `json-schema-to-typescript` because this worktree had no installed frontend dependencies. After `npm ci` (exit 0; 127 packages installed, audit reported 0 vulnerabilities), rerun passed: discovery response TypeScript type matches the JSON Schema. The first failure was checkout setup, not a contract mismatch. |
| Obsidian sync check | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/sync_obsidian.py --check` | 0 | 1394 managed files, 1 pending export, 0 conflicts; read-only. No `--apply` was run. |
| Frontend suite | `npm test` in `apps/web` | 0 | Vitest: 34 files, 332 tests passed. |
| Python suite | `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q tests` | 0 | 1338 passed, 1315 skipped, 2 deselected, 0 failed, 94.81s. Project pytest configuration excludes `docker_host`; the two deselections are outside this run. |

## Python skips and limits

The 1315 skips are not passing tests. They include PostgreSQL cases gated by absent `INV_TEST_ADMIN_DSN`, explicit browser-smoke/approval opt-ins, Linux-only execution paths on this Windows host, and tool prerequisites not present in this worktree (the launcher-injection case checks for this checkout's `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, while tests were invoked with the root checkout's interpreter). Two image tests require an explicitly pinned local candidate image. The individual pytest skip reasons were emitted by `-ra`; no live PostgreSQL, browser acceptance, Docker-host lane, or physical-device acceptance is claimed here.

## Route result interpretation

The CLI exit 1 is a current direct observation, not a new backend outage finding. `/v1/workspaces` is sourced from nginx deployment configuration text in `deploymentEngine.ts`; the frontend makes workspace subroute calls, whose backend routes are present. `tests/test_route_coverage.py` passes 28 cases. The static scanner limitation and the test result must remain separate from live HTTP/browser acceptance.

## Prior reports versus this audit

Earlier pass reports from other branches or snapshots are not counted as current-tip evidence. This audit directly ran the named checks on `cb505f6`. `check_docs.py` failed on the integration snapshot after `5c7ce9d` because four wiki links pointed to memory-only targets; `b728ad0` changed those references to explicit `memory:` slugs and restored the check. On `cb505f6`, `check_docs.py` directly passed. Separately, `b728ad0` introduced a question-mark-corrupted progress summary sentence; its file stem and wikilink were intact. This audit records and fixes that prose corruption. The route coverage CLI remains a known static false positive as described above.

## Reporting rule proposed

Every verification claim should identify: (1) full commit SHA and branch, (2) checkout/worktree path, (3) exact command and working directory, (4) interpreter/runtime version, (5) KST start and finish time, (6) direct exit code, (7) pass/fail/skip/deselected counts with skip reasons, (8) artifact path where applicable, and (9) whether the executor and reviewer are the same person. A report from another branch, an earlier SHA, or a different worktree must be labeled as such. After a relevant change, rerun the affected checks at the resulting SHA before calling that SHA verified.

## Integration progress-board text correction

`git blame` attributes the garbled first DSN audit summary sentence in `INDEX-PROGRESS-001` to `b728ad0`; the actual file stem and wikilink target were intact. The sentence itself contained literal question marks where non-ASCII text had been lost. This is consistent with Windows PowerShell native-pipeline encoding damage, but the exact write command is not retained, so that causal detail is an inference. `check_docs.py` passed despite the damaged prose because it validates links and document structure, not arbitrary sentence readability. The progress sentence is replaced with ASCII text and a stable link to this record.
