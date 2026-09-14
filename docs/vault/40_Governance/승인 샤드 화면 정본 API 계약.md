---
doc_id: "CONTRACT-PROJECT-OBSERVATION-001"
title: "승인 샤드 화면 정본 API 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:31:15+09:00"
source_of_truth: "Git"
---

# 승인·샤드 화면 통합 계약

Codex owner, Claude 독립 검토/Gemini 화면 통합 pending. source contracts/v1alpha1/core.schema.json → 생성 Python/TypeScript/Go. 실제 factory inv.app.create_app 및 create_configured_app에 연결한다. demo_server/fixture route coverage는 인수 증거가 아니다.

| 화면 기능 | 정본 경로와 의미 |
|---|---|
| 승인 목록 | GET /v1/projects/{project}/approvals → ApprovalPage(items, nextCursor). limit1..200 기본50, after=ApprovalId, 선택 runId=RunId. status로 숨기지 않고 저장된 모든 상태를 반환. expiresAt 이후 pending을 승인 가능으로 표시하지 않는다. 최종 결정은 challenge/decision 서버 검사가 소유한다. |
| 승인 상세 | GET /v1/projects/{project}/approvals/{approvalId} → 기존 ApprovalView. actionDigest/policyVersion/runVersion/requiredApprovals 보존, nonce·workload·개인키 반환하지 않음. |
| 승인 결정 | 기존 POST …/approvals/{approvalId}/challenge 이후 …/decision. 일회nonce와 actionDigest·decision·Idempotency-Key, 현재subject권한 필요. 화면의 단순 /approve 호출로 대체하지 않음. |
| 샤드 관측 | GET /v1/projects/{project}/runs/{parentRunId}/shards → ShardObservation. items가 아니라 shards 배열. plan/lineage/부모상태/실제증거/집계manifest 포함. 부모가 아닌Run/다른project/tenant는404 또는 권한403. |
| 전체 샤드 취소 | **기존 POST /v1/projects/{project}/runs/{parentRunId}/cancel**. body expectedVersion은 직전 부모Run GET의 version, Idempotency-Key 필수. 별도 cancel-all 성공 응답을 모사하지 않는다. 실제 ShardRuntime.cancel의 원자자식취소·멱등ledger·현재권한 재검사를 사용한다. |
| 자원 회수 | 브라우저 수동 /reclaim-resources 없음. 위 cancel 후 resourceReleasePending=true이면 실제 Node 정지receipt 기반 자동회수 대기. UI는 상태 새로고침을 제공할 수 있으나 회수 완료로 먼저 바꾸지 않는다. |

## 화면 상태와 보안 경계

ApprovalView approvalId/runId/projectId와 기존 UI의 id 등은 Gemini가 명시적으로 매핑한다. 비어 있는 승인목록은0개이며 데모 안건으로 채우지 않는다. 401=인증필요,403=현재project권한없음,404=해당scope에서대상없음,422=입력오류,503=재시도가능잠금/epoch문제 등 서버문제코드를 유지한다.

샤드의 allPhysicallyStopped와 allSucceeded는 별개다. 취소상태만으로 물리정지를 확정하지 않는다. 불완전plan은 실제 shardCount와 빈/부족한 shards를 함께 표시하며 성공으로 합성하지 않는다. resultManifest=null은 검증된 전체출력manifest가 준비되지 않은 상태다. 관측 응답은 실행권한·새로운 승인·Node활성화 근거가 아니다.

project grant와 업무project/user/member 현재권한을 읽기 트랜잭션 안에서 검사한다. tenant RLS와project조건을 모두 적용한다. 브라우저 권한으로 enqueue/프로필교체/epoch무시/리소스강제반납을 허용하지 않는다. 저장소이름이나 payload에 synthetic fixture가 들어간 검증은 실제 원격실행 인수와 구분한다.

## 다음 담당

Gemini는 최신 integration에서 flat승인목록·shards/cancel-all·reclaim 호출을 위계약으로 연결하고, generated타입을 사용해 응답을 대조한다. 임의data fallback을 제거한 configured factory에 브라우저를 붙여 실제401/403/취소후pending을 확인한다. Claude는 권한·schema·라우트 독립검토. Codex는 실제원격profile/7개실행·CI/운영OIDC 의존을 이어서 확인한다.
