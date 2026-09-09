---
doc_id: "APPROVAL-CONTRACT-001"
title: "Codex 승인 경계 계약과 인계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T22:58:56+09:00"
source_of_truth: "Git"
---

# Codex 승인 경계 계약과 인계

Task approval-boundary / owner Codex / reviewer Claude(pending). OUT-04/AC-04의 승인 소비 계약을 S04-BE/DB 통합 전에 검증하는 준비 작업이다. S01~S03 선행 미완료 상태와 48개 baseline Task의 상태를 승격하지 않는다. 시작 기준·scope는 [[2026-09-09_22-25-39_KST_APPROVAL-BOUNDARY_Codex_개발과정]]을 따른다.

## ADR-024 승인 내용 고정 및 원자 소비

서버의 신뢰된 인증 adapter가 검증한 tenant/subject를 `Principal`로 만들고, 신뢰된 PDP가 생성한 PolicyDecision과 policy version을 입력한다. 브라우저의 actor·approvedBy·policy JSON을 그대로 전달해서는 안 된다. 이 모듈에는 공개 HTTP mutation이나 실제 명령 실행기가 없다. 사용자께서 개발 작업의 일반 승인을 미리 주신 것은 이 제품의 사용자 승인 정책을 낮추는 설정으로 사용하지 않는다.

| 계약 | 서버 동작 |
|---|---|
| 요청 | 현재 planned Run/version, project can_request, PolicyDecision scope/subject/digest 확인. require_approval만 수용; 외부 approvedBy 거부; L2는 2인, L3는 차단 |
| 불변 범위 | tenant/project/Run/requester/actionDigest/policy decision·version/recovery epoch/Run version/승인 수/만료 고정. 변경하려면 새 Run·승인을 생성 |
| 만료 | 서버 DB clock 기준 승인 유효 기간 최대 1시간, actor별 challenge 최대 30초. 이 값은 이번 계약의 설계 상한이며 운영 설정 완료를 뜻하지 않음 |
| challenge | 요청자 자기 승인 금지, can_approve 재검사. 256bit 난수 원문은 응답에만 포함; DB는 SHA-256만 저장. 재발급은 같은 actor의 이전 challenge를 무효화 |
| 결정 | actor/nonce/digest/현재 Run/expiry/epoch 검증 후 nonce 소비·유일한 actor vote·audit·outbox·멱등 응답을 동일 txn에 저장. 같은 사람이 두 표를 채울 수 없음 |
| dispatch | 현재 requester와 모든 승인자의 project 권한 재검사. 유효 quorum에 한해 commandId 1개, dispatch 행, audit, inv.command.authorized outbox, Run scheduled 전이를 하나의 txn에 저장 |
| 멱등 재시도 | 동일 tenant/project/operation/key와 subject/epoch/content는 이전 응답. 같은 key의 변경 내용은 IDEM-0001. 새로운 key로 소비된 nonce 또는 dispatch를 재실행할 수 없음 |
| 거절·만료 | 승인 rejected/expired와 Run failed를 동일 txn으로 반영. 취소·버전 변경·복원 epoch 불일치 후 새로운 dispatch 차단 |
| 직접 전이 | awaiting_approval → scheduled는 DB trigger가 유효한 durable dispatch를 요구. planned → scheduled의 기존 내부 저위험 경로에는 이번 계약이 정책 분류를 추가하지 않음 |

`inv.command.authorized`는 실행 요청의 durable 등록이다. 메시지 발행은 at-least-once이므로 후속 consumer는 commandId inbox로 중복을 제거하고, 실제 실행 직전에 내용 digest·expiry·현재 epoch·정책·Node allocation fence를 검증해야 한다. 본 코드가 장비의 부수 효과를 exactly-once로 만들었다고 주장하지 않는다. 개인정보/비밀을 포함할 수 있는 원문 command·nonce는 audit/outbox/idempotency payload에 저장하지 않는다.

## DB·동시성 및 배포 인계

