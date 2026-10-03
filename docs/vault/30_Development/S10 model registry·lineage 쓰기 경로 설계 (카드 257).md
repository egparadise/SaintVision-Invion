---
doc_id: "DESIGN-CARD257-S10-MODEL-REGISTRY-LINEAGE-WRITE"
title: "카드 257 — S10 model registry·lineage: 읽기는 이미 있다. 없는 것은 계보를 만드는 제품 경로다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T10:21:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "694217b0"
task_ids: ["S10-DB", "S10-ST"]
tags: ["s10-db", "s10-st", "lineage", "model-registry", "design", "vf-cl", "claude"]
---

# 카드 257 — S10 model registry·lineage 쓰기 경로 설계 (측정 먼저, 구현 0줄)

## 0. 결론 먼저

**읽기 축은 이미 있다.** 계보 추적 route 둘, 표 여덟 개, 불변 version·보존 pin·검증·release route가 전부 제품에 있고 `S10-DB`·`S10-ST`·`S10-BE`·`S10-FE` 네 행은 **이미 75**다(48 task 재산정 v1.15). 그러니 이 카드는 "없으니 만든다"가 아니다.

**측정으로 나온 공백은 하나의 모양이다 — 계보의 subject를 만드는 제품 경로가 없다.** `register_dataset_version`·`register_commit`·`register_image`·`record_deployment` 네 service 함수는 **제품 호출자가 0건**이고 시험만 부른다. 그리고 공개 등록 route는 `producedByRunId`와 `lineage`를 **의도적으로 받지 않는데**, 그 docstring이 적은 두 선행 조건 중 **하나는 이 tree에서 이미 해소됐다**.

외부 전제(실 Provider CLI 인수 `G-25`, 배포 digest 운영 인수 `G-23`) 없이 닫을 수 있는 것은 **셋**이고, 그 셋은 모두 "기록을 만드는 쓰기 경로"다. 점수를 올리는 것은 이 카드의 목표가 아니다 — 네 행의 100은 외부 인수이고, 이 설계는 **그 인수가 가능해지는 자리**를 만든다.

## 1. 측정 — train 36 후보 `694217b0`에서 무엇이 있는가

전부 이 worktree에서 읽었다. 실행한 것은 route 열거(라우터 객체)와 caller 집계이고, 나머지는 정독이다.

### 1-1. 표 — 여덟 개가 이미 있다

`src/saintvision/db/models/lineage.py` 하나에 계보 사슬 전체가 있다.

| 표 | 자리 | 무엇 |
|---|---|---|
| `datasets` | `src/saintvision/db/models/lineage.py:46` | 데이터셋 정체 |
| `dataset_versions` | `:76` | 내용 digest로 고정된 판 |
| `code_commits` | `:121` | 학습 코드 |
| `container_images` | `:156` | 실행 image |
| `models` | `:177` | 모델 정체 |
| `model_versions` | `:204` | **불변 version** — `content_sha256`·`byte_size`·`uri`·`stage`·`verified_at`·`verified_measurement_id`·`retention_pinned_until`·`produced_by_run_id` |
| `model_lineage` | `:274` | **간선** — `kind IN ('dataset_version','code_commit','container_image','eval_run','approval')`, `relation`, `recorded_at` |
| `deployments` | `:306` | **배포 digest** — `deployed_digest`가 AC-10이 말하는 "나간 내용 그 자체" |

평가 축도 있다 — `eval_suites`·`eval_cases`·`eval_runs`·`eval_results`(`src/saintvision/db/models/evaluation.py:52`·`:86`·`:129`·`:174`), release 축도 있다(`release_manifests` `src/saintvision/db/models/operations_pilot.py:229`, `release_acceptance_*` `src/saintvision/db/models/release_acceptance.py:85` 이하, `release_evidence_bindings` `src/saintvision/db/models/release_evidence.py:19`), MLflow 미러도 있다(`src/saintvision/db/models/tracking.py:110`·`:161`·`:225`).

### 1-2. route — 일곱 개가 이미 제품에 있다

