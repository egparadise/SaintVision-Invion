---
doc_id: "DESIGN-S12-BE-RELEASE-ACCEPTANCE-WRITE-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 보안 계약 설계"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
audience: "agent"
updated: "2026-10-01T18:48:04+09:00"
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
2. `accepted`만 **서로 다른 두 사람**이 같은 proposal digest를 확인해야 최종
   `operatorSignOff=true`가 된다. `conditional`과 `rejected`는 한 사람의 최종 기록이지만
   sign-off를 만들지 않는다.
3. 클라이언트는 승인하려는 `targetManifestSha256`을 보낸다. 서버는 잠근 manifest에서
   digest를 다시 읽어 일치할 때만 그 서버 값을 기록한다. caller 값은 저장값의 정본이
   아니다.
4. target과 measurement는 strict reference 목록으로 분리한다. **목표 선언은 관측이
   아니며**, opaque hash를 보내는 것만으로 측정 증거가 되지 않는다.
5. 최종 기록·투표·철회는 append-only다. 철회는 과거를 지우지 않고 sign-off를 즉시
   false로 만드는 새 사건이다.

이 PR은 설계와 공개 JSON Schema만 낸다. route, 서비스, DB migration, OIDC claim 보존,
감사 기록 구현은 Claude의 다음 카드다. 구현 전까지 기존 읽기 route는 계속 read-only이고
`operatorSignOff`를 새로 true로 만들 수 없다.

## 1. 현재 코드 경계와 필요한 변경

| 현재 정본 | 확인한 사실 | 구현 카드가 해야 할 일 |
|---|---|---|
| `src/saintvision/db/models/operations_pilot.py` | `acceptance_records.accepted_by_user_id`는 실제 user FK이나 release×criterion unique라 재결정·철회·2인 투표를 표현하지 못한다 | proposal·operator vote·withdrawal을 append-only로 표현하고 active criterion을 원자적으로 하나만 유지한다 |
| `src/saintvision/services/pilot.py` | `record_acceptance()`가 manifest digest를 server-side로 읽는 좋은 경계를 이미 갖는다 | manifest row lock과 final recheck를 추가하고 caller digest를 optimistic concurrency target으로만 쓴다 |
| `src/saintvision/identity/oidc.py` | verified subject를 활성 user로 매핑하지만 `Principal`에는 `auth_time`·`amr`·`acr`가 없다 | 검증된 identity의 fresh-auth metadata를 내부 principal/context에 보존한다. raw token은 저장하지 않는다 |
| `src/saintvision/services/settings.py` | tenant 전역 권한은 `business_admin_allowed`로 매 요청 DB에서 확인한다 | coordinator가 배정한 migration에서 `releases.accept` 권한을 추가하고 create·confirm·withdraw 때 각각 live 재확인한다 |
| `src/saintvision/api/deps.py` | durable idempotency ledger와 advisory lock이 있다 | tenant-wide endpoint이므로 `project_id=NULL`, endpoint별 상수를 사용한다 |
| `src/saintvision/services/audit.py` | 요청 transaction 감사와 rollback 밖 denial 감사를 나눈다 | 성공·거절을 §8의 닫힌 action/payload로 기록한다 |

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
- 검증된 `amr`가 `pwd`, `webauthn`, `mfa` 중 하나 이상의 대화형 방법을 포함한다.
  claim 부재·형식 오류·미래 시각은 fail closed다. `exp-iat<=3600`은 token 수명일 뿐
  재인증 증거를 대신하지 않는다.
- client-credentials·system·service identity는 user 행을 가리키더라도 위 interactive
  조건을 충족하지 못하므로 거부한다.

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

## 3. 공개 route와 strict body

모든 POST는 `Content-Type: application/json`, `Authorization`, printable ASCII 33..126의
1..128자 `Idempotency-Key`가 필수다. JSON은 duplicate key·scalar·array·8 KiB 초과를
`VAL-0003/422`로 거부한다. 공개 body는 `src/saintvision/api/schemas.py`에서 생성하며
`tools/export_schemas.py`가 `contracts/*.schema.json`을 만든다.

