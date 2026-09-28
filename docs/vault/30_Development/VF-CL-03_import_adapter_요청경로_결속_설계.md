---
doc_id: "CLAUDE-VFCL03-IMPORT-REQUEST-PATH-DESIGN-001"
title: "VF-CL-03 import adapter 요청 경로 결속 설계 — blocker import-adapter-has-no-request-path-contract 해소"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:17:03+09:00"
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

### 1-6. business 오류 표면은 정본 `ProblemDetails`가 아니다

`ProblemDetails`는 `code` 패턴 `^[A-Z]+-[0-9]{4}$`와 `additionalProperties: false`를 요구한다. business 어휘(`VAL-SCHEMA`·`AUTH-PROJECT-SCOPE`·adapter의 `VAL-MODEL-IMPORT-DECLARATION`)는 **패턴에 맞지 않고**, `InvError.to_problem()`(`errors.py:104-121`)의 `problem.update(self.extra)`가 `mismatches`를, 앱 전역 `_validation_error` 핸들러가 `fields`를 **top-level에 올린다**. v1.0은 이것을 "기존 분기"로 두고 넘어갔으나, **새 공개 route까지 비정본으로 만들 근거가 아니다**(F-R3 수용).

### 1-7. 정본 code 재고 (실측)

- `MODEL-*` 사용: `MODEL-0001`~`MODEL-0008` → **`MODEL-0009`가 다음 빈 번호다.**
- `SYS-0001` = 503 "…unavailable"의 기존 정본 관례(`app.py`의 configuration/resolver unavailable).
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

v1.0은 "route + request 1건"이라고 적었다. 정본 `ProblemDetails`와 응답 계약을 확정하면 **3건 + code 1개**다.

| # | 항목 | 내용 |
|---|---|---|
| 1 | **새 route** | `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/release` |
| 2 | **새 요청 타입** `ModelReleaseRequest` | `additionalProperties: false`, `required: [licensePolicy, classification]`, 제약은 `ModelManifest`에서 복제 |
| 3 | **새 응답 타입** `ModelReleaseResult` | `additionalProperties: false`, `required: [modelVersionId, modelId, version, stage, contentSha256]`, `stage`는 **`const: "released"`**. status **200** |
| — | **새 정본 code 1개** | `MODEL-0009`(선언 불일치, 409). `ProblemDetails.code`는 enum이 아니라 패턴이므로 **JSON Schema 변경은 없다**. 그래도 새 공개 오류 신원이므로 여기 센다 |

기존 표현을 재사용할 수 있는지 확인했다 — 정본 `$defs`에 model version을 나타내는 응답 타입이 **없다**(`Model*`은 `ModelManifest`·`ModelShard`·`ModelReplica`·`ModelExecutionRef`·두 Observation·`ModelRetry*`·`ModelId`뿐). 그래서 3번은 신설이다.

커널 schema·라우트·migration·registry status 변경은 **없다**. 동반 산출물: JSON Schema, 생성 TS/Go/Python, fixture, 서빙 앵커, `generate_contracts.py` drift 0, `tests/test_route_coverage.py`.

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

1. **(트랜잭션 없음)** `get_principal`로 인증. 요청 본문을 `validate_contract("ModelReleaseRequest", body)`로 검증 — FastAPI의 `RequestValidationError`가 앱 전역 핸들러에 닿지 않게 **본문을 dict로 받아 직접 검증**한다(§1-6의 top-level `fields` 회피). 위반은 `VAL-0003` 422.
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

## 7. 정본 `ProblemDetails` 고정 (F-R3)

이 route의 **모든** 오류는 정본 `ProblemDetails`다 — `code`가 `^[A-Z]+-[0-9]{4}$`, 키 집합은 정본 required와 정확히 일치, **top-level 임의 key 금지**(`mismatches`·`fields` 둘 다).

