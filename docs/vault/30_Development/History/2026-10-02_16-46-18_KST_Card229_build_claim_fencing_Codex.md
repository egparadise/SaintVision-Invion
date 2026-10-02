---
doc_id: "HISTORY-CARD229-BUILD-CLAIM-FENCING-CODEX-001"
title: "Card 229 Build dispatch claim ownership fencing"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-10-02T17:17:14+09:00"
source_of_truth: "Git"
---

# Card 229 — build dispatch claim ownership fencing

## Selection and boundary

Card 223 left two explicit activation prerequisites: a slow worker must lose authority after the
30-second sweeper reclaims its intent, and interruption or transport uncertainty must not become a
permanent quarantine. This card starts from Card 223 head
`233c2da1f689cc6e940d61e31eeefe1a9e710aec`. Product dispatch remains default-off; this card does
not activate it or claim S08-BE completion.

No migration is required. Migration `0059_build_execution_intents` already increments
`attempt_count` on every `pending -> claimed` transition. The claimed row's value is therefore the
durable, monotonic `claim_fencing_token`; adding a second counter would create two authorities.

## Ownership rule

- Every queue mutation (`requeue`, terminal `quarantine`, `completed`) requires both `claimed`
  status and the exact `attempt_count` observed by that worker.
- The product worker passes that token into `BuildExecutionService`.
- The same token reaches `BuildExecutionAdapter`. Its admission transaction locks the intent and
  validates `claimed + exact token` before consuming the one-shot ledger. A stale worker records
  `inv.build.dispatch_fenced` durably without consuming that ledger, then returns `IDEM-0001`;
  the pending/current generation can therefore continue instead of leaving a dispatched but
  uncommittable build.
- The final transaction locks the intent row and validates `claimed + exact token` before it reads
  or releases the resource lease, persists Evidence, or appends the completion outbox event.
- A sweeper reclaim followed by a new claim increments the token. The old worker can no longer
  change queue state or commit downstream consequences. The existing canonical
  `build.dispatch` ledger key independently prevents the external dispatch from occurring twice.

## Failure classification

| Failure class | Queue result | Reason |
|---|---|---|
| retryable `DomainError` | bounded-backoff `pending` | the product explicitly says another attempt is safe |
| `KeyboardInterrupt`, `SystemExit`, task/future cancellation | bounded-backoff `pending` | worker ownership ended without proving a permanent product defect |
| built-in or subprocess timeout, connection, temporary DNS/URL and selected network `errno`, PostgreSQL operational loss | bounded-backoff `pending` | authority or remote outcome is uncertain |
| non-retryable `DomainError`, validation/programming/local permission error | terminal `quarantined` | retrying unchanged input would repeat a permanent refusal |

The original exception is re-raised even if durable queue recovery itself fails; recovery errors are
logged and never replace the initiating cause.

## Verification plan and honest state

PG-free tests pin the classification table, original-cause preservation, worker-to-service token
binding, and the adapter's pre-ledger owner check. The real-PostgreSQL file pins stale-owner
mutation rejection, rejection before Evidence/outbox/lease consequences, the existing rule that a
consumed ledger row is not swept, and the adverse ordering where the stale worker reaches the
ledger boundary before the new owner. The stale worker dispatches zero builds, a durable fenced
event remains, the current owner dispatches and completes once, and the canonical ledger has one
row. It also pins `subprocess.TimeoutExpired` and `SystemExit` to retryable `pending`, never terminal
quarantine. Local Python is 3.10 while the repository requires `StrEnum`; a compatibility shim was
used only in the test process for focused PG-free execution. Exact-head hosted Core and Backend,
including the real-PG file, remain required before approval.
