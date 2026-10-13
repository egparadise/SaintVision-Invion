---
doc_id: "HIST-20261014-CARD295-CODEX"
title: "Card 295 fully expired offline LAN pilot recovery"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-14T07:42:37+09:00"
updated: "2026-10-14T07:42:37+09:00"
source_of_truth: "Git"
---

# Card 295 fully expired offline LAN pilot recovery

## Selection and starting state

The user selected Option B from Card 294 on 2026-10-14: preserve the r2 identity and implement a
fully expired recovery protocol. The implementation base is train 70 candidate
`7c433080ab54f802c4e85f4851a037e86bc642fb`. The preserved state has one Node at the expired
Card 292 staged channel and one Node at its expired original channel; the global old Control Plane
leaf is also expired.

This card changes code, tests, and documentation only. It did not connect to or alter the LAN,
database, tunnel, Nodes, containers, volumes, certificates, journals, or operator-private files.
Docker Desktop was not used.

## Implemented recovery boundary

The new command is separate from the ordinary Card 293 path:

```text
prepare-fully-expired-leaf-rotation-recovery-batch
```

It requires every active old Node and CP leaf to be expired, then combines the exact external CA
and revocation registry, a strict private offline-authorization record, fresh CSRs from the
existing Node-local keys, the preserved CP key, the exact partial batch/journal, and locked DB
channel rows. Expired leaves are validated only as signed identity history. They never establish
TLS, sign an accepted receipt, or appear in the newly installed policy. The detailed authority
and crash model is in [[Card295_fully_expired_offline_recovery_설계]].

The output is schema v2. It contains one shared fresh CP leaf and one fresh leaf for each existing
Node key. The execution policy is fresh-CP-only from the first atomic write. Node receipts are
verified with fresh Node leaves, channels advance by exact `+1` CAS, the global CP switches only
after all Nodes stage, and final policies remain next-only. Old Card 292/293 public material and
journals are archived by exact digest; they are never silently cleared or edited.

## Regression evidence

The focused suite currently reports **40 passed**. The 2-Node end-to-end case proves preserved
private keys, one shared CP leaf, a crash after public material publication followed by exact
replay, both signed restart receipts, both monotonic channel stages, one global switch, and both
finalizations. Named negative cases cover authorization drift and duplicate keys, wrong CSR,
channel drift, chain drift, tenant/epoch drift, revocation, a not-yet-expired set, a mixed
live/expired set, a changed journal, and a concurrent writer. The ordinary Card 293 path remains
strict and rejects the all-expired fixture.

## Reviewed execution commands — recorded, not executed

First, the user performs exactly the two prerequisite package installs. A stale package index may
be refreshed on that host only; no broad upgrade is authorized.

```powershell
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 saintvision-invion@192.168.45.143 -- `
  sudo apt-get install -y python3.14-venv
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 inviz@192.168.45.210 -- `
  sudo apt-get install -y python3.12-venv
```

After independent review, landing, and a new explicit execution instruction, copy the approved
worker script and helper to each Node and create the isolated runtime before any recovery write:

```bash
bash deploy/lan/prepare-leaf-rotation-runtime.sh \
  /tmp/saintvision-card295-py \
  /tmp/saintvision-card295/worker_leaf_rotation.py \
  <optional-operator-wheelhouse>
/tmp/saintvision-card295-py/bin/python \
  /tmp/saintvision-card295/worker_leaf_rotation.py runtime-preflight
```

On each Node, generate a CSR from the existing private key. Transfer only the CSR to the Control
Plane; never copy `node-key.pem` away from the Node.

```bash
worker_root="$HOME/.local/share/saintvision/<NODE_ID>"
openssl req -new -key "$worker_root/node-key.pem" \
  -subj "/CN=<NODE_ID>" -out /tmp/saintvision-card295/node.csr
```

The operator-private offline-authorization JSON is stored below `.work/intranet/`, is a regular
non-symlink file, and contains the exact reviewed tenant/epoch, expired batch digest, old CP
identity, and sorted per-Node address/channel/identity rows. Its confirmation literal is
`fully-expired-offline-recovery-approved`. Do not print the file or its identity fields.

Prepare one replacement batch on the CP:

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py `
  --state .work/lan-5node/r2-7057dcd0 `
  prepare-fully-expired-leaf-rotation-recovery-batch `
  --expired-batch <exact-card292-or-card293-partial-batch> `
  --offline-authorization <private-offline-authorization-json> `
  --csr <first-node-csr.pem> --csr <second-node-csr.pem> `
  --output .work/lan-5node/r2-7057dcd0/rotations/<card295-batch> `
  --ca-key <operator-private-intermediate-key> `
  --ca-key-password-file <operator-private-password-file> `
  --ca-chain <operator-private-exact-chain> `
  --revocations <operator-private-revocations-json> `
  --overlap-seconds 14400 --leaf-valid-seconds 518400
```

Install the exact public sub-bundle on each Node. The staged Node names its exact old sub-bundle;
the untouched Node has no old Node journal to supersede.

```bash
/tmp/saintvision-card295-py/bin/python worker_leaf_rotation.py install \
  --bundle <card295-staged-node-public-bundle> \
  --supersede-expired-bundle <exact-expired-staged-node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/<STAGED_NODE_ID>"

/tmp/saintvision-card295-py/bin/python worker_leaf_rotation.py install \
  --bundle <card295-untouched-node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/<UNTOUCHED_NODE_ID>"
```

Return only the two signed restart receipt JSON files. Stage each through
`stage-leaf-rotation-batch`, commit once through `commit-leaf-rotation-batch`, restart observer and
serve against the same state without stopping or replacing the desktop-owned database tunnel, and
finalize each Node with its matching commit receipt:

```powershell
.\.venv\Scripts\python.exe tools/lan_pilot.py --state .work/lan-5node/r2-7057dcd0 `
  stage-leaf-rotation-batch --bundle <card295-batch> --node-receipt <first-receipt.json>
.\.venv\Scripts\python.exe tools/lan_pilot.py --state .work/lan-5node/r2-7057dcd0 `
  stage-leaf-rotation-batch --bundle <card295-batch> --node-receipt <second-receipt.json>
.\.venv\Scripts\python.exe tools/lan_pilot.py --state .work/lan-5node/r2-7057dcd0 `
  commit-leaf-rotation-batch --bundle <card295-batch> --output <private-commit-receipts-dir>
```

```bash
/tmp/saintvision-card295-py/bin/python worker_leaf_rotation.py finalize \
  --bundle <matching-card295-node-public-bundle> \
  --worker-root "$HOME/.local/share/saintvision/<NODE_ID>" \
  --commit-receipt <matching-control-plane-commit-receipt>
```

Operational acceptance requires both Nodes online/fresh with heartbeats after the single global
switch, exact incremented channel versions, next-only policies, and fresh leaf expiries. Any
failure stops at its journaled kill point; manual file edits, journal deletion, expired rollback,
and a second replacement batch are prohibited.

## Handoff

- Reviewer: Claude.
- Review focus: expired-history/live-authority separation, OOB authorization strength, exact
  staged/unstaged supersession, DB locks/CAS, crash replay, concurrent writer rejection, runtime
  gate, and the absence of private material.
- Live recovery remains forbidden until this PR is approved, landed, and followed by a separate
  explicit execution instruction.
