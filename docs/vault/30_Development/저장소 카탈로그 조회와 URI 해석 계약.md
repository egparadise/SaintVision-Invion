---
doc_id: "CONTRACT-STORAGE-CATALOG-READ-001"
title: "저장소 카탈로그 조회와 URI 해석 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T15:04:02+09:00"
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
