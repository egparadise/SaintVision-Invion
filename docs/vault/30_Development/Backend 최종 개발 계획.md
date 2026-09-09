---
doc_id: "PLAN-BACKEND-001"
title: "Backend 최종 개발 계획"
version: "1.0.0"
status: "baseline"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Backend 최종 개발 계획

책임: **Claude; 핵심 Codex**. 공통 기준은 [[최종 개발 계획 - 모든 개발의 지침]], 주차별 작업은 [[24주 통합 실행 계획]]을 따른다.


## 구조

Python FastAPI·Pydantic·SQLAlchemy의 모듈러 모놀리스다. identity/project/resource/scheduling/execution/policy/context/tooling/storage/audit의 경계를 유지한다. Go Node Agent, TypeScript Agent Gateway, Python ML worker는 별도 프로세스다. 버전은 S01 호환성 검증 후 lock한다.

Claude는 업무 API·Context·Adapter·CLI·관찰성과 운영 문서를 맡는다. Codex는 Scheduler·RunGraph·권한·fencing·복구 경계를 맡는다. 외부 Provider는 공통 probe/install/authenticate/run/cancel/collect/redact/attest 계약으로 연결한다.

## 공개 인터페이스

JSON Schema가 단일 원본이며 Pydantic/TS/Go 생성물을 수동 수정하지 않는다. 생성기가 입력 유효성까지 보장한다고 가정하지 않고 각 경계에서 validator를 실행한다. API는 `/v1` REST, SSE `/v1/runs/{id}/events`, WS `/v1/workspaces/{id}/terminals/{sid}`다. `/cancel`, `/decision`, `/heartbeats` 서브리소스로 통일한다.

입력 IntentSpec → WorkloadSpec으로 변환하고 Agent 작업만 AgentRunSpec의 도구·예산 제약을 추가한다. AgentRunSpec은 일반 GPU Workload 모두에 필수인 대체 스키마가 아니다. ContextBundle·RunRecord·RunAttempt·EvidenceEnvelope 계약을 명시한다.

오류는 RFC 9457 형태에 code/category/retryable/traceId/causeRef/evidenceId를 추가한다. 내부 message는 HTTP detail로 매핑한다. cursor pagination 기본 limit 50, 최대 200; tenant/project 권한을 먼저 검사한다. 중요 mutation은 durable idempotency ledger와 request hash를 사용한다.

## 실행·안전

OPA fail-closed, Node mTLS, scope 제한 Agent token, 승인 내용 digest 검증. 모든 실행은 Tool Gateway와 Sandbox를 거친다. unrestricted shell 문자열 분류만으로 안전하다고 보지 않는다. Node 단절 시 새 작업 금지, 기존 작업은 lease 만료·local policy에 따라 정리한다.

Scheduler: hard filter → policy 조정 → deterministic score → transactional lease → Node 재검증 → explain. minmax의 분모 0은 해당 항목 0, 미측정 필수 자원은 후보 제외, 동점은 nodeId 정렬이다. 가중치·snapshot·policy 버전을 기록하고 모델은 직접 바꾸지 않는다.

RunGraph는 상태·checkpoint·outbox를 함께 저장한다. 재전달은 정상 시나리오이며 consumer 중복 제거가 필수다. 실패 재시도 2회 기본, 총 시간·비용 내에서만 복구한다. 외부 부수 효과 확인 불가 시 자동 재시도하지 않는다.

## 관찰·검증

application redaction → Alloy/OTel → Prometheus/Grafana, Loki, Tempo. runId/stepId/evidenceId는 업무 연결 키이며 traceId/spanId와 구별한다. 계약·권한·중복 요청·취소·재시작·Node 분할·outbox 발행 후 crash를 시험한다. 정책 P95 200ms, API 읽기 P95 300ms, 이벤트 P95 5초를 5노드·동시 10 Run에서 측정한다.
