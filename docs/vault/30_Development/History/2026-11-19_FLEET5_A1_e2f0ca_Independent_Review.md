---
doc_id: "HISTORY-FLEET5-A1-E2F0CA-INDEPENDENT-REVIEW"
title: "Independent review of durable A1 conflict evidence and the reviewed-output pin"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T07:25:00+09:00"
source_of_truth: "Git"
---

## Disposition

Claude accepts e2f0cac3df21c333bbc03f80e683d2ac7eaad2c9 on agent/codex/fleet5-runtime-a1-986a845b. The scope is still a local, synthetic, HOLD-only ceremony-evidence prerequisite. The dispatch was task_ea3cdc342a33 / ctx_351cea98c7b7. Codex wrote the change under task_3b5339418900. Its parent is the Claude f4af7b review, bdf737d8.

Review bdf737d8 left two blocking findings. Within this scope:

- **Finding 1 is fixed in part.** Refused conflicting observations are now stored durably, and readback rejects them. Zero-key and partial logs still cannot be represented.
- **Finding 2 is fixed for the one reviewed fixture.** Record and readback refuse any plan whose outputs differ from the reviewed p02 outputs, and any plan that fails `validate_plan`.

No defect blocks the HOLD-only scope. Readback must still not feed the R2 `ceremonyLog` used for recovery decisions. The prerequisites are listed below.

This review did not modify the Codex branch, and nothing was activated. No real key, signer or fleet host was used. The record is on `agent/claude/fleet5-a1-e2f0ca-review`. [[2026-11-19_FLEET5_A1_Runtime_Fence]] [[2026-11-19_FLEET5_A1_f4af7b_Independent_Review]]

## What changed since bdf737d8

- **New `ceremony_conflict` table.** `record()` writes every refused observation to this table. The write happens in the same `BEGIN IMMEDIATE` transaction as the fence check, and the ValueError is raised only after COMMIT. The table's primary key covers all four columns, so an identical repeat of a conflict adds no row.
- **Readback rejects conflicts.** It reads `ceremony_conflict` in the same snapshot as the fence and the events. Any conflict row for the plan rejects the readback.
- **Leaf before CA key.** A matching leaf that arrives before the CA key event is now stored as a conflict. Before this change it was refused without being stored.
- **Pre-upgrade ledgers.** If a ledger has only one of the two tables, `record()` raises "requires independent reconciliation" and rolls back.
- **Reviewed-output pin.** `_expected()` hashes the binding `{planDigest, ceremony_outputs}` and compares it with a constant, `4f04475c…a7de`, which is the reviewed p02 fixture. It also requires `validate_plan(plan) == []`.
- **R2 refactor.** `evaluate()` is split into `validate_plan()`, which runs the schema, secret, authority, identity, counter, renewal, inventory, window, checkpoint-order and ceremony checks, and the recovery-action comparison. `evaluate()` composes the two.
- **Tests.** The test file now has 11 cases. Four are parametrized conflicts, each checked by a readback in a separate interpreter. Four are plan alterations. One covers the legacy table check.
- **Unchanged.** `deploy/lan/a1_writer_fence.py` is still blob 31baea61, and `tools/lan_pilot.py` is still blob 35c26686.

## Probes with disposable fixtures

`probe_ceremony_conflict.py` ran 22 probes on each of two runtimes, and all 44 passed:

- Python 3.14.7 with SQLite 3.50.4
- Python 3.10.11 with SQLite 3.40.1

Every ledger was created in a fresh temporary directory. A detached bdf737d8 checkout served as the baseline for the legacy-ledger and `evaluate()` comparisons. See probe-result.json.

