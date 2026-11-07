---
doc_id: "HISTORY-FLEET5-CURRENT-THREE-NODE-RENEWAL-PLAN-REVIEW-R1-20261108-CLAUDE"
title: "Current three-Node pilot renewal plan review R1"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08"
source_of_truth: "Git"
---

Task FLEET5-CURRENT-THREE-NODE-RENEWAL-PLAN-ACTUAL-CLAUDE-REVIEW-R1-20261108 (Orca task_f69368c7f664, dispatch ctx_a4e143e61944), started 2026-11-08 07:37 KST. Claude is the actual independent reviewer, the author is Codex task_8298b23be39f, and Root is the sole APPLY/SSH/credential/operator owner.

Targets:
- **Original plan:** PLAN-FLEET5-CURRENT-THREE-NODE-RENEWAL-R1 v1.0.0 at `a3c6984fa25c6cf179827e15e4259000e7bd294e` (parent abb707, 28 docs-only files).
- **Root537 management copy:** v1.0.1 at `a2d7977196363955de0cdc9dd1a412e1c5297199`.
- **Source revisions:** runtime `1efea494`, API `96afd799`. Every cited blob is byte-identical on this branch.

Review branch: `agent/claude/fleet5-current-three-node-renewal-plan-review-r1-20261108`, created from my prior head `29046535c0bb0e2629286c8c678f563080f30a67`. Pins and per-area reasoning are in [review](../Evidence/fleet5-current-three-node-renewal-plan-review-r1-20261108-claude/review.json), and the blobs read are in [read pins](../Evidence/fleet5-current-three-node-renewal-plan-review-r1-20261108-claude/read-pins.json).

**Verdict: REQUEST_CHANGES, mandatory blockers 2 (F1, F2).** The HOLD decision itself is correct.

**Root537 adaptation: verified as citation-only.** I reversed every one of the 34 permalinks back to its original citation, in plan order. The diff against a3c698 then leaves only three changes: the version, the updated time and the publication note. All 34 links point to the right repository, SHA (API 96afd799 for control-plane files, runtime 1efea494 for the rest), path and line. The other 26 imported files are byte-identical to a3c698.

**Source checks.** All 21 source-contract-map entries match exactly in SHA, bytes and excerpts. Of the 34 citations, 4 fall outside the mapped ranges, but their claims are still true at those lines. All 11 Root input pins are exact. Every private handle and current generation in the manifest is null. I found no secrets.

## Mandatory findings

**F1 (MAJOR): nothing covers what happens after the 16:15:30 KST peer-policy deadline.**
- **Node behaviour after expiry:**
  - The Node pins the floor first, then rejects an expired policy (`services/node-agent/transport/trust.go:85`, :91).
  - It re-reads the policy on every handshake (:107), so from 16:15:30 every CP heartbeat, snapshot and delivery fails closed.
  - Startup builds the authority and exits on error (`services/node-agent/cmd/inv-node/main.go:104`, :22). After expiry, no restart, Docker restart, reboot or migration can bring a Node process back. Without a serving process, no M2 floor can be produced.
- **Normal machinery after expiry:** it refuses an expired current policy (`deploy/lan/peer_policy_phase.py:119`, `tools/lan_pilot.py:1584`).
- **Why this blocks:** the proposed card cannot realistically complete in the remaining ~8.6 h.
- **Required changes:**
  - A computed release cut-off.
  - An explicit post-expiry HOLD state. The Nodes are CP-unreachable, which is not a Node fault and must not be shown as healthy. No restart, reboot or migration; floors, journals and keys untouched.
  - A named post-expiry next card: an expired-authority forward-recovery contract owned by Codex and reviewed by Claude, bounded by leaf expiry (11-09 16:15:30 KST) and CA expiry (11-14 16:15:30 KST).

**F2 (MAJOR): the image migration is required, not conditional.**
- **Only the serving binary can produce M2.** The floor observer must be the exact serving binary (`services/node-agent/runtime/peer_floor_linux.go:78`).
- **That binary rejects the current setup:** it rejects the current layout, profile and ownership (:150, :174, :82).
- **Both Dockerfiles leave `/inv-node` root-owned** (`deploy/lan/Dockerfile.node:2`, `deploy/lan/Dockerfile.node.remote:11`).
- **The plan forbids every workaround:** fake argv, relabelling and chown.
- **Consequence:** a new Go binary, a new image and a new container (new CID) must come first. Executable changes are rejected mid-renewal (`deploy/lan/worker_plain_rotation.py:92`, :178), so the migration must settle before the pre-floor is taken. The plan's freeze on the exact CIDs/image contradicts this.
- **Required changes:**
  - A separately reviewed predecessor migration card that preserves identity and journal.
  - A rule for how the frozen identity carries over to the new container.
  - Deadline handling per F1.

