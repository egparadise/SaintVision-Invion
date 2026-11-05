---
doc_id: "HIST-FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105-CODEX"
title: "FLEET5 consecutive normal leaf rotation source investigation"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-11-05T18:02:00+09:00"
source_of_truth: "Git"
---

# FLEET5 consecutive normal leaf rotation source investigation

Card `FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105`, Task `task_a9b68a07d157`, Dispatch `ctx_4194506d5037`. Owner Codex; independent reviewer Claude through coordinator. Start 2026-11-05 17:16 KST, clean base `59f0a3c2ff41ba1ae99a38515a2cdc65b2144067`, branch `agent/codex/fleet5-consecutive-leaf-rotation-20261105`.

Read coordinator vault INDEX-PROGRESS-001 1.0.399 and WORKBOARD-CODEX-001 1.0.360; INDEX-VIRTUAL-COMPUTER-001/ROADMAP-VIRTUAL-COMPUTER-001 1.0.0, GOV-CONTINUOUS-001 1.1.0, GUIDE-001 1.1.0, ADR-INDEX-001 1.37.0, delivery 1.1.0 and core-reliability 1.0.0, role/handoff, Git/Obsidian and continuity policies, Backend/Storage plans and task registry. Claude finding is actual `d254fc6a511db108be351a3ba82645341748fea3`; `d7a4e450e569d61887475ad054117c708992743a` records the separate DB readiness review.

Authorized scope is future source only: trace supported server preparation, bundle and worker wrappers; prove two distinct NORMAL cycles using signed fixture identities; repair only a confirmed lifecycle defect and preserve immutable history, key, backups and receipt bindings. No live CA/Node/Docker, private r5/executorB5, source03, clock/receipt reset, board/registry edit or Obsidian apply. Frozen first-wave59f archive and existing48-task/VF-CL/physical-node identity status remain unchanged.

Initial trace: `prepare_leaf_rotation` issues public CSR-bound proposals; batch preparation serializes all active Nodes with one CP leaf; staging CASes restarted Node receipts; commit signs per-Node receipts and leaves CP batch phase `switched`. Worker `finalize` leaves phase `finalized`; only expired-partial supersession unlinks that journal. The venv shell wrapper and standalone `run_worker` execute the same worker entry point without lifecycle retirement. The scheduled runner explicitly does not edit journals. A distinct CP batch is also blocked until its switched journal has a supported retirement; this boundary is reported separately and is not evidence of a live failure.

## Confirmed source defect and design

Before production edits, `main .venv Python3.14.7 -B -m pytest tests/test_lan_leaf_rotation_consecutive.py -q -p no:cacheprovider` failed **exit1 / 1 failed**. The test completed real CSR/Ed25519 issuer/CP-commit/Node-finalize normal cycle7->8, advanced only the fixture clock four days, then prepared a distinct normal8->9 proposal with six-day leaves. Unlike Claude's isolated changed-ID probe, the real path fails earlier: the retained finalized journal selects `installed=True`, so validation expects the successor's NEXT certificate instead of its CURRENT base. `red-two-cycle.txt` preserves the actual failure. Original worker SHA256 is `bca76df80a7bf80a6847e9b115679b1aa3e698d8b3a80ff843aacdd1370cd9b4`; original red-test SHA256 is `601bf7f86eb8121d91d3483e55d980be806c006e465279250923839b71b0f26f`.

Finalization now publishes an immutable public proof, including exact original journal bytes, original proposal bytes, public bundle and both signed receipts. Owned nonredirected directories and regular history files are checked; exclusive staging + fsync + no-overwrite hard-link publication preserves collisions and incomplete evidence. The active slot remains finalized until a distinct normal proposal validates its tenant/Node/epoch/address/chain, preceding target/current generation, exact current certificate/peer-policy bytes, certificate hashes and Node key continuity against that proof. Replacement occurs at the existing durable install-intent boundary; no phase/lock reset or prior-backup deletion occurs. Unknown/null/partial/rolled-back states remain rejected. The standalone entry-point pin is updated to the new source bytes only; lock/wheels and old runtime archives remain unchanged.

