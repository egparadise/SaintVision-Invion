---
doc_id: "HIST-FLEET5-P0-FROZEN-SOURCE-DELIVERY-001"
title: "FLEET5 bounded P0 frozen source delivery and exact CI"
version: "1.0.0"
status: "in-progress"
author: "Codex"
reviewer: "Claude actual source ACCEPT 2736aec1303ca6b6ed80bdc4aa6b9c23c3693985"
updated: "2026-11-06T01:37:19+09:00"
source_of_truth: "Git"
---

# Frozen bounded P0 handoff

Owner Codex; task `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, Orca
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`; branch
`agent/codex/fleet5-compute-storage-contract-20261105`. Frozen accepted source is
`4f97ba71b1482ae70d72dda1833a28fddcd05994`; runtime interfaces remain exact
`4a928310e88ac336efb040c1621525fee7133f32`. This report is documentation/evidence
only, and its containing report SHA is handed to root separately. Original base
`0bcf9670d098fac87667fc9e2448b332db46e691` was preliminary, not a final candidate.
Exact first-read doc IDs/versions, Index401/Codex362, skill versions and scopes
remain in the original source inventory and
[[2026-11-05_FLEET5_P0_plain_peer_phase_implementation_Codex]].

Actual independent Claude verdict
`2736aec1303ca6b6ed80bdc4aa6b9c23c3693985`, task
`task_e1a7c90d207a / ctx_0aba9fd1087f`, is **ACCEPT at bounded P0 source level**.
T1, T2, T3 and C2-V1 are closed; runtime is unchanged from the earlier reviewed
4a source. The original verdict bytes are preserved in the evidence directory.
The two Low test-strength follow-ups L-T3-1 and L-T3-2 are nonblocking and remain
separate: a valid oversized token and duplicate key inside a complete valid
token should kill their corresponding removed-bound/parser mutants. They are
not silently included in source 4f or its CI evidence.

All assigned exact-head required CI is now terminal SUCCESS at source 4f:

- Core `42058859797`: both core `127354635414` and S01 `127354634788` succeed.
  Full pytest: 9109 passed, 46 declared platform/integration skips, two
  deselected. Provisioned installer evidence: seventeen executed, zero errors,
  failures or skips. All-package Go tests, build and TypeScript check succeed.
- Backend `42058865926`: Python 3.12 `127354655684`, Python 3.14
  `127354655149`, and MLflow `127354655585` succeed. Each Python matrix records
  8751 passed, 75 skips and two deselected.
- Docs `42058871808`, job `127354676431`, succeeds at source 4f.

The actual observed toolchain line in the completed Core setup log is
`go version go1.27.1 linux/amd64`, timestamp
`2026-11-05T15:49:43.2135216Z` (2026-11-06 00:49:43 KST). This is an executed
observation, distinct from configured setup-go 1.27.1 and the go.mod minimum.
Raw completed Core log SHA-256 is
`bfe8a6f1e8cde72741e07669c14e8a261d799c0b2033fe677f191c18902598ff`.

The real native Go proof completes two normal cycles with peer floors
7,8,9,10,11 and independent control channels 8,9. All specified guard flags
pass. Seven decoded Unicode canonical bodies match actual Go, static expected
bytes and Python, with actual Ed25519 verification under the v2 domain. Its
original ZIP is artifact `13429894778`, SHA-256
`b1d100279ff98d0d4fb8f2948c0d303ca09f95684eaab27562b6dd0c0dc09b1c`.

Each actual installed pinned runtime passes ten default generic-guard verifier
stages, with no callback substitution or pinning bypass. The Node/Go observer
in this specific proof remains synthetic; real crypto/launcher/hash checks are
assessed. Python 3.12 artifact `13429399588` has SHA-256
`c77ae65caeae757725afc3a2bc4846d7794551227d1bb3ff22c5f6df02d913d2`;
Python 3.14 artifact `13431055483` has SHA-256
`4aafbc3995e7f1606318ddd902d1000d97efe8e3295ffae9e3c24f3cdb746f39`.
The 3.12 artifact also proves baseline thirteen green and all five specified
RS1/SF1/executable-hash mutants killed without errors or skips. The closed
standalone lifecycle :3 result remains unchanged, with two fixture cycles,
four restarts, rollback refusal, no rollback and no bytecode caches.

Current real Docker/Go installer reports are separately preserved in Core
artifact `13433310888`, ZIP SHA-256
`06fb3dd8066ed624c1bc404d750d42a9cd4102e36094c8ce0acf17bdff92a836`.
S01 candidate artifact `13428944525` has SHA-256
`30229271e484940c8792ae0990cf8ae5791c553fcf3c74975b2c1d1665802938`.
All original ZIP digests matched GitHub metadata. Raw terminal run/job API,
completed logs, summaries, original independent review and extracted reports
are under `Evidence/fleet5-compute-storage-contract-20261105-codex/p0-t123-exacthead-ci/`.
Historical red 6c/526d/4a runs remain preserved and are not relabelled green.

Root message `msg_2170d0e42ec4` independently re-verifies all exact 4f required
CI and selects this bounded source for candidate inclusion. Integrator must still
complete its new immutable combined ci2, focused/freeze/archive/all-eight and
actual combined review gates; landing and NodeOps are not authorized by this
selection. Whole integration/full-eight acceptance, NodeOps/bootstrap, physical
five-PC execution/storage and all real bindings remain HOLD/NULL. Broad B is
OPEN: current default R4 storage guards are intact, and a separately reviewed
compute-plus-readonly-storage/coherent-renewal/post-settled migration contract
is still required. After-stop/no-copy and restarted states remain guarded
BLOCK; whole-operation recovery is not claimed. No protected pilot identity,
private config/key, issuer, host Docker/WSL/SSH/trust/clock/schedule, registry,
shared board, original source or Obsidian apply action was made.

Codex next publishes this report SHA and its Docs result to root, then may
prepare the separately labelled Low test delta and a DOCS-only Broad B proposal
under Root's existing directions. No production Broad B or migration code may
change before Root chooses its concrete architecture contract. Sync remains
check-only, with exact publication command exits in the accompanying receipt.
