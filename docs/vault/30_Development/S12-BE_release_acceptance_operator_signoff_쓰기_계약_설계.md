---
doc_id: "DESIGN-S12-BE-RELEASE-ACCEPTANCE-WRITE-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 보안 계약 설계"
version: "1.2.1"
status: "proposed"
author: "Codex"
reviewer: "Claude"
audience: "agent"
updated: "2026-10-01T19:55:28+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3ff89b84"
task_ids: ["S12-BE", "S12-FE"]
tags: ["s12", "release-manifest", "acceptance", "operator-sign-off", "security", "contract", "codex"]
---

# S12-BE release 수락·operator sign-off 쓰기 보안 계약

## 0. 결정

[[S12-BE_release_manifest_읽기_route_설계_메모]]가 요청한 쓰기 경계를 다음처럼
고정한다.

1. **모든 결정은 신선한 대화형 인증을 마친 활성 사람**만 쓸 수 있다. 요청 본문은
   `acceptedByUserId`, bearer token, 재인증 증거를 받지 않는다. 서버가 검증된 OIDC
   subject에서 `public.users`의 활성 사용자를 다시 도출한다.
2. `accepted`만 **서로 다른 두 사람**이 같은 proposal digest를 확인해야 그 decision의
   `decisionSignOff=true`가 된다. release 전체의 `operatorSignOff`는 그 뒤 §5의
   required criterion 전부를 집계한 읽기 projection만 계산한다. `conditional`과 `rejected`는
   한 사람의 최종 기록이지만 sign-off에 세지 않는다.
3. 클라이언트는 승인하려는 `targetManifestSha256`을 보낸다. 서버는 잠근 manifest에서
   digest를 다시 읽어 일치할 때만 그 서버 값을 기록한다. caller 값은 저장값의 정본이
   아니다.
4. target과 measurement는 strict reference 목록으로 분리한다. **목표 선언은 관측이
   아니며**, opaque hash를 보내는 것만으로 측정 증거가 되지 않는다.
5. proposal·투표·최종 기록·철회·무효화 사건은 append-only다. 활성 상태는 별도 coordination
   slot projection에서 계산하며 과거 결정을 수정하거나 삭제하지 않는다.

이 PR은 설계와 공개 JSON Schema만 낸다. route, 서비스, DB migration, OIDC claim 보존,
감사 기록 구현은 Claude의 다음 카드다. 구현 전까지 기존 읽기 route는 계속 read-only이고
`operatorSignOff`를 새로 true로 만들 수 없다. 코디네이터의 2026-10-01 N2 최종 결정에 따라
release 범위 `confirmedOperatorCount`는 현재 manifest와 required criterion 전부에 대해
**fresh interactive human attestation이 검증된 서로 다른 운영자 수**이고, service/system/
client-credentials 주체는 세지 않는다. `operatorSignOff`는 비어 있지 않은 policy registry의
모든 required criterion이 유효한 `decisionSignOff=true`일 때만 true다. 이 정의의 owner는
#282다. #280은 구현 전 `confirmedOperatorCount=0`,
`operatorSignOff=false`, `operatorSignOffBlockedBy=human-attestation-implementation-unavailable`
로 내고, legacy accepted 행과 manifest hash만 맞는 raw 사용자 수는 별도
`matchingAcceptedUserCount`로 표시해야 한다. 이 release 집계는 proposal 투표 수가 아니며
#282의 `proposalConfirmationCount`·`decisionConfirmationCount`·`decisionSignOff`와 이름과
범위를 분리한다. 구현 카드는 아래 attestation·
quorum·withdrawal projection이 한 transaction 경계로 모두 착지한 뒤에만 blocker literal을
제거하고 true variant를 공개한다.

## 1. 현재 코드 경계와 필요한 변경

