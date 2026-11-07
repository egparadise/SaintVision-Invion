---
doc_id: "HISTORY-CR90501-FIRST-WORKSPACE-TEST-DELTA-REVIEW-R2-20261107-CLAUDE"
title: "CR-905-01 first Workspace test delta review R2"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-11-07"
source_of_truth: "Git"
---

Task CR90501-FIRST-WORKSPACE-TEST-DELTA-REVIEW-R2-20261107 (Orca task_816b0fa2824f). Claude is the only actual reviewer; the author is Codex B task_82627c80384c, and Root is the sole APPLY owner. The target is `96afd799d49717fd40e4ddabd538d82accbe1958`, whose direct parent is the original implementation `90578f49ea400958fcdbc1ded3908d624e856f57`. The delivery base is my original review `a18095e2aff59433b93bdd755a2d050a26c15546`, which is left unmodified, and the Root checkpoint is `a2513f2f826898c96cc0b9488ce43842c7c8f76e`. Branch: `agent/claude/fleet5-first-workspace-cr90501-delta-r2-20261107`. Pins and reasoning are in [review](../Evidence/fleet5-first-workspace-cr90501-delta-r2-20261107-claude/review.json).

**Verdict: ACCEPT_FIRST_WORKSPACE_R1_CODE_AND_CR90501_TEST_DELTA_KEEP_REAL_DEPLOYMENT_GATES.** It closes only CR-905-01 and inherits the original R1 production review unchanged. Protected bytes are verified: the only existing file changed is `tests/integration/test_workspace_first_intents.py` (+179/−6), and the 0068 SQL SHA-256 is still `8b79f552…05d3`.

The delta separates the old loop into three direct calls on the restricted runtime role. Missing subject and cross-tenant each first prove a valid epoch and a non-killed tenant control, so neither can be mistaken for an epoch failure, and missing epoch is its own case. Each asserts 42501 with its exact message and unchanged owner counts. The intent helper is now called directly, bypassing Python/API validation: a rolled-back positive control proves the baseline passes every guard, and 11 single-property negatives recompute canonical/SHA and assert guard-specific messages. The run helper has a three-row rolled-back positive control and four negatives, each expecting "Current selected intent required". I confirmed that no `public.workspaces` trigger changes the version, so the not-ready cases change status alone. No skip/xfail or blanket catch was added. Mutation sensitivity is reasoned from setup and assertions; no SQL mutants were run.

Checks I ran: git verification of scope, parent and SQL hash; SHA-256 of the Core archive (`c495bcc3…8ea9e`, 14,056,869 B) before any read; and bounded data reads. All 18 direct18 entries match the official XML. Core is 9469 pass / 46 skip and Go 696 / 0 / 1 opt-in skip. Local docs gates are in [local gates](../Evidence/fleet5-first-workspace-cr90501-delta-r2-20261107-claude/local-gates.json). Hosted CI (Core 42378656486, Backend 42374998823, Docs 42375001689) is Root-verified evidence, not my runtime test. The cancelled Core 42374996228 is retained and not counted. Backend 9109 is author-reported.

Retained operating gates O1–O6: a superuser 0068 migrator with no writer memberships; backup and forward-fix only, where no-reversible-tail is not a PASS; control-plane + web redeploy with live Node compatibility confirmation; restricted DSNs/JWKS/profile/roots/provider/signer/TLS/policy/queue/links and a genuinely ready Workspace; fail-closed listing of pre-existing non-CPU workloads; and real approver/votes/Run/output/audit/browser/PC1 SSH/PC5 RAM and Linux VM Node/GPU/storage/renewal/reboot-reconnect/5PC. No migration, deployment, real approval, Run, browser or five-PC acceptance is issued. Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN unchanged.

Next action: Root records the CR-905-01 closure and owns O1–O6 and the live gates.
