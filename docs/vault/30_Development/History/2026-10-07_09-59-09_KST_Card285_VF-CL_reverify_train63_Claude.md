---
doc_id: "HIST-20261007-CARD285-CLAUDE"
title: "Card 285 VF-CL implementation claims re-verified at the train 63 candidate"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
created: "2026-10-07T09:59:09+09:00"
updated: "2026-10-07T09:59:09+09:00"
source_of_truth: "Git"
---

# Card 285 VF-CL implementation claims re-verified at the train 63 candidate

## Scope and decision

- Re-verification tree: train 63 candidate `517880099743cf2d62131012191b7ba54650c44d`
  (`coord/train63a-ci-0847` = train 62 `59050d2a` plus the single merge of `#381`).
- Owner-side scope only: `implemented`, `locallyVerified`, `ciVerified`, `ciVerifiedRun` and
  `verifiedAgainst`. **No reviewer field was touched** — `independentlyReviewed` is unchanged on
  all five cards, including VF-CL-05 where it stays `false` on purpose (§VF-CL-05 below).
- **Zero state-field values changed.** The re-verification confirmed the existing claims rather
  than altering them, which is the correct outcome when they are true. What changed is the
  *basis*: the registry now records the tree it was actually re-derived at.
- No product, migration, contract, evaluator or workflow file was changed.

## What was stale, and how stale

`verifiedAgainst` named the **train 11** candidate `25f43a25` (`coord/train11-ci-0047`). It
passed rule 8 only because that candidate never reached integration, so the "re-verify at the
landed SHA" branch never fired. The claim was therefore technically admissible and **52 trains
out of date** — a rule that cannot expire is a rule that stops being a deadline. Measured:
`25f43a25` is an ancestor of this tree, and is not an ancestor of
`origin/integration/all-agents-unified` (`6fc0428b`).

## implemented — re-derived, 56/56

Every manifest check was re-applied **independently of the checker** at this tree (own script,
`path-exists` / `path-absent` / `references`): **56 checks, 56 hold, 0 fail**. That is what
re-derives `implemented`, and it covers the five cards' checks, VF-CL-04's eight
`ciVerifiedChecks`, and all eight closed-blocker check sets. `tools/check_vf_cl_registry.py`
agrees (exit 0).

## locallyVerified — re-measured per card

Environment: Python 3.14.7, **docker hidden from PATH**, real PostgreSQL only through a
**disposable `c285_reverify` database** created and dropped on `127.0.0.1:55432` (the shared
`invdev` database was not used).

| card | attributed tests | local result |
|---|---|---|
| VF-CL-01 | 1 file | **90 passed** |
| VF-CL-02 | 8 files | **212 passed, 1 skipped** (Windows symlink privilege) |
| VF-CL-03 | 3 files | **124 passed** |
| VF-CL-04 | 9 files | **195 passed, 31 skipped** (Linux-boundary and CX01-container cases) |
| VF-CL-05 | 0 | no code; this card ships review documents |

**A gap closed by the disposable DB**: `tests/test_vf_replica_migration.py`'s two real-PostgreSQL
cases, which skip for want of `INV_TEST_ADMIN_DSN` and which card 284 could only show through
hosted CI, **executed locally this round** — run together with the two other PG suites:
**13 passed, 0 skipped**.

## The attribution rule, and the first version of it that was worthless

A test counts for a card when it imports one of that card's **distinctive** owned modules — an
owned module that is not shared API infrastructure, counting a bare `import <basename>` for tools
because tools are imported after a `sys.path` insert — or when the card's own manifest checks name
that test file.

The first attempt matched module basenames as **substrings** and attributed **128–153 files per
card**, because tokens like `storage`, `resolver`, `problem` and `projects` are everywhere. That is
exactly the failure the manifest's `whyCiVerified` names: it would have read as coverage while
asserting nothing. It is recorded here because the discarded version is the instructive half.

Two limits are recorded rather than papered over:

- `saintvision.api.problem` is imported by **31** test files across unrelated cards, so it
  attributes nothing and is excluded **by measurement**.
- Route modules (`api/v1/storage.py`, `api/v1/projects.py`) have **0** direct importers — they are
  exercised through the ASGI app — so the import graph cannot reach them at all.

## ciVerified — unchanged, and why that is the honest answer

