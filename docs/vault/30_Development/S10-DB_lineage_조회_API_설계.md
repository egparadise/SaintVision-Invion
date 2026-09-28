---
doc_id: "CLAUDE-S10DB-LINEAGE-QUERY-API-DESIGN-001"
title: "S10-DB lineage 조회 API 설계 — 순방향 trace와 dataset digest 역조회 (계약 변경 명시)"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:47:23+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
task_ids: ["S10-DB"]
tags: ["s10-db", "lineage", "read-api", "design", "contract-change", "index", "claude"]
---

# S10-DB lineage 조회 API 설계

S10-FE 매트릭스(#144)와 #146이 찾은 "데이터셋 해시로 역추적이 실제로 지원되지 않는다"를 닫는 읽기 전용 API 설계. **설계만이고 구현은 승인 뒤 별도 PR이다.** 실행 0건 — 아래 사실은 전부 `grep`/정독이다.

> **v1.1**: PR #152(카드 ap)에 대한 Codex 계약 검토 F-R1~F-R5의 원칙을 이 설계에도 처음부터 적용했다 — live 권한 재확인, 정본 `ProblemDetails`, strict 응답, path→row 결속, 존재 비노출 404. **v1.2**: Codex 계약 검토 F-R1~F-R5와 코디네이터 10:40·10:43 결정을 반영했다 — `container_images`에 `project_id`가 **없다**는 사실을 바로잡고(§1-4), 소유를 증명할 수 없는 subject는 **fail-closed `unresolved` 개수**로만 보고하며 `dangling`과 합쳐 **존재 oracle을 없앴고**(§5), 역조회를 distinct·안정 정렬·`limit+1`로 고정했고(§4), 공유 모듈·helper의 owner를 **#152**로 못 박았으며(§9), query 인자 경계와 `CREATE INDEX CONCURRENTLY`를 확정했다(§7·§10). v1.1에는 10:25 코디네이터 결정 2건도 처음부터 반영했다 — 정본 `ProblemDetails`는 **공유 모듈**이 내고(business `InvError`로는 `MODEL`·`SYS` category를 만들 수 없다), 요청 검증은 **FastAPI annotation이 아니라 handler의 직접 검증**으로 한다. 바뀐 절은 §2·§4·§6·§9·§10·§11이고 `updated`는 `date` 출력에서 복사했다.

## 1. 실측한 현재 상태

### 1-1. 서비스는 있고 라우트가 없다

`src/saintvision/services/lineage.py`: `register_dataset_version`(64) · `register_commit`(100) · `register_image`(143) · `register_model_version`(184) · `record_lineage`(235) · `verify_model_version`(271) · `pin_retention`(292) · `release_model_version`(308) · `trace_model`(343) · `record_deployment`(454).

`services/control-plane/src/inv/app.py`에 lineage 라우트는 **없다**. 모델 관련 읽기는 `:449` commitment · `:454` execution-manifest · `:459` resolve 셋이고, 전부 **manifest 관측**이며 **lineage가 아니다**. `src/saintvision/api/`에도 lineage 라우트가 없다. 즉 `trace_model`은 구현·시험돼 있으나 **HTTP로 도달할 수 없고**, 역조회는 **함수 자체가 없다**.

### 1-2. `trace_model`이 이미 세운 원칙 (API가 물려받아야 하는 것)

`trace_model`의 반환(`lineage.py:436-453`)은 `datasets`·`commits`·`images`·`evaluations`·`approvals`와 함께 **세 가지 정직성 필드**를 낸다.

- `missing` — `REQUIRED_KINDS`(`lineage.py:49`: `dataset_version`·`code_commit`·`eval_run`·`approval`; **`container_image`는 필수가 아니다**) 중 edge가 0건인 kind.
- `dangling` — edge는 있는데 subject 행이 없는 것. docstring이 *"a recorded edge whose subject row is gone is worse than a missing edge"*라고 적는다.
- `fullyTraceable = not missing and not dangling`.

docstring이 이유를 적어 뒀다: *"A traceback that returned only its hits would look complete for a model nobody recorded anything about."* **이 원칙을 API에서 빈 배열로 되돌리면 안 된다**(§5).

### 1-3. `deployments`는 `trace_model`에 없다

`deployments` 테이블은 `model_version_id`로 묶이지만(`lineage.py:274` 이하: `environment`·`status`·`deployed_digest`·`image_id`·`approval_id`·`deployed_by_user_id`·`deployed_at`·`superseded_at`·`notes`) `LINEAGE_KINDS`(`db/models/lineage.py:40`)에 없고 `trace_model`도 조회하지 않는다. 코디네이터가 요구한 순방향 trace에 deployment가 포함되므로 **서비스 확장이 필요하다**(§3-1).

### 1-4. project 범위가 테이블마다 다르다 — 이 설계의 핵심 제약 (v1.2에서 정정)

**v1.1의 표가 틀렸다.** `container_images`에 `project_id`가 있다고 적었으나 실제로는 없다. Codex 지적을 받아 `ContainerImage`(`db/models/lineage.py:139-166`)와 migration `0004_s10_lineage.py`의 `container_images` 컬럼(`image_id`·`tenant_id`·`repository`·`digest`·`tag`·`byte_size`·`built_at`·`recorded_at`)을 다시 읽었다 — **`project_id`가 없다.** 아래가 정정한 표다.

| 테이블 | `project_id` | 확인 위치 |
|---|---|---|
| `models` | **있음** (FK → `projects`) | `db/models/lineage.py:180`, `0004:159` |
| `datasets` | **있음** (FK → `projects`) | `db/models/lineage.py:64`, `0004:49-50` |
| `container_images` | **없음** | `db/models/lineage.py:139-166`, `0004`의 container_images 블록 |
| `code_commits` | **없음** | `db/models/lineage.py:109-137` |
| `eval_runs` | **없음** | `db/models/evaluation.py:118` 이하 |
| `approvals` | **없음** | `db/models/execution.py:337` 이하 |
| `model_versions` · `dataset_versions` · `model_lineage` · `deployments` | **없음** | `db/models/lineage.py` |

따라서:

1. **진입점 둘은 project 강제가 가능하다** — model version은 `models.project_id`로, dataset digest는 `datasets.project_id`로 **부모 join**을 통해서다. 행 컬럼 필터가 아니라 join이라는 점을 구현이 잊으면 안 된다.
2. **`LINEAGE_KINDS` 다섯 중 project 소유를 증명할 수 있는 것은 `dataset_version` 하나뿐이다.** `code_commit`·`container_image`·`eval_run`·`approval`은 부모에도 project 컬럼이 없어 **어떤 join으로도 project를 증명할 수 없다.**
3. **`deployments`는 전이적으로 증명된다** — `deployments`가 `(tenant_id, model_version_id)`로 `model_versions`를 FK 참조하고(`db/models/lineage.py:283-287`) 그 model version은 §6-4에서 path project에 이미 결속되므로, deployment는 **자기 컬럼이 아니라 결속된 부모를 통해** project 안에 있다. `dataset_version`과 다른 근거이므로 따로 적는다.
4. **교차 project edge가 기록 가능하다.** `record_lineage`(`lineage.py:243-250`)는 `kind`만 검사하고 subject의 project도 **존재 여부조차** 검사하지 않는다. 그래서 project A의 model version이 project B의 subject를 가질 수 있다.
5. **응답의 범위 표시만으로는 권한이 생기지 않는다**(Codex F-R1). "이 항목은 tenant 범위다"라고 적어 주는 것이 project A 구성원에게 tenant 내 다른 project의 `repository`·`violations`·`riskLevel`·`subjectSha256`·image digest를 읽을 권한을 주지는 않는다. v1.1은 표시로 충분하다고 읽히게 써 두었고, **그것이 결함이다.** §5가 고친다.

### 1-5. 역조회에 필요한 인덱스가 없다

- `dataset_versions.content_sha256`: `Sha256` 컬럼에 `checksum_is_lowercase` CHECK만 있고 **인덱스가 없다**(`db/models/lineage.py:77-91`의 `__table_args__`에 없고, `migrations/versions/*.py`에서 `content_sha256` 인덱스 grep **0건**).
- `model_lineage`: `Index("ix_model_lineage_subject_id", "subject_id")`가 **이미 있다**(`db/models/lineage.py:263`).

역조회 경로는 `digest → dataset_versions → model_lineage(subject_id, kind='dataset_version') → model_versions`이고, **첫 단계만 인덱스가 없다** → §7.

## 2. 계약 변경 (명시)

**새 라우트 2개 · 새 응답 타입 2개 = 계약 변경 4건. 새 오류 code는 0개다**(§9에서 정본 3개 재사용). 커널 schema·라우트·registry status 변경은 없다.

1. `GET /v1/projects/{project_id}/models/{model_id}/versions/{version}/lineage` → `ModelLineageTraceResponse`
2. `GET /v1/projects/{project_id}/lineage/dataset-versions/by-digest/{content_sha256}/model-versions` → `ModelVersionByDatasetDigestPageResponse`

두 응답 타입 모두 `additionalProperties: false`다. **어디에 선언되는지 실측으로 고친다(v1.1)**: business 응답 타입은 정본 `contracts/v1alpha1/core.schema.json`의 `$defs`가 아니라 **`src/saintvision/api/schemas.py`의 `Strict` 파생 Pydantic 클래스**다. 그 파일이 스스로 적는다 — *"these Pydantic models are the source, and `tools/export_schemas.py` emits the JSON Schema from them — one direction"*. `tools/check_response_freshness.py:32`도 `"kernel" = core.schema.json $def; "saintvision" = a schemas.py class`로 두 표면을 구분한다.

따라서 동반 산출물은 이것이다 — `schemas.py`에 `Strict` 파생 클래스 2개(`extra="forbid"`, `populate_by_name=True`), `python tools/export_schemas.py`로 `contracts/model-lineage-trace-response.schema.json`·`contracts/model-version-by-dataset-digest-page-response.schema.json` 생성, `.github/workflows/backend.yml:78`의 `export_schemas.py --check` drift 0, `tests/test_route_coverage.py` 반영. **TS/Go 생성 타입과 `generate_contracts.py`는 커널 정본 전용이라 이 카드의 산출물이 아니다** — v1.0이 적은 목록은 커널 라우트의 것이었고 여기서 철회한다. 클래스는 `exported()`가 **열거가 아니라 탐색**으로 찾으므로 목록 갱신은 없다.

**읽기 전용이다.** 두 라우트는 어떤 행도 쓰지 않으며 감사 행도 만들지 않는다(기존 읽기 라우트 관례와 같다).

경로 형태 근거: 진입점이 둘 다 project 강제 가능하므로(§1-4-1) `/v1/projects/{project_id}/` 아래 둔다. digest를 경로 변수로 두는 이유는 캐시·로그 친화이고, 64 hex 소문자 외에는 라우트 단계에서 422로 거부한다.

## 3. 순방향 trace

### 3-1. 서비스 변경

**기존 `trace_model`을 이 route가 직접 쓰지 않는다(v1.2).** 그 함수는 다섯 kind의 상세를 모두 적재하므로(`lineage.py:365-410`) route가 뒤에서 걸러내는 모양이 되고, 그것은 §5-2의 불변식(내지 않을 행은 읽지도 않는다)을 어긴다. 그래서 **새 함수 `trace_model_for_project(session, *, tenant_id, project_id, model_version_id)`** 를 둔다.

- `model_lineage` edge를 kind별로 센다.
- `dataset_version` edge의 subject만 `dataset_versions` → `datasets` join으로 적재하고 `project_id == :project`인 것만 남긴다. 나머지는 `unresolved[dataset_version]` 개수다.
- `code_commit`·`container_image`·`eval_run`·`approval`은 **subject 행을 조회하지 않고** edge 수를 그대로 `unresolved`에 넣는다.
- `deployments`를 `(tenant_id, model_version_id)`로 별도 select한다(lineage edge가 아니다, §1-3).
- `missing`은 기존 정의 그대로 `REQUIRED_KINDS` 중 edge 0건이다.

**`trace_model`은 바꾸지 않는다** — `release_model_version`이 `trace_model(...)["missing"]`을 쓰고 있고(`lineage.py:328-331`) 그 내부 호출자는 tenant 범위에서 전체를 볼 권한이 있다. 읽기 route의 경계를 내부 승격 경로에 강요하면 승격이 더 느슨해지거나 더 엄격해진다.

deployment 배열에는 **상한 200과 `truncated["deployment"]`** 를 둔다(§8, Codex F-R2). deployment는 `REQUIRED_KINDS`에 **넣지 않는다**: 배포되지 않은 released 모델은 정상이며, 배포 부재를 "추적 불가"로 부르면 `missing`의 뜻이 흐려진다. 대신 `deployments: []`는 그대로 빈 배열이 맞다 — 이것은 "기록이 없다"가 아니라 "배포된 적 없다"는 **완결된 사실**이다. `missing`/`dangling`/`outOfScope`와 구분되는 이유를 응답 설명에 적는다.

### 3-2. 응답 shape

`ModelLineageTraceResponse`(`additionalProperties: false`):

- `modelVersionId` · `version` · `stage` · `contentSha256` · `producedByRunId`
- `datasets[]` — `trace_model`의 현재 항목 shape 유지. **`commits[]`·`images[]`·`evaluations[]`·`approvals[]`는 응답에 없다**(v1.2): 빈 배열로 두면 "기록이 없다"로 읽히고, 값을 채우면 §5-2를 어긴다. 그 kind들은 `unresolved`와 `countOnlyKinds`에만 나타난다.
- `deployments[]` — `deploymentId`·`environment`·`status`·`deployedDigest`·`imageId`·`approvalId`·`deployedAt`·`supersededAt` (`deployedByUserId`·`notes`는 **넣지 않는다**: 사용자 식별자와 자유 텍스트를 lineage 읽기에 노출할 이유가 없다)
- `missing[]` · **`unresolved[]`**(`{kind, count}`, v1.2에서 `dangling`·`outOfScope`를 흡수) · `truncated{}` · `fullyTraceable` · **`traceabilityLimitedByScope`**(§5-3)
- `detailedKinds[]`와 `countOnlyKinds[]` — v1.1의 `projectScopedKinds`/`tenantScopedKinds`를 **이름과 뜻 둘 다 바꾼다**. 소비자에게 필요한 구분은 "project로 걸렸는가"가 아니라 **"상세를 받았는가, 개수만 받았는가"** 다(§5-2). `detailedKinds`는 `["dataset_version", "deployment"]`이고 `countOnlyKinds`는 나머지 넷이다.

## 4. 역조회 (dataset digest → model versions)

### 4-1. 새 서비스 함수

`models_from_dataset_digest(session, *, tenant_id, project_id, content_sha256, limit, cursor)`.

1. `content_sha256`을 소문자 64 hex로 검증(아니면 `VAL-0003` 422, §9). 대문자를 소문자로 **정규화하지 않는다** — 컬럼 CHECK가 소문자만 허용하므로 대문자 입력은 클라이언트 오류이고, 조용한 정규화는 "대소문자 무시 비교"라는 오해를 만든다.
2. `dataset_versions`를 digest로 찾고 `datasets`에 join해 `project_id = :project`인 것만 남긴다. **0건이면 404**(§6).
3. **(v1.2) 그 dataset version 집합 자체에 상한 200을 둔다** — `dataset_version_id` 오름차순으로 최대 200개만 취하고, 전체 개수를 `truncated["datasetVersionIds"]`에 적는다. 그리고 **3단계 `IN` 집합은 그 잘린 200개와 정확히 같다.** 응답에 200개만 싣고 `IN`에는 전부 넣으면 "응답에 없는 dataset version에서 나온 model version"이 섞여 근거를 대조할 수 없다(Codex F-R2).
4. 그 집합을 `model_lineage.subject_id`(`kind='dataset_version'`)로 조회한다.
5. `model_versions`를 적재하고 `models`에 join해 `project_id = :project`인 것만 남긴다. **project 밖·부재 model version은 목록에서 제외하고 개수만 `unresolvedModelVersions` 하나로 보고한다**(식별자 없음, 이유 구분 없음 — §5-1과 같은 이유다. v1.1의 `outOfScopeModelVersions`·`danglingSubjects` 두 필드를 하나로 합친다).
6. **(v1.2) SQL 불변식 고정**: project filter **뒤에** `model_version_id`로 **DISTINCT**를 취하고, `model_version_id` **오름차순 안정 정렬**한 뒤 커서(`> :cursor`)와 **`limit + 1`**(기존 `build_page`, `pagination.py:44-56`)을 적용한다. 순서가 중요하다 — 여러 dataset version이 같은 model version으로 합류할 수 있으므로(같은 model이 여러 데이터셋 버전을 썼을 때) DISTINCT를 pagination **전에** 하지 않으면 같은 item이 중복되고 커서 경계에서 누락된다. "집합"이라는 산문으로는 이 불변식이 고정되지 않는다는 지적을 받아들여 SQL 순서로 적는다.

### 4-2. 응답 shape

`ModelVersionByDatasetDigestPageResponse`(`additionalProperties: false`):

- `contentSha256`(요청 echo) · `datasetVersionIds[]`(**최대 200**, 2단계에서 project 안에 있던 것이고 3단계 `IN`과 동일 집합) · `items[]`(`modelVersionId`·`modelId`·`version`·`stage`·`contentSha256`) · `nextCursor` · **`unresolvedModelVersions`**(정수) · **`truncated{}`**(현재 키는 `datasetVersionIds` 하나) · **`complete`**(boolean)
- `unresolvedModelVersions`: 다른 project 소유이거나 행이 없는 수를 **합친 하나**다(§5-1).
- `complete`는 `unresolvedModelVersions == 0 and not truncated`일 때만 true다. `truncated`가 있으면 items가 **dataset version 전체가 아니라 앞 200개에서 나온 것**이므로 완전하지 않다.

**한 digest가 여러 dataset version에 걸릴 수 있다**(같은 바이트를 다른 dataset로 등록). 그래서 `datasetVersionIds`가 배열이고, 이것을 단일 값으로 좁히면 일부 model version이 조용히 빠진다.

## 5. 숨기지도 않고 새지도 않게 — fail-closed `unresolved` (v1.2 결정)

코디네이터 10:40 결정: 선택지 셋(별도 tenant-wide lineage 권한 / `project_id` migration·backfill / fail-closed `unresolved`) 중 **fail-closed `unresolved`** 로 간다.

### 5-1. 두 범주로 줄인다 — `dangling`과 `outOfScope`를 합친다

| 범주 | 뜻 | 응답 |
|---|---|---|
| `missing` | `REQUIRED_KINDS` 중 **edge가 0건** | kind 이름 배열 (기존 그대로) |
| **`unresolved`** (v1.2) | edge는 있으나 **이 route가 상세를 내지 않는 것 전부** | `{kind, count}` 배열 — **식별자 없음, 이유 구분 없음** |

`unresolved`에 들어가는 세 경우는 **응답에서 구분되지 않는다**:

1. subject 행이 **없다**(v1.1의 `dangling`),
2. subject 행이 있으나 **다른 project 소유**다(v1.1의 `outOfScope`),
3. subject의 kind에 **project 컬럼이 아예 없다**(`code_commit`·`container_image`·`eval_run`·`approval` — §1-4-2).

**왜 합치는가**: v1.1처럼 `dangling`과 `outOfScope`를 구분하면 식별자를 숨겨도 **"그 id는 실재하고 남의 것이다"를 확인해 주는 존재 oracle**이 된다. 호출자가 subject id를 추측해 edge를 심을 수 있는 경로가 있다면(쓰기 측은 project를 검사하지 않는다, §1-4-4) 그 oracle로 tenant 안의 다른 project 자원 존재를 열거할 수 있다. 두 범주를 한 개수로 합치면 그 채널이 닫힌다. `missing`은 남긴다 — 그것은 **우리 model version에 edge가 없다**는 사실이고 남의 것에 대해 아무 말도 하지 않는다.

### 5-2. 상세를 내는 kind는 둘뿐이다

| kind | 상세 | 근거 |
|---|---|---|
| `dataset_version` | **낸다**(project 안의 것만) | `datasets.project_id` join으로 소유 증명 |
| `deployment` | **낸다** | 결속된 model version의 자식(§1-4-3) |
| `code_commit`·`container_image`·`eval_run`·`approval` | **내지 않는다 — `unresolved` 개수만** | project를 증명할 수단이 없다 |

**구현 불변식**: 서비스는 **내지 않을 subject 행을 읽지도 않는다.** 개수는 `model_lineage` edge에서 세고, 상세는 소유가 증명된 kind에 대해서만 `SELECT`한다. "읽어서 걸러내기"는 fail-closed가 아니다 — 필터 한 줄이 빠지면 바로 유출되고, 로그·오류에 행이 실릴 수 있다. §10-3이 이것을 고정한다.

### 5-3. 정직한 결과: 이 route는 지금 AC-10 완전 추적을 증명할 수 없다

`REQUIRED_KINDS`는 `dataset_version`·`code_commit`·`eval_run`·`approval`(`lineage.py:49-55`)이고 **그중 셋이 §5-2에서 상세 불가**다. 그러므로:

- `fullyTraceable`은 `missing`·`unresolved`·`truncated`가 **모두 비어야** true인데, code/eval/approval edge가 하나라도 있으면 그것이 `unresolved`로 들어간다 → **현재 스키마에서 이 route의 `fullyTraceable`은 사실상 항상 false다.**
- 이것을 숨기지 않는다. 응답은 `fullyTraceable`을 그대로 내고, **`traceabilityLimitedByScope: true`** 를 함께 낸다 — "false인 이유가 기록 부실이 아니라 이 route의 권한 경계 때문"임을 소비자가 구분할 수 있어야 한다. 이 플래그가 없으면 운영자가 `fullyTraceable=false`를 보고 기록을 고치려 할 것이다.
- **권고**: 순방향 route의 현재 가치는 "dataset 상세 + deployment 상세 + 나머지 개수"까지다. AC-10 증명에 쓰려면 후속이 필요하다 — (a) tenant-wide lineage read 권한, 또는 (b) `code_commits`·`eval_runs`·`approvals`·`container_images`에 `project_id` migration·backfill. 코디네이터 결정대로 **둘 다 이번 범위가 아니고 후속 설계 후보로만** 적는다(§11). 이 한계를 안 채로 착지하는 것이 결정이며, 내가 그것을 완전 추적으로 부르지는 않는다.

## 6. 권한 경계와 404 정책 (v1.1)

1. **tenant(RLS)**: 두 route 모두 기존 `get_session`(`src/saintvision/api/deps.py:59`)을 쓴다 — `tenant_scope` 안에서 한 트랜잭션으로 읽는다. **이 설계에는 커널 HTTP 호출이 없으므로** 카드 ap가 필요했던 3구간 분리(트랜잭션 밖 HTTP)가 여기서는 필요 없다. 읽기 한 번이 한 트랜잭션이다.
2. **project(live)**: `principal.require_project`(snapshot)를 **쓰지 않는다.** `identity/principal.py:42-50`이 그 snapshot은 양방향으로 틀린다고 스스로 적는다. live 검사는 `services.projects.require_project_access(session, tenant_id=…, project_id=…, user_id=…)`(`services/projects.py:204`)이고, 이것이 `project_members`를 조회 시점에 읽는다.
3. **읽기에 필요한 등급은 membership이다** — `canRequest`·`canApprove`를 요구하지 **않는다**. `require_project_access`는 membership이 없으면 이미 거부하고, 두 flag는 행위 등급이므로 조회에 요구하면 "읽기도 승인 권한이 필요하다"는 잘못된 경계가 된다. (카드 ap의 release는 반대로 `canApprove`를 요구한다 — 등급이 다른 이유를 두 문서가 함께 말한다.)
4. **path → row 결속** (카드 ap F-R4와 같은 원칙): 순방향 route의 path는 `(project_id, model_id, version)`인데 `trace_model()`은 `model_version_id`를 받는다. 그래서 정본 lookup을 명시한다 — `models`에서 `(tenant_id, model_id)`를 찾아 **`project_id == path project`** 를 확인하고, `model_versions`에서 **`(model_id, version)`** 행을 읽어 그 `model_version_id`로 trace한다. **읽기이므로 `FOR UPDATE`를 걸지 않는다**(승격과 달리 상태를 바꾸지 않으므로 잠금이 불필요하고, 읽기 경로에 배타 잠금을 넣으면 §7의 목적인 조회 성능을 스스로 깎는다).
   역조회도 같다 — digest로 찾은 `dataset_versions`를 `datasets`에 join해 `project_id == path project`인 것만 남기고, 결과 `model_versions`도 `models`에 join해 같은 project인 것만 남긴다(나머지는 §5-1의 `unresolvedModelVersions` 개수 하나이고 부재와 구분하지 않는다).
5. **행 수준 project**: §1-4대로 **부모 join**이 유일한 경로다(`model_versions`·`dataset_versions`에 `project_id` 컬럼이 없다). 컬럼이 없는 kind는 tenant 범위임을 응답이 밝힌다(§3-2).
6. **404 정책**: 부재·다른 project·다른 tenant·path와 row의 불일치를 **모두 같은 404**로 낸다. `require_project_access`가 이미 같은 원칙을 쓴다 — *"Reports the same denial whether the project does not exist or the caller simply cannot see it."* 403은 **그 project에 대한 접근 자체가 없을 때**만이고, 접근이 있는 project 안에서 대상이 없으면 404다. 두 코드를 갈라 쓰면 경로 변수로 존재를 탐침할 수 있다.

## 7. 인덱스와 migration

**필요하다. additive 인덱스 하나.**

```
CREATE INDEX ix_dataset_versions_tenant_id_content_sha256
    ON dataset_versions (tenant_id, content_sha256);
```

- 이유: §1-5. 없으면 역조회 1단계가 `dataset_versions` 전체 스캔이고, 이 API의 목적이 바로 그 조회다.
- `tenant_id`를 앞에 두는 이유: 모든 조회가 RLS tenant 범위 안이라 선행 컬럼이 tenant일 때 정책 술어와 인덱스가 같은 방향이다.
- **UNIQUE로 만들지 않는다**: 같은 바이트를 여러 dataset version이 참조할 수 있고(§4-2), 유일 제약은 그 사실을 금지해 버린다.
- `model_lineage`는 `ix_model_lineage_subject_id`가 이미 있어 **추가하지 않는다**. `(tenant_id, subject_id, kind)` 복합으로 바꿀 이유도 지금은 없다 — subject id가 충분히 선택적이다. 측정 없이 인덱스를 늘리지 않는다.
- **(v1.2, 코디네이터 10:43 결정) `CONCURRENTLY`로 만든다.** 일반 `CREATE INDEX`는 `dataset_versions`에 `ACCESS EXCLUSIVE`를 잡아 등록 쓰기를 막는다. Alembic에서는 autocommit 없이는 `CONCURRENTLY`를 쓸 수 없으므로 **autocommit block** 안에서 실행한다.

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        # A previous attempt can leave an INVALID index behind; it is not used
        # by the planner but it does block the same name, so clear it first.
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_dataset_versions_tenant_id_content_sha256")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_dataset_versions_tenant_id_content_sha256 "
            "ON dataset_versions (tenant_id, content_sha256)"
        )

