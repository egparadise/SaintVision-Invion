---
doc_id: "HISTORY-FLEET5-E1-20261119"
title: "FLEET5 PC1 enrollment reservation prerequisite"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-19T07:58:00+09:00"
source_of_truth: "Git"
---

# E1 PC1 reservation

Task task_bb73ee7201bc, branch agent/codex/task_bb73ee7201bc, base 433ea326a29b8afe9edc8bfa5f8fed525ea69bb5. Codex owns implementation. Coordinator assigns independent reviewer. Start 2026-11-19 07:52 KST. INDEX-PROGRESS-001 v1.0.389, WORKBOARD-CODEX-001 v1.0.350, delivery v1.1.0 and core reliability v1.0.0.

The R2 fixture is copied from p14 at 14ddc8e9. A1 e2f0cac3df21c333bbc03f80e683d2ac7eaad2c9 reviewed at cfbd678cadbd9dd5a46d2278a357b3985e56f9e8 demonstrates single-host synthetic custody. Coordinator confirmed its scope. A1 owner contacted via ctx_21bada8e3b1e. No production provider is wired. The disposable adapter locks its authority row before validating holder, generation and the full approved R2 binding. Reservations commit in the caller transaction. Rows are unique by tenant/PC, tenant/node and tenant/request, including across epochs.

The current supported recovery schema is 0067_audit_reader_revoke. Incrementing Alembic head would invalidate existing exact-head consumers. Candidate storage lives outside migration discovery and needs a reviewed installation, access policy and migration decision. The existing lan_pilot row writer does not participate in this protocol. Operational admission stays on HOLD until all competing writers use a shared authoritative transaction, with verified A7, current inventory including retired rows and PC1 empty-state evidence.

Windows disposable PostgreSQL 18.6, Python 3.10, psycopg 3.3.4. Fresh database, synthetic R2 binding. Command python -m pytest -q tests/core/test_e1_reservation.py returned 0 (2 passed). Exercised simultaneous connections, request replay, conflict, changed approved binding, stale generation, missing fence and rollback. Next owner is the shared fleet authority owner. Independent review, hosted CI and operational acceptance pending.

## Follow-up on preflight msg_0a100db83cf3

Task task_3cfbc21d5762 continues on the existing E1 branch and integration base 433ea326. The PC1/PC5 preflight report supplied the requirements. Its earlier integration SHA is superseded. A1 owner receipt msg_8965382a5e23 confirms at 3988ecd7 that A1 supplies neither a shared PostgreSQL fence nor an E1 migration slot. Migration coordination request msg_1b59adbc6081 remains open. No migration number allocated.

The trusted adapter must provide evidence under the tenant lock, refreshed on both reads. Production has no adapter. Synthetic PostgreSQL verifies eligibility from the complete ordered history, including retired/disabled identities, signed CSR and derived SPKI, rotation keys, preserved epoch and committed A7 for the same plan and manifest. A tenant-scoped immutable E1 audit and reservation commit or roll back together. Exact replay checks both. Lost-ack reconciliation uses a fresh read-only repeatable-read transaction. Real kernel migration tables from 0001 through 0005 supplied the node, channel, channel audit and resource snapshots. Non-bypass-role RLS reads and cross-tenant inserts are tested. Raw node evidence, signer access and enrollment were outside this run.

P14 fixture issue: its published rowsReadbackSHA256 is 5091dd3e3200648bf983c23a869ddc0065590e64bcc4b6b8478804a87c2a7479. Canonical JSON of its supplied rows hashes to f48cc8e3fafd0e69521afd3ecf7a75439f574151296735cde4dc30b7ad0d1476. The unmodified fixture is a negative case. Disposable positive cases explicitly use the recomputed value. The A0 owner must define and authenticate the canonical readback bytes, history completeness and freshness. The A1 owner must supply the fence, authenticated tenant binding and shared journal, then coordinate an E1 migration. Current tested adapter and audit are isolated candidates only.