| 현재 정본 | 확인한 사실 | 구현 카드가 해야 할 일 |
|---|---|---|
| `src/saintvision/db/models/operations_pilot.py` | `acceptance_records.accepted_by_user_id`는 실제 user FK이나 release×criterion unique라 재결정·철회·2인 투표를 표현하지 못한다 | proposal·operator vote·withdrawal을 append-only로 표현하고 active criterion을 원자적으로 하나만 유지한다 |
| `src/saintvision/services/pilot.py` | `record_acceptance()`가 manifest digest를 server-side로 읽는 좋은 경계를 이미 갖는다 | manifest row lock과 final recheck를 추가하고 caller digest를 optimistic concurrency target으로만 쓴다 |
| `src/saintvision/identity/oidc.py` | verified subject를 활성 user로 매핑하지만 `Principal`에는 `auth_time`·`amr`·`acr`가 없다 | 검증된 identity의 fresh-auth metadata를 내부 principal/context에 보존한다. raw token은 저장하지 않는다 |
| `src/saintvision/services/settings.py` | tenant 전역 권한은 `business_admin_allowed`로 매 요청 DB에서 확인한다 | coordinator가 배정한 migration에서 `releases.accept` 권한을 추가하고 create·confirm·withdraw 때 각각 live 재확인한다 |
| `src/saintvision/api/deps.py` | durable idempotency ledger와 advisory lock이 있다 | tenant-wide endpoint이므로 `project_id=NULL`을 쓰되 endpoint 상수뿐 아니라 `releaseId`와 `proposalId` 또는 `acceptanceId`를 canonical payload에 포함한다 |
| `src/saintvision/services/audit.py` | 요청 transaction 감사와 rollback 밖 denial 감사를 나눈다 | 성공·거절을 §8의 닫힌 action/payload로 기록한다 |
| `deploy/intranet/idp-realm.sh`·portal OIDC | audience/client mapper만 있고 `auth_time`·`amr` 결속과 step-up 흐름이 없다 | Keycloak access token mapper와 portal `prompt=login&max_age=300` step-up을 먼저 구현한다. 그 전에는 write route를 enable하지 않는다 |

현재 `Principal`이 fresh-auth claim을 버리므로 구현자가 token을 다시 decode하거나 body에서
재인증 문자열을 받으면 안 된다. `inv.identity.AccessTokens`가 검증한 claim만 다음 내부
context로 전달한다.

## 2. 사람·권한·재인증

### 2-1. 사람만 가능

다음 조건을 **모두** 충족해야 한다.

- access token은 기존 verifier가 issuer·audience·client ID·서명·`typ=at+jwt`·수명을
  검증한다.
- subject는 같은 tenant의 `public.users` 활성 행 하나로 매핑된다. user ID는 서버가
  도출하며 body·path에서 받지 않는다.
- 검증된 token에 `auth_time`이 있고 요청 시각보다 **300초 이내**다.
- 검증된 `amr`는 RFC 8176 값만 받는다. `mfa`가 있거나, `pwd`와 `otp|hwk|swk` 중 하나가
  함께 있어야 한다. `pwd` 단독과 비등록 문자열 `webauthn`은 허용하지 않는다. claim 부재·
  형식 오류·미래 시각은 fail closed다. `exp-iat<=3600`은 token 수명일 뿐 재인증 증거를
  대신하지 않는다.
- client-credentials·system·service identity는 user 행을 가리키더라도 위 interactive
  조건을 충족하지 못하므로 거부한다.
- vote에는 raw token/subject 대신 `human_attestation_version`, verified issuer/client identity,
  `auth_time`, 정규화된 AMR 집합의 digest와 identity verification event ID를 immutable하게
  남긴다. 단순 `accepted_by_user_id` FK나 distinct user count는 사람 attestation이 아니며
  legacy accepted 행에서 센 `matchingAcceptedUserCount`는 관측값일 뿐 sign-off 근거가 아니다.
  attestation 구현 전 release 범위 `confirmedOperatorCount`는 0이다.

인증 부재·무효는 `AUTH-0050/401`; 유효하지만 fresh interactive proof가 없거나 권한이
없으면 `AUTH-0030/403`이다. 오류에는 subject, user ID, claim 값, token을 넣지 않는다.

### 2-2. tenant 전역 권한