A legacy finalized journal without proof remains blocked until an explicit replay of `finalize` supplies its original proposal and signed commit receipt. This exact finalized replay may archive after the old overlap closes, only while its current leaves remain valid and its final peer policy matches; it does not restart. A first finalization outside overlap or an expired replay still fails. Same-batch install resume, finalize idempotence and fresh uncommitted rollback remain valid.

## Local evidence and limits

Evidence directory: `docs/vault/30_Development/Evidence/fleet5-consecutive-leaf-rotation-20261105`.

- `two-normal-cycles.json`: two distinct server-issued **single-Node** normal proposals7->8->9; previous NEXT equals successor CURRENT for both Node and CP; previous/current hashes, finalized-journal/archive digests, four restart-seam calls, unchanged key and previous backup. DB CAS is a fixture store and restarts are injected callbacks; this is source proof, never live acceptance.
- `green-focused-final.txt`: **109 passed / 11 skipped / exit0**, worker rotation + standalone runtime + new consecutive suite on Python3.14.7. After adding successor rollback/expiry cases, `green-consecutive-final.txt` is **38 passed / 5 skipped / exit0**. Suites overlap and must not be added. Windows skips cover actual symlink creation (OS1314) and POSIX ownership; hosted Linux remains required.
- Negatives cover installing/installed/restarted/rolled-back/prepared/staged/switched/unknown/null/empty journals, generation/identity/control drift, current leaf/policy inconsistency, missing/tampered/colliding archives and backups, invalid signature, concurrent lock, install kill points, finalize-publication crashes, legacy byte preservation, expiry and successor rollback. No physical clock, old receipt, live latch or remote state was reset.
- `local-gates.json`: docs, ontology, contract bindings, frontend integrity, single-source ratchet, path-citation ratchet against59f, ontology generation, sync-check and freshness reporter **exit0**; serving-anchor + route tests **50 passed / exit0**. Sync-check:2225 managed /21 pending /0 conflicts /no writes. No Obsidian apply.
- Initial `check_docs` **exit1** was real and preserved in `local-gates-attempt1.json`/`check_docs-attempt1.txt`: PowerShell redirected red/green transcripts as UTF-16. They were losslessly transcoded to UTF-8; subsequent checks exit0. This is an evidence encoding repair, not a change to test outcomes.

## Server batch boundary at the a93 milestone

`prepare_leaf_rotation_batch` rejects any distinct output while the CP batch journal exists; `commit_leaf_rotation_batch` retains phase `switched`. The existing focused test `test_multi_node_batch_shares_one_cp_leaf_and_switches_only_after_all_nodes` confirms that refusal even after both Nodes finalize. No shipped wrapper retires that server journal. This repair therefore establishes consecutive NORMAL Node lifecycle and two complete single-Node server cycles, **not** a second multi-Node/FIVE batch. A server retirement contract needs separate proof of every finalized Node and immutable CP history; no speculative server reset is added. Root received this source boundary with early cause/hash evidence.

Implementation: worker SHA256 `114ae59fd9d5fa41e4ed84d33ebd050dca714106fb9270042901f67ca40ccb60`; launcher SHA256 `199e8b2d6193a8f31393254449a5dfe2e6afef21f0ae918256b30509d31cbf77`. CI and independent Claude review are pending; no full-card/FIVE operational acceptance is claimed. Next first action: Codex pushes this source and dispatches exact Core/Docs; coordinator obtains actual Claude review and decides the separate CP batch-retirement scope. The base59f DB readiness race is not repaired here; any hosted failure is preserved for combined integration with independent84bb. Coordinator owns current-board aggregation and eventual safe Obsidian export; no old vault export.

The preceding section records the original Node-only milestone `a93ec9f1906cf5374fa8e2de172e11be0fd7cbdf`, not the final card scope. Its exact Docs run41995699334 succeeded; Core41995694509 was still running at17:58KST. Root message `msg_0ee0b2f49d8b` explicitly extended this card to the missing public CP retirement/successor contract. The extension, new red/green proof and next actions are recorded in [[2026-11-05_FLEET5_batch_successor_Codex]]; the a93 red/green evidence is preserved in place.