`src/saintvision/api/v1/projects.py:61-70`이 일곱 모듈을 `register(router)`로 붙인다(데코레이터가 아니라 `add_api_route`를 쓰는 이유는 `lineage_query.py:267-274`가 적는다 — `BusinessDispatch`가 `projects.router.routes`를 읽으므로 중첩 `include_router`는 lazy placeholder만 남긴다).

| route | 모듈 |
|---|---|
| `POST /v1/projects/{project_id}/models/{model_id}/versions` | `src/saintvision/api/v1/model_versions.py` |
| `POST …/versions/{version}/verify` | `src/saintvision/api/v1/model_verify.py` |
| `POST …/versions/{version}/retention-pin` | `src/saintvision/api/v1/model_retention.py` |
| `POST …/versions/{version}/release` | `src/saintvision/api/v1/model_release.py` |
| `GET …/versions/{version}/lineage` | `src/saintvision/api/v1/lineage_query.py` |
| `GET /v1/projects/{project_id}/lineage/dataset-versions/by-digest/{content_sha256}/model-versions` | 같은 모듈 (역추적) |
| `POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs` | `src/saintvision/api/v1/eval_runs.py` |

### 1-3. 시험 — 열넷 이상이 이미 있다

`tests/test_lineage.py` · `tests/core/test_lineage_query_routes.py` · `tests/core/test_model_version_register_route.py` · `tests/core/test_model_release_route.py` · `tests/core/test_model_verify_route.py` · `tests/core/test_model_retention_pin_route.py` · `tests/test_model_version_invariants_static.py` · `tests/core/test_dataset_digest_index_migration.py` · `tests/core/test_model_version_digest_scope_migration.py` · `tests/core/test_model_version_measurements_migration.py` · `tests/integration/test_lineage_query_real_pg.py` · `tests/integration/test_lineage_digest_index_real_pg.py` · `tests/integration/test_model_release_real_pg.py` · `tests/integration/test_model_retention_pin_real_pg.py`.

### 1-4. 설계 문서도 이미 있다 — 이 카드가 다시 쓰지 않는 것

| 문서 | 이 카드와의 관계 |
|---|---|
| `docs/vault/30_Development/S10-DB_lineage_조회_API_설계.md` | **읽기 API의 정본**이고 구현됐다. 그 §1-3이 "`deployments`는 `trace_model`에 없다"를, 그 §1 넷째 항목이 "`record_lineage`는 `kind`만 검사하고 subject의 존재조차 검사하지 않는다"를 **이미 적었다**. 이 카드는 그 둘을 **다시 발견하지 않고** 쓰기 쪽에서 닫는 설계만 한다 |
| `docs/vault/30_Development/S09-DB_S10-DB_S10-ST_운영_판정_기준.md` | 운영 판정 기준(카드 106 → `#222`). 기준은 있고 남은 것은 **실행**이다 |
| `docs/vault/30_Development/S10-DB AC-10 acceptance Evidence collector 설계.md` | AC-10 수락 Evidence collector 설계 |
| `docs/vault/30_Development/S10-BE MLflow 연동 설계 v1.0.md` · `S10-BE Evidence 대응표.md` · `S10-ST Model immutable version·보존 pin Evidence 대응표.md` | `S10-BE`·`S10-ST` 쪽 정본 |

## 2. 없는 것 — caller 집계 (이 카드의 측정)

제품(`src/saintvision`·`services/control-plane/src/inv`)과 시험(`tests`)에서 각 함수의 호출 지점을 세었다. 정의 줄은 제외했다.

| service 함수 | 자리 | 제품 호출자 | 시험 호출자 |
|---|---|---:|---:|
| `register_model_version` | `src/saintvision/services/lineage.py:191` | **1** (`src/saintvision/api/v1/model_versions.py:383`) | 12 |
| `record_lineage` | `:253` | **1** — 그런데 그 1은 **같은 모듈 안**(`:231`, `register_model_version`이 자기 인자를 쓸 때)이고 **모듈 밖 제품 호출자는 0** | 8 |
| `trace_model` | `:416` | 2 (`src/saintvision/api/v1/model_release.py:367`, 모듈 내부 `:389`) | 6 |
| `register_dataset_version` | `:71` | **0** | 4 |
| `register_commit` | `:107` | **0** | 6 |
| `register_image` | `:150` | **0** | 5 |
| `record_deployment` | `:527` | **0** | 20 |

