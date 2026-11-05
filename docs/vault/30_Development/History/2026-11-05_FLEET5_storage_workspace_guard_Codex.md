---
doc_id: "HISTORY-FLEET5-STORAGE-WORKSPACE-GUARD-20261105-CODEX"
title: "2026-11-05 FLEET5 storage workspace upgrade guard Codex"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude via root"
updated: "2026-11-05T15:43:00+09:00"
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
