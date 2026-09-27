---
doc_id: "SPEC-CORE-CX01-DISPOSABLE-001"
title: "Core CX01 hosted disposable container 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T06:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["Core", "CX01", "Docker", "recovery", "CI"]
---

# Core CX01 hosted disposable container 설계

## 목표와 불변식

hosted Core에서 `CX01_CONTAINER is unset`으로 setup 단계에서 멈춘 recovery drill 19건을
실제 시험 본문으로 전환한다. mock이나 identity 단언 완화 없이, 해당 job이 직접 만든
PostgreSQL 16 컨테이너만 `CX01_CONTAINER`와 `INV_TEST_ADMIN_DSN`으로 공급한다. 로컬·옛 PC
보호 컨테이너와 다른 프로젝트 컨테이너는 검색하거나 사용하지 않는다.

Core job은 기존 암묵적 service container 대신 이름에 run ID/attempt를 넣은 컨테이너를
명시적으로 만든다. `ai.saintvision.kernel-test`와 `ai.saintvision.cx01` 값은 같은 고유
run owner 문자열이어야 하며, 데이터는 tmpfs, host bind는 loopback 5432 하나뿐이다.
health가 `healthy`가 된 뒤에만 컨테이너 ID와 DSN을 `$GITHUB_ENV`로 넘긴다. 기존
`resolve_owned_postgres_container`는 Docker inspect와 owner label 검증을 그대로 수행한다.
host pytest는 loopback publish를 쓰고, default bridge의 candidate container에는 같은 owned
CX01을 inspect한 bridge IP만 전달한다. host bind를 전체 인터페이스로 넓히거나 bridge
gateway의 host publish를 추측하지 않는다.

## 생명주기와 실패 경계

1. checkout/setup/dependency 설치 뒤 `Create disposable CX01 PostgreSQL` step이 고유 이름,
   run owner label, tmpfs, 메모리 상한, healthcheck로 컨테이너를 만든다.
2. 생성 직후 inspect로 정확한 이름·두 owner label·running/healthy를 재검증한다. ID는
   job workspace의 고정 receipt 파일에도 기록한다.
3. migration·focused lanes·전체 Core pytest는 같은 loopback DSN을 사용한다. recovery
   fixture는 receipt의 정확한 컨테이너만 stop/start하며 source DB와 container identity가
   일치한다.
4. 마지막 `Cleanup disposable CX01 PostgreSQL` step은 `if: always()`다. receipt ID의
   owner label과 이름을 다시 확인한 뒤 그 ID 하나만 `docker rm -f -v`하고, inspect 실패로
   제거를 확인한다. label/name 불일치면 다른 자원을 지우지 않고 job을 실패시킨다.

Core JUnit의 기존 CX01 unset 19-count skip 기대값은 제거한다. 새 body-level skip이나
failure가 나오면 성공으로 바꾸지 않고 JUnit의 실제 이유를 분류하며, 플랫폼 공통 사유라면
backend/core 양쪽 exact map을 함께 갱신한다. 합격 증거는 hosted run ID, head SHA,
`core-tests.xml`의 recovery case별 passed/skipped/failed 수, 전체 skip Counter, cleanup step
success다. 로컬은 workflow 정적 경계 시험과 recovery prerequisite 단일 파일까지만 실행한다.
