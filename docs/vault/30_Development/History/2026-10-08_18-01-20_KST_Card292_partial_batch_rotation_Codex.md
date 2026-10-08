---
doc_id: "HIST-20261008-CARD292-CODEX"
title: "Card 292 partial LAN leaf rotation evidence"
version: "1.0.0"
status: "blocked"
author: "Codex"
created: "2026-10-08T18:01:20+09:00"
updated: "2026-10-08T18:01:20+09:00"
source_of_truth: "Git"
---

# Card 292 partial LAN leaf rotation evidence

## Authorized operation and stop boundary

- The operator authorized the reviewed Card 291 batch rotation for the accepted r2 pilot state.
  This record contains only redacted state transitions; Node identities, certificate fingerprints,
  private keys, passwords, DSNs, and private paths are excluded.
- Read-only preflight observed two active and fresh Nodes, one shared next Control Plane leaf,
  exact per-Node CSR bindings, monotonic target channel versions, and an unchanged old global
  Control Plane leaf. Both CSRs were generated with the existing Node-local keys; only the CSRs
  reached the Control Plane.
- The first Node installed its public bundle, restarted, signed an installation receipt, and its
  channel CAS advanced by one. The private batch journal entered `staging` with one of two Nodes
  staged. The global Control Plane leaf remained old.
- The second Node failed before any Node state write. The executed worker source matched the
  accepted train source, but its isolated host runtime was Python 3.12.3 with cryptography 41.0.7.
  `worker_leaf_rotation.py` attempted to read `Certificate.not_valid_before_utc`, which is absent
  in that cryptography release. That Node retained its old leaf, old policy, old channel, and no
  rotation journal or backup.
- The operation stopped before the global switch. No batch commit, observer/serve restart,
  finalize, rollback, local Docker access, private-key transfer, or secret output occurred. The
  desktop-owned database tunnel remained running.

## Last read-only state and evidence boundary

At 2026-10-08 17:59 KST, before the overlap deadline, the private batch journal reported
`phase=staging`, `stagedNodeCount=1`, `expectedNodeCount=2`, and `globalControlLeaf=old`. The live
overview still reported both Nodes online and fresh with advancing heartbeats, and the database
tunnel remained listening. The overlap deadline was 2026-10-08 18:11:25 KST. This card did not
claim or measure either Node after that deadline.

The accepted design makes an expired overlap fail closed. After expiry the first Node's policy no
longer authorizes either the old or next Control Plane certificate even though both fingerprints
remain listed. Its DB channel already names the next Node leaf and target version, so restoring
only the old public files would contradict the channel CAS. The ordinary rollback does not undo
that CAS, while ordinary retry and finalize require a fresh overlap. Therefore no live recovery
was attempted without a separately reviewed recovery protocol.

## Handoff

Card 293 owns the read-only recovery analysis and product hardening. It must define an official
expired-partial-batch supersession path, verify the remote Python/cryptography runtime before any
Node mutation, remove dependence on an unverified system package set, and document why an overlap
deadline cannot be edited in place. Live recovery remains operator-authorized work after that PR
is independently reviewed and landed.
