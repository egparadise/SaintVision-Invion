---
doc_id: "HISTORY-FLEET5-AUTHORITY-REPLACEMENT-CONTRACT-R2-20261119-CLAUDE"
title: "FLEET5 authority replacement and advance-renewal contract R2 (proposed)"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T02:30:00+09:00"
source_of_truth: "Git"
---

Task FLEET5-AUTHORITY-REPLACEMENT-CONTRACT-R2-20261119 (Orca task_150a776816d0, dispatch ctx_2e57edccd6db). The coordinator instruction is msg_69075d54887a.

| Item | Value |
|---|---|
| Branch | `egparadise/fleet5-authority-replacement-r2-20261119` (isolated revision worktree) |
| Base | R1 evidence head `bb6e028d179495f547921cc2afa57681a68db95b` (contains Root544 `d81d40f8` and R1 `12b67c01`) |
| Review addressed | Codex R1 review, `docs/vault/30_Development/History/2026-11-19_FLEET5_Authority_Replacement_R1_Codex_Review.md` |
| Review copy location | reviewer worktree `fleet5-ca-replacement-review-20261119`, untracked |
| Review sha256 | `5c88dcf38f527a3ee98d85f88a44cdc9516691d987e0a6de28a06ec66ce2d829` |

The full report was read first. It was not copied here because it is the reviewer's file.

**Coordination.** No other worker was editing this scope:
- The R1 authoring dispatch ctx_c2a33ffbd832 is settled and its terminal released.
- No R2 branch existed locally or on origin.
- The R1 worktree now holds another review branch and was not touched.
- The reviewer worktree was not touched.
- The Codex supervision worktree was not touched.
- The Codex custody and preflight files were not touched: `tools/recovery_preflight/*`, `services/node-agent/recoverycandidate/*` and `contracts/proposed/expired-policy-custody-*`.

**Roles.**
- Claude authored R2.
- The independent security review goes to Codex and has **not been performed**.
- Root owns canonical APPLY, SSH, DB recovery and every operation.

## What was done

- Added [[Proposed FLEET5 authority replacement and advance-renewal contract R2]]. Its sections D1–D6 close review findings 1–6. It contains a finding → fixture → test map and a list of ten production runtime integration gaps.
- Added the R2 schema, checker, recovery decision and reference executor model, plus a drift-gated generator, under `contracts/proposed/fleet5-authority-replacement-r2/`. The corpus is:
  - 1 real HOLD instance;
  - 39 positive fixtures, covering all 18 recovery actions;
  - 58 rejection fixtures, covering 30 rejection codes;
  - 1 PC1 handoff;
  - 1 committed full operation manifest for human review.
- The fixtures carry real public PKI:
  - Ed25519 roots, CSRs and leaves are built with `cryptography`, and the checker verifies their signatures, chains, SANs, EKUs and validity.
  - Fixture keys are derived from public labels, so they are deliberately not secret. Only public DER is written.
  - A gate test asserts that no DER value parses as a private key and that no real fleet ID appears in a fixture.
- Added the gate `tests/core/test_fleet5_authority_replacement_r2.py` (224 tests). Core and Backend whole-suite pytest collect it, so no workflow edit was needed.
- **R1 is unchanged.** Its 155 tests still pass, and the R2 gate also runs R1's `check_all()`.
- No live credential, SSH, DB, Docker, certificate or key access was used. Nothing was enrolled, activated, synced canonically or cut over.

## Design decisions worth reviewing

1. **A1 is the ceremony.**
   - R1 required new-CA and leaf hashes in a PROPOSED plan before A1 created the key. That is an ordering inconsistency.
   - In R2, ceremony outputs are forbidden before A1 is attempted (AR-CHECKPOINT-ORDER) and required once A1 is durable (AR-CEREMONY-INCOMPLETE).
   - The plan digest covers only the pre-ceremony frozen inputs.
2. **Pinned manifest.**
   - Embedding every operation's pre/post image in every fixture would have added about 40,000 lines.
   - The plan and journal therefore carry only the pin {planDigest, digest, operationCount}.
   - The manifest itself is recomputed deterministically, and one full copy is committed and gate-checked against its source plan.
3. **Recovery outcome is a quadruple.** The decision is (action, phase, apply, acknowledge). A RESUME that would re-apply a committed CAS (`r50`) is therefore rejected, not only a wrong action enum.
4. **Test oracles are not the checker.**
   - The generator computes expected apply and acknowledge lists from the effects it landed itself.
   - Gate tests drive the reference executor through crashes and duplicate delivery, and assert zero second mutations.
   - A mutation harness confirms each safeguard is load-bearing.

## Verification

Local runs on Windows, Python 3.10.11, cryptography 49.0.0, jsonschema 4.26.0, `PYTHONUTF8=1`:

- `python tools/check_fleet5_authority_replacement_r2.py`: PASS, 98 documents matched their expected verdicts.
- `python tools/generate_fleet5_authority_replacement_r2_fixtures.py --check`: exit 0, no drift.
- R2 gate together with the R1 gate: 379 passed (224 R2 + 155 R1).
- **Mutation harness**, a scratch script that is not committed:
  - It applied 23 single-fault mutants to the R2 checker, each disabling one F1–F5 safeguard, and ran the R2 gate against each.
  - All 23 were killed.
  - The checker sha256 was `257c6e00f9676786051b38cc117508fa0358f00fcd71c4534df61d0e94766ee9` before and after.
- **Two mutants initially survived.** Each exposed a missing test, which was added:
  - A committed effect in an un-journaled next phase needed a test.
  - CA notBefore was masked by leaf notBefore and needed an independent check.

Two test bugs found during authoring were corrected:
- The inventory padding re-added the removed site.
- The deadline arithmetic counted 10 phases instead of 9.

The full local gate set and hosted runs are recorded in `docs/vault/30_Development/Evidence/fleet5-authority-replacement-r2-20261119-claude/`.

## Next

1. **Codex** performs the independent security review of R2: contract, schema, checker, recovery decision, executor model and fixture oracles. The questions are at the end of the contract.
2. **Runtime implementation owners** take the ten runtime integration gaps as separate cards. They need hosted integration evidence on a disposable transactional DB with real ephemeral PKI, interrupted phase effects and duplicate delivery.
3. **Root** recovers the DB and reads it back read-only, decides signer compromise status, measures phase budgets and diagnoses PC1 without secrets.
4. **The author** then revises the real instance toward PROPOSED.