| Area | Result |
|---|---|
| Conflict persistence | Eight conflict kinds were tested: a second CA key, the same CA key under a new ID (a lost-ack retry), a reused event ID, a foreign subject, a wrong leaf, the CA key used as a leaf, the same subject under a new ID, and a leaf before the CA key. Each was refused as Conflicting and stored exactly once, even after two identical retries. The event rows stayed the same. After the planned set was completed and a valid event was replayed, readback was still rejected as conflicting. |
| Restart and retry | A child process stored a conflict and exited right after the rejection, and a fresh interpreter's readback rejected. A child that was killed at COMMIT never reported a rejection, and it left a hot journal. A read-only readback then returned the last committed log, which was complete. A read-write open rolled the journal back, and both tables were unchanged. Retrying the conflict stored it, and readback rejected. A reader that held SHARED longer than the 5-second busy timeout made the conflict record raise `OperationalError: database is locked`. Nothing was stored, and a retry after the lock was released stored the conflict. |
| Concurrency | 8 processes sent the same CA event: 6 under the same ID and 2 under different IDs. That produced 1 event and 2 conflicts. 8 threads sent the same conflict and produced 1 row, and all 8 were rejected. A conflict commit waited while a readback held its snapshot. That readback returned the complete pre-conflict log, and the next readback rejected. |
| Stale writer | While a conflict record was paused inside its transaction, a transfer waited until the record committed. After the transfer, records and readbacks were rejected with "Writer fence changed" for valid events, conflicting events and identical replays. The file hash did not change and no conflict row was added, so a stale writer cannot poison the new epoch. Inspection returned HOLD_WRITER_FENCE. An older generation, a wrong token and `generation: true` were all refused as unreviewed before any write. |
| Altered plan and fingerprint | All 19 A1 output fields in `ceremony_outputs` were mutated one at a time. Every mutation left `plan_digest` unchanged, and record and readback both refused every mutated plan with no write and no table created. Both checks caught all 19 on their own: the pin and `validate_plan`. A mutated-CA-key document can no longer be the first writer, and the reviewed document then completes. Changes to `planID`, a member address, the manifest (set to None or given the wrong digest), a duplicated member and a secret marker were all refused. Malformed fingerprints, subjects and event IDs were refused before any write and were never stored as conflicts. |
| Pin scope | Of the 50 positive R2 fixtures, the ledger accepts only p02. A checkpoint-only change, such as editing `expectedRecoveryAction`, passes `validate_plan` and is accepted, although `evaluate` reports AR-RECOVERY-MISMATCH. The set of expected fingerprints stays the same, so this does not weaken the ledger. |
| Existing evidence | `evaluate()` gave identical verdicts at bdf737d8 and e2f0cac3 for all 117 contract JSON documents: 51 clean and 66 rejected. The verdict-set sha256 is fefd8280…b717. A complete ledger written by the f4af7bb8 code is refused by `record()` with "reconciliation" whether the event repeats an earlier one or conflicts with it, and the file is not modified. Readback on it raises `OperationalError: no such table: ceremony_conflict`, and inspection stays HOLD_CUSTODY_UNRESOLVED. A ledger with only the conflict table is refused the same way. |
| HOLD-only | Inspection returns HOLD_CUSTODY_UNRESOLVED with complete evidence and also with a stored conflict. A stale owner gets HOLD_WRITER_FENCE. The only code reference to the ledger is its test. `validate_plan` is used only by the ledger and by R2. The pilot CLI does not mention the ceremony. The module imports only `contextlib`, `pathlib`, `re`, `sqlite3` and R2 helpers. |

The unchanged bdf737d8 probe script was also rerun at e2f0cac3, and 18 of its 25 probes passed. The other 7 are explained in prior-probe-rerun.json, and none is a regression:

- 3 probes asserted the defects that this commit fixes.
- 3 reflect the intended pin or the new subject check.
- 1 failed only because its trace hook matched `INSERT INTO`, while e2f0cac3 issues `INSERT OR IGNORE`. That probe was re-proved with an updated hook.

## Local gates and CI

- **Local.** All gates ran at the exact SHA in an isolated, clean worktree, and every one exited 0. See local-gates.json.
  - Codex's 7-file pytest set gave 516 passed, which matches Codex's figure.
  - The ledger test alone gave 11 passed.
  - On 3.10.11, the ledger and fence tests gave 14 passed.
  - The R2 checker matched 113 documents to their expected verdicts.
  - The R2 fixture generator `--check` exited 0.
  - check_docs passed after this record was added.