def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_dataset_versions_tenant_id_content_sha256")
```

- **재시도 전 정리가 핵심이다**: `CREATE INDEX CONCURRENTLY`가 중간에 실패하면 PostgreSQL이 **invalid index를 남긴다.** 그것은 계획에 쓰이지 않으면서 이름을 점유하고 쓰기 비용은 그대로 문다. 그래서 upgrade가 **먼저 `DROP INDEX CONCURRENTLY IF EXISTS`** 를 실행한다 — 재실행이 안전해진다.
- **downgrade도 `CONCURRENTLY`** 다(같은 lock 이유).
- **이 저장소의 첫 `CONCURRENTLY` migration이다** — `migrations/`에서 `CONCURRENTLY`·`autocommit_block` grep이 **0건**이다. 그래서 (i) autocommit block 안에서는 이 migration이 **트랜잭션으로 되돌아가지 않는다**(부분 실패 시 상태는 위 IF EXISTS 조합으로 수렴한다), (ii) `tools/migration_graph.py`의 가역성 검사는 `downgrade()`가 refusal이 아니어야 하는데 위 downgrade는 실제 DROP이므로 통과한다.
- 데이터 변경·행 이동 없음. 기존 migration은 손대지 않고 head 다음 번호로 만든다.
- **역조회 라우트는 이 인덱스 없이 착지하지 않는다** — 구현 PR에서 migration과 라우트가 같은 PR에 들어간다.

## 8. 페이지네이션 상한

- 역조회: `build_page(rows, limit=…, id_attr="model_version_id")`와 `validate_cursor`의 `is_id` 형태 검사를 **재사용**한다(`pagination.py`). `build_page`가 이미 `limit + 1`로 "더 있는가"를 답하므로 §4-1-6이 그것을 그대로 쓴다.
- **`clamp_limit`은 쓰지 않는다(v1.2)**. 그 함수는 상한 초과를 **조용히 200으로 깎는데**(`min(requested, maximum)`), 그러면 `limit=10000`을 보낸 클라이언트가 자기가 요청한 페이지 크기를 받았다고 믿는다. 이 두 route는 **10진수 아님·1 미만·200 초과를 모두 `VAL-0003` 422로 거부**한다. 기존 라우트보다 엄격해지는 의도된 차이이고, §9-4대로 질의 인자를 handler가 직접 검증하므로 애초에 `int`가 아니라 문자열이 온다.
- **응답 배열에는 예외 없이 상한이 있다(v1.2, Codex F-R2)**: `datasets` 200 · `deployments` 200 · `datasetVersionIds` 200. 넘으면 `truncated{키: 전체개수}`에 적고 순방향은 `fullyTraceable=false`, 역방향은 `complete=false`다. **상한 없는 배열은 응답에 없다.** 조용한 slice는 금지다.
- 상한 200의 근거는 기존 `pagination.py`의 `maximum=200` 관례이고 측정값이 아니다. 구현 PR에서 사전 등록한다(§11).

## 9. 오류 코드 — 정본 `ProblemDetails`는 공유 모듈이 낸다 (v1.1)

### 9-1. business `InvError`로는 정본 body를 만들 수 없다 (실측)

| 실측 | 위치 | 결과 |
|---|---|---|
| `category_of()`가 `VAL·AUTH·CTX·TOOL·RES·NET·GRAPH·VERIFY·SEC·BUDGET`만 허용 | `errors.py:62-69` | `MODEL-*`·`SYS-*`는 **생성 시점에 `ValueError`** |
| `to_problem()`의 `type`이 `https://saintvision.invenio/problems/<code>` | `errors.py:59`·`:106` | 정본은 `const: "about:blank"` → **위반** |
| `_problem()`이 `instance=str(request.url.path)`를 넣는다 | `api/app.py:100` | `instance`는 정본 properties에 **없고** `additionalProperties: false`다 → **위반** |
| `detail`을 `public`일 때만 넣는다 | `errors.py:112-113` | 정본 `required`에 `detail`이 있다 → 비공개 오류는 **required 누락** |
| `problem.update(self.extra)` | `errors.py:120` | top-level 임의 key → **위반** |
| `RES` 기본값이 409·retryable true | `errors.py:36`·`:50` | `RES-0004`는 404·false여야 한다 → 기본값 사용 불가 |