The manifest still asserts **nothing** for VF-CL-01/02/03/05 (`impliesCiVerified: null` with a
stated `whyCiVerified`) and `false` for VF-CL-04. I did not upgrade any of them, and the reason is
measurable: the hosted Core lane runs whole directories (`pytest tests/core`, `pytest tests/`), so
a green lane shows **the lane passed**, not that a named card was exercised.

What this round added is the per-card attribution above, recorded in `verifiedAgainst.reverification`
as what the run does and does not show. **VF-CL-01's attribution is a single file** — the thinnest of
the four — and it is stated rather than padded.

## The receipt had to be re-recorded, which the card did not anticipate

Moving `verifiedAgainst.tree` broke a binding the card description did not mention: the checker
compares the VF-CL-04 receipt's `claimedTree` against the registry's tree, so the first attempt
failed with `the receipt is about tree '25f43a25a999', not the registry's '517880099743'`.

It was **re-recorded with `tools/record_vf_cl_ci_receipt.py` from GitHub's own answers** (three
`gh api` documents for run `36851875128`), not hand-edited — the tool re-verified the run, every
job and all four required steps, the artifact name/expiry/digest, and that the head
`40b3ec78` is still an ancestor of the new claimed tree, then recomputed `receiptSha256`.
**Three lines changed** (`claimedTree`, `receiptSha256`, `recordedAt`); run id, head, artifact
digest, step list and input digests are byte-identical. `docs/vf-cl-ci-receipts/VF-CL-04.json` is
therefore a third changed file beyond the two the card named.

## The two Low findings from the #381 review

- **Canonical form restored.** `docs/vf-cl-task-registry.json` was byte-identical to
  `json.dumps(indent=1, ensure_ascii=False)` before `#381` and had drifted 34 lines. The file is
  re-serialised to that form and asserted equal to it after writing.
- **One spelling for "no open blockers".** `blockers: []` is now present on all five cards;
  VF-CL-01 and VF-CL-05 previously omitted the key. The checker is indifferent either way — it
  reads `card.get("blockers") or []` — so this is consistency, not behaviour.

## VF-CL-05 — the reason was already recorded, and my #381 note was imprecise about it

The `#381` review said VF-CL-05 has "no blocker naming why" `independentlyReviewed` is false. That
is literally true and misleading: the reason was already in `notApplicable` — *"this card IS the
review function"*. The field is not missing a reason; it never needed a blocker.

The entry is sharpened to say the rest of it out loud: an independent review of the review card is
**the reviewer's act, not the owner's**, so the owner may not raise this field and Codex raising it
is the only way it becomes true. Card 284 closed the other four cards' review blockers and did not
reach this one, so VF-CL-05 is now the only card without an independent review. The field stays
`false`.

## Exact-head evidence at `51788009`

| lane | run | result |
|---|---|---|
| Core Build | `37548456022` | success |
| Backend Build | `37548452805` | success |
| Documentation Build | `37548464717` | success |

`core.yml` asserts `skips == Counter()` and `passed == 20` for the owned CX01 recovery drill, so a
successful Core run is what lets VF-CL-04's recovery-drill gap say `0 skips, 20 passed` at this
tree; its `measuredIn` is re-pointed from run `36886647197` at `25f43a25` to this run.

**Attempt 1 of that run id failed, and the record says so.** It concluded `failure` on a single
unrelated real-PG setup error -- `test_kernel_cancel_bridge_real_pg`, `NODE-0030` uncertain
delivery -- with **8,623 passed, 0 failures, 1 error, 23 skipped**. The failure cannot come from
this train's content: train 62 and train 63 differ **only under `docs/`** (four files, no product
code) and train 62's Core run `37401903045` was green, so by elimination it is environmental. The
three owned CX01 steps succeeded in attempt 1 too, so VF-CL-04's drill measurement never depended
on the re-run. The attempt number is recorded in `hostedRun` because a reader who opens that run
id will see both attempts, and a record that hid the first would be misleading. Codex card 286
(`#382`) makes that setup deterministic; I reviewed it separately.

**Index version**: `1.0.358`, not `1.0.357`. `#382` branches from the same base and takes
`1.0.357`, so this card steps over it rather than colliding.

## Residual

`ciVerified` stays `false` for VF-CL-04 and VF-CL-05, no card becomes `operationallyAccepted`,
`acceptedCards` stays **0/5**, and VF-CL-05 keeps `independentlyReviewed: false` for the reviewer
to decide. The attested-receipt follow-up that rule 7 describes is still open and untouched here.
