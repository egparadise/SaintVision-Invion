---
doc_id: "DESIGN-S08-BE-BUILD-REQUEST-ENTRY-001"
title: "S08-BE BuildRequest 제품 진입점 설계"
version: "1.1.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-03T01:32:09+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "53458da3604027e91d428e11db02bc09d279097c"
task_ids: ["S08-BE", "CARD-246"]
tags: ["s08-be", "build-request", "approval", "buildkit", "contract", "design"]
---

# S08-BE BuildRequest 제품 진입점 설계

## 0. 선택 근거와 비주장 경계

카드 241은 승인된 build authority를 0060 admission에 기록하는 internal seam을 만들었다.
그러나 현재 `ApprovalStore.dispatch()` 제품 호출자는 모두 `WorkloadSpec`만 전달하며,
사용자 intent를 서버 소유 `BuildRequest`로 바꾸는 입구가 없다. 이 문서는 raw build
문서를 받지 않는 prepare/enqueue 표면과, 인간 승인 전후 authority를 분리한다.

이 PR은 docs-only다. route, schema, migration, worker를 구현하지 않고 S08-BE 승격이나
운영 BuildKit 인수를 주장하지 않는다. 제품 dispatch flag는 기본 off다.

## 1. 공개 표면: prepare와 enqueue

### 1.1 prepare

`POST /v1/projects/{project}/runs/{run_id}/builds`

- 서명 검증된 사용자와 `Idempotency-Key`가 필수다.
- strict `BuildPreparationInput`은 `checkoutId`, `buildPolicyProfileId`, `expectedRunVersion`,
  `requestedTarget` 네 필드만 받는다. target은 현재 `image` 단일 literal이다.
- caller가 `BuildRequest`, `BuildPlan`, `PolicyDecision`, source SHA, path, provider, lease,
  evidence ID, `approvedBy`를 보내면 `VAL-0003/422`다.
- prepare는 schema, project/source/profile scope, action identity, policy precondition만 검증한다.
  승인 전 `approvedBy=[]`이므로 `authorize_build()`/`enforce_decision()`을 호출하지 않는다.
- 성공은 `201 BuildPreparationView`이며 `buildId`, `runId`, `sourceRunId`, `approvalId`,
  `requestDigest`, `decisionIdentityDigest`, `status=awaiting_approval`, `expiresAt`만 노출한다.
  prepare 응답에 `planDigest`, lease, provider, evidence ID는 없다.

### 1.2 review와 quorum

prepare transaction은 서버가 만든 `BuildRequest`와 pre-approval `PolicyDecision`을 기존
approval snapshot에 같이 고정한다. pre-approval decision의 full digest는 `approvedBy=[]`을
포함하며, `decisionIdentityDigest`는 `approvedBy`를 제외한 불변 필드의 canonical digest다.
0060 `decision_sha256`는 enqueue 시점에 DB vote로 `approvedBy`를 재구성한 승인 후 full
decision digest로 다르다. enqueue는 승인 전/후 decision의 identity digest가 같은지 검증한다.

기존 `ApprovalReviewView.workload`는 하위 호환 union으로 확장한다.

- 기존 `WorkloadSpec` variant는 필드와 의미를 바꾸지 않는다.
- 새 `BuildApprovalReviewSummary` variant는 `kind=build`, target, risk level, profile ID/version,
  source revision, context/dockerfile digest, network/cache mode, secret 사용 여부와 개수만
  포함한다. raw path, secret alias/ID, provider/node/lease는 노출하지 않는다.
- requester는 approver가 될 수 없고 distinct two-person quorum을 유지한다.
- web `ApprovalReviewPanel`은 Gemini 후속 카드로 인계하며 API redaction 계약을 약화하지 않는다.

### 1.3 enqueue

`POST /v1/projects/{project}/runs/{run_id}/builds/{build_id}/enqueue`

- strict body는 `BuildEnqueueInput { approvalId, expectedRunVersion }`이고 `Idempotency-Key`가 필수다.
- flag off이면 approval을 소비하거나 Run을 전이하기 **전** `RES-0006/503/retryable=true`로
  거부한다. preparation은 awaiting_approval에 남고 admission은 0이다.
- flag on이면 requester, project/run/build/approval, `bound_run_version`, current voter grant,
  source/profile/policy를 재검증한다.
- provider 측정은 DB lock 밖에서 candidate로 읽고, 최종 transaction에서 source/profile/
  approval을 다시 잠그고 Run을 scheduled로 전이한 뒤 live lease를 획득한다.
