---
doc_id: "HISTORY-CODEX-CARD286-20261007"
title: "Card 286 cancel bridge real-PG flake determinization"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-07T09:34:33+09:00"
source_of_truth: "Git"
---

# Card 286 cancel bridge real-PG flake determinization

## Scope and provenance

- Task: `CARD-286`
- Owner / reviewer: Codex / Claude
- Branch: `agent/codex/c286-cancel-bridge-flake`
- Base and train 63 candidate: `517880099743cf2d62131012191b7ba54650c44d`
- PR base: `coord/train63a-ci-0847`
- Local Docker: not used; Docker paths were removed from `PATH` for local commands.
- Local PostgreSQL roles and databases: not inspected or changed. The real Linux Node regression is
  assigned to hosted Core.

## Hosted frequency measurement before the change

The same JUnit case was extracted from the `saintvision-core-evidence` artifacts. This is an
observed sample, not a population-rate claim.

| Core run | Head | Result | Case time (s) |
|---|---|---:|---:|
| `37331227492` | `f5234236` | passed | 0.754 |
| `37346779738` | `314dd9ff` | passed | 1.163 |
| `37361623575` | `867f9745` | passed | 0.781 |
| `37376934093` | `3be7547c` | passed | 0.917 |
| `37380773795` | `f2433bbf` | passed | 1.025 |
| `37384952505` | `0e81d3af` | passed | 1.000 |
| `37398066451` | `c28a40ce` | passed | 1.084 |
| `37401903045` | `59050d2a` | passed | 0.973 |
| `37545644638` | `b9ea9992` | passed | 1.034 |
| `37548456022`, attempt 1 | `51788009` | setup error | 6.479 |

Observed frequency: **1 setup error / 10 executions (10%)**, with nine immediate predecessor
executions passing. Run `37548456022` attempt 1 completed the full suite as 8,623 passed and one
error. The coordinator-started failed-job rerun is recorded separately when it finishes.

## Root cause boundary

The traceback ends in `tests/integration/test_workspace_resume.py::build_resume`, before
`test_missing_current_audit_partition_rolls_back_and_same_key_retries` detaches the current audit
partition or sends either idempotent request. The setup called the Node execution endpoint once;
the client received a non-confirming response and correctly raised `NODE-0030: Node delivery
unconfirmed; observe the same command`. The fixture propagated that uncertainty instead of using
the receipt observation path. Therefore neither audit partition creation nor the same-key retry
was involved in this failure.

The Node runtime journals the command before container creation, and its receipt endpoint is
observation-only. Reissuing the execution would be unsafe, while observing the same command is the
protocol-defined convergence action.

## Change and fail-closed properties

- Added a test-only `deliver_once_then_observe()` helper.
- It calls execution exactly once. Only `NODE-0030` enters a maximum of three receipt observations.
- Observation exhaustion re-raises `NODE-0030`; all non-uncertainty errors are propagated without
  observation. No product timeout, status mapping, retryability, or audit behavior changed.
- A real-Node regression raises a synthetic lost acknowledgement only after the first execution was
  accepted. It requires the fixture to recover by observation and asserts call modes
  `[execute, observe]`; reverting the fixture call fails.

## Verification

| Time (KST) | Command / environment | Result |
|---|---|---|
| 09:24 | `python -m pytest tests/core/test_node_delivery_support.py -q`, Docker absent from `PATH` | 3 passed |
| 09:24 | `python -m compileall -q` for the helper, unit test and integration test | exit 0 |
| 09:35 | docs, citation ratchet with base, single-source ratchet, contract binding, ontology | all exit 0 |
| 09:36 | `python tools/sync_obsidian.py --check` | exit 0; 11 pre-existing unmanaged destination conflicts, no files written |

Hosted exact-head Core, the repeated real-Node target, complete JUnit totals, commit SHA, PR, and
Claude review status are pending and must not be inferred from the local pure tests.
