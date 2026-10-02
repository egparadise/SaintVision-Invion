---
doc_id: "HISTORY-CARD247-S08-BE-BUILD-REQUEST-ENTRY-001"
title: "Card 247 S08-BE BuildRequest product entry implementation"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T02:05:18+09:00"
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
- Approval review uses a redacted union summary. Enqueue refuses while the product flag is
  off before consuming approval state. When enabled, its authority factory runs after the
  scheduled transition and before 0060 admission in the same transaction. Non-retryable
  drift is terminalized in a separate durable transaction; transient authority failures
  remain retryable.
- A preparation-backed worker intent carries capsule locator and digest to a required
  materializer seam. A deployment without that seam refuses with `RES-0006`; mutable host
  checkout fallback is not allowed.

## Evidence status and non-claims

Contract generation reports 97 matching schemas and contract binding reports 0 failures.
The migration graph has the single head `0061_build_preparations`; Python compilation and
`git diff --check` pass. Hosted PostgreSQL end-to-end evidence, the live 0061 RLS census,
and exact-head Backend/Core remain pending at this checkpoint. The census must be produced
by `tools/write_rls_table_census.py` from the hosted collector observation, not by hand.

S08-BE completion, product flag enablement, and physical builder acceptance are not
claimed. The actual census count is derived from the hosted catalogue; the current base
already contains 157 reviewed tables and 0061 creates three, so no unmeasured count is
predeclared merely to match an older estimate.