**읽는 방법**: 사슬의 **읽기**와 **model version 등록**은 제품 경로가 있고, **subject를 만드는 쓰기**와 **배포 digest 기록**은 제품 경로가 없다. 그래서 `GET …/lineage`는 **아무도 만들지 않는 간선을 조회하는 route**다 — 간선은 `register_model_version`에 인자로 들어올 때만 생기고, 그 인자를 공개 route가 받지 않는다(§2-1).

### 2-1. 공개 등록 route가 두 필드를 받지 않는 이유 — 그리고 **하나는 이미 해소됐다**

`src/saintvision/api/v1/model_versions.py:29-43`이 스스로 적는다.

* `produced_by_run_id` — "foreign key가 없으므로 결속되지 않은 값은 **다른 project의 run에 이 version을 붙인다** — 거짓 provenance 주장이다. 그것을 결속하려면 `project_scope.run_in_project`(PR 1 of 8, `#184`)가 필요한데 **이 branch에는 없다**(base가 `#175`로 고정)."
* `lineage` — "간선은 `record_lineage`가 쓰는데 그 함수는 **subject 행이 존재하는지 검사하지 않는다**. 여기서 노출하면 **아무것도 가리키지 않는 간선**을 쓸 수 있고 `trace_model`은 그 version을 subject가 없는 kind로 traceable하다고 보고한다."

**측정**: `run_in_project`는 **이 tree에 있다** — `src/saintvision/api/v1/project_scope.py:29`이고, `(project, run)`을 **workload를 거쳐** 한 `Run` 행으로 풀며 아니면 404다. 이미 `src/saintvision/api/v1/run_records.py:93`·`:111`과 `src/saintvision/api/v1/context_bundles.py:131`이 쓴다. 즉 docstring이 적은 선행 조건 중 **첫 번째는 더 이상 없다.** 두 번째(subject 존재 검사)는 **여전히 참**이다.

그리고 FK의 대상도 이 앱 안에 있다 — `runs`는 `src/saintvision/db/models/execution.py:170`, `workloads`는 `:141`이다. 즉 `produced_by_run_id`의 결속은 **외부 전제가 아니라 migration 하나와 route 한 줄**의 문제다.

## 3. 48 task 재산정 v1.15에서 이 행들

`docs/vault/30_Development/2026-09-28 48 task 진행률 재채점.md`의 §3 표와 v1.15(§4-12) 기준이다.

| 행 | scope | 점수 | 막는 자리 | 종류 |
|---|---|---:|---|---|
| `S10-DB` | Dataset/commit/image/model lineage | **75** | 배포 digest **운영 인수**(카드 106·`G-23`) | 외부 |
| `S10-ST` | Model immutable version·보존 pin | **75** | 보존 pin·측정의 **운영 판정 실행**(기준은 `#222`로 닫혔다) | 외부 |
| `S10-BE` | 두 Provider adapter·MLflow·승인 배포 | **75** | **실 Provider adapter·실 로그인 계정 CLI 인수**(`G-25`) | 외부 |
| `S10-FE` | AI 도구·실험·모델·배포 화면 | **75** | 실 provider conformance 표시 | 외부 (Gemini) |

**그래서 이 카드는 점수를 올리지 않는다.** 네 행 모두 75이고 100을 막는 것은 전부 외부 인수다. 이 설계가 바꾸는 것은 **그 인수가 가능해지는 자리** 하나다 — 배포 digest를 운영에서 인수하려면 먼저 **배포 digest를 기록하는 제품 경로**가 있어야 하고(§2 측정: 0건), 계보를 인수하려면 **계보를 만드는 제품 경로**가 있어야 한다.

## 4. 설계안 — 외부 전제 없이 닫히는 셋 (구현 0줄, 이 PR은 이 문서만)

### 4-1. (ㄱ) `producedByRunId`를 공개 등록 route에서 받고 **project 안의 run에 결속**한다

