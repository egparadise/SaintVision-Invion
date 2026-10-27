---
doc_id: "HIST-20261027-R4-LIVE-CODEX"
title: "Fresh isolated r4 LAN pilot live acceptance"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-27T12:45:29+09:00"
updated: "2026-10-27T12:45:29+09:00"
source_of_truth: "Git"
---

# Fresh isolated r4 LAN pilot live acceptance

## Authority and redaction boundary

The operator explicitly approved a fresh isolated r4 connection after merge train 77 was judged
landable. The executed source was exact commit
`e86064239e219394e24831acc78ee01ef4a29bfd`. The prior r2 and r3 states, databases, roles,
journals, containers, volumes, and Node keys were not modified or deleted. The desktop-owned
loopback database tunnel remained running throughout, and Docker Desktop was not used.

This record omits account and Node identities, addresses, private paths, database credentials,
DSNs, certificate fingerprints, and all private-key material. It records only redacted control
results required for independent review.

## Execution and recovery record

1. Read-only port checks found the originally proposed Node port already owned by an older pilot.
   The coordinator fixed a port that was unused on both Nodes; the bootstrap rechecked it before
   any Node write. The Control Plane download port was also free.
2. An initial database attempt targeted an obsolete stopped pilot instance and was stopped without
   starting or changing it. Read-only ownership, image, and network measurements identified the
   active hardened PostgreSQL instance. A distinct r4 database and least-privilege runtime role
   were then created there; the older pilot namespaces remained untouched.
3. The generated r4 DSNs initially encoded a Windows passfile with backslashes. The repository
   parser rejected that form before `init`. Only the two new r4 DSNs were rewritten with an
   absolute forward-slash path and revalidated. The empty r4-owned state directory left by the
   rejected attempt was confirmed empty before retry. `init` and `bind-db-auth` then passed.
4. An exact Git archive of the train 77 source was built into the Linux Node image on an approved
   Linux host. The public image archive and inspect receipt matched out-of-band SHA-256 values.
   The bundle emitted exactly two Node-specific worker archives.
5. Two local orchestration assertions initially treated a JSON array as one element. The first
   stopped before Node write and the second before certificate issuance. After correcting those
   r4-only command wrappers, each Node received only its own archive and verified its SHA-256.
6. Each Node generated its private key locally and returned only a CSR. Repository enrollment
   validated the external chain, fixed peer subject, exact Node URI and IP SANs, CSR public-key
   match, and validity window. Each public certificate was returned only to its matching Node and
   verified out of band. Both `finish-worker.sh` runs passed; no private key left a Node.
7. The first desktop cutover attempt stopped before listener mutation because its temporary
   worktree was not attached to the repository that owns the reviewed `.venv` and web dependency
   tree. An exact train 77 worktree under the correct Git common directory passed that gate.
   The cutover then stopped only the owned prior console/web listeners and the temporary r4
   serve/observer, preserved the database tunnel, and restarted all r4 processes from exact train
   77. The owned shortcut was replaced only after the two-Node acceptance passed.

## Final measured state

- The loopback overview reports `source=live-postgresql-mtls`.
- Exactly two r4 Nodes are `online` and `fresh`; both heartbeats advanced after successful
  enrollment and finish.
- Web `3000`, overview `18082`, and database-forward `55448` each have one loopback-only listener.
  The desktop shortcut points to the r4 state and contains no r3 state argument.
- Both database channel rows are enabled at monotonic **version 1**.
- The Control Plane leaf expires **2026-11-02 12:32:25 KST**. The two Node leaves expire
  **2026-11-02 12:37:16 KST** and **2026-11-02 12:37:19 KST**.
- Workload execution remains disabled; this procedure established observation only.

## Approved next rotation window

The operator separately authorized an automatic renewal attempt about two days before leaf expiry,
using only the already reviewed batch-rotation implementation. The earliest safe start time is
**2026-10-31 12:32:25 KST** and the reviewed overlap is **4 hours**. The attempt must stop and
report on any failed gate; it may not introduce new code or manually edit a journal. The pinned
standalone runtime now supplies the Node cryptography dependency without `sudo`, venv creation,
pip, or Internet access, and must pass its exact-wheel/runtime preflight before any rotation write.

## Review handoff

Reviewer: Claude. Confirm the exact train 77 source, r2/r3 non-interference, the Node-local-key and
CSR-only boundary, the listener/tunnel ownership transition, the two enabled channel-version rows,
the three public expiry timestamps, and the renewal start/overlap calculation.
