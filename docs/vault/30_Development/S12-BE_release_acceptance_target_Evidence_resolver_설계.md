---
doc_id: "DESIGN-S12-ACCEPTANCE-RESOLVER-001"
title: "S12 release 수락 target·Evidence 정본 resolver 설계"
version: "1.1.1"
status: "proposed"
author: "Codex"
updated: "2026-10-01T22:14:13+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S12-BE", "acceptance", "target-registry", "evidence", "resolver", "security"]
---

# S12 release 수락 target·Evidence 정본 resolver 설계

## 0. 결정과 범위

이 문서는 [[S12-BE_release_acceptance_operator_signoff_쓰기_계약_설계]] v1.3.0이
`measurementRefs[].evidenceSha256`을 `evidence_envelopes.input_sha256`으로 대체하지 않기로 한
결정을 구현 가능한 계약으로 좁힌다. 이번 카드가 만드는 것은 다음 세 가지다.

1. Git 정본 `contracts/release-acceptance-target-registry-v1.json`과 공개 strict schema.
2. Evidence envelope 자체의 versioned digest와 release 범위 binding 설계.
3. caller ref를 server-owned row에 exact resolve한 all-or-nothing 내부 결과 계약.

route, resolver service, DB migration, legacy backfill은 **미구현**이다. 따라서 이 PR만으로
`INV_RELEASE_ACCEPTANCE_WRITE_ENABLED`를 켜거나 `operatorSignOff=true`를 만들 수 없다. 구현 owner는
Claude이고 coordinator가 migration 번호 **`0058`을 카드 190 계열 구현에 예약 승인**했다
(`0057`은 카드 187).

현재 사실은 다음과 같다.

- `EvidenceEnvelope`의 정본 키는 `(evidence_id, recorded_at)`이고 `input_sha256`은 collector 입력의
  identity다(`src/saintvision/db/models/evidence.py:49-88`). envelope 전체 digest 열은 없다.
- Evidence는 tenant RLS와 append-only `SELECT, INSERT` 경계다
  (`migrations/versions/0002_s03_execution.py:323-365`, `:517-526`).
- Run의 project는 `EvidenceEnvelope.run_id -> runs.workload_id -> workloads.project_id`로만
  도출된다(`src/saintvision/db/models/execution.py:139-181`). release manifest 자체에는 project가
  없으므로 caller가 준 Evidence ID만으로 release/project 귀속을 주장할 수 없다.
- 공개 입력은 target과 measurement를 구분하고, measurement가
  `{evidenceId,evidenceSha256,observedAt}`임을 이미 고정한다
  (`src/saintvision/api/schemas.py`, `ReleaseAcceptanceMeasurementRef`).

## 1. target registry

### 1-1. 정본과 초기 target

정본 파일은 `contracts/release-acceptance-target-registry-v1.json`이고 다음 닫힌 envelope다.

| 필드 | 규칙 |
|---|---|
| `schemaVersion` | `release-acceptance-target-registry:1` literal |
| `registryId` | 카드 187 policy registry가 가리키는 `release-acceptance-targets-v1` literal |
| `registryVersion` | v1에서는 `1`; 변경 시 단조 증가하고 배포가 파일 blob과 함께 pin |
| `owner` | `S12-BE` |
| `canonicalization` | `saintvision-canonical-json-v1` |
| `targets` | 1..64, `(targetId,targetVersion)` unique; 빈/누락은 실패 |

초기 `AC-12.release-acceptance-v1`은 `S12 파일럿.md`의 blob
`0606c0dc2a1adb90636bf1461deba37541726caa`(commit
`b96068b6d009cf2d9ea677b9801749a1e6efd9d0`)에 결속한다. AC-12의 네 축은 5노드 전체
여정, 사전 등록 정량 목표, 알려진 제한·미측정 외부 전제, exact manifest에 대한 사람 인수다.
target은 요구사항 선언이고, 그 자체가 어느 축의 측정 증거도 아니다.

source commit `b96068b6…`은 #282의 승인 head다. 착지는 **merge commit만** 허용해 이 commit을
integration landing SHA의 조상으로 보존하며, squash/rebase로 도달 불가능해지면 registry source gate가
실패한다. 카드 190도 #282 뒤에만 착지한다.

