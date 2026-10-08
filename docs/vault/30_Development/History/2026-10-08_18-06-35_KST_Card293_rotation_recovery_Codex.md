---
doc_id: "HIST-20261008-CARD293-CODEX"
title: "Card 293 expired partial leaf rotation recovery"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-08T18:06:35+09:00"
updated: "2026-10-08T18:06:35+09:00"
source_of_truth: "Git"
---

# Card 293 expired partial leaf rotation recovery

## Measured starting state and selection

Card 292 stopped the live operation with one Node installed/restarted/staged and one Node
untouched. The staged Node has the first batch's next Node leaf and its DB channel CAS is already at
the target version; its overlap policy expires without a global Control Plane switch. The second
Node and global Control Plane retain their old material. This PR performs no live mutation.

The ordinary Card 291 commands cannot safely continue after expiry:

- `worker_leaf_rotation.py` rejects an expired overlap in `validate_bundle()`;
- `stage_leaf_rotation_batch()` rejects a receipt after the overlap deadline;
- `finalize()` also validates the still-open overlap before narrowing it; and
- Node rollback restores files only. It cannot undo the already committed DB channel CAS, so a
  staged-Node rollback would make the Node files disagree with the channel authority.

## Recovery choice

### A. Selected: formally supersede the expired batch, then rotate every Node in one fresh batch

`prepare-leaf-rotation-recovery-batch` accepts only an expired, incomplete `staging`/`staged`
journal whose global Control Plane leaf is still the exact old leaf and whose leaves remain valid.
It locks the pilot state and re-reads every channel row. A previously staged Node must still be at
the old batch's target version and next certificate; an untouched Node must still be at its old
version and certificate. Any other state is refused.

The command archives a redacted old-to-new batch binding, replaces the active CP journal with a
fresh complete-Node batch, and issues one new shared Control Plane leaf plus one new Node leaf per
Node. The staged Node's old-batch next leaf/version becomes the new batch's current leaf/version;
the untouched Node retains its own old baseline. Every CSR must still match the respective
Node-local key. No private Node key enters the Control Plane.

On the previously staged Node, `install --supersede-expired-bundle` requires the exact old and new
bundles together. It accepts only an old `restarted` journal, expired overlap, still-valid installed
leaf, byte-identical expired overlap policy, same tenant/Node/epoch/CA, unchanged old global CP
authority, and a new manifest whose current leaf/version exactly equal the installed old-batch
target. It durably archives the old journal before the fresh install. A crash after archive and
before the new intent is replayable because the public files still match the fresh manifest's
declared base. The untouched Node uses ordinary `install`.

After both fresh receipts are staged, the unchanged Card 291 complete-set gate performs one global
switch and both Nodes finalize next-only. Estimated operator time after CSR and wheelhouse inputs
are ready is 15–28 minutes: runtime preparation 5–10, recovery prepare/transfer 3–5, two installs
and stages 5–8, and global switch/finalize/observation 3–5.

### B. Rejected: re-enroll only the staged Node in the same state

Card 287 bootstrap enrollment does not model a mixed partial-rotation journal. Re-enrolling only
one Node would have to bypass or rewrite its already advanced channel, expired policy floor, and
Node rotation journal while the complete active-Node batch journal remains authoritative. The
existing key can be preserved by CSR, but the same-state identity/channel history cannot be
preserved by the enrollment command. A separate new pilot state would abandon the accepted state
and does not repair this one. This is therefore not an approved recovery path.

### C. Rejected: edit the expired policy, clear journals, or roll back only files

An overlap extension changes policy bytes already pinned by the proposal digest, batch digest,
Node journal, receipt, and CP journal. Reusing the same channel version with different bytes also
violates the Node's durable version/hash floor. Clearing journals loses the concurrent-writer and
crash-recovery proof. File-only rollback contradicts the staged DB CAS. None of these manual paths
is allowed.

