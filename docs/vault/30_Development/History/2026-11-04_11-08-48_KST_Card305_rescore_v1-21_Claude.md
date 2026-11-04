---
doc_id: "HIST-20261104-CARD305-CLAUDE"
title: "Card 305 48 task rescore v1.21"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-11-04T11:08:48+09:00"
updated: "2026-11-04T13:26:09+09:00"
source_of_truth: "Git"
---

# Card 305 48 task rescore v1.21

문서만. 전체 판정은 재채점 문서 §4-18이고, 이 문서는 읽을 수 있는 요약이다.

## Columns

- Landed: `git ls-remote` read the integration tip again at 2026-11-04 11:04 KST and it is still
  `6fc0428b49f28379cb4da17830d92256b55c2eb2` — the **nineteenth** identical reading.
- Candidate **Z** = train 78 `03e17c31cf535008d39534aaa80d3ae274bd75cc` (`coord/train78a-ci-1343`).
  **The candidate was not re-cut this round** — `ls-remote` shows no `coord/train78b` or later.
- Chain machine-checked in both directions: `6fc0428b ⊂ V ⊂ W ⊂ X ⊂ Y ⊂ Z`, and Z is **not** an
  ancestor of the landed tree.
- Thirteen PRs arrived — `#386`, `#387`, `#388`, `#389`, `#391`, `#392`, `#393`, `#394`, `#395`,
  `#396`, `#397`, `#398`, `#399`. All OPEN, none an ancestor of the landed tree, and this round
  has **no double merge**: thirteen merge commits for thirteen PR numbers.
- Two are **not** counted. `#390` was never merged into Z, and `#400` (Card 302, my own) has Z's
  own tip as its base so it cannot be inside Z. Same rule v1.20 applied to `#386`.
- `#397` **moved after the train took it**: Z contains the merged `f2936ae5`, and that PR's
  current head `a44d578a` is not an ancestor of Z. This round judged the tree inside Z.
- Inventory **158** by the same `--first-parent` command, calibrated by reproducing **145** at Y
  first so the method is provably the one v1.20 used. Y was 145, so +13.

## Result

| basis | score | of | ratio |
|---|---:|---:|---:|
| landed `6fc0428b` | **3,425** | 4,800 | **71.35%** |
| Z lands | **3,475** | 4,800 | **72.40%** |

**No row rises.** Same as V, W, X and Y.

## Why the most operational round yet still moves nothing — four measurements

This is the closest-to-operation batch so far. Where v1.20 closed with "the rotation tool exists
and was not applied", the tool has since advanced six more times — batch rotation, expired-partial
recovery, fully-expired offline recovery, the venvless pinned runtime, bytecode-free execution, and
the pinned worker module closure — and the live pilot was stood up **twice**, as r3 and then r4.

**(a) The r4 state is observation-only, and this time I measured it rather than citing it.**
`#398`'s record says *"Workload execution remains disabled; this procedure established observation
only."* During that review I read the loopback overview myself and measured `killSwitch=true`,
`userWorkloadSubmission=false`, `runs=0`. v1.20 had to cite the coordinator's reading; this round
does not.

**(b) Two Nodes online, five required.** r4 was accepted with exactly two, and every row whose
remaining item is a physical-node acceptance asks for five (`S03-BE`, `S05-BE`, `S05-DB`, `S05-FE`,
`S06-FE`, `S07-BE`; `S11-ST` wants a 24-hour soak). Same distance as v1.20.

**(c) Rotation advanced six times and still never completed.** The live attempts stopped **twice,
both fail-closed** — `#396` on the `__pycache__` the preflight left inside the verified tree, and
`#397` on the missing `worker_config.py` just before the first Node restart. Both defects had
passed my own earlier reviews, and I said so in each PR. And r4 is a **fresh bootstrap, not a
rotation**. No row lists certificate rotation as its remaining item — I grepped the whole document
and §3's 48-row table carries no such condition.

**(d) New this round: the approved renewal window passed with no record, and the leaves expired.**
`#398` recorded the renewal start as 2026-10-31 12:32:25 KST and the Control Plane leaf expiry as
2026-11-02 12:32:25 KST. At 2026-11-04 11:04 KST I measured three things: there is **no History
document after 2026-10-27** and train 78's last commit is 2026-10-27T13:43; the console at
`127.0.0.1:18082` **refuses the connection**; and the expiry is therefore about two days past. A
refused TCP connection changes nothing, so this is a measurement of absence, not live contact.

