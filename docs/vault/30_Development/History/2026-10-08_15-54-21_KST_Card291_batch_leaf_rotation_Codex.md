---
doc_id: "HIST-20261008-CARD291-CODEX"
title: "Card 291 multi-Node leaf rotation batch"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-08T15:54:21+09:00"
updated: "2026-10-08T15:54:21+09:00"
source_of_truth: "Git"
---

# Card 291 multi-Node leaf rotation batch

## Selection and measured defect

- The coordinator assigned Card 291 after the approved Card 288 operational preflight stopped
  before mutation. The accepted train 68 candidate
  `d5fa830f55ae464ba97049b6c95861b715fcf943` is the base.
- Read-only preflight found two active, fresh Nodes that trust one current Control Plane leaf.
  Card 288 prepared a new Control Plane leaf inside each per-Node proposal, committed that
  proposal by replacing the single global `control-cert.pem`, and finalized each Node to only its
  proposal fingerprint. With two Nodes, committing the second proposal would therefore disconnect
  the first finalized Node.
- The live r2 pilot state, both Nodes, channel rows, DB tunnel, observer, and every certificate
  remained unchanged. No rollback was needed. This PR is implementation and synthetic evidence;
  the approved live operation remains a separate post-review step.

## Implemented batch boundary

1. `prepare-leaf-rotation-batch` requires exactly one CSR for every active Node and reuses Card
   288's exact current leaf, Node key, issuing chain, revocation, address, tenant, recovery epoch,
   peer-policy, channel-version, safety-window, and expiry checks. It issues exactly one next
   Control Plane leaf and binds every per-Node public bundle to the same batch ID and fingerprint.
   No Node private key is accepted or emitted.
2. The old single-Node prepare and commit commands fail closed when the state has multiple active
   Nodes. A strict batch manifest binds the sorted complete Node set, every proposal digest,
   monotonic channel versions, exact shared old/new Control Plane fingerprints, issuing-chain
   digest, overlap deadline, and certificate deadline. An active private-state journal rejects a
   different concurrent batch; an exact retry reuses the published next Control Plane leaf.
3. Each Node installs its ordinary Card 288 bundle first, atomically enters the old+next overlap
   policy, restarts, and signs its exact receipt. `stage-leaf-rotation-batch` then performs only
   that Node's channel CAS and durable stage journal update. It does not replace the global Control
   Plane leaf or reduce any policy.
4. `commit-leaf-rotation-batch` refuses until every Node is staged and every channel row still
   matches its target certificate and version. Only then does one atomic write switch the global
   Control Plane leaf. The CP records the switched phase, updates its public Node copies, and emits
   one exact signed commit receipt per Node. Each Node then uses the unchanged Card 288 `finalize`
   command to reduce its overlap policy to the shared next fingerprint.
5. A failure after one Node stage, a missing/failed second Node install, or the injected kill
   immediately before the global switch leaves the old global leaf byte-for-byte unchanged.
   Already installed Nodes still accept that old fingerprint. A failure immediately after the
   atomic switch is replayable because all Nodes already accept next.

## Previous test gap and mutation evidence

Card 288 exercised only one configured Node in the CP prepare/commit fixture. It proved per-Node
CAS and crash recovery but never compared two proposal Control Plane fingerprints and never
asserted that the global leaf remains old between the first and last Node CAS. That gap allowed the
per-Node global overwrite defect to survive review.

`tests/test_lan_leaf_rotation.py` now creates two independently keyed Nodes. These direct
reversions fail:

- issuing a Control Plane leaf inside the per-Node loop breaks the one-value fingerprint/public
  byte sets and the strict batch loader;
- switching `control-cert.pem` during the first Node stage breaks the exact-byte assertion after
  the first stage and the one-Node-failure case;
- permitting commit before all restart receipts/channel CAS operations breaks early refusal;
- removing the immediate pre-switch kill boundary breaks the simulated-crash assertion; and
- accepting a different output while an active journal exists breaks concurrent-writer refusal.

Focused local evidence is **54 passed, 1 declared POSIX-only skip** across
`tests/test_lan_pilot_multinode.py`, `tests/test_lan_leaf_rotation.py`, and
`tests/test_intranet_pki.py`; the leaf-rotation file is **23 passed**. No local Docker command ran,
and no private value was printed or committed.

## Post-review live rotation procedure

These commands are recorded but were not run by this card. Inputs in angle brackets remain in
operator-private storage or Node-local state. Generate each CSR on its own Node with its existing
key; transfer only the CSR to the CP.

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  prepare-leaf-rotation-batch `
  --csr <first-node-csr.pem> `
  --csr <second-node-csr.pem> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<batch-id> `
  --ca-key <operator-private-intermediate-key> `
  --ca-key-password-file <operator-private-intermediate-password-file> `
  --ca-chain <operator-private-exact-node-chain> `
  --revocations <operator-private-revocations-json>
```

For each Node, transfer only its `nodes/<node-id>` public subdirectory, run the reviewed installer
with its existing Node-local key, and return its signed receipt:

```bash
python3 worker_leaf_rotation.py install \
  --bundle <node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID" \
  > node-rotation-receipt.json
```

Stage every receipt. The global Control Plane leaf remains old after each command:

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  stage-leaf-rotation-batch `
  --bundle .work/lan-5node/r2-7057dcd0/rotations/<batch-id> `
  --node-receipt <node-rotation-receipt.json>
```

After all Nodes are restarted and staged, perform the one global switch:

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  commit-leaf-rotation-batch `
  --bundle .work/lan-5node/r2-7057dcd0/rotations/<batch-id> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<batch-id>/commit-receipts
```

Restart observer/serve from the recorded r2 state command so it loads the new public CP leaf.
Then finalize each Node with its own sub-bundle and matching receipt:

```bash
python3 worker_leaf_rotation.py finalize \
  --bundle <node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID" \
  --commit-receipt <matching-node-commit-receipt.json>
```

Acceptance still requires both exact Nodes online and fresh on the new monotonic channel versions,
both policies reduced to the same next-only Control Plane fingerprint, and the new expiry recorded
in redacted evidence. Expired material is never accepted; before the global switch, only Card
288's fresh exact rollback remains available.

## Handoff

- Reviewer: Claude.
- Review focus: shared-leaf uniqueness, complete active-Node set, stage/commit ordering,
  pre/post-switch crash recovery, concurrent batch refusal, and preservation of every Card 288
  identity and expiry check.
