---
doc_id: "DESIGN-S08-BE-BUILD-REQUEST-ENTRY-001"
title: "S08-BE BuildRequest 제품 진입점 설계"
version: "1.0.1"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T01:16:21+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "53458da3604027e91d428e11db02bc09d279097c"
task_ids: ["S08-BE", "CARD-246"]
tags: ["s08-be", "build-request", "approval", "buildkit", "contract", "design"]
---

# S08-BE BuildRequest 제품 진입점 설계

## 0. 선택 근거와 비주장 경계

카드 241의 승인 후보는 승인된 build 문서를 0060 admission에 기록하는 내부 seam을 만든다.
그러나 현재 제품의 `ApprovalStore.dispatch()` 호출자 세 곳
(`workspace_api.py:307`, `workspace_start.py:303`, `shard_recovery.py:314`)은 모두 기존
`WorkloadSpec`만 전달하며 build plan/evidence를 전달하지 않는다. 정본 `BuildRequest`와
`BuildPlan` 계약은 존재하지만(`generated/models.py:246`, `:276`), 사용자가 build 문서를
직접 넣는 route는 없다. 따라서 다음 공백은 transport가 아니라 **사용자 intent를 서버 소유
build authority로 바꾸고 승인에 올리는 제품 입구**다.

이 문서는 그 입구의 공개 계약과 저장 경계를 결정한다. route, schema, migration, worker를
구현하지 않으며 S08-BE 점수 상승이나 운영 BuildKit 인수를 주장하지 않는다. 구현은 카드 241
최종 승인 head를 포함한 별도 카드에서 수행한다. 제품 dispatch flag는 계속 기본 off다.

## 1. 결정: prepare + enqueue의 두 단계 route

### 1.1 prepare

`POST /v1/projects/{project}/runs/{run_id}/builds`

- 인증된 사용자와 `Idempotency-Key`가 필수다.
- strict request `BuildPreparationInput`은 다음 네 필드만 허용한다.
  `checkoutId`, `buildProfileId`, `expectedRunVersion`, `requestedTarget`.
- `requestedTarget`은 `image` 단일 literal이다. 향후 target 추가는 계약 version 변경이다.
- caller가 `BuildRequest`, `BuildPlan`, `PolicyDecision`, source SHA, context/dockerfile path,
  network/cache/secret policy, builder/node/lease, evidence ID, `approvedBy`를 보내면
  `VAL-0003/422`다. unknown field도 같은 오류다.
- 성공은 `201 BuildPreparationView`다. 공개 응답은 `buildId`, `runId`, `approvalId`,
  `requestDigest`, `planDigest`, `policyDecisionId`, `status=awaiting_approval`, `expiresAt`만
  포함한다. raw plan, secret ref, provider topology는 반환하지 않는다.

### 1.2 review와 quorum

prepare transaction은 서버가 만든 immutable build authority의 digest와 같은 action digest로
기존 approval request를 만든다. 두 번째 운영자는 기존
`GET /v1/projects/{project}/approvals/{approval_id}/review`(`app.py:643`)에서 위험 수준과
서버가 만든 redacted build 요약을 읽고, 기존 challenge/decision route(`app.py:660`, `:674`)로
투표한다.

- requester는 approver가 될 수 없다.
- `PolicyDecision.requiredApprovals`를 그대로 적용하며 L3는 계속 거부한다.
- quorum을 줄이거나 승인 snapshot을 건너뛰는 build 전용 예외는 없다.
- review snapshot에는 raw secret ID 배열 대신 secret 사용 여부와 개수만 보인다.
- 승인 만료, run version 변화, source/profile/policy drift는 enqueue 전에 다시 검증한다.

### 1.3 enqueue

`POST /v1/projects/{project}/runs/{run_id}/builds/{build_id}/enqueue`

- strict body는 `BuildEnqueueInput { approvalId, expectedRunVersion }`이고
  `Idempotency-Key`가 필수다.
- requester 본인, `can_request`, exact project/run/build/approval binding, distinct approval
  quorum을 다시 검사한다.
- 서버 저장소에서 frozen `BuildRequest`, `BuildPlan`, `PolicyDecision`, policy version,
  evidence ID를 읽어 카드 241의 trusted admission seam에 전달한다. caller가 어느 문서도
  합성하지 않는다.
- 성공은 `202 BuildPreparationView`의 `status=queued`다. 같은 key와 같은 body는 exact
  replay, 같은 key와 다른 body 또는 다른 path identity는 `IDEM-0001/409`다.
- flag off, provider observation 부재/노후, lease drift, quarantine channel 부재는 admission을
  우회하지 않는다. dispatch는 0이며 정본 `RES-0006/503/retryable=true`를 유지한다.

별도 공개 `/admit`, raw queue route, CLI는 만들지 않는다. 실제 transport는 기존 worker가
0060 admission을 0059 intent로 승격한 뒤에만 접근한다
(`build_product_runtime.py:85`, `:165`).

## 2. 서버 소유 compilation