- 그 transaction에서만 DB vote로 approved decision을 재구성하고 `BuildPlan`,
  `buildSessionId`, evidence ID를 처음 생성한다. 그 뒤 `authorize_build()`를 실행하고
  0060 admission을 원자적으로 삽입한다. 외부 BuildKit 호출은 이 transaction에 없다.
- drift나 승인 만료는 approval/preparation을 terminal로, dedicated build Run을 failed로
  전이하고 새 Run을 요구한다.

별도 `/admit`, raw queue route, CLI는 만들지 않고 enqueue는 0059 intent를 직접 만들지
않는다. 0060 admission이 기존 product worker를 통해 0059 intent로 승격된다.

## 2. build Run과 source authority

- path `{run_id}`는 build 전용 planned Run이다. checkout을 소유한 `sourceRunId`는 같은
  tenant/project의 recovering Run이고 requester가 두 Run 모두에 접근 권한을 가져야 한다.
- prepare는 `checkout_id`, editor `revision`, 해당 revision의 snapshot hash, source Run/attempt/
  recovery epoch를 고정한다. 낡은 `workspace_checkouts.content_hash`만을 권위로 쓰지 않는다.
- prepare 후 editor revision이 바뀌면 enqueue는 `VERIFY-0002/422`로 거부한다.
- source capsule materialization은 DB transaction 밖에서 한다. lstat 기준으로 absolute path,
  `..`, symlink/hardlink/device, case collision, context/dockerfile escape를 거부한다. 완성 후
  transaction에서 revision/hash를 다시 검증한다.
- capsule은 tenant/project scoped ObjectStore에 canonical digest로 보관하고, worker는 오직 그
  digest의 bytes를 다운로드한다. retention은 preparation/audit과 같은 최소 35일이다.
- Git SHA가 필요하면 tree bytes, fixed author/committer, fixed timestamp, fixed message, no parent로
  합성한 deterministic commit만 사용한다.

## 3. profile registry와 build PDP

0061에 `inv.build_policy_profiles`를 둔다. 이 테이블은 operator-owned, versioned,
append-only authority이며 `inv_kernel`은 SELECT만 가능하다. public mutation route는 없다.
profile은 tenant/project allowlist, `contextPath`, `dockerfilePath`, target platform/stage, network/cache,
secret alias allowlist, timeout을 소유한다. 이 ID는 `buildPolicyProfileId`이며 provider의
`BuildPlan.builderProfileId`와 다른 의미다.

build PDP는 최소 L2, requester 제외 distinct 2인, `require_approval`, 만료 600초 이하다.
secret을 쓰거나 `networkMode != none`이거나 cache write가 있으면 위험을 낮출 수 없다.
privileged, host socket/access, host bind/device는 profile로 표현할 수 없다. secret alias는
해당 tenant의 서버 저장소에서만 resolve하며 실제 값과 ID를 review/감사에 남기지 않는다.

## 4. idempotency, quota, lock order

- operation은 path를 포함하지 않는 `build.prepare`/`build.enqueue`로 고정한다.
  tenant/project/run/build/approval/subject는 request hash에 포함한다. 다른 path에서 같은 key를
  재사용하면 같은 ledger row에서 `IDEM-0001/409`다. ledger에 TTL이 없으므로 epoch/
  input drift도 409로 남는다.
- quota는 subject prepare 5/min, enqueue 10/min, project prepare+enqueue 30/min, tenant+project
  60/min이다. DB `clock_timestamp()`과 0061 fixed-window counter를 쓴다.
- 인증/project access와 changed-key 검사 후, expensive materialization 전에 별도 짧은
  transaction으로 idempotency reservation과 quota를 commit한다. exact replay는 새 quota를 소비하지
  않고, 이후 prepare가 실패해도 quota는 소비된다.
- DB row lock을 잡은 채 file/Git/ObjectStore/provider I/O를 하지 않는다. 최종 enqueue lock order는
  idempotency -> run -> preparation -> approval/snapshot/votes -> profile -> lease -> 0060 admission이다.

## 5. migration 0061: 예약 확정, column 재설계

coordinator가 0061을 카드 246에 확정 배정했다. `down_revision` 은 0060이고 graph head는
하나여야 한다. 구현은 이 v1.1 승인 전에 시작하지 않는다.

`inv.build_preparations`:

- PK `(tenant_id, project_id, run_id, build_id)`, active partial unique `(tenant_id, run_id)`;
- source run/checkout/revision/snapshot/capsule digests, approval FK, requester, profile ID/version,
  expected/bound run version, request digest, pre-approval decision full/identity digests, `expires_at`;
