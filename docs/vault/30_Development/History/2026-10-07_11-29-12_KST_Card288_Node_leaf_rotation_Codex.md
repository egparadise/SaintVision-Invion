---
doc_id: "HIST-20261007-CARD288-CODEX"
title: "Card 288 Node and Control Plane leaf rotation"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-07T11:29:12+09:00"
updated: "2026-10-07T11:29:12+09:00"
source_of_truth: "Git"
---

# Card 288 Node and Control Plane leaf rotation

## Selection and scope

- Coordinator-assigned Card 288 is time-critical because the accepted Card 287
  Node leaves expire on 2026-10-13 at 02:04 UTC. The implementation is stacked
  on Card 287 head `1db671a182472d9ba5540ab5e1695c3beb7353fd` because both cards own
  `tools/lan_pilot.py` and the isolated LAN pilot contract.
- The implementation PR does not touch `.work/lan-5node/r2-7057dcd0`, any live
  Node, Docker Desktop, database, certificate, private key, DSN, or operator
  credential. Live rotation is a separate step after independent review.
- Node private keys remain generated and stored on the assigned Node. The CP
  accepts only a signed CSR for the already pinned public key and emits public
  material only.

## Implemented boundary

1. `prepare-leaf-rotation` requires the exact externally pinned issuing chain,
   its current revocation registry, a fresh current Node/control leaf, the exact
   DB channel pin, the exact peer policy, and a CSR that preserves the Node key.
   It rotates only inside a configurable safety window and fixes the target to
   `currentChannelVersion + 1`.
2. The public proposal binds tenant, Node, recovery epoch, Node address, old/new
   Node and control fingerprints, chain digest, validity/overlap windows, and the
   digest of every public file. A different chain, identity, key, digest, expired
   leaf, revoked current leaf, stale version, or second writer is rejected.
3. `worker_leaf_rotation.py install` validates the proposal against Node-local
   pinned material and the private-key public half. It backs up only public
   material, writes each replacement through flush/fsync/rename, journals the
   exact proposal, copies/verifies the material, and only then restarts. Exact
   retries resume; a different proposal cannot take over the journal.
4. The CP accepts only the exact Node-key-signed restart receipt and performs the
   existing channel-version CAS before durably replacing its public control leaf
   and the public Node/policy copies. The Node accepts only the exact
   control-key-signed CP commit receipt before reducing its bounded
   two-control-leaf overlap to the new control fingerprint.
5. Before CP commit, rollback can restore the exact prior public leaf/policy only
   while both remain valid. Expired public material is never restored. Kill
   points before install, after install, and before restart all recover by exact
   idempotent retry without changing the Node private key.

No migration, public HTTP route, product workload flag, or contract schema was
added. The existing operator-only channel authority remains the only DB mutation
boundary.

## Focused evidence

- `tests/test_lan_leaf_rotation.py`: short-lived leaf issue/install/finalize,
  exact key preservation, all three kill points, retry replay, fresh-only
  rollback, wrong Node, wrong chain, wrong key, stale version, expiry, concurrent
  writer, revoked registry, CSR-only prepare, and channel-CAS commit.
- Local focused result before commit: **16 passed** using the repository Python
  3.14 environment. No local Docker command was executed.
- The test suite uses synthetic keys and short-lived certificates in temporary
  directories. No private or live pilot value is recorded.

## Post-review operational commands

These commands are recorded but were not run. Replace angle-bracket inputs only
with operator-private paths. Keep the CSR and public receipts separate from all
private key/passphrase files.

Node, using its existing key:

```bash
openssl req -new -key "$HOME/.local/share/saintvision/$NODE_ID/node-key.pem" \
  -subj "/CN=$NODE_ID" -out "$HOME/.local/share/saintvision/$NODE_ID/leaf-rotation.csr"
```

CP prepare:

```powershell
py -3.14 tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  prepare-leaf-rotation `
  --csr <node-csr-file> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<rotation-id> `
  --ca-key <operator-private-intermediate-key> `
  --ca-key-password-file <operator-private-intermediate-password-file> `
  --ca-chain <operator-private-exact-node-chain> `
  --revocations <operator-private-revocations-json>
```

Node install and receipt:

```bash
python3 worker_leaf_rotation.py install \
  --bundle <public-rotation-directory> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID" \
  > node-rotation-receipt.json
```

CP commit and public commit receipt:

```powershell
py -3.14 tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  commit-leaf-rotation `
  --bundle .work/lan-5node/r2-7057dcd0/rotations/<rotation-id> `
  --node-receipt <node-rotation-receipt-json> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<rotation-id>/commit-receipt.json
```

Node overlap finalization, after the CP observer has been restarted from its
recorded command:

```bash
python3 worker_leaf_rotation.py finalize \
  --bundle <public-rotation-directory> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID" \
  --commit-receipt <commit-receipt-json>
```

If installation succeeded but CP commit was not attempted, and only while the
prior leaf/policy remain fresh:

```bash
python3 worker_leaf_rotation.py rollback \
  --bundle <public-rotation-directory> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID"
```

Acceptance of the later operational step requires a current mTLS heartbeat on
the new monotonic channel version and a finalized one-fingerprint policy. A
successful command or container restart alone is not acceptance evidence.

## Handoff

- Reviewer: Claude.
- Review focus: receipt trust boundary, filesystem crash points, CAS ordering,
  overlap/finalization, expired rollback refusal, and proof that the Node private
  key is neither read by the CP nor included in a public proposal.
