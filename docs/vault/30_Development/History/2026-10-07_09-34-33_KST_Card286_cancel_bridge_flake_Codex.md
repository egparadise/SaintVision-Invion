---
doc_id: "HISTORY-CODEX-CARD286-20261007"
title: "Card 286 cancel bridge real-PG flake determinization"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-10-07T10:12:00+09:00"
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
| `37548456022`, attempt 2 | `51788009` | passed | 1.011 |

The initial sample was **1 setup error / 10 executions (10%)**, with nine immediate predecessor
executions passing. Including the coordinator-started rerun, the observed sample is **1 setup error
/ 11 executions (9.1%)**. This is a measured sample, not a population-rate estimate. Run
`37548456022` attempt 1 completed as 8,623 passed and one error; attempt 2 completed as 8,624
passed, 23 skipped, 2 deselected and zero failures/errors. Its Core artifact is `11454093615`.

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
| 09:42 | repository Python 3.14: focused pure regressions and Workspace test collection | 3 passed; 12 collected |
| 10:10 | Core run `37553014490`, code head `39204885d9be0a2d8b59c159a2f4d75675087ee5` | success; 8,628 passed, 23 skipped, 2 deselected, zero failures/errors |
| 10:10 | Same Core artifact `11454546580` | original cancel-bridge case passed in 0.909 s; lost-ack regression passed in 0.738 s; early Workspace lane also passed it in 2.841 s |
| 10:11 | Backend run `37552996243`, same code head | Python 3.12 and 3.14 jobs both success |

PR `#382` is based on `coord/train63a-ci-0847`. The final documentation-only head CI and Claude
independent review remain pending; neither is inferred from the successful code-head runs.