| route | 요청 contract | 성공 |
|---|---|---|
| `POST /v1/release-manifests/{release_id}/acceptance-decisions` | `ReleaseAcceptanceDecisionRequest` | `accepted`: `202 ReleaseAcceptanceProposalResponse`; `conditional/rejected`: `201 ReleaseAcceptanceRecordedResponse` |
| `POST /v1/release-manifests/{release_id}/acceptance-decisions/{proposal_id}/confirm` | `ReleaseAcceptanceConfirmationRequest` | `201 ReleaseAcceptanceRecordedResponse` |
| `POST /v1/release-manifests/{release_id}/acceptances/{acceptance_id}/withdrawals` | `ReleaseAcceptanceWithdrawalRequest` | `201 ReleaseAcceptanceWithdrawalResponse` |

같은 idempotency key와 같은 canonical body의 replay는 최초 status와 body를 그대로 반환하고
`replayed=true`로만 직렬화한다. 같은 key와 다른 body는 `IDEM-0001/409`다. header는 body
digest에 들어가되 raw credential은 들어가지 않는다.

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
targetManifestSha256,reasonCode,targetRefs,measurementRefs,knownLimitations)`의 alias-key JSON을
datetime을 UTC RFC 3339로 정규화한 뒤 key sort·compact separators·UTF-8로 canonicalize한
SHA-256이다. 배열 순서는 의미가 있으므로 서버가 정렬하지 않는다. confirmer는 proposal
ID와 digest, manifest digest를 모두 고정한다.

## 4. transaction과 경합

lock 순서는 모든 세 route에서 같다.

1. idempotency advisory lock/ledger를 먼저 획득한다.
2. tenant·active user·`releases.accept`·fresh-auth를 확인한다. confirm은 proposer와 confirmer
   두 사람의 active 상태·권한, 저장된 proposer fresh-auth 시각을 모두 재확인한다.
3. `(tenant_id,release_id)` manifest를 잠그고 `targetManifestSha256`과 server digest를
   constant-time 비교한다.
4. criterion의 active proposal/final decision/withdrawal 상태를 잠근다.
5. target·measurement ref를 authoritative row/blob에 다시 결속한다.
6. proposal/vote/final acceptance/withdrawal과 audit/outbox를 같은 transaction에 쓴다.
7. response를 idempotency ledger에 확정한 뒤 commit한다.

accepted 동시 첫 요청은 release×criterion×manifest digest의 active proposal 하나로만
수렴한다. 서로 다른 body는 `GRAPH-0003/409`; 같은 body·다른 key는 existing proposal의
identity를 반환하되 새 vote나 감사 사건을 만들지 않는다. confirmer 두 개가 경쟁하면
서로 다른 두 번째 사람의 첫 vote만 final transition을 수행하고, loser는 동일 final response를
replay한다. 동일 proposer는 직접 confirm할 수 없다.

manifest·proposal·권한·evidence가 lock 전후 달라지면 transaction 전체를 rollback한다.
lock/statement timeout은 기존 `RES-0007/503/retryable=true`; commit 전 부분 행·audit은 0이다.

## 5. manifest digest와 sign-off 계산

- request digest 불일치는 malformed input이 아니라 stale target이므로 `GRAPH-0003/409`다.
- proposal 이후 manifest digest가 달라지면 confirm은 `GRAPH-0003/409`, proposal은 expired로
  닫고 final acceptance를 만들지 않는다.
- final acceptance에는 **잠근 server manifest digest**만 쓴다.
- accepted final row의 기존 `accepted_by_user_id`에는 final transition을 수행한 confirmer를
  저장하고 proposer는 immutable proposal/vote 행에 보존한다. conditional/rejected는 그
  결정을 낸 actor를 저장한다. 어느 user ID도 공개 response에는 나오지 않는다.
- read route의 `operatorSignOff`는 다음을 모두 만족할 때만 true다: outcome accepted,
  distinct fresh operators 2, not withdrawn, accepted digest == current manifest digest,
  target/Evidence binding valid.
- manifest가 바뀌면 기존 행을 수정하지 않아도 즉시 false다. 같은 이름의 새 composition은
  새 proposal과 두 fresh operators가 필요하다.

## 6. 철회·재결정

- 철회는 `DELETE`가 아니라 append-only POST다. final decision만 철회할 수 있다.
- 철회는 안전 쪽 전이이므로 fresh `releases.accept` 운영자 **한 명**이 수행할 수 있다.
  자신이 만들지 않은 decision도 철회할 수 있지만 actor는 server-derived audit에 남는다.
- 철회는 acceptance·vote·Evidence를 삭제하거나 수정하지 않는다. 철회된 accepted decision은
  sign-off 계산에서 빠지고, release 전체 값은 남은 다른 criterion의 유효한 accepted
  decision까지 다시 계산한다. 남은 유효 decision이 없을 때만 false다.
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

허용 action은 다음 다섯 개뿐이다.

| action | 언제 | redacted detail |
|---|---|---|
| `release.acceptance.proposed` | accepted 첫 proposal | release/proposal/criterion IDs, manifest/proposal digest, ref count |
| `release.acceptance.recorded` | conditional/rejected final | release/acceptance/criterion IDs, outcome, manifest digest, ref count |
| `release.acceptance.confirmed` | distinct second operator final | release/proposal/acceptance IDs, manifest/proposal digest |
| `release.acceptance.withdrawn` | append-only withdrawal | release/acceptance/withdrawal IDs, reasonCode, manifest digest |
| `release.acceptance.denied` | auth·scope·digest·state 거부 | reasonCode와 route kind만 |

성공 audit의 actor는 server-derived user다. denial은 transaction rollback 밖
`record_denial_out_of_band()`로 남기되 credential 검증 전에는 `actor_type=anonymous`를 쓴다.
token, OIDC claims, user display data, free text, target/measurement payload, known limitation 본문,
상대 tenant ID는 어느 audit에도 넣지 않는다.

## 9. 구현 카드 수용 시험

### PG-free

1. strict request/response schema, duplicate JSON key, oversized body, unknown key, digest pattern.
2. body의 `acceptedByUserId`·token·reauth proof·notes 거부.
3. conditional limitation 규칙과 target/measurement 최소 1·중복 ID 거부.
4. service token, missing/future/stale `auth_time`, non-interactive/malformed `amr` 거부.
5. accepted proposal이 sign-off false, accepted final이 2명/true, nonaccepted가 1명/false.
6. same key same body replay; same key different body; same proposal 다른 key 수렴.
7. same actor confirm 거부, proposal expiry, manifest/evidence/permission drift.
8. withdrawal append-only·double withdrawal·withdrawal 뒤 sign-off false.
9. 오류 10-key exact·no-store·identifier/non-secret leakage 0, audit payload closed set.
10. 생성된 `contracts/*.schema.json`과 Pydantic source 일치.

### hosted real PostgreSQL

1. 두 연결 동시 proposal → active proposal 1, vote 1, audit 1.
2. 서로 다른 confirmer 경쟁 → final acceptance 1, distinct vote 2, confirm audit 1.
3. proposer self-confirm, service identity, suspended user, 권한 회수 → final row 0.
4. manifest/evidence row를 proposal과 confirm 사이 바꾸면 final row 0·sign-off false.
5. lock timeout·audit INSERT 실패·idempotency finish 실패 → 부분 row 0, 같은 key 재시도 1건.
6. accepted 철회 경합 → withdrawal 1, 역사 보존, read route sign-off false.
7. tenant cross-scope는 존재 비노출 404이고 다른 tenant row 변화 0.

되살림 변이는 최소한 user ID body 허용, fresh-auth 제거, same-person confirm, digest 재확인 제거,
Evidence resolve 제거, idempotency lock 순서 변경, withdrawal delete, audit transaction 분리,
nonaccepted sign-off true를 각각 독립 시험이 죽여야 한다.

## 10. 비주장과 인계

- 이번 PR은 route·migration·runtime permission·audit event를 구현하지 않는다.
- 현재 OIDC principal에는 fresh-auth metadata가 없으므로 이 설계만으로 사람 인증이
  측정됐다고 주장하지 않는다.
- target/Evidence authoritative registry가 결속되기 전에는 accepted route를 enable하지 않는다.
- physical 5-node acceptance, operator training, PITR 복구, browser sign-off는 이 계약의
  `measurementRefs` 입력일 뿐 이 PR이 측정한 결과가 아니다.
- 구현 owner는 Claude, 계약·보안 reviewer는 Codex다. migration이 필요하므로 구현자는
  coordinator에게 다음 revision을 배정받고, 이 설계를 바꾸면 contract PR부터 다시 낸다.
