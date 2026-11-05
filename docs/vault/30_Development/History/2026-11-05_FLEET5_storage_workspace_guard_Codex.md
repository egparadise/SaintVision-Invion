---
doc_id: "HISTORY-FLEET5-STORAGE-WORKSPACE-GUARD-20261105-CODEX"
title: "2026-11-05 FLEET5 storage workspace upgrade guard Codex"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude via root"
updated: "2026-11-05T15:57:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "FLEET5-STORAGE-WORKSPACE-GUARD-20261105"
base_sha: "59f0a3c2ff41ba1ae99a38515a2cdc65b2144067"
---

# FLEET5 storage workspace upgrade guard

Owner Codex worker; independent reviewer Claude through coordinator root. Orca run `run_e57ecd84a7bc`, task `task_30f1fb073ec1`, dispatch `ctx_64e306776a86`. Scope: workspace installer source, simulated installer/rollback regressions and this unique History/Evidence only. No deployment, Docker execution, remote/device/admin changes, shared boards, registry, schema, source originals or Obsidian apply.

## Start and canonical context

Started 2026-11-05 15:31 KST in the newly coordinator-created Orca-managed child checkout `D:/Project/SaintVisionI-Invion/fleet5-storage-workspace-guard-20261105`, base `59f0a3c2ff41ba1ae99a38515a2cdc65b2144067`, initially clean. Renamed only this child's new branch to `agent/codex/fleet5-storage-workspace-guard-20261105`; no other checkout/branch changes.

Read current context from coordinator `fleet-five-orchestration-20261105/docs/vault`: `INDEX-PROGRESS-001` 1.0.396 and `WORKBOARD-CODEX-001` 1.0.357. Required context: `INDEX-VIRTUAL-COMPUTER-001` 1.0.0, `ROADMAP-VIRTUAL-COMPUTER-001` 1.0.0, `GOV-CONTINUOUS-001` 1.1.0, `GUIDE-001` 1.1.0, `ADR-INDEX-001` 1.37.0, `GOV-AGENT-001` 1.1.3, `GOV-GIT-001` 1.1.4, `GOV-CONTINUITY-001` 1.0.0; repository `AGENTS.md`, task registry and relevant storage plan/verification rules. Skills: `agent-delivery` 1.1.0, `core-reliability` 1.0.0, current Orca CLI/orchestration guides. The scoped dispatch overrides routine common-board edits and whole-vault export.

Actual independent input: Claude review `HISTORY-FLEET5-20261105-WORKER-REVIEW-CLAUDE` 1.0.1, finding R4 (possibility pending reproduction). `worker_config.repair_target` validates durable identity and the state volume; `worker_workspace.validate_target` adds profile checks but accepts storage-policy arguments and extra mounts. Installer recreates only the state volume and Docker socket while retaining other command arguments. Rollback reuses `validate_target`, so the new rejection must be separate from its existing backup validator.

## Verification and handoff

Actual Evidence is stored at `docs/vault/30_Development/Evidence/fleet5-storage-workspace-guard-20261105-codex/`. On unchanged source59f the new test file produced **15 failed / 15 passed**, direct pytest exit **1** (expected red regression), with simulated image loading and replacement instead of refusal. After repair, focused workspace/config/storage/readiness produced **101 passed / 0 skipped**, exit **0**. Separate serving-anchor/route gates produced **50 passed**, exit **0**. Provisioned real Linux/Docker installer collection produced **15 skipped / 0 passed**, exit **0** on Windows: 3 workspace installer and 12 storage installer cases are unmeasured locally, not passed.

The new `validate_install_target` runs before idle/image loading/stop and permits only the already validated state volume and the exact writable default Docker socket bind with private propagation. It rejects storage-policy flags (Go single/double dash and equals forms, including empty values) and any unpreserved mount, directing the operator to preserve the Node and use a separate plain Node. The shared `validate_target`, `worker_config` and storage installation/ACL/quota code are unchanged. Tests exercise the install entry point, no subsequent Docker/image calls, unchanged running inspection/private files/previous record, supported observe/test/workspace upgrades and `undo=True` restoration of plain and storage-enabled recorded backups.

Direct source gates: docs, ontology, contract bindings, frontend integrity, document single-source ratchet and path-citation ratchet all exit **0**. Sync **check only** exit **0**, 2219 managed / 15 pending / 0 conflicts / no writes at this checkpoint. The 290 pre-existing path-citation entries remain the baseline; no new/stale entry. No whole-suite local product build or physical acceptance claim.

