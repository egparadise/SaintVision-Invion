---
doc_id: "HIST-CLAUDE-G04-W3-MEASUREMENT-0054-001"
title: "G-04 W3 측정 seam PR A-1 — migration 0054, kernel-owned measurement 표, verify_model_version(measurement_id 필수)"
version: "1.3.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T20:44:44+09:00"
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

## 2-1. R1 — Codex #213 수정 요청(348e2403)과 hosted 실패 반영

Codex F1/F2 두 건과, 같은 head의 hosted Backend 36411181371(48 failed / 51 errors)이 드러낸 세 가지 결함을 함께 고쳤다.

- **F1 kernel-table shape 검사 = 이름 목록이 아니라 전체 보안·제약 shape.** `KERNEL_SHAPE_QUERIES`가 열(이름·`format_type`·NOT NULL, 순서 포함)·제약(`pg_get_constraintdef`)·인덱스(`indexdef`)·`relrowsecurity/relforcerowsecurity`·정책(command·permissive·roles·USING·WITH CHECK)·비소유자 ACL(`aclexplode`)·trigger(이름·enabled·함수 schema/이름·`tgtype`)를 읽고 `EXPECTED_KERNEL_SHAPE`와 부분별로 대조한다. 하나라도 다르면 public 쪽 DDL 전에 `different definition (part)`로 정지. 표현식은 `normalise`(cast·괄호·공백·대소문자 제거)로 양쪽을 같은 철자로 만든다 — 렌더링 차이는 무시, 연산자·이름·리터럴 차이는 잡는다. PG-free 되살림 30건(RLS 해제/미강제, `USING/WITH CHECK true`, SELECT-only·restrictive·role 축소·정책 없음·둘째 정책, trigger 삭제/disable/다른 함수/UPDATE만, inv_app INSERT/SELECT·PUBLIC SELECT·inv_kernel UPDATE/DELETE·ACL 없음, PK/UNIQUE 삭제, digest CHECK 삭제/완화, byte_size integer, sha256 nullable, 열 누락/추가/순서, 인덱스 누락, UNIQUE 인덱스 강등) + 실 PG 13건(같은 부류를 실제 ALTER/GRANT/DROP으로 만들고 재실행 정지·public 열 미생성·복구 뒤 수렴).
- **F2 byte_size 항상 대조.** `row.byte_size and …` sentinel 제거. 등록 0 + 측정 1 → 거부(실 PG 되살림: `(verified_at, verified_measurement_id)`가 `(NULL, NULL)` 유지), 등록 0 + 측정 0 → 검증.
- **CHECK 이름 이중 접두.** alembic이 명시 이름에도 naming convention을 적용해 `ck_model_versions_ck_model_versions_…`가 만들어졌고, 재개 검사가 자기 제약을 못 찾아 중복 생성으로 실패했다. `op.f(CHECK)`로 이름을 최종 고정; 실 PG 시험이 이름을 단언한다.
- **application role의 kernel schema 접근.** inv_app에는 `USAGE ON SCHEMA inv`가 없어 서비스의 직접 SELECT가 `permission denied for schema inv`였다. schema USAGE를 주는 대신(kernel schema 전체가 열린다) 0044 `model_registry_snapshot` 모양의 tenant-bound `SECURITY DEFINER` reader `public.model_version_measurement(text)`를 두고 inv_app에 EXECUTE만 준다. kernel SQL의 `GRANT SELECT … TO inv_app`은 삭제 — application은 표를 **이름조차 못 댄다**(실 PG: SELECT/INSERT/UPDATE/DELETE 모두 permission denied). reader의 `pg_get_functiondef` 렌더링을 `reader_definition()`으로 재현해 `tools/definer-policy.json`의 `definitionSHA256`을 오프라인 계산했고(0044 항목의 해시를 같은 렌더러로 재현해 검증), 재개 시 정의가 byte-identical하지 않으면 거부한다. 설계 §4의 "application SELECT만"보다 좁다 — 코디네이터·Codex 확인 요청.
- **직접 `verified_at`를 심던 시험 seed 4곳**(`test_model_release_real_pg._seed`, `test_lineage_query_real_pg._seed`, `test_model_registry_binding.registered`, `test_model_registry_runtime`)이 CHECK iff에 걸렸다. `measurement_support`에 connection-level `insert_measurement`/psycopg용 `insert_measurement_psycopg`를 추가해 seed가 measurement를 먼저 심고 `verified_measurement_id`를 함께 넣는다. RLS evidence collector의 `unmeasured=1`(inv_app 권한은 있는데 schema 접근이 없어 identity 검증 불가)은 inv_app 권한 자체가 사라져 해소.

## 2-2. R2 — Codex 재검토(ccb35a87)와 hosted 36414777597 반영

