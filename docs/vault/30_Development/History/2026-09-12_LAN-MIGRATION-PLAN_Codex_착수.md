---
doc_id: "HIST-LAN-MIGRATION-PLAN-START-20260912"
title: "2026-09-12 LAN-MIGRATION-PLAN Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T18:14:22+09:00"
source_of_truth: "Git"
---

# 운영 migration 계획과 최소권한 판정

CX-02 무결성 지원, owner Codex/reviewer Claude pending (상위 S12-ST owner Claude/reviewer Codex 유지), basec5d1d39a79f4d30bac7e1799ce7224ccb36ffe4f, branch agent/codex/workspace-bridge. 진행판1.0.43/Codex1.0.24, GUIDE/GOV-AGENT/GOV-GIT1.1.0, ADR096, agent-delivery1.1.0/core-reliability1.0.0.

운영 Alembic 현재 revision을 관리 연결의 READ ONLY metadata 조회로 확인하고 migration DAG의 미적용 목록/파일 hash를 계획으로 기록한다. 실행 권한·backfill·backup 인수를 대신하지 않는다. runtime relation 점검의 열별 SELECT 권한 누락을 수정한다. 운영0023에서 head까지 기존 disposable upgrade 시험을 선택 실행하도록 보완하고 실제 PostgreSQL로 검증한다. 운영 DB migration/역할/Node 변경 없음.
