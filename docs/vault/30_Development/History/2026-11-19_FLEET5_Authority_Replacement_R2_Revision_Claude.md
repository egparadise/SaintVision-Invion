---
doc_id: "HISTORY-FLEET5-AUTHORITY-REPLACEMENT-R2-REVISION-20261119-CLAUDE"
title: "FLEET5 authority replacement contract R2, revision 2 after the Codex R2 review (proposed)"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T01:49:19+09:00"
source_of_truth: "Git"
---

Orca task_f0b055d0a9ae, dispatch ctx_1a8f915dd262.

| Item | Value |
|---|---|
| Branch | `egparadise/fleet5-authority-replacement-r3-20261119` (separate worktree `fleet5-authority-replacement-r3-20261119`) |
| Base | R2 evidence head `9a9bc90c3d7b3c2aa1889d8de0d5906fac7e5412`, which contains candidate `14ddc8e9efa198918d433ae1ac21afd66605cb89` |
| Review addressed | Codex R2 review, `docs/vault/30_Development/History/2026-11-19_FLEET5_Authority_Replacement_R2_Codex_Review.md` |
| Review copy location | reviewer worktree `fleet5-independent-review-task723adb91`, not committed on this branch |
| Review sha256 | `a2de6b545983b3e3609bd36663187e840dce4f196b5a79fedc713ae6d6fec7a8` |

The full review was read first. It was not copied, because it is the reviewer's file.

**What was not touched:**
- the reviewer worktree;
- the Codex custody and preflight files (`tools/recovery_preflight/*`, `services/node-agent/recoverycandidate/*`, `contracts/proposed/expired-policy-custody-*`);
- the R1 artifacts.

**Roles.**
- Claude authored this revision.
- The independent review of the revision goes to Codex and has **not been performed**.
- Root owns DB recovery, custody, PC1, canonical APPLY and operational acceptance.

## What was done

The fixes went in place in the R2 files, in the order the review gave. Each fix has its own commit with focused regression tests in isolated fixtures:

| Commit | Fix |
|---|---|
| `17f6b3a3` | Writer fence on interrupted A1 (finding 4, high). Once a mutation was attempted, the live fence (token, holder plan digest, monotonic generation, fresh `readAt`) is checked before any custody, ceremony, abandon, resume or COMPLETE decision. A1 in flight with a key always validates the ceremony log. An absent log, a key count other than 1, or a key the plan did not record is HOLD_CUSTODY_UNRESOLVED. The executor model refuses to sign or apply without the fence. |
| `7d7356c0` | Serving freshness and inventory (finding 3). Challenge issuance age is bounded by `challengeLifetimeSeconds`. Every answer carries a CP receipt time, and the responder clock is bounded by skew. Challenges are one-use through `consumedChallengeNonces`. An authoritative live inventory (CP process registry, instance IDs) must equal the frozen inventory, otherwise the new HOLD_PROCESS_INVENTORY_CHANGED. Freshness, heartbeat and challenge windows are measured plan inputs under contract caps (AR-SERVING-WINDOW). |
| `fbc26157` | Row representation (finding 4). `rowPresent` is removed: absence is omission. The executor never appends a second row for a NodeID. |
| `3bc2f47e` | Terminal validity (finding 5, high). The policy start time is checked at resume. COMPLETE is judged on validity at the final observation, otherwise the new HOLD_VALIDITY_LAPSED. The handoff re-checks validity at its own time and records `validity`. Advance renewal budgets still-serving prior leaves and the installed prior policy (`installedPolicyNotAfter` readback). A committed policy publication reads back the planned validity. DUAL_ANCHOR_OVERLAP needs `overlapRuntimeEvidenceRef`. |
| `afa538c0` | Manifest-scoped identities (remaining question). The opID is the digest of the canonical operation body (epoch, expected version, endpoint, pre and post) under the plan digest. Channel audit and policy journal rows are `{manifestDigest, opID}`. The same opID under another manifest is CONFLICT. |
| `7174b3ee` | Test: a foreign-manifest audit of our opID blocks even at the preimage. The mutation harness had found this case missing. |
| this commit | Contract document 1.1.0 (*Revision 2 changes*, D3–D6, finding table, runtime gaps, reviewer questions), this History, the Claude board and the evidence. |

[[Proposed FLEET5 authority replacement and advance-renewal contract R2]] is now 1.1.0. Its paths and schema ID are unchanged. R2 was never accepted, so nothing consumes the earlier shape, and an R2 1.0.0 document now fails the schema.

**The corpus:**
- 1 real HOLD instance, which keeps the new windows, fence generation and overlap evidence null;
- 49 positive fixtures (new: p40–p49), covering all 20 recovery actions;
- 61 rejection fixtures (new: r59–r61), covering 31 codes;
- 1 handoff, which now carries `validity`;
- 1 full manifest.

The R2 gate has 357 tests (224 before). R1 is unchanged, and its 155 tests pass.

No live credential, SSH, DB, Docker, certificate or key access was used. Nothing was enrolled, activated, synced canonically or cut over.

## Design decisions worth reviewing

