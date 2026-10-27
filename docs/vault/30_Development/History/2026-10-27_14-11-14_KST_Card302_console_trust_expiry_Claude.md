---
doc_id: "HIST-20261027-CARD302-CLAUDE"
title: "Card 302 console certificate expiry and renewal window"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-10-27T14:11:14+09:00"
updated: "2026-10-27T14:11:14+09:00"
source_of_truth: "Git"
---

# Card 302 console certificate expiry and renewal window

## Why

r3 went silent when its leaves expired on 2026-10-23 and the console said only `untrusted`.
The screen carried no answer to the two questions an operator actually has: how long is left,
and when does the approved automatic renewal start. Both values were already being read from
the database on every request and then thrown away.

## Scope

`tools/lan_console.py` only: `node_view()`, `snapshot()`, and one module-level helper that
`snapshot()` delegates to. No new SQL, no new data source, no new file read. The projection
uses exactly the two values already selected — `inv.node_channels.certificate_not_after` for
the row's current channel and the connection's `clock_timestamp()`. No private state, key or
pgpass file is read; `load(path)` is the pre-existing state read and is unchanged. Existing
fields, the `status` ladder, the loopback-only bind and the `Cache-Control: no-store` header
are untouched. The live console was not restarted.

## The contract as delivered

Per node, beside the other observation stamps:

- `certificateNotAfter`: ISO-8601 **UTC** string, or `null` when the row has no current
  channel certificate. Published for every node, not gated on `channel_enabled`, so a
  revoked channel still shows the certificate it last held.

Top level, beside the other observations:

- `trust.earliestCertificateNotAfter`: ISO-8601 UTC, or `null`
- `trust.renewalWindowStartsAt`: ISO-8601 UTC, or `null` — `earliest − 172800s`, the
  operator-approved "about two days before expiry" lead
- `trust.secondsUntilEarliestExpiry`: number, never negative, `0` once expired, `null` when
  unknown. Rounded to one decimal, matching the file's existing `observationAgeSeconds`
- `trust.state`: `ok` | `renewal-window` | `expired` | `unknown`

The aggregate counts **only enabled channels with a non-null certificate**; with none it is
`unknown` and all three stamps are `null`. Boundary conventions follow the existing
`node_view` trust test (`certificate_not_after > now`): exactly at the window start is inside
the window, and exactly at expiry is `expired`.

## A correction to the card's premise, and what it means for the screen

The card stated that `certificate_not_after` is recorded as `min(Node leaf, CP leaf)` by batch
rotation, citing `tools/lan_pilot.py:1726` and `:1845`, and asked me to confirm it. **It is
not.** Measured:

- those two lines do compute `not_after = min(next_node.not_valid_after_utc,
  next_control.not_valid_after_utc)`, but the value is a local that bounds the rotation
  window — `overlap_expires = min(now + overlap_seconds, not_after)` — and goes into the
  overlap/execution policy, not into the channel row;
- the column is written only by `provision_channel()` in
  `services/control-plane/src/inv/node_channels.py:184`, from
  `fingerprint, not_after = certificate_identity(certificate_der, node, epoch)`, and
  `certificate_identity` returns `cert.not_valid_after_utc` of the **Node** certificate.

So the column is the current channel's own Node leaf expiry. This is not academic: in the
live r4 state the Control Plane leaf expires at 12:32:25 KST while the two Node leaves expire
at 12:37:16 and 12:37:19 KST, so the Control Plane leaf is the earliest by about five
minutes. mTLS needs both ends valid, so trust breaks when the earlier of the two expires —
which these fields cannot see. They will therefore **overstate** remaining trust whenever the
Control Plane leaf is the earlier one, and a renewal keyed only to them would start late.

I implemented the contract as specified rather than redefining it, because Gemini's Card 303
is building the screen to this shape. The field names stay; what changed is that their
meaning is now documented precisely, in the helper's docstring and here. Two consequences
worth routing:

1. The screen should say "Node certificate" rather than "certificate", or the operator will
   read a number that is right about the Nodes and silently wrong about the path.
2. Surfacing the Control Plane leaf needs a data source this card is not allowed to use — it
   lives in the state directory's `control-cert.pem`, not the database. That is a follow-up
   card, and until it exists the renewal window should be treated as an upper bound.

## Verification

- `pytest tests/core/test_lan_console_trust.py tests/core/test_lan_console.py -q` —
  **23 passed**. The pre-existing console file is unchanged and still passes.
- Wider run including the launcher boundaries: **42 passed, 12 skipped**; every skip is a
  pre-existing "launcher prerequisites absent" guard for this worktree, not a new one.
- **Each new test proved to be a witness.** Nine plausible wrong versions of the projection
  were applied one at a time to the product file and each was caught by the new file while
  the pre-existing console file kept passing: an exclusive window start, an exclusive expiry
  boundary, a missing non-negative clamp, counting disabled channels, letting a null
  certificate reach `min()`, a one-day instead of two-day lead, publishing a session offset
  instead of UTC, and omitting either the aggregate or the per-node field. **9/9 caught, 0
  collateral.** The file was restored and byte-compared after every mutation.
- The snapshot-level test drives the real `snapshot()` with a fake connection that supplies
  rows only; every assertion is on what the product projects. It also asserts the statement
  count is still **five** and that `certificate_not_after` appears in exactly one of them, so
  "no new SQL" is enforced by a test rather than by inspection.

## Next

- First action: open the PR and route it to Codex.
- Owner for the follow-up decision: coordinator — whether to raise a card for the Control
  Plane leaf expiry, which is the half of the trust path these fields cannot reach.
- Then Card 305, the 48-task rescore v1.21 over trains 67–78 with r4 live reflected.
