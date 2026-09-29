---
doc_id: "HIST-CODEX-CARD135-LEGACY-PROBLEM-LOCK-001"
title: "카드 135 — legacy RES 404·denial audit·lock-wait Low 항목 종결"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T03:40:51+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["G-04"]
tags: ["card-135", "problem-details", "existence-nondisclosure", "lock-wait"]
---

# 카드 135 — legacy ProblemDetails·lock-wait Low 항목

## 범위와 먼저 실패한 재현

입력은 [[2026-09-29_카드122_쓰기route_idempotency_전역감사_Claude]] §4 Low 3건이다. `#241` 승인 head `77a0620f` 위에서 제품 코드보다 시험을 먼저 추가했다. 최초 focused 실행은 **10 failed, 33 passed, exit 1**이었다. legacy not-found 5종은 모두 409였고, legacy write 전용 dependency와 manual transaction bound는 없었다.

## 판정과 구현

1. `RES-NODE-NOT-FOUND`, `RES-CONTRIBUTION-NOT-FOUND`, `RES-RUN-NOT-FOUND`, `RES-WORKSPACE-NOT-FOUND`, `RES-ARTIFACT-NOT-FOUND`만 API exception boundary에서 정본 `RES-0004`/404/non-retryable, exact 10-key `ProblemDetails`, 고정 detail `No such resource.`로 변환한다. 내부 service `InvError` code는 바꾸지 않았다. 다른 `RES-*`는 의미가 모호하므로 기존 route별 상태를 유지한다.
2. 존재하는 타 tenant/project row와 실제 부재 row가 같은 공개 표면이 되며 resource 종류·내부 message·path를 내보내지 않는다. `apps/web/src/shared/api/client.ts::isRouteNotFoundError`는 404이면서 `RES-` code인 응답을 이미 “route는 존재하고 resource가 없거나 가려짐”으로 처리하므로 unsafe fallback을 열지 않는다.
3. `DENIAL_CATEGORIES` 밖이라는 감사 지적은 **변경 불필요로 닫았다**. 정본 규칙은 AUTH/SEC의 401·403만 denial audit이며 resource 404는 인증 거부가 아니다. 새 회귀 시험은 변환된 404가 audit row를 만들지 않음을 명시한다.
4. 기존 #240 storage registration 1개와 #241 optional-idempotency 7개는 각자의 bound를 유지한다. 나머지 dependency-injected write 11개는 `get_write_session`, manual route 3개(enroll, heartbeat, announcement의 두 transaction span)는 같은 `bounded_lock_wait`를 사용한다. 55P03/40P01은 값·SQL을 숨긴 `SYS-0001`/503/retryable로 끝나며 읽기 route에는 새 timeout을 적용하지 않는다. 이로써 감사표의 legacy write 22개 전부가 bounded span을 갖는다.

## FE 영향

기존 legacy not-found의 HTTP 409·resource별 legacy code·`retryable:true`가 HTTP 404·`RES-0004`·`retryable:false`로 바뀐다. FE는 이미 모든 `RES-*` 404를 application/resource 404로 분류하므로 코드 변경은 필요 없고, 오히려 존재 비노출과 route fallback 차단이 정본 계약과 같아진다. lock 경합 때 무한 대기 대신 기존 정본 `SYS-0001`/503을 받을 수 있다는 동작 변화가 있다.

## 검증

- RED: `tests/core/test_legacy_problem_details.py tests/core/test_lock_wait.py` → **10 failed, 33 passed, exit 1**.
- GREEN: 같은 두 파일 → **43 passed, exit 0**.
- 관련 PG-free 회귀(`canonical_denial_audit`, legacy idempotency, discovery admission/announcement, pool write security, storage registration security 포함) → **87 passed, exit 0**.
- write/workspace/discovery response contract 회귀 → **90 passed, exit 0**.
- 첫 hosted Backend 3.14 run `36465143025`는 제품 경로가 아니라 `test_pool_placement_response_contract.py`의 PG-free app이 옛 `get_session`만 override해 pool mutation 2건이 `app.state.engine`을 찾으면서 실패했다(**4580 passed, 50 skipped, 2 failed**). fixture가 새 `get_write_session`도 override하도록 고정했고 해당 파일은 **24 passed, exit 0**; exact-head 재실행 증거를 기다린다.
- real PostgreSQL은 로컬에서 실행하지 않았다. `tests/test_api.py`의 타 tenant node 404와 `tests/test_storage_api.py`의 unknown node 404 기대를 갱신했으며 hosted Core `run-core`에서 실행 증거를 남긴다.
- migration과 JSON Schema 변경은 없다.

## 상태

owner Codex, reviewer Claude. hosted Core와 문서·계약 gate가 green일 때까지 `review`; 사용자 병합은 별도다.