1. **A lost fence blocks abandon too.** Abandoning before new trust still writes the journal, so HOLD_WRITER_FENCE now precedes ABANDON_BEFORE_NEW_TRUST. COMPLETE requires the fence as well, because the journal must not be settled by a plan that no longer owns it.
2. **Inventory churn re-plans.** A started replica, a stopped or moved process, a changed kind, or a readback from an unlisted process means the frozen manifest no longer covers the live CP. These hold with HOLD_PROCESS_INVENTORY_CHANGED. A restart of a listed process under a new instance ID only makes that process's readback UNVERIFIED (HOLD_SERVING_EVIDENCE_INCOMPLETE), so a re-read under a fresh challenge resolves it.
3. **One-use is recorded in the journal.** The executor model appends the challenge it acted on to `consumedChallengeNonces`, and `observe()` models the fresh re-read. Enforcing one-use in the CP challenge store is listed as a runtime gap.
4. **Dependencies are budgeted conservatively.** Prior leaves and the installed prior policy must outlive the end of all remaining work, not only the phase where each stops being relied upon. A stale PC2 row hits the anchor-staging gate first, so the dependency rule there is defence in depth. The tests assert the first gate.
5. **COMPLETE uses the safety + skew margin, not the renewal leads.** `renewalDueBy` is reported in the handoff for the consumer.
6. **An equivalent mutant.** `ID-exact-key-not-required` (match the opID only) survives, because the schema limits an audit key to exactly `{manifestDigest, opID}` and any foreign-manifest entry with our opID is already CONFLICT. This is recorded, not hidden.

## Verification

Local runs on Windows, Python 3.10.11, `PYTHONUTF8=1`.

**Per commit**, R2 checker documents and R1+R2 pytest:

| Commit | Documents | Pytest |
|---|---|---|
| `17f6b3a3` | 101 | 418 passed |
| `7d7356c0` | 105 | 474 passed |
| `fbc26157` | 105 | 477 passed |
| `3bc2f47e` | 110 | 501 passed |
| `afa538c0` | 111 | 510 passed |
| `7174b3ee` | 111 | 512 passed |

The generator `--check` reported no drift.

**Mutation harness** (scratch driver, copied as `Evidence/fleet5-authority-replacement-r2-revision-20261119-claude/mutation-harness.py.txt`):
- 29 single-fault mutants, each removing one guard added in this revision. The R2 gate ran with `-x` against each.
- 28 were killed. The 29th is the equivalent mutant above.
- The checker sha256 was the same before and after: `18f386ff3d2142d76948e0b4b51e8f948bbbd841785aeecee7a9ef8ab2cddad9`.
- On the first pass, `ID-foreign-manifest-audit-accepted` survived. That exposed the missing preimage case, and `7174b3ee` adds it.
- Record: `mutation-result.json`.

**Full local gate set:** the argv driver (`local-gates-driver.py.txt`) ran 14 gates individually, 2026-11-19 01:49:51–01:51:01 KST. **All 14 exited 0**:
- check_docs (1279 documents)
- path-citation ratchet against `9a9bc90c`
- contract bindings, frontend integrity, test_sync
- ontology generation, ontology check, single-source ratchet
- sync_obsidian `--check` (no apply)
- the R1 checker (45 documents) and R1 generator `--check`
- the R2 checker (111 documents) and R2 generator `--check`
- pytest R1+R2 (512 passed)

Record: `Evidence/fleet5-authority-replacement-r2-revision-20261119-claude/local-gates.json`. It was taken at head `7174b3ee` with this commit's documents uncommitted.

**Hosted CI:** the branch is pushed, and Docs, Core and Backend are dispatched at the final SHA. The run IDs and their state at handoff are in `hosted-ci.json` (a snapshot; confirm verdicts at the exact SHA). Separately, the R2 candidate's own runs at `14ddc8e9` have since completed: Docs 44342327704, Core 44342335017 and Backend 44342342100 are all **success**. The R2 `hosted-ci.json` snapshot had recorded Core and Backend as in progress.

**Stamp note.** R2 1.0.0's `updated` stamp (02:30 KST) was later than its commit (01:01 KST). This revision uses real KST times.

## Outstanding runtime work

The production runtime has none of these mechanisms. Each needs its own card with hosted integration evidence on a disposable transactional DB with ephemeral PKI:
1. Transactional fenced admission, with a monotonic fence generation and reservation verification at commit.
2. Exact-preimage CAS and audit rows keyed by `{manifestDigest, opID}`.
3. Rooted leaf verification.
4. Signed-policy bytes, validity and journal readback.
5. Live process registry with instance IDs, and per-process trust readback.
6. CP-clock challenge issuance with receipt times and one-use enforcement in the challenge store, plus fresh handshake observation.
7. Node anchor reload and retirement, plus overlap runtime evidence. Quiescence needs its own proof.
8. Measured phase budgets and serving windows.
9. Deterministic ceremony tooling.
10. A fenced executor whose commit point is the DB transaction.

## Next

1. **Codex** independently reviews revision 2 at the exact SHA reported in worker_done. The questions are in the contract's *Verification and handoff*.
2. **Root** handles DB recovery and read-only readback, the custody and signer decision, fence and budget measurement, PC1 diagnosis and operational acceptance.
3. **Runtime owners** take the ten gaps as separate cards.
