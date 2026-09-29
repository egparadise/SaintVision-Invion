---
doc_id: "HIST-CLAUDE-S10DB-LINEAGE-QUERY-IMPL-001"
title: "S10-DB lineage 조회 API 구현 — 순방향 trace와 dataset digest 역조회, fail-closed unresolved, PG-free 36 + 실 PG 6 시험 (인덱스 migration은 별 PR)"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T12:41:18+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-DB"]
tags: ["s10-db", "lineage", "query-api", "problem-details", "implementation", "claude"]
---

# S10-DB lineage 조회 API 구현

승인된 설계 `#158` v1.2(head `40d75ae7`)를 그대로 구현했다. **`#167`(VF-CL-03) 위에 stack**했고 base는 그 브랜치다 — 공유 `api/problem.py`와 `strict_json_object`·`read_bounded_body`가 거기서 오므로 병합 순서는 `#167` → 이 PR이다. 로컬 실 PG·Docker·전체 suite는 돌리지 않았다.

## 1. 착지한 것

| 파일 | 내용 |
|---|---|
| `src/saintvision/services/lineage.py` | `trace_model_for_project()`, `models_from_dataset_digest()`, `ARRAY_LIMIT`, `DETAILED_KINDS`, `COUNT_ONLY_KINDS`, `_bounded()` |
| `src/saintvision/api/v1/lineage_query.py` (신규) | 읽기 route 2개, query 경계, path→row 결속 |
| `src/saintvision/api/schemas.py` | `ModelLineageTraceResponse`, `ModelVersionByDatasetDigestPageResponse` + 중첩 3타입 |
| `src/saintvision/api/v1/projects.py` | `lineage_query.register(router)` 한 줄 |
| `contracts/model-lineage-trace-response.schema.json`, `contracts/model-version-by-dataset-digest-page-response.schema.json` | `export_schemas.py` 생성물 |
| `tests/core/test_lineage_query_routes.py` (신규) | 설계 §10의 PG-free 부정 시험 + 실 PG fixture guard, 37 test |
| `tests/integration/test_lineage_query_real_pg.py` (신규) | 설계 §10-30~34·37 실 PG 6 node |

`trace_model`은 **바꾸지 않았다** — `release_model_version`이 그 `missing`을 쓰고 있고, 읽기 route의 권한 경계를 내부 승격 경로에 강요하면 승격이 더 느슨해지거나 더 엄격해진다.

## 2. 설계의 핵심 결정을 코드로 옮긴 방식

- **`trace_model_for_project()`는 필터가 아니다.** 상세를 낼 수 없는 kind(`code_commit`·`container_image`·`eval_run`·`approval`)는 **행을 조회하지 않고** edge 수만 센다. "적재한 뒤 걸러내기"는 필터 한 줄이 빠지면 바로 유출되고 로그·traceback에도 닿는다. 시험이 발행된 SQL 문자열에 그 네 테이블 이름이 **없음**을 단언한다.
- **`unresolved`는 이유를 구분하지 않는다.** subject 부재 / 다른 project 소유 / project 컬럼 없는 kind가 **같은 `{kind, count}`** 로 합쳐진다. 구분하면 식별자를 숨겨도 "그 id는 실재하고 남의 것"을 확인해 주는 **존재 oracle**이 된다. 시험이 "다른 project subject fixture"와 "부재 subject fixture"의 반환값이 **완전히 동일**함을 단언한다.
- **`traceabilityLimitedByScope`**: `REQUIRED_KINDS` 넷 중 셋이 상세 불가이므로 `fullyTraceable`은 사실상 항상 false다. 그 false가 **기록 부실이 아니라 권한 경계** 때문임을 응답이 말한다. 이 플래그가 없으면 운영자가 고칠 것이 없는 기록을 고치러 간다.
- **역조회 SQL 불변식 둘**: (i) dataset version 집합을 먼저 200으로 자르고 `IN` 집합을 **잘린 그 집합과 정확히 같게** 두어 모든 item이 응답에 실린 dataset version으로 되짚어진다. (ii) `model_version_id` 중복 제거를 **pagination 앞에서** 한다 — 여러 dataset version이 한 model version으로 합류할 수 있어 뒤에서 하면 중복·경계 누락이 생긴다. Python 집합(`wanted`)과 SQL `DISTINCT` 둘 다 앞에 있다.
- **`unresolvedModelVersions`는 페이지와 무관하다** — 별도 `COUNT(DISTINCT)`로 전체 wanted 집합에 대해 센다. 페이지 기준으로 세면 같은 부재가 페이지마다 다시 보고된다.
- **query 경계**: 허용 key exact set(순방향 0개, 역조회 `{limit, cursor}`), `multi_items()`로 중복 key 거부, GET 본문 1바이트도 `VAL-0003`(`#167`의 공유 `read_bounded_body` + `require_absent_body`).
- **`clamp_limit`을 쓰지 않는다** — 상한 초과를 조용히 깎으므로 `limit=201`을 보낸 클라이언트가 자기 요청대로 받았다고 믿는다. 10진수 아님·1 미만·200 초과를 모두 422로 거부한다. `build_page`의 `limit+1`과 `validate_cursor`의 `is_id` 형태 검사는 재사용한다.
- **읽기라 `FOR UPDATE`가 없다.** 시험이 소스에 `with_for_update`가 없음을 단언한다.

## 3. 인덱스 migration은 별 PR이다 (v1.1)

