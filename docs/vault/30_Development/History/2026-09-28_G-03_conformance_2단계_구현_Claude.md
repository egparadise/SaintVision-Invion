---
doc_id: "HIST-CLAUDE-G03-CONFORMANCE-STAGE2-IMPL-001"
title: "G-03 2단계 구현 — conformance 실행 기록 저장(0055)·RECORDED branch·fixture 생산자·host 결속"
version: "1.0.1"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T23:17:05+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-03", "conformance", "migration", "adapter", "api", "claude"]
---

# G-03 2단계 구현 (카드 103)

설계 #218 v1.2(head `56106eac`, Codex 승인) 그대로. base는 #215 head `3bdc6e70`이고, 먼저 #218 head를 해소만으로 merge(`772c6fcc`, 충돌은 진행 현황·작업 현황 두 docs)한 뒤 그 위에 구현했다. migration 번호 **0055**는 조정자 배정(`down_revision = 0054_model_version_measurements`). 코디네이터 보충(Codex 카드 105 W5): 읽기 route의 권한 preflight·기록 읽기와 생산자의 쓰기를 **`bounded_lock_wait` span**으로 감쌌다.

## 1. 들어간 것

- **migration `0055_adapter_conformance_records`** — table `adapter_conformance_records`: `record_id`(cfr_ULID PK)·`host_id uuid NOT NULL`·`adapter`·`contract_version`·`suite_contract_version`·`subject`·`provenance`·counts 4·`checks jsonb`·`recorded_at`·`created_at`·`version`. CHECK 5종(`subject = 'fixture-adapter'`, `provenance = 'in-server'`, counts ≥ 0, `passed+failed+skipped = total`, `jsonb_array_length(checks) = total`), index `(host_id, adapter, recorded_at DESC, record_id DESC)`, `GRANT SELECT, INSERT TO inv_app`. **`tenant_id` 없음·RLS 없음**(설계 §2-1(c), Codex 승인), `source_ref` 없음. 온라인 upgrade는 같은 이름 table의 column·constraint·index·privilege·RLS shape를 대조해 다르면 거부(0052–0054 방식). downgrade는 기록 행이 있으면 거부, 없으면 DROP(0054와 같은 guard) → AC-11 manifest **PRESERVED**, reversible tail `[0053, 0054, 0055]`.
- **ORM** `db/models/conformance.py::AdapterConformanceRecord` + `APPEND_ONLY_TABLES` 등록(`TENANT_SCOPED_TABLES`에는 넣지 않음), `CONFORMANCE_SUBJECTS`/`CONFORMANCE_PROVENANCES` 단일값 tuple, `ids.PREFIXES["conformance_record"] = "cfr"`.
- **host 결속** `Settings.control_plane_host_id: uuid.UUID | None` ← `INV_CONTROL_PLANE_HOST_ID`, `parse_control_plane_host_id()`는 **canonical 소문자 hyphen UUID 정규식만** 통과(대문자·공백·brace·urn·32hex·hostname·IP·경로 전부 거부, 메시지에 값 미포함). dataclass는 str도 거부.
- **생산자** `services/conformance_records.py::record_fixture_conformance(session, *, adapter, host_id, now)` — `adapter`는 `agents.BY_NAME` 이름 allowlist(선택은 아님), 측정 대상은 항상 `adapters/reference.py::ReferenceAdapter`(제품 in-memory fixture), `credential_ref`는 `conformance://dummy` 외 거부, counts는 report의 checks에서 **재계산**하고 `failed`는 유도, `checks`는 `name/passed/skipped`만(skipped는 `passed=False`로 저장해 둘 다 true 불가), 쓰기 전 reader와 같은 `validate_outcomes()`를 통과. **운영 명령** `tools/record_fixture_conformance.py`(`Settings.from_env()` 실패·host 부재 → exit 2 값 비출력; 쓰기 tx는 `bounded_lock_wait` 1 span, 55P03/40P01 → exit 3 + 고정 문장, 그 외 OperationalError는 전파).
- **읽기** `latest_records(session, host_id, adapters)`는 `DISTINCT ON (adapter) … ORDER BY adapter, recorded_at DESC, record_id DESC`(index 순서와 동일), 행마다 `to_recorded()`가 §2-8 불변식(키 집합·bool·둘 다 true·이름/순서 = CHECKLIST·suite version·counts 재대조·subject/provenance/adapter allowlist·aware recorded_at)을 검사해 `StoredRecordInvalid`(규칙 이름만, row 내용 없음).
- **route** `conformance_status.py`: 목록 `GET /projects/{p}/adapters/conformance` → `Annotated[Union[ConformanceStatusResponse, ConformanceStatusRecordedResponse], discriminator=status]`(기록 0 → 1단계 7키 그대로, `reason`만 새 문장; 기록 ≥1 → `records[]`는 `adapters` 순서·미기록 adapter 부재·`latestRecordedAt` = max). 단건 `GET /projects/{p}/adapters/{name}/conformance` → `AdapterConformanceNotObservedResponse` / `AdapterConformanceRecordedResponse`; `BY_NAME` 밖 → `RES-0004` 404 고정 detail(이름 비echo, denial 아님). host 미설정 → `SYS-0002` 500 `retryable:false` 고정 문장; 깨진 row → `SYS-0002` 500 `retryable:false` 고정 문장. **두 span**: membership preflight와 기록 읽기가 각각 `make_session_factory` → `session.begin()` → `tenant_scope` + `bounded_lock_wait`(`get_session` 의존 제거). module 코드는 `run_conformance`·생산자·adapter class를 참조하지 않는다(AST 시험).
- **schemas** `ConformanceCheckOutcome`(둘 다 true 거부)·`ConformanceRecordItem`·`ConformanceStatusRecordedResponse`(중복/순서/subset/latest 검증)·`AdapterConformanceNotObservedResponse`·`AdapterConformanceRecordedResponse`(counts↔outcomes 재대조), `subject`/`provenance`는 Literal 단일값. 계약 파일 3개 신규, `conformance-status-response.schema.json`은 **바이트 무변경**. union alias는 `Strict`가 아니라 export 대상이 아니다.
- `tests/core/test_lock_wait.py` ratchet에 `conformance_status` 추가(span 2 = bounded 2, 사본 없음).

