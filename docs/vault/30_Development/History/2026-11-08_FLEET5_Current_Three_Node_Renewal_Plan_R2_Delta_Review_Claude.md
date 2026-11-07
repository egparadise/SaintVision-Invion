---
doc_id: "HISTORY-FLEET5-CURRENT-THREE-NODE-RENEWAL-PLAN-R2-DELTA-REVIEW-20261108-CLAUDE"
title: "Current three-Node pilot renewal plan R2 delta review"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-08T08:35:00+09:00"
source_of_truth: "Git"
---

Task FLEET5-CURRENT-THREE-NODE-RENEWAL-PLAN-R2-ACTUAL-CLAUDE-DELTA-20261108 (Orca task_ed462b9da76f, dispatch ctx_ba1258a6cbe3), started 2026-11-08 08:28 KST.

**Roles:**
- I am the same actual independent Claude reviewer who wrote R1 (f29228ed28c651cb2470b45d9f8d14521e1ce75d, REQUEST_CHANGES, 2 mandatory blockers).
- The author is Codex task_3e413989dcaa, now exited/released.
- Root is the sole APPLY/SSH/credential/operator owner.

**Target:**
- R2 plan b8c839d1daf28677a0587af115cbea496626d5ea, direct base a3c6984f.
- PLAN-FLEET5-CURRENT-THREE-NODE-RENEWAL-R1 v1.1.0 (39704 B).
- The Root539 copy is byte-identical; operation-manifest SHA is b4e0d99b…ae7c.

**Branch:** `agent/claude/fleet5-current-three-node-renewal-plan-r2-delta-review-20261108`, created from Root539 `2733d3ce92bba47a94d9414d965a9a0d12d916d1` so that my own board is updated from current shared state. My R1 commit f29228ed is an input only.

**Records:** pins are in [read pins](../Evidence/fleet5-current-three-node-renewal-plan-r2-delta-review-20261108-claude/read-pins.json) and per-finding reasoning is in [review](../Evidence/fleet5-current-three-node-renewal-plan-r2-delta-review-20261108-claude/review.json).

**Verdict: ACCEPT_R2_PLAN_DELTA_KEEP_IMPLEMENTATION_AND_OPERATING_GATES, mandatory blockers 0, new mandatory findings 0.** F1–F6 are all CLOSED_AT_PLAN_ONLY. This closes the findings at plan level only; it does not accept any source or runtime behaviour, and it releases no operation.

## Per finding