prepare는 다음 순서로 짧은 DB transaction 안에서 authority를 잠그고, 외부 BuildKit 호출은
하지 않는다.

1. authenticated tenant와 path project/run을 검증하고 `can_request`를 재확인한다.
2. current Run과 `expectedRunVersion`, current workspace checkout을 잠근다.
   checkout은 tenant/run/source attempt/recovery epoch와 결속돼 있고
   `workspace_checkouts`에는 content hash가 있다
   (`services/control-plane/src/inv/migrations/0017_workspace_checkouts.sql:2`).
3. `buildProfileId`를 운영자 소유, versioned profile registry에서 resolve한다. profile이
   `contextPath`, `dockerfilePath`, target platform/stage, network/cache policy, 허용 secret
   aliases, timeout을 소유한다. registry가 비거나 profile이 없으면 fail closed다.
4. source adapter가 checkout의 immutable snapshot을 private Git checkout으로 materialize한 뒤
   commit/tree SHA를 관측한다. 사용자 문자열이나 remote branch head를 SHA authority로 쓰지
   않는다. dirty checkout, SHA/content-hash 불일치는 `VERIFY-0002/422`다.
5. 측정된 provider health, live resource lease, current recovery epoch, containment, project
   budget을 읽는다. provider가 없거나 15초 freshness를 넘으면 문서를 만들지 않는다.
6. 서버가 strict `BuildRequest`를 구성하고 `canonical_build_action()`
   (`build_governance.py:46`)으로 policy를 조회한다. policy result와 live authority로
   `BuildPlan`을 구성하며 `buildSessionId`와 evidence ID도 서버가 발급한다.
7. `authorize_build()`(`build_governance.py:139`)과 JSON Schema validation을 통과한 세 문서,
   canonical digest, profile version, checkout content hash, run version을 한 frozen row와
   approval snapshot으로 원자적으로 저장한다.

enqueue는 같은 lock order로 current Run → frozen preparation → approval → live lease/provider를
재검증한다. prepare 때의 plan을 무조건 신뢰하지 않고, 변하는 authority(provider observation,
lease expiry, containment)는 새 값과 exact binding이 다르면 fail closed다. plan을 조용히
재작성하지 않으며 사용자는 새 preparation을 요청해야 한다.

## 3. 권한, 감사, idempotency, rate limit

| 경계 | 결정 |
|---|---|
| 인증/tenant | 서명 검증된 principal만 사용하고 tenant는 token에서만 온다. path/body가 다른 tenant를 고를 수 없다. |
| project | prepare/enqueue 모두 live `require_project_access`와 `can_request`; review/decision은 기존 `can_approve`. 존재 비노출 정책을 유지한다. |
| 승인자 | requester와 다른 활성 사용자, 기존 challenge nonce, current quorum. `approvedBy`는 DB votes에서만 재구성한다. |
| idempotency | operation은 path identity를 포함한 `build.prepare:{project}:{run}` / `build.enqueue:{project}:{run}:{build}`. replay 전에도 인증·권한을 다시 검사한다. |
| 동시성 | run마다 nonterminal build preparation 하나. 두 prepare/enqueue가 경합하면 row lock+unique constraint로 한 건만 전이하고 패자는 exact replay 또는 `IDEM-0001`이다. |
| rate limit | tenant+project+subject 기준 prepare 5회/분, enqueue 10회/분. DB-backed fixed window이고 재시작으로 초기화하지 않는다. 초과는 `RES-0007/429/retryable=true`; idempotent replay는 새 quota를 소비하지 않는다. |
| 감사 | `inv.build.preparation_requested`, `inv.build.approval_bound`, `inv.build.enqueue_requested`, 카드 241의 `inv.build.admission_recorded`. ID와 digest만 기록하고 plan, paths, secret aliases, token은 기록하지 않는다. |

감사 쓰기 실패는 business transaction 전체를 rollback한다. 권한·quorum·rate-limit 거부에는
정본 denial 경계를 사용하되 raw 불일치 값은 ProblemDetails, 감사, 로그에 싣지 않는다.

## 4. migration 결정: 0061 필요

0060 `inv.build_execution_admissions`는 승인과 dispatch가 끝난 뒤의 immutable authority이며
(`migrations/versions/0060_build_execution_admissions.py:24`), prepare와 review 사이 authority를
보관할 수 없다. 기존 approval snapshot도 `WorkloadSpec`/policy 중심이고 BuildPlan, profile
version, checkout/content binding을 소유하지 않는다. coordinator는 0061을 **조건부 예약**했다.
Claude가 이 설계에서 table 필요성을 승인하면 확정하며, 승인 전 migration 파일을 만들지 않는다.
확정 시 `down_revision`은 0060이고 migration graph는 단일 head여야 한다.

제안 table `inv.build_preparations`:

