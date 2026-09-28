---
doc_id: "CLAUDE-VFCL03-IMPORT-REQUEST-PATH-DESIGN-001"
title: "VF-CL-03 import adapter 요청 경로 결속 설계 — blocker import-adapter-has-no-request-path-contract 해소"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:36:30+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
task_ids: ["VF-CL-03"]
tags: ["vf-cl-03", "model-registry", "import", "design", "contract-change", "claude"]
---

# VF-CL-03 import adapter 요청 경로 결속 설계

blocker `import-adapter-has-no-request-path-contract` 해소안. 근거는 Codex 공백 재검토(#147 §4)와 제 #139 대장 §6-2다. **설계만이고 구현은 승인 뒤 별도 PR이다.** 실행 0건 — 아래 사실은 전부 `grep`/정독이다.

> **v1.1 변경 요약** (Codex 계약 검토 F-R1~F-R5 반영, `f303aec2` 대상)
> - **F-R1**: 권한을 `principal.require_project`(snapshot)에서 **`services.projects.require_project_access()`(live)** 로 바꾸고, 필요한 permission을 **`canApprove`** 로 확정. `get_session`을 **쓰지 않고** 3구간(인증 → 짧은 tx 권한 → tx 종료 → 커널 HTTP → 새 tx 원자 구간)으로 재설계(§6).
> - **F-R2**: `ModelCommitObservation`에 `observedAt`이 없다는 지적 수용. **freshness 주장을 철회**하고 경계를 "최종 tx의 live grant 재확인"으로 다시 씀. consumer 측 strict 검증 추가(§5).
> - **F-R3**: 새 route의 **모든** 오류를 정본 `ProblemDetails`로 고정. top-level `mismatches`·`fields` 금지. 새 code는 **`MODEL-0009` 하나**이고 나머지는 기존 정본 code 재사용. 계약 변경 수 **재계산**(§4·§7).
> - **F-R4**: `(tenant, project, model, version)` → project 소유 model → version row 잠금 → 관측 identity 재결속 순서 확정. 응답 계약·status code **지금 확정**(§7).
> - **F-R5**: 부정 시험 7건 추가(총 19건, §9).
>
> **v1.2 변경 요약** (Codex 재검토의 F-R3 잔존 2건 + 코디네이터 10:25 결정, `99018d9c` 대상)
> - **F-R3-1**: business `InvError`로는 `MODEL-0009`·`SYS-0001`을 **만들 수 없다**는 지적이 맞다(`category_of()`가 10개 prefix만 허용). 코디네이터 결정대로 선택지 **(b)를 route 전용이 아닌 공유 모듈**로 확정했다 — `src/saintvision/api/problem.py`(신규). 카드 ar(#158)의 lineage route도 같은 모듈을 쓴다. 기존 `InvError`는 이 경계에서 번역하고 release precondition `VAL-SCHEMA`는 `GRAPH-0002`로 번역한다(§7).
> - **F-R3-2**: `body: dict` annotation으로는 `RequestValidationError`를 피할 수 없다는 지적이 맞다. `Request`의 **raw body를 handler가 직접 파싱**하는 경로로 고정하고 malformed JSON·배열·scalar 부정 시험을 넣었다(§6-1·§9-17~19).
> - 그 과정에서 **v1.1의 계약 표면 서술이 틀린 것을 찾았다** — business 요청·응답 타입은 정본 `core.schema.json` `$defs`가 아니라 `api/schemas.py`의 `Strict` 클래스다(§4). 새 code는 `MODEL-0009` + 공유 모듈의 `SYS-0002` **둘**로 재계산한다.
> - business error infrastructure 변경은 **구현 변경 범위로 따로** 적었다(§11-3). 기존 표면 전체 정리(선택지 (a))는 이번 범위가 아니다.

## 1. 실측한 현재 상태

### 1-1. adapter는 있고 호출부가 시험뿐이다

`src/saintvision/adapters/model_import.py`: `DECLARED_FIELDS = ("licensePolicy", "classification")`, `compare_declaration()`(이유를 `missing:`·`differs:`·`extra:`·`undeclared:` 토큰으로만, **값 없음**), `require_exact_declaration()`, `declaration_mismatch()`. 호출부는 `tests/core/test_registry_policy_exact_match.py` **하나뿐**이다.

### 1-2. 막힌 것은 adapter가 아니라 business model-registry lane 전체다

`src/saintvision/services/lineage.py`의 `register_model_version`(184) · `verify_model_version`(271) · `pin_retention`(292) · `release_model_version`(308) 네 함수의 호출부가 `src/saintvision/api/`·커널 양쪽에서 **0건**이다. adapter 한 줄을 서비스에 끼워 넣고 blocker를 닫으면 그 문장("no request path")은 여전히 참이다.

### 1-3. 선언은 이미 business에 서빙된다 — 커널 변경 불필요

`services/control-plane/src/inv/app.py:449` `GET …/commitment` → `ModelCommitObservation`, `:454` `…/execution-manifest` → `ModelExecutionManifestObservation`. 두 정본 타입 모두 `additionalProperties: false`이고 `licensePolicy`(string 1~200)·`classification`(enum public·internal·restricted)을 `required`에 담는다. manifest 테이블은 커널 소유이고 `inv_app`은 SELECT 불가(VF-CL-02 확정) — **이 설계는 grant를 추가하지 않는다.**

### 1-4. 권한 snapshot은 권한 근거가 아니다

`src/saintvision/identity/principal.py:42-50`이 스스로 적는다 — `project_ids`는 snapshot이고 **양방향으로 틀린다**(가입 후 생성된 project는 빠지고, 회수된 membership은 토큰 만료까지 남는다). live 대체는 `services.projects.require_project_access()`(`src/saintvision/services/projects.py:204`)이며 그것이 `project_members`를 조회 시점에 읽고 `settings_service.effective_permission()`을 돌려준다.

### 1-5. `get_session`은 handler 진입 전에 트랜잭션을 연다

`src/saintvision/api/deps.py:59` `get_session`은 `session.begin()`과 `tenant_scope()`를 **handler 앞에서** 연다. 그래서 이 dependency를 받으면서 "커널 HTTP를 트랜잭션 밖에서" 하는 것은 **성립하지 않는다**(v1.0의 모순). 자체 세션 관리 전례가 이미 있다 — `src/saintvision/api/v1/nodes.py:75-78`과 `pools.py:196-199`가 `make_session_factory(request.app.state.engine)` 뒤 `with factory() as session: with session.begin(): with tenant_scope(...)`를 직접 쓴다.

### 1-6. business `InvError`로는 정본 `ProblemDetails`를 만들 수 없다 (v1.2 확장 실측)

v1.1은 "패턴이 안 맞고 `extra`가 top-level로 올라간다"까지만 적었다. Codex 재검토의 지적을 받아 **여섯 곳을 전수 확인**했고, 전부 사실이다.

| 실측 | 위치 | 결과 |
|---|---|---|
| `category_of()`가 `VAL·AUTH·CTX·TOOL·RES·NET·GRAPH·VERIFY·SEC·BUDGET`만 허용 | `errors.py:18-28`·`:62-69` | `InvError("MODEL-0009", …)`·`InvError("SYS-0001", …)`는 **`__post_init__`에서 `ValueError`** |
| `to_problem()`의 `type`이 `https://saintvision.invenio/problems/<code>` | `errors.py:59`·`:106` | 정본은 `const: "about:blank"` → **위반** |
| `_problem()`이 `instance=str(request.url.path)`를 넣는다 | `api/app.py:100` | `instance`는 정본 properties에 **없고** `additionalProperties: false`다 → **위반** |
| `detail`을 `public`일 때만 넣는다 | `errors.py:112-113` | 정본 `required`에 `detail`이 있다 → 비공개 오류는 **required 누락** |
| `problem.update(self.extra)` | `errors.py:120` | top-level 임의 key(`mismatches`) → **위반** |
| `_STATUS`/`_RETRYABLE`이 `RES`를 409·retryable **true**로 둔다 | `errors.py:36`·`:50` | `RES-0004`는 404·false여야 한다 → 카테고리 기본값 사용 불가 |
| `_validation_error` 핸들러가 `extra={"fields": …}` | `api/app.py:129-138` | top-level `fields` → **위반** |

**정본 쪽이 막는 것은 하나도 없다.** `ProblemDetails.category`는 `^[A-Z]+$`이고, 커널이 이미 `MODEL-0001`~`MODEL-0008`·`SYS-0001`을 `problem()`(`services/control-plane/src/inv/app.py:24-41`)으로 내며 그 함수가 `validate_contract("ProblemDetails", body)`를 통과한다. 즉 **`MODEL`·`SYS` category는 정본에서 이미 살아 있고, 막는 것은 business `InvError` 한 곳이다.** Codex가 적은 대로 `SYS-0001`의 "기존 관례"는 커널 `DomainError`의 것이지 business 오류 타입의 것이 아니다 — v1.1이 그 둘을 뭉갠 것을 정정한다.

### 1-7. 정본 code 재고 (실측)

- `MODEL-*` 사용: `MODEL-0001`~`MODEL-0008` → **`MODEL-0009`가 다음 빈 번호다.**
- `SYS-0001` = 503 "…unavailable"의 기존 **커널** 관례(`services/control-plane/src/inv/app.py:205`·`:462`·`:629`·`:932`). business 쪽 관례가 아니므로 §7의 공유 모듈을 통해서만 낸다.
- `SYS-0002` = **미사용**(위 grep에 `SYS-0002`가 0건). §7이 공유 모듈의 미매핑 fallback으로 쓴다.
- `AUTH-0030` = project permission 거부·불가. `RES-0004` = not found. `VAL-0003` = 요청 검증. `GRAPH-0002` = 상태 전제 미충족(`DomainError` 기본 status **409**, `errors.py:8`).

## 2. 결속 지점

| 후보 | 판단 |
|---|---|
| A. 서비스 계층만 | 계약 변경 0이지만 **blocker를 닫지 못한다** |
| **B. 서비스 + 새 route** (권고) | blocker를 문구대로 닫고 커널 무변경 |
| C. 커널 manifest commit 시점 | manifest가 곧 선언이라 자기 자신과 비교. importer 주장이 도착하는 곳이 아니고 owner도 다르다 |

**draft가 아니라 release**인 이유: 선언은 커널이 run 결과로 commit하는 manifest에서 나오므로 draft 시점엔 비교 대상이 없을 수 있다. `release_model_version`은 docstring이 *"released is the point at which someone may deploy it"*이라 적고 이미 unverified·unpinned·untraceable을 거부하는 **기존 검사 단계**다.

## 3. 필요한 live permission — `canApprove`

`require_project_access()`가 돌려주는 permission dict는 `roleCode`·`canRequest`·`canApprove`를 담는다(`services/settings.py::effective_permission`). release는 **배포 가능 상태로 승격**하는 행위이고 `release_model_version` docstring이 그 점을 명시하므로, 요청 등급이 아니라 **승인 등급**이다. 따라서 **`canApprove`가 true여야 한다**. `canRequest`만으로는 부족하다.

현재 business route 중 `canApprove`를 **강제**하는 곳은 없고 보고만 한다(`services/projects.py:199`). 이 route가 그 첫 강제 지점이 된다는 사실을 적어 둔다 — 조용한 선례가 되지 않게.

## 4. 계약 변경 — 재계산 (F-R3·F-R4)

v1.0은 "route + request 1건"이라고 적었다. 정본 `ProblemDetails`와 응답 계약을 확정하면 **3건 + code 2개**다(v1.2에서 code를 1개→2개로 재계산: `MODEL-0009` + 공유 모듈의 `SYS-0002`).

| # | 항목 | 내용 |
|---|---|---|
| 1 | **새 route** | `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/release` |
| 2 | **새 요청 타입** `ModelReleaseRequest` | `api/schemas.py`의 `Strict` 파생 클래스(`extra="forbid"`, `populate_by_name=True`) → 생성 schema가 `additionalProperties: false`, `required: [licensePolicy, classification]`, 제약은 `ModelManifest`에서 복제 |
| 3 | **새 응답 타입** `ModelReleaseResult` | 같은 `Strict` 파생. `required: [modelVersionId, modelId, version, stage, contentSha256]`, `stage`는 **`Literal["released"]`**(생성 schema에서 `const`). status **200** |
| — | **새 정본 code 2개** | `MODEL-0009`(선언 불일치, 409)와 `SYS-0002`(공유 모듈의 미매핑 fallback, 500). `ProblemDetails.code`는 enum이 아니라 패턴이므로 **JSON Schema 변경은 없다**. 그래도 새 공개 오류 신원이므로 여기 센다. **`SYS-0002`는 공유 모듈의 것이고 카드 ar(#158)은 세지 않는다** — 같은 code를 두 카드가 각각 세면 분모가 부풀어 오른다 |

기존 표현을 재사용할 수 있는지 확인했다 — 정본 `$defs`에 model version을 나타내는 응답 타입이 **없다**(`Model*`은 `ModelManifest`·`ModelShard`·`ModelReplica`·`ModelExecutionRef`·두 Observation·`ModelRetry*`·`ModelId`뿐). 그래서 3번은 신설이다.

**어디에 신설하는지를 v1.2에서 고친다.** v1.1은 정본 `$defs` 추가와 TS/Go 생성을 동반 산출물로 적었는데 그것은 **커널 정본의 절차**였다. 실측: business 요청·응답 타입은 `src/saintvision/api/schemas.py`의 `Strict` 파생 Pydantic 클래스이고, 그 파일이 *"these Pydantic models are the source, and `tools/export_schemas.py` emits the JSON Schema from them — one direction"*이라 적는다. `tools/check_response_freshness.py:32`도 `"kernel" = core.schema.json $def; "saintvision" = a schemas.py class`로 두 표면을 구분한다.

따라서 동반 산출물은 — `schemas.py`에 `Strict` 클래스 2개, `python tools/export_schemas.py`로 `contracts/model-release-request.schema.json`·`contracts/model-release-result.schema.json` 생성, `.github/workflows/backend.yml:78`의 `export_schemas.py --check` drift 0, `tests/test_route_coverage.py` 반영이다. 클래스는 `exported()`가 **열거가 아니라 탐색**으로 찾으므로 목록 갱신은 없다. **TS/Go 생성과 `generate_contracts.py`는 커널 전용이라 이 카드의 산출물이 아니다 — v1.1의 목록을 철회한다.**

이 정정은 §6-1에도 영향을 준다: `validate_contract("ModelReleaseRequest", …)`는 **불가능**하다(그 함수는 정본 `$defs`를 찾고 `ModelReleaseRequest`는 거기 없다). 대신 handler가 `ModelReleaseRequest.model_validate(...)`를 부르고 `pydantic.ValidationError`를 잡아 `VAL-0003`으로 번역한다. 커널 관측 검증(`validate_contract("ModelCommitObservation", …)`)은 정본 `$def`이므로 그대로다.

커널 schema·라우트·migration·registry status 변경은 **없다**.

## 5. 어느 관측을 쓰는가 — `ModelCommitObservation`, freshness 주장 철회 (F-R2)

**`ModelCommitObservation`을 쓴다. v1.0의 freshness gate는 철회한다.**

근거: `ModelCommitObservation`의 정본 required에는 `committedAt`이 있고 **`observedAt`은 없다**(`observedAt`은 `ModelExecutionManifestObservation`에만 있다). `model_view.py::ModelCommitObservation.get()`도 `committedAt`만 낸다. 그러므로 v1.0 §6-2의 "`observedAt`이 한계 초과면 거부"와 §9의 숫자 결정은 **이 계약으로 구현 불가능하다.**

그리고 더 근본적으로 **freshness가 이 비교의 방어가 아니다**: 선언은 **불변 manifest**의 값이므로 오래된 관측도 여전히 옳다. 그 사이에 바뀔 수 있는 것은 **선언이 아니라 권한**이고, 그것은 §6의 최종 트랜잭션 재확인이 덮는다. 따라서 경계를 이렇게 다시 쓴다.

- `committedAt`은 **기록된 provenance**로만 쓰고 freshness 판정에 쓰지 않는다.
- `committed != true`면 거부한다 — 아직 불변이 아닌 선언과는 비교하지 않는다.
- 관측을 신선하게 유지하는 대신 **권한을 최종 구간에서 다시 읽는다**(§6-5).

`ModelExecutionManifestObservation`을 쓰지 않는 이유: `observedAt`은 얻지만 `executionAuthorized`·`requiresExecutionRevalidation`·shard/location까지 딸려 와 **실행 준비**의 의미가 섞인다. 승격은 실행 승인이 아니다(adapter docstring의 경계와 같다).

**consumer 측 strict 검증**: 받은 본문을 `validate_contract("ModelCommitObservation", body)`로 검증한다. 커널이 보냈다는 사실을 검증의 대체로 삼지 않는다. malformed·extra·missing·const 위반·identity 불일치는 전부 **fail-closed**이며 `stage`는 바뀌지 않는다(§9-10~13).

## 6. 검사 순서 — 3구간 (F-R1)

`get_session`을 **쓰지 않는다**(§1-5). `get_principal`로 인증만 받고 세션은 직접 관리한다(`nodes.py:75-78` 전례).

1. **(트랜잭션 없음)** `get_principal`로 인증. **요청 본문은 handler가 raw로 파싱한다(v1.2, F-R3-2)** — `body: dict` annotation으로는 `RequestValidationError`를 피할 수 없기 때문이다(FastAPI가 handler 진입 **전에** 검증하고 전역 핸들러가 top-level `fields`를 붙인다). 고정 경로:
   1. 서명은 `async def release(request: Request, project_id: str, model_id: str, version: str)` — **제약 annotation을 쓰지 않는다**(제약 없는 `str` path 변수는 검증 예외를 만들지 않는다).
   2. `raw = await request.body()` → 빈 본문이면 `VAL-0003` 422.
   3. `json.loads(raw)` → `json.JSONDecodeError`는 `VAL-0003` 422(**malformed JSON**).
   4. `isinstance(parsed, dict)`가 아니면 `VAL-0003` 422(**배열·scalar·null**). 이것이 "JSON이 object가 아닌" 경우다.
   5. `ModelReleaseRequest.model_validate(parsed)` → `pydantic.ValidationError`를 잡아 `VAL-0003` 422. **`exc.errors()`를 body에 싣지 않는다**(필드 경로도 top-level key도 없다). 미지 필드는 `extra="forbid"`가 여기서 거부한다.
   6. 모든 `VAL-0003`은 §7 공유 모듈이 만든 정본 body다 — 여섯 갈래가 **같은 키 집합**을 낸다.
2. **(짧은 tx #1)** `tenant_scope` 안에서 `require_project_access(session, tenant_id=…, project_id=…, user_id=…)` → 반환 permission의 `canApprove`가 false면 `AUTH-0030` 403. **트랜잭션을 닫는다.**
3. **(트랜잭션 없음)** 커널 `…/commitment` 호출 → `validate_contract("ModelCommitObservation", …)`. 실패·도달 불가는 `SYS-0001` 503 **retryable**. `committed != true`면 `GRAPH-0002` 409.
4. **(tx #2 — 원자 구간 시작)** `tenant_scope` 안에서:
   1. `require_project_access` **재확인** + `canApprove` 재확인 → 회수됐으면 `AUTH-0030` 403이고 **`stage`는 바뀌지 않는다**. (2와 4-1 사이의 권한 회수 TOCTOU를 이것이 막는다.)
   2. **정본 lookup**: `models`에서 `(tenant_id, model_id)`를 찾고 `project_id == path project`인지 확인 → 아니면 `RES-0004` 404. 이어서 `model_versions`에서 `(model_id, version)` 행을 **`with_for_update()`로 잠근다** → 없으면 `RES-0004` 404. **다른 project·다른 tenant·부재는 모두 같은 404다**(§8).
   3. **관측 identity 재결속**: 관측의 `projectId`·`modelId`·`version`이 path와 잠근 행의 값과 **모두** 같은지 확인 → 아니면 `RES-0004` 404(존재를 드러내지 않는다).
   4. 기존 승격 전제 검사 — `verified_at`·`retention_pinned_until`·`trace_model().missing`(`lineage.py:324`·`:326`·`:332`). 미충족은 `GRAPH-0002` 409. **순서를 바꾸지 않는다: 기존 거부가 먼저다.**
   5. **`require_exact_declaration(manifest=관측의 두 필드, proposal=요청의 두 필드)`** → 불일치는 `MODEL-0009` 409.
   6. `row.stage = "released"` → `flush`.
   7. 감사: `record_event`를 같은 `tenant_scope` 안에서. `detail`에는 **필드 이름만**.
5. 커밋. 4-1~4-7이 **한 트랜잭션**이므로 권한 재확인과 release가 쪼개지지 않는다.

5를 4보다 앞에 두지 않는 이유(4-4 → 4-5 순서): 선언 불일치는 409이고 전제 미충족도 409지만 **뜻이 다르다**. 검증 안 된 버전에 선언 불일치를 먼저 말하면 "선언만 맞추면 승격된다"로 읽힌다.

**커널 HTTP는 3에서만 일어나고 그 순간 열린 DB 트랜잭션이 없다.** 이것을 부정 시험으로 고정한다(§9-8).

## 7. 정본 `ProblemDetails`는 **공유 모듈**이 낸다 (F-R3, v1.2)

### 7-1. 결정: 선택지 (b)를 route 전용이 아닌 공유 모듈로

Codex가 준 (a)(b) 중 코디네이터가 **(b)를 공유 모듈로** 결정했다 — 새 business route가 함께 쓰는 정본 예외와 handler를 한 곳에 둔다. **`src/saintvision/api/problem.py`(신규)** 이고, 이 카드의 release route와 카드 ar(#158)의 lineage route **둘 다** 이것을 쓴다. route마다 `JSONResponse`를 여섯 군데 만드는 방식은 Codex가 지적한 drift 때문에 쓰지 않는다.

요구 사항 넷:

1. **required exact key 집합**: `type·title·status·code·category·detail·retryable·traceId·causeRef·evidenceId` 정확히 10개. **`instance` 없음**(정본 properties에 없다), **`extra` 병합 없음**, **`detail`은 항상 존재**(비공개 사유일 때도 code별 고정 문구 — required이므로 생략할 수 없다).
2. **`type: "about:blank"`** 고정.
3. **`MODEL`·`SYS` category 지원**: category를 `code.split("-", 1)[0]`에서 파생하고 **enum 화이트리스트를 두지 않는다**(정본 제약이 `^[A-Z]+$`이므로 그것이 유일한 제약이다). status·retryable은 카테고리 기본값 표가 아니라 **code별로 명시**한다 — `errors.py`의 `_STATUS`/`_RETRYABLE`이 `RES`를 409·retryable true로 두므로 기본값을 쓰면 `RES-0004`가 틀린다.
4. **정본 앵커**: body를 만든 뒤 `from inv.contracts import validate_contract`로 `validate_contract("ProblemDetails", body)`를 호출한다. business 제품 코드가 `inv`를 import하는 전례가 있다(`server.py:2`, `identity/oidc.py:72`). 커널 `problem()`과 **같은 앵커**를 쓰므로 두 표면이 갈라질 수 없다.

`traceId`는 `request.state.trace_id`(`api/app.py:90-96`의 `_trace` 미들웨어) 또는 `ids.new_trace_id()`이고 둘 다 32 hex라 정본 `TraceId`(`^[0-9a-f]{32}$`)를 만족한다. 응답은 `application/problem+json` + `Cache-Control: no-store`(커널 `problem()`과 동일)다. handler는 `create_app`에 `@app.exception_handler(...)`로 한 번 등록하고, **기존 `InvError`·`RequestValidationError` 핸들러는 건드리지 않는다**(§11-3).

### 7-2. 이 route의 오류 표 (변동 없음, 한 줄 추가)

| 상황 | code | status | retryable |
|---|---|---|---|
| 요청 본문 위반(빈 본문·malformed JSON·배열·scalar·미지 필드·제약 위반) | `VAL-0003` | 422 | false |
| `canApprove` 없음 / project 접근 불가 | `AUTH-0030` | 403 | false |
| model·version 부재, 다른 project, 다른 tenant, identity 불일치 | `RES-0004` | 404 | false |
| 승격 전제 미충족(unverified·unpinned·untraceable), `committed != true` | `GRAPH-0002` | 409 | false |
| 커널 관측 도달 불가·schema 위반 | `SYS-0001` | 503 | **true** |
| **선언 불일치** | **`MODEL-0009`** | 409 | false |
| **(v1.2) 번역표에 없는 business code** | **`SYS-0002`** | 500 | false |

### 7-3. 기존 `InvError`는 이 경계에서 번역한다

| 서비스·adapter가 던지는 것 | 이 route의 정본 code |
|---|---|
| `release_model_version`의 `VAL-SCHEMA`(unverified·unpinned·untraceable — `lineage.py:324`·`:326`·`:331`) | **`GRAPH-0002` 409** |
| adapter의 `VAL-MODEL-IMPORT-DECLARATION` | `MODEL-0009` 409 |
| `AUTH-PROJECT-SCOPE` / `require_project_access` 거부 | `AUTH-0030` 403 |
| `_load_model_version`의 부재 | `RES-0004` 404 |

`VAL-SCHEMA`→`GRAPH-0002`는 코디네이터 결정대로 이 경계에서 한다. **다만 전역 규칙이 아니다**: 같은 `VAL-SCHEMA`가 카드 ar의 lineage route에서는 digest·커서 형식 위반이라 `VAL-0003` 422로 번역된다. 한 business code의 뜻이 호출 지점마다 다르다는 것이 실측이므로, 모듈은 **route별로 명시한 매핑**을 받고 전역으로 추측하지 않는다. `errors.py`·adapter·서비스는 **바꾸지 않는다**.

**표에 없는 code**는 정본 신원으로 꾸미지 않는다. 우리 장부에 기록된 실패를 되풀이하지 않기 위해서다 — 타 tenant model-retry가 `503 SYS-0001`로 새어 *"클라이언트가 서버 장애로 오해해 재시도하고 운영 알람에 503으로 잡힌다"*가 F1로 남아 있다(`History/2026-09-22_결정6a_model-retries_통합검증_실PG_실HTTP_Claude.md`). 그래서 미매핑은 **`SYS-0002` 500 · retryable false**다 — 우리 쪽 매핑 누락이므로 "일시적 장애"도 아니고 재시도도 의미가 없다. 그리고 **PG-free 시험이 이 route에서 도달 가능한 business code를 열거해 표가 그것을 모두 덮음을 요구**하므로(§9-23) `SYS-0002`는 계약이 깨지지 않게 두는 자리이고 실제로는 도달하지 않는다.

### 7-4. 불일치 이유를 어디에 싣는가 (변동 없음)

top-level key는 쓸 수 없으므로 **`detail` 문자열에 필드 이름만** 넣는다 — 예 `"import proposal differs from the immutable manifest declaration: missing:classification"`. 값은 여전히 어디에도 없다. `ProblemDetails`에 정식 필드를 추가하는 길은 **공개 계약 확대**이므로 이 카드에서 하지 않는다.

## 8. 권한 경계와 404 정책

1. **tenant(RLS)**: 두 트랜잭션 모두 `tenant_scope` 안. grant 추가 없음.
2. **project(live)**: `require_project_access()` + `canApprove`, **2와 4-1 두 번**.
3. **행 수준**: `models.project_id`로 소유를 확인한 뒤에만 version 행을 잠근다(§6-4-2). `model_versions`에는 `project_id` 컬럼이 없으므로 **부모 join이 유일한 경로**다.
4. **404 정책**: 부재·다른 project·다른 tenant·identity 불일치를 **모두 같은 `RES-0004` 404**로 낸다. `require_project_access`가 이미 같은 원칙을 쓰고("Reports the same denial whether the project does not exist or the caller simply cannot see it"), 403은 **그 project에 대한 접근 자체가 없을 때**만이다.

## 9. 부정 시험 — 되돌리면 실패해야 하는 것 (총 26건)

**PG-free** (`tests/core/`):

1. `require_exact_declaration` 호출 제거 → 불일치 제안이 승격에 성공한다.
2. 4-4와 4-5 순서 뒤집기 → unverified 버전에 `GRAPH-0002`가 아니라 `MODEL-0009`가 나온다.
3. 관측 identity 재결속(4-3) 제거 → 다른 model/version의 관측으로 승격이 성공한다.
4. `committed != true` 거부 제거 → 미commit 선언으로 승격이 성공한다.
5. `extra`/`detail`에 값 넣기 → "본문·감사에 두 필드의 **값**이 없다" 단언이 실패한다.
6. 요청 schema의 `additionalProperties: false` 완화 → 미지 필드가 422로 거부되지 않는다.
7. `canApprove` 검사를 `canRequest`로 바꾸기 → 요청 등급 principal이 승격에 성공한다.
8. **(F-R5) 커널 HTTP 호출 시점에 열린 business 트랜잭션이 0건**임을 단언 — `get_session`을 쓰거나 3을 tx 안으로 옮기면 실패한다.
9. **(F-R5) 2 통과 후 membership/`canApprove` 회수 → 4-1에서 403이고 `stage`·감사 행 불변.**
10. **(F-R5) 관측 strict 검증 — missing 필드** → fail-closed, `stage` 불변.
11. **(F-R5) 관측 strict 검증 — extra 필드** → fail-closed(`additionalProperties: false`), `stage` 불변.
12. **(F-R5) 관측 strict 검증 — const/enum drift**(예 `classification`이 enum 밖) → fail-closed.
13. **(F-R5) 관측 identity mismatch**(projectId·modelId·version 중 하나가 다름) → 404, `stage` 불변.
14. **(F-R5) 정본 `ProblemDetails` exact key set** — 여섯 오류 각각의 `code`·`status`·`retryable`이 §7 표와 같고, top-level에 `mismatches`·`fields` 같은 임의 key가 **없다**. 요청 검증 오류에도 없다.
15. **(F-R5) `(model_id, version)` lookup/lock 제거 또는 다른 `model_version_id` 선택** → 잘못된 행이 release되거나 잠금 없이 진행된다.
16. **(F-R5) 확정된 성공 응답의 missing/extra 필드 거부** — `ModelReleaseResult`가 `stage: "released"` const를 포함해 exact key set으로 검증된다.

**PG-free 추가 (v1.2, F-R3)**:

17. **malformed JSON 본문**(`{"licensePolicy":`) → `VAL-0003` 정본 body이고 top-level `fields`가 **없다**. `body: dict` annotation으로 되돌리면 `fields`가 붙어 실패한다.
18. **top-level 배열 본문**(`[{…}]`) → 같은 `VAL-0003` 정본 body. 무시하거나 첫 원소를 쓰지 않는다.
19. **scalar 본문**(`"released"`·`3`·`null`) → 같은 `VAL-0003` 정본 body.
20. `ModelReleaseRequest.model_validate`의 `ValidationError`를 그대로 직렬화하면 → 필드 경로·입력 값이 body에 들어가 "값 미노출"·"exact key set" 단언이 함께 실패한다.
21. 공유 모듈을 `InvError`로 되돌리면 → `MODEL-0009`·`SYS-0001` 생성이 `category_of()`에서 `ValueError`가 되어 **오류 경로 자체가 500으로 무너진다**(§1-6).
22. 모듈의 `validate_contract("ProblemDetails", …)` 호출을 지우면 → `instance`를 다시 넣거나 `detail`을 빼도 통과한다(정본 앵커 회귀).
23. 번역표에서 한 항목을 지우면 → 그 실패가 `SYS-0002` 500으로 떨어지고, **도달 가능 business code 열거 시험이 표 미충족으로 실패**한다(§7-3).

**실 PG** (단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

24. RLS: 다른 tenant의 model version은 404이고 행이 바뀌지 않는다.
25. path project와 model 소유 project 불일치 → **타 tenant와 같은 404**, 행 불변.
26. 양성 대조: 검증·pin·trace 완비 + 선언 일치 + `canApprove` → 200 `ModelReleaseResult`, `stage='released'`, 감사 1행(값 없음).

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 24~26의 실행 근거는 hosted CI다.

## 10. 값 미노출 규칙

- adapter가 이유를 `missing:`·`differs:`·`extra:`·`undeclared:` 토큰으로만 만든다 — 값 없음이 구현으로 보장된다.
- route는 그 토큰을 `detail` 문자열에만 넣고 top-level key를 만들지 않는다(§7).
- 감사 `detail`도 필드 이름만. **`services/audit.py::redact`의 marker에 `license`·`classification`이 없다**(실측: secret·token·password·credential·authorization·signature·presigned·url·prompt·key) → 값을 넣으면 자동으로 걸러지지 않으므로 **넣지 않는 것이 유일한 방어**이고 §9-5가 그것을 고정한다.

## 11. 범위 밖 · 미해결

1. **쓰기 라우트 전체는 범위 밖이다.** `register_model_version`·`verify_model_version`·`pin_retention`에는 여전히 요청 경로가 없다. 이 설계는 승격 한 지점만 연다 — blocker를 닫은 뒤에도 그 사실은 장부에 남아야 한다.
2. `canApprove`를 강제하는 **첫 business route**가 된다(§3). 다른 승격류 행위에도 같은 등급을 적용할지는 별 결정이다.
3. **business error infrastructure 변경 = 구현 변경 범위 (v1.2 명시)**. 이 카드가 만드는 것은 **`src/saintvision/api/problem.py` 신설 + `create_app`에 handler 1개 등록 + 이 route가 그 모듈 사용**까지다. `errors.py`·`InvError`·`_inv_error`·`_validation_error`·기존 `nodes`·`pools`·`storage` 라우트는 **건드리지 않는다** — 기존 오류 표면 전체의 정본화(Codex 선택지 (a))는 코디네이터 결정대로 이번 범위가 아니고, 그 분기는 §1-6에 드러내 둔다. 모듈은 카드 ar(#158)과 **공유**하므로 **먼저 착지하는 쪽이 만들고 나중 쪽은 재사용한다**(두 PR이 같은 파일을 각각 만들면 충돌한다).
4. adapter는 **변경하지 않는다**. route가 `InvError`를 정본 오류로 번역한다(§7).
5. `MODEL-0009`·**`SYS-0002`** 번호 확정과 `SYS-0001` 재사용 판단은 Codex 확인 대상이다. `SYS-0002`는 grep 0건이라 비어 있음을 확인했을 뿐, 커널 쪽 예약 의도는 내가 알 수 없다.