정본 쪽은 막지 않는다 — `ProblemDetails.category`는 `^[A-Z]+$`이고, 커널이 이미 `MODEL-0001`~`MODEL-0008`·`SYS-0001`을 `problem()`(`services/control-plane/src/inv/app.py:24-41`)으로 내며 그 함수가 `validate_contract("ProblemDetails", body)`를 통과한다. **막는 것은 business `InvError` 한 곳이다.**

### 9-2. 결정: route 전용이 아닌 **공유 모듈**

코디네이터 10:25 결정대로, 새 business route가 함께 쓰는 정본 예외와 handler를 한 곳에 둔다 — **`src/saintvision/api/problem.py`**. 

**owner와 착지 순서를 v1.2에서 못 박는다(Codex F-R3, 코디네이터 10:40 결정)**: 이 모듈과 `SYS-0002`, 그리고 §9-5의 `strict_json_object` helper의 **owner는 #152**다. **이 설계는 #152 v1.3 head `e9e5e78e`에 의존하고, 병합 순서는 #152 → #158이다.** 이 카드는 모듈을 만들지 않고 **쓴다.** v1.1이 "먼저 착지하는 쪽이 만든다"라고 적은 것은 두 PR이 같은 이름을 각각 "예정"하는 상태를 남겼고, Codex 지적대로 **현재 integration base에는 그 모듈이 없으므로** 그 서술로는 "새 code 0개"가 성립하지 않았다. 지금은 선행 PR·head가 고정되어 성립한다. 아래 요구 4건과 §9-5는 **#152 v1.3 §7-1·§7-2와 글자 그대로 같은 계약**이다.