- 새 live permission은 `releases.accept` 하나다. project role·token role·UI role은 이를
  대신하지 못한다.
- create·confirm·withdraw 각각 `public.business_admin_allowed(tenant,user,'releases.accept')`
  를 DB에서 다시 확인한다. 캐시와 login 시점 role snapshot은 권한 근거가 아니다.
- `accepted` proposer와 confirmer는 서로 다른 active `user_id`여야 한다. one-to-one인
  external subject도 같아서는 안 된다. 동일인은 `AUTH-0033/403`이다.
- `conditional`·`rejected`는 sign-off를 만들지 않으므로 한 사람으로 최종 기록한다.
  accepted proposal의 `expiresAt`은 proposer의 검증된 `auth_time + 300초`와 token `exp`
  중 이른 값이다. confirmation 순간에도 proposer가 active이고 권한을 유지하며 그 fresh-auth
  창 안이어야 한다. 하나라도 아니면 새 fresh-auth proposal로 다시 시작한다.
- `releases.accept` 부여·회수 자체도 append-only audit 대상이다. 대상자 자신은 부여를
  제안·확정할 수 없고, 서로 다른 두 `users.manage` 활성 사람이 같은 grant digest를
  확인해야 enable된다. 한 관리자가 두 번째 계정을 만들고 스스로 권한까지 주는 경로를
  허용하지 않는다.
- 초기 bootstrap도 한 사람의 web route로 열지 않는다. 설치 시 서로 다른 두 물리 운영자가
  서명한 offline bootstrap bundle을 배포 도구가 검증해 최초 두 `users.manage`를 만들고,
  bundle digest·두 operator certificate fingerprint·적용 결과를 append-only audit에 남긴다.
  bundle이 없거나 서명이 하나뿐이면 tenant는 `releases.accept`를 부여하지 못하는 상태로
  fail closed한다. break-glass도 같은 2인 서명과 사후 감사 없이는 허용하지 않는다.

## 3. 공개 route와 strict body

모든 POST는 `Content-Type: application/json`, `Authorization`, printable ASCII 33..126의
1..128자 `Idempotency-Key`가 필수다. JSON은 duplicate key·scalar·array·8 KiB 초과를
`VAL-0003/422`로 거부한다. 공개 body는 `src/saintvision/api/schemas.py`에서 생성하며
`tools/export_schemas.py`가 `contracts/*.schema.json`을 만든다.

| route | 요청 contract | 성공 |
|---|---|---|
| `POST /v1/release-manifests/{release_id}/acceptance-decisions` | `ReleaseAcceptanceDecisionRequest` | `accepted`: `202 ReleaseAcceptanceProposalResponse`; `conditional/rejected`: `201 ReleaseAcceptanceRecordedResponse` |
| `GET /v1/release-manifests/{release_id}/acceptance-decisions?state=pending_second_operator&limit={1..100}&cursor={opaque}` | body 없음 | `200 ReleaseAcceptanceProposalReviewPageResponse` |
| `GET /v1/release-manifests/{release_id}/acceptance-decisions/{proposal_id}` | body 없음 | `200 ReleaseAcceptanceProposalReviewResponse` |
| `POST /v1/release-manifests/{release_id}/acceptance-decisions/{proposal_id}/confirm` | `ReleaseAcceptanceConfirmationRequest` | `201 ReleaseAcceptanceRecordedResponse` |
| `POST /v1/release-manifests/{release_id}/acceptances/{acceptance_id}/withdrawals` | `ReleaseAcceptanceWithdrawalRequest` | `201 ReleaseAcceptanceWithdrawalResponse` |

두 GET은 같은 tenant의 fresh active human이 live `releases.accept`를 보유할 때만 pending proposal의
outcome·reasonCode·manifest/proposal digest·targetRefs·measurementRefs·knownLimitations·expiresAt을
반환한다. proposer/confirming user ID는 반환하지 않는다. confirmer는 이 응답의 내용을 본 뒤
그 `proposalDigest`를 confirm body에 넣는다. inactive·다른 tenant proposal은 존재 비노출
`RES-0004/404`다. 목록은 `(created_at,proposal_id)` 안정 정렬, `limit+1`, opaque cursor를 쓰고
최대 100건만 반환한다. 따라서 confirmer가 proposal ID를 out-of-band로 전달받을 필요가 없다.

