---
doc_id: "HISTORY-FLEET5-A1-F4AF7B-INDEPENDENT-REVIEW"
title: "Independent review of the synthetic A1 ceremony ledger"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T06:30:00+09:00"
source_of_truth: "Git"
---

## Disposition

Claude accepts f4af7bb8f571c0cba326aeeeb9888e5514dd118c on agent/codex/fleet5-runtime-a1-986a845b, scoped to a local, synthetic, HOLD-only ceremony-evidence prerequisite. The dispatch was task_174a021b9057 / ctx_7c75c9345756. Codex wrote the change under task_b51f6917ccef. Its parent is the Claude 9e21 acceptance, 4fdc9a33.

No defect blocks that scope. Finding 1 does block one later step: readback must not become the R2 `ceremonyLog` input for recovery decisions until finding 1 is fixed.

This review did not modify the Codex branch, and nothing was activated. No real key, signer or fleet host was used. The record is on `agent/claude/fleet5-a1-f4af7b-review`. [[2026-11-19_FLEET5_A1_Runtime_Fence]] [[2026-11-19_FLEET5_A1_9e2142_Independent_Review]]

## What changed

- **New module.** `tools/a1_ceremony_ledger.py` adds `record()` and `readback()`. Events go into a `ceremony_event` table in the same SQLite file as the writer fence.
- **New test.** `tests/core/test_a1_ceremony_ledger.py` adds 3 cases.
- **Docs.** Codex added a gate file, a History section and board lines.
- **Unchanged.** `deploy/lan/a1_writer_fence.py` is still blob 31baea61, the same as at 9e2142a9. `tools/lan_pilot.py` is still the card150 blob 35c2668690b0.

## Code reading

- **Atomic event write.** `record()` runs four steps in one `BEGIN IMMEDIATE` transaction: the fence check, the CA-first check, the replay check and the INSERT. That transaction uses the same database lock as `transfer()`, so a transfer cannot land between the fence check and the insert. A rejected call rolls back everything, including the table creation.
- **Snapshot readback.** `readback()` opens the database with `mode=ro` and runs a deferred `BEGIN`. The fence SELECT and the event SELECT share one read transaction. The SHARED lock is held across both, so a transfer cannot commit in between.
- **Epoch binding.** Rows are keyed by `plan_digest`, and the digest covers `writerFence.token` and `writerFence.generation`. The fence generation only increases, so a later epoch never matches an older digest. Old rows stay in the table, but the new plan cannot see them.
- **Idempotence.** Repeating the same event ID with the same subject and fingerprint is a no-op. The same subject under a different event ID is a conflict. Event IDs therefore have to stay stable across restarts.
- **HOLD-only.** Nothing in the repository consumes `readback()`. The only references are the test and Codex's gate file. `interrupted_a1_hold` is unchanged and still returns only HOLD values. The module imports only `contextlib`, `pathlib`, `re`, `sqlite3` and `plan_digest`.

## Probes with disposable fixtures

`probe_ceremony_ledger.py` ran 25 probes on each of two runtimes, and all 50 passed:

- Python 3.14.7 with SQLite 3.50.4
- Python 3.10.11 with SQLite 3.40.1

Every ledger was created in a fresh temporary directory from the public p02 R2 fixture. See probe-result.json.

| Area | Result |
|---|---|
| Atomic event write | While a record was paused inside its transaction, a concurrent `transfer()` waited until the record committed. A record after the transfer was then rejected. |
| Atomic readback | While a readback was paused between its two SELECTs, a transfer waited for it, and the readback returned the pre-transfer state. While the last leaf was still uncommitted, a concurrent readback reported the log as incomplete, never as partial. The file hash stayed the same across readbacks, and no journal was left behind. |
| Concurrency | 8 threads sent the same event and produced one row. 8 processes sent 6 identical events and 2 events with a different ID: the 6 succeeded and the 2 were rejected as Conflicting. 6 processes split between two documents with different CA keys, and exactly one key was committed. |
| Restart | A child process exited right after COMMIT, and the identical retry did nothing. A child process exited before the first COMMIT, and the table was rolled back. A process holding RESERVED during the last leaf insert was hard-killed, leaving a hot journal. Readback then reported the last committed state as incomplete and inspection stayed HOLD. A normal retry completed the log. A separate interpreter read back the same log. |
| Missing evidence | Five cases were rejected. No table or no file raised `OperationalError`. CA only, one leaf missing, and an empty fence raised `ValueError`. A leaf before the CA key was rejected and rolled back the table creation. A planned leaf of `None` can never complete. Malformed IDs and fingerprints, a manifest digest mismatch, and duplicate nodes were rejected before any write. |
| Conflicting evidence | Each conflict was refused, and the stored rows stayed the same. The conflicts were a second CA key, the same key under a new ID, a reused ID, a foreign subject, a wrong leaf, the CA key used as a leaf, and the same subject under a new ID. |
| Writer ownership | A plan with an older generation, a wrong token or `generation: true` was rejected for both record and readback, and no table was created. After a transfer away, record and readback were rejected and inspection returned HOLD_WRITER_FENCE. A fresh epoch did not see the 6 old rows. `record()` never changed the `fence` or `transfer_receipt` rows. |
| HOLD-only | With complete evidence, the current owner still gets HOLD_CUSTODY_UNRESOLVED and a stale owner gets HOLD_WRITER_FENCE. The pilot CLI does not mention the ceremony ledger. |