1. **required exact key 집합**: `type·title·status·code·category·detail·retryable·traceId·causeRef·evidenceId` 정확히 10개. `instance` 없음, `extra` 병합 없음, `detail`은 **항상** 존재(비공개 사유일 때도 code별 고정 문구).
2. **`type: "about:blank"`** 고정.
3. **`MODEL`·`SYS` category 지원**: category를 `code.split("-", 1)[0]`에서 파생하고 **enum 화이트리스트를 두지 않는다**(정본 제약이 `^[A-Z]+$`이므로 그것이 유일한 제약이다). status·retryable은 카테고리 기본값 표가 아니라 **code별로 명시**한다 — `errors.py`의 `_STATUS`/`_RETRYABLE`이 `RES`를 409·retryable true로 두기 때문이다.
4. **정본 앵커**: body를 만든 뒤 `from inv.contracts import validate_contract`로 `validate_contract("ProblemDetails", body)`를 호출한다. business 제품 코드가 `inv`를 import하는 전례가 있다(`server.py:2`, `identity/oidc.py:72`). 커널 `problem()`과 **같은 앵커**를 쓰므로 두 표면이 갈라질 수 없다.

`traceId`는 `request.state.trace_id`(`api/app.py:90-96`의 `_trace` 미들웨어) 또는 `ids.new_trace_id()`이고 둘 다 32 hex라 정본 `TraceId`(`^[0-9a-f]{32}$`)를 만족한다. 응답은 `application/problem+json` + `Cache-Control: no-store`(커널 `problem()`과 동일)다.