코디네이터가 migration 순서를 하나로 고정했다 — `0047_audit_events_isolation`(#128) → `0048_object_store_locator`(#159) → `0049_mlflow_mirror`(#172) → **`0050_dataset_digest_lookup`**. 내 인덱스는 `0050`이고 `down_revision`은 `0049_mlflow_mirror`여야 하므로 #172 위에 있어야 하는데, **#172는 아직 수정 요청 상태**다. 그래서 코디네이터 권고대로 **migration만 분리해 #172 위의 작은 PR**로 올리고, 이 PR은 #167 위에 둔다.

같이 옮긴 것: `DatasetVersion`의 인덱스 선언(모델과 DB가 어긋나지 않게 migration과 같은 PR에 있어야 한다), CONCURRENTLY 구조를 읽는 PG-free 시험, 그리고 설계 §10-35(계획 관측)·§10-36(CONCURRENTLY 재시도) 실 PG 두 node. 인덱스가 이 diff에 없으므로 그 셋도 여기 있으면 안 된다.

**설계 §7의 "역조회 라우트는 이 인덱스 없이 착지하지 않는다"는 여전히 지켜야 한다.** 같은 PR이 아니라 **병합 순서**로 지킨다 — `#159 → #172 → 인덱스 PR → 이 PR`. 이 PR이 인덱스보다 먼저 병합되면 역조회 1단계가 `dataset_versions` 전체 스캔이 되므로, 그 순서를 PR 본문과 시험 docstring에 적었다. 순서를 코드로 강제할 방법은 없다는 것도 함께 적는다.

**보고할 사실**: #172의 `0049_mlflow_mirror`는 현재 `down_revision = "0046_model_manifest_readiness"`다. #128(`0047`→`0046`)·#159(`0048`→`0047`)가 먼저 들어가면 `0046`에서 가지가 갈라져 **head가 둘**(`0048`과 `0050`)이 된다. 고정 순서대로 단일 head를 유지하려면 **#172가 `0049`를 `0048_object_store_locator` 위로 옮겨야** 한다. 내 카드로는 닫을 수 없다.

## 4. 실 PG node와 그것을 DB 없이 지키는 방법

설계 §10-30~34와 37을 `tests/integration/test_lineage_query_real_pg.py`(`pytest.mark.postgres`, 6 node)로 넣었다 — RLS 타 tenant 비가시 · grant 없는 project 403과 안쪽 404의 분리 · **교차 project subject fixture와 부재 subject fixture의 응답 동일** · 같은 digest 두 dataset version이 한 model version으로 합류 시 item 1건 · 페이지 경계 중복·누락 0(3건을 limit 2로 순회) · 양성 겸 정직성 대조(`fullyTraceable=false` + `traceabilityLimitedByScope=true`). 35(계획 관측)과 36(CONCURRENTLY 재시도)은 인덱스와 함께 별 PR로 갔다(§3).

`#167`에서 배운 것을 여기에 먼저 적용했다: 그 카드의 실 PG 6 node는 hosted에서 **fixture의 `new_id` kind 하나** 때문에 전부 죽었고 제품 단언은 하나도 돌지 않았다. DB 없이 잡히는 실패였으므로, 이 파일의 `_seed`도 **core 시험이 statement만 기록하는 stub connection으로 실행**한다(두 분기 모두: 5 kind 전체·deployment 포함, 그리고 edge 0건·교차 project dataset). id kind와 컬럼 목록이 틀리면 hosted가 아니라 그 자리에서 깨진다.

**CONCURRENTLY 재시도에서 재현하지 못하는 것**(인덱스 PR에 적었다): 진짜 INVALID index는 동시 build를 중간에 죽여야 생기고 시험이 안정적으로 만들 수 없다. 재현한 것은 **이름이 이미 점유된 상태**이고, 선행 DROP이 없으면 재시도가 실패하는 바로 그 조건이다.

## 5. 관측하지 못한 것 (정직한 경계)

- **실 PG 6건은 로컬에서 돌리지 않았다** — RLS 타 tenant 404, grant 없는 project 403과 안쪽 404의 분리, 교차 project edge fixture와 부재 fixture의 동일 응답, 같은 digest 두 dataset version의 합류, 페이지 경계, 인덱스 제거 시 계획 관측, **CONCURRENTLY 재시도**, 양성·정직성 대조. 메모리 규칙이고 근거는 hosted CI다. PG-free 세션은 서비스가 부르는 호출에만 답하는 대역이므로 증명하는 것은 **응답의 모양과 검사 순서**이고 데이터베이스의 행동이 아니다.
- **`fullyTraceable`이 사실상 항상 false**라는 한계는 설계가 결정한 대로 그대로 착지한다. AC-10 완전 추적 증명에는 후속(tenant-wide lineage 권한 또는 `project_id` backfill)이 필요하고 둘 다 범위 밖이다. 이 route를 완전 추적의 근거로 부르지 않는다.
- 쓰기 경로(`register_*`·`record_lineage`·`record_deployment`)는 여전히 HTTP로 도달할 수 없다.

## 6. 검증 증거 (실행)

- `pytest tests/core -q` → **1127 passed, 4 skipped**. 신규 파일 `tests/core/test_lineage_query_routes.py` → **36 passed**.
- `pytest tests/integration/test_lineage_query_real_pg.py` → 로컬 **6 skipped**(`INV_TEST_ADMIN_DSN` 부재). hosted 결과를 PR에 적는다.
- `python tools/export_schemas.py --check` → **PASS: 62 contract schemas**.
- `python tools/route_coverage.py --served src --served services/control-plane/src --client apps/web/src` → **0 unserved**, exit 0.
- `check_docs`·`check_doc_single_source --ratchet` → exit 0.
- 로컬 실 PG·Docker·전체 suite **미실행**.

## 7. 다음 첫 행동

Codex 독립 검토를 받는다. 실 PG 6건은 hosted 결과로 확인하고, 인덱스 PR(#172 위)이 이 PR보다 **먼저** 병합되는지 확인한다.