proposal 범위 공개 필드는 `proposalConfirmationCount`와
`decisionSignOff=false`, final decision 범위는 `decisionConfirmationCount`와
`decisionSignOff`다. #280 읽기의 `confirmedOperatorCount`·`operatorSignOff`는 release
전체 집계 범위이므로 write 응답에서 재사용하지 않는다. withdrawal 응답의 `operatorSignOff`만
철회 commit 뒤의 release 집계값이라는 같은 의미로 유지한다.

ledger canonical payload는 parse 완료 모델에서 다음 exact object로 만든다.

- decision: `{releaseId,request}`
- confirm: `{releaseId,proposalId,request}`
- withdrawal: `{releaseId,acceptanceId,request}`

따라서 같은 key를 다른 path ID에 재사용하면 `IDEM-0001/409`다. 인증·active user·fresh AMR·live
permission을 **매 요청과 replay 전에** 다시 확인하고 나서만 ledger receipt를 반환한다. 같은
key와 같은 canonical payload replay는 최초 status/body를 반환하되 `replayed=true`; raw header·
credential은 digest에 들어가지 않는다.

### 3-1. target과 measurement

- `targetRefs[] = {targetId,targetSha256}`는 Git에 고정된 수용 목표·registry blob의
  identity다.
- `measurementRefs[] = {evidenceId,evidenceSha256,observedAt}`는 이미 저장된 immutable
  Evidence identity다.
- 둘은 각각 1개 이상 필요하고 ID 중복은 거부한다. `knownLimitations`는
  `conditional`일 때만 비어 있지 않을 수 있다.
- 구현은 모든 ref를 서버가 소유한 target/Evidence registry에서 exact digest로 resolve해야
  한다. 조회 저장소가 없거나 digest·tenant·release scope가 다르면 accepted로 기록하지
  않는다. caller가 보낸 ID·hash만 맞춰 보는 구현은 허용하지 않는다.
- `accepted`는 측정된 사실을 뜻하지만 **AC-12 전체 완료를 자동 판정하지 않는다**.
  이 route는 사람이 고정된 target과 measurement를 수락했다는 사실만 기록한다.

### 3-2. proposal digest

`proposalDigest`는 server-derived `(tenantId,releaseId,acceptanceIdRef,outcome,
targetManifestSha256,reasonCode,targetRefs,measurementRefs,knownLimitations,expiresAt)`의
**parse 완료 모델** alias-key JSON으로만 계산한다. 모든 datetime은 UTC
`YYYY-MM-DDTHH:MM:SS.ffffffZ` 6자리 소수초로 만들고 key sort·compact separators·UTF-8로
canonicalize한 SHA-256이다. 배열 순서는 의미가 있으므로 서버가 정렬하지 않는다. digest는
strip 전에 정확히 소문자 hex 64자여야 하며 끝 개행도 거부한다. confirmer는 먼저 GET으로
내용을 읽고 proposal ID·digest·manifest digest를 모두 고정한다.

## 4. transaction과 경합

lock 순서는 모든 쓰기 route에서 같다.

1. token을 검증하고 tenant·active user·fresh-auth·`releases.accept`를 확인한다.
2. path ID까지 포함한 idempotency advisory lock/ledger를 획득한다. replay path도 1번을
   건너뛰지 않는다.
3. confirm은 proposer와 confirmer
   두 사람의 active 상태·권한, 저장된 proposer fresh-auth 시각을 모두 재확인한다.
4. `(tenant_id,release_id)` manifest를 잠그고 `targetManifestSha256`과 server digest를
   constant-time 비교한다.
5. criterion coordination slot과 proposal/final decision/withdrawal 상태를 잠근다.
6. target·measurement ref를 authoritative row/blob에 다시 결속한다.
7. proposal/vote/final acceptance/withdrawal/lifecycle event와 audit/outbox를 같은 transaction에 쓴다.
8. permission·manifest·Evidence binding을 최종 재확인하고 response를 ledger에 확정한 뒤 commit한다.

