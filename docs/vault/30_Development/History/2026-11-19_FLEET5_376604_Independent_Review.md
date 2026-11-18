---
doc_id: "HISTORY-FLEET5-376604-INDEPENDENT-REVIEW"
title: "Independent review of the interrupted A1 custody decision"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T03:13:42+09:00"
source_of_truth: "Git"
---

## Disposition

Accept R2 revision 3 as a proposed reference contract. The high-priority ab22abd1 custody finding is closed at 37660421c34e4bea43171cd5a0ac77c7559f52a7. Claude authored the change on agent/claude/fleet5-r3-custody-hold-20261119. Codex independently reviewed that exact base in agent/codex/task_d2d08f102f72 under dispatch ctx_58d0ad80a1eb. The reviewed contract is version 1.2.0. Baseline boards are INDEX-PROGRESS-001 1.0.544 and WORKBOARD-CODEX-001 1.0.505.

## Decision evidence

| Interrupted A1 observation | Independent result |
|---|---|
| Writer fence missing, transferred, wrong generation or unreadable, stale or future timestamp | With available DB and matching epoch, all eight faults across three custody states yield HOLD_WRITER_FENCE. The executor refuses to resume. The freshness upper bound is inclusive. |
| Held fence, NO_NEW_KEY, read-back log with zero keys and zero signatures, no recorded output | Both UNKNOWN and FAILED_BEFORE_MUTATION yield ABANDON_BEFORE_NEW_TRUST. Evaluation accepts the decision and the executor refuses resume. |
| Absent log, recorded key, signed Node or CP leaf, or missing or inconclusive custody | HOLD_CUSTODY_UNRESOLVED. The original one-key, two-signature contradiction is positive fixture p50 for HOLD. A claim of abandonment in r62 yields AR-RECOVERY-MISMATCH. |
| Clean zero log with earlier A1 output | Each of 19 fields individually forces HOLD. These comprise three CA fields, two CP fields, two bundle fields and three fields for each of four members. |

Source inspected in tools/check_fleet5_authority_replacement_r2.py at lines 365?378, 1124?1164 and 1190?1215. The same output inventory drives completeness and absence. Existing tests at tests/core/test_fleet5_authority_replacement_r2.py lines 742?790 and 828?915 exercise decision, evaluation and executor behavior.

## R1 reachability and impact

The R1 checker remains callable by its explicit CLI, v1 fixture generator and v1 test suite. An exact-tree reference search across tracked code and workflows found no service, deployed executor, runtime version selector or R2 fallback to R1. Pytest collects the two proposal suites independently. R1 lines 283?287 still permit interrupted abandonment on NO_NEW_KEY alone. A future caller treating the v1 verdict as operational authorization could discard prior issuance evidence. Root must bind any future recovery executor to the reviewed R2 contract and enforce its fence at commit. This review covers repository callers only.

## Reproduction and handoff

Windows, Python 3.10.11, isolated checkout. Evidence/fleet5-376604-independent-review/local-gates.json records each command, KST time and exit. All 14 gates exited zero, including 560 tests, 45 R1 fixtures/instances, 113 R2 fixtures/instances and both generator drift checks. The initial pytest invocations used an unexpanded wildcard and then a nonexistent R1 filename, collected zero cases and exited nonzero. The recorded run uses the two tracked filenames. Obsidian check found 20 pending exports and zero conflicts. Root owns integration, operational acceptance and selective report consolidation. No fleet connection, deployment, push or vault export was performed.

The repository's revision 3 mutation harness was independently rerun against the isolated checkout. All six mutations produced an assertion failure in the existing suite. The restored checker SHA-256 matched the original, 056e4d819e93f2f998120751043b131d7e2723651d7bffca21c11b5759a71301. See mutations.json in the evidence directory.

Read-only hosted results at 2026-11-19T03:14:49.4322009+09:00 confirm four successful runs on the exact candidate SHA. Core 44361790662, Backend 44361797503, Docs 44361783543 and Portal Login Journey Harness 44361729512 are recorded with their URLs in hosted-ci.json.
