---
doc_id: "HISTORY-CARD229-BUILD-CLAIM-FENCING-CODEX-001"
title: "Card 229 Build dispatch claim ownership fencing"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T16:46:18+09:00"
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
- The final transaction locks the intent row and validates `claimed + exact token` before it reads
  or releases the resource lease, persists Evidence, or appends the completion outbox event.
- A sweeper reclaim followed by a new claim increments the token. The old worker can no longer
  change queue state or commit downstream consequences. The existing canonical
  `build.dispatch` ledger key independently prevents the external dispatch from occurring twice.

## Failure classification

| Failure class | Queue result | Reason |
|---|---|---|
| retryable `DomainError` | bounded-backoff `pending` | the product explicitly says another attempt is safe |
| `KeyboardInterrupt`, task/future cancellation | bounded-backoff `pending` | worker ownership ended without proving a permanent product defect |
| timeout, connection and selected network `errno`, PostgreSQL operational loss | bounded-backoff `pending` | authority or remote outcome is uncertain |
| non-retryable `DomainError`, validation/programming/local permission error | terminal `quarantined` | retrying unchanged input would repeat a permanent refusal |

The original exception is re-raised even if durable queue recovery itself fails; recovery errors are
logged and never replace the initiating cause.

## Verification plan and honest state

PG-free tests pin the classification table, original-cause preservation and worker-to-service token
binding. The real-PostgreSQL file pins stale-owner mutation rejection, rejection before
Evidence/outbox/lease consequences, and the slow-worker → sweeper → second-worker interleaving in
which the canonical ledger records exactly one dispatch. Local Python is 3.10 while the repository
requires `StrEnum`, so local collection is unavailable; syntax compilation and `git diff --check`
passed. Exact-head hosted Core and Backend, including the real-PG file, remain required before
approval.

