---
doc_id: "CLAUDE-S10DB-LINEAGE-QUERY-API-DESIGN-001"
title: "S10-DB lineage 조회 API 설계 — 순방향 trace와 dataset digest 역조회 (계약 변경 명시)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
task_ids: ["S10-DB"]
tags: ["s10-db", "lineage", "read-api", "design", "contract-change", "index", "claude"]
---

# S10-DB lineage 조회 API 설계

S10-FE 매트릭스(#144)와 #146이 찾은 "데이터셋 해시로 역추적이 실제로 지원되지 않는다"를 닫는 읽기 전용 API 설계. **설계만이고 구현은 승인 뒤 별도 PR이다.** 실행 0건 — 아래 사실은 전부 `grep`/정독이다.

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

### 1-4. project 범위가 테이블마다 다르다 — 이 설계의 핵심 제약

실측 결과다.

| 테이블 | `project_id` |
|---|---|
| `models` · `datasets` · `container_images` | **있음** (FK → `projects`) |
| `model_versions` · `dataset_versions` · `model_lineage` · `deployments` · `eval_runs` · `approvals` · `code_commits` | **없음** (tenant 범위만) |

따라서:

1. **진입점 둘은 모두 project 강제가 가능하다** — model version은 `models.project_id`로, dataset digest는 `datasets.project_id`로 **부모 join**을 통해서다. 행 컬럼 필터가 아니라 join이라는 점을 구현이 잊으면 안 된다.
2. **trace 내용 일부는 project로 걸 수 없다** — `eval_run`·`approval`·`code_commit`은 project 컬럼이 아예 없어 **tenant 범위 사실**이다. 응답이 이것을 숨기면 "project로 걸러진 목록"으로 오독된다.
3. **교차 project edge가 기록 가능하다.** `record_lineage`(`lineage.py:243-250`)는 `kind`만 검사하고 subject의 project(존재 여부조차) **검사하지 않는다**. 그래서 project A의 model version이 project B의 dataset version을 subject로 가질 수 있다. project A 범위 trace가 그것을 그대로 내면 **다른 project 행이 새고**, 조용히 빼면 **완전성을 위장한다**. §5-3이 이 딜레마의 처리다.

### 1-5. 역조회에 필요한 인덱스가 없다

- `dataset_versions.content_sha256`: `Sha256` 컬럼에 `checksum_is_lowercase` CHECK만 있고 **인덱스가 없다**(`db/models/lineage.py:77-91`의 `__table_args__`에 없고, `migrations/versions/*.py`에서 `content_sha256` 인덱스 grep **0건**).
- `model_lineage`: `Index("ix_model_lineage_subject_id", "subject_id")`가 **이미 있다**(`db/models/lineage.py:263`).

역조회 경로는 `digest → dataset_versions → model_lineage(subject_id, kind='dataset_version') → model_versions`이고, **첫 단계만 인덱스가 없다** → §7.

## 2. 계약 변경 (명시)

**새 라우트 2개 · 새 응답 타입 2개.** 커널 schema·라우트·registry status 변경은 없다.

1. `GET /v1/projects/{project_id}/models/{model_id}/versions/{version}/lineage` → `ModelLineageTraceResponse`
2. `GET /v1/projects/{project_id}/lineage/dataset-versions/by-digest/{content_sha256}/model-versions` → `ModelVersionByDatasetDigestPageResponse`

두 응답 타입 모두 `additionalProperties: false`. 동반 산출물: JSON Schema, 생성 TS/Go/Python 타입, fixture, 서빙 앵커, `generate_contracts.py` drift 0, `tests/test_route_coverage.py` 반영.

**읽기 전용이다.** 두 라우트는 어떤 행도 쓰지 않으며 감사 행도 만들지 않는다(기존 읽기 라우트 관례와 같다).

경로 형태 근거: 진입점이 둘 다 project 강제 가능하므로(§1-4-1) `/v1/projects/{project_id}/` 아래 둔다. digest를 경로 변수로 두는 이유는 캐시·로그 친화이고, 64 hex 소문자 외에는 라우트 단계에서 422로 거부한다.

## 3. 순방향 trace

### 3-1. 서비스 변경

`trace_model`에 **deployments를 더한다**(§1-3). `deployments`는 lineage edge가 아니라 `model_version_id` 직접 조회이므로 `by_kind` 경로가 아니라 별도 select다. 그리고 `fullyTraceable` 술어에 §5-3의 `outOfScope`를 더한다 — **기존 두 조건을 빼지 않고 더한다**.

deployment는 `REQUIRED_KINDS`에 **넣지 않는다**: 배포되지 않은 released 모델은 정상이며, 배포 부재를 "추적 불가"로 부르면 `missing`의 뜻이 흐려진다. 대신 `deployments: []`는 그대로 빈 배열이 맞다 — 이것은 "기록이 없다"가 아니라 "배포된 적 없다"는 **완결된 사실**이다. `missing`/`dangling`/`outOfScope`와 구분되는 이유를 응답 설명에 적는다.

### 3-2. 응답 shape

`ModelLineageTraceResponse`(`additionalProperties: false`):

- `modelVersionId` · `version` · `stage` · `contentSha256` · `producedByRunId`
- `datasets[]` · `commits[]` · `images[]` · `evaluations[]` · `approvals[]` — `trace_model`의 현재 항목 shape 유지
- `deployments[]` — `deploymentId`·`environment`·`status`·`deployedDigest`·`imageId`·`approvalId`·`deployedAt`·`supersededAt` (`deployedByUserId`·`notes`는 **넣지 않는다**: 사용자 식별자와 자유 텍스트를 lineage 읽기에 노출할 이유가 없다)
- `missing[]` · `dangling[]` · `outOfScope[]` · `truncated{}` · `fullyTraceable`
- `projectScopedKinds[]`와 `tenantScopedKinds[]` — **어느 항목이 project로 걸러졌고 어느 항목이 tenant 범위인지 응답이 스스로 말한다**(§1-4-2). 이것이 없으면 소비자가 전부 project 범위라고 읽는다.

## 4. 역조회 (dataset digest → model versions)

### 4-1. 새 서비스 함수

`models_from_dataset_digest(session, *, tenant_id, project_id, content_sha256, limit, cursor)`.

1. `content_sha256`을 소문자 64 hex로 검증(아니면 `VAL_SCHEMA` 422). 대문자를 소문자로 **정규화하지 않는다** — 컬럼 CHECK가 소문자만 허용하므로 대문자 입력은 클라이언트 오류이고, 조용한 정규화는 "대소문자 무시 비교"라는 오해를 만든다.
2. `dataset_versions`를 digest로 찾고 `datasets`에 join해 `project_id = :project`인 것만 남긴다. **0건이면 404**(§6).
3. 그 `dataset_version_id` 집합을 `model_lineage.subject_id`(`kind='dataset_version'`)로 조회 → `model_version_id` 집합.
4. `model_versions`를 적재하고 `models`에 join해 `project_id = :project`인 것만 남긴다. **project 밖 model version은 목록에서 제외하고 개수만 `outOfScopeModelVersions`로 보고한다**(식별자 없음).
5. `model_version_id` 오름차순 커서 페이지로 반환.

### 4-2. 응답 shape

`ModelVersionByDatasetDigestPageResponse`(`additionalProperties: false`):

- `contentSha256`(요청 echo) · `datasetVersionIds[]`(2단계에서 project 안에 있던 것) · `items[]`(`modelVersionId`·`modelId`·`version`·`stage`·`contentSha256`) · `nextCursor` · `outOfScopeModelVersions`(정수) · `danglingSubjects`(정수)
- `danglingSubjects`: edge는 있으나 `model_versions` 행이 없는 수. 순방향의 `dangling`과 같은 이유로 **0이 아니면 숨기지 않는다**.

**한 digest가 여러 dataset version에 걸릴 수 있다**(같은 바이트를 다른 dataset로 등록). 그래서 `datasetVersionIds`가 배열이고, 이것을 단일 값으로 좁히면 일부 model version이 조용히 빠진다.

## 5. `missing`을 빈 배열로 숨기지 않는다 — 세 범주

| 범주 | 뜻 | 응답 |
|---|---|---|
| `missing` | `REQUIRED_KINDS` 중 edge가 0건 | kind 이름 배열 (기존 그대로) |
| `dangling` | edge는 있고 subject 행이 없음 | `{kind, subjectId}` 배열 (기존 그대로) |
| **`outOfScope`** (신규) | edge는 있고 subject 행도 있으나 **다른 project 소유** | `{kind, count}` 배열 — **식별자 없음** |

`outOfScope`가 §1-4-3의 딜레마를 푼다: 다른 project의 행을 내보내지 않으면서도 "여기 우리가 보여주지 않는 것이 n개 있다"를 말한다. 완전성 위장도, 누설도 아니다.

`fullyTraceable`은 **세 범주가 모두 비어야** true다. 그리고 `truncated{kind: count}`가 비어 있지 않으면 **역시 false**다 — 잘라낸 응답을 완전 추적으로 부를 수 없다.

## 6. 권한 경계와 404 정책

1. **RLS(tenant)**: 라우트는 기존 `get_session`(`src/saintvision/api/deps.py:59`)을 쓴다 — `get_principal` 뒤 `tenant_scope(session, principal.tenant_id)` 안에서 열리므로 모든 조회가 tenant 범위다. 이 설계는 grant를 추가하지 않는다.
2. **app 권한(project)**: `principal.require_project(project_id)`(`src/saintvision/identity/principal.py:54`) → 위반 시 `AUTH_PROJECT_SCOPE` 403.
3. **행 수준 project**: §1-4대로 **부모 join**으로 강제한다(`models`·`datasets`·`container_images`). 컬럼이 없는 kind는 tenant 범위임을 응답이 밝힌다(§3-2).
4. **404 정책**: 없는 것과 남의 것을 **구분하지 않는다**. 대상이 다른 tenant든 다른 project든 아예 없든 **동일한 `RES_ARTIFACT_NOT_FOUND` 404**다. 기존 `_load_model_version`·`lineage.py:206`이 이미 그 방식이고("model not found"), 403과 404를 갈라 쓰면 **경로 변수로 존재 여부를 탐침**할 수 있다. `require_project`의 403은 **principal이 그 project에 대한 grant 자체가 없을 때**만이고, grant가 있는 project 안에서 대상이 없으면 404다.

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
- migration은 **forward-only, 되돌릴 수 있는 downgrade 포함**(인덱스 DROP). 데이터 변경·행 이동 없음. 기존 migration은 손대지 않고 head 다음 번호로 만든다.
- **역조회 라우트는 이 인덱스 없이 착지하지 않는다** — 구현 PR에서 migration과 라우트가 같은 PR에 들어간다.

## 8. 페이지네이션 상한

- 역조회: 기존 `services/pagination.py`의 `clamp_limit(requested, default=50, maximum=200)` · `validate_cursor` · `build_page(rows, limit=…, id_attr="model_version_id")`를 **그대로 재사용**한다. 새 페이지네이션을 만들지 않는다. 잘못된 커서는 `VAL_CURSOR`(`errors.py:128`) 422.
- 순방향 trace는 단일 객체이므로 커서가 없지만 **배열이 무한할 수 있다**. kind별 상한 **200**을 두고, 넘으면 `truncated{kind: 전체개수}`에 기록하고 `fullyTraceable=false`로 만든다. 조용한 slice는 금지다.

## 9. 오류 코드 (기존 재사용 우선)

| 상황 | 코드 | status |
|---|---|---|
| digest가 소문자 64 hex 아님, 알 수 없는 질의 인자 | `VAL_SCHEMA` | 422 |
| 커서가 잘못됨 | `VAL_CURSOR` | 422 |
| principal에 그 project grant 없음 | `AUTH_PROJECT_SCOPE` | 403 |
| model version 없음 / 다른 tenant·project / digest에 해당하는 project 내 dataset version 0건 | `RES_ARTIFACT_NOT_FOUND` | 404 |

**새 오류 코드를 만들지 않는다.** 네 상황 모두 기존 `errors.py` 코드로 정확히 표현된다.

## 10. 부정 시험 — 되돌리면 실패해야 하는 것

**PG-free** (`tests/core/`, 순수·fake session):

1. `missing` 계산을 제거하면 → 아무 edge도 없는 model version이 `fullyTraceable=true`로 보고된다.
2. `dangling` 계산을 제거하면 → subject 행이 없는 edge가 완전 추적으로 통과한다.
3. `outOfScope`를 빈 배열로 바꾸면 → 다른 project subject를 가진 trace가 `fullyTraceable=true`가 된다.
4. `fullyTraceable`에서 `truncated` 조건을 빼면 → 잘린 응답이 완전 추적으로 보고된다.
5. kind 상한 200을 제거하면 → 배열이 무한히 커진다(경계 시험).
6. digest 검증을 대소문자 무시로 완화하면 → 대문자 입력이 422가 아니라 조회를 시작한다.
7. `projectScopedKinds`/`tenantScopedKinds`를 제거하면 → 응답이 범위를 스스로 말하지 않는다.
8. `deployedByUserId`·`notes`를 응답에 넣으면 → "lineage 읽기에 사용자 식별자·자유 텍스트 없음" 단언이 실패한다.
9. `outOfScope`에 식별자를 담으면 → "다른 project 식별자 미노출" 단언이 실패한다.

**실 PG** (단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

10. RLS: 다른 tenant의 model version·digest는 404이고 행이 보이지 않는다.
11. grant 없는 project는 403이며, grant 있는 project 안에서 없는 대상은 404다(두 코드가 섞이지 않는다).
12. 교차 project edge를 심은 뒤 순방향 trace가 **다른 project 행을 내보내지 않고** `outOfScope` 개수만 낸다.
13. 같은 digest를 두 dataset version이 가질 때 역조회가 **둘 다**의 model version을 모은다(`datasetVersionIds` 길이 2).
14. 역조회 페이지 경계: `limit` 초과 시 `nextCursor`로 이어지며 중복·누락이 없다.
15. 인덱스 부재 되살림: 인덱스를 지우면 계획이 seq scan으로 바뀐다(성능 단언이 아니라 **계획 관측**으로만 기록).
16. 양성 대조: 완전 기록된 model version이 `fullyTraceable=true`이고 세 범주가 모두 비어 있다.

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 10~16의 실행 근거는 hosted CI다.

## 11. 범위 밖 · 미해결

1. **쓰기 라우트는 범위 밖이다.** `register_*`·`record_lineage`·`record_deployment`에는 여전히 요청 경로가 없다. 이 설계는 읽기 둘만 연다. 그 사실을 장부에 남겨야 한다(VF-CL-03 카드 ap와 같은 부류).
2. **`record_lineage`가 교차 project edge를 막지 않는 것**(§1-4-3)은 **쓰기 측 결함**이고 이 설계가 고치지 않는다. 읽기에서 누설을 막을 뿐이다. 쓰기에서 거부해야 하는지는 Codex 판단을 받는다 — 막으면 기존 행 중 위반이 있을 수 있어 backfill 조사가 필요하다.
3. **`eval_runs`·`approvals`·`code_commits`에 project 컬럼이 없는 것**을 이 카드가 바꾸지 않는다. 필요하다고 판단되면 별 카드(migration + backfill)다.
4. `container_images`는 project 컬럼이 있으므로 §6-3 join 대상이다. `REQUIRED_KINDS`에 없다는 사실(§1-2)은 유지한다 — 이미지 없는 모델도 완전 추적일 수 있다.
5. 순방향 trace의 kind별 상한 200은 관례를 따른 값이고 측정 근거가 없다. 구현 PR에서 사전 등록한다.

## 12. 요약

- `trace_model`은 있는데 **HTTP로 도달할 수 없고**, 역조회는 **함수부터 없다**(§1-1).
- 계약 변경은 **라우트 2개 + 응답 타입 2개**, 커널 무변경(§2).
- project 범위가 테이블마다 달라서 **진입점은 부모 join으로 강제 가능하고 일부 kind는 tenant 범위**다. 응답이 그 구분을 스스로 말한다(§1-4·§3-2).
- 교차 project edge는 **`outOfScope` 개수만** 내어 누설과 위장을 동시에 피한다(§5).
- **인덱스 하나가 필요하고 migration이 필요하다** — `dataset_versions(tenant_id, content_sha256)`, additive·가역(§7).
- 404는 없음과 남의 것을 구분하지 않고, 새 오류 코드는 만들지 않는다(§6·§9).