So **r4 now sits where r3 sat when v1.20 was written.** Thirteen PRs built the rotation machinery,
and machinery that is not applied does not merely fail to raise a row — it takes back a partial
that had already been counted. One line of the distance table **regresses** for the first time.

**The accessibility axis is identical for the fifth time.** I downloaded Z's own envelope (run
`40451352612`, `workflow_dispatch`, success, `sourceHeadSha` matching the 40 characters,
`cleanCheckout: true`) and compared it directly against Y's (`37572321090`) under one method:
`payload.observations` are **byte-identical**, `payloadSha256` differs, and `targetRef` is the same
blob `737853bb…`. Two separate real runs, same observation, unrotated axis definition.

**One correction to the earlier rounds.** v1.18 through v1.20 record the observations digest as
`348491efbc4c447f…` but never pinned the canonicalisation, so that string **cannot be reproduced** —
my method yields `d57b5549…` on the same bytes. Rather than assert a match I could not derive, I
compared the two envelopes A/B and recorded my own method's digest so the next round can reproduce
it. The historical string is noted as method-less.

**AC-11 axis aggregation did not run here.** At Z's tip the API lists **eight** runs — accessibility,
security scan, auth/desktop acceptance, Backend, Core, Documentation, Frontend, portal harness, all
`workflow_dispatch` and all success — and `AC-11 Axis Aggregation` is not among them. So `S11-BE`'s
eight-axis condition could not have moved. A run state, not an inference.

## The judgement v1.20 deferred

v1.20 deliberately refused to pre-record an opinion on whether the desktop launcher touches any row,
because the rule is not to write a judgement before looking. `#386` and `#387` are in Z now, so I
looked: **no row's rubric mentions a desktop path, launcher or shortcut** — I grepped the whole
document and the only hits are v1.20's own prose. It is an operator-convenience path and not any
row's remaining item.

## Stacking, and why

This branch is based on **`#400`'s head, not on train 78**. Both cards bump the Index and the Claude
board, and both would otherwise claim 1.0.376 / 1.2.118 off the same parent — the precise collision I
reported as a finding on `#399`. Stacking makes the chain linear: `#400` holds 376 / 118 and this card
takes **377 / 119**. Basing on train 78 and skipping to 377 would avoid a collision but let the Index
go *backwards* if this landed first, which is worse. **`#400` must land before this one.**

## Verification

- `check_docs.py` and the citation ratchet both pass; `git diff --check` clean.
- Every number above came from a command, and the inventory method was calibrated against v1.20's
  recorded 145 before being used for 158.

## Correction after landing (v1.0.1, 2026-11-04 13:26 KST)

The Columns and Result sections above are the 11:04 KST record and stay as written. They are not
the present state:

- The GitHub branch activity API records the push `6fc0428b → 03e17c31` to
  `integration/all-agents-unified` at **2026-11-04 12:08:42 KST**. Z landed about an hour after this
  round measured. The landed tree is now `03e17c31`.
- **This correction does not raise the score.** 3,475/4,800 is the "Z lands" calculation.
  The first integration push runs after landing failed: Backend `41765284237` and Core
  `41765284130`, each with 42 failed and 9 errors. All of it is attributable without a product
  regression:
  - the test database's 2026-10 partition gap (40 failures and the 9 errors), fixed on
    `agent/claude/s20261104-partition-rollover`;
  - the AC-11 fixture expiry (1), fixed by `#397`'s `751ea725`;
  - the VF-CL registry rule-8 drift (1).
  Post-landing verification is unfinished, so re-scoring the landed column belongs to the next
  round.
- Codex independently accepted `#400` at `611a9aab`, within Node-leaf-only scope.

## Next

- First action: Codex re-reviews this exact head (correction only, no score change). `#400` still lands first.
- Owner for the operational decision: coordinator and user. Codex worker's read-only measurement,
  relayed by the coordinator and not re-measured by me: r4's Control Plane and Node leaves are
  expired, all three listeners are absent, there are two real Nodes, and resources are 0.
  Untouched r4 has no partial batch for `#391` to recover, so the supported path is a **fresh
  isolated namespace bootstrap**. Whether to run it is a live decision.
