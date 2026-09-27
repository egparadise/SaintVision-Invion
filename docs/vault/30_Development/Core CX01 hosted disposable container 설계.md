---
doc_id: "SPEC-CORE-CX01-DISPOSABLE-001"
title: "Core CX01 hosted disposable container 설계"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T07:55:00+09:00"
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
run owner 문자열이어야 하며, 데이터는 tmpfs, host bind는 loopback 5432 하나뿐이다. Core
전체가 공유하는 PostgreSQL이므로 컨테이너 자체의 512 MiB 상한은 두지 않고 hosted runner의
job 자원 경계 안에서 실행한다.
health가 `healthy`가 된 뒤에만 컨테이너 ID와 DSN을 `$GITHUB_ENV`로 넘긴다. 기존
`resolve_owned_postgres_container`는 Docker inspect와 owner label 검증을 그대로 수행한다.
host pytest는 loopback publish를 쓰고, default bridge의 candidate container에는 같은 owned
CX01을 inspect한 bridge IP만 전달한다. host bind를 전체 인터페이스로 넓히거나 bridge
gateway의 host publish를 추측하지 않는다.

## 생명주기와 실패 경계

1. checkout/setup/dependency 설치 뒤 `Create disposable CX01 PostgreSQL` step이 고유 이름,
   run owner label, tmpfs, healthcheck로 컨테이너를 만든다. `--cidfile`은 생성과 함께 receipt를
   남겨 이후 명령이 실패해도 always cleanup이 정확한 ID를 회수하게 한다.
2. 생성 직후 inspect로 정확한 이름·두 owner label·running/healthy를 재검증한다. ID는
   job workspace의 고정 receipt 파일에도 기록한다.
3. migration·focused lanes·전체 Core pytest는 같은 loopback DSN을 사용한다. recovery
   fixture는 receipt의 정확한 컨테이너를 inspect하고 그 안에서 dump/restore를 실행하며,
   별도 archiver 컨테이너에서도 source DB와 container identity가 일치해야 한다.
4. 마지막 `Cleanup disposable CX01 PostgreSQL` step은 `if: always()`다. receipt ID의
   owner label과 이름을 다시 확인한 뒤 그 ID 하나만 `docker rm -f -v`하고, inspect 실패로
   제거를 확인한다. label/name 불일치면 다른 자원을 지우지 않고 job을 실패시킨다.

Core JUnit의 기존 CX01 unset 19-count skip 기대값은 제거한다. recovery 파일은 전체 suite가
공유한 session DB의 선행 시험 상태와 섞이지 않도록 fresh pytest session에서 먼저 실행하고,
전체 suite에서는 중복 수집하지 않는다. 19개 CX01 의존 case 중 17개는 pass해야 하며, 별도
owned internal network의 archiver 2개는 host에서 Docker-only 이름을 해석할 수 없다는 정확한
사유로만 skip을 허용한다. standalone cleanup case까지 포함한 focused JUnit은 18 passed/2
skipped/0 failed가 기준이다. backend는 CX01을 공급하지 않으므로 기존 unset 19-count를 유지하고,
Core의 archiver 사유를 backend의 불가능한 기대값으로 추가하지 않는다. 합격 증거는 hosted run
ID, head SHA, `cx01-recovery-tests.xml`의 case별 결과, `core-tests.xml` 전체 skip Counter, cleanup
step success다. 로컬은 workflow 정적 경계 시험과 recovery prerequisite 단일 파일까지만 실행한다.