| 상황 | code | status | retryable |
|---|---|---|---|
| 요청 본문이 `ModelReleaseRequest` 위반 | `VAL-0003` | 422 | false |
| `canApprove` 없음 / project 접근 불가 | `AUTH-0030` | 403 | false |
| model·version 부재, 다른 project, 다른 tenant, identity 불일치 | `RES-0004` | 404 | false |
| 승격 전제 미충족(unverified·unpinned·untraceable), `committed != true` | `GRAPH-0002` | 409 | false |
| 커널 관측 도달 불가·schema 위반 | `SYS-0001` | 503 | **true** |
| **선언 불일치** | **`MODEL-0009`** | 409 | false |

**불일치 이유를 어디에 싣는가**: top-level key는 쓸 수 없으므로 **`detail` 문자열에 필드 이름만** 넣는다 — 예 `"import proposal differs from the immutable manifest declaration: missing:classification"`. 값은 여전히 어디에도 없다. `ProblemDetails`에 정식 필드를 추가하는 길은 **공개 계약 확대**이므로 이 카드에서 하지 않는다.

business 어휘를 이 route에 쓰지 않는다. adapter는 내부에서 `InvError`를 던지지만 route가 그것을 잡아 `MODEL-0009` 정본 오류로 **번역**한다(adapter 자체는 바꾸지 않는다). exact schema 시험을 둔다(§9-14).

## 8. 권한 경계와 404 정책

1. **tenant(RLS)**: 두 트랜잭션 모두 `tenant_scope` 안. grant 추가 없음.
2. **project(live)**: `require_project_access()` + `canApprove`, **2와 4-1 두 번**.
3. **행 수준**: `models.project_id`로 소유를 확인한 뒤에만 version 행을 잠근다(§6-4-2). `model_versions`에는 `project_id` 컬럼이 없으므로 **부모 join이 유일한 경로**다.
4. **404 정책**: 부재·다른 project·다른 tenant·identity 불일치를 **모두 같은 `RES-0004` 404**로 낸다. `require_project_access`가 이미 같은 원칙을 쓰고("Reports the same denial whether the project does not exist or the caller simply cannot see it"), 403은 **그 project에 대한 접근 자체가 없을 때**만이다.

## 9. 부정 시험 — 되돌리면 실패해야 하는 것 (총 19건)

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

**실 PG** (단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

17. RLS: 다른 tenant의 model version은 404이고 행이 바뀌지 않는다.
18. path project와 model 소유 project 불일치 → **타 tenant와 같은 404**, 행 불변.
19. 양성 대조: 검증·pin·trace 완비 + 선언 일치 + `canApprove` → 200 `ModelReleaseResult`, `stage='released'`, 감사 1행(값 없음).

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 17~19의 실행 근거는 hosted CI다.

## 10. 값 미노출 규칙

- adapter가 이유를 `missing:`·`differs:`·`extra:`·`undeclared:` 토큰으로만 만든다 — 값 없음이 구현으로 보장된다.
- route는 그 토큰을 `detail` 문자열에만 넣고 top-level key를 만들지 않는다(§7).
- 감사 `detail`도 필드 이름만. **`services/audit.py::redact`의 marker에 `license`·`classification`이 없다**(실측: secret·token·password·credential·authorization·signature·presigned·url·prompt·key) → 값을 넣으면 자동으로 걸러지지 않으므로 **넣지 않는 것이 유일한 방어**이고 §9-5가 그것을 고정한다.

## 11. 범위 밖 · 미해결

1. **쓰기 라우트 전체는 범위 밖이다.** `register_model_version`·`verify_model_version`·`pin_retention`에는 여전히 요청 경로가 없다. 이 설계는 승격 한 지점만 연다 — blocker를 닫은 뒤에도 그 사실은 장부에 남아야 한다.
2. `canApprove`를 강제하는 **첫 business route**가 된다(§3). 다른 승격류 행위에도 같은 등급을 적용할지는 별 결정이다.
3. business 오류 표면 전체를 정본 `ProblemDetails`로 통일하는 것은 **이 카드 범위 밖**이다. 이 route만 정본을 지키며, 기존 분기는 그대로 드러내 둔다(§1-6).
4. adapter는 **변경하지 않는다**. route가 `InvError`를 정본 오류로 번역한다(§7).
5. `MODEL-0009` 번호 확정과 `SYS-0001` 재사용 판단은 Codex 확인 대상이다.
