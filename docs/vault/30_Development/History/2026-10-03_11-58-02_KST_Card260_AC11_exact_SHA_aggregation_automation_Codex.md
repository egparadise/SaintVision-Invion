---
doc_id: "HISTORY-CARD260-AC11-EXACT-SHA-AUTOMATION-CODEX-001"
title: "Card 260 AC-11 exact-SHA aggregation automation"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-10-03T12:02:31+09:00"
source_of_truth: "Git"
---

# Card 260 AC-11 exact-SHA aggregation automation

## Selection and base

Card 258 measured four hosted axes at one exact SHA, but an operator still had to search runs,
dispatch the missing producer, wait, and start aggregation by hand. Card 260 automates only that
repeatable part. It started from accepted train 37 candidate
`e5549f4bae23f2206dd0bf8f02b00207e07f2750`; it changes no evaluator, evidence schema, target
registry, migration or score.

## Trust boundary

`tools/run_ac11_exact_sha_aggregate.py` reads the three complete producer chains from
`docs/ac11-axis-sources.json`. The reviewed set is fixed to security, accessibility and migration
rehearsal; migration emits two axes. For a caller-supplied full SHA and remote ref it:

1. requires a clean local exact checkout and proves the remote ref still resolves to that SHA;
2. accepts only `workflow_dispatch`, attempt 1, exact workflow/ref/SHA runs and refuses two usable
   candidates;
3. dispatches only a missing producer and binds correlated lanes to a fresh opaque run title;
4. requires exactly one unexpired expected artifact, binds its run/SHA/ref metadata, downloads it
   and compares its bytes with GitHub's SHA-256 digest;
5. rechecks producer uniqueness before dispatching the aggregate lane;
6. binds the aggregate checkout receipt and each complete axis's `sourceRunId`,
   `sourceHeadSha`, `artifactSha256` and `artifactObservedSha256` to the selected inputs; and
7. calls the existing `aggregate_ac11_evidence.aggregate()` against the reviewed allowlist Git
   blob. An uploaded result that differs from that recomputation is rejected.

Run IDs and artifact IDs cannot be reused across lanes. A rerun attempt, missing/expired/duplicate
artifact, concurrent duplicate run, malformed or duplicate-key JSON, unsafe ZIP member, changed
remote ref, or mismatched canonical result is a refusal. Command stderr and artifact content are
not copied to the redacted receipt. Exit 0 means the procedure reached the canonical verdict; it
does not turn `MEASURED_FAIL` or `INVALID_RUN` into success and `promotesScore` is always false.

## Verification before hosted execution

- `python -m pytest -q tests/test_run_ac11_exact_sha_aggregate.py`: **25 passed**.
- The fake-gh suite covers missing-only dispatch and the SHA/ref/event/workflow/attempt, duplicate
  run/correlation, run-id reuse, saturated run/artifact listings, artifact identity/expiry/digest
  and canonical-result boundaries.
- `python -m py_compile` and `git diff --check`: exit 0.
- The first direct CLI smoke found that package imports worked under pytest but not under
  `python tools/...`; no workflow had been dispatched. The direct invocation is now a regression
  test and uses the repository root without exposing or modifying credentials.

The exact-head hosted producer/aggregate run IDs belong in the PR verification comment after this
documentation commit fixes the final code SHA. Until those runs complete, this record claims only
the PG-free fake-gh result above.