- PK `(tenant_id, project_id, run_id, build_id)`, active partial unique `(tenant_id, run_id)`;
- FK run/checkout/approval, requester ID, profile ID+version, expected/current run version;
- strict request/plan/decision JSONB와 각 canonical SHA-256, checkout content hash,
  evidence ID, status(`awaiting_approval|approved|queued|rejected|expired`);
- FORCE RLS, tenant exact policy, `inv_kernel` 최소 column grant;
- payload/identity immutable trigger, 허용된 status 전이만 update, DELETE 금지;
- `expires_at`은 approval/policy/lease 중 가장 이른 시각 이하이고 최대 1시간이다. 만료 row는
  dispatch할 수 없고 `expired` terminal 전이와 감사만 허용한다;
- terminal row는 감사·재현을 위해 35일 보존한 뒤 별도 운영 GC가 digest receipt를 남기고
  삭제한다. migration downgrade는 row가 한 건이라도 있으면 거부한다.

승인 snapshot과 preparation은 같은 transaction에서 만들어지며 approval ID와 action digest가
양방향 exact match해야 한다. 구현 PR은 `tools/write_rls_table_census.py`로 RLS census와 ground
truth를 재생성하며 손으로 편집하지 않는다. trigger가 새 SECURITY DEFINER를 요구한다면 #333
allowlist/definer policy에 넣기 전에 별도 보안 검토 근거와 pin 회전을 제공한다. 가능하면
SECURITY INVOKER trigger를 사용한다.

## 5. 오류와 공개 계약

| 조건 | ProblemDetails |
|---|---|
| malformed/unknown/raw build field | `VAL-0003`, 422, non-retryable |
| scope/permission/actor mismatch | 기존 `AUTH-0011` 또는 `AUTH-0030`, 403 |
| requester가 승인하거나 quorum 불충분 | 기존 `AUTH-0033`, 403 |
| source/profile/plan/decision binding drift | `VERIFY-0002`, 422 |
| changed idempotency input/path | `IDEM-0001`, 409 |
| stale run/terminal state/version | `GRAPH-0003`, 409 |
| build/preparation 존재 비노출 | `RES-0004`, 404 |
| provider/quarantine/worker authority unavailable | `RES-0006`, 503, retryable |
| lock/rate budget 초과 | `RES-0007`, 429 또는 기존 lock 경계의 503, retryable |

구현 계약 PR은 `BuildPreparationInput`, `BuildEnqueueInput`, `BuildPreparationView`를
`contracts/v1alpha1/core.schema.json`에 strict `additionalProperties:false`로 추가하고 Python,
TypeScript, Go 생성물을 함께 갱신한다. 기존 BuildRequest/BuildPlan의 공개 의미는 바꾸지 않는다.

## 6. 구현 순서와 수용 시험

1. 계약 schema/생성물과 0061 migration/권한/trigger를 한 PR에서 먼저 고정한다.
2. compiler service와 prepare route를 구현한다. 실제 BuildKit 호출은 없어야 한다.
3. review redaction과 기존 quorum 결속을 구현한다.
4. enqueue route가 카드 241 trusted seam을 호출하도록 연결한다. flag 기본 off를 유지한다.
5. worker/transport 실측은 그 다음 enablement 카드에서만 수행한다.

필수 PG-free/실-PG 부정 시험:

- raw BuildRequest/BuildPlan 및 unknown field, forged tenant/project/run/requester/approvedBy 거부;
- caller source SHA/context/network/secret/provider/lease 입력 거부, server-derived 값 exact match;
- missing/unknown/changed profile, dirty source, checkout content/SHA drift 거부;
- request/plan/decision/action digest 하나씩 변조, expired policy/lease/provider 거부;
- requester vote, 같은 사람 중복 vote, quorum 부족, stale approval/run version 거부;
- same key same body exact replay, changed body/path key reuse 거부;
- 두 connection prepare/enqueue 경합에서 preparation/admission/audit 각 정확히 1행;
- rate window 경계와 replay 비소비, clock rollback에도 우회 불가;
- audit 실패, admission 실패, 0060 insert 실패에서 approval/preparation/status 전체 rollback;
- flag off에서 admission까지 저장돼도 external dispatch 0, public `/admit` route 0;
- tenant A가 tenant B preparation을 GET/enqueue/list할 수 없고 존재를 드러내지 않음;
- migration upgrade/downgrade, FORCE RLS, column grant, immutable payload, nonempty downgrade 거부.

되살림 변이는 `additionalProperties`, profile ownership, source SHA 재관측, `approvedBy` DB 재구성,
quorum, unique active row, action digest, audit rollback, flag-off, public-admit-route 금지를 각각
한 줄씩 제거해도 해당 단독 시험이 실패해야 한다.

## 7. 외부 전제와 판정

route/DB/compiler/quorum은 hosted PostgreSQL에서 MEASURED 가능하다. 실제 rootless builder 왕복,
node mTLS receipt, cleanup, lease release와 물리 LAN 인수는 이 카드의 통과 조건이 아니며 기존
enablement/실장비 카드에 남는다. 설계 승인만으로 S08-BE를 승격하지 않는다.
