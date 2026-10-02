---
doc_id: "HISTORY-CARD232-S08-BE-WORKER-PRODUCER-20261002"
title: "Card 232 S08-BE product worker loop and trusted intent producer"
version: "1.6.0"
status: "review"
author: "Codex"
updated: "2026-10-02T20:34:16+09:00"
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
0059 at 156 tables. Its approved head `f91ce5db` was merged non-force before repinning
0060. Hosted security run `36992706201` measured the combined exact head `1269f37f` on a
disposable migrated PostgreSQL 16 database. The normalized RLS report carried 157 unique
tables with digest `32ecadb725a9f231aef60117346c76f6707c5f32dded1084d48b6f002298299e`.
`tools/write_rls_table_census.py`, not a hand edit, wrote the reviewed census and produced
Git blob `ee6c3f7fb1eefc25388893ff0bad76797dabe3ab`; the aggregator pins that exact blob.

The 0060 table's measured ground truth matches its owner design: it is tenant scoped with
RLS enabled and forced; `inv_kernel` has table SELECT/INSERT, lifecycle-column UPDATE,
no DELETE, and the single `build_execution_admissions_tenant_isolation` ALL policy.
The other seven measured runtime/audit roles have no table privilege or policy on it.
All observed row counts were zero, so this run remains `UNMEASURED` for row isolation; it
is catalog/RLS disposition evidence and is not promoted to a security PASS.

The writer also accepts the hosted normalized RLS artifact only when `reportAvailable` is
true, threat and run IDs match, its source SHA is the current exact HEAD, and the migration
graph has one readable head. This keeps hosted-only repinning generated and fail closed.

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
| r1 correction + AC-11 census/aggregator focused set | 247 passed |
| hosted 0060 RLS catalog observation | run `36992706201`, 157 tables, `UNMEASURED` row verdict |
| `tools/migration_graph.py --head` | `0060_build_execution_admissions`, one head |
| `git diff --check` | exit 0 |

# Claude r2 queue-fairness correction

The r1 retry branch committed a one-second database-owned backoff and returned from the
promotion call. Because the product tick also waits one second, the oldest temporarily
stale admission could become due again before every tick and starve all later healthy
admissions. The retry branch now commits its backoff and continues the bounded selection
loop, so that row is no longer due and the same tick can promote the next healthy row.

A real-PostgreSQL regression creates one admission on a stale Node and a later admission
on a healthy Node. The first tick must leave only the stale row at
`ready/RES-0003/retry_count=1` with a future `next_attempt_at` and must promote the healthy
row. Replacing the `continue` with the former `return None` makes that regression fail.
The local workstation could only compile these two changed Python files: its installed
Python 3.14 has no pytest package and default Python 3.10 cannot import `enum.StrEnum`.
The real-PG result is therefore an exact-head hosted Core merge condition, not a local
measurement claim.

# Claude r3 bounded-tick correction

The r2 `continue` fix could select the same oldest row again if validation of a large
stale queue took longer than its one-second backoff. One `promote_next` call could then
run indefinitely instead of returning control to the product loop. Each call now has a
fixed 128-candidate budget and a call-local set of visited Run IDs. The SQL selection
continues to exclude future `next_attempt_at` values and also excludes every row already
visited by the current call. Exhausting the budget returns without weakening the durable
per-row backoff or the next tick's ability to retry it.

The hosted real-PostgreSQL regression creates 60 admissions on one stale Node followed
by one healthy admission. A single promotion call must visit each stale row once, leave
all 60 at `ready/RES-0003/retry_count=1`, promote the healthy row, and return in under
15 seconds. Removing the visited-row SQL exclusion recreates the reviewer-observed
long-running selection; reducing the budget below the healthy row prevents promotion.

# Claude r4 cross-tick fairness correction

A fixed 128-row budget bounded one call but did not by itself make progress fair across
calls. With more than 128 stale rows and a one-second product-loop interval, the oldest
retried rows became due again and `ORDER BY created_at` selected them ahead of every
unseen row. Selection now orders by `next_attempt_at`, then `retry_count`, creation time,
project, and Run. A retry therefore moves behind never-attempted due work even after its
backoff expires; the existing due-time predicate still prevents early retry.

The hosted real-PostgreSQL regression creates 200 stale admissions followed by one
healthy admission. The first call consumes the 128-row budget and returns; the second
must process the remaining stale rows and promote the healthy row. Both calls are capped
at 20 seconds, every stale row has exactly one retry, and no row has a second retry.
Removing the fair ordering restores the six-tick starvation class and fails the test.