### 9-3. 기존 `InvError`는 경계에서 번역한다

lineage route는 기존 서비스 함수(`trace_model`, `_load_model_version`)를 부르고 그것들은 business `InvError`를 던진다. **모듈이 경계에서 번역하고 서비스와 `errors.py`는 바꾸지 않는다.**

| 서비스가 던지는 것 | 정본 code | status | retryable |
|---|---|---|---|
| `VAL-SCHEMA`(digest·커서 형식), 알 수 없는 질의 인자 | `VAL-0003` | 422 | false |
| `AUTH-PROJECT-SCOPE` / `require_project_access` 거부 | `AUTH-0030` | 403 | false |
| `RES-ARTIFACT-NOT-FOUND` / `_load_model_version` 부재, 다른 project, 다른 tenant, path/row 불일치, digest에 해당하는 project 내 dataset version 0건 | `RES-0004` | 404 | false |

번역표는 **route별로 명시한 매핑**이고 전역 규칙이 아니다. 같은 `VAL-SCHEMA`가 카드 ap의 release 경로에서는 **상태 전제 위반**(`release_model_version`이 unverified·unpinned·untraceable에 `VAL_SCHEMA`를 쓴다 — `lineage.py:324`·`:326`·`:331`)이므로 거기서는 `GRAPH-0002` 409로 번역된다. 한 business code의 뜻이 호출 지점마다 다르다는 것이 실측이므로, 모듈이 전역으로 추측하면 안 된다.

