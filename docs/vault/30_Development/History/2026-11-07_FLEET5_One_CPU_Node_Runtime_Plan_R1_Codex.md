---
doc_id: "HIST-FLEET5-ONE-CPU-NODE-RUNTIME-PLAN-R1-20261107-CODEX"
title: "Fresh one CPU Node runtime plan R1"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-07T15:50:02+09:00"
source_of_truth: "Git"
---

# Fresh one CPU Node runtime plan R1

Finite card FLEET5-ONE-CPU-NODE-RUNTIME-PLAN-R1-20261107, parent task_a8fd2969f0b3, dispatch ctx_6f0f8253b8a7; owner Codex, reviewer Root Codex (actual plan review pending).
Branch agent/codex/fleet5-one-cpu-node-runtime-plan-r1-20261107 starts at docs delivery base b51d827e507a35aca3737e31103bd3b3311298a5.
Product source target is separately 1efea494f026e932360c35ae811b6423d874a2e7; this branch does not include that candidate and changes no production source.
Root public inputs are immutable commit ae211280c5c8ab50b19303450288ba1421af827e; no private configs/certificates/keys/incident logs or runtime data were read.

## Plan and source proof

[Runtime plan](../Evidence/fleet5-one-cpu-node-runtime-plan-r1-20261107-codex/runtime-plan.json) gives public identifiers, pending slots, ordinary serve argv, PKI roles, peer-policy/profile/workspace/worker shapes, admission/uncertain-commit disposition, scoped observation and first Workspace entrypoints.
[Source bindings](../Evidence/fleet5-one-cpu-node-runtime-plan-r1-20261107-codex/source-bindings.json) pins 38 immutable source bindings with Git blobSHA1/fileSHA256/line-excerpt hashes, cross-branch GitHub links, six contract shapes, seven public input hashes and 14 first-read doc/version/hash/KST pins.
Canonical Root boards were Index1.0.508/Codex1.0.469; agent-delivery1.1.0/core-reliability1.0.0 apply. Shared boards/registry/ADRs/source originals were not edited.

Ordinary serve requires peer-policy and mTLS; optional K2 floor observation remains NULL/HOLD.
Node channel pins the Node leaf DER hash; peer-policy allowlists CP-client DER hashes.
Launch signing is a separate Ed25519 pair (CP PEM private, Node raw32 public).
Ordinary CPU observation uses pinned mTLS plus nonce/epoch/channel checks, without an application signature.
Configured500CPU-millis/64MiB metadata, profile policy, observed capacity, leases and actual Docker limits differ.
Client API cap1.45 means observed Docker maximum1.56 alone is insufficient without MinAPIVersion.
Current public API shape has workspace absent; nodes/capacity routes are independent, but first Workspace needs trusted runtime, correct business intent and two actual distinct nonrequester approvals.
Tenant-wide observer/delivery entrypoints need Root scope disposition; a scoped observation library entrypoint is identified separately.

## Verification and delivery

Adjacent static-verification and local-gates receipts record exact commands/exit/environment and checks.
Publication receipt after commit will bind exact planSHA, normal push and one unique correlated docs.yml; no post-CI commit loop.
No Core/Backend/Frontend fanout, product import/execution, crypto generation, compiler/Go/pytest, DB/SSH/Docker/install/start/PKI/config/workload/browser actions occurred.
Obsidian is CHECK only, full canonical state before/after preserved; no apply/export/adopt/resolve/state write.
Old untracked task receipts remain untouched and will not be staged.

## Next owner and disposition

Root Codex reviews the source-bound plan and binds actual DB/auth/CA/client/leaf/signer/profile/image/policy/deployment privately.
Root then controls fully bounded admission and actual runtime/observation/approved Workspace operation.
Pending values stay ROOT_PENDING/NOT_BOUND; authority null, admission/observations/Run NOT_RUN, whole program/fivePC acceptance incomplete.
This finite plan delivery does not settle broader B work or discharge any operational HOLD.
