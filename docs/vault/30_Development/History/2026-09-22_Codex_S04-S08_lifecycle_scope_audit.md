---
doc_id: "HIST-2026-09-22-CODEX-S04-S08-LIFECYCLE-AUDIT"
title: "S04-S08 lifecycle scope audit"
version: "1.0.0"
owner: Codex
reviewer: Claude
author: "Codex"
updated: "2026-09-22T23:59:00+09:00"
source_of_truth: "Git"
status: drafted
---

# Scope

The S04/S05/S07/S08 Codex-owned lifecycle scopes were reviewed by task scope,
not only by module: cancellation/timeout/reconnect, hard filtering and node
revalidation, drain/rescheduling/reconciliation, and kill-switch/cleanup.

# Findings

No additional unambiguous product-path mismatch was found after the S07 node
loss/replica wiring fix at `062c20db`. The following paths already keep the
related state in one transaction or deliberately defer physical cleanup until
evidence arrives:

- approval expiry/rejection transitions the Run atomically; physical leases
  remain until the authenticated stop receipt and reconciliation,
- delivery timeout/cancellation leaves the delivery uncertain and does not
  release physical reservations without a Node receipt,
- drain and kill-switch reconciliation cancel only work that is safe to cancel;
  in-flight work remains fenced until its physical stop evidence,
- placement uses the current enabled project-node membership, active-node
  filtering, fresh resource snapshots, and locked revalidation before reserve,
- a node heartbeat can restore the node to active while its stale replicas stay
  unavailable; this is intentional fail-closed behavior pending re-verification,
  not a ready-replica claim.

# Verification boundary

`python -m pytest tests/test_run_state.py tests/core/test_node_loss_replica_wiring.py -q --tb=short`
passed: 48, failed 0, skipped 0.

`python -m pytest tests/test_pools.py -q --tb=short` collected 34 PostgreSQL
tests but skipped all 34 because `INV_TEST_ADMIN_DSN` is not configured. No
PostgreSQL state-transition claim is made from that run. Real PostgreSQL
verification remains an external environment step for this audit.

The source review did not change product code. No user decision was inferred.