accepted 동시 첫 요청은 release×criterion의 coordination slot을 통해 active proposal 하나로만
수렴한다. 서로 다른 body는 `GRAPH-0003/409`; 같은 body·다른 key는 existing proposal의
최초 `202` body를 `replayed=true`로 반환하고 loser key의 ledger에도 그 canonical receipt를
확정하되 새 vote나 감사 사건을 만들지 않는다. confirmer 두 개가 경쟁하면
서로 다른 두 번째 사람의 첫 vote만 final transition을 수행하고, loser는 동일 final response를
최초 `201` status로 `replayed=true` 반환하며 loser key를 확정한다. 동일 proposer는 직접
confirm할 수 없다.

권한·Evidence가 lock 전후 달라지면 transaction 전체를 rollback한다. proposal의 시간 만료나
manifest drift는 예외다. immutable proposal을 수정하지 않고 `expired|manifest-superseded`
lifecycle event를 append하고 coordination slot을 비운 transaction을 **commit한 뒤**
`GRAPH-0003/409`를 반환한다. 오류 예외로 그 transaction을 rollback해서는 안 된다.
lock/statement timeout은 기존 `RES-0007/503/retryable=true`; commit 전 부분 행·audit은 0이다.

### 4-1. migration·DB 불변식

구현 migration은 proposal, vote, final decision, withdrawal, lifecycle event, coordination slot을
tenant-scoped table로 만들고 모두 `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`를
적용한다. 사건 table은 `inv_app`에 `SELECT,INSERT`만 주고 `UPDATE,DELETE`는 PUBLIC·inv_app에서
회수한다. coordination slot만 canonical 함수 안에서 갱신 가능하다.

- `(proposal_id,user_id)` vote UNIQUE, `withdrawal.acceptance_id` UNIQUE.
- `(tenant_id,release_id,acceptance_id_ref)` coordination slot UNIQUE가 active proposal/final을
  하나만 가리키며 FK로 immutable row를 참조한다.
- terminal lifecycle event는 `(proposal_id,event_kind)` UNIQUE이고 proposal row를 고치지 않는다.
- final accepted는 distinct user 두 명과 proposal digest를 DB 함수가 재검증한 경우만 INSERT한다.
- `business_admin_grants.permission` CHECK를 `releases.accept`와 grant-governance permission까지
  명시적으로 확장한다.
- 기존 `uq_acceptance_records_release_criterion`은 새 slot 불변식으로 대체한다. 0005의
  `inv_app UPDATE,DELETE` grant는 회수한다.
- proposal/vote/withdrawal RLS `WITH CHECK`는 current tenant와 server-derived user mapping을
  다시 확인한다. canonical write 함수는 `SECURITY INVOKER`이고 EXECUTE는 `inv_app`에만 준다.
  함수는 raw user ID 인자를 받지 않고 요청 transaction이 verified principal에서 설정한
  `SET LOCAL inv.tenant_id`·`inv.user_id`를 읽어 active mapping과 권한을 다시 확인한다.
  SECURITY DEFINER 함수, dynamic SQL, PUBLIC EXECUTE는 금지한다.

기존 `record_acceptance()`의 1인 `accepted` 경로는 migration과 같은 release에서 폐쇄한다.
legacy row는 `attestation_version=legacy-unverified`로 분류해 sign-off에 세지 않으며, 함수가
accepted를 받으면 fail closed한다. conditional/rejected도 새 canonical service로만 생성한다.

## 5. manifest digest와 sign-off 계산

- request digest 불일치는 malformed input이 아니라 stale target이므로 `GRAPH-0003/409`다.
- proposal 이후 manifest digest가 달라지면 confirm은 invalidation event와 slot 해제를 commit하고
  `GRAPH-0003/409`를 반환한다. 시간 만료도 `now >= expires_at`으로 계산한 뒤 같은 방식으로
  append-only event를 남긴다. 그 409 ProblemDetails를 같은 idempotency transaction의 receipt로
  확정하므로 같은 key·payload replay는 인증·fresh-auth·권한 재확인 뒤 같은 409를 돌려준다.
  다른 key는 inactive state를 다시 판정해 같은 409를 새 receipt로 확정한다.
