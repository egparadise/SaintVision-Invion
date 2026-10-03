---
doc_id: "HISTORY-CARD260-AC11-EXACT-SHA-AUTOMATION-CODEX-001"
title: "Card 260 AC-11 exact-SHA aggregation automation"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-10-03T12:17:50+09:00"
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

- `python -m pytest -q tests/test_run_ac11_exact_sha_aggregate.py`: **35 passed**.
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

## Claude r1 correction and superseded dispatches

Claude r1 found that a completed non-success dispatch at the exact SHA was discarded before the
tool considered dispatching again. That is retry-to-green laundering even if a later run passes.
There is now no override: any exact workflow/ref/SHA `workflow_dispatch` with a completed
non-success conclusion refuses the procedure before another dispatch. The aggregate lane performs
the same pre-dispatch check and also refuses an unowned prior successful aggregate rather than
reusing its correlation or creating a duplicate. Failure followed by success, each supported
non-success conclusion, expiry by time with `expired=false`, and a concurrent producer appearing
after binding all have independent regressions. The focused result is the 35 passed count above.

Two security runs were created while bringing up the live procedure and are not final Card 260
evidence:

- Run `37091487344`, head `6afdcc4d2e6e0d73d8a2cc829ec671b597dd37b5`, completed success with
  artifact `11262209537` (`sha256:c5bef8e415772fa5836897c37b1cb52392a243736f09d0da41f953c4f38946c6`).
  The surrounding orchestration lost GitHub REST access before producing an aggregate receipt, and
  later documentation and fail-closed corrections superseded that head.
- Run `37092129615`, head `f9227a630b6267ebc1447ad8aa1eb848aa2f58e2`, completed success with
  artifact `11263290786` (`sha256:3502d87d6a8a1b1877a2febb0290a56624ef03cf5dc83aac487c2aa877ea1183`).
  It was followed by accessibility run `37092192002` at the same head, completed success with
  artifact `11263161184`
  (`sha256:46233a2faa555775f9de02783472ae74881991b7ad970b63bbf83852d52a5294`).
  Claude r1 arrived before migration or aggregate; the local orchestrator was then interrupted so
  it would not continue measuring a head that required correction.

None of these runs is promoted, substituted for a final-head measurement, or counted as an
aggregate.

The live accessibility run also exposed that GitHub's `workflowName` is not a stable workflow path:
that run reports `AC-11 Accessibility E2E Evidence`, while some security runs report their YAML
path. Candidate discovery remains server-filtered by workflow file, but completed runs are now
bound to the authoritative REST `path`, SHA, ref, event, attempt, status and conclusion before an
artifact is accepted. A friendly-name candidate is accepted only when that REST path is exact; a
changed REST path is refused.