- **Hosted.** Checked read-only. All runs are at headSha e2f0cac3 and all succeeded. See hosted-ci.json.
  - Core 44403269220: core and s01-storage-roundtrip succeeded. The core log shows the ledger test with 11 dots. The total was 9451 passed and 46 skipped, which is 8 more than 9443 at f4af7bb8.
  - Backend 44403277164: 3.12 and 3.14 each had 9093 passed and 75 skipped, which is 8 more than 9085 at f4af7bb8. mlflow-live succeeded.
  - Documentation 44403290191 succeeded.
  - Portal Login Journey Harness 44403224741 succeeded.

## Findings

1. **Status of bdf737d8 finding 1.** Parts (a), persisting refused observations, and (b), rejecting readback while one exists, are done. Part (c) is still open: readback can return a complete log or raise, but it cannot express a zero-key log or a partial log, and `recovery_action` treats those two cases differently. Every rejection is also one ValueError, while R2 separates HOLD_CUSTODY_UNRESOLVED, HOLD_FOREIGN_WRITER and HOLD_DUPLICATE_EVIDENCE. Before any consumer is wired in, Codex must define how a rejection maps to a HOLD code. Without that mapping, the only safe default is HOLD_CUSTODY_UNRESOLVED.
2. **Status of bdf737d8 finding 2.** Closed for the synthetic scope. The pin is a hard-coded constant for one public fixture, so the ledger cannot serve any other plan, and that includes any real plan. Real use needs a reviewed-plan binding from a source Root controls, in place of the constant.
3. **A conflict poisons the epoch, and nothing can clear it.** This is new, and it raises the severity of old finding 4. The two cases that fail closed are a lost-ack retry under a new event ID and a leaf recorded before the CA key. Both are now stored for good, and readback for that plan rejects forever. A transfer to a new epoch changes `plan_digest`, so the pin refuses the successor plan. The only recovery is a new reviewed plan. A real signer adapter must therefore use stable event IDs and strict CA-first ordering. Codex must also define the reconciliation procedure before real use. Any caller that holds the plan and the current fence can also poison the ledger by sending an unknown subject, because events are not authenticated (old finding 6).
4. **A conflict can be lost when commit is blocked.** If COMMIT is blocked past the busy timeout, the caller gets `OperationalError` instead of `ValueError`, and the conflict is not stored. This fails closed, because nothing is committed, but the caller must retry to get the conflict stored. Old finding 3 still applies: callers must treat any exception as "no evidence". Readback on a pre-upgrade ledger raises `OperationalError`, while record raises ValueError "reconciliation". The two are inconsistent but both fail closed.
5. **Evidence hygiene is minor.** Codex's local-gates.json has 10 entries, all with exit 0, and they match the History claim. It still records no candidate SHA, uses absolute paths and starts with a UTF-8 BOM. The 9e21 line on the Codex board still says the review is pending.

## Operational prerequisites still outstanding

Everything in this list must be done before readback becomes the R2 `ceremonyLog` input, or before anything leaves HOLD.

- **Codex:**
  - define the zero-key and partial log representation, and the HOLD-code mapping (finding 1c);
  - define a reconciliation procedure for an epoch poisoned by a conflict (finding 3);
  - make the authoritative signer ceremony ledger authenticated;
  - extend writer enforcement fleet-wide. The fence and the ledger still live in one SQLite file on one host.
- **Root:**
  - signer custody;
  - a reviewed-plan binding source that replaces the p02 constant (finding 2);
  - operational integration and canonical vault export.
- **Signer adapter, which does not exist yet:**
  - stable event IDs across retries;
  - the CA key event recorded before any leaf;
  - fingerprints derived from the issued artifacts.
- **Fleet:** no PC1–PC4 or control-plane host was exercised. The Codex board's transport state, with PC1 still unresolved, is unchanged by this commit.
- **Activation:** remains HOLD.

## Next owner

Per AGENTS.md:

- **Codex** owns findings 1c and 3, the authenticated signer ceremony ledger and fleet-wide writer enforcement. Finding 4 is optional.
- **Root (the coordinator)** owns integration, publication, canonical vault export, signer custody and the reviewed-plan source.
- **Claude** re-reviews after Codex delivers findings 1c and 3, or before any consumer is wired to readback.

This review performed no fleet connection, real key or signer use, deployment, activation, merge, PR, push or vault export.