- v1에는 proposer 임의 취소 route를 열지 않는다. 잘못 만든 proposal은 최대 5분 뒤 만료되고,
  security operator는 manifest/permission을 바꿔 fail closed시킬 수 있다. 취소를 추가하려면
  별도 reason enum·idempotency·audit 계약을 먼저 추가한다.
- final acceptance에는 **잠근 server manifest digest**만 쓴다.
- accepted final row의 기존 `accepted_by_user_id`에는 final transition을 수행한 confirmer를
  저장하고 proposer는 immutable proposal/vote 행에 보존한다. conditional/rejected는 그
  결정을 낸 actor를 저장한다. 어느 user ID도 공개 response에는 나오지 않는다.
- read route의 `operatorSignOff`는 server policy registry가 선언한 **모든 required criterion**에
  대해 active final이 존재하고 각각 outcome accepted, distinct fresh operators 2, not withdrawn,
  accepted digest == current manifest digest, target/Evidence binding valid일 때만 true다. required
  criterion 하나라도 missing·conditional·rejected·withdrawn이면 false다. `pilot_readiness()`도
  이 단일 함수를 사용하고 별도 rejected 규칙을 만들지 않는다.
- release 범위 `confirmedOperatorCount`는 위 aggregate에 기여하는 decision의 proposer와
  confirmer 중 fresh interactive human attestation이 유효한 서로 다른 운영자 수다. raw legacy
  accepted user, service/system/client-credentials 주체, 만료·철회·manifest drift decision은 세지
  않는다. attestation projection이 구현되기 전에는 0이며 blocker를 함께 반환한다.
- manifest가 바뀌면 기존 행을 수정하지 않아도 즉시 false다. 같은 이름의 새 composition은
  새 proposal과 두 fresh operators가 필요하다.

### 5-1. required criterion policy registry

구현 카드는 기존 `contracts` 디렉터리에 Git 소유 정본
`release-acceptance-policy-registry-v1.json`을 새로 만들고 S12-BE owner가 관리한다. 파일은 strict
JSON object이며 `schemaVersion`, 단조 증가 `policyVersion`,
`requiredCriteria[]`(`acceptanceIdRef`, `targetRegistryRef`, `measurementRegistryRef`)를 갖는다.
배포는 파일 bytes의 SHA-256과 `policyVersion`을 release manifest에 고정하고, 읽기 projection과
proposal digest는 그 고정값을 함께 결속한다.

- 파일 누락·parse/schema 실패·`requiredCriteria=[]`·중복 criterion·고정 digest 불일치는
  `operatorSignOff=false`다. 빈 집합에 `all(...)`을 적용해 true로 만들 수 없다.
- registry에 없는 `acceptanceIdRef` decision은 `GRAPH-0003/409`로 거부하고 final row를 만들지 않는다.
- registry version/digest가 바뀌면 기존 release는 manifest drift와 같은 방식으로 즉시 false이며,
  새 manifest와 새 proposal·두 fresh operators가 필요하다.
- 정책 파일과 이를 읽는 code owner는 S12-BE, 계약·보안 reviewer는 Codex다. merge review 없이
  required criterion을 줄이거나 빈 목록으로 바꾸는 운영 override는 없다.

## 6. 철회·재결정

- 철회는 `DELETE`가 아니라 append-only POST다. final decision만 철회할 수 있다.
- 철회는 안전 쪽 전이이므로 fresh `releases.accept` 운영자 **한 명**이 수행할 수 있다.
  자신이 만들지 않은 decision도 철회할 수 있지만 actor는 server-derived audit에 남는다.
- 철회 request의 `acceptedManifestSha256`은 **철회 대상 final row에 저장된 digest**와 같아야
  한다. 현재 release digest와는 다를 수 있으며 현재 digest는 aggregate 재계산에만 쓴다.
