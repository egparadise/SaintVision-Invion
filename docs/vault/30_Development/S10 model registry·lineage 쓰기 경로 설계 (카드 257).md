---
doc_id: "DESIGN-CARD257-S10-MODEL-REGISTRY-LINEAGE-WRITE"
title: "카드 257 — S10 model registry·lineage: 읽기는 이미 있다. 없는 것은 계보를 만드는 제품 경로다"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T10:56:12+09:00"
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

외부 전제(실 Provider CLI 인수 `G-25`, 배포 digest 운영 인수 `G-23`) 없이 닫을 수 있는 것은 **셋**이고, 그 셋은 모두 "기록을 만드는 쓰기 경로"다. **r2에서 그 셋의 계약을 고쳤다** — subject의 project는 kind별 사슬로 증명하고 증명 못 하는 둘은 거부하며(§4-2), 배포 digest는 **호출자가 주지 않고** 기존 정본이 model version에서 파생한다(§4-3), 그 route의 권한·멱등·감사는 카드 250 계약 그대로이고(§4-3-1), `0064`는 기존 dangling 값을 **측정하고 거부**한다(§4-4). 점수를 올리는 것은 이 카드의 목표가 아니다 — 네 행의 100은 외부 인수이고, 이 설계는 **그 인수가 가능해지는 자리**를 만든다.

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

### 4-2. (ㄴ) subject의 **project를 증명하는 사슬**을 kind별로 고정한다 (r2, Codex F1)

r1의 "tenant까지만 검사"는 **틀렸다** — tenant만 보면 **같은 tenant의 다른 project** subject로 provenance를 위조할 수 있고, 그것은 읽기 정본(`docs/vault/30_Development/S10-DB_lineage_조회_API_설계.md` §5)이 이미 금지한 상태다. 그래서 schema를 다시 읽어 **kind별로 project를 증명하는 실제 사슬**을 아래 표로 고정한다. 증명할 수 없는 kind는 **쓰기에서 거부**한다(fail-closed).

| `kind` | subject 표 | 그 표에 `project_id`가 | project를 증명하는 사슬 | 쓰기 판정 |
|---|---|---|---|---|
| `dataset_version` | `dataset_versions` (`src/saintvision/db/models/lineage.py:76`) | **없다** | `dataset_versions.dataset_id` → `datasets.project_id` (`src/saintvision/db/models/lineage.py:46`, **NOT NULL**) | **증명 가능** — 그 값이 경로의 project와 같아야 한다 |
| `eval_run` | `eval_runs` (`src/saintvision/db/models/evaluation.py:129`) | **없다** | `eval_runs.suite_id` → `eval_suites.project_id` (`src/saintvision/db/models/evaluation.py:52`, **nullable** — `0053`이 더했다) | **조건부** — 값이 있으면 같아야 하고, **NULL이면 거부**(증명 불가) |
| `approval` | `approvals` (`src/saintvision/db/models/execution.py:337`) | **없다** | `approvals.run_id`(NOT NULL) → `runs.workload_id` → `workloads.project_id` (`src/saintvision/db/models/execution.py:141`, **NOT NULL**) | **증명 가능** — 세 hop을 거쳐 같아야 한다 |
| `code_commit` | `code_commits` (`src/saintvision/db/models/lineage.py:121`) | **없다** | **없다** — 그 표에는 `tenant_id`뿐이다 | **거부**(fail-closed) |
| `container_image` | `container_images` (`src/saintvision/db/models/lineage.py:156`) | **없다** | **없다** | **거부**(fail-closed) |

그리고 간선이 붙는 **model version 자신**도 같은 방식으로 경로에 결속한다 — `model_versions`에 `project_id`가 없으므로 부모 `models.project_id`(`src/saintvision/db/models/lineage.py:177`, NOT NULL)를 거친다. 그 idiom은 이미 있다: `src/saintvision/api/v1/lineage_query.py:144-167 _version_in_project`이고, 없음·다른 project·다른 tenant를 **한 가지 404**로 돌려준다. 쓰기도 그 함수를 쓴다.

| 무엇 | 확정 |
|---|---|
| 검사 지점 | `record_lineage`(`src/saintvision/services/lineage.py:253`) 안이다. route가 아니라 service에 두는 이유: 그 함수를 부르는 **모든** 경로(지금은 `register_model_version` 하나)가 같은 규칙을 받아야 한다 |
| 거부 코드 | 증명 실패·subject 없음·다른 project·다른 tenant는 **모두 같은** `RES-0004` 404 `"No such resource."`다. 네 가지를 구별하면 **존재 oracle**이 된다(읽기 설계 §5의 같은 원칙) |
| `code_commit`·`container_image` | **그래서 공개 `lineage`가 지금 받을 수 있는 kind는 세 개**(`dataset_version`·`eval_run`·`approval`)다. 나머지 둘을 받으려면 그 두 표에 project 열이 필요하고 **그것은 이 카드의 migration이 아니다** — 별 카드로 남긴다(§6). r1처럼 "tenant까지만 검사하고 한계를 시험에 적는다"로 열지 않는다 |
| 순서 | **(ㄴ)이 먼저 들어가고 그 다음에** 요청의 `lineage`를 받는다. 역순이면 dangling·교차 project 간선이 생기고, 그것은 읽기 설계가 "없는 간선보다 나쁘다"고 적은 상태다 |