**표에 없는 code가 올라오면** 모듈은 그것을 정본 신원으로 꾸미지 않는다. 우리 장부에 기록된 실패를 되풀이하지 않기 위해서다 — 타 tenant model-retry가 `503 SYS-0001`로 새어 *"클라이언트가 서버 장애로 오해해 재시도하고 운영 알람에 503으로 잡힌다"*가 F1로 남아 있다(`History/2026-09-22_결정6a_…_Claude.md`). 그래서 미매핑은 **`SYS-0002` 500 · retryable false**(우리 쪽 매핑 누락이라 재시도가 의미 없다)로 두고, **PG-free 시험이 route에서 도달 가능한 code를 열거해 표가 그것을 모두 덮음을 요구**한다 — `SYS-0002`는 계약이 깨지지 않게 두는 자리이고 실제로는 도달하지 않는다.

**이 카드가 새로 만드는 code는 0개다** — 단, 그것은 **#152가 먼저 착지한다는 전제 위에서만** 참이다(§9-2). 독립 착지가 필요해지면 `api/problem.py`·`strict_json_object`·`SYS-0002`가 이 PR의 계약 변경에 들어가고 수는 4건 + code 1개가 된다. 그 경우 owner 충돌을 피하려면 **#158이 owner가 되고 #152가 의존하는 방향으로 뒤집어야** 하며, 그것은 코디네이터 결정 사항이다. 현재 결정은 **#152 owner · #152 → #158 순서**다.

### 9-4. 요청 검증은 handler가 직접 한다 (FastAPI annotation 금지)

`RequestValidationError` 핸들러(`api/app.py:129-138`)는 top-level `fields`를 넣으므로 정본 키 집합을 깨뜨린다. **annotation 타입을 선언하는 것으로는 이것을 피할 수 없다** — FastAPI가 handler 진입 **전에** 검증하고 그 예외를 던지기 때문이다. 그래서:

- 두 route는 질의 인자를 `int`·`Literal` 같은 **제약 annotation으로 받지 않는다.** `request.query_params`에서 **문자열로** 읽고 handler가 직접 검증한다. 잘못된 값은 모듈의 `VAL-0003` 422다.
- path 변수는 `str`로 받고(제약 없는 `str`은 검증 예외를 만들지 않는다) digest·UUID 형태를 handler가 검사한다.
- **(v1.2, Codex F-R4) 허용 query key를 exact set으로 고정한다** — 순방향 route는 `{}`(질의 인자 없음), 역조회 route는 `{"limit", "cursor"}`. 그 밖의 key가 하나라도 있으면 `VAL-0003` 422다. 미지 인자를 조용히 무시하면 오타 난 필터가 "적용된 것처럼" 보인다.
- **(v1.2) 중복 key를 거부한다** — `request.query_params.get()`은 `?limit=1&limit=2`에서 **하나를 조용히 택한다**. 그래서 `request.query_params.multi_items()`로 읽어 같은 key가 두 번 이상이면 `VAL-0003` 422로 거부한다. 어느 값을 택할지 규칙을 만들지 않는다 — 모호한 요청은 거부가 정답이다.
- **(v1.2) `limit`·`cursor` 검증**: `limit`은 10진수 문자열(`^[0-9]{1,4}$`)이어야 하고 1~200 범위여야 한다(§8: 초과를 깎지 않고 거부). `cursor`는 `pagination.validate_cursor`의 `is_id` 형태를 만족해야 하고, 형식 위반과 **과대 길이**(ULID 길이를 넘는 문자열) 모두 `VAL-0003` 422다.
- **(v1.2, 코디네이터 10:43) GET 본문은 1바이트라도 있으면 `VAL-0003`이다.** 무시하지 않는다. 이 경계는 #152 v1.3이 만든 **공유 helper와 같은 곳**에서 온다(§9-5) — GET에 본문이 오는 것은 요청이 무엇을 뜻하는지 모호하다는 신호이고, 조용히 버리면 클라이언트가 그 본문이 반영됐다고 믿는다. Content-Type·크기 경계는 본문이 없는 GET에서는 검사하지 않는다(검사할 본문이 없다).

