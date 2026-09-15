---
doc_id: "HIST-LEGACY-ROLE-REPAIR-START-20260914"
title: "2026-09-14 LEGACY-ROLE-REPAIR Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:53:33+09:00"
source_of_truth: "Git"
---

# 공용 역할 재활성화 반복 대응

CX-01 owner Codex/reviewer Claude pending. 17:51 읽기전용운영검사에서 inv_app LOGIN/password 재활성화 다시확인, 직접세션0. 현재integration fixture는수정돼있으나 실제상주서비스의코드경로 agent-codex-dev-environment의 tests/conftest.py에는공용역할LOGIN/PASSWORD변경이남아있다. 현재pytest/alembic프로세스없음. **해당fixture가이번변경을실행했다는증거는없다**.

수정대상별도Codex worktree C:/Project/SaintVision-Invion/agent-codex-dev-environment, branch agent/codex/dev-environment, base97e68af8dfe7b886e72f26efe8f5bb20e717a713, clean확인. 검증된시험전용난수login/정리 helper만backport하고서비스파일은변경하지않는다. 별도폐기PG에서RLS/권한검증. 운영은9월12일기존사용자승인에따라동일NOLOGIN/password NULL을재적용,직접세션재확인/강제종료없음/기존권한보존. 다른Agent작성자귀속/오래된vault전체export없이현재정본에기록한다.