`targetSha256`의 입력은 해당 target object에서 **`targetSha256` 하나만 제외한 object**다.
`saintvision-canonical-json-v1`은 duplicate key를 거부하고, 문자열은 NFC, 정수만 허용하며
float·NaN·Infinity를 거부한다. object key는 Unicode scalar 순으로 정렬하고 array 순서는 보존,
UTF-8(BOM 없음), 공백 없는 `,`·`:` separator로 직렬화한다. hash는 lowercase
`hex(SHA-256(bytes))`다. 초기 target의 값은
`d57198451ef2b1784cd61c04c70d9092a285565b633853b2ec57ef18d25eee9d`다.

### 1-2. 변경 절차

- target 문구·source·criteria를 바꾸면 기존 `(targetId,targetVersion,targetSha256)`를 덮어쓰지
  않고 새 `targetVersion`과 digest를 추가한다. 과거 release의 target은 삭제하지 않는다.
- owner Codex(S12-BE), reviewer Claude의 계약 검토와 generated schema gate가 필요하다.
- criterion 축소·삭제, owner 변경, registry 비우기는 운영 override가 아니라 계약 변경이다.
- 배포는 registry file의 Git blob SHA-1과 file SHA-256, `registryVersion`을 함께 pin한다.
  파일 부재, 빈 target, unknown schema/version, blob/hash drift는 resolver prerequisite 부재로
  `SYS-0003/503/retryable=false`다. caller가 같은 target text를 보내 복구할 수 없다.
- decision의 `acceptanceIdRef`와 target의 `acceptanceIdRef`, 카드 187 policy registry의
  `requiredCriteria[]`가 exact match해야 한다. registry에 없는 target/ref는 final row를 만들지 않는다.

## 2. Evidence identity

### 2-1. digest 대상

Evidence identity는 stored row 전체 의미를 고정한다. `input_sha256`·`output_ref` 중 하나만 해시하거나
caller payload를 다시 해시하지 않는다. digest v1의 입력 object는 아래 exact key set이다.

`schemaVersion,evidenceId,recordedAt,tenantId,runId,stepId,traceId,actorType,actorId,action,`
`policyId,effect,approvalId,inputSchema,inputSha256,outputSchema,outputRef,result,telemetry,componentVersions`

