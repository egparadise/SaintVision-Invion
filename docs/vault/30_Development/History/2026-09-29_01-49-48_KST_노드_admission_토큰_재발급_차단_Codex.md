---
doc_id: "HIST-CODEX-NODE-ADMISSION-REISSUE-GUARD-001"
title: "노드 admission bootstrap token 재발급 차단"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T01:49:48+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["security", "identity", "discovery", "bootstrap-token", "card-122"]
---

# 노드 admission bootstrap token 재발급 차단

## 결론

Claude 카드 122 감사의 High finding을 수용했다. `POST /v1/discovery/candidates/{announcement_id}/admission`은 announcement를 잠그지 않고 상태를 `candidate`로 유지한 채 매 호출마다 새 bootstrap token을 만들었으므로, 응답 유실 재시도나 동시 요청이 같은 후보에 유효 token을 둘 이상 발급할 수 있었다.

평문 token은 최초 응답 뒤 저장하지 않는 보안 불변식 때문에 기존 token 재제시는 불가능하다. 따라서 announcement row를 `FOR UPDATE`로 잠그고, 최초 발급 때 이미 기록되는 `admitted_by_user_id`를 단일 발급 marker로 사용한다. marker가 있으면 새 token·audit을 만들기 전에 `GRAPH-INVALID-TRANSITION`/409/non-retryable로 닫는다. candidate 상태는 실제 enrollment 완료 전까지 유지하므로 “발급됨”과 “가입 완료”를 혼동하지 않는다.

## 회귀 증거

- PG-free 단일 파일 `tests/core/test_discovery_admission_replay.py`: 잠금 존재, 두 호출 중 발급 함수 1회, 두 번째 409를 검증한다.
- 실 PG `tests/test_pools.py`: 같은 candidate의 순차 재호출 뒤 미소비 bootstrap token이 정확히 1개임을 검증한다.
- HTTP+PG `tests/integration/test_discovery_machine_credentials.py`: 첫 요청 201, 두 번째 요청 409, 오류 body에 token 없음, DB 미소비 token 1개를 검증한다.
- 로컬은 PG DSN이 없어 PG-free `1 passed`, compile exit 0만 실행했다. 실 PG 두 경로는 hosted Core `run-core`에서 실행하며 실행 전까지 미측정이다.

## 카드 122 Medium 분리

- pool member 추가·삭제와 plan 생성의 live project 권한 누락은 같은 보안 인계의 후속 카드로 유지한다. pool→project와 run→project를 한 트랜잭션에서 함께 결속하지 않고 route에 단순 조회만 추가하면 TOCTOU와 cross-project plan 공백을 남기므로 이 High hotfix에 섞지 않았다.
- unique `IntegrityError`의 500 번역은 제약별 공개 409 매핑이 필요하다. 전역 handler로 모든 무결성 오류를 409로 낮추면 실제 서버 결함까지 공개 충돌로 오분류하므로 후속에서 route별 constraint allowlist로 처리한다.
- legacy audit 중복·선택적 `Idempotency-Key` 소비도 response replay 계약과 ledger 원자성 설계가 필요한 별도 후속이다.

S04-DB/S08-DB collector 카드 123은 이 보안 hotfix 리뷰 요청 뒤 재개한다.