### 4-3. (ㄷ) **배포 기록 route** 하나 — digest는 호출자가 주지 않는다 (r2, Codex F2)

r1은 몸체에 `deployedDigest`를 두고 "승인 digest와 대조한다"고 적었다. **그것은 기존 정본과 모순이다.** `record_deployment`(`src/saintvision/services/lineage.py:527-615`)를 다시 읽으면 권위 사슬이 이미 전부 그 안에 있다.

| 기존 함수가 이미 하는 것 | 자리 |
|---|---|
| `environment`를 `('lab','staging','pilot')`로 제한 | `:554` |
| model version을 **`FOR UPDATE`** 로 잠그고 `populate_existing` | `:558-566` |
| `stage != 'released'`면 거부 | `:569-574` |
| 승인을 **`FOR UPDATE read=True`** 로 잠금 | `:576-581` |
| `decision != 'approved'`면 거부 | `:584` |
| **반열린 유효구간** `decided_at <= now < expires_at` 아니면 거부 | `:586` |
| **`approval.subject_sha256 != version.content_sha256`면 거부** | `:588-593` |
| 같은 environment의 기존 `active` 배포를 **같은 transaction에서 `superseded`** | `:596-603` |
| `deployed_digest`를 **`version.content_sha256`에서 파생** | `:611` |

즉 **digest는 호출자가 주는 값이 아니다.** 그래서 설계를 고친다.

| 무엇 | 확정 |
|---|---|
| route | `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments` |
| 요청 몸체 | `environment`(enum `lab|staging|pilot`) · `approvalId` · `imageId`(optional). **`deployedDigest`는 없다** — `additionalProperties:false`가 보낸 것을 거부한다. `notes`도 받지 않는다(서버가 쓰는 자리이고 호출자 text를 넣을 이유가 없다) |
| 권위 | **route는 새 권위를 만들지 않는다.** 위 표의 검사는 전부 기존 함수의 것이고, route는 경로의 `(project, model, version)`을 `_version_in_project`로 풀어 `model_version_id`를 넘기는 일만 더한다 |
| 응답 | 기록된 행(`deploymentId`·`environment`·`status`·`deployedDigest`·`imageId`·`approvalId`·`deployedAt`)을 strict 계약으로 돌려준다. `deployedDigest`는 **응답에만** 있다 |
| 읽기 | `trace_model`에 `deployments`를 **더하지 않는다** — 읽기 설계 §1-3이 그 부재를 의도로 적었으므로 그 변경은 그 문서 owner의 결정이다 |
| 외부 경계 | **실제 배포를 수행하지 않는다.** 함수 docstring이 "it does not perform deployment or issue a kernel execution permit"라고 적고, `G-23`(배포 digest 운영 인수)은 그대로 외부다 |

#### 4-3-1. 그 route의 권한·동시성·멱등·감사 계약 (r2, Codex F3 — 카드 250에서 맞춘 계약 그대로)

`#345`(카드 250) §3-2-2·§3-2-3에서 Codex와 맞춘 쓰기 계약을 **그대로** 쓴다. 순서가 계약이다.