이 규칙이 살아 있음을 §10의 되돌림 시험이 고정한다.

### 9-5. 공유 `strict_json_object` helper — owner는 #152 (v1.2)

#152 v1.3이 `api/problem.py` 옆에 두는 helper이고, **이 카드는 그 경계를 재사용한다.** 커널 `inv.identity.strict_object`(`inv/identity.py:23-38`)에 파싱을 위임해 duplicate key(`object_pairs_hook`)·non-finite(`parse_constant`)·비object를 거부하고, 호출부가 `(ValueError, TypeError, RecursionError, UnicodeError)`를 잡아 **전부 같은 `VAL-0003`** 으로 번역한다. Content-Type `application/json`(415)과 최대 본문 크기(413)도 같은 경계다.

이 카드의 두 route는 **GET이라 본문이 없어야 하므로** helper의 파싱 경로에 들어가지 않고 **"본문 0바이트" 단정만** 쓴다. 그래도 같은 helper를 통과시키는 이유는 두 PR이 같은 문구·같은 code·같은 status를 쓰게 하는 것이 목적이기 때문이다 — 경계가 두 곳에 따로 있으면 한쪽만 고쳐진다.

## 10. 부정 시험 — 되돌리면 실패해야 하는 것 (총 37건, v1.2)

**PG-free** (`tests/core/`, 순수·fake session):

1. `missing` 계산을 제거하면 → 아무 edge도 없는 model version이 `fullyTraceable=true`로 보고된다.
2. `unresolved`를 빈 배열로 바꾸면 → 다른 project subject·부재 subject·count-only kind를 가진 trace가 `fullyTraceable=true`가 된다.
3. **§5-2 불변식 위반 — 내지 않을 subject 행을 적재하면** → `code_commit`·`container_image`·`eval_run`·`approval` 행이 서비스 반환값(또는 발행된 SQL)에 나타난다. "읽지도 않는다"를 SQL 수준에서 단언한다.
4. **(F-R1) 다른 project subject와 존재하지 않는 subject가 응답에서 구분되면** → 두 fixture의 응답이 달라 "존재 oracle 없음" 단언이 실패한다. 같은 kind·같은 개수면 **응답이 완전히 동일해야** 한다.
5. `dangling`과 `outOfScope`를 두 필드로 되살리면 → 4번과 같은 oracle이 재생된다.
6. `unresolved`에 식별자나 이유(`reason`)를 담으면 → 미노출 단언이 실패한다.
7. `traceabilityLimitedByScope`를 지우면 → `fullyTraceable=false`의 이유가 기록 부실과 권한 경계로 구분되지 않는다(§5-3).
8. `commits`/`images`/`evaluations`/`approvals`를 빈 배열로 응답에 넣으면 → "기록이 없다"로 읽히는 응답이 만들어진다(§3-2).
9. `fullyTraceable`에서 `truncated` 조건을 빼면 → 잘린 응답이 완전 추적으로 보고된다.
10. `datasets`·`deployments`·`datasetVersionIds` 상한 200을 제거하면 → 상한 없는 배열이 응답에 생긴다(경계 시험, §8).
11. digest 검증을 대소문자 무시로 완화하면 → 대문자 입력이 422가 아니라 조회를 시작한다.
12. `deployedByUserId`·`notes`를 응답에 넣으면 → "lineage 읽기에 사용자 식별자·자유 텍스트 없음" 단언이 실패한다.
13. `require_project_access`를 `principal.require_project`로 바꾸면 → 회수된 membership이 조회에 성공한다(snapshot이 토큰 만료까지 남으므로).
14. 읽기에 `canRequest`/`canApprove`를 요구하도록 바꾸면 → membership만 가진 principal이 403을 받아 "읽기에 승인 권한 필요" 경계가 생긴다(회귀).
15. 정본 `ProblemDetails` **exact key set** — 세 code(`VAL-0003`·`AUTH-0030`·`RES-0004`)의 `code`·`status`·`retryable`이 §9-3 표와 같고, top-level에 `fields`·`instance` 같은 임의 key가 **없다**.
16. path→row 결속 제거(`(model_id, version)` 조회를 건너뛰고 임의 `model_version_id` 사용) → 다른 model의 trace가 반환된다.
17. `models.project_id == path project` 확인 제거 → 다른 project의 model version trace가 반환된다.
18. 두 응답 타입의 **missing/extra 필드 거부**(strict response) — `extra="forbid"`와 required 집합이 정확히 검증되고 `export_schemas.py --check`가 drift 0이다.
19. 질의 인자를 `int`/`Literal` **annotation으로 되돌리면** → `?limit=abc`가 정본 body가 아니라 top-level `fields`를 가진 `VAL-SCHEMA` 422를 낸다(§9-4 회귀).
20. **(F-R4) 허용 query key exact set을 제거하면** → `?foo=1`·`?project=other`가 조용히 무시되어 "적용된 필터"로 오해된다. 순방향은 질의 인자 0개, 역조회는 `{limit, cursor}`만이다.
21. **(F-R4) 중복 key**(`?limit=1&limit=2`) → `VAL-0003` 422. `multi_items()`를 `get()`으로 되돌리면 하나가 **조용히 채택**된다.
22. **(F-R4) malformed cursor와 과대 cursor**(ULID 형태 위반, 긴 문자열) → `VAL-0003` 422이고 exact canonical key set이다.
23. **(F-R4) `limit`이 10진수가 아님·`0`·`201`** → 셋 다 `VAL-0003` 422. `clamp_limit`으로 되돌리면 `201`이 **조용히 200으로 깎여** 성공한다(§8).
24. **(F-R4·10:43) GET 본문이 1바이트라도 있으면** → `VAL-0003` 422. 무시하도록 되돌리면 클라이언트가 그 본문이 반영됐다고 믿는다.
25. 공유 모듈의 번역표에서 한 항목을 지우면 → 그 실패가 `SYS-0002` 500으로 떨어지고, 도달 가능 code 열거 시험이 **표 미충족**으로 실패한다.
26. 모듈의 `validate_contract("ProblemDetails", …)` 호출을 지우면 → `instance`를 다시 넣거나 `detail`을 빼도 통과한다(정본 앵커 회귀).
27. **(F-R2) DISTINCT를 pagination 뒤로 옮기면** → 두 dataset version이 같은 model version으로 합류할 때 같은 item이 **중복**되고 커서 경계에서 **누락**된다.
28. **(F-R2) `datasetVersionIds` 상한과 3단계 `IN` 집합이 달라지면** → 응답에 없는 dataset version에서 나온 model version이 items에 섞인다(근거 대조 불가).
29. `complete` 계산에서 `truncated` 조건을 빼면 → 앞 200개에서 나온 결과가 `complete=true`로 보고된다.

