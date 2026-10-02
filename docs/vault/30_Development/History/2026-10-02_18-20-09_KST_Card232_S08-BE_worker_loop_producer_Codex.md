---
doc_id: "HISTORY-CARD232-S08-BE-WORKER-PRODUCER-20261002"
title: "Card 232 S08-BE product worker loop and trusted intent producer"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-10-02T18:55:06+09:00"
source_of_truth: "Git"
base_sha: "c57697d2ab80877f44e189c1efe172a6dd03a7e6"
reviewer: "Claude"
---

# Selection and scope

The mechanical measurement recorded by Card 223 and the later v1.12 rescore found two
independent S08-BE gaps: no product process constructed `BuildExecutionWorker`, and no
product path supplied migration 0059 with committed Run, policy-decision, and lease
authority. Card 229 closed claim-owner fencing at base `c57697d2`; Card 232 is therefore
the first external-prerequisite-free Codex card that can connect those two ends without
opening a public route. Migration number 0060 was coordinator-reserved for this card.

# Database authority

`migrations/versions/0060_build_execution_admissions.py` adds an internal-only,
tenant-scoped authority row above `0059_build_execution_intents`. The exact
`BuildRequest`, `BuildPlan`, and `PolicyDecision`, policy version, Evidence ID, and human
actor are immutable. PostgreSQL computes all three JSONB digests. FORCE RLS isolates
tenants, DELETE is forbidden, and only a guarded `ready -> ready` retry or
`ready -> promoted|quarantined` terminal transition is legal. A
downgrade refuses while any committed admission exists.

0060 is intentionally separate from 0059. The admission row is the durable, immutable
authority accepted by the trusted producer; it may remain `ready` while the product
worker is disabled or while a current Node observation is temporarily unavailable. The
0059 row is instead an executable queue item: its claim lease, fencing token, retry
classification, and one-shot dispatch ledger begin only after promotion. Writing 0059
at producer time would either expose an un-revalidated executable item while the product
lane is disabled, or overload 0059's dispatch state with pre-dispatch policy and live
authority waiting. The two-row boundary therefore separates durable intent acceptance
from executable dispatch authority, while promotion binds them in one transaction.

`services/control-plane/src/inv/build_product_runtime.py` records an admission only after
current project permission, the policy expiry/effect, Run state, Node/resource, and exact
live lease fence have been locked and checked. Promotion repeats those checks, recomputes
all three database digests, inserts the 0059 intent and redacted outbox audit event in one
transaction, and isolates one poison row rather than blocking the tenant queue. There is
no HTTP route or CLI for either operation.

Promotion treats digest or existing-0059 conflicts as permanent row-local quarantine
and continues to the next admission. Stale observations, temporarily offline Nodes, and
explicit retryable errors remain `ready` with a database-owned retry counter and bounded
`next_attempt_at`; replay exposes the `ready` state and can recover after freshness is
restored. Replaying a permanently quarantined admission raises its recorded error rather
than returning an object that appears accepted.

# Product process boundary

`services/control-plane/src/inv/worker.py` constructs the product runtime and its eighth,
single build lane only when `INV_BUILDKIT_PRODUCT_ENABLED` is exactly `1`. With the
default-off value it does not parse build configuration, snapshot a Node channel, or
claim/promote a row. The enabled composition connects the measured rootless BuildKit
client, pinned Node TLS quarantine channel, `BuildExecutionAdapter`,
`BuildExecutionService`, admission producer, and 0059 worker.

The concrete BuildKit client remains reference-only and deliberately refuses product
dispatch. Thus this change proves a reachable product composition and durable producer,
not a physical builder success. The flag remains off; S08-BE completion and physical
acceptance remain NOT_OBSERVED/BLOCKED_EXTERNAL. A successful LAN product build still
requires the operational transport replacement and its Node receipts.

# v1.12 75-point condition comparison

The v1.12 rescore measured that the reviewed durable quarantine channel and the internal
0059 worker seam already existed, but found two remaining 75-point implementation ends.
This change compares itself to those exact conditions; it does not independently rescore
the task.

| v1.12 condition | Before | Card 232 result | Evidence boundary |
|---|---|---|---|
| A product process constructs and runs `BuildExecutionWorker` | zero product references outside its own module | `inv.worker` owns one bounded build loop behind the exact enable value | process-level flag-off/flag-on regressions; default off is preserved and was explicitly not a v1.12 blocker |
| A trusted product producer supplies 0059 from committed authority | zero product enqueue path | 0060 admission rechecks the committed Run, current permission and policy, and the exact live lease before atomic 0059 promotion | FORCE-RLS/immutable migration, PG-free mutation guards, and hosted real-PG cases required before merge |

Both code conditions that v1.12 named for a possible `S08-BE 50 -> 75` transition are now
implemented. The scoring document remains the owner of the eventual score change after
independent review and exact-head hosted evidence. This is not a 100-point or operational
acceptance claim: the physical builder receipt path remains externally unmeasured and the
reference transport still refuses product dispatch.

# Cross-train RLS census condition

Card 234 (`#330`) introduced the reviewed RLS-table census and correctly repinned it for
0059 at 156 tables. Migration 0060 adds one more FORCE-RLS table, so a train that contains
both changes must measure and repin the census to 157 before landing Card 232. This branch
does not merge Card 234's wider train into the Card 229 stack; the merge-train owner must
order Card 234 first and regenerate the census from the combined 0060 tree. A 156-table
census beside 0060 is stale and must fail closed, never be accepted as this card's evidence.

# Corrective finding

The strict `BuildLeaseFence` contract carries the database recovery epoch only as the
UUID prefix of `fencingToken`. `BuildExecutionService` previously read a nonexistent
`lease.recoveryEpoch`, so every strict plan would fail Node quarantine preflight. It now
passes the verified fencing-token prefix, with a direct regression that stops at the
preflight call and asserts the exact UUID.

# Claude r1 corrections

- The AC-11 definer-policy blob pin now follows the reviewed 0060 policy revision. 0060
  adds no `SECURITY DEFINER` function; its guard is explicitly `SECURITY INVOKER` and
  executable by neither `PUBLIC` nor `inv_kernel`.
- An existing 0059 row with different content now quarantines only its matching 0060
  admission as `IDEM-0001`; the same promotion call can advance the next ready row.
- Observation staleness and temporary Node offline state back off without becoming a
  terminal quarantine. Node recovery-epoch drift remains a permanent authority error.
- The touched eval-suite, model-version, object-store, release-acceptance, and AC-11
  rehearsal tests only advance their expected migration head from 0059 to 0060. They do
  not change those features' behavior or acceptance criteria.

# Verification

Local verification uses Python 3.14 because this workstation's default Python 3.10
cannot import `enum.StrEnum`. The focused producer/worker/migration set is green; the new
real-PostgreSQL file is intentionally left for hosted Core and must execute without skips.
No local PostgreSQL, Docker, BuildKit, or full suite was started.

| Check | Result |
|---|---|
| producer, intent, AC-11 migration, and resolver focused set | 197 passed |
| BuildExecution, adapter, intent, producer, worker-config, and migration regressions | 185 passed |
| `tools/migration_graph.py --head` | `0060_build_execution_admissions`, one head |
| `git diff --check` | exit 0 |
