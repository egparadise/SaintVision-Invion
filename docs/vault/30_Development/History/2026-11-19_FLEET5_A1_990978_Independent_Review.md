---
doc_id: "HISTORY-FLEET5-A1-990978-INDEPENDENT-REVIEW"
title: "Independent re-review of the standalone interrupted A1 inspection"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T04:39:27+09:00"
source_of_truth: "Git"
---

## Disposition

Claude accepts 990978075d9fe53fe9c1c8f11b3bdf0e4d4f64e3 on agent/codex/fleet5-runtime-a1-986a845b as a HOLD-only prerequisite. The blocker from msg_353a0df9eb55 on 700b9480 is closed. Dispatch was task_dfb422639644 / ctx_13d37d696789. Codex wrote the change under task_319373acf0fd. This review did not modify that branch. Activation stays off.

## Original blocker

| Check at the exact SHA | Result |
|---|---|
| `tools/lan_pilot.py` blob | 35c2668690b0681ab87da86099400e83f39d098b. This equals 986a845b and the card150 pin. 700b9480 had 1a31ae9f. |
| All five `toolGitBlobSHA1` pins in Evidence/card150-intranet-pki-lan-pilot.json | Each one equals `git rev-parse 990978075d9f:<path>`. |
| card150 evidence JSON and tests/test_intranet_pki.py | Byte-identical to 986a845b. The historical evidence was kept, not rebound. |
| `test_public_pilot_evidence_is_redacted_and_bound_to_the_tooling` | Passed locally in an isolated detached worktree. Passed in hosted Core junit: 9485 cases, 0 failures, 0 errors. |

## Standalone CLI

`deploy/lan/inspect_interrupted_a1.py` imports only `Writer` and `interrupted_a1_hold`. It has no provisioning, transfer, signing or recovery entry point. No tracked reference to the removed `inspect-interrupted-a1` subcommand remains. The probe script ran 37 probes on each interpreter, 74 in total, and all 74 passed on Python 3.14.7 and 3.10.11. It used disposable directories and an unrelated working directory. See probe-result.json in the evidence directory.

- **Missing state or uninitialized ledger.** Both report HOLD_WRITER_FENCE with exit 2. A missing state directory is not created.
- **Matching owner.** Reports HOLD_CUSTODY_UNRESOLVED with exit 2. After 21 inspections the state directory is byte-identical and has no journal sidecar.
- **Wrong identity.** A wrong token, plan or generation yields HOLD_WRITER_FENCE. So does a stale generation 1 after a transfer, while the current generation 2 matches.
- **Malformed expected-writer file.** Each of 16 inputs yields HOLD_WRITER_FENCE with exit 2. The inputs were: a string, bool, float or zero generation; an empty or null token; a missing key; `{}`; a list, string or number; invalid JSON; non-UTF-8 bytes; an empty file; a missing file; a directory.
- **Damaged or locked ledger.** HOLD_WRITER_FENCE with exit 2 in each of these cases: another connection holds an exclusive lock; the ledger file is empty; it holds random bytes; it is a directory; `--state` is a regular file; a forged schema stores the generation as text.
- **Crash between file reservation and schema.** A re-initialize then raises FileExistsError. This confirms the documented limitation.

## Test coverage

The new subprocess test covers three outcomes: a missing state, a matching owner with a byte-identical ledger, and a malformed `{}` writer. Ownership mismatch and concurrent transfer remain in the existing unit test `test_interrupted_a1_fence`. The 498-test local set plus tests/test_intranet_pki.py gave 504 passed at the exact SHA. tools/check_docs.py passed.

## Exact-SHA hosted CI

All four runs are read-only observations at 990978075d9f and are recorded in hosted-ci.json.

- Backend 44376440429 succeeded. Python 3.12 and 3.14 each had 9081 passed and 75 skipped, and mlflow-live succeeded.
- Core 44376434506 succeeded, including s01-storage-roundtrip.
- Portal Login Journey Harness 44376433707 succeeded.
- Documentation Build did not run at this SHA. On this branch it runs only by workflow_dispatch, and no dispatch was made. The local docs gate passed, and the coordinator may dispatch it before integration.

## Non-blocking findings

1. The correction paragraph says local gates now include tests/test_intranet_pki.py and both HOLD outcomes. The committed Evidence/fleet5-a1-runtime-fence/local-gates.json is still the 03:22 KST run from 700b9480 and does not show that test. The exact-SHA hosted Core junit and this review supply the missing evidence. Codex should refresh the file or reword the paragraph at integration.
2. The CLI uses exit 2 for both HOLD reasons, and argparse usage errors also exit 2. A usage error leaves stdout empty and is still fail-closed. A caller must read stdout to learn the reason, not rely on the exit code.
3. The script finds `a1_writer_fence` through the script directory on sys.path. Under `python -I` it exits 1 with empty stdout and ModuleNotFoundError. This is fail-closed but not a HOLD reason.

## Remaining runtime limitations

- **No resume or recovery path.** Inspection is advisory and HOLD-only. No path resumes, abandons or completes A1 recovery. The signer still has no authoritative ceremony ledger, so a matching owner yields HOLD_CUSTODY_UNRESOLVED.
- **Single-host fence.** The fence is a local SQLite ledger on one host. It does not yet govern every signer across the fleet. The pilot has no provisioning or transfer commands.
- **Initialization crash.** A crash between reserving the file and creating the schema leaves a ledger that cannot be initialized again. Inspection then holds, which is fail-closed. An operator must remove the empty ledger.
- **Lost acknowledgement.** A committed transfer whose acknowledgement was lost cannot be retried idempotently. The caller must reconcile ownership first.
- **No live exercise.** No real fleet host, signer or PC was exercised.

## Next owner

Per AGENTS.md, the coordinator, Root, owns publication, integration and an optional Docs dispatch. Root also keeps operational custody and crash-recovery integration. Codex owns the high-difficulty work: signer ceremony ledger, fleet-wide fence enforcement and the idempotent transfer contract. Codex should also handle finding 1. No fleet connection, deployment, activation, PR or vault export was performed.
