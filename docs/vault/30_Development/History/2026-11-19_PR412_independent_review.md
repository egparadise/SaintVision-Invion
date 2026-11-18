---
doc_id: "REVIEW-PR412-20261119"
title: "Independent unified recovery candidate review"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T04:38:33+09:00"
source_of_truth: "Git"
---

# PR 412 independent fixture review

Task task_318884aec93e. Reviewer Codex, correction owner PR 412 author, integration owner coordinator. Reviewed d35f28f59270ffd17e993cffbdff7bb9d87d8024 against 59f0a3c2ff41ba1ae99a38515a2cdc65b2144067 in a dedicated Windows worktree. Tracking baseline INDEX-PROGRESS-001 1.0.389 and WORKBOARD-CODEX-001 1.0.350.

**Request changes on the CX01 regression guard.** In tests/test_core_workflow_cx01.py the two artifact-name searches match substrings in raw YAML. Four independent temporary workflow mutations run through the actual test function rejected a rename and duplicate but accepted both a commented-out name and saintvision-core-evidence-wrong. Both accepted fixtures lose the required artifact identity. The current workflow has the correct literal name and published artifact 14464280752. Parse jobs.core.steps and require exactly one upload with the exact with.name, always condition, dist/ path and lifecycle ordering. Preserve these two false-pass fixtures as regression tests.

Git diff --shortstat found 53 files (+5835/-2), including historical receipts, proposed contracts, standalone helper/proof, collectors, CI and tests. Migrations are identical to unified. PR 411's original base contains 0068, whose SQL adds writer privileges including access to inv.project_nodes and inv.runs, workspace-specific functions and public policies. The collector reads these relations via its existing bound reader and calls neither new function. Equivalence is limited to the observed query contract. The exact 0067 revision check precedes membership, channels and resources. Foreign, empty and multihead fixtures assert the typed refusal with only transactionReadOnly retained. The positive fixture reaches MEMBERSHIP_UNKNOWN. The reader fixture leaves its unique disposable operator grant until database teardown.

Git rev-parse confirmed deploy/lan/peer_policy_phase.py blob 052b4a7e156e75a69bc4acf9656c12d25fd5a9d8 matches b8c839d1, 15384c36, abe0c971 and 4a928310. Its imports are standard library and cryptography. The isolated proof calls verify_floor to reject candidate input. Core artifact 14459544167 contains result.json for merge ref 8319be5cc7cff7a7af8ee522364d2fe0612d6738, two cycles, 61 negative controls and activationAllowed false.

Windows Python 3.10 ran python -m pytest -q tests/test_core_workflow_cx01.py tests/core/test_recovery_preflight_schema_pin.py (7 passed, exit 0). Hosted Core 44374576359 attempt 1 checked out the merge of the exact reviewed parents and logged 10 passing revision-pin PG cases plus 2 cohort cases. Backend 44374576478 passed on both matrix versions on attempt 1. Desktop 44374576340 attempt 1 failed the mounted-config browser fetch, then attempt 2 passed. PR checks include seven skipped jobs. Operating acceptance remains pending.

After the guard fix, repeat the named mutations and hosted Core on the new merge ref. Then port PR 411's scoped test harnesses, cohort assertions and applicable workflow changes from 15384c36..2598d3c0 onto the corrected unified candidate, reconcile tracking separately, retain 0067 and repeat PG and hosted proof before integration. No merge, fleet contact or activation occurred.
