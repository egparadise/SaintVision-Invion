---
doc_id: "HIST-20261104-CARD303B-F5-CODEX"
title: "Card 303b F5 인증서 관측의 표시 신선도와 만료 경계"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-11-04T15:14:00+09:00"
updated: "2026-11-04T15:14:00+09:00"
source_of_truth: "Git"
---

# Card 303b F5 인증서 관측의 표시 신선도와 만료 경계

- Task `task_7e08af39fe78`, dispatch `ctx_bb8984a92eb7`; F5 owner Codex, independent reviewer Claude pending, coordinator Codex.
- Checkout `D:/Project/SaintVisionI-Invion/supervision-gemini-20261104`, existing successor PR #406, branch `agent/gemini/c303b-frontend-evidence`, base `789999d821702b8f2152f2721ace1fb4c2ba928c`. Delivery SHA is the commit containing this page and is sent exactly in the worker receipt.
- Scope: canonical certificate observation retention, displayed freshness/expiry, per-node certificate provenance, renewal wording, focused fake-clock App tests. No unrelated root-base merge, shared-board edit, hosted-CI dispatch, or Obsidian apply is included, per coordinator message `msg_65c50afb70c4`.
- Read baseline: `INDEX-PROGRESS-001` v1.0.380, `WORKBOARD-CODEX-001` v1.0.342, `INDEX-VIRTUAL-COMPUTER-001` v1.0.0, `ROADMAP-VIRTUAL-COMPUTER-001` v1.0.0, `GOV-CONTINUOUS-001` v1.1.0, `GUIDE-001` v1.1.0, `ADR-INDEX-001` v1.37.0, role/Git/continuity governance and task registry v1.0.1. Applied repository skills: agent-delivery v1.1.0, core-reliability v1.0.0, frontend-delivery v1.0.0.
- Attribution: Gemini owns the prior F1–F4/canonical caller implementation at the base SHA and supplied partial ResourceExplorer wording/API helper edits. The preserved starting patch `.work/gemini-f5-preserved-before-provider-retry.patch` directly hashes to SHA256 `3fa23a4dadca0b48e57021cc94e2dc5323a70a46e3504109719ac40d9feb4c99`; Codex completed F5 and its tests. Prior history remains [[2026-11-04_13-22-00_KST_Card303b_Review_Remediation_and_Caller_Wiring_Gemini]].

## Work and invariants

App retains the entire validated project certificate observation, including project identity and `observedAt`, rather than storing only `trust`. Displayed trust is derived at the current time. A separate boundary timer triggers at the next renewal-window, leaf-expiry, or verifier freshness boundary even when all 5-second refresh requests remain unresolved. Exactly 60 seconds remains accepted, matching the existing verifier; the next millisecond becomes visibly unknown. Poll starts retain the last fresh observation and cause no healthy/unknown flicker.

The canonical validator body is unchanged, including its microsecond comparisons and fail-closed schema/project/summary checks. Display derivation also retains microsecond ordering, rounds timer boundaries to the first applicable browser millisecond, and does not move backwards before the validated observation time. Existing session, scope, and request guards still fence responses. Project changes and authentication teardown clear the stored observation.

Per-node certificate timestamps are projected exclusively from a current canonical observation. Missing, rejected, or stale observations clear these values to `undefined`/미확인; an explicit validated `null` remains distinct. NodePage fallback certificate fields cannot survive a failed observation. The renewal banner says `인증서 갱신 창 (갱신 필요)` because global scheduler registration is unobserved.

## Direct local evidence

Evidence environment: Windows PowerShell, Node v24.10.0, npm 11.6.1, Python 3.10.11, Vitest 4.1.11/happy-dom, Vite 6.4.5. Direct console execution on the enumerated dirty candidate above, 2026-11-04 KST, with each native exit captured immediately before proceeding. No skipped cases are counted as passes.

| Command | Direct result |
|---|---|
| `npm --prefix apps/web test -- tests/app-node-certificate-freshness.test.tsx tests/node-certificate-observation-contract.test.ts tests/auth-app-oidc-integration.test.tsx tests/node-cert-trust-expiry.test.tsx` | 4 files, 62 passed; 0 failed/skipped; exit 0; started 15:11:55 KST |
| `npm --prefix apps/web test` | 102 files, 1217 passed; 0 failed/skipped; exit 0; started 15:12:21 KST, 25.00 seconds |
| `npm --prefix apps/web run lint` | 0 warnings/errors; exit 0 |
| `npm --prefix apps/web run contracts:check` | 41 API response types match schema; exit 0 |
| `npm --prefix apps/web run build` | TypeScript and production Vite build pass; 297 modules; exit 0 |
| `python tools/check_frontend_integrity.py` with `PYTHONUTF8=1` | 94 production files, 9 rules, 0 violations; exit 0 |
| `python tools/check_contract_bindings.py` | 57 referenced fixtures, 21 bound types, 14 replay guards; exit 0; type coverage does not prove every serving site |
| `python -m pytest tests/test_route_coverage.py` | 41 passed; 0 failed/skipped; exit 0 |
| `python tools/check_docs.py` | 24 original hashes, 1185 versioned documents, links and registry pass; exit 0 |
| `python tools/check_ontology.py` | RDF/SHACL, 48 task mappings, 4 rejected invalid fixtures and 4 queries pass; exit 0 |
| `python tools/sync_obsidian.py --check` | 2093 managed files, 13 pending exports, 0 conflicts, no writes; exit 0 |
| `git diff --check` | exit 0 |

The new App test file contains eight cases: pending node refresh, pending certificate refresh, precise expiry between polls, renewal-window boundary, rejected observation, missing-item observation, A→B→A project late response, and same-project reauthentication late response. The last two resolve the earlier request with a newly fresh timestamp so freshness rejection alone cannot conceal a missing session/scope fence. Tests exercise the actual canonical adapter, App, DesktopShell and ResourceExplorer badge/node output. They also assert no unvalidated 2099 NodePage certificate reaches the display.

Full-suite logs include existing localhost HTTP 500/ECONNRESET and happy-dom teardown AbortError diagnostics; these are not actual API/browser acceptance evidence. The production build reports its existing large-chunk warning (1295.47 kB main bundle). Neither diagnostic changed the recorded successful process exits.

## Delivery and next owner

Implementation, local frontend verification and documentation/ontology pre-push gates are complete. Source-branch push is recorded in the final worker receipt. CI and independent review remain pending; no operational acceptance was performed. The coordinator owns final same-SHA hosted CI, integration and shared-board/Obsidian reporting (13 pending exports, no worker apply), and Claude owns independent review of the exact corrected source head. First next action: inspect the F5 diff and fake-clock cases at that head, then integrate the owned successor PR #406 after its required gates.