## Evidence ancestry and CI

- **Ancestry.** 9e2142a9 and 4fdc9a33 are ancestors of f4af7bb8. Since 9e21 the only code change is the new module and its test.
- **Local.** These ran at the exact SHA in an isolated detached worktree:
  - Codex's 7-file pytest set gave 508 passed, which matches Codex's figure.
  - The new test passed 3 cases on 3.14.7.
  - The new and fence tests passed 6 cases on 3.10.11.
  - check_docs passed after this record was added.

  See local-gates.json.
- **Hosted.** Checked read-only. All runs are at headSha f4af7bb8 and all succeeded. See hosted-ci.json.
  - Core 44393750942: core and s01-storage-roundtrip succeeded. Its pytest ran `tests/core/test_a1_ceremony_ledger.py` with 3 dots, and the total was 9443 passed, 3 more than 9440 at 9e21.
  - Backend 44393757575: 3.12 and 3.14 each had 9085 passed and 75 skipped, and mlflow-live succeeded.
  - Documentation 44393764341 succeeded.
  - Portal Login Journey Harness 44393751537 succeeded.

## Findings

1. **Conflicting observations are refused, not recorded.** This blocks any consumer. R2's `_ceremony_log_hold` treats a conflict as a HOLD: `caKeysCreated != 1` gives HOLD_CUSTODY_UNRESOLVED, and a foreign or different leaf gives HOLD_FOREIGN_WRITER. `record()` raises ValueError for these observations and stores nothing. If the planned set is completed later, readback returns a clean log with `caKeysCreated: 1`, and `_ceremony_log_hold` on that log returns None. So Codex's sentence "Missing or conflicting evidence rejects readback" holds only for missing evidence. Stored rows cannot conflict, so readback's conflict branch can fire only when the reading document differs from the recording one. Readback also has no way to express a zero-key log or a partial log, and `recovery_action` treats those two cases differently. Before wiring readback into recovery:
   - persist refused observations;
   - make readback reject or HOLD while any refused observation exists;
   - define how zero-key and partial logs are represented.
2. **Planned fingerprints are not digest-bound, and the ledger does not validate the plan.** `caPublicKeySHA256` and `plannedLeafSHA256` are A1 outputs, and `plan_digest` excludes them. Both functions check only `operationManifest.planDigest`. In the probe, a document with a mutated CA key and the same digest made the first record. It pinned that key, and the real document was refused afterwards. R2 `evaluate` rejects both mutated documents (AR-CERT-ROOT, AR-CERT-LEAF and AR-MANIFEST), but the ledger never calls it. Comparing `manifest_pin` alone would not catch a CA-key-only mutation. The fix is to require `evaluate(plan) == []` inside `record()` and `readback()`, or to state the precondition at every call site.
3. **The error contract mixes exception types.** A missing table or file raises `sqlite3.OperationalError`, and the test asserts this. A lock wait longer than 5 seconds also raises `OperationalError`. An unhashable subject raises TypeError. A missing plan key raises KeyError. All of these are fail-closed and commit nothing, so callers must treat any exception as "no evidence".
4. **Stable event IDs are the caller's job.** After a lost acknowledgement, a retry under a new event ID is refused as Conflicting. This fails closed, but a signer adapter that generates a fresh ID on each attempt would get stuck until someone intervenes.
5. **Evidence hygiene is minor.** Codex's local-gates.json records no candidate SHA, uses absolute paths and has no final newline. Its 10 entries do match the "ten command exits" claim. The older Codex board line still says the 9e21 review is pending, although the new line above it supersedes it.
6. **Carried over.** Events are not authenticated, so they share the fence file's trust boundary. The 990978 findings on CLI exit 2 and `python -I` remain.

## Remaining fleet and real-signer dependencies

- **Real signer.** No signer adapter exists. Nothing creates a CA key, signs a leaf, or takes fingerprints from a real key or certificate. Root holds signer custody. A real adapter must emit stable event IDs and derive each fingerprint from the issued artifact.
- **Authoritative ceremony ledger.** The ledger is still synthetic and not wired to `recovery_action` or the R2 executor. The `interrupted_a1_hold` docstring still says the signer has no authoritative ceremony ledger. Findings 1 and 2 come first.
- **Fleet-wide writer enforcement.** The fence and the ledger live in one SQLite file on one host. They do not govern other signers or hosts.
- **Fleet.** No PC1–PC4 or control-plane host was exercised. The Codex board's own transport status, with PC1 still unresolved, is unchanged by this commit.
- **Activation.** Activation remains HOLD.

## Next owner

Per AGENTS.md:

- **Codex** owns the high-difficulty work: findings 1 and 2, the authoritative signer ceremony ledger, and fleet-wide writer enforcement. Findings 3 and 4 are optional.
- **Root (the coordinator)** owns integration, publication, canonical vault export, signer custody and operational integration.
- **Claude** re-reviews after Codex addresses findings 1 and 2.

This review performed no fleet connection, real key use, deployment, activation, merge, PR, push or vault export.
