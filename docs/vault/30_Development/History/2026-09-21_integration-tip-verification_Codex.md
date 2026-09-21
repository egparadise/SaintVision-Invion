---
doc_id: "INTEGRATION-TIP-VERIFICATION-20260921-CODEX"
title: "Integration tip verification audit"
version: "1.1.0"
status: "complete"
author: "Codex"
updated: "2026-09-21T14:40:00+09:00"
source_of_truth: "Git"
---

# Integration tip verification audit

## Scope and execution identity

All direct checks below ran in `C:/Project/SaintVision-Invion/.worktrees/codex-public-dsn-integration`, branch `integration/all-agents-unified`, HEAD `cb505f6697beffe78a1cbdaee027f415003c55d3`, on Windows PowerShell, during 2026-09-21 14:07-14:12 KST. Python commands used `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` (project Python 3.14). Frontend commands ran in `apps/web` with Node v24.17.0 and npm.

The first full Python suite started at 14:10:07 KST and finished after 94.81 seconds. That run's result was captured from direct console output without a JUnit artifact. No command was piped when capturing its exit code; PowerShell `$LASTEXITCODE` was printed immediately after each external command.

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

The 1315 skips are not passing tests. The first run reported the individual pytest reasons through `-ra`; no live PostgreSQL, browser acceptance, Docker-host lane, or physical-device acceptance is claimed.

## Skip distribution capture and independent rerun

To preserve the skip distribution, the suite was rerun at 2026-09-21 14:26:53-14:28:19 KST with a JUnit artifact. At test start, HEAD was `b2c20808142d55e3cd79237bf051d6e2891aecbd` (Claude's documentation-only independent audit had fast-forwarded after code tip `cb505f6`); `git status --porcelain` showed four modified documentation files and no source/test changes. The `.work` output is ignored. Command from the worktree root: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q tests --junitxml=.work/pytest-skip-distribution-cb505f6.xml`; direct exit 0, 85.16s. The XML SHA-256 is `7fa83def326155e3ac24aeee57d95fadf561025754daa9e21a7ca12383026380`.

The JUnit suite recorded 2653 collected cases: 1338 passed, 1315 skipped, 0 failed, 0 errors. Two cases were deselected by the configured `not docker_host` marker and are not part of that XML count. Skip distribution: **1046 PostgreSQL DSN gated** (587 require a disposable PostgreSQL 16+ DSN and 459 report `INV_TEST_ADMIN_DSN` absent); **225 Linux-only**; **34 Docker/image prerequisites or explicit opt-ins** (13 local PostgreSQL image, 12 owned storage installer opt-in, 7 built-image opt-in, 2 pinned local candidate image); **7 browser opt-ins** (4 browser test, 2 browser acceptance, 1 browser smoke); **3 other host prerequisites** (launcher shim's worktree-local venv absent, Antigravity absent, Windows symlink privilege absent). These are skip reasons, not test passes.

Claude's separate clean worktree rerun at the code SHA `cb505f6697beffe78a1cbdaee027f415003c55d3` independently reported the same command's 1338/1315/2/0 result. See [[2026-09-21_통합tip검사_독립대조_Claude]]. The 423-skip Claude batch result is a different run selection/environment and is not comparable to the full Windows suite; same code SHA alone does not fix the execution set.

## Route result interpretation

The CLI exit 1 is a current direct observation, not a new backend outage finding. `/v1/workspaces` is sourced from nginx deployment configuration text in `deploymentEngine.ts`; the frontend makes workspace subroute calls, whose backend routes are present. `tests/test_route_coverage.py` passes 28 cases. The static scanner limitation and the test result must remain separate from live HTTP/browser acceptance.

## Prior reports versus this audit

Earlier pass reports from other branches or snapshots are not counted as current-tip evidence. This audit directly ran the named checks on `cb505f6`. `check_docs.py` failed on the integration snapshot after `5c7ce9d` because four wiki links pointed to memory-only targets; `b728ad0` changed those references to explicit `memory:` slugs and restored the check. On `cb505f6`, `check_docs.py` directly passed. Separately, `b728ad0` introduced a question-mark-corrupted progress summary sentence; its file stem and wikilink were intact. This audit records and fixes that prose corruption. The route coverage CLI remains a known static false positive as described above.

## Reporting rule proposed

The original nine-item proposal was expanded after Claude's independent review. The accepted rule is now in [[Agent 연속 실행과 최종 보고 정책]] v1.1.0: full SHA/branch/worktree, measured clean-or-dirty status (`git status --porcelain`, plus canonical diff checks where EOL can mislead), exact command/cwd, absolute interpreter/runtime and version, environment fingerprint and omitted lanes, KST start/end, direct unpiped exit code, separate pass/fail/error/skip/deselected totals with skip distribution, artifact path/hash, and executor/reviewer identity. Reports from another branch/SHA/worktree remain explicitly attributed; affected checks rerun at the resulting final SHA.

## Documentation closeout checks

After the final six documentation paths were edited at HEAD `b2c20808142d55e3cd79237bf051d6e2891aecbd`, the project venv Python ran `tools/check_docs.py` (exit 0, 604 versioned documents), `tools/check_ontology.py` (exit 0), `tools/sync_obsidian.py --check` (exit 0, 1396 managed/6 pending/0 conflicts), and `git diff --check` (exit 0). The six pending document exports were then applied; the sync tool reported every destination hash matched. A following `--check` returned 1396 managed/0 pending/0 conflicts, exit 0. These document checks ran on a dirty-doc worktree; the only changed tracked paths were the six Markdown records, and the Python/Vitest product results above remain attributed to the earlier clean code SHA and the separately described dirty-doc JUnit rerun.

The origin integration branch advanced by Claude's provenance utility and rule commits `89c6bc3` and `5c1e9ef`; `git merge --ff-only` brought this worktree to `5c1e9ef2e13f20262feeb8323fd7c870d81dfbb9`. At 2026-09-21 14:36 KST, `tools/provenance.py --json` directly reported this SHA in sync with origin and a dirty documentation-only worktree. The tool's wrap mode was exercised. A first wrapped command used bare `python tools/check_ontology.py`, which failed because that system interpreter lacked `rdflib`; this was a caller interpreter error. Repeating through the wrapper with the absolute project interpreter `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` returned exit 0 and ontology PASS. The correction is in the daily ledger. Post-merge `check_docs.py` passed with 605 versioned documents. A post-merge sync check reported 1397 managed/1 pending/0 conflicts; the remaining pending record came from the newly merged Claude provenance doc and is included in the final export. Full Python/Vitest suites were not rerun at `5c1e9ef`; their results remain directly attributed to `cb505f6`.

The integration branch then advanced once more to `03e0c6117ae90d16bee94514345312eb7f4afecc` with Claude's documentation-only main-checkout sync convention. It separates the main checkout from agent worktrees, recommends reference-only use, and documents a tripwire/guarded automation; no product code changed. Final validators were rerun at this SHA. The full Python/Vitest regression was not rerun at `03e0c61`; it remains attributed to `cb505f6`.

## Integration progress-board text correction

`git blame` attributes the garbled first DSN audit summary sentence in `INDEX-PROGRESS-001` to `b728ad0`; the actual file stem and wikilink target were intact. The sentence itself contained literal question marks where non-ASCII text had been lost. This is consistent with Windows PowerShell native-pipeline encoding damage, but the exact write command is not retained, so that causal detail is an inference. `check_docs.py` passed despite the damaged prose because it validates links and document structure, not arbitrary sentence readability. The progress sentence is replaced with ASCII text and a stable link to this record.