Pending: normal commit/push, exact-head hosted Core/Docs and actual Claude review through root. Early source findings/test summary was delivered to root in Orca message `msg_55b1838d62e2`.

Interpreter is the existing main-repo Python 3.14.7 at `D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.venv/Scripts/python.exe`, always `-B`/`PYTHONDONTWRITEBYTECODE=1`; no install/pip and no protected r5 interpreter. Windows tests will simulate Docker and the Unix lock boundary explicitly. Actual Docker, device, runtime, lock semantics and physical acceptance are not measured here.

Next action/owner: Codex publishes the guarded source and local evidence, dispatches exact-head Core/Docs and gives root the fixed commit for actual independent Claude review. This is a future source revision; existing source59f first-wave packet/bundle hashes remain separate and unchanged.

## Published checkpoint, 2026-11-05 15:51 KST

Implementation/evidence commit `ff97cd9ef01bf9aebda3313cd90631c247a9f63a` is normally pushed and remote readback matches. Source/committed helper SHA-256 is `83930f4d40be82ba211ba57ea9e8c13218a3f8217cf6d13ae4d6b127536e5b7d`; tests `b4b47fb1b586ff2644189788e8b00846004671e86077a1ed35591b888549041f`. Captured artifact hashes were directly rechecked, exit0. `code-source-mapping.json` separately preserves the original source59f helper digest `da46ab67d0220b705c54bf889c3bf63e18b3bddb327bfe5881969121d43711c3` and unchanged config/storage/launcher bytes; no packet was rebuilt or replaced.

Exact-head Documentation run **41982381571** is completed/success; Core **41982378091** has storage roundtrip success and provisioned LAN installer acceptance in progress at 15:50:49 KST. No Core success claim yet. Root received review request `msg_930144b3c5f4`; actual independent Claude verdict is still pending. Next action: coordinator relays that verdict; Codex then observes terminal CI results, resolves any finding and publishes the final History/Evidence report and report-head Docs check. No `worker_done` until delivery is complete.

Delivery diagnostics: the first staged diff check returned exit2 for whitespace in captured pytest failure tracebacks; text/XML logs were explicitly normalized to UTF-8/LF without trailing whitespace, then staged diff check exited0 and the commit succeeded. An optional Python `-c` hash-verification invocation returned exit1 because Windows PowerShell stripped embedded quotes; the UTF-8 stdin invocation directly verified all hashes with exit0. Neither diagnostic changed product source or its test results.

## Core attempt 1 failed after installer acceptance

Core run **41982378091**, exact source `ff97cd9ef01bf9aebda3313cd90631c247a9f63a`, completed **failure** at 15:54:52 KST in `Verify LAN pilot database scripts with real PostgreSQL`. Initial `prepare-pilot-database.sh` returned exit1 with `Pilot runtime role hardening failed; diagnostics suppressed.` The database JUnit has **1 failure**, and the later main Core pytest/build checks were skipped by the failed gate. This is not a Core PASS. The source guard's provisioned installer step and its executed-evidence gate both succeeded; downloaded JUnit directly confirms **15 tests / 0 failures / 0 errors / 0 skips**. S01 storage roundtrip succeeded separately.

Evidence: `hosted-core-source.json`, `hosted-core-failure.txt`, `hosted-core-attempt1-summary.json`, and copied installer/database JUnit in the unique Evidence directory. Artifact ID **13395590043**, archive digest `88c564a142355e2830840e24546f204bac54477fc92fc97eaf05c1e8f0ec2587`; downloaded to ignored `.work/fleet5-storage-ff97cd9e-core-attempt1`, without executing its contents. Both failing database source/test files are unchanged from source59f. Static inference only: readiness uses a local Unix-socket query, which might observe initdb's temporary server before the target database exists; the suppressed diagnostics do not establish that cause. No database source changes, Docker actions or rerun were performed locally.

Root reply `msg_3a4b885a38eb` confirms actual Claude review is still pending on task `task_5fd9ea4e3779` / dispatch `ctx_ac008a621cfe`; it is not acceptance. Core failure was escalated to root as `msg_47919a2e5927` for a same-head CI retry or separate-owner fix decision. Next owner/root: relay actual review and resolve the out-of-scope Core failure; next owner/Codex: record the resulting CI verdict, publish final evidence/report with documentation gate and send truthful delivery outcome. Physical acceptance, integration landing and source59f bundle mapping remain unchanged.