- 철회는 acceptance·vote·Evidence를 삭제하거나 수정하지 않는다. 철회된 active final이 맡던
  required criterion은 새 유효 final이 생기기 전까지 미충족이므로 sign-off는 false다. superseded
  old final을 철회할 때만 다른 active final 때문에 release aggregate가 계속 true일 수 있다.
- rejected/conditional 철회도 그것만으로 sign-off를 만들지 않는다. 다음 accepted 결정은
  새 proposal ID, 새 digest, 두 fresh operators가 필요하다.
- 한 final decision의 withdrawal은 한 번만 생성한다. exact replay는 같은 receipt,
  다른 이유·manifest는 `IDEM-0001/409`, 이미 철회된 row에 새 key는 `GRAPH-0003/409`다.

## 7. 오류 계약

모든 오류는 `contracts/v1alpha1/core.schema.json::$defs.ProblemDetails`의 exact 10-key,
`about:blank`, `application/problem+json`, `Cache-Control: no-store`를 쓴다.

| 조건 | code / HTTP / retryable |
|---|---|
| token 부재·무효·만료 | `AUTH-0050` / 401 / false |
| fresh interactive auth 부재, user 비활성, 권한 없음 | `AUTH-0030` / 403 / false |
| 같은 사람 confirm, distinct quorum 없음 | `AUTH-0033` / 403 / false |
| 다른 tenant·부재 release/proposal/acceptance | `RES-0004` / 404 / false |
| malformed JSON·unknown key·schema 위반 | `VAL-0003` / 422 / false |
| same idempotency key + different body | `IDEM-0001` / 409 / false |
| digest/state/expiry/evidence drift | `GRAPH-0003` / 409 / false |
| DB lock/statement timeout | `RES-0007` / 503 / true |
| 선언하지 않은 내부 오류 | `SYS-0002` / 500 / false |

404는 입력 ID나 존재 여부를 detail에 echo하지 않는다. 403은 missing permission인지 stale
fresh-auth인지 구분하지 않는다. measurement 내용·known limitation·사용자 ID도 오류에 싣지
않는다.

## 8. 감사 사건

허용 action은 다음 여섯 개뿐이다.

| action | 언제 | redacted detail |
|---|---|---|
| `release.acceptance.proposed` | accepted 첫 proposal | release/proposal/criterion IDs, manifest/proposal digest, ref count |
| `release.acceptance.recorded` | conditional/rejected final | release/acceptance/criterion IDs, outcome, manifest digest, ref count |
| `release.acceptance.confirmed` | distinct second operator final | release/proposal/acceptance IDs, manifest/proposal digest |
| `release.acceptance.proposal_invalidated` | 시간 만료·manifest drift를 append-only로 닫음 | release/proposal/criterion IDs, closed reason |
| `release.acceptance.withdrawn` | append-only withdrawal | release/acceptance/withdrawal IDs, reasonCode, manifest digest |
| `release.acceptance.denied` | auth·scope·digest·state 거부 | reasonCode와 route kind만 |

성공 audit의 actor는 server-derived user다. denial은 transaction rollback 밖
`record_denial_out_of_band()`로 남기되 credential 검증 전에는 `actor_type=anonymous`를 쓴다.
token, OIDC claims, user display data, free text, target/measurement payload, known limitation 본문,
상대 tenant ID는 어느 audit에도 넣지 않는다.

## 9. 구현 카드 수용 시험

### PG-free

1. strict request/response schema, exact required set, duplicate JSON key, oversized body, unknown key,
   digest 대문자·63자·끝 개행 거부.
2. body의 `acceptedByUserId`·token·reauth proof·notes 거부.
3. conditional limitation 규칙과 target/measurement 최소 1·중복 ID 거부.
4. service token, missing/future/stale `auth_time`, non-interactive/malformed `amr` 거부.
5. pending proposal은 `proposalConfirmationCount=1`·`decisionSignOff=false`, accepted final은
   `decisionConfirmationCount=2`·`decisionSignOff=true`, nonaccepted는 count 1·false.
