---
doc_id: "CONTRACT-STORAGE-CATALOG-READ-001"
title: "저장소 카탈로그 조회와 URI 해석 계약"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-15T15:19:04+09:00"
source_of_truth: "Git"
---

# 저장소 카탈로그 조회와 URI 해석 계약

VF-CX-01/02 후속, VF-CL-01/02 소비 경계. ADR-010/011/031/047 및 기존 public.DataLocation/StorageContribution을 재사용한다. reviewer Claude pending.

## 정본 HTTP 표면

business=true로 구성된 saintvision.server:create_app이 기존 inv_app 제한 연결과 동일 AccessTokens→OidcPrincipalVerifier 검증을 사용한다. 미구성일 때 fixture fallback을 제공하지 않는다.

| Method / path | 결과 | 권한 |
|---|---|---|
| GET /v1/storage/contributions | 기존 ContributionResponse items/nextCursor | 현재 검증 사용자 자신이 등록한 contribution, 상태 포함 |
| GET /v1/storage/locations | 기존 DataLocationResponse items/nextCursor | 자신이 등록했고 현재 active인 contribution의 metadata |
| GET /v1/storage/resolve?uri=... | location: DataLocationResponse | 동일 소유권·active 조건으로 정확한 URI lookup |

- tenant와 user는 검증된 principal에서만 얻는다. 헤더/쿼리의 tenant·user 선언으로 바꿀 수 없다. non-owner DB role/RLS와 명시적 tenant 필터를 유지한다.
- 같은 tenant의 다른 등록자, 다른 tenant, 존재하지 않는 URI, 비활성/철회 contribution은 파일조회에 노출되지 않는다. resolve는 동일404와 일반 메시지, 목록은 빈 결과로 응답한다.
- contribution 소유자는 철회된 폴더의 상태를 조회할 수 있지만 location lookup은 차단된다. 새 요청에서 account suspension도 기존JWT에 반영한다.
- owner 필터는 새 공개 HTTP 경계에서 필수다. 내부 service의 생략 가능한 reader_user_id는 기존 유지관리호출 호환용이지 새로운 공개 인자나 권한 우회가 아니다.
- 목록은 기존 기본50/최대200과cursor를 재사용한다. contributionId·nodeId·cursor·readyOnly 등 추가필터는 소유권조건을 좁힐 뿐 대체하지 않는다.
- uri 길이1~2048, 기존 namespace grammar 사용. malformed는422, 미존재/권한없음404. 입력 URI를 오류 detail에 반사하지 않는다.
- business dispatch는 route path와HTTP method가 모두 일치할 때만 위임한다. POST/activation/DELETE는 이 조회연결로 노출하지 않는다. 기존 business app 안의 mutation을 GET path의 부분매칭으로 호출할 수 없다.

## 응답 해석과 남은 범위

location.ready/checksumSha256/verifiedAt은 카탈로그의 기록이며 이번HTTP요청이 현재바이트를 다시 읽었다는 뜻이 아니다. 다운로드URL·실행permit·새검증Evidence·물리폴더 access를 발급하지 않는다. ModelManifest→shard확장, remote materialization/write-back, 프로젝트공유/관리자전체조회, 실제브라우저여정은 별도 구현·계약·검증이다. 무검증상태를 성공값으로 채우지 않는다.

실제 검증과 담당은 [[2026-09-15_VF-STORAGE-API_Codex]] 참조. 운영migration/장비 변경 없음.


## 복제본 기록 관측 (1.1.0)

GET /v1/storage/replica-status?uri=... 는 같은 검증 사용자/tenant·자신의 active contribution 조건으로 observation을 반환한다. URI와 오류 규칙은 resolve와 동일하다. 새 service의 reader_user_id는 필수 내부 인자이며 공개 파라미터로 받지 않는다.

| observation 필드 | 의미 |
|---|---|
| locationId / locationVersion | 해당 SQL snapshot의 catalog 식별자와 버전 |
| observedAt | DB statement_timestamp. 이 SQL이 시작한 시각이며 bytes 검증 시각이 아님 |
| recordedStates | ready/transferring/stale/corrupt/evicted 각각의 저장된 행 수. 없는 상태는0 |
| totalRecords | 위 다섯 값의 합. evicted 기록도 포함하므로 현재 보유 copy 수가 아님 |
| currentAvailability | 항상 unknown. Node/실 bytes/프로젝트 실행 인가를 새로 검증하지 않음 |
| requiresExecutionRevalidation | 항상 true |

- 소유권/활성폴더 조건과 replica 집계를 단일SELECT에서 수행한다. 중간 요청으로 허가와 개수가 서로 다른 snapshot에서 합쳐지지 않는다. 이후 회수/상태변경까지 잠그거나 미래권한을 보장하지 않는다.
- DB에서 최대5개 상태행(복제본 없는 catalog는 outer join1행)을 받아 고정 크기 응답을 만든다. 전체tenant 순회/Node 후보 목록/폴더경로를 응답하지 않는다.
- 소유 catalog가 있지만 replica가 없으면200과0개다. 모르는/숨긴/철회 catalog는404다. 같은URI의 타tenant 행은 결과에 포함하지 않는다.
- ready 기록이 lost Node에 있거나 현재 bytes와 불일치할 수 있다. healthy/실행가능/복구성공으로 표시하지 않는다. 자동repair·desired 정책·materialization은 후속이다.
- 계약 산출: ReplicaObservationResponse → contracts/replica-observation-response.schema.json. business=true canonical factory에서만 제공한다.

구현/검증/인계: [[2026-09-15_VF-REPLICA-OBSERVATION_Codex]]. Gemini는 기록상 복제본 수와 현재가용성 미확인을 구분해 표시한다. Claude 독립검토와 실제브라우저/운영인수는 별도다.