**실 PG** (단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

30. RLS: 다른 tenant의 model version·digest는 404이고 행이 보이지 않는다.
31. grant 없는 project는 403이며, grant 있는 project 안에서 없는 대상은 404다(두 코드가 섞이지 않는다).
32. **(F-R1) 교차 project edge를 심은 fixture와 부재 subject를 심은 fixture의 응답이 동일**하다 — 상세 0건, `unresolved` 개수만, 식별자 없음.
33. **(F-R2) 같은 digest를 두 dataset version이 가지고 둘이 같은 model version으로 합류할 때** → `datasetVersionIds` 길이 2, items의 그 model version은 **한 번만** 나온다.
34. 역조회 페이지 경계: `limit` 초과 시 `nextCursor`로 이어지며 중복·누락이 없다.
35. 인덱스 부재 되살림: 인덱스를 지우면 계획이 seq scan으로 바뀐다(성능 단언이 아니라 **계획 관측**으로만 기록).
36. **(F-R5) `CONCURRENTLY` 재시도**: invalid index를 남긴 상태에서 upgrade를 다시 실행하면 성공한다(선행 `DROP INDEX CONCURRENTLY IF EXISTS` 때문). downgrade 뒤 해당 인덱스는 0건이다.
37. 양성 대조 겸 정직성 대조: dataset·deployment 상세가 오고 `missing`이 비어 있으며, **code/eval/approval edge가 있으면 `fullyTraceable=false`이고 `traceabilityLimitedByScope=true`** 다(§5-3을 응답으로 확인).

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 30~37의 실행 근거는 hosted CI다.

## 11. 범위 밖 · 미해결

1. **business 오류 표면 전체의 정본화는 범위 밖이다**(코디네이터 10:25 결정의 선택지 (a)). 이 카드가 여는 것은 **새 route 둘**이고 기존 `nodes`·`pools`·`storage` 라우트의 `InvError` body는 그대로 둔다. 구현 변경 범위는 **`api/problem.py` 신설 + `create_app`에 handler 등록 + 새 route 둘이 그 모듈 사용**까지이며 `errors.py`·기존 handler·기존 라우트는 **건드리지 않는다**. 모듈은 카드 ap(#152)와 공유하므로 **먼저 착지하는 쪽이 만들고 나중 쪽은 재사용한다**(두 PR이 같은 파일을 각각 만들면 충돌한다).
2. **쓰기 라우트는 범위 밖이다.** `register_*`·`record_lineage`·`record_deployment`에는 여전히 요청 경로가 없다. 이 설계는 읽기 둘만 연다. 그 사실을 장부에 남겨야 한다(VF-CL-03 카드 ap와 같은 부류).
3. **후속 설계 후보 2건(v1.2, 코디네이터 10:40)** — §5-3의 한계를 닫는 길이다. (a) **tenant-wide lineage read 권한**: project membership과 별개로 tenant 범위 lineage 상세를 읽는 등급. (b) **`project_id` migration·backfill**: `code_commits`·`eval_runs`·`approvals`·`container_images`에 컬럼 추가. **둘 다 이번 범위가 아니다.** (b)는 기존 행의 소속을 무엇으로 정할지부터 결정해야 하고(교차 project edge가 이미 있을 수 있다, §1-4-4), (a)는 권한 모델 변경이라 owner가 다르다.
4. **`record_lineage`가 교차 project edge를 막지 않는 것**(§1-4-4)은 **쓰기 측 결함**이고 이 설계가 고치지 않는다. 읽기에서 누설을 막을 뿐이다. 쓰기에서 거부해야 하는지는 Codex 판단을 받는다 — 막으면 기존 행 중 위반이 있을 수 있어 backfill 조사가 필요하다.
5. **`eval_runs`·`approvals`·`code_commits`에 project 컬럼이 없는 것**을 이 카드가 바꾸지 않는다. 필요하다고 판단되면 별 카드(migration + backfill)다.
6. **`container_images`는 project 컬럼이 없다**(v1.2 정정) — v1.1이 join 대상이라 적은 것은 틀렸고 `countOnlyKinds`에 들어간다. `REQUIRED_KINDS`에 없다는 사실(§1-2)은 유지한다 — 이미지 없는 모델도 완전 추적일 수 있다.
7. 배열 상한 200은 `pagination.py` 관례를 따른 값이고 측정 근거가 없다. 구현 PR에서 사전 등록한다.
8. **전역 strict-body 미들웨어**(커널에는 있고 business app에는 없다)는 #152와 같은 이유로 범위 밖이다.

## 12. 요약

- `trace_model`은 있는데 **HTTP로 도달할 수 없고**, 역조회는 **함수부터 없다**(§1-1).
- 계약 변경은 **라우트 2개 + 응답 타입 2개 = 4건**이고 **새 오류 code 0개**다. 응답 타입은 `schemas.py`의 `Strict` 클래스이고 정본 `core.schema.json`은 무변경이다(§2·§9).
- project 범위가 테이블마다 다르다 — **`project_id`가 있는 것은 `models`와 `datasets` 둘뿐**이고 `container_images`에는 **없다**(v1.1 정정). 응답은 `detailedKinds`/`countOnlyKinds`로 **상세를 받았는지 개수만 받았는지**를 말한다(§1-4·§3-2).
- 소유를 증명할 수 없는 subject는 **fail-closed `unresolved` 개수 하나**로만 보고한다 — 부재·타 project·project 컬럼 없음을 **구분하지 않아 존재 oracle이 없다**(§5-1).
- 그래서 **이 route는 지금 AC-10 완전 추적을 증명할 수 없다**. `REQUIRED_KINDS` 넷 중 셋이 상세 불가이므로 `fullyTraceable`은 사실상 항상 false이고, 그 이유를 `traceabilityLimitedByScope`가 말한다. 후속 후보 둘(tenant-wide 권한 / `project_id` backfill)은 범위 밖이다(§5-3·§11-3).
- 공유 모듈·helper·`SYS-0002`의 **owner는 #152**이고 병합 순서는 **#152 → #158**이다(§9-2).
- 인덱스는 **`CREATE INDEX CONCURRENTLY`** 를 autocommit block에서 만들고 재시도 전에 invalid index를 정리한다(§7).
- **인덱스 하나가 필요하고 migration이 필요하다** — `dataset_versions(tenant_id, content_sha256)`, additive·가역(§7).
- 권한은 **live `require_project_access`**(읽기는 membership 등급), 404는 없음과 남의 것을 구분하지 않으며, 오류는 전부 **공유 모듈 `api/problem.py`가 내는 정본 `ProblemDetails`**다 — business `InvError`로는 만들 수 없음을 실측으로 확인했다(§6·§9).
- 되돌리면 실패하는 **부정 시험 37건**(PG-free 29 + 실 PG 8)이고 실 PG 8건의 근거는 hosted CI다(§10).
