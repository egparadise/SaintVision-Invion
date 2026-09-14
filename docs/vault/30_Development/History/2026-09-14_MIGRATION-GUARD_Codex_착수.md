---
doc_id: "HIST-MIGRATION-GUARD-START-20260914"
title: "2026-09-14 MIGRATION-GUARD Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T13:41:11+09:00"
source_of_truth: "Git"
---

# Migration 시작 전 권한 그룹 검사

CX-01 Codex owner/Claude reviewer pending. base79e8d65b733b9994f9d427d964e28f69c89272c3, agent/codex/workspace-bridge. 진행판1.0.56/Codex1.0.34, agent-delivery1.1.0/core-reliability1.0.0.

Claude87eeb71 helper 보강이 published0001의 실제 실행 경로를 덮지 못하는 범위를 보완한다. 기존migration은 수정하지 않고 online Alembic 진입점에서 실제inv_app/inv_kernel의 LOGIN/SUPERUSER/BYPASSRLS/CREATEDB/CREATEROLE/REPLICATION을 읽기전용으로 검사한다. 합격: 별도 폐기PostgreSQL에서 잘못된그룹은 schema쓰기 전 거부·역할보존, 정상/없는그룹은 fresh upgrade 및 replay 성공. 운영role/credential/schema 미변경. Offline SQL 생성은 실제그룹 검증 증거가 아니다.

## 운영 재발 대응 범위 추가

2026-09-14T13:45:45+09:00 읽기 전용 확인에서 inv_app LOGIN/password 재활성화 발견. 직접 세션0, 실제 서비스 inv_lan_runtime, Windows Python 프로세스 명령 패턴에서 pytest/alembic/test_ 실행 없음. 재활성화 주체는 미확인. 2026-09-12 DB-ROLE-REVOKE 운영적용보고의 사용자 승인에 따라 동일 SQL을 다시 적용하고, 세션·그룹권한·runtime 조회를 전후 검증한다. 세션 강제 종료 및 schema 변경은 하지 않는다.