- approval status는 `approval_requests`에서 파생하고 중복 저장하지 않는다. preparation은
  immutable이고 `queued_at` 한 필드만 NULL -> timestamp set-once를 허용한다.
- raw request/decision JSON, plan, lease, provider, evidence ID를 저장하지 않는다. request/decision 정본은
  approval snapshot이고 0060은 승인 후 plan/decision 정본이다.

`inv.build_policy_profiles`와 `inv.build_preparation_rate_windows`도 같은 migration에 추가한다.
세 테이블은 FORCE RLS tenant exact policy를 사용하고 trigger는 SECURITY INVOKER다.
preparation/profile payload UPDATE와 application DELETE는 거부한다. terminal preparation은 최소 35일
보존하며 v1에 GC carve-out을 두지 않는다. 삭제는 별도 승인된 GC 계약 전까지
NOT_IMPLEMENTED다. nonempty downgrade는 거부한다.

구현 PR은 `tools/write_rls_table_census.py`로 census/ground truth를 재생성하고 migration head
ratchet도 0061로 repin한다. SECURITY DEFINER를 새로 만들지 않는다.

## 6. 오류와 감사

| 조건 | ProblemDetails |
|---|---|
| malformed/unknown/raw build field | `VAL-0003`, 422, non-retryable |
| scope/permission/actor mismatch | `AUTH-0011` 또는 `AUTH-0030`, 403 |
| requester vote/quorum 부족 | `AUTH-0033`, 403 |
| source/profile/decision drift | `VERIFY-0002`, 422 |
| changed idempotency input/path | `IDEM-0001`, 409 |
| stale/terminal Run | `GRAPH-0003`, 409 |
| preparation 존재 비노출 | `RES-0004`, 404 |
| provider/quarantine/worker authority 부재 | `RES-0006`, 503, retryable |
| lock/rate budget 초과 | `RES-0007`, 429 또는 lock 503, retryable |

감사는 preparation requested, approval bound, enqueue requested, admission recorded를 구분하고 ID/
digest만 남긴다. 감사 실패는 해당 business transaction 전체를 rollback한다.

## 7. 수용 시험과 되살림 변이

- contract/generated models와 `ApprovalReviewView` union 하위 호환, build review redaction;
- prepare가 `authorize_build()`를 호출하지 않고 enqueue만 승인 후 decision으로 호출;
- build/source Run project 결속, revision drift, symlink/hardlink/path escape, capsule digest 거부;
- profile tenant/project/version, secret alias scope, PDP 하한, provider freshness, live lease 거부;
- requester vote, duplicate voter, grant 회수, stale approval, approval identity drift 거부;
- fixed operation idempotency: exact replay, body/path/subject drift 409;
- 실패한 prepare도 quota 소비, project/subject/tenant 상한, DB clock;
- concurrent enqueue는 0060 admission/audit 각 1건, 0059 intent 직접 생성 0;
- flag off에서 approval consumption, Run transition, admission, dispatch 모두 0;
- FORCE RLS, immutable payload, queued_at set-once, DELETE/nonempty downgrade 거부, census 0061 repin.

필수 real-PG 성공 경로는 `request -> prepare -> 서로 다른 2인 approve -> enqueue ->
admission 1 -> promote -> claim -> dispatch 1`을 flag-on test fixture로 실행한다. raw path/secret/provider는
evidence/JUnit에 남지 않는다.

되살림 변이는 pre-approval authorize 호출, prepare lease 획득, legacy review union 제거,
source/project/revision 결속 제거, profile scope 제거, quota precommit 제거, operation에 path 포함,
flag-off admission commit, 0059 direct intent 생성을 각각 독립 시험으로 사살한다.

## 8. 구현 순서와 외부 전제

1. strict contract/union/generated models와 0061 migration을 고정한다.
2. source capsule/profile/prepare를 구현한다. BuildKit 호출은 0이다.
3. review redaction과 quorum을 결속하고 Gemini UI 인계를 남긴다.
4. enqueue가 scheduled transition, live lease/plan, 0060 admission을 원자적으로 만든다.
5. hosted real-PG e2e로 성공/경합/rollback을 실측한다.

실제 rootless builder, node mTLS receipt, cleanup/lease release, LAN 인수는 기존 enablement/실장비
카드의 외부 전제다. 이 설계 승인만으로 S08-BE를 승격하지 않는다.