- **expected shape에 `channel_version >= 1` CHECK가 빠져 있었다**(Codex R2-1). 실 PG는 정확히 그 한 항목만 다르다고 답했고(다른 13개 제약·인덱스·정책 렌더링은 normalise 뒤 일치), 재개 거부 → 시험 `finally`의 재실행도 거부 → `verified_measurement_id` 없는 DB가 남아 이후 126건이 연쇄 실패했다. 항목을 추가하고, kernel SQL의 CREATE TABLE 본문에서 CHECK/PK/UNIQUE를 독립적으로 파싱해 expected 'c/p/u' 집합과 1:1임을 고정하는 PG-free 시험을 뒀다(stand-in이 expected를 되돌려 주는 구조로는 잡히지 않던 drift).
- **owner shape**(Codex R2-2): `owner` 부분을 추가 — `(owner ∉ {inv_app, inv_kernel}, pg_has_role(inv_app, owner), pg_has_role(inv_kernel, owner)) == (True, False, False)`; reader에도 같은 검사(`READER_OWNER`). PG-free 되살림 4+4, 실 PG: `OWNER TO inv_app`·owner role membership 부여·reader `OWNER TO inv_app` 각각 public DDL 전 거부·복구 뒤 수렴. definer audit의 `runtime_can_assume_function_owner`는 `tests/integration/test_definer_audit.py::test_runtime_must_not_assume_function_owner`가 hosted에서 실행한다.
- 실 PG `trigger-disabled` 변이는 `tests/test_db_integrity_static.py`가 helper 밖 raw `DISABLE TRIGGER`를 금지해 삭제(PG-free 'D' 상태·실 PG trigger 삭제가 남는다). downgrade 시험에 전제(revision 0054·행 ≥1·열 존재) 단언 추가. seed에 measurement 2문(GUC·INSERT)이 늘어 PG-free seed 카운트 시험 3곳(15→17, 7→9, 18→20)과 INSERT-only 테이블 집합 필터를 갱신.

## 2-3. AC-11 fixture manifest — #177 카드 90 head(da112daf) merge + 0054 분류

코디네이터 규칙(새 migration PR은 같은 PR에서 AC-11 fixture manifest를 갱신). #177 head `da112daf`("classify migrations through 0053")를 해소만으로 merge(충돌 0)하고 `docs/vault/30_Development/Evidence/s11-migration-fixture-manifest-v0.json`에 `0054_model_version_measurements → PRESERVED`를 추가했다. 근거는 migration 원문: `downgrade()`는 결속된 version 또는 measurement 행이 하나라도 있으면 거부하고, 없을 때만 빈 CHECK·FK·열·reader·표를 내린다 — 어느 쪽도 데이터를 잃지 않는다(0053과 같은 부류). `tools/migration_graph.py`는 0054를 reversible로 분류하고(`downgrade_body_kind`도 `reversible`), reversible tail은 `[0053, 0054]`가 되어 `tests/test_ac11_migration_rehearsal.py`의 tail·PRESERVED 단언을 그에 맞게 늘렸다. 로컬: `test_ac11_migration_rehearsal.py` 21 passed.

## 3. 소유권 경계 (코디네이터 확인 필요)

PR A-2(kernel `node-model-measure-v1` issue/accept + node 측 endpoint)는 kernel(`services/control-plane/src/inv`)과 **Go node-agent**(`services/node-agent/storage/sample.go`, domain `saintvision/node-storage-sample/v1`)에 걸친다. node-agent는 Claude 배정 영역이 아니므로 착수 전에 owner 결정을 받는다. 이 PR은 그 결정과 독립적으로 병합 가능하다(표와 결속만, 쓰는 코드 없음).

## 4. 검증 (실제 수행한 것만)

R2 head 기준 로컬(단일 파일): `test_model_version_measurements_migration.py` 77 passed / 0 failed; `test_model_release_route.py` 59; `test_lineage_query_routes.py` 36; `test_db_integrity_static.py` 14; `test_migrations.py` 26; 실 PG 파일 collect-only 44. 실 PG NOT_OBSERVED.

R1 head 기준 로컬(공유 venv 3.14, PG 없음, 단일 파일): `tests/core/test_model_version_measurements_migration.py` 68 passed / 0 failed; `tests/test_migrations.py` 26; `tests/core/test_object_store_locator_migration.py` 9; `tests/test_collect_rls_evidence.py` 17 passed / 3 skipped. 실 PG 파일 `--collect-only`: measurements 42, release 6, lineage_query 6, registry_binding 16, registry_runtime 22, test_lineage 30. 실 PG 결과 NOT_OBSERVED — hosted 인용은 PR 코멘트.

(v1.0.0 기록)

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
