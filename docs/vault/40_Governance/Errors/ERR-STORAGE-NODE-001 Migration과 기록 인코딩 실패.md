---
doc_id: "ERR-STORAGE-NODE-001"
title: "Migration과 기록 인코딩 실패"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T03:15:23+09:00"
source_of_truth: "Git"
---

# Migration과 기록 인코딩 실패

초기 Core #34386461632/db7eae7에서 새 0008 migration이 실패해 DB fixture가 시작되지 않았다. SQL format의 `%I`를 포함한 script를 SQLAlchemy exec_driver_sql 경로로 실행했다. 민감 진단이 섞일 수 있는 DSN/stderr는 출력하지 않았다.

로컬 PowerShell에서 한글 Python 소스를 pipe로 넘기면서 경로가 물음표로 바뀌어 문서 작성이 실패했고, 해당 pathspec으로 git add/commit도 실패했다. 그때 push된 branch는 기존 base SHA뿐이었다. 이 실패를 구현 push 성공으로 기록하지 않았다.

Obsidian check도 외부 변경 13개 때문에 쓰기 전에 중단됐다. 원본 snapshot/hash를 보존하고 검토한 후에만 동기화를 재개했다.

해결: [[RES-STORAGE-NODE-001 Migration 실행과 UTF8 기록 복구]].