## Non-mandatory findings

- **F3 (MODERATE):** the CP client context is built in five places, not just "API and observer": `services/control-plane/src/inv/observer_worker.py:58`, `services/control-plane/src/inv/worker.py:122` (delivery), `services/control-plane/src/inv/workspace_config.py:54`, `services/control-plane/src/inv/build_product_runtime.py:537` and `services/control-plane/src/inv/storage_check_collect.py:381`. The next card must enumerate them and switch each one, or prove it absent.
- **F4 (MINOR):** no pinned input evidences the CP-client leaf expiry. Mark it Root-attested.
- **F5 (MINOR):** the ownership-relevant COPY is `deploy/lan/Dockerfile.node.remote:11`, not :12. The build recipe of image de654cd3 is not pinned.
- **F6 (MINOR):** CA expiry ends any same-CA recovery. The plan lists the date but not that meaning.

## Confirmed sound

- **Incompatibility proof:** the claimed incompatibilities are correct.
- **Keys and membership:** same keys, IDs and membership are retained.
- **C/P monotonicity:** C and P are independent and monotone (`deploy/lan/peer_policy_phase.py:87`).
- **Antirollback:** the floor is pinned before expiry is checked, so the forward-only, no-rollback reasoning holds.
- **CA chain:** normal tooling requires exactly two CAs (`tools/lan_pilot.py:411`, :1587), and the plan refuses any generic trust relaxation.
- **Publication:** writes are atomic per file, not multi-file.
- **Channel commit:** the CAS and audit contract is right.
- **TLS reload behaviour:**
  - Node GetCertificate is dynamic and the policy is re-read per handshake.
  - The CP builds its SSLContext once (`services/control-plane/src/inv/node_transport.py:61`).
  - The CP pins each channel's fingerprint per request, giving a transient NODE-0032 window that Phase 3 acknowledges.
- **Timing:** the timing table matches the receipts.
- **Generations:** current generations stay null.

Checks I ran:
- Git blob reads and diffs.
- Scratchpad Python checks: source-map and citation verification, the Root537 reverse diff, root-input pins, the manifest null walk and a secret grep.
- Static source reads.
- The six local metadata gates, in [local gates](../Evidence/fleet5-current-three-node-renewal-plan-review-r1-20261108-claude/local-gates.json).
- A full canonical byte comparison, in [sync state](../Evidence/fleet5-current-three-node-renewal-plan-review-r1-20261108-claude/sync-state-comparison.json).

This review is static. I ran no Go, compiler, Docker, Linux, crypto, CA, pytest, browser, SSH, API, DB or live action, and I claim no runtime proof. APPLY false; I wrote no canonical state.

Next card requirements:
- Codex plan R2 (docs-only) for F1 and F2, folding in F3–F6, then a bounded Claude delta review.
- Then, depending on the cut-off, either:
  - before the cut-off: the migration card followed by FLEET5-CURRENT-CPU-COHORT-RENEWAL-ADAPTER-R1, or
  - after the cut-off (expected): the expired-authority forward-recovery contract.
- Each card needs real Go + Linux Docker hosted proof, two complete three-member cycles, the plan's negative cases, the affected CI and one actual source review. A new image is always a separately released migration, with no identity or journal reset.

Preserved state:
- Run run_01M6VXSMM9SV8MAB7K4B1YCRX8 is still awaiting_approval/v4/attempt0. The approval expired at 06:24:26 KST, and two genuine approvers are absent.
- PC1 key, PC5 RAM, GPU/storage/all 5, screen reader, renewal and reboot remain open.
- CR-905-01, CR-CSP-02 and the DASH findings remain closed.
- Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged, and wholeProgramComplete is false.

Next action: Root verifies this review and dispatches Codex plan R2. No rotation, restart or migration on PC2, PC3 or PC4 in the meantime.