| # | 단계 | 확정 |
|---|---|---|
| 1 | 필수 key | `_require_idempotency_key`(`src/saintvision/api/v1/model_versions.py:192`)를 **edge에서** 부른다 — 없거나 `[A-Za-z0-9._:-]{1,128}` 밖이면 **`VAL-0003` 422**이고 그 앞에 아무 일도 일어나지 않는다 |
| 2 | 권한 1차 | `project_service.require_project_access`(`src/saintvision/services/projects.py:204`)를 부르고 **`canApprove` boolean을 읽는다**. 이유: 이 행은 "이 내용이 그 승인 아래 나갔다"는 **결정 등급의 진술**이고 `canRequest`로는 만들 수 없다. `effective_permission`은 archived project·suspended user에서 **예외 없이 false 셋**을 주므로 "예외가 없었다"를 승인으로 쓰지 않는다 |
| 3 | 직렬화 | `serialise_idempotent_write`를 **자원 행보다 먼저** 잡는다(그 docstring이 잠금 순서를 고정한다). 그래서 이 lane의 잠금 순서는 **key → model version 행 → 승인 행**이고 기존 함수의 두 잠금이 그 뒤에 온다 |
| 4 | 권한 2차 | **replay 판단 전에** 다시 읽는다 — 그 lock을 기다리는 동안 등급을 잃은 호출자에게 저장된 성공을 돌려주면 안 된다 |
| 5 | ledger 결속 | `replay_or_reserve`가 `(tenant, project, endpoint, key)`로 조회하고 본문을 `request_digest`로 비교한다(`src/saintvision/api/deps.py:164`). 그 본문에 **경로의 `modelId`·`version`을 함께 넣는다** — 그러지 않으면 같은 key로 **다른 version**의 저장된 응답이 replay된다. `ENDPOINT`는 식별자 없는 bounded template `"POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments"` |
| 6 | 자원 | `record_deployment`가 version을 `FOR UPDATE`, 승인을 `FOR UPDATE read=True`로 잡고 §4-3의 검사를 한다 |
| 7 | 권한 3차 | **insert 직전** 한 번 더 — 행 잠금도 대기이고 그 사이에 같은 철회가 커밋될 수 있다(카드 253에서 `T21`·`T22`로 고정한 것과 같은 이유) |
| 8 | 기록 | `store_idempotent_response` + **allow 감사 1행**(`model.deployment.record`, `target_type="deployment"`, `detail`은 `projectId`·`modelVersionId`·`environment`만 — digest와 notes는 넣지 않는다), 전부 **같은 transaction 경계** |
| 9 | 거부 감사 | `AUTH-0030` 403은 `src/saintvision/api/app.py`의 단일 recorder가 범주로 적는다. 없는 version·없는 승인은 **`RES-0004` 404**이고 카드 253의 `_absent` 방식으로 `audit_action`을 붙여 **감사된다** |
| 10 | 번역표 | route가 자기 `TRANSLATION` 표를 갖고 `AUTH_APPROVAL_DIGEST_MISMATCH`·`VAL_SCHEMA`·`RES_ARTIFACT_NOT_FOUND`·`GRAPH_IDEMPOTENCY_CONFLICT`를 공개 코드로 바꾼다. **표의 빈칸은 `SYS-0002` 500**이 되므로 **coverage 시험**을 둔다(선례: `tests/core/test_eval_run_route.py`) |

승인 digest 불일치의 **공개 코드**를 정한다 — 내부 `AUTH_APPROVAL_DIGEST_MISMATCH`는 "승인이 다른 내용에 주어졌다"는 **상태** 거부이므로 공개는 **`GRAPH-0002` 409**다(`AUTH-0030`은 호출자의 권한 이야기이고 여기서는 권한이 아니다). 없는 승인과 결정이 승인이 아닌 경우도 같은 409로 묶어 **승인 id의 존재 oracle을 만들지 않는다**.

### 4-4. migration `0064` 예약 — `produced_by_run_id`의 복합 FK와 **기존 행 경계** (r2, Codex F4)

| 무엇 | 확정 |
|---|---|
| 번호 | **`0064`** (`0062` = `#348` 카드 253, `0063` = `#351` 카드 255) |
| revision 식별자 | **32자 이하.** `alembic_version.version_num`이 `varchar(32)`이고 `#351`의 34자가 그 벽에 부딪혀 `upgrade head`가 실패하는 것을 카드 255 r1에서 실 DB로 재현했다 |
| 내용 | `model_versions`에 `(tenant_id, produced_by_run_id)` → `runs(tenant_id, run_id)` **복합 FK 하나**. 열은 **이미 있고**(nullable) 더하지 않는다 |
| FK 대상이 가능한가 | **측정했다** — `runs`에 `UniqueConstraint("tenant_id", "run_id", name="uq_runs_tenant_id_run_id")`가 있고(`src/saintvision/db/models/execution.py`), 이미 **다섯 표**가 같은 쌍을 FK로 참조한다(`src/saintvision/db/models/artifacts.py:54`, `src/saintvision/db/models/context.py:94`·`:189`, `src/saintvision/db/models/execution.py:239`·`:313`) |
| 참조 동작 | `ON UPDATE NO ACTION` · `ON DELETE NO ACTION`(제품이 만드는 기본값, `0062`에서 `a`/`a`로 실측). version이 주장하는 run을 **지울 수 없게** 되는 것이 의도다 |

**기존 행 경계 — FK는 조용히 실패할 수 있다.** 열은 FK 없이 살아왔으므로 지금 값 중 `runs`에 없는 것(**dangling**)이 있으면 `ADD CONSTRAINT`가 실패한다. 그래서 upgrade가 **먼저 측정하고, 고치지 않고 거부**한다(`0053`·`0062`·`0063`과 같은 규율이다).

