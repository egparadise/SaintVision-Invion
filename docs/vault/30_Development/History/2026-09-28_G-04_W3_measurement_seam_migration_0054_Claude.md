---
doc_id: "HIST-CLAUDE-G04-W3-MEASUREMENT-0054-001"
title: "G-04 W3 측정 seam PR A-1 — migration 0054, kernel-owned measurement 표, verify_model_version(measurement_id 필수)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T19:39:57+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["G-04"]
tags: ["g-04", "w3", "migration", "lineage", "kernel", "claude"]
---

# G-04 W3 측정 seam PR A-1

승인된 설계(#209 v1.1) §4의 DB 결속만 착지한다. kernel의 `node-model-measure-v1` accept 경로(PR A-2)와 W3 route(PR B)는 이 위에 올린다. base는 #202 head `9c2733de`(0053) — 코디네이터가 0054를 0053 위로 확정했다.

## 1. 들어간 것

- **kernel SQL `inv/migrations/0027_model_version_measurements.sql`** — 설계 §4의 22개 열 그대로. `PRIMARY KEY (tenant_id, measurement_id)`, `UNIQUE (tenant_id, request_id)`, RLS `tenant_isolation`(`inv.tenant_id`), `REVOKE ALL … FROM PUBLIC, inv_app, inv_kernel`, `GRANT SELECT, INSERT → inv_kernel`, `GRANT SELECT → inv_app`, `immutable` trigger(0037 template). 0048이 0026을 감싸듯 alembic이 `resources.files("inv")`로 실행한다.
- **alembic `0054_model_version_measurements`** — `public.model_versions.verified_measurement_id CHAR(30) NULL`, 복합 FK `(tenant_id, verified_measurement_id) → inv.model_version_measurements`, CHECK `(verified_at IS NULL) = (verified_measurement_id IS NULL)`, `GRANT UPDATE (verified_measurement_id) ON model_versions TO inv_app`. 0052/0053 방식: catalogue 먼저 읽고 없으면 추가, 같은 모양이면 유지, 다른 모양이면 거부(표는 열 집합+정책 유무, 열은 type/width/nullability, FK는 10-tuple(match type 포함), CHECK는 `pg_get_constraintdef` 문자열+validated). **데이터 검사 먼저**: `verified_at`만 있고 결속할 measurement가 없는 행이 있으면 DDL 전에 id를 나열하고 멈춘다(자동 보정·추측 없음). downgrade는 결속된 version 또는 measurement 행이 하나라도 있으면 거부.
- **`verify_model_version(session, *, tenant_id, model_version_id, measurement_id, content_sha256, now)`** — `measurement_id` 필수(기본값 없음). RLS 아래 raw SELECT로 measurement를 읽어 version 일치·digest 일치(호출자 digest = measurement digest = 등록 digest)·byte_size(등록값이 0이 아닐 때) 대조 뒤 두 열을 한 flush로 세운다. 이미 검증된 행은 같은 measurement면 no-op, 다른 measurement면 거부.
- ORM `ModelVersion.verified_measurement_id` + CHECK 선언(convention 이름 `ck_model_versions_verified_iff_measurement`), `LIFECYCLE_UPDATE_COLUMNS["model_versions"]`에 열 추가, id kind `model_measurement → mvm`, `tools/definer-policy.json` revision 0054, head 시험 0053→0054.

## 2. 판단한 것

- **measurement → model_versions 역방향 FK를 두지 않았다.** 설계 §4는 두 UNIQUE와 public 쪽 FK·CHECK만 요구한다. 역방향 키를 두면 시험에서 kernel을 대신해 owner가 measurement를 넣는 순간(version이 app session의 미커밋 transaction 안에 있음) FK가 깨져 기존 lineage/registry/mirror 시험 11개 호출부를 모두 transaction 분할로 다시 써야 한다. 결속은 public 쪽 키와 서비스의 tenant·version·digest 대조가 강제하고, kernel은 challenge 발급 시 version 존재를 확인하며, 아무것도 결속하지 않은 measurement는 inert다. SQL 주석에 같은 이유를 적었다. Codex가 역방향 키를 요구하면 시험 분할 비용을 함께 받는다.
- **grant 누적**: 0004의 `UPDATE (stage, verified_at, retention_pinned_until)`에 0054의 `UPDATE (verified_measurement_id)`가 더해진다. `tests/test_migrations.py`의 "column-scoped UPDATE 정확히 하나" 단언을 "누적 합집합 = whitelist"로 바꿨다(DELETE 없음·무제한 UPDATE 없음은 유지).
- **시험 stand-in `tests/measurement_support.py`**: `record_measurement(owner_engine, …)`가 owner로 measurement 행을 넣는다(`two_tenants`가 tenant를 RLS 밖에서 심는 것과 같은 지위). application role로는 INSERT/UPDATE/DELETE가 거부됨을 실 PG 시험이 고정한다 — 시험이 스스로 measurement를 만들 수 있으면 seam을 증명하지 못한다.
- **digest-only 호출 경로 0개**: 시그니처 시험(`measurement_id` keyword-only·기본값 없음) + `src/`·`tests/` 전수 grep 시험(모든 `verify_model_version(` 호출이 `measurement_id=`를 넘김).

## 3. 소유권 경계 (코디네이터 확인 필요)

PR A-2(kernel `node-model-measure-v1` issue/accept + node 측 endpoint)는 kernel(`services/control-plane/src/inv`)과 **Go node-agent**(`services/node-agent/storage/sample.go`, domain `saintvision/node-storage-sample/v1`)에 걸친다. node-agent는 Claude 배정 영역이 아니므로 착수 전에 owner 결정을 받는다. 이 PR은 그 결정과 독립적으로 병합 가능하다(표와 결속만, 쓰는 코드 없음).

## 4. 검증 (실제 수행한 것만)

로컬(공유 venv Python 3.14, PG 없음, 단일 파일):
- `tests/core/test_model_version_measurements_migration.py` — 33 passed / 0 failed
- `tests/core/test_object_store_locator_migration.py` — 9 passed; `tests/core/test_eval_suite_project_scope_migration.py` — 31 passed (head 0054)
- `tests/test_migrations.py`(offline render) — 26 passed
- 실 PG 파일은 `--collect-only`만: `test_model_version_measurements_real_pg.py` 25 collected, `test_lineage.py` 30, `test_model_registry.py` 14, `test_service_credentials.py` 35, `test_tracking_mirror.py` 63 (import·이름 오류 없음). **실 PG 결과는 NOT_OBSERVED** — hosted Backend 3.12/3.14가 정본이며 PR 코멘트에 run id로 인용한다.
- gate 체인(check_docs → … → migration_graph → `git diff --cached --check`) exit 0.

## 5. 다음

1. hosted Backend green 인용 → Codex 재검토 요청.
2. 코디네이터: PR A-2 owner 결정(kernel + Go node-agent).
3. PR B(W3 route, §6 3-span)는 A-2 뒤.
