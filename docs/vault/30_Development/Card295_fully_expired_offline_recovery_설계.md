---
doc_id: "CARD295-FULLY-EXPIRED-OFFLINE-RECOVERY-DESIGN"
title: "Card 295 fully expired offline LAN pilot recovery design"
version: "1.0.0"
status: "review"
author: "Codex"
created: "2026-10-14T07:42:37+09:00"
updated: "2026-10-14T07:42:37+09:00"
source_of_truth: "Git"
---

# Card 295 fully expired offline LAN pilot recovery design

## Decision and scope

The operator selected Card 294 Option B: preserve the r2 tenant, recovery epoch, Node identities,
Node-local private keys, database, containers, volumes, and state directory. This card adds a
separate `prepare-fully-expired-leaf-rotation-recovery-batch` protocol. It does not relax or route
through the ordinary Card 288, Card 291, or Card 293 preparation rules.

This change performs no live LAN operation. Live execution remains a separate post-review,
post-landing instruction. The desktop-owned database tunnel, Docker Desktop, remote containers,
volumes, and operator-private files are outside this implementation run.

## Authority model

An expired certificate is not authentication authority in this protocol. It is accepted only as
a signed historical identity record after all of the following independent authorities agree:

1. The exact external issuing chain is pinned by the r2 state and its private intermediate key is
   re-bound before new material is issued. The revocation registry must reject neither the
   historical identities nor the newly issued identities.
2. The old Control Plane certificate must be signed by that chain, carry the exact
   tenant/epoch/client-auth identity, be expired, and match the still-local Control Plane private
   key. It is never used for a TLS connection or an accepted restart receipt.
3. Every old Node certificate must be signed by the same chain, carry the exact
   tenant/epoch/Node/address/server-auth identity, and be expired. A fresh CSR generated on the
   Node must contain the same public key, proving possession of the preserved Node-local private
   key without exporting it.
4. A private, strict offline-authorization record under the operator-private boundary must bind
   the exact expired batch digest, tenant, epoch, old Control Plane identity, complete sorted Node
   set, addresses, database channel versions, and channel certificate identities. Unknown or
   duplicate JSON keys are rejected.
5. Under the single CP writer lock, each database channel is read with `FOR UPDATE`. Its exact
   version, certificate identity, expiry, enabled bit, and endpoint must match the authorization
   and the preserved Card 292/293 journal. The old staged and unstaged baselines are distinguished
   explicitly. Every row must already be expired.

Only after all five checks pass does the external CA issue one shared fresh Control Plane leaf and
one fresh leaf for each preserved Node key. The Node execution policy contains only the fresh CP
identity from its first write; the expired CP identity is not placed into an overlap set. The
field retained as `overlapExpiresAt` is therefore a bounded offline execution deadline, not a
period in which old authority is trusted.

## State machine and crash recovery

- Preparation replaces the exact incomplete v1 batch journal with a v2 recovery journal while
  holding the CP writer lock. A durable recovery record binds old batch, new batch, authorization,
  and the exact subset that had been staged.
- On the previously staged Node, `install --supersede-expired-bundle` validates and archives the
  exact old `restarted` journal and public bundle. An untouched Node has no old Node journal to
  archive. Both install only public material; neither bundle can contain a private key.
- The Node writes a new intent journal before replacing public material. A crash before intent,
  after intent, after public installation, after the installed journal, or before restart is
  replayed against the same rotation/proposal/channel tuple. A different tuple is refused.
- A signed restart receipt is checked with the newly issued Node leaf. Its database update is
  the unchanged monotonic `current version -> current version + 1` CAS. A poison, stale, or second
  writer cannot reuse a version.
- The global Control Plane leaf switches once, and only after the complete active Node set has
  staged exact receipts. Commit receipts are signed by the key of the fresh shared CP leaf. Each
  Node then converges to the same next-only final policy.
- Retrying preparation after the global switch replays the already bound recovery record and
  batch. It does not mint another authority. Rolling back to expired material is never allowed.

## Fail-closed matrix

The 2-Node fixture models one expired staged Node and one expired untouched Node. Focused tests
reject altered offline authorization, duplicate JSON keys, a CSR from another key, channel CAS
drift, external chain pin drift, tenant/epoch identity drift, revocation, a not-yet-expired batch,
a mixed live/expired channel set, a changed journal, and a concurrent writer. The success path
also kills the staged-Node install after public material publication and requires exact replay,
unchanged private keys, one shared CP leaf, complete staging, one global switch, and next-only
finalization.

Removing any of the corresponding comparisons makes at least one named boundary case accept an
invalid recovery or changes the success path, so the focused suite fails. The ordinary Card 293
command is also invoked against the fully expired fixture and must continue to reject it.

## Runtime and operational prerequisites

The existing runtime gate remains unchanged: Python 3.11 or newer, `cryptography==50.0.1` or
newer, and the UTC certificate APIs must pass before a Node state write. The reviewed helper
creates an isolated venv and does not replace a system Python package.

The user-owned prerequisites are:

```powershell
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 saintvision-invion@192.168.45.143 -- `
  sudo apt-get install -y python3.14-venv
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 inviz@192.168.45.210 -- `
  sudo apt-get install -y python3.12-venv
```

If a host reports stale package indexes, the user may run `sudo apt-get update` on that host and
repeat only its listed install. A broader package upgrade is not authorized.

## Acceptance and non-claims

Code acceptance requires the focused 2-Node and PKI pin suites plus hosted Backend/Core/Docs at
the exact PR head. It does not claim that the r2 pilot has recovered. Operational acceptance is a
later measurement requiring both Nodes online/fresh after the new global switch, post-switch
heartbeats, exact incremented channel versions, fresh leaf expiries, and redacted evidence. No
secret, DSN, private key, or certificate identity belongs in Git, console output, or PR comments.