```sql
-- upgrade의 첫 문장. offline(--sql) 모드에서는 건너뛴다(context.as_sql).
SELECT mv.tenant_id, mv.model_version_id, mv.produced_by_run_id
  FROM model_versions mv
  LEFT JOIN runs r
    ON r.tenant_id = mv.tenant_id AND r.run_id = mv.produced_by_run_id
 WHERE mv.produced_by_run_id IS NOT NULL
   AND r.run_id IS NULL
 ORDER BY mv.model_version_id
 LIMIT 10;
```

| 무엇 | 확정 |
|---|---|
| 행이 있으면 | **`RuntimeError`로 거부**하고 최대 10개의 `model_version_id@produced_by_run_id`를 메시지에 적는다. 그 값이 **다른 tenant의 run**을 가리키는 경우도 같은 거부다(위 조회가 `tenant_id`를 같이 묶으므로 교차 tenant는 dangling으로 나온다) |
| **자동 수정 금지** | 값을 `NULL`로 만들거나 행을 지우지 **않는다**. 그 값은 누군가 기록한 provenance 주장이고, 그것을 지우는 것은 **검토된 데이터 수정**의 일이다. 메시지가 그렇게 적는다 |
| 운영 절차 | 거부 메시지가 (ㄱ) 위 조회를 그대로 실행해 목록을 받고, (ㄴ) 잘못된 주장은 검토 뒤 `NULL`로 정정하고, (ㄷ) 다시 `upgrade`하라고 적는다 |
| downgrade | **FK 하나만 떨어뜨린다.** 열과 값이 남으므로 **잃는 것이 없고**, 그래서 `0063`이 세운 거부 규칙은 여기 **필요하지 않다** — 그 이유를 migration이 적는다 |
| 불변 | 표를 더하지 않으므로 census **160**과 definer **15**가 그대로다(`0062`에서 같은 성질을 실 DB로 확인했다). 정책·GRANT·`ENABLE`·`FORCE`도 건드리지 않는다 |

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
| T13 (r2) | **dangling `produced_by_run_id`가 있으면 `0064` upgrade가 거부**하고 FK가 생기지 않으며 행이 그대로다. 값을 정정한 뒤 같은 upgrade가 성공한다 | 실 PG | 조용한 실패·자동 수정 |
| T14 (r2) | ledger가 **경로의 `modelId`·`version`까지 결속**한다 — 같은 key로 다른 version을 부르면 저장된 응답이 아니라 **`GRAPH-0002` 409** | 실 PG | 같은 key의 교차 version replay |
| T15 (r2) | **같은 tenant 다른 project의 subject**를 가리키는 간선이 kind 셋 각각에서 거부되고 `model_lineage`에 행이 0이다. `code_commit`·`container_image`는 **project를 증명할 수 없으므로 언제나 거부**다 | 실 PG | §4-2의 provenance 위조 |
| T16 (r2) | `eval_suites.project_id`가 **NULL인 suite의 `eval_run`** 간선은 거부된다(증명 불가) | 실 PG | nullable을 통과로 읽는 것 |
| T17 (r2) | `canRequest`만 가진 주체의 배포 기록은 **`AUTH-0030` 403 + denial audit 1행**이고 `deployments`에 행이 0이다. `canApprove`는 성공한다 | 실 PG | §4-3-1의 등급 |
| T18 (r2) | 요청 계약에 **`deployedDigest`가 없고** 보내면 거부된다. 응답에는 있고 그 값이 `model_versions.content_sha256`과 같다 | PG 없음 | 호출자가 digest를 주는 것 |
| T19 (r2) | 승인 불일치 셋(없는 승인·`decision != approved`·`subject_sha256` 불일치)이 **같은 `GRAPH-0002` 409**이고 서로 구별되지 않는다 | 실 PG | 승인 id 존재 oracle |

## 6. 이 카드가 하지 않는 것

* **점수를 올리지 않는다.** 네 S10 행은 75이고 100을 막는 것은 외부 인수다(§3).
* **실제 배포도, 실 Provider 인수도 하지 않는다**(`G-23`·`G-25`).
* **읽기 API를 다시 설계하지 않는다** — 정본은 `S10-DB_lineage_조회_API_설계.md`다.
* **`trace_model`에 `deployments`를 더하지 않는다**(§4-3).
* **MLflow 미러를 건드리지 않는다** — `S10-BE`의 정본 설계가 따로 있다.
* **`code_commits`·`container_images`에 project 열을 더하지 않는다** (r2). 그 둘은 project를 증명할 수 없어 §4-2가 **거부**로 두었고, 받으려면 열과 migration이 필요하다 — **별 카드**다. 이 카드의 `0064`는 FK 하나뿐이다.
* **구현 0줄.** 이 PR은 이 문서뿐이고, 구현은 승인 뒤 별도 카드다.