## Runtime preflight and bounded overlap

The failed Node used Python 3.12.3 with cryptography 41.0.7; the accepted source reads the UTC
certificate properties supplied by cryptography 50.0.1. `runtime-preflight` now verifies Python
3.11+, cryptography 50.0.1+, and both UTC certificate APIs before any state write. Every install,
finalize, and rollback invokes that gate too.

`deploy/lan/prepare-leaf-rotation-runtime.sh` creates an isolated Node-local venv and installs the
exact repository pin `cryptography==50.0.1`; it never changes the system interpreter. An optional
operator-provided wheelhouse makes the install offline and exact-version. The same absolute venv
interpreter must run preflight, install, and finalize.

The default overlap changes from 15 minutes to four hours, with a six-hour hard maximum and a
ten-minute minimum remaining window for recovery generation. Four hours covers remote package
preparation, two sequential restarts, receipt transfer, and an operator pause while still bounding
the period in which the prior CP leaf is accepted. The deadline remains immutable after prepare;
extension requires the reviewed supersession protocol above, never an in-place edit.

## Post-review recovery commands — recorded, not executed

First prepare and verify the same isolated runtime on every active Node, before creating any new
certificate material:

```bash
bash deploy/lan/prepare-leaf-rotation-runtime.sh \
  /tmp/saintvision-leaf-rotation-py \
  /tmp/saintvision-rotation/worker_leaf_rotation.py \
  <optional-operator-wheelhouse>
/tmp/saintvision-leaf-rotation-py/bin/python \
  /tmp/saintvision-rotation/worker_leaf_rotation.py runtime-preflight
```

Generate a fresh CSR on each Node with its existing Node-local key and transfer only the CSRs.
Then supersede the expired batch on the CP:

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  prepare-leaf-rotation-recovery-batch `
  --expired-batch .work/lan-5node/r2-7057dcd0/rotations/<expired-batch> `
  --csr <first-node-csr.pem> --csr <second-node-csr.pem> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<recovery-batch> `
  --ca-key <operator-private-intermediate-key> `
  --ca-key-password-file <operator-private-password-file> `
  --ca-chain <operator-private-exact-chain> `
  --revocations <operator-private-revocations-json>
```

Install the fresh bundle on the previously staged Node with the exact expired sub-bundle, and use
ordinary install on the untouched Node:

```bash
/tmp/saintvision-leaf-rotation-py/bin/python worker_leaf_rotation.py install \
  --bundle <recovery-node-public-bundle> \
  --supersede-expired-bundle <expired-node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID"

/tmp/saintvision-leaf-rotation-py/bin/python worker_leaf_rotation.py install \
  --bundle <recovery-node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/$NODE_ID"
```

Return only the signed receipts, stage both with `stage-leaf-rotation-batch`, commit once with
`commit-leaf-rotation-batch`, restart observer/serve without stopping the desktop-owned DB tunnel,
then run `finalize` on each Node with its matching commit receipt. Acceptance requires both Nodes
online/fresh with heartbeats after the switch, exact new channel versions, next-only policies, and
the new expiry in redacted evidence. These commands require a new explicit operator approval.

## Regression evidence

The focused suite covers the measured cryptography 41.0.7 rejection before mutation, isolated
runtime pin, mixed channel baselines, exact old/new supersession, wrong policy and channel drift,
crash after old-journal archive, one shared fresh CP leaf, and bounded defaults. Reverting the
runtime version gate, mixed-channel comparison, expired-policy byte comparison, journal archive,
or four-hour bounded default makes a focused assertion fail. Local Docker was not used.

## Handoff

- Reviewer: Claude.
- Review focus: mixed channel authority, old/new journal binding, crash replay, inability to use
  file-only rollback, runtime preflight before mutation, and the four-hour/six-hour risk boundary.
- Live recovery remains blocked until this PR is independently approved and the operator issues a
  separate execution instruction.
