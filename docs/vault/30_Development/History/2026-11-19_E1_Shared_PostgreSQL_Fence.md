---
doc_id: "HISTORY-FLEET5-E1-PG-FENCE"
title: "E1 shared PostgreSQL writer candidate"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T08:49:00+09:00"
source_of_truth: "Git"
---

# E1 shared writer candidate

Task task_c4b4b9ea0b7d, branch agent/codex/fleet5-shared-pg-fence, base b31b780b625707a0853fb83b3114cfb63096b24b on unified 433ea326. Codex implementation, Claude reviewer ctx_acf402d6296e. INDEX-PROGRESS-001 v1.0.389, WORKBOARD-CODEX-001 v1.0.350, delivery v1.1.0, core reliability v1.0.0. A1 review 1f458b46 remains HOLD-only.

One empty-database candidate installer (reservations.sql) runs in a caller transaction outside both migration discovery paths. Alembic 0067_audit_reader_revoke descends from 0066_tenant_registry_revoke. No revision reserved. Promotion requires a coordinated migration, grants, verified operator identities and updates to pinned consumers. This script is unsuitable as an in-place upgrade for an existing candidate installation.

Bootstrap is privileged and explicit. Each database session login maps to one tenant. The active holder, login and monotonically advancing generation are persistent PostgreSQL state. Transactional row locking serializes transfer and E1, including exact replay. Direct journal append independently checks holder and generation. The shared journal and scoped reservation audit commit with the reservation. Reconciliation requires both. No grant, principal, holder, runtime adapter or route is installed by default.

Disposable PostgreSQL, Windows, Python 3.10. Fresh initdb, loopback, 16 MB shared buffers, stopped after test. E1_DISPOSABLE_PG_DSN set only for the disposable instance. Command py -3.10 -m pytest -q tests/core/test_e1_reservation.py exited 0, 10 passed in 3.17 seconds. Probes cover observed blocking across sessions, old generations, exact replay, missing journal, stale direct append, transaction rollback and unregistered session login spoofing the tenant setting.

Direct SQL inventory located identity/membership writers in tools/lan_pilot.py and tools/remote_workspace_entry.py. The similarly named nodes table in proposed_expired_policy_recovery.py belongs to a local SQLite model and supplies no PostgreSQL authority. Validation/fixture writers include tools/check_migration_upgrade.py and tools/run_s04_fe_matrix.py. Related node/channel/resource mutations occur in containment, leases, node_channels, observation, node_transport and build_execution. These paths require owner-level classification, fencing or privilege exclusion before admission. Dynamic SQL, ORM writers and out-of-repository clients require a deployment privilege inventory. A0 canonical history, eligible evidence and authenticated operating identities remain unverified. No fleet, signer, production DB or live writer changes. CI, independent review and operational acceptance pending. Next owner: independent reviewer, then integration coordinator.

Review input msg_1b44cf0256b7 confirmed no competing reservation. Added statement-level TRUNCATE rejection and removed the CI dependency on a dedicated E1 environment variable. Repeated the suite using INV_TEST_ADMIN_DSN pointing to a new disposable cluster. Its test created and dropped a private database and passed all 10 in 6.16 seconds, exit 0. Evidence expiry beyond the adapter's final read while the caller retains an outer transaction remains unresolved (F3). The shared lock protects holder transfer through commit; A0/A7 evidence validity needs its own commit-time contract. ORM identity writers in src/saintvision/services/nodes.py and discovery.py also need classification against the authority domain.
