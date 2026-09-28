---
doc_id: "CLAUDE-S10DB-LINEAGE-QUERY-API-DESIGN-001"
title: "S10-DB lineage 조회 API 설계 — 순방향 trace와 dataset digest 역조회 (계약 변경 명시)"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:29:04+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
task_ids: ["S10-DB"]
tags: ["s10-db", "lineage", "read-api", "design", "contract-change", "index", "claude"]
---

# S10-DB lineage 조회 API 설계

S10-FE 매트릭스(#144)와 #146이 찾은 "데이터셋 해시로 역추적이 실제로 지원되지 않는다"를 닫는 읽기 전용 API 설계. **설계만이고 구현은 승인 뒤 별도 PR이다.** 실행 0건 — 아래 사실은 전부 `grep`/정독이다.

> **v1.1**: PR #152(카드 ap)에 대한 Codex 계약 검토 F-R1~F-R5의 원칙을 이 설계에도 처음부터 적용했다 — live 권한 재확인, 정본 `ProblemDetails`, strict 응답, path→row 결속, 존재 비노출 404. 여기에 10:25 코디네이터 결정 2건도 처음부터 반영했다 — 정본 `ProblemDetails`는 **공유 모듈**이 내고(business `InvError`로는 `MODEL`·`SYS` category를 만들 수 없다), 요청 검증은 **FastAPI annotation이 아니라 handler의 직접 검증**으로 한다. 바뀐 절은 §2·§4·§6·§9·§10·§11이고 `updated`는 `date` 출력에서 복사했다.

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
6. **trace 내용 일부는 project로 걸 수 없다** — `eval_run`·`approval`·`code_commit`은 project 컬럼이 아예 없어 **tenant 범위 사실**이다. 응답이 이것을 숨기면 "project로 걸러진 목록"으로 오독된다.
3. **교차 project edge가 기록 가능하다.** `record_lineage`(`lineage.py:243-250`)는 `kind`만 검사하고 subject의 project(존재 여부조차) **검사하지 않는다**. 그래서 project A의 model version이 project B의 dataset version을 subject로 가질 수 있다. project A 범위 trace가 그것을 그대로 내면 **다른 project 행이 새고**, 조용히 빼면 **완전성을 위장한다**. §5-3이 이 딜레마의 처리다.

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

1. `content_sha256`을 소문자 64 hex로 검증(아니면 `VAL-0003` 422, §9). 대문자를 소문자로 **정규화하지 않는다** — 컬럼 CHECK가 소문자만 허용하므로 대문자 입력은 클라이언트 오류이고, 조용한 정규화는 "대소문자 무시 비교"라는 오해를 만든다.
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

## 6. 권한 경계와 404 정책 (v1.1)

1. **tenant(RLS)**: 두 route 모두 기존 `get_session`(`src/saintvision/api/deps.py:59`)을 쓴다 — `tenant_scope` 안에서 한 트랜잭션으로 읽는다. **이 설계에는 커널 HTTP 호출이 없으므로** 카드 ap가 필요했던 3구간 분리(트랜잭션 밖 HTTP)가 여기서는 필요 없다. 읽기 한 번이 한 트랜잭션이다.
2. **project(live)**: `principal.require_project`(snapshot)를 **쓰지 않는다.** `identity/principal.py:42-50`이 그 snapshot은 양방향으로 틀린다고 스스로 적는다. live 검사는 `services.projects.require_project_access(session, tenant_id=…, project_id=…, user_id=…)`(`services/projects.py:204`)이고, 이것이 `project_members`를 조회 시점에 읽는다.
3. **읽기에 필요한 등급은 membership이다** — `canRequest`·`canApprove`를 요구하지 **않는다**. `require_project_access`는 membership이 없으면 이미 거부하고, 두 flag는 행위 등급이므로 조회에 요구하면 "읽기도 승인 권한이 필요하다"는 잘못된 경계가 된다. (카드 ap의 release는 반대로 `canApprove`를 요구한다 — 등급이 다른 이유를 두 문서가 함께 말한다.)
4. **path → row 결속** (카드 ap F-R4와 같은 원칙): 순방향 route의 path는 `(project_id, model_id, version)`인데 `trace_model()`은 `model_version_id`를 받는다. 그래서 정본 lookup을 명시한다 — `models`에서 `(tenant_id, model_id)`를 찾아 **`project_id == path project`** 를 확인하고, `model_versions`에서 **`(model_id, version)`** 행을 읽어 그 `model_version_id`로 trace한다. **읽기이므로 `FOR UPDATE`를 걸지 않는다**(승격과 달리 상태를 바꾸지 않으므로 잠금이 불필요하고, 읽기 경로에 배타 잠금을 넣으면 §7의 목적인 조회 성능을 스스로 깎는다).
   역조회도 같다 — digest로 찾은 `dataset_versions`를 `datasets`에 join해 `project_id == path project`인 것만 남기고, 결과 `model_versions`도 `models`에 join해 같은 project인 것만 남긴다(나머지는 §5의 `outOfScope` 개수).
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
- migration은 **forward-only, 되돌릴 수 있는 downgrade 포함**(인덱스 DROP). 데이터 변경·행 이동 없음. 기존 migration은 손대지 않고 head 다음 번호로 만든다.
- **역조회 라우트는 이 인덱스 없이 착지하지 않는다** — 구현 PR에서 migration과 라우트가 같은 PR에 들어간다.

## 8. 페이지네이션 상한

- 역조회: 기존 `services/pagination.py`의 `clamp_limit(requested, default=50, maximum=200)` · `validate_cursor` · `build_page(rows, limit=…, id_attr="model_version_id")`를 **그대로 재사용**한다. 새 페이지네이션을 만들지 않는다. 잘못된 커서는 `VAL_CURSOR`(`errors.py:128`) 422.
- 순방향 trace는 단일 객체이므로 커서가 없지만 **배열이 무한할 수 있다**. kind별 상한 **200**을 두고, 넘으면 `truncated{kind: 전체개수}`에 기록하고 `fullyTraceable=false`로 만든다. 조용한 slice는 금지다.

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

코디네이터 10:25 결정대로, 새 business route가 함께 쓰는 정본 예외와 handler를 한 곳에 둔다 — **`src/saintvision/api/problem.py`(신규)**. 카드 ap(#152)의 release route와 이 카드의 lineage route **둘 다 이 모듈을 쓴다**. 요구 사항은 넷이다.

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

**이 카드가 새로 만드는 code는 0개다.** `SYS-0002`는 공유 모듈의 것이고 카드 ap(#152) v1.2에서 셈에 들어간다 — 같은 code를 두 카드가 각각 세면 분모가 부풀어 오른다.

### 9-4. 요청 검증은 handler가 직접 한다 (FastAPI annotation 금지)

`RequestValidationError` 핸들러(`api/app.py:129-138`)는 top-level `fields`를 넣으므로 정본 키 집합을 깨뜨린다. **annotation 타입을 선언하는 것으로는 이것을 피할 수 없다** — FastAPI가 handler 진입 **전에** 검증하고 그 예외를 던지기 때문이다. 그래서:

- 두 route는 질의 인자를 `int`·`Literal` 같은 **제약 annotation으로 받지 않는다.** `request.query_params`에서 **문자열로** 읽고 handler가 직접 검증한다(`limit`이 10진수인지, 상한 안인지, 커서 형식이 맞는지). 잘못된 값은 모듈의 `VAL-0003`이다.
- path 변수는 `str`로 받고(제약 없는 `str`은 검증 예외를 만들지 않는다) digest·UUID 형태를 handler가 검사한다.
- GET이라 본문이 없지만 **본문이 실려 오면 무시하지 않고 `VAL-0003`으로 거부**한다. 카드 ap의 POST route는 같은 이유로 `Request`의 raw body를 직접 파싱해 malformed JSON·배열·scalar를 모두 `VAL-0003`으로 번역한다(#152 v1.2).

이 규칙이 살아 있음을 §10의 16·18이 되돌림 시험으로 고정한다.

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

**PG-free 추가 (v1.1, 카드 ap F-R3~F-R5 원칙)**:

10. `require_project_access`를 `principal.require_project`로 바꾸면 → 회수된 membership이 조회에 성공한다(snapshot이 토큰 만료까지 남으므로).
11. 읽기에 `canRequest`/`canApprove`를 요구하도록 바꾸면 → membership만 가진 principal이 403을 받아 "읽기에 승인 권한 필요" 경계가 생긴다(회귀).
12. 정본 `ProblemDetails` **exact key set** — 세 오류 각각의 `code`·`status`·`retryable`이 §9 표와 같고, top-level에 `fields` 같은 임의 key가 **없다**.
13. path→row 결속 제거(`(model_id, version)` 조회를 건너뛰고 임의 `model_version_id` 사용) → 다른 model의 trace가 반환된다.
14. `models.project_id == path project` 확인 제거 → 다른 project의 model version trace가 반환된다.
15. 두 응답 타입의 **missing/extra 필드 거부**(strict response) — `extra="forbid"`와 required 집합이 정확히 검증되고 `export_schemas.py --check`가 drift 0이다.
16. 질의 인자를 `int`/`Literal` **annotation으로 되돌리면** → `?limit=abc`가 정본 body가 아니라 top-level `fields`를 가진 `VAL-SCHEMA` 422를 낸다(§9-4 회귀).
17. 공유 모듈의 번역표에서 한 항목을 지우면 → 그 실패가 `SYS-0002` 500으로 떨어지고, 도달 가능 code 열거 시험이 **표 미충족**으로 실패한다.
18. 모듈의 `validate_contract("ProblemDetails", …)` 호출을 지우면 → `instance`를 다시 넣거나 `detail`을 빼도 통과한다(정본 앵커 회귀).

**실 PG** (단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

19. RLS: 다른 tenant의 model version·digest는 404이고 행이 보이지 않는다.
20. grant 없는 project는 403이며, grant 있는 project 안에서 없는 대상은 404다(두 코드가 섞이지 않는다).
21. 교차 project edge를 심은 뒤 순방향 trace가 **다른 project 행을 내보내지 않고** `outOfScope` 개수만 낸다.
22. 같은 digest를 두 dataset version이 가질 때 역조회가 **둘 다**의 model version을 모은다(`datasetVersionIds` 길이 2).
23. 역조회 페이지 경계: `limit` 초과 시 `nextCursor`로 이어지며 중복·누락이 없다.
24. 인덱스 부재 되살림: 인덱스를 지우면 계획이 seq scan으로 바뀐다(성능 단언이 아니라 **계획 관측**으로만 기록).
25. 양성 대조: 완전 기록된 model version이 `fullyTraceable=true`이고 세 범주가 모두 비어 있다.

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 19~25의 실행 근거는 hosted CI다.

## 11. 범위 밖 · 미해결

1. **business 오류 표면 전체의 정본화는 범위 밖이다**(코디네이터 10:25 결정의 선택지 (a)). 이 카드가 여는 것은 **새 route 둘**이고 기존 `nodes`·`pools`·`storage` 라우트의 `InvError` body는 그대로 둔다. 구현 변경 범위는 **`api/problem.py` 신설 + `create_app`에 handler 등록 + 새 route 둘이 그 모듈 사용**까지이며 `errors.py`·기존 handler·기존 라우트는 **건드리지 않는다**. 모듈은 카드 ap(#152)와 공유하므로 **먼저 착지하는 쪽이 만들고 나중 쪽은 재사용한다**(두 PR이 같은 파일을 각각 만들면 충돌한다).
2. **쓰기 라우트는 범위 밖이다.** `register_*`·`record_lineage`·`record_deployment`에는 여전히 요청 경로가 없다. 이 설계는 읽기 둘만 연다. 그 사실을 장부에 남겨야 한다(VF-CL-03 카드 ap와 같은 부류).
3. **`record_lineage`가 교차 project edge를 막지 않는 것**(§1-4-3)은 **쓰기 측 결함**이고 이 설계가 고치지 않는다. 읽기에서 누설을 막을 뿐이다. 쓰기에서 거부해야 하는지는 Codex 판단을 받는다 — 막으면 기존 행 중 위반이 있을 수 있어 backfill 조사가 필요하다.
4. **`eval_runs`·`approvals`·`code_commits`에 project 컬럼이 없는 것**을 이 카드가 바꾸지 않는다. 필요하다고 판단되면 별 카드(migration + backfill)다.
5. `container_images`는 project 컬럼이 있으므로 §6-3 join 대상이다. `REQUIRED_KINDS`에 없다는 사실(§1-2)은 유지한다 — 이미지 없는 모델도 완전 추적일 수 있다.
6. 순방향 trace의 kind별 상한 200은 관례를 따른 값이고 측정 근거가 없다. 구현 PR에서 사전 등록한다.

## 12. 요약

- `trace_model`은 있는데 **HTTP로 도달할 수 없고**, 역조회는 **함수부터 없다**(§1-1).
- 계약 변경은 **라우트 2개 + 응답 타입 2개 = 4건**이고 **새 오류 code 0개**다. 응답 타입은 `schemas.py`의 `Strict` 클래스이고 정본 `core.schema.json`은 무변경이다(§2·§9).
- project 범위가 테이블마다 달라서 **진입점은 부모 join으로 강제 가능하고 일부 kind는 tenant 범위**다. 응답이 그 구분을 스스로 말한다(§1-4·§3-2).
- 교차 project edge는 **`outOfScope` 개수만** 내어 누설과 위장을 동시에 피한다(§5).
- **인덱스 하나가 필요하고 migration이 필요하다** — `dataset_versions(tenant_id, content_sha256)`, additive·가역(§7).
- 권한은 **live `require_project_access`**(읽기는 membership 등급), 404는 없음과 남의 것을 구분하지 않으며, 오류는 전부 **공유 모듈 `api/problem.py`가 내는 정본 `ProblemDetails`**다 — business `InvError`로는 만들 수 없음을 실측으로 확인했다(§6·§9).
- 되돌리면 실패하는 **부정 시험 25건**(PG-free 18 + 실 PG 7)이고 실 PG 7건의 근거는 hosted CI다(§10).
