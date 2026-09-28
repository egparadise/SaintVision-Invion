---
doc_id: "CLAUDE-VFCL03-IMPORT-REQUEST-PATH-DESIGN-001"
title: "VF-CL-03 import adapter 요청 경로 결속 설계 — blocker import-adapter-has-no-request-path-contract 해소"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf045c5a554209aaef601ae4883b64da50a7"
task_ids: ["VF-CL-03"]
tags: ["vf-cl-03", "model-registry", "import", "design", "contract-change", "claude"]
---

# VF-CL-03 import adapter 요청 경로 결속 설계

blocker `import-adapter-has-no-request-path-contract`(#143 브랜치 `docs/vf-cl-task-registry.json`) 해소안. 근거는 Codex 공백 재검토(#147, History `2026-09-28_16-25`, §4 "adapter는 아직 request/service 경로 계약에 연결되지 않았다")와 제 #139 대장 §6-2다. **설계만이고 구현은 승인 뒤 별도 PR이다.** 실행 0건 — 아래 사실은 전부 `git show`/`grep` 정독이다.

## 1. 실측한 현재 상태

### 1-1. adapter는 있고 호출부가 시험뿐이다

`src/saintvision/adapters/model_import.py`:

- `DECLARED_FIELDS = ("licensePolicy", "classification")`
- `compare_declaration(manifest, proposal) -> list[str]` — 이유를 `missing:<field>` · `differs:<field>` · `extra:<field>` · `undeclared:<field>`로 명명하고 **값은 담지 않는다**
- `require_exact_declaration(...)` — 불일치면 `declaration_mismatch()`가 만든 `InvError`를 raise
- `declaration_mismatch()` — code `VAL-MODEL-IMPORT-DECLARATION`, `status=409`, `public=True`, `extra={"mismatches": [...]}`

호출부는 `tests/core/test_registry_policy_exact_match.py` **하나뿐**이다.

### 1-2. 막힌 것은 adapter가 아니라 **business model-registry lane 전체**다

`src/saintvision/services/lineage.py`의 등록·검증·승격 함수는 전부 HTTP 표면이 없다.

| 함수 | 위치 | 역할 |
|---|---|---|
| `register_model_version` | `lineage.py:184` | `stage="draft"`로 행 생성. 선언 필드 인자 **없음** |
| `verify_model_version` | `lineage.py:271` | 실제 weight 해시 확인, `verified_at` 기록 |
| `pin_retention` | `lineage.py:292` | 보존 pin 연장 전용 |
| `release_model_version` | `lineage.py:308` | `released`로 승격. **이미 검사 단계**다 — unverified·unpinned·untraceable 거부 |

`src/saintvision/api/`와 `services/control-plane/src/`에서 이 네 함수의 호출부를 grep하면 **0건**이다. 즉 blocker의 문구("no request path")는 adapter만의 문제가 아니라 이 lane에 라우트가 아예 없다는 사실이다. **이 구분을 흐리면 안 된다** — adapter 한 줄을 어디에 끼워 넣어 blocker를 "닫았다"고 쓰면 요청 경로는 여전히 없다.

### 1-3. 선언(declaration)은 이미 business에 서빙된다 — 커널 변경 불필요

`services/control-plane/src/inv/app.py`:

- `:449` `GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment` → `ModelCommitObservation`
- `:454` `…/execution-manifest` → `ModelExecutionManifestObservation`
- `:459` `GET /v1/projects/{project}/models/resolve` → VF-CL-02(d) 결속

`contracts/v1alpha1/core.schema.json` 실측 — 세 타입 모두 `additionalProperties: false`이고 **`licensePolicy`와 `classification`을 `required`에 담는다**:

| 타입 | licensePolicy | classification |
|---|---|---|
| `ModelManifest` | `string`, minLength 1, maxLength 200 | `enum: [public, internal, restricted]` |
| `ModelCommitObservation` | 같음 | 같음 |
| `ModelExecutionManifestObservation` | 같음 | 같음 |

manifest 자체는 커널 소유(`inv.model_manifests`, `inv_app`은 SELECT 불가 — VF-CL-02에서 확정)지만, **비교에 필요한 두 값은 이미 관측 라우트가 준다.** 따라서 선언을 얻기 위한 **새 커널 라우트도, 커널 코드 변경도 필요 없다.**

### 1-4. 오류 코드 어휘가 둘이고, adapter의 코드는 계약 패턴에 맞지 않는다

- 커널: `inv.errors.DomainError`, 코드가 `MODEL-0001`·`VAL-0003`·`SYS-0001` 형태. 응답은 `ProblemDetails`로 계약 검증된다(`tests/core/test_identity.py:137·158`, `tests/integration/test_model_execution_manifest_http.py:79·199·202`).
- business: `saintvision.errors.InvError`, 코드가 `VAL-SCHEMA`·`RES-ARTIFACT-NOT-FOUND` 형태(`src/saintvision/errors.py:126` 이하).
- **`ProblemDetails.code`의 패턴은 `^[A-Z]+-[0-9]{4}$`이고 `additionalProperties: false`다.** 그래서 adapter의 `VAL-MODEL-IMPORT-DECLARATION`은 **그 패턴에 맞지 않는다**. business 어휘 전체가 맞지 않으며, 이는 이 카드가 만든 것이 아니라 기존 분기다(business 오류 본문은 현재 `ProblemDetails`로 계약 검증되지 않는다).
- 추가 제약: `InvError.to_problem()`(`errors.py:104-121`)이 `problem.update(self.extra)`로 **`mismatches`를 top-level 키로 올린다**. `ProblemDetails`가 `additionalProperties: false`이므로, 이 본문을 `ProblemDetails`로 검증하려면 `mismatches`가 들어갈 계약상 자리가 없다.
- 커널 `MODEL-*` 사용 현황(실측): `MODEL-0001`~`MODEL-0008`. **다음 빈 번호는 `MODEL-0009`다.**

## 2. 결속 지점 후보

| 후보 | 위치 | 장점 | 비용·문제 |
|---|---|---|---|
| **A. 서비스 계층만** | `lineage.py:308` `release_model_version`에 선언 비교 추가 | 계약 변경 0. 즉시 구현 가능 | **blocker 문구를 닫지 못한다** — 요청 경로가 여전히 없다. 장부에 "요청 계약 없음"이 그대로 남아야 한다 |
| **B. 서비스 + 새 business 라우트** (권고) | A + `src/saintvision/api/v1/`에 라우트 1개, 요청 타입 1개 | blocker를 문구대로 닫는다. 선언은 기존 관측 라우트에서 얻으므로 커널 무변경 | **계약 변경**: 새 라우트 + 새 요청 schema + 생성 타입·fixture·서빙앵커 |
| C. 커널 manifest commit 시점 | `services/control-plane/src/inv/model_commit.py` | 선언의 발생지 | 그 지점에서 manifest가 **곧 선언**이므로 자기 자신과 비교하는 셈이다. importer의 주장이 도착하는 곳이 아니다. 커널 경계이므로 owner도 Codex다 |

**권고는 B다.** A는 정직하지만 blocker를 닫지 못하고, C는 비교 대상이 성립하지 않는다.

### 2-1. 왜 draft 등록이 아니라 release인가

`release_model_version`의 docstring이 이미 *"released is the point at which someone may deploy it"*이라고 적고, unverified·unpinned·untraceable을 거부하는 **기존 검사 단계**다. 반면 선언은 커널이 run 결과로 commit하는 manifest에서 나오므로 **draft 생성 시점에는 비교할 manifest가 없을 수 있다.** 그래서 선언 일치는 승격 게이트에 속한다. 기존 거부들과 같은 자리에 같은 모양(`InvError` + `extra`)으로 붙는다는 점도 맞다.

## 3. 요청 계약 (계약 변경)

**새 route**: `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/release`

**새 요청 타입** `ModelReleaseRequest` — `additionalProperties: false`, `required: [licensePolicy, classification]`, 필드 제약은 `ModelManifest`와 **동일하게** 복제한다(`licensePolicy`: string minLength 1 maxLength 200 / `classification`: enum public·internal·restricted).

- 응답은 기존 business 응답 관례(`response_model=schemas.…`)를 따르고 새 응답 타입은 **만들지 않는다** — 승격 결과는 기존 model version 표현으로 충분한지 구현 시 확인하고, 필요하면 그때 별도 계약 항목으로 올린다.
- `additionalProperties: false`의 부작용을 명시한다: 스키마가 미지 필드를 먼저 422로 거부하므로 **adapter의 `extra:<field>` 분기는 라우트 경유로는 도달하지 않는다.** 그 분기는 서비스·PG-free 시험에서만 덮인다. adapter 검사를 그래도 유지하는 이유는 (a) 라우트 아닌 호출자(배치·이관 도구)가 생길 수 있고 (b) 이중 방어다. **"스키마가 막으니 adapter 검사는 불필요"로 줄이지 않는다.**

**이것이 이 설계의 유일한 계약 변경이다.** 필요한 동반 산출물: JSON Schema, 생성 TS/Go/Python 타입, fixture, 서빙 앵커, `generate_contracts.py` drift 0, route coverage. 커널 schema·라우트·migration·registry status 변경은 **없다**.

## 4. 오류 코드

우선순위는 "기존 `errors.py` 코드 재사용"이지만, 재사용이 의미를 망치는 자리가 있어 나눠 제안한다.

| 상황 | 코드 | status | 근거 |
|---|---|---|---|
| 요청이 schema를 어김(미지 필드·타입·enum 위반) | `VAL_SCHEMA`(기존) | 422 | 기존 business 관례 그대로 |
| 모델/버전 없음 | `RES_ARTIFACT_NOT_FOUND`(기존) | 404 | `lineage.py:206`이 이미 이 코드를 쓴다 |
| tenant·project 권한 밖 | `AUTH_PROJECT_SCOPE`(기존) | 403 | 기존 관례 |
| 커널 관측을 얻을 수 없음 | **판단 필요** — 기존 business 코드에 대응이 없다. VF-CL-02가 쓴 "unavailable을 빈 성공으로 위장하지 않는다" 원칙에 따라 **재시도 가능한 503**이어야 한다 | 503 | §7 미해결 1 |
| **선언 불일치** | adapter의 `VAL-MODEL-IMPORT-DECLARATION` 유지 | 409 | 아래 |

선언 불일치에 `VAL_SCHEMA`를 재사용하지 **않는** 이유: 이것은 요청이 문법을 어긴 것이 아니라 **불변 선언과 충돌**하는 것이고, 기존 `InvError`가 이미 409를 쓴다. 422로 낮추면 "요청을 고치면 된다"로 읽히는데 실제로는 고칠 수 없다(선언이 불변이다). 그래서 **adapter의 기존 코드를 그대로 쓰고 `errors.py`로 승격**해 audit 코드와 API 표면이 한 곳에서 관리되게 한다(`errors.py`의 주석이 그 목적을 적고 있다).

**단, 이 코드는 `ProblemDetails.code` 패턴 `^[A-Z]+-[0-9]{4}$`에 맞지 않는다**(§1-4). 세 선택지와 판단:

1. business 어휘 유지(`VAL-MODEL-IMPORT-DECLARATION`) — 기존 business 오류들과 일관되고 그 표면은 현재 `ProblemDetails`로 검증되지 않는다. **권고.**
2. 커널식 `MODEL-0009`로 바꾼다 — 패턴에 맞지만 business 어휘에 커널 번호를 섞고, `mismatches`가 `additionalProperties: false` 때문에 여전히 계약상 자리가 없다.
3. `ProblemDetails`에 `mismatches` 필드를 추가한다 — **공개 계약 확대**이므로 이 카드 범위를 넘는다.

권고는 1이고, **"business 오류 본문은 `ProblemDetails` 계약 대상이 아니다"는 기존 사실을 설계에 적어 둔다.** 나중에 business 표면을 `ProblemDetails`로 통일하기로 하면 그때 2·3을 함께 결정해야 하며, 그것은 이 카드가 만든 부채가 아니라 기존 분기를 드러낸 것이다.

## 5. tenant·project 권한 경계

1. 라우트는 기존 `get_session` 의존성을 쓴다(`src/saintvision/api/deps.py:59`) — `get_principal` 뒤 `tenant_scope(session, principal.tenant_id)` 안에서 열린다. 따라서 모든 DB 접근은 **RLS tenant 범위 안**이다.
2. `project_id`는 경로 변수이므로 `principal.require_project(project_id)`로 검사한다(`AUTH_PROJECT_SCOPE` 403). 기존 business 라우트와 같은 방식이다.
3. 모델 소유 확인은 서비스가 이미 한다 — `lineage.py:206`이 `model.tenant_id != tenant_id`면 `RES_ARTIFACT_NOT_FOUND`(존재를 노출하지 않는 404).
4. 커널 관측 호출은 **호출자의 권한으로** 나간다. 커널 라우트가 `Depends(authenticated)` + project grant를 다시 검사하므로(VF-CL-02(d)가 기록), business가 커널 권한을 대리하지 않는다.
5. `inv_app`에 `inv.model_manifests` SELECT를 주지 않는다. 이 설계는 grant를 추가하지 않는다.

## 6. 트랜잭션 안에서의 검사 순서

**커널 관측 HTTP 호출은 DB 트랜잭션 밖에서 한다.** 트랜잭션을 열어 둔 채 네트워크를 기다리면 행 잠금을 쥔 idle-in-transaction이 되고, 그것은 제가 #145 F2에서 차단 사유로 든 것과 **같은 부류**다. 순서는 이렇다.

1. (트랜잭션 밖) 요청 schema 검증 → project grant 검사.
2. (트랜잭션 밖) 커널 관측 조회 → `ModelCommitObservation`. `committed != true`면 승격 거부(선언이 아직 불변이 아니다). `observedAt`이 설정된 신선도 한계를 넘으면 거부 — **stale 관측으로 승격하지 않는다.**
3. 트랜잭션 시작(`tenant_scope`).
4. model version 행 적재(`_load_model_version`) — 없으면 404.
5. **관측 identity 재결속**: 관측의 `projectId`·`modelId`·`version`이 경로 변수와 행의 값과 모두 같은지 확인. 다르면 거부. (VF-CL-02(d)가 세운 "관측을 다시 묶는다" 규율과 같다.)
6. 기존 승격 조건 검사 — `verified_at`, `retention_pinned_until`, `trace_model().missing` (`lineage.py:324`·`:326`·`:332`). **순서를 바꾸지 않는다**: 기존 거부가 먼저다.
7. **`require_exact_declaration(manifest=관측의 두 필드, proposal=요청의 두 필드)`** — 여기서 처음 선언을 비교한다.
8. `row.stage = "released"` → `flush`.
9. 감사 기록: 기존 `record_event`를 `tenant_scope` 안에서 호출(6 라우트와 같은 형태). `detail`에는 **필드 이름만**, 값은 넣지 않는다(§8).

7을 6보다 앞에 두지 않는 이유: 선언 불일치는 409이고 기존 거부는 422다. 검증되지 않은 버전에 대해 선언 불일치를 먼저 말하면 "선언만 맞추면 승격된다"로 읽힌다.

## 7. 불일치 값을 오류에 싣지 않는 규칙

- adapter가 이미 이유를 `missing:<field>`·`differs:<field>`·`extra:<field>`·`undeclared:<field>`로만 만든다 — **값 없음**이 구현으로 보장된다.
- 라우트·감사·로그에서도 같다: `extra={"mismatches": [...]}`는 필드 이름만, `record_event`의 `detail`도 필드 이름만. `licensePolicy` 문자열은 운영자 텍스트이고 `classification`은 분류 자체가 민감할 수 있다.
- `services/audit.py::redact`의 키 marker에 `license`·`classification`은 **없다**(실측: `secret`·`token`·`password`·`credential`·`authorization`·`signature`·`presigned`·`url`·`prompt`·`key`). 그러므로 값을 `detail`에 넣으면 redact가 잡아 주지 않는다 — **넣지 않는 것이 유일한 방어**이고, 이를 부정 시험으로 고정한다(§8-5).

## 8. 부정 시험 — 되돌리면 실패해야 하는 것

PG-free(순수·monkeypatch)로 가능한 것과 실 PG가 필요한 것을 나눈다.

**PG-free** (`tests/core/`):

1. `require_exact_declaration` 호출을 제거하면 → 불일치 제안이 승격에 성공한다(현재 409). **가장 중요한 되살림.**
2. 검사 순서를 7↔6으로 바꾸면 → unverified 버전에 대해 422가 아니라 409가 나온다.
3. 관측 identity 재결속(5)을 제거하면 → 다른 model/version의 관측으로 승격이 성공한다.
4. `committed != true` 거부를 제거하면 → 미commit 선언으로 승격이 성공한다.
5. `extra`/`detail`에 값을 넣으면 → "본문·감사에 `licensePolicy`/`classification` 값이 없다"는 단언이 실패한다.
6. 신선도 한계를 제거하면 → stale 관측으로 승격이 성공한다.
7. 요청 schema의 `additionalProperties: false`를 풀면 → 미지 필드가 422로 거부되지 않는다.
8. 커널 관측 불가를 성공으로 낮추면 → 503이어야 할 곳이 200이 된다.

**실 PG** (`tests/` 단일 파일, hosted 또는 가용 메모리 1.5GB 이상일 때만):

9. RLS: 타 tenant의 model version에 대해 404(존재 비노출)이고 행이 바뀌지 않는다.
10. project grant 없는 principal은 403이며 행이 바뀌지 않는다.
11. 승격 실패 시 `stage`가 `draft`로 남고 감사 행이 tenant 범위 안에 있다.
12. 기존 승격 happy path(검증·pin·trace 완비 + 선언 일치)가 여전히 통과한다 — 양성 대조.

**로컬 실 PG는 이 세션에서 돌리지 않는다**(메모리 규칙). 9~12의 실행 근거는 hosted CI로 둔다.

## 9. 범위 밖 · 미해결

1. **커널 관측 불가의 오류 코드**가 business 어휘에 없다(§4). 503 retryable이 맞다고 보지만 코드 이름은 Codex 판단을 받는다.
2. **신선도 한계 값**을 이 문서가 정하지 않았다. VF-CL-02 계열이 쓴 15s가 후보지만, 승격은 대화형 조작이라 더 길어도 된다. 숫자는 구현 PR에서 사전 등록한다.
3. `register_model_version`·`verify_model_version`·`pin_retention`의 라우트는 **이 카드 범위 밖**이다. 이 설계는 승격 한 지점만 연다. 그래서 blocker를 닫은 뒤에도 "model registry lane은 승격 외 요청 경로가 없다"는 사실은 남고, 장부에 그렇게 적어야 한다.
4. 응답 타입 신설 여부(§3)는 구현 시 확인 후 결정한다.
5. import adapter가 **법적 허가나 실행 승인을 뜻하지 않는다**는 adapter docstring의 경계는 그대로다. 승격은 배포 admission(`inv.model_registry_binding`)과 별개다.

## 10. 요약

- 막힌 것은 adapter가 아니라 **business model-registry lane에 라우트가 없다는 것**이다(§1-2).
- 선언은 이미 커널 관측 라우트가 준다 → **커널 변경 0**(§1-3).
- 권고: `release_model_version`에 선언 게이트를 붙이고 **business 라우트 하나를 새로 연다**. 이것이 **유일한 계약 변경**이다(§2·§3).
- 오류 코드는 기존 코드를 최대한 재사용하고, 선언 불일치만 adapter의 409 코드를 `errors.py`로 승격한다. `ProblemDetails` 패턴 불일치는 **기존 business 분기를 드러낸 것**이며 이 카드가 확대하지 않는다(§4).
- 커널 관측 HTTP는 **트랜잭션 밖**, 선언 비교는 기존 승격 거부 **뒤**(§6).
- 값은 오류·감사·로그 어디에도 넣지 않으며 redact가 잡아 주지 않으므로 부정 시험으로 고정한다(§7·§8-5).
