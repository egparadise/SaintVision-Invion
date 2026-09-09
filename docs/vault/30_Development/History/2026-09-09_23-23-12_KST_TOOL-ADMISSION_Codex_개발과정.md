---
doc_id: "DEV-TOOL-ADMISSION-001"
title: "Codex ToolGateway 실행 허가 개발 과정"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-09T23:23:12+09:00"
source_of_truth: "Git"
---

# Codex ToolGateway 실행 허가 개발 과정

TaskCard tool-admission; owner Codex; reviewer Claude; branch agent/codex/tool-admission; base `0fbf66e2487cfdea54de66aadcb8c8b646335591`.

입력: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-DB-001/PLAN-S03 v1.0.0, ADR-INDEX-001 v1.2.0, APPROVAL-CONTRACT-001 v1.0.0, agent-delivery/core-reliability v1.0.0. 사용자 이어서 진행 및 critical 외 일반 개발 승인 유지. PR #1/#2 open draft, review/comment 없음을 API로 확인했다.

목표 OUT-03/AC-03·OUT-04/AC-04 → 증거(동시 재전달 단일 claim, 현재 정책·권한·lease·Node 재검사, 실행 설정 변조 차단, txn rollback) → ToolGateway claim·SandboxLaunchSpec 계약 → S03-BE 및 S04 실행 연결 사전 검증. S02 선행/독립 검토 미완료로 baseline 48개 task는 승격하지 않는다.

scope: 서버 내부 admission/inbox, 고정 Sandbox launch 계약과 config allowlist, migration 0003, JSON Schema와 Python/TS/Go 생성물, 합성 tests/CI/docs. 실제 Node mTLS·OS 격리 driver·임의 프로세스 실행·장비/운영 배포는 후속이며 이번 claim 성공을 외부 실행 성공으로 쓰지 않는다.

합격 요구: commandId별 신규 실행 허가 1개; 같은 message 재전달/응답 유실/서비스 재생성 시 신규 허가 0개; 위조 event·다른 Node·취소·정책 deny/unavailable·권한 철회·epoch/lease/Node stale·Sandbox 완화 차단; claim/outbox 실패 전체 rollback. 이 경계에서 raw argv/secret은 durable audit/outbox에 저장하지 않는다.

명령·exit·SHA·실제 CI와 Obsidian 결과는 검증 보고에 기록한다. Windows sandbox 초기화 오류는 지속되므로 승인된 외부 실행으로 범위 내 작업을 진행한다.

## 2026-09-09T23:38:28+09:00 로컬 구현·검증

python tools/generate_contracts.py exit 0; pytest -q --junitxml=.work/tool-local-tests.xml exit 0 (89 passed/83 PostgreSQL skipped). 신규 71개 시험을 추가했다. 문서·Ontology 검사와 실제 PostgreSQL CI를 이어간다. 공유 Obsidian export에 이전 코어 ADR/진행/인계 기록이 빠진 사본을 발견하여 정본 증거와 외부 새 인계 제안을 함께 보존할 예정이다.
