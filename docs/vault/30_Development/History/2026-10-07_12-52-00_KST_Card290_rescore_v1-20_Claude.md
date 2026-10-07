---
doc_id: "HIST-20261007-CARD290-CLAUDE"
title: "Card 290 48 task rescore v1.20"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-10-07T12:52:00+09:00"
updated: "2026-10-07T12:52:00+09:00"
source_of_truth: "Git"
---

# Card 290 48 task rescore v1.20

## Columns

- Landed: `git ls-remote` read the integration tip again at 12:42 KST and it is still
  `6fc0428b49f28379cb4da17830d92256b55c2eb2` — the **eighteenth** identical reading.
- Candidate **Y** = train 66 `2146a70b0e588654a99030dfc9cee815147d37ba`
  (`coord/train66a-ci-1216`).
- Chain machine-checked in both directions: `6fc0428b ⊂ V ⊂ W ⊂ X ⊂ train62 ⊂ train63 ⊂
  train65 ⊂ Y`, and Y is **not** an ancestor of the landed tree.
- `#380`–`#385` are all in Y and all OPEN. **`#386` (card 289, my own) is not in Y and is not
  counted.** `#384` was merged **twice** (at `298a33e1`, then at `57c3479f` after its delta
  review), so there are seven merge commits for six distinct PR numbers.
- Inventory **145** by the landed-tip range convention (X was 138, so +7).

## Result

| basis | score | of | ratio |
|---|---:|---:|---:|
| landed `6fc0428b` | **3,425** | 4,800 | **71.35%** |
| Y lands | **3,475** | 4,800 | **72.40%** |

**No row rises.** That is the same number as V, W and X — but this round is a different shape
from the two before it. v1.18 and v1.19 judged accessibility *screen* work; what arrived here is
the six changes **closest to operation**: the expired CA was abandoned for a fresh isolated state
with **two Nodes re-attached over real mTLS** and a hardened remote database behind an SSH tunnel
(`#384`, which also fixed three bootstrap defects), and a **fail-closed leaf rotation tool** was
added for the 2026-10-13 leaf expiry (`#385`, which I reviewed r1 and r2).

## Why the most operational round still moves nothing — three measurements

**The state is observation-only.** Card 287's History says it in its own words: *"Workload
execution remains disabled and the state is observation-only."* Rows whose remaining item needs
execution, result transfer or a volume mount are therefore not reached. The coordinator's
operational reading (11:15 KST, overview `source=live-postgresql-mtls`, two Nodes `online` and
fresh) is an **observation**, not an execution. I did not open the private state.

**Two of four configured workers are online, and the other two wait on the operator.** The same
History names them: worker 3's non-root account cannot open the Docker socket until the operator
adds it to the Docker group and signs in again; worker 4's approved public key is not enrolled and
its account name is not established. Meanwhile **every row that lists a physical-node acceptance
asks for five** — `S03-BE`, `S05-BE`, `S05-DB`, `S05-FE`, `S06-FE`, `S07-BE` (and `S11-ST` wants a
24-hour soak). Two is not five, so the partial stays partial and the row does not move. What this
round changed is not the score but the **distance**: zero Nodes to two.

**Rotation is tooling, not an application.** Card 288's History says *"Live rotation is a separate
step after independent review"*, and its operational command block says *"These commands are
recorded but were not run."* No row lists certificate rotation as its remaining item either —
rotation **preserves** the inputs that `G-19`/`G-24` need rather than **producing** an acceptance.

**And the accessibility axis is identical for the fourth time.** The envelope from Y's own head
(run `37566028638`, success) has five observations byte-identical to what v1.18 and v1.19 recorded
— sorted canonical JSON sha256 `348491efbc4c447f` — with the same `targetRef` blob
`737853bbde0b`, `MEASURED_FAIL`, and the single failing box `manualAcceptanceMissingCount` 1.

**The AC-11 axis aggregation did not run here.** That lane is `skipped` at Y's tip and at all eight
recent heads, so `S11-BE`'s "all eight axes" condition could not have moved. That is a lane state,
not an inference.

## Rows considered

VF-CL work (`#381`, `#383`) belongs to a **separate track** and is not a 48-task row; `#381`
changed only reviewer-owned booleans and `#383` changed no state-field value at all. `#382` is
test-only with a zero product diff. `#380` is a document, which is not a score. The full row table
with the reason for each is §4-17-3 of the rescore document.

## What this round did not check

- The private pilot state, passfile, DSN and private keys were not opened; the operational
  reading is the coordinator's measurement, cited rather than reproduced.
- No rotation was applied, and I did not estimate what a row would do if one were.
- The AC-11 aggregator was not run — only its `skipped` lane state was read.
- Y's exact-head lanes were not counted exhaustively; the six PRs' lanes were checked per head in
  their own reviews. Y's Core Build was still running while this was written.
- `#386` was not judged, and I deliberately did **not** pre-record an opinion about whether the
  desktop launcher touches any row — the rule is not to write a judgement before looking.
- All 48 rows were not re-audited. Only the places the six changes could reach were judged; the
  rest carry forward, which is this document's standing limitation.
