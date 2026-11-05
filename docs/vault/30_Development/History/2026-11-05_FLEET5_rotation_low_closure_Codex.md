---
doc_id: "HIST-FLEET5-ROTATION-LOW-CLOSURE-20261105-CODEX"
title: "FLEET5 immutable staging residue and precise supported lifecycle closure"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-11-05T18:52:00+09:00"
source_of_truth: "Git"
---

# FLEET5 immutable staging residue and precise supported lifecycle closure

Same card `FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105`, Task `task_a9b68a07d157`, Dispatch `ctx_4194506d5037`, owner Codex / actual independent reviewer Claude through root. Branch `agent/codex/fleet5-consecutive-leaf-rotation-20261105`, base milestone `8b53fbfef107837602b1b2f700e1f8e7bae28638`, original base59f. Required doc/skill versions and earlier evidence are in [[2026-11-05_FLEET5_consecutive_leaf_rotation_Codex]] and [[2026-11-05_FLEET5_batch_successor_Codex]]. No board/task-registry, live hardware or private runtime action is part of this delta.

Actual Claude source review `b852f9e089bac41fc19bd6060230aef90823f885` is **ACCEPT**, no High/Medium findings, with79 passed/10 capability skips and five independent probes including three consecutive two-Node batches. Codex read its actual JSON at Git object `docs/vault/30_Development/Evidence/fleet5-20261105-claude/consecutive-rotation-8b53-review.json`. Root independently verified that review's Docs42003881586 success and authorized this narrow follow-up in `msg_efc20b4eded2`; the8b acceptance is not represented as acceptance of this later delta.

## L1 actual failure and minimal repair

Using real Node finalize and CP retirement fixture paths, the test crashes immediately after the actual `os.link` succeeds and before staging unlink. On8b it reproduced equal `.next` residue surviving exact replay; it also reproduced a terminal CP journal left by the prior source. Initial regression **9 failed /2 capability skips /exit1**, then with the legacy-terminal case **10 failed /2 skips /exit1**. Original legacy red-test SHA256 `21d55342ae8da4d30e6652999841d80ebae373242f8bea147f21f3f5d43e4e7e`. The exact raw red transcript text is preserved in `low-closure/raw-red-transcripts.json`; display logs only trim trailing spaces.

The shared immutable publisher first verifies that the canonical archive is a regular, permitted-owner/mode file with exactly the expected bytes. If `.next` exists, it must independently pass the same checks and equal those bytes. Only a publishing replay unlinks that verified duplicate and fsyncs the parent on POSIX; preflight never removes it. Unequal, empty, partial, foreign-owner/mode, symlink or otherwise ambiguous residue is refused and preserved. The canonical archive's content/inode is unchanged. This retires a redundant staging link after completed publication; it never clears a journal, lock, backup, key, certificate or receipt.

The CP terminal retirement replay invokes that same publisher only **after** verifying all Node proofs, the signed CP archive, current authority/DB channel and exact receipt byte binding. This one call is required to clean a legacy already-terminal residue produced by8b; changing the publisher alone would leave that CP path permanently unchanged. First-publication Node/CP crashes and exact already-terminal replay are both exercised. No API/schema/package or credential change was introduced.

Focused rotation/archive suites: **162 passed /18 Windows/POSIX capability skips /exit0**. After adding two foreign-owner metadata-injection cases, final residue suite is **10 passed /4 Windows/POSIX skips /exit0**; these suites overlap and are not added. Foreign-owner/mode and symlink execution remain Linux CI requirements. Existing two/five-Node complete normal cycles, legacy and rollback tests are in the focused suite.

## L2/L3 contract closure and metadata

Per root, L2 remains strict: retain the original transferred attestation bytes, including encoding, whitespace and line endings. JSON reformatting is not a supported crash-replay recovery path. README now says so explicitly; no broader receipt acceptance or canonicalization design is introduced.

L3 README now explicitly requires the same full active membership, tenant, epoch, pinned CA, addresses and Node/CP keys. Add/remove/revoke/re-IP/authority/key changes block retirement or normal succession. This source does not support arbitrary cohort/key changes. A new five-PC cohort should initialize all five only when ready; no new two-Node cohort is created here, and existing r5 remains untouched. Root's integrator owns future setup classifier/registry adaptation: bare `finalized` never proves closure; canonical signed archives and every member proof must verify. No private classifier/registry was changed by this worker.

Actual delta worker SHA256 `9219cd817778278cb5e92ef4d4ed08b666d6dfe7ab727ee9e660cf1d8a0ca68b`, repinned in the standalone launcher. CP SHA256 `e1437600dad2231f40b24cb44d7c3edf1c147e42bc68d39dad2ebb0c9b51f574` / Git blob `111922523062608efeb02f81de82f0b41a8189fe`. Under the explicit recomputation authorization, ONLY Card150's two current lan_pilot hash/blob fields advanced from8b values. Every other JSON field, observedAt, source/controlPlaneToolingCommit, other hash and base59f DB preparation pair compares exactly equal (`low-closure/tooling-pair-applied.json`). Historical observations are not relabeled as measurements made with the new tooling.

## Delivery state and next action

New evidence is isolated under `docs/vault/30_Development/Evidence/fleet5-consecutive-leaf-rotation-20261105/low-closure`; a93/c540/8b evidence is preserved. Required local docs/ontology/contracts/frontend integrity/single-source and path ratchets/ontology generation/sync-check/freshness reporter all returned **exit0**, and serving/route tests are **50 passed /exit0** (`low-closure/local-gates.json`). Normal commit/push, metadata-bound head check, exact final Core/Docs and actual Claude delta review are next. At18:52KST8b Core42001883513 still ran its full pytest step; its terminal outcome must be preserved before a same-ref Core dispatch could supersede it. It is not silently rerun. No independent acceptance of this delta or terminal new CI success is yet claimed.

Next owner Codex completes the local/source delivery and hands exact SHA/hashes to root for actual delta review; root integrates accepted future source with other independent fixes and adapts future setup verification. Source59f first-wave archive, source03/executorB5/private r5, clocks/claims/latches/pins/schedules, physical identities/permissions, original48-task/VF-CL and FIVE operational acceptance are unchanged. No Obsidian apply or old-vault export.