6. same key same body replay; 같은 key를 다른 release/proposal/acceptance path에 재사용 거부;
   replay 전 auth·fresh-auth·permission 재확인; same proposal 다른 key 수렴.
7. same actor confirm 거부, proposal expiry, manifest/evidence/permission drift.
8. proposal 목록·단건 GET은 refs/reason/expiry를 전부 반환하고 user ID 0; stable cursor·100건
   상한; 만료·manifest drift lifecycle event append와 409 receipt 확정; withdrawal append-only·
   double withdrawal·required criterion 미충족 계산.
9. 오류 10-key exact·no-store·identifier/non-secret leakage 0, audit payload closed set.
10. 생성된 `contracts/*.schema.json`과 Pydantic source 일치. pending review의
    `decisionSignOff=true` 변이는 Pydantic과 JSON Schema 양쪽에서 거부.
11. policy registry 누락·빈 required set·unknown criterion·version/digest drift는 모두
    release sign-off false 또는 decision 409이며 빈 `all()` true는 금지.

### hosted real PostgreSQL

1. 두 연결 동시 proposal → active proposal 1, vote 1, audit 1.
2. 서로 다른 confirmer 경쟁 → final acceptance 1, distinct vote 2, confirm audit 1.
3. proposer self-confirm, service identity, suspended user, 권한 회수 → final row 0.
4. manifest/evidence row를 proposal과 confirm 사이 바꾸면 final row 0·sign-off false.
5. lock timeout·audit INSERT 실패·idempotency finish 실패 → 부분 row 0, 같은 key 재시도 1건.
6. accepted 철회 경합 → withdrawal 1, 역사 보존, read route sign-off false.
7. tenant cross-scope는 존재 비노출 404이고 다른 tenant row 변화 0.
8. 사건 table UPDATE/DELETE, duplicate vote/withdrawal, slot 우회, inv_app/PUBLIC 함수 EXECUTE,
   grant self-approval은 DB가 거부한다.
9. legacy `record_acceptance(accepted)`는 sign-off를 만들지 못하고 legacy row도 aggregate에서 빠진다.

되살림 변이는 최소한 user ID body 허용, fresh-auth 제거, same-person confirm, digest 재확인 제거,
Evidence resolve 제거, idempotency lock 순서 변경, withdrawal delete, audit transaction 분리,
nonaccepted sign-off true를 각각 독립 시험이 죽여야 한다.

## 10. 비주장과 인계

- 이번 PR은 route·migration·runtime permission·audit event를 구현하지 않는다.
- 현재 OIDC principal에는 fresh-auth metadata가 없으므로 이 설계만으로 사람 인증이
  측정됐다고 주장하지 않는다.
- target/Evidence authoritative registry가 결속되기 전에는 accepted route를 enable하지 않는다.
- Keycloak access-token `auth_time`·`amr` mapper와 portal step-up 흐름이 exact claim fixture로
  검증되기 전에는 모든 write route를 enable하지 않는다.
- 기존 #280 read route는 withdrawal/quorum/required-criterion-aware projection으로 교체하고
  `operator_sign_off()`와 `pilot_readiness()`가 같은 함수를 쓰기 전에는 이 계약과 결속됐다고
  주장하지 않는다. release 범위 `confirmedOperatorCount`는 human-attested distinct operator
  수로만 쓰고 구현 전에는 0으로 고정한다. raw legacy row 수는 `matchingAcceptedUserCount`,
  proposal/decision 범위는 `proposalConfirmationCount`·`decisionConfirmationCount`·
  `decisionSignOff`로 분리한다.
- physical 5-node acceptance, operator training, PITR 복구, browser sign-off는 이 계약의
  `measurementRefs` 입력일 뿐 이 PR이 측정한 결과가 아니다.
- 구현 owner는 Claude, 계약·보안 reviewer는 Codex다. migration이 필요하므로 구현자는
  coordinator에게 다음 revision을 배정받고, 이 설계를 바꾸면 contract PR부터 다시 낸다.