## 2. 판단한 것

- **downgrade guard**: 설계 §2-7은 "table drop으로 가역"이라고만 적었는데, 행이 있는 상태의 drop은 관측 기록 파기라 0054와 같은 **행 존재 시 거부**를 넣었다. 빈 table은 그대로 drop되므로 가역이고 AC-11 분류는 PRESERVED다. Codex 확인 요청.
- **`host_id` column 형은 `TenantId` annotation 재사용**(uuid 형만 빌림, tenant 아님 — 주석으로 명시). 별 annotation을 만들지 않았다.
- skipped check의 저장값은 `passed=False, skipped=True`. suite의 `Check`는 skipped를 `passed=True`로 표기하는데 그것은 `conformant` 계산용 관례라 §2-8 "둘 다 true 불가"를 지키려면 저장 시 접어야 했다. counts는 영향 없다(`passed`는 원래 `passed and not skipped`).
- 읽기 route도 두 span으로 바꾸면서 tenant scope를 두 span 모두에 두었다(기록 table은 RLS 없음이라 필요 없지만 membership 조회는 필요하고, 한 모양이 ratchet에 맞다).
- **FE 파괴 지점**(설계 §4-4): `NOT_OBSERVED_REASON`이 `"No conformance run is recorded for this host and these adapters."`로 바뀌었고 #208 head `0f0d82df`의 `apps/web/tests/model-lineage.test.ts:665`가 1단계 문장을 byte로 고정하고 있다. `apps/web`는 건드리지 않았다(Gemini 후속 카드). 목록 응답의 `status`가 `RECORDED`일 수 있게 된 것도 FE가 discriminated union으로 받아야 한다.

## 3. 검증 (실제 수행한 것만)

로컬(공유 venv 3.14, PG 없음, 단일 파일): `tests/core/test_conformance_status_route.py` + `tests/core/test_conformance_records.py` + `tests/core/test_lock_wait.py` + `tests/test_migrations.py` + `tests/test_ac11_migration_rehearsal.py` + `tests/core/test_conformance_checklist_ratchet.py` + `tests/test_adapters.py` + `tests/core/test_adapters_route.py` + `tests/core/test_audit_action.py` **326 passed / 0 failed**. 실 PG 파일 2개 **40 collected**(fixture guard가 PG-free에서 seed·tampering shape를 미리 검사) — 실 PG는 **NOT_OBSERVED**, hosted 인용은 PR 코멘트. `tools/export_schemas.py`로 계약 3개 생성, `migration_graph.py --head` = `0055_adapter_conformance_records`. 게이트 결과는 커밋 전 §4에 기록.

### 3-1. hosted 1차 (head `dd4adf40`) — 실패 1종, 수정
Backend 36432549781: 3.12/3.14 각 **25 failed / 4476 passed / 50 skipped / 2 deselected**, Core 36432550254 core failure. 25건 전부 한 원인 — 0055가 alembic head가 됐는데 `tools/definer-policy.json`의 `revision`과 head를 고정한 시험 4곳(`test_eval_suite_project_scope_migration.py`, `test_model_version_measurements_migration.py` ×2, `test_object_store_locator_migration.py` ×2)이 `0054`를 가리켜 definer audit이 `migration_revision_mismatch`를 내고(`test_definer_audit.py` 20건, `test_account_integration.py`의 disposable migration 검증), head 단언 4건이 깨졌다. **새 conformance 실 PG 시험 40건은 실패 목록에 없다(통과).** 수정: policy `revision` → `0055_adapter_conformance_records`(0055는 definer function을 추가하지 않으므로 항목 무변경), 시험 4곳을 0055로 옮기고 0054는 `down_revision` 단언으로 유지. 로컬 5파일 211 passed.

## 4. 다음

1. 게이트 chain → push → PR(base `agent/claude/g04-w3-verify-route`, `run-core`) → hosted Backend/Core 인용 → Codex 검토.
2. Gemini 후속 카드: `NOT_OBSERVED_REASON` fixture·RECORDED union FE.
3. #213·#215 head가 바뀌면 이 branch에 다시 merge(해소만).
