---
doc_id: "HISTORY-FLEET5-A1-9E2142-INDEPENDENT-REVIEW"
title: "Independent review of the A1 writer-transfer replay"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T05:36:00+09:00"
source_of_truth: "Git"
---

## Disposition

Claude accepts 9e2142a9ec5067fb9ee7ee43609f34ea113b754f on agent/codex/fleet5-runtime-a1-986a845b. The scope is a local, HOLD-only writer-fence prerequisite. The dispatch was task_0a3ed5ea2132 / ctx_e8ffe48b7c9e. Codex wrote the change under task_a5a7ea66e8f6 on review base 055254c1. This review found no blocking defect. It did not modify the Codex branch. Nothing was activated and no live host was contacted. The record is on `agent/claude/fleet5-a1-9e2142-review`. [[2026-11-19_FLEET5_A1_Runtime_Fence]] [[2026-11-19_FLEET5_A1_990978_Independent_Review]]

## What changed

Only `deploy/lan/a1_writer_fence.py` `transfer()` and one new test changed in code. The vault edits are a board note and a History section. `transfer()` now creates a singleton `transfer_receipt` table inside the `BEGIN IMMEDIATE` write transaction. That table holds the predecessor tuple and the successor generation. A call returns the successor without writing only when two things hold. The current fence must equal the requested successor. The receipt must also name the same generation and the exact predecessor, with NULLs for a first transfer. Otherwise the existing compare-and-swap runs, and the receipt is replaced in the same transaction.

## Code reading

- **Atomic commit.** The fence UPDATE or INSERT and the receipt write share one transaction. That transaction is opened explicitly. Python's legacy transaction mode does not open a second one, and `with db:` commits on exit or rolls back on an exception.
- **Replay only while current.** The receipt is a singleton keyed by generation, and the join uses `(singleton, generation)`. A later transfer overwrites the receipt, so an older request can never match again.
- **No ABA.** Generation rises strictly: the UPDATE sets `previous.generation + 1` only when the fence still holds `previous`. Cycling ownership between the same plan and token pairs therefore never reproduces an older tuple.
- **Pre-upgrade ledgers.** A ledger without receipts gives no replay. A transfer from its current owner works and starts writing receipts. A rejected call rolls back the `CREATE TABLE`, so the old ledger stays as it was.
- **Mixed versions.** Suppose pre-9e21 code advances the fence after a receipt was written. The receipt generation then no longer equals the fence generation, so neither request is replayed.
- **Inspection.** `interrupted_a1_hold` and the CLI only read the `fence` table in `mode=ro`. They return only HOLD_WRITER_FENCE or HOLD_CUSTODY_UNRESOLVED, and the CLI always exits 2.

## Probes with disposable fixtures

`probe_writer_fence.py` ran 45 probes on each interpreter. All 90 passed: Python 3.14.7 with SQLite 3.50.4, and Python 3.10.11 with SQLite 3.40.1. Every ledger was a fresh temp directory. See probe-result.json.

| Area | Result |
|---|---|
| Atomic receipt and transfer | After the first and second transfer, the fence row and the receipt row agree. |
| Lost acknowledgement | A child process exits right after commit. The retry from the current owner returns generation 2. A second retry changes nothing. |
| Conflicting retries | Each of these raises ValueError and leaves the fence and receipt untouched: same predecessor with another token or plan; wrong predecessor plan or token; a repeated or different initial transfer. |
| Ownership cycling | Transfers went A1, B2, A3, B4, then a self-transfer B5. Every stale tuple is rejected, including old-generation ABA tuples and a stale self-transfer retry. Only the current request replays. |
| Pre-upgrade ledger | It never infers a predecessor. A lost acknowledgement it cannot prove is rejected, and no schema change is left behind. A current-owner transfer works and can then be replayed. |
| Crash before commit | A raw writer was killed mid-transaction. In a second case, `transfer()` was killed between the fence UPDATE and the receipt write. A process holding RESERVED was also hard-killed. Each time the hot journal rolled back to the last commit, and a normal retry succeeded. |
| Concurrency | 8 threads sent the same request: all 8 got generation 2. 8 threads sent competing requests: exactly one won. 8 separate processes sent 6 identical and 2 competing requests: the 6 identical ones all returned `b@2`, and the 2 others were rejected. |
| HOLD-only | Inspection returned HOLD under an uninitialized ledger, a hot journal, a held write lock, and stale or wrong writers. It reported the last committed owner, and the ledger stayed byte-identical. It does not create `transfer_receipt` on a legacy ledger. All 5 CLI inputs exited 2 with a HOLD reason, including `generation: true`, `"2"` and `{}`. |
| Surface | The public callables are `Writer`, `initialize`, `interrupted_a1_hold` and `transfer`. There is no network, subprocess or signing entry point. |

## Evidence ancestry and CI

- 055254c1 (the Claude 990978 review) and 990978075d9f are ancestors of 9e21. `tools/lan_pilot.py` is still the card150 blob 35c2668690b0. Between 990978 and 9e21, only the fence module and its test changed in code.
- Local, at the exact SHA in an isolated detached worktree: the 6-file gate set gave 505 passed, which matches Codex's figure. `test_a1_writer_fence.py` gave 3 passed. check_docs passed after this record was added. See local-gates.json.
- Hosted, read-only, all at headSha 9e2142a9 and all success. Details are in hosted-ci.json.
  - Backend 44383727603: Python 3.12 and 3.14 each had 9082 passed and 75 skipped, and mlflow-live succeeded.
  - Core 44383720924: core and s01-storage-roundtrip succeeded. Its pytest ran `tests/core/test_a1_writer_fence.py` with 3 cases, and the total was 9440 passed.
  - Documentation 44383714514 succeeded. Unlike the 990978 review, Docs was dispatched at this SHA.
  - Portal Login Journey Harness 44383714007 succeeded.

## Non-blocking findings

1. **Lost-ack evidence is prose only.** Codex's 04:44 KST paragraph claims 505 passed, but nothing new was committed. Evidence/fleet5-a1-runtime-fence/local-gates.json is still the 700b9480 run. This review reproduced the figure, and its own local-gates.json is the artifact. Codex may refresh or reword the paragraph at integration.
2. **Lock waits can raise OperationalError.** Python's default 5-second busy timeout applies. If a transfer waits longer than that for the write lock, it raises `sqlite3.OperationalError`, not ValueError. Nothing is committed, and an identical retry is safe because replay is idempotent. Callers should treat this as retryable rather than as a fence change. No test covers it.
3. **Receipts are not authenticated.** Anyone with write access to the ledger file can forge a receipt, just as they can forge the fence row. Custody of the file is Root's, so this adds no new trust boundary.
4. **Carried over from the 990978 review.** Usage errors also exit 2, so a caller must read stdout for the reason. Under `python -I` the CLI fails its import and exits 1, which is still fail-closed. The empty-ledger limitation after an initialization crash remains.

## Remaining limitations

- **No recovery path.** Inspection is advisory and HOLD-only. Nothing resumes, abandons or completes A1 recovery. The signer still lacks an authoritative ceremony ledger.
- **Single host.** The fence is a single-host SQLite ledger and does not govern every signer in the fleet. The pilot CLI has no transfer command.
- **No live exercise.** No real fleet host, signer or PC was exercised.

## Next owner

Per AGENTS.md, Root (the coordinator) owns publication, integration and canonical vault export. Root also keeps operational custody and crash-recovery integration. Codex owns the high-difficulty work: the signer ceremony ledger and fleet-wide writer enforcement. Codex may also take findings 1 and 2. The review performed no fleet connection, deployment, activation, PR, push or vault export.
