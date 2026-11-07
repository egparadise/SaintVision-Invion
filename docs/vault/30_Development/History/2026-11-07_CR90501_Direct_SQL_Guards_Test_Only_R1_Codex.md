---
doc_id: "HISTORY-FLEET5-CR90501-R1-CODEX"
title: "CR90501 direct SQL guard test correction"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-11-07"
source_of_truth: "Git"
---

Owner Codex B implements only the test adequacy finding CR-905-01 from actual Claude review `a18095e2aff59433b93bdd755a2d050a26c15546`. The base is `90578f49ea400958fcdbc1ded3908d624e856f57`, branch `agent/codex/fleet5-first-workspace-cr90501-tests-r1-20261107`, task `task_82627c80384c`. The frozen Root checkpoint is `3f481fa870f409d56030b6fa6db877c6f87e5f45`, progress board519 and Codex board480. Root owns boards, canonical APPLY, obligations O1–O6 and the later actual Claude delta review; this author cannot close the finding or approve deployment.

The retained privilege/context test now supplies current epoch and admitted tenant controls to the missing-subject and cross-tenant calls, and distinguishes their exact SQLSTATE42501 messages from the separately retained missing-epoch refusal. Fifteen new direct helper negatives isolate CPU/GPU/memory, closed keys, canonical/spec equality, SHA binding, ready/versioned Workspace, enabled target and tenant binding; Run negatives isolate the selected Workspace/workload versions, digest and readiness. Every mutation bypasses Python validation, and canonical bytes/SHA are recomputed whenever they are not the property under test. Two positive controls read successful restricted-role inserts inside a forced rollback transaction. Owner-visible global counts cover workloads, both Run tables, immutable mapping, outbox and idempotency, avoiding an RLS-hidden zero.

[Case matrix](../Evidence/fleet5-first-workspace-cr90501-tests-r1-20261107-codex/case-matrix.json) identifies the precise intended guard and why earlier checks pass. [Scope proof](../Evidence/fleet5-first-workspace-cr90501-tests-r1-20261107-codex/scope-proof.json) records unchanged protected trees and the immutable0068 SQL SHA256 `8b79f55289661d7590dbe24e60d60d319360e7fcaf35454fe21c722fe11905d3`. Existing replay/concurrency/revocation/rollback/GUC assertions are retained. No SQL, product, DTO, frontend, workflow, dependency or security catalogue pin is edited.

Main performs source/AST/data and the eight permitted lightweight gates only. All PostgreSQL execution belongs to fresh exact-SHA hosted Core/Backend/Docs workflows; their final receipts will be published after execution, with failures retained. Frontend42368189302 belongs to905 and is retained solely as unchanged-component evidence. Local gate commands, exit codes and full new sync-state before/after bytes are in this task's Evidence directory; no historic snapshot is reused, no APPLY occurs, and pending old-vault exports must not be applied.

Next action: Codex B completes explicit test-only commit/push and exact hosted CI/report, then Root verifies the packet and starts one actual Claude delta re-review. The production/no-defect review statement remains distinct from this unresolved test finding. Real identities, approvals, ready Workspace, PC3 routing, user Run, browser and five-PC acceptance are not exercised here. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN remain held.