| 무엇 | 확정 |
|---|---|
| 입력 | `POST /v1/projects/{project_id}/models/{model_id}/versions`의 요청에 `producedByRunId`(optional) 하나를 더한다. **다른 필드는 더하지 않는다** |
| 결속 | handler가 `src/saintvision/api/v1/project_scope.py:29 run_in_project(session, tenant_id=…, project_id=<경로>, run_id=<요청>)`로 푼다 — 그 함수가 workload를 거쳐 project 소속을 확인하고 아니면 `RES-0004` 404(`NO_SUCH_RUN`)다. **거짓 provenance는 그 404로 끝난다** |
| 잠금 순서 | 기존 route의 순서를 바꾸지 않는다 — 이 조회는 `register_model_version` **앞**, idempotency 잠금 **뒤**에 둔다(기존 두 span 구조는 `model_versions.py`가 적는 그대로 유지) |
| DB | §4-4의 migration `0064`가 복합 FK를 더한다. **FK가 있어도 route의 검사는 남는다** — FK는 tenant 안의 존재만 보장하고 project 소속은 보장하지 않는다 |

### 4-2. (ㄴ) `record_lineage`에 **subject 존재·소유 검사**를 넣고, 그 뒤에만 `lineage`를 공개한다

| 무엇 | 확정 |
|---|---|
| 검사 | `kind`별로 subject 행을 **같은 tenant 안에서** 조회한다 — `dataset_version`→`dataset_versions`, `code_commit`→`code_commits`, `container_image`→`container_images`, `eval_run`→`eval_runs`, `approval`→ 승인 축의 정본 표. 없으면 **거부**다 |
| project 소유 | 읽기 설계(`S10-DB_lineage_조회_API_설계.md` §5)가 이미 정한 규칙을 **쓰기에서 그대로 쓴다** — 소유를 증명할 수 없는 subject는 **쓰기 시점에 거부**한다. `container_images`에 `project_id`가 **없다**는 그 문서의 측정이 여전히 참이므로, 그 kind는 **tenant 소유까지만** 검사하고 그 한계를 거부 사유에 넣지 않는다(존재 oracle 금지) |
| 거부 코드 | 없는 subject는 `RES-0004` 404(기존 `legacy_not_found_problem` 경로), kind 밖 값은 계약이 먼저 거부한다 |
| 공개 순서 | **(ㄴ)이 먼저 들어가고 그 다음에** 요청의 `lineage`를 받는다. 역순으로 하면 dangling 간선이 생기고, 그것은 읽기 설계가 "없는 간선보다 나쁘다"고 적은 상태다 |

### 4-3. (ㄷ) **배포 digest 기록 route** 하나 — 기록은 제품, 인수는 외부

| 무엇 | 확정 |
|---|---|
| route | `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments` 하나. 몸체는 `environment`·`deployedDigest`·`imageId`(optional)·`approvalId`이고 **서버가 version을 경로에서 결속**한다 |
| 권위 | `deployedDigest`는 **호출자가 주는 값이 아니라** release가 승인한 digest와 **대조**된다 — `release_acceptance_*`와 `release_evidence_bindings`가 이미 그 승인 사슬을 든다. 불일치는 `GRAPH-0002` 409다("하나를 승인하고 다른 것을 같은 version 이름으로 내보내는 것"을 `deployments` docstring이 금지한다) |
| 읽기 | `trace_model`에 `deployments`를 **더하지 않는다** — 읽기 설계 §1-3이 그 부재를 의도로 적었으므로, 더할지는 **그 문서의 owner 결정**이고 이 카드의 범위가 아니다. 대신 이 route의 응답이 기록된 행을 그대로 돌려준다 |
| 외부 경계 | **실제 배포를 수행하는 것은 이 설계가 아니다.** `G-23`(배포 digest 운영 인수)은 그대로 외부에 남는다 — 이 route는 그 인수가 기록할 자리를 만든다 |

### 4-4. migration `0064` 예약 — `produced_by_run_id`의 복합 FK