migration 0002는 0001 뒤에 적용한다. approval_requests/nonces/votes/dispatches/audit와 project_grants에 tenant RLS USING/WITH CHECK, 소유 관계 FK를 둔다. 요청 scope와 audit/vote/dispatch는 불변이다. 파괴적인 downgrade는 지원하지 않는다.

잠금 순서는 idempotency → Run → Approval → subject 정렬 project grant → nonce다. 권한 projection writer는 subject 정렬 grant만 잠그고 Run을 역으로 잠그지 않는다. dispatch가 먼저 grant 공유 잠금을 획득하면 그 txn은 권한 철회보다 먼저 처리된 것으로 본다. 철회가 먼저 commit되면 dispatch가 거부된다. 이후 실행 직전 권한·정책 재검사는 실제 consumer의 별도 책임이다.

Runtime role은 non-superuser/non-owner/NOBYPASSRLS이며 신원 projection을 변경하지 못해야 한다. 일반 테이블 일괄 GRANT 뒤에도 반드시 아래 제한을 적용한다. 실제 운영 role 생성/권한 변경은 이번에 실행하지 않았다. CI fixture가 동일 권한을 검증한다.

```sql
-- inv_runtime은 후속 설치 시 정하는 role 이름의 예시다.
REVOKE INSERT, UPDATE, DELETE ON inv.project_grants FROM inv_runtime;
GRANT SELECT, UPDATE(lock_sentinel) ON inv.project_grants TO inv_runtime;
REVOKE UPDATE, DELETE ON inv.approval_votes, inv.approval_dispatches,
  inv.approval_audit FROM inv_runtime;
```

lock_sentinel은 CHECK(true)인 고정 컬럼으로 SELECT FOR SHARE에 필요한 잠금 권한만 제공한다. can_request/can_approve/enabled 변경 권한은 별도 신뢰된 identity projection writer에 둔다. RLS tenant 설정과 Principal은 서비스 내부 신뢰 경계이며 임의 SQL 접근이나 브라우저 claim 자체를 인증으로 취급하지 않는다.

## 생성 계약 및 검증

원본은 `contracts/v1alpha1/core.schema.json`. ApprovalChallenge, ApprovalDecisionInput, ApprovalView, AuthorizedCommand를 추가하고 Python/TypeScript/Go를 생성한다. input은 additionalProperties=false여서 subjectId/approvedBy 삽입을 거부한다. raw nonce를 요청 key·URL·로그·분석 이벤트에 넣지 않는다.

검증은 JSON Schema/Principal 입력 거부 10개, PostgreSQL 승인·scope·권한·nonce·두 actor/8개 재시도 동시성·취소·epoch·expiry·audit 실패 rollback 25개와 기존 66개 회귀다. 로컬은 63 passed/38 PostgreSQL skipped이며 실제 CI 결과는 검증 보고에 기록한다. 실제 OIDC/브라우저/Node 또는 장비 명령 시험은 아직 하지 않았다.

## 다음 담당자

- Claude: 독립 코드 검토, 신뢰된 인증/PDP adapter·project grant projection·API 오류 매핑 연결. 기존 FR-04의 승인 소비 미구현 부분은 이 내부 계약으로 보완되며 공개 API는 별도 작업이다.
- Gemini: 생성 타입을 사용하되 actor/approvedBy를 브라우저 요청 본문에 넣지 않음. 승인 표시와 버튼 비활성화는 서버 결정을 대체하지 않음. nonce는 메모리에서만 1회 사용하고 재접속 시 새 challenge 요청.
- Codex: 리뷰 지적 반영, S03 ToolGateway/Sandbox와 실제 dispatch 소비자의 정책 재검사·command inbox·Node fence 결합. S01 환경 근거 없이 S04 전체를 완료 처리하지 않음.

제품 Prompt/Context/Harness/ROOF/Graph 배포 버전은 미연동이다. 테스트 policy_version `roof:test:1`은 합성 fixture이며 운영 ROOF 버전이나 사람의 실제 승인이 아니다.

실제 CI 확인: [[2026-09-09_23-03-51_KST_APPROVAL-BOUNDARY_Codex_검증보고]]. PostgreSQL 포함 101개 시험 통과이며 독립 검토는 pending이다.
