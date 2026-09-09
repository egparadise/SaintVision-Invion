---
doc_id: "DEV-CONTROL-INTEGRATION-001"
title: "Codex 인증된 Control Plane 통합 개발 과정"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T02:05:49+09:00"
source_of_truth: "Git"
---

# Codex 인증된 Control Plane 통합 개발 과정

TaskCard: task_id control-integration; sprint S02/S04/S07 통합 경계; area Backend/Core; owner Codex; reviewer Claude; depends_on node-transport(구현/CI/보고 완료, 교차 검토 pending); branch agent/codex/control-integration; base `31f423679107ddc55c9d05566959d6aa69a36e2d`.

입력 GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-DB-001/PLAN-STORAGE-001 v1.0.0, ADR-INDEX-001 v1.5.0, NODE-TRANSPORT-CONTRACT-001 v1.0.0, agent-delivery/core-reliability Skill v1.0.0, baseline task registry v1.0.0. 사용자 남은 모든 작업 진행·critical 외 일반 승인 지시 유지.

OUT-02/04/07 → 인증/권한 위조·취소/재연결·Node 재관측·동시성 증거 → bearer resource-server adapter·project 권한·durable mutation/event cursor·authenticated Node control → 구현·실제 PostgreSQL/TLS/Go/Docker 통합 시험. 운영 IdP/CA 발급·사용자 장비 배포는 미확인 값을 만들지 않고 별도로 기록한다.

Codex core worktree에서만 구현한다. Claude 069ae9f의 src/saintvision과 Gemini c323f55의 apps/web는 별도 schema 및 미검증 주장 때문에 무검토 병합하지 않는다. 읽기 계약 검토 및 명시적 adapter 인계를 남긴다. 다른 Agent 검토 완료를 대행하지 않는다. baseline 48 task와 12 Outcome의 선행/실장비 합격을 구현 수로 대체하지 않는다.

scope: 공개 API의 검증된 identity·프로젝트 grant·승인 vote/취소·이벤트 재연결, Node mTLS 관측과 정지 control, 권한/상태 변경 경쟁, 실제 CI와 인계. 남은 Storage/RunGraph/운영 항목은 증거별 차이로 정리하고 수행 가능한 후속을 이어간다. raw bearer/개인키/Node permit argv를 공개 응답·로그·Obsidian에 싣지 않는다.

## 2026-09-10T02:16:46+09:00 구현과 로컬 검증

Python 138 passed / 136 skipped exit 0; JWT 신규 24건 포함. Windows Go test ./... exit 0 및 Linux cross-build exit 0. 신규 Run cancel/approval/SSE/PostgreSQL 7건, 실제 mTLS Node 관측·취소 6건과 Go 동시 cancel 2건은 CI에서 실행한다. [[Codex Control API 인증과 Node 관측 계약]]과 ADR-INDEX v1.6.0을 기록했다.