- **F1 (MAJOR): CLOSED_AT_PLAN_ONLY.**
  - **Cut-off formulas:** normal release T_cutN = E − B_N − 630 s − 30 s. Migration release T_cutM = E − (B_M + B_N) − 630 s − 30 s, and migration must settle before T_cutN.
  - **Nothing is filled in:** every budget, actual E, cut-off and eligibility stays null/HOLD. The 48 h eligibility window is explicitly not a release.
  - **Post-expiry state:** it is defined even if nothing started.
    - CP handshakes and every request fail closed. I checked this against the policy read ([trust.go](https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/trust.go#L50-L93)) and the per-request authorization ([server.go](https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/services/node-agent/transport/server.go#L55-L139)).
    - Node startup exits 1.
    - No restart, reboot or migration is allowed while authority is unchanged.
    - The UI shows stale/unreachable honestly, and CP health is not Node health.
    - With no serving PID, no ordinary M2 can be produced.
  - **Recovery branches:**
    - The policy-expired branch (cut-off L − B_Rpolicy − 660 s) and the expired-leaf branch (cut-off A − B_Rleaf − 660 s) are separate.
    - Both are owned by Codex, reviewed by Claude and NOT_IMPLEMENTED.
    - Neither may reuse the normal adapter unchanged.
- **F2 (MAJOR): CLOSED_AT_PLAN_ONLY.**
  - **Mandatory predecessor:** FLEET5-CURRENT-CPU-SERVING-BINARY-CONTAINER-MIGRATION-R1 delivers the new Go binary, image and CID, keeping NodeID, keys, journal, floors and mounts.
  - **Freeze phases:** M0 → M1 → M2 → M3 → N0 → N1. The fresh pre-floor is taken on the new serving binary, and the executable must not change mid-batch.
  - **Release conditions:** release needs either valid authority before T_cutM, with the adapter and B_N already ready, or the distinct expired-authority contract.
  - **Old identity:** the old CID/image is historical evidence, not a universal frozen identity.
- **F3 (MODERATE): CLOSED_AT_PLAN_ONLY.**
  - **Five sites, verified at API 96afd799:**
    - [observer_worker](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/observer_worker.py#L42-L81)
    - [worker delivery/build](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/worker.py#L111-L160)
    - [workspace](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/workspace_config.py#L12-L68)
    - [build runtime](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/build_product_runtime.py#L503-L546)
    - [storage collector](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/storage_check_collect.py#L350-L388), via [app composition](https://github.com/egparadise/SaintVision-Invion/blob/96afd799d49717fd40e4ddabd538d82accbe1958/services/control-plane/src/inv/app.py#L1405-L1420)
  - **Required controls:** for each site, a Root present-or-absent attestation (all null now), cached-object acknowledgement, a launch guard, an all-context barrier before P+2, and stale-context refusal.
  - **No overclaim:** the plan does not claim five live instances.
- **F4 (MINOR): CLOSED_AT_PLAN_ONLY.**
  - **New evidence:** Root538 read the PC3 public certificate at 07:52:28 KST: DER 48911c5d…6481, notAfter 2026-11-09T07:15:30Z, expected URI.
  - **How it was read:** only the public file. No private key, context or handshake.
  - **Limit:** it is not evidence of active use. The R1 F4 finding remains historically correct.
- **F5 (MINOR): CLOSED_AT_PLAN_ONLY.**
  - **COPY lines corrected:** remote :11 and local :2.
  - **Citations:** all 49 permalinks resolve to exact blobs inside the 25-entry source map (49 ranges, excerpts exact).
  - **Deployed image:** its provenance stays a future Root attestation.
- **F6 (MINOR): CLOSED_AT_PLAN_ONLY.**
  - **CA terminal:** from 2026-11-14 16:15:30 KST, same-CA renewal or recovery is impossible.
  - **Out of scope:** authority replacement is a separate workflow, and never legacy init/reset/repin.

## Non-blocking observations

- **O1 (LOW):** at review time no migration or adapter code, CI, review, budgets or preflight exists. Under the plan's own readiness rule, the valid-authority branch is unlikely to be reachable before 16:15:30 KST. Root should expect to choose FLEET5-EXPIRED-CURRENT-AUTHORITY-FORWARD-RECOVERY-CONTRACT-R1 next.
- **O2 (LOW):** the expired-branch budgets B_Rpolicy and B_Rleaf must include that contract's own migration component and its settlement.

## Checks and scope

**Checks I ran:**
- Git diffs and blob reads.
- Scratchpad Python checks: the 49 permalinks against blobs and the map, the manifest null walk, the finding dispositions (no author self-closure), the Root538 copies, and a reverse diff of Root538's v1.0.1 copy of my R1 History (citation rendering only).
- Static source reads at exact SHAs.
- The six local metadata gates at base 2733d3ce, in [local gates](../Evidence/fleet5-current-three-node-renewal-plan-r2-delta-review-20261108-claude/local-gates.json).
- A full canonical comparison, in [sync state](../Evidence/fleet5-current-three-node-renewal-plan-r2-delta-review-20261108-claude/sync-state-comparison.json).

This review is static. I ran no Go, compiler, Node, npm, pytest, browser, crypto, CA, SSH, API, DB, Docker or live action, and I claim no runtime proof. APPLY false; no canonical write.

**Next implementation card requirements:**
- Root picks the branch from real time, a reattested E, frozen budgets and readiness.
- Expected now: the expired-authority recovery card. It needs finite coverage of never-started, partial-migration and partial-normal states; a versioned no-serving custody evidence schema and authorization; P strictly above the pinned floor; C+1 CAS/audit; Node-owned signatures; its migration inside B_Rpolicy; completion before L, or the separately released expired-leaf branch before A.
- Otherwise: migration first, then the adapter.
- Each card needs P1–P7, Go and real Linux Docker hosted proof, two three-member cycles, negative cases, the five-site context barrier, affected CI, one actual source review, Root preflight and an explicit release.

Preserved state:
- Live versions: runtime 1efea494, API 96afd799/schema0068, UI abb7074e.
- Historical results (the 500m/64MiB offers, the UI 30.167 s/1811 frames and the Root536 reconnect) are not current health.
- The Run is still awaiting_approval/v4/attempt0; the approval has expired and two approvers are absent.
- PC1, PC5, GPU/storage, manual acceptance, full 5 and reboot remain open.
- Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged, and wholeProgramComplete is false.

Next first action: Root verifies and publishes this delta, then selects the branch (expected: dispatch Codex for the expired-authority recovery card). No rotation, restart, reboot or migration of PC2, PC3 or PC4 in the meantime.
