---
doc_id: "CREDENTIAL-MIGRATION-ERROR-BOUNDARY-20260919-CODEX"
title: "credential provisioning 및 LAN migration 예외 경계 수정"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-19T02:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# credential provisioning 및 LAN migration 예외 경계 수정

## 범위

Claude가 인계한 `tools/provision_credentials.py` catch-all과 `tools/plan_lan_migration.py` CLI 오류 경계를 수정했다. DSN, SQL, credential 파일 내용은 출력하지 않는다.

## 변경

- `provision_credentials.py`
  - 의도된 `ProvisioningDenied`는 denial로 유지한다.
  - `psycopg.Error`는 안전한 `credential_provisioning_database_error`와 5자리 sqlstate만 보고한다.
  - `TypeError/KeyError/AttributeError` 및 기타 예기치 않은 오류는 `credential_provisioning_internal_error`와 오류 타입만 보고하며 denial로 위장하지 않는다.
  - 기존 missing DSN/manifest 거부의 exit 2 호환성을 유지하고, DB 오류는 exit 3, 내부 오류는 exit 4로 구분한다.

- `plan_lan_migration.py`
  - DB/driver 오류는 `migration_metadata_database_error`와 안전한 sqlstate로 구분한다.
  - 잘못된 migration metadata는 `migration_metadata_refused`로 유지한다.
  - fetchone shape 오류 등 내부 오류는 `migration_metadata_internal_error`, exit 4로 구분한다. pending 결과의 exit 1은 유지한다.
  - migration plan은 여전히 read-only이며 apply 권한을 만들지 않는다.

호출자 조사 결과 `provision_credentials.provision`은 CLI와 credential integration 시험에서 사용되고, `plan_lan_migration.gap_plan`은 `rehearse_lan_upgrade.py`와 core 시험에서 사용된다. 새 예외 타입은 기존 성공/거부 반환 구조를 바꾸지 않고 실패 분류만 세분화한다.

## 검증

`.venv/Scripts/python.exe -m pytest -q tests/core/test_credential_provision_cli.py tests/core/test_lan_migration_plan.py` → **22 passed / 1 skipped**. skip은 `INV_TEST_ADMIN_DSN` 부재에 따른 실제 PostgreSQL 시험 미실행이다.

DB 오류·의도된 거부·TypeError·RuntimeError를 합성 주입해 category와 exit를 확인했다. 구현 원복 후 동일 신규 종료 코드 시험 6건은 모두 실패했다(기존 catch-all/일반 unavailable 메시지로 분류가 사라짐). 실제 PostgreSQL provisioning/migration 실행은 하지 않았다.

## 공통 종료 코드 계약

두 CLI의 공통 규칙은 `0=성공`, `1=정상 업무 결과(마이그레이션 pending)`, `2=의도된 거부`, `3=DB/driver 오류`, `4=예기치 않은 내부 결함`이다. 같은 JSON 라벨은 항상 같은 종료 코드를 내며, TypeError와 RuntimeError는 모두 내부 결함 코드 4를 낸다.