| 무엇 | 확정 |
|---|---|
| 번호 | **`0064`** (`0062` = `#348` 카드 253, `0063` = `#351` 카드 255) |
| 내용 | `model_versions`에 `(tenant_id, produced_by_run_id)` → `runs(tenant_id, run_id)` **복합 FK** 하나. 열은 **이미 있다**(`src/saintvision/db/models/lineage.py` `produced_by_run_id`, nullable) — **열을 더하지 않는다** |
| nullable | 유지한다. run에서 나오지 않은 version(가져온 가중치)이 있고, NULL은 "주장하지 않음"이다 |
| 정책·GRANT | **건드리지 않는다.** 표를 더하지 않으므로 census(160)와 definer(15)도 그대로다 — `0062`에서 같은 성질을 측정으로 확인했다 |
| downgrade | FK 하나를 떨어뜨린다. `0063`이 세운 규칙(값을 가진 행이 있으면 거부)은 **여기에 필요하지 않다** — FK를 떨어뜨려도 열과 값이 남으므로 **잃는 것이 없다**. 그 이유를 migration이 적는다 |
| revision 식별자 | **32자 이하**로 짓는다 — `alembic_version.version_num`이 `varchar(32)`이고 `#351`이 34자로 그 벽에 부딪혔다(카드 255 r1에서 실 DB로 재현했다) |

## 5. 시험 계획

| # | 시험 | 종류 | 무엇을 거부하게 하는가 |
|---|---|---|---|
| T1 | 요청 계약에 `producedByRunId`만 더해지고 `lineage`는 **(ㄴ) 전에는 없다** | PG 없음 | 순서 위반 |
| T2 | 다른 project의 run id는 `RES-0004` 404이고 **version이 생기지 않는다** | 실 PG | 거짓 provenance |
| T3 | 같은 project의 run id는 201이고 `produced_by_run_id`가 그 값이다 | 실 PG | 결속 누락 |
| T4 | `0064` 적용 뒤 **없는 run id로 직접 INSERT가 FK로 거부**된다 | 실 PG | 앱만의 검사 |
| T5 | `0064` **downgrade 왕복**: FK만 사라지고 열·값·정책·`relforcerowsecurity`가 불변 | 실 PG | 가역성 |
| T6 | 없는 subject를 가리키는 간선은 **거부**되고 `model_lineage`에 행이 0이다 (다섯 kind 각각) | 실 PG | dangling 간선 |
| T7 | 다른 tenant의 subject를 가리키는 간선도 **같은 거부**이고 메시지가 둘을 구별하지 않는다 | 실 PG | 존재 oracle |
| T8 | `container_image` kind는 tenant까지만 검사한다는 **그 한계가 시험으로 적힌다**(없는 project 검사를 통과한 것처럼 적지 않는다) | 실 PG | 과장된 주장 |
| T9 | 배포 digest가 승인된 digest와 다르면 `GRAPH-0002` 409이고 `deployments`에 행이 0이다 | 실 PG | 승인 우회 |
| T10 | 같은 (version, environment, digest)에 같은 key로 두 번 → 행 1개·ledger 1개 | 실 PG | exactly-once |
| T11 | 기존 route·시험 **무회귀** — `GET …/lineage` 응답 shape과 역추적 정렬이 그대로 | 기존 | 회귀 |
| T12 | `trace_model`은 **여전히 `deployments`를 보고하지 않는다**(§4-3의 경계를 시험으로 고정) | PG 없음 | 범위 확장 |

## 6. 이 카드가 하지 않는 것

* **점수를 올리지 않는다.** 네 S10 행은 75이고 100을 막는 것은 외부 인수다(§3).
* **실제 배포도, 실 Provider 인수도 하지 않는다**(`G-23`·`G-25`).
* **읽기 API를 다시 설계하지 않는다** — 정본은 `S10-DB_lineage_조회_API_설계.md`다.
* **`trace_model`에 `deployments`를 더하지 않는다**(§4-3).
* **MLflow 미러를 건드리지 않는다** — `S10-BE`의 정본 설계가 따로 있다.
* **구현 0줄.** 이 PR은 이 문서뿐이고, 구현은 승인 뒤 별도 카드다.
