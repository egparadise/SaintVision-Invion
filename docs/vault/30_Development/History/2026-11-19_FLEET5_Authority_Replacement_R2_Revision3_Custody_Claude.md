---
doc_id: "HISTORY-FLEET5-AUTHORITY-REPLACEMENT-R2-REVISION3-CUSTODY-20261119-CLAUDE"
title: "FLEET5 authority replacement contract R2, revision 3: custody reconciled with the signing log before abandon (proposed)"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-19T02:39:01+09:00"
source_of_truth: "Git"
---

Orca task_5bf1837a153a, dispatch ctx_2c36507be87c.

| Item | Value |
|---|---|
| Branch | `agent/claude/fleet5-r3-custody-hold-20261119` (reused worktree `fleet5-authority-replacement-r3-20261119`, no new worktree) |
| Base | reviewed candidate `ab22abd1f4947a0c588f54601118a6c190fe5f98` through its evidence head `eaa73b9f` (hosted CI snapshot only), both preserved unchanged |
| Review addressed | Codex independent review of `ab22abd1`, `docs/vault/30_Development/History/2026-11-19_FLEET5_ab22_Independent_Review.md` |
| Review copy location | reviewer checkout `D:/Project/sv-r3-ab22-review`, commit `a8c9aea2`, not committed on this branch |
| Review sha256 (committed blob at `a8c9aea2`) | `50c4004f7ab4848d20b2c88218d5c422c2c8277f451e737e3aa372c09d2ad545` |

The full review was read first. Only its high-priority finding asks for a change. Every other row is preserved or closed in the model, so this revision changes nothing else.

**What was not touched:** the reviewer checkout, the R1 artifacts, any runtime code, any live credential, SSH, DB, Docker or key. This is fixture and source work only. There is no operational change. The Nov18 instance stays HOLD.

**Roles.**
- Claude authored this revision.
- The independent re-review goes to Codex and has **not been performed**.
- Root owns DB recovery, custody, PC1 and operational acceptance.

## The finding

With A1 in flight and the writer fence held, `recovery_action` returned ABANDON_BEFORE_NEW_TRUST as soon as custody read `NO_NEW_KEY`. It did that before it looked at the ceremony log. The fence regression `test_r2f4_interrupted_a1_decides_nothing_outside_the_live_fence[*-no-key]` built its "no-key" state from a log with one CA key and two signed leaves and a plan that records the ceremony outputs. It then expected abandonment. A fence proves who may write. It does not prove what was issued, so that state is contradictory custody evidence.

## What was done

Commit `4a495f70` (source and fixtures):

| Area | Change |
|---|---|
| `recovery_action` | Custody `NO_NEW_KEY` abandons only when `_a1_no_key_hold` finds every witness in agreement: the ceremony log is read back with `caKeysCreated = 0` and no signed entry, and the plan records no A1 output. An absent log, a logged CA key, any logged signed leaf (Node or CP) or any recorded output is HOLD_CUSTODY_UNRESOLVED. The fence check still runs first, so a lost fence is HOLD_WRITER_FENCE in every case. |
| `ceremony_outputs()` | One list of the 19 A1 output fields (new CA, CP client, staged and final anchor bundles, each member's leaf, planned leaf hash and planned policy). `ceremony_missing()` now derives from it, so the durable-A1 completeness check and the no-key check read the same fields. |
| Fixtures | p03 (coherent abandon) now carries an explicit zero-key, zero-signature log. New p50 is the reviewed contradiction with expectation HOLD_CUSTODY_UNRESOLVED. New r62 is the same state claiming ABANDON, rejected as AR-RECOVERY-MISMATCH. The corpus is now 113 documents (1 instance, 50 positive, 62 rejection). |
| Corrected regression | The fence test is parametrized over three custody states. Under a held fence: key present → RESUME_FORWARD, coherent no-key → ABANDON_BEFORE_NEW_TRUST, the old contradicted shape → HOLD_CUSTODY_UNRESOLVED. Under each of the 8 fence faults all three are HOLD_WRITER_FENCE and the executor refuses. |
| New tests `test_ab22_*` | At the `recovery_action` and `evaluate` boundaries: coherent no-key abandons for both A1 outcomes (`UNKNOWN`, `FAILED_BEFORE_MUTATION`) and the executor refuses to resume it; p03 is that state; six log contradictions × both outcomes hold, with a claimed ABANDON rejected AR-RECOVERY-MISMATCH; each of the 19 recorded output fields alone holds; the reviewed state holds even after its log is replaced by a zero log, because the plan still records outputs; an empty log under custody `NOT_READ`, `UNKNOWN` or `NEW_KEY_PRESENT_MISMATCH` holds. |

The contract [[Proposed FLEET5 authority replacement and advance-renewal contract R2]] is now 1.2.0. It gains a *Revision 3 changes* table, two ceremony-log decision rows, a finding-to-tests row and the revision 3 mutation record.

## Verification

Environment: Windows 11, `PYTHONUTF8=1`. The gate ledger used Python 3.10.11, the reviewer's interpreter. The focused runs during development used the owner venv's Python 3.14.7.

| Check | Result |
|---|---|
| Baseline at `eaa73b9f` (3.14.7) | R2 gate 357 passed; generator `--check` exit 0 |
| After the checker change, before the test correction | exactly the 8 `[*-no-key]` cases of the reviewed regression failed (ABANDON expected, HOLD returned); 351 passed |
| R2 gate after the change (3.14.7) | 405 passed (357 − 16 old fence cases + 24 fence cases + 38 `test_ab22_*` + 2 corpus cases for p50 and r62) |
| Revision 3 mutants (`mutation-harness.py.txt`) | 6 of 6 killed; checker sha256 `056e4d81…5b759a71301` before and after |
| Local gates (`local-gates.json`, Python 3.10.11, head `4a495f70` with these docs uncommitted) | 14 of 14 exit 0: check_docs (1280 documents), path citations ratchet against `eaa73b9f`, contract bindings, frontend integrity, test_sync, ontology generation, ontology, single source ratchet, sync check (3814 managed, 20 pending exports, 0 conflicts), R1 checker 45 documents, R1 drift, R2 checker 113 documents, R2 drift, pytest 560 passed (405 R2 + 155 R1) |
| Driver slip, recorded | The first ledger run was given a malformed base ref by me, so only the path-citation gate exited 1 ("not a commit"). The driver was rerun with the full SHA `eaa73b9f49b3570dfdae40e49061b7b416f1c844`, and the committed ledger is that rerun. |

Evidence folder: `docs/vault/30_Development/Evidence/fleet5-authority-replacement-r2-revision3-custody-20261119-claude/`.

Hosted CI: none has been read yet for this branch. The handoff to the coordinator reports the hosted run IDs at the exact SHA once they are dispatched and read back.

## Next

- **Codex:** independently re-review commit `4a495f70` and the docs commit on top of it, at the exact SHAs reported in the handoff.
- **Root:** owns operational acceptance, DB recovery, custody, PC1 diagnosis and the runtime cards listed in the review. Runtime ceremony tooling must write the log before it creates any key, because an absent log now always holds.
- **Claude:** no further action unless the re-review asks for changes.