- `schemaVersion`은 `evidence-envelope-digest:1`이다.
- `recordedAt`은 UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`로 정규화하며 **digest에 포함**한다. 이것은
  partition routing 값인 동시에 기본키 일부다. partition table 이름은 포함하지 않는다.
- NULL은 JSON `null`; UUID/InvId/TraceId는 각 SQL `::text` cast 결과를 쓴다. `recorded_at`은
  `to_char(recorded_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`로 만들고 session
  `TimeZone`에 의존하지 않는다. JSONB 두 필드는 저장된 JSONB 값을 쓴다. 비밀 원문을 새로 읽거나
  digest payload를 API에 노출하지 않는다.
- 직렬화는 PostgreSQL **16**의 `jsonb_build_object(...)::text`다. v1은 PostgreSQL의 JSONB object
  key 길이/byte 정렬, `", "`·`": "` separator, JSONB numeric 표기를 그대로 버전 계약에 포함한다.
  Python target canonical JSON과 같은 규칙이라고 주장하지 않는다. domain separator
  `saintvision:evidence-envelope:v1\n`과 이 text의 UTF-8 bytes를 이어 해시한다. real-PG가 만든 고정
  byte/vector를 commit하고 PG-free 시험은 그 fixture를 대조만 한다. DB major나 출력 byte가 달라지면
  digest version을 올린다.

이 정의는 서버가 가진 row를 해시하므로 caller가 `evidenceSha256`으로 identity를 선택하지 못한다.
`record_evidence()`의 기존 `canonical_sha256(input_payload)`는 계속 input identity일 뿐 envelope
identity가 아니다(`src/saintvision/services/evidence.py:23-42`, `:62-101`).

### 2-2. migration `0058` 설계

1. partition parent `public.evidence_envelopes`에 nullable `envelope_sha256 char(64)`와 lowercase
   hex CHECK를 추가한다. 기존 partition에도 parent column이 전파되는지 real-PG로 확인한다.
2. `BEFORE INSERT`의 `SECURITY INVOKER` trigger function이 **NEW의 모든 stored field를 위의 exact
   SQL 식으로 inline 직렬화하고 digest를 계산해 caller 값을 항상 덮어쓴다**. INSERT 권한 외에 별도
   digest 함수 EXECUTE가 필요하지 않게 한다. 검증·backfill용
   `public.evidence_envelope_digest_v1(...)`은 owner만 실행하고 PUBLIC·`inv_app` EXECUTE를 revoke한다.
   두 함수 모두 `search_path=pg_catalog`을 고정하고 object 이름은 schema-qualified하며 dynamic SQL을 쓰지 않는다. definition hash를
   migration/ontology gate에 고정한다. hosted 시험은 `SET ROLE inv_app` INSERT 성공과 forged digest
   overwrite를 함께 단언한다.
3. `(tenant_id,evidence_id,recorded_at)` 조회 index를 추가한다. resolver는 tenant GUC가 설정된
   RLS transaction 안에서 이 exact key로만 읽는다.
4. 새 append-only `public.release_evidence_bindings`를 둔다. key는
   `(tenant_id,release_id,evidence_id,evidence_recorded_at)`이고 `project_id`, server-derived
   `envelope_sha256`, `bound_at`을 가진다. release·project·evidence FK, tenant RLS/FORCE RLS,
   `inv_app` SELECT/INSERT만 허용한다. INSERT trigger는 Evidence의 Run→Workload project를 다시
   도출해 `project_id`와 같음을 요구하고, digest를 Evidence row에서 복사한다. caller digest·project는
   authoritative 값이 아니다.
5. binding producer owner는 카드 190 구현의 `release acceptance evidence binder`다. producer는
   release manifest와 source Evidence를 같은 transaction에서 읽고, Run→Workload project를 재도출한
   뒤 binding을 만든다. 기존 row를 운영자가 임의 연결하는 generic HTTP route는 만들지 않는다.
   기존 증거는 exact source artifact/provenance를 검증하는 importer만 연결할 수 있다.
6. proposer가 유효한 ref를 발견하는 read surface
   `GET /v1/release-manifests/{release_id}/acceptance-evidence?acceptanceIdRef=...`를 구현 카드가 추가한다.
   서명 검증된 fresh human principal과 live `releases.accept`를 매 page 요청에서 재확인한다. caller가
   project를 고르지 않으며 server-owned release binding이 Run→Workload project를 결속한다.
   `ReleaseAcceptanceEvidenceDiscoveryPageResponse`가 release·criterion·policy/target pin,
   `targets[1..64]`, server-derived Evidence `items[1..100]`, opaque `nextCursor`, literal
   `scopeVerified=true`를 반환하고 telemetry·actor·project를 노출하지 않는다. binder/route가 배포되지
   않았거나 binding이 하나도 없으면 빈 page나 per-row 404가 아니라 prerequisite
   `SYS-0003/503/false`다. `observedAt`은 수집 시각이 아니라 Evidence 기본키의 `recorded_at`을 UTC
   microseconds로 직렬화한 값이다.

### 2-3. legacy backfill

- 기존 row의 NULL `envelope_sha256`을 0, 빈 문자열, `input_sha256`, `output_ref` hash로 채우지 않는다.
- 지원하는 retained partition만 DB 함수로 batch 재계산하고, `(partition, rowCount, min/max
  recordedAt, beforeNullCount, afterNullCount, digestFunctionHash, sourceHeadSha)` receipt를 남긴다.
- complete stored fields, digest fixed vector, clean source SHA를 검증한 row만 backfill한다. expired/dropped
  partition과 incomplete row는 영구 `UNRESOLVED_LEGACY`다. resolver는 이를 PASS나 빈 measurement로
  바꾸지 않는다.
- 전 partition backfill·receipt 검토 전에는 column NOT NULL로 바꾸지 않는다. 새 INSERT는 trigger가
  non-NULL을 보장한다. NOT NULL 전환은 별도 migration과 rollback 계획이다.

## 3. resolver 계약과 권한 경계

### 3-1. 입력과 순서

resolver는 외부 route가 아니라 decision writer가 호출하는 server service다. **ledger 전**에는 배포에
pin된 registry가 유효하고 migration·resolver·binder가 설치됐다는 prerequisite만 확인하며 caller ref를
resolve하지 않는다. ref resolve는 #282 §4의 lock 순서 안에서 수행한다.
입력은 verified principal의 `tenant_id`, path의 `release_id`, policy에서 고른 `acceptance_id_ref`,
Pydantic으로 검증한 target/measurement refs다. 순서는 다음과 같다.

1. #282 순서대로 idempotency ledger와
   `(tenant_id,release_id,acceptance_id_ref)` criterion coordination slot을 먼저 잠근다.
2. release를 같은 tenant로 exact 조회하고, 배포·release manifest에 pin된 policy registry와 target
   registry Git blob SHA-1/file SHA-256/version을 검증한다. 없으면 존재 비노출 404다.
3. #282 §4 단계 6에서 target ref마다 registry row를 server-side 조회해 target
   ID·digest·criterion을 exact 비교한다.
4. measurement ref의 `observedAt`을 UTC로 정규화하고 **Evidence `recorded_at`과 exact match**시켜
   partition key로 사용한다.
5. `release_evidence_bindings`를 통해 release·tenant·project 귀속을 확인하고 Evidence row의 stored
   `envelope_sha256`을 constant-time 비교한다. binding의 project와 Run→Workload project도 final
   transaction에서 재확인한다.
6. #282 §4 단계 8, final write 직전에 target·Evidence·binding·policy pin을 한 번 더 exact resolve한다.
   하나라도 실패하면 결과를 만들지 않는다. 모두 성공할 때만
   `ReleaseAcceptanceReferenceResolutionResponse(allResolved=true,scopeVerified=true)`를 decision
   service에 넘긴다. raw Evidence telemetry·actor ID·project ID는 응답/오류/audit에 싣지 않는다.

target registry는 tenant 공통 선언이지만 Evidence는 tenant+release+project binding이다. 다른 tenant,
다른 release, binding 없는 project의 같은 `evidenceId`는 존재하지 않는 것과 같은 표면이다. RLS를
우회하는 owner/admin session으로 resolver를 실행하지 않는다.

### 3-2. 오류 표면

| 조건 | 정본 ProblemDetails |
|---|---|
| malformed body, naive `observedAt`, upper/malformed digest, duplicate ref | `VAL-0003 / 422 / false` |
| target registry/resolver/migration 부재, registry empty/invalid/unpinned, digest function unavailable, legacy digest NULL | `SYS-0003 / 503 / false` |
| release/Evidence/binding이 없거나 다른 tenant·release·project | `RES-0004 / 404 / false` |
| accessible target/Evidence의 version/hash/time이 caller ref와 drift | `GRAPH-0003 / 409 / false` |
| DB lock/deadlock/statement timeout | `RES-0007 / 503 / true` |

404와 409 detail은 ID·hash·tenant·project·존재 여부를 echo하지 않는다. resolver prerequisite 실패는
fixed detail `Release acceptance prerequisites are unavailable.`을 유지한다. ref mismatch는 receipt,
proposal, vote, acceptance, success audit를 쓰지 않는다.

## 4. 공개 계약

- `ReleaseAcceptanceTargetRegistryResponse`는 checked-in registry의 strict shape다. 공개 JSON file을
  읽는 계약이며 새 HTTP route가 아니다.
- `ReleaseAcceptanceReferenceResolutionResponse`는 service→decision writer DTO의 공개 schema다.
  `releaseId`·`acceptanceIdRef`, policy registry version/file SHA-256, target registry version/Git blob
  SHA-1/file SHA-256를 포함해 어느 release·criterion·policy pin의 결과인지 고정한다.
  targets·measurements는 각각 1..64, ID unique, digest lowercase hex, aware timestamp이고
  `allResolved`·`scopeVerified`는 literal true다. partial/false branch는 존재하지 않는다.
- `ReleaseAcceptanceEvidenceDiscoveryPageResponse`는 위 GET route의 공개 schema다. page 상한은 100,
  target 상한은 64이며, `nextCursor` 외 caller-selected scope는 없다. top-level `acceptanceIdRef`와 모든
  target의 ref가 exact match해야 한다.
- policy registry v1을 `Literal[1]`로 고정한 것은 의도다. policyVersion이 증가하면 새 schema version과
  generated contract review가 필요하며 구 계약이 새 policy를 조용히 해석하지 않는다.
- 공개 response는 target/evidence의 identity만 담고 Evidence actor/telemetry, binding project,
  caller fallback 값은 담지 않는다.
- generated files는 `tools/export_schemas.py`로만 만들며 손 편집하지 않는다.

## 5. 구현 시험과 변이 표

### 5-1. PG-free

1. checked-in registry loader가 duplicate key·implicit whitespace trim을 거부하고, nonempty,
   unique target/version·criterion, exact target digest를 검증한다.
2. source commit:path가 recorded blob을 resolve; registry source·target text drift는 digest mismatch.
3. 빈 registry, unknown version/owner(전체/target), duplicate/extra key, non-NFC string, uppercase·63자
   digest 거부.
4. resolution의 partial list, false scope/allResolved, naive time, duplicate refs, caller fallback key 거부.
   top-level/target `acceptanceIdRef` drift와 discovery page의 빈 items·false scope·caller project도 거부.
5. real-PG에서 commit한 fixed Evidence serialization byte/digest vector를 PG-free에서 대조한다.
   timestamp timezone·microseconds, NULL, JSONB key order, array order, UUID cast, telemetry 한 byte
   변화마다 예상 digest를 검증한다.
6. error mapping이 raw ID/hash/tenant/project를 echo하지 않음.

### 5-2. hosted real-PG (`run-core`)

1. migration 0058 forward/downgrade/forward, 기존 partition 열 전파, `SET ROLE inv_app` INSERT 성공,
   trigger overwrite, direct digest helper EXECUTE 거부.
   trigger가 저장한 `envelope_sha256 == owner helper(same row)`를 exact 비교해 신규 INSERT와 backfill
   직렬화가 갈라지는 변이를 거부한다.
2. 같은 semantic row의 JSONB key 순서 차이는 같은 digest; recorded_at/tenant/run/telemetry 한 필드
   변화는 다른 digest.
3. tenant A release가 tenant B evidence를 resolve 못함; 같은 tenant 다른 project/release binding도 404.
4. binding insert의 forged project/digest 거부와 Run→Workload final recheck.
5. digest NULL legacy row는 SYS-0003, batch backfill 뒤 exact resolve; input_sha256 fallback 변이는 실패.
6. Evidence insert와 binding/decision rollback 원자성, lock timeout의 정본 RES-0007.

### 5-3. 되살림 변이

| 변이 | 죽이는 단언 |
|---|---|
| registry missing/empty를 no targets PASS로 처리 | prerequisite SYS-0003, decision row 0 |
| target hash를 caller 값끼리 비교 | registry target mutation에서 GRAPH-0003 |
| `input_sha256`을 envelope digest로 사용 | fixed vector·fallback 부정 시험 |
| digest에서 `recorded_at` 또는 tenant 제외 | timestamp/tenant 단독 변이 digest 변화 |
| digest trigger가 caller 값을 보존 | forged digest INSERT 뒤 stored digest 재계산 |
| Evidence ID만 조회해 최신 partition 선택 | observedAt mismatch 409, exact partition key 단언 |
| release/project binding 생략 | 다른 release/project 404 |
| owner/BYPASSRLS resolver 사용 | 실행 role·row_security 부정 시험 |
| legacy NULL을 0/빈 hash로 통과 | unresolved legacy SYS-0003 |
| partial resolution을 반환 | literal true + list length/unique contract 거부 |
| 404에 caller ID/hash echo | redaction exact-key 시험 |
| ref resolve를 ledger/lock 전에 수행하거나 final 재검증 생략 | 단계 6/8 사이 binding·digest drift 경합 시험 |
| resolution DTO에서 release/criterion/policy pin 제거 | required key·lowercase digest schema 단언 |

## 6. 착수/롤백 조건

Claude 구현 카드는 예약된 `0058`로 target registry loader → digest migration/backfill dry-run →
binder/read surface → binding/resolver → 카드 187 decision writer 결속 순으로 간다. 모든 focused/real-PG gate와 독립 검토가
끝나기 전 write flag는 off다. migration rollback은 resolver/write flag를 먼저 off하고 binding
trigger/table·digest trigger/function/index·column을 역순 제거한다. 이미 기록된 acceptance가 새 resolver
없이 재검증될 수 없으므로 운영 data가 생긴 뒤 downgrade는 금지하고 restore 계획을 요구한다.

이번 카드의 판정은 **계약 준비**다. 실제 resolver, backfill receipt, hosted PG evidence, 사람 인수는
모두 `NOT_OBSERVED`다.
