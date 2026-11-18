---
doc_id: "REVIEW-PR412-R2-20261119"
title: "PR 412 independent re-review"
version: "1.0.0"
author: Codex
status: review
updated: "2026-11-19T05:14:00+09:00"
source_of_truth: "Git"
---
# PR 412 independent re-review

Task task_2fe3b63ccfe9. Disposition **accept the correction at 3f3defb1 and close the blocker recorded at 58f61b2c**. The correction changes only tests/test_core_workflow_cx01.py. This disposition covers the CX01 guard and its hosted evidence.

The parsed workflow has one exact with.name of saintvision-core-evidence across jobs. Its owner is core, its action is actions/upload-artifact@v4, its condition is always(), and its path is dist/. Both the workflow and guard place creation before migrations, migrations before cleanup, and cleanup before upload. The commented-out name fixture yields no parsed name and the suffixed fixture yields a different scalar. Both exercise the real guard and require rejection on valid YAML. Duplicate, renamed, wrong action, missing condition, changed path and early upload cases also passed.

From the clean pinned author worktree on Windows, python -m pytest -q tests/test_core_workflow_cx01.py tests/core/test_recovery_preflight_schema_pin.py returned 16 passed, exit 0. GitHub API commit parents of f143a677310f4fd51f16a377962dae2d7d8dc1f0 were 59f0a3c2ff41ba1ae99a38515a2cdc65b2144067 and 3f3defb16d10d9bada75df653225daf74d7e40b7 in order. Core job 135082273683 printed the same merge SHA after checkout. Its full suite reported 8954 passed, 46 skipped and 2 deselected. Focused CX01 reported 20 passed. Downloaded saintvision-core-evidence artifact 14467157426 from run 44383652777 and inspected core-tests.xml. All 10 integration revision-pin cases and both integration cohort-preflight cases executed and passed. Backend 44383652853 passed on 3.12 and 3.14. Desktop 44383652833 passed. The PR rollup also contained seven skipped jobs.

Next owner is the coordinator for integration sequencing. The scoped PR 411 port, retention of 0067, repeated PG and hosted verification on the resulting candidate, and operating acceptance remain pending. Review evidence is local. No merge, deployment or PR 411 application was performed.
