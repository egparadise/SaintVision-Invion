---
doc_id: "HISTORY-FLEET5-DATABASE-READINESS-20261105-CODEX"
title: "FLEET5 disposable PostgreSQL readiness boundary"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-11-05T16:04:34+09:00"
source_of_truth: "Git"
---

# FLEET5 database readiness

Task `FLEET5-DATABASE-READINESS-20261105`, Orca task `task_58f4ada5c2d8`, dispatch `ctx_77b63db632d7`; owner Codex worker, reviewer Claude through root (not yet requested or performed). Branch `agent/codex/fleet5-database-readiness-20261105`, clean initial base `59f0a3c2ff41ba1ae99a38515a2cdc65b2144067`. Start 2026-11-05 16:04:34 KST, Windows/PowerShell, interpreter `D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe` Python 3.14.7.

Read source boards INDEX-PROGRESS-001 1.0.389 / WORKBOARD-CODEX-001 1.0.350 and latest coordinator boards 1.0.397 / 1.0.358 from `D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault`. Context: GUIDE-001 1.1.0, ADR-INDEX-001 1.37.0, GOV-AGENT-001 1.1.3, GOV-GIT-001 1.1.4, GOV-CONTINUITY-001 1.0.0, INDEX-VIRTUAL-COMPUTER-001 / ROADMAP-VIRTUAL-COMPUTER-001 1.0.0, GOV-CONTINUOUS-001 1.1.0; agent-delivery 1.1.0 and core-reliability 1.0.0. The direct dispatch is the work assignment; task registry and common boards remain unchanged by explicit scope.

Scope: prepare-pilot-database.sh, related meaningful regressions, exact executed-case gate if needed, this unique History/Evidence. No shared/local Docker actions, package installs, device/admin authentication, original-source edits, Obsidian apply, common-board/registry writes, or other runtime changes. Hosted disposable Docker/PostgreSQL and normal branch push/exact-head Core+Docs are authorized. Frozen source59f archive stays unchanged.

Trigger (reported, not reproduced here): guard `ff97cd9e`, Core run41982378091 attempt1 failed during initial preparation with suppressed role-hardening diagnostics; main Core suite never ran. Provisioned installer15 and its executed gate passed. The guard owner alone may retry that same head once; this worker will not do so. The actual cause of that original failure is unproven.

Initial source finding: readiness polls authenticated Unix-socket SQL against postgres, then hardens in the target database. Need actual controlled official-image initialization evidence that temporary Unix service can precede database creation/final TCP availability before choosing a source change. A disposable test-only entrypoint hook can pause immediately before docker_setup_db, with an authenticated socket-positive/TCP-negative observation and later release to the official final server. Raw sensitive diagnostics stay private; public evidence contains classifications/digests only.

Implementation/local/CI/independent review/operational acceptance: all pending at start. First action Codex: add a controlled real-PG regression, execute the unmodified script on hosted disposable CI, preserve failing proof separately, and only then choose the minimal repair. Root owns shared progress and final Obsidian consolidation.

## Baseline regression preparation

Added a second actual-PG case and changed only the exact case-count gate from one to two (zero skips/failures/errors still required). The disposable test wrapper sources the image's own entrypoint, preserves root-to-postgres setup and the original docker_setup_db body, and pauses only its call. It measures authenticated Unix SQL, TCP rejection and target DB absence before allowing the original setup/final server. Image digest/ID, shipped-entrypoint/test-hook/prepare digests, preparation phase exits and owned-resource removal/reinspection go to a public classification-only JSON artifact. Passwords, SQL diagnostics and DSNs are excluded. [Upstream entrypoint inspected 2026-11-05](https://raw.githubusercontent.com/docker-library/postgres/master/16/bookworm/docker-entrypoint.sh) corroborates the socket-only temporary-server ordering; hosted measurement is still pending and the shipped digest is recorded by the test.

Local Windows command `D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe -m pytest -q tests/test_lan_pilot_multinode.py tests/integration/test_lan_pilot_database_real_pg.py --junitxml=dist/fleet5-database-baseline-local.xml` returned0: 39 passed, 5 skipped (3 POSIX-driver/verifier prerequisites, 2 explicit hosted-Linux image prerequisites). This is not actual PostgreSQL execution. Separate serving/route suite returned0, 50 passed. No local Docker commands were executed.

Initial required local docs/ontology/contracts/frontend-integrity/ratchet checks returned0. An extra path-citation command used a nonexistent tool filename and returned2; the runner stopped immediately before sync/commit/push. Corrected to the existing check_doc_path_citations.py and re-running the gated chain before delivery. Detailed command/exit/KST records and console output are in `30_Development/Evidence/fleet5-database-readiness-20261105-codex`; nothing failed has been treated as a passing gate.

Early status delivered to root via Orca message msg_3752c32cae4e. Source prepare blob remains `0a5572cb6206b89c2691c199513ffba9adf8556f`; initial regression blob `232528b317af817462811d21f4249358ba378480`. Root confirmed guard41982378091 retry ownership separately; no duplicate rerun here. Independent Claude review has not occurred. Next Codex action: push a regression-only baseline and dispatch its own hosted Core run, preserve the controlled failure, then repair if confirmed.

16:10 KST: path checker then required --base-ref (exit2, no subsequent action); corrected invocation `tools/check_doc_path_citations.py --ratchet --base-ref 59f0a3c2ff41ba1ae99a38515a2cdc65b2144067` returned0, 290 known baseline citations/no additions. Required sync --check returned0: 2220 managed/16 pending/0 conflicts/no writes. Both failed wrapper invocations are distinct from the passing corrected commands. Gate logs are preserved. Root supplied guard evidence commit f40c38056628ecac88afd5c6ace46b6734ec080b and confirmed its sole same-head attempt2 is in progress; the controlled proof here will have a different source and run ID.
