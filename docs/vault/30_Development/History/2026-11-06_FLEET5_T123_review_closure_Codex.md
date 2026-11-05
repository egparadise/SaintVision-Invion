---
doc_id: "HIST-FLEET5-T123-REVIEW-CLOSURE-001"
title: "FLEET5 independent review T1 T2 T3 test closure candidate"
version: "1.0.0"
status: "in-progress"
author: "Codex"
reviewer: "Actual independent Claude delta review via root pending"
updated: "2026-11-06T00:43:09+09:00"
source_of_truth: "Git"
---

# Review closure candidate

Owner Codex; task `FLEET5-COMPUTE-STORAGE-CONTRACT-20261105`, Orca
`task_a8fd2969f0b3 / ctx_6f0f8253b8a7`; own branch
`agent/codex/fleet5-compute-storage-contract-20261105`. This test-only closure
starts at `46b4573f2b333dfbb3d37f695c19df9ae805a364`; runtime remains exact
`4a928310e88ac336efb040c1621525fee7133f32`. Original combined base, first-read
document IDs/versions, Index401/Codex362 and delivery/core-reliability skills
are recorded in the original source inventory and
[[2026-11-05_FLEET5_P0_plain_peer_phase_implementation_Codex]].

Actual independent Claude CODE verdict
`8baaa6b568f1e467a76272faa6d7f2084545c525`, task
`task_c90b362f7470 / ctx_1e0814952956`, is **NOT ACCEPTED**. It reports no
runtime correctness defect found in the reviewed M2/C2/RS1/SF1 paths, while
requiring CI-B1, C2-V1 and test gaps T1/T2/T3. Root directions
`msg_620855c76519` and `msg_70add7c29003` authorize bounded test closure without
runtime weakening and consolidation before the next long Core run. The actual
46 isolation delta review is separate and still pending at this checkpoint.

T1 adds fresh, correctly signed post-start acknowledgements with the wrong
phase, policy hash or executable, stopped actual-volume and context races,
finalizing P/current refusal with P+1/P+2 positive controls, and generic guard
post-operation drift. It checks unchanged journals/archives, no unauthorized
start before failed preflight, no acknowledgement acceptance, and no old restore
after an allowed same-CID start. T2 changes only servingExecutableSHA256 to
malformed strings and re-signs the otherwise valid body; the key signature is
independently verified before the digest rejection assertion.

Thirteen T1/T2 cases pass. The disposable-copy mutation driver kills all four
specified T1 mutants and the T2 hex-guard mutant. Every child executes all
thirteen cases; failures are only the expected DID NOT RAISE assertions, with
no errors or skips. Mutant exit 1 is expected evidence; the overall driver exit
is 0. Production originals remain byte-identical before/after. Commands, source
hashes, mutation hashes, counts and raw logs are in
`Evidence/fleet5-compute-storage-contract-20261105-codex/p0-t123-closure/mutations/`.

T3 adds default-dispatch framing and error units without substituting a callback
verifier. The hosted fixture uses byte-identical installer sources and an owned
isolated OS home containing a copy of the already installed pinned runtime;
it invokes the real default generic guard, its fixed -I/-B launcher subprocess,
actual pinned crypto and existing signature/hash checks. Positive stages surround
missing launcher/entry/runtime, changed entry/runtime/crypto bytes, invalid fresh
Node signature and malformed runtime-receipt cases. The CLI preserves sanitized
error-class reporting. The Docker/Node observation remains explicitly synthetic;
this is not native Go/Docker acceptance. No package install or host Docker action
is performed locally. A separate strict public proof artifact is required; the
existing closed eleven-field standalone lifecycle :3 result is retained.

Original Core `42047390811` is terminal failure, not timeout/cancellation:
five failed, 9075 passed, 46 skipped, two deselected, the same five stale fixture
cases as Backend. Its installer stage executed seventeen cases with zero skips
or failures; its existing real Docker SF1 test substitutes pinned dispatch, so
it does not establish T3. The complete original artifact `13427633755` has
GitHub-verified ZIP SHA-256
`82685c759b9fd997c406dc64edd4335001294ba3247a7599f3e46d0593137fd1`.
Raw terminal API/logs and the two actual Go/Docker reports are preserved here.
The original native two-cycle artifact remains preserved at its original path.

Correction to [[2026-11-05_FLEET5_P0_v2_exacthead_CI_Codex]] at 46: I misread the
Backend step order. Both original 4a matrices PASSED the installed standalone
CLI stage before their later Tests failures; 3.12 also passed the existing
standalone guard mutations, while 3.14's mutation step was expected to skip.
The prior statement that neither reached installed verification is wrong.
The terminal jobs API proves this correction, reported in `msg_f665968bb86c`.
That success remains scoped to the old installed CLI fixture; T3 default dispatch
and whole Backend/Core acceptance were not established by it.

No production runtime/interface, current guard, schema, freshness, phase table,
identity, policy, mount or rollback behavior changes. Only test fixtures, CI proof
producers/workflow and unique History/Evidence change. Before-copy and restarted
states remain guarded BLOCK under Root A; whole recovery, bootstrap predecessor,
full compound storage/workspace B and physical acceptance remain unaccepted.
Codex next publishes this consolidated SHA, runs exact-head native/full Core and
Backend/Docs while preserving earlier terminal runs, then requests actual
independent delta review through root. No shared boards, registry, ADRs, original
sources, protected pilot or Obsidian apply were changed.
