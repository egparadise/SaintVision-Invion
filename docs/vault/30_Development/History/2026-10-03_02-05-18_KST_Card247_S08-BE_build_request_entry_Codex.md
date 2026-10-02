---
doc_id: "HISTORY-CARD247-S08-BE-BUILD-REQUEST-ENTRY-001"
title: "Card 247 S08-BE BuildRequest product entry implementation"
version: "1.2.2"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T04:03:33+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S08-BE", "CARD-247"]
---

# Card 247 S08-BE BuildRequest product entry implementation

## Selection and base

Card 246 design v1.1 (`#341`) identified the first missing product authority above the
Card 241 admission seam: callers could dispatch only a server-created `BuildRequest`, but
no public surface could request its creation. This branch started from Card 241 approved
head `1b4df727` and merged the coordinator-only board correction `e9956576` without source
changes.

## Implemented boundary

- Migration `0061_build_preparations` follows `0060` and adds the operator-owned profile,
  immutable preparation, and fixed-window rate tables. All three use exact tenant FORCE
  RLS. Triggers are SECURITY INVOKER; no new SECURITY DEFINER function exists. Profiles
  are SELECT-only to `inv_kernel`; preparations expose SELECT/INSERT and `queued_at` only.
- The two public routes accept only strict `BuildPreparationInput` and `BuildEnqueueInput`.
  Raw build, plan, policy, provider, lease, and secret documents are not public inputs.
- Prepare reserves idempotency and quota in a short transaction, copies an immutable
  editor snapshot, performs ObjectStore I/O without a DB transaction, then rechecks source
  revision/profile and commits the approval snapshot and preparation together.
- The capsule locator is tenant/project scoped (native S3 scope or a scoped local opaque
  handle), bytes are read back by full SHA-256 before approval commit, and the retained
  authority records a minimum 35-day deadline. A nonempty secret-alias profile remains
  fail closed unless a server-owned resolver is installed; aliases are never treated as
  secret values.
- Approval review uses a redacted union summary with the profile's explicit `cache_mode`.
  Enqueue refuses while the product flag is
  off before consuming approval state. When enabled, its authority factory runs after the
  scheduled transition and before 0060 admission in the same transaction. Only the explicit
  drift codes `VERIFY-0002` and `GRAPH-0003` terminalize. Pending approval maps to rejected;
  approved approval maps to the already permitted expired transition. Both write canonical
  approval audit plus the redacted build terminal event. `AUTH-0031`, `RES-0003`, provider
  absence and budget errors do not mutate approval state.
- A preparation-backed worker intent carries capsule locator and digest to a required
  materializer seam. A deployment without that seam refuses with `RES-0006`; mutable host
  checkout fallback is not allowed.
- Source authority now records the recovering Run's attempt and recovery epoch and rechecks
  those values, state, editor revision, and digest before quorum dispatch. Provider measurement
  is performed without a business transaction; only its candidate is compiled against the
  locked preparation and newly acquired live lease.
- Under exact product flag `1`, the configured API reads the same strict private
  `worker.json` builder measurement authority as the worker. It measures BuildKit outside
  the transaction, then selects the configured Node's project-authorized CPU resource and
  creates the live lease, build session, plan and evidence identity inside the final
  approval transaction. Missing config, stale health, missing ceilings/capacity or flag-off
  state remains fail closed. Compose keeps the flag at default `0`.
- Legacy internal BuildRequest approval remains valid for Card 241's already committed exact
  authority. Only the public review projection requires a 0061 preparation, so a raw legacy
  request is never exposed as the new redacted review summary.

## Evidence status and non-claims

Contract generation reports 97 matching schemas and contract binding reports 0 failures.
The migration graph has the single head `0061_build_preparations`; Python compilation and
`git diff --check` pass. Hosted AC-11 run `37039236221` observed the 0061 catalogue at source
head `448ec9e0`; `tools/write_rls_table_census.py` regenerated the reviewed population as
160 tables (the 157-table base plus the three design-approved 0061 tables), SHA-256
`4bb34251a97b1b918104249ab87b9623137829c0806bf82eb1a19dd6b7641077`, Git blob
`dc641de461553bda1eff2f6d6c83b2f7b37ed8c4`. That old run is reference-only and failed; this
card uses only its catalogue census and does not claim that its security axis passed.

Claude r1 and the first hosted Backend/Core attempt exposed and fixed the operational blockers:
the immutable source/profile recheck no longer requests row locks that `inv_kernel` cannot own;
the review union is on `ApprovalReviewView` rather than Workspace input; direct Card 241 quorum
remains valid; terminal drift uses legal status transitions with audit; the configured API owns
a measured plan authority; Git SHA-1 is explicitly non-security; census is 160; migration parent
and fixture imports are current. Focused PG-free results are `test_build_preparations.py` 15,
`test_build_product_runtime.py` 19, `test_deployment_credentials.py` 15,
`test_object_store_locator_migration.py` 9, approval contract files 13, and the RLS census
ratchet 5 passed. The two-case real-PG file collects with all dependencies. Exact-head
Backend/Core/security and real-PG results are intentionally recorded in the PR review-baseline
comment after the single final push, because those runs do not exist when this commit is made.

The first exact-head frontend compile exposed the intended H2 union at its consumer: the UI
still assumed every `ApprovalReviewView.workload` was a `WorkloadSpec`. The consumer now
discriminates the generated `kind: build` type, validates every redacted build-summary field,
and presents that summary without inventing a workspace or command. Production build and the
two focused approval-review UI files pass (`33 passed`).

Exact-head Core run `37047480344` then executed the full collection (`8285 passed`) and exposed
that the new two-case real-PG module registered `remote` without registering its transitive
`node_runtime` and `approval` fixtures. Both cases failed during setup rather than being skipped
or reaching product code. The module now imports the complete fixture chain explicitly; the
replacement exact-head Core run is the only run eligible for the final review baseline.

S08-BE completion, product flag enablement, and physical builder acceptance are not
claimed. The actual census count is derived from the hosted catalogue; the current base
already contains 157 reviewed tables and 0061 creates three, so no unmeasured count is
predeclared merely to match an older estimate.
