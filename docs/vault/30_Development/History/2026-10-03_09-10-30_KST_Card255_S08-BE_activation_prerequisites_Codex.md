---
doc_id: "HISTORY-CARD255-S08-BE-ACTIVATION-PREREQUISITES-CODEX-001"
title: "Card 255 S08-BE activation prerequisites"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-10-03T10:15:54+09:00"
source_of_truth: "Git"
---

# Card 255 S08-BE activation prerequisites

## Selection and base

Card 247 and Claude backend review r3 left exactly three Medium prerequisites before product flag
enablement: the synthetic `1/1/1` budget, the request-derived fake base-image digest, and API access
to private worker configuration. Card 254 was already approved, so this card started from train 35
candidate `e025492527d94734de1c0514719c6691bca4cefa`. Because migration 0063 was necessary and 0062
was reserved to PR #348, the reviewed #348 head `47039aaac36aaee0b8b86c6829e07b279ed5176c`
was merged first. The graph is one head: `0063_build_policy_budgets`.

## Changes

- The immutable policy profile now carries all-or-none CPU/RAM/storage build budgets. Existing NULL
  versions remain audit records but cannot activate dispatch. Downgrade refuses if any version has
  activation budgets, so no authority is silently discarded.
- Plan compilation rebinds the exact profile version and checks its three values against the locked
  `project_resource_limits` and `storage_budgets` authorities. The plan copies those profile values;
  there is no fallback or default.
- The BuildKit transport measures literal digest-pinned Dockerfile bases only after exact clean Git
  head/tree verification. The old `sha256(digest(request))` image fabrication was removed.
- `api.json.buildPlanAuthority` replaces API parsing of `worker.json`. Worker TLS and product receipt
  locations cannot enter this object, the deployment collector checks the exact key set, and the
  Control Plane container no longer receives `INV_WORKER_CONFIG`.
- Definer revision and AC-11 migration fixtures were advanced to 0063. No definer function or RLS
  table population changed; the reviewed 15-function set and 160-table census remain unchanged.
- Claude r1 found PostgreSQL three-valued logic made the first 0063 constraint accept some partial
  rows. The constraint now requires `num_nulls(...)` to be exactly 4 (legacy audit row) or exactly
  0 plus all positive/cardinality bounds. The hosted real-PG suite covers all 16 NULL combinations
  and separate zero/negative complete rows.
- Project-ceiling, positive/available authority, source/profile image pin, final profile budget/pin
  drift, and pre-0063 profile boundaries now each have an independent regression assertion.
- The Dockerfile policy is deliberately conservative: stage-alias reuse and ARG-based image names
  are rejected even with a digest suffix. The shared read-only config volume is recorded as an OS
  trust-base residual; removing `INV_WORKER_CONFIG` narrows parsing but does not hide worker TLS
  bytes from a compromised API container. Dispatch stays off until that residual is accepted or
  the volumes are split.

## Verification so far

- Focused PG-free contract, transport, deployment-config, migration rehearsal and pin tests:
  **254 passed, 2 declared environment skips**.
- `tools/migration_graph.py --head`: `0063_build_policy_budgets`.
- Exact-head hosted Backend/Core/security results are pending after the r1 corrections and must be
  recorded in the PR before merge review is complete.

The flag remains default off. This card does not claim physical builder acceptance or S08-BE
completion.
