---
doc_id: "HIST-FLEET5-P0-PLAIN-PEER-PHASE-IMPLEMENTATION-001"
title: "FLEET5 P0 plain peer phase implementation and native proof candidate"
version: "1.0.0"
status: "in-progress"
author: "Codex"
reviewer: "Claude through root; implementation review pending"
updated: "2026-11-05T21:30:00+09:00"
source_of_truth: "Git"
---

# Authorized P0 implementation candidate

Owner Codex; task `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, Orca task
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`; branch
`agent/codex/fleet5-compute-storage-contract-20261105`; implementation base
`5023ce7d72b7f13431cb6a7182e2677eb6926662` (historical combined base
`0bcf9670d098fac87667fc9e2448b332db46e691`). Exact first-read document IDs,
versions, Index401/Codex362 and skill versions are in
[[2026-11-05_FLEET5_compute_storage_contract_Codex]] and its source inventory.

Root authorization `msg_340dea13aa6f`, clarified by `msg_31229a2b9a06`, follows
actual independent Claude architecture verdict
`f012b206f9505bf93fc5d57f7ca2713a68dbbb6f`, review task
`task_3529eefa626c / ctx_ba275b06ce0c`. The verdict accepts bounded plain P0
under M1–M10. It does not accept full compound B, implementation correctness,
physical cutover or five-PC acceptance. Existing 48-task/VFCL status is unchanged.

## Current implementation scope

- New closed normal `:3` uses independent actual peer P/P+1/P+2 and existing
  per-member C/C+1 CAS. Frozen raw hashes, previous public bytes and the signed
  current floor travel with the proposal. No CAS ladder or floor reset.
- A new Linux Go read-only CLI reads the existing journal floor and identity
  through no-follow bounded regular-file reads, checking UID/0600, exact keys,
  coherent rename observation, active policy hash/scope and the exact serving
  executable/process. It does not acquire the serving journal lock or initialize
  missing state. The Node signs a fresh independent nonce and actual observations.
  Old images lack this CLI and must refuse before normal renewal mutation.
- The default Python transport selects the exact owned Node container/volume,
  validates allowed plain mounts/arguments and fenced workspace predecessor,
  invokes the Go observer in that container and checks ownership again. Unknown
  consumers, storage configuration, contribution mounts and unsupported sockets
  refuse. An unsigned host mirror is never an alternate floor source.
- Durable publication intent precedes host/live peer-file exposure. Install and
  finalize use exact frozen phases; explicit rollback refuses after intent.
  Install receipts include signed actual pre/post floors; CP commit binds final
  P+2/hash. Final evidence and attestations bind actual final observations.
- Legacy live installation/rollback and in-flight conversion refuse. Exact
  finalized legacy archive verification and byte-preserving replay remain.
  Generic repair/workspace/execution/storage mutation paths refuse owned leaf
  rotation state. Expired/partial/unknown states remain blocked for separately
  reviewed offline recovery.
- Current standalone/package closure is five Python modules; Backend's exact
  module count and current tooling hash pairs are updated together, preserving
  the existing database-preparation pair and historical observations.

## Validation status and limits

The historical expected-red result remains immutable: Core `42014770700`, actual
Go same-version rejection, zero complete cycles; see
[[2026-11-05_FLEET5_compound_lifecycle_B_contract_Codex]]. The new fixed proof is
a separate early Core gate. It requires a real compiled Go process, real journal,
Node-signed observations, mTLS old/new narrowing, two complete normal cycles
7→8→9→10→11 and required negatives before returning zero. It substitutes only
Docker selection with an explicitly named native fixture adapter and reports
Docker ownership and PostgreSQL CAS as unassessed there. Main Core must then run
its provisioned integration checks; the early proof alone cannot represent them.

At 21:30 KST the initial focused Python command returned exit 1: 52 passed,
6 Windows-only symlink skips, one standalone file-count assertion still expected
the prior two-module closure. The assertion now derives the five-module count;
reverification, native CI, full relevant regression closure, independent code
review and root integration remain pending. No host Docker, WSL, real PKI,
remote Node, protected pilot, automation or Obsidian apply action was performed.

Root's later message `msg_61629794b86f` records its own 21:14:42 KST scheduler
HOLD action. Earlier unchanged-scheduler observations stay historical; this worker
performed no scheduler action and does not claim the old three remain globally
unchanged after that root action.

Next owner Codex: obtain exact-head fixed native evidence, close regressions and
deliver source/CI bindings for actual independent Claude implementation review.
Root retains physical/bootstrap/runtime-image migration and full program
acceptance ownership; this derivative is not integrated or accepted hardware.
