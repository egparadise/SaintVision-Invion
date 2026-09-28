---
doc_id: "CLAUDE-G03-CONFORMANCE-API-DESIGN-001"
title: "G-03 conformance 결과 API 노출 설계 v1.0 — 저장된 결과가 없으므로 1단계는 NOT_OBSERVED와 계약 표면만, 기록·노출은 migration이 필요한 2단계 (docs-only)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:55:28+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["s10-be", "conformance", "adapter", "api", "design", "not-observed", "claude"]
---

# G-03 conformance 결과 API 노출 설계

PR #179 통합 분류표의 **G-03**("conformance 결과의 API 노출이 없다 — #146이 FE에서 '미측정'으로 정직화")을 닫는 설계다. **설계만이고 구현은 승인 뒤 별 PR**이다. 실행 0건 — 아래 사실은 전부 `git grep -n -F`와 정독이다.

결론 먼저: **노출할 결과가 저장돼 있지 않다.** 그래서 이 설계는 두 단계로 나눈다 — 1단계는 서버가 **`NOT_OBSERVED`를 스스로 말하고** 정적으로 알 수 있는 계약 표면(계약 버전·check 이름)만 내는 읽기 route, 2단계는 실행 기록을 남기고 그것을 노출하는 것이며 **2단계는 migration이 필요하므로 이 카드에 넣지 않는다**.

## 1. 실측 — 생산자는 있고, 저장도 호출부도 없다

| 무엇 | 위치 | 상태 |
|---|---|---|
| 생산자 | `src/saintvision/adapters/conformance.py:121` `run_conformance(adapter, *, credential_ref=…)` → `ConformanceReport` | **있다** |
| 증거 shape | 같은 파일 `:91` `to_dict()` — docstring이 *"The shape recorded as AC-10 evidence"* | **있다** |
| 두 adapter 비교 | 같은 파일 `:327` `compare_reports()` — AC-10 "Codex/Claude 계약 동일" | **있다** |
| 계약 버전 | `src/saintvision/adapters/contract.py:35` `CONTRACT_VERSION = "1.0.0"` | **있다** |
| **제품 호출부** | `git grep -n -F run_conformance -- src tools services` → `conformance.py:121`(정의) **한 줄뿐** | **없다** |
| 시험 호출부 | `tests/test_adapters.py` 11곳 | 있다(시험만) |
| **저장** | `git grep -n -i -F conformance -- src/saintvision/db migrations` → **0건** | **없다** |
| **CI 증거 산출물** | `git grep -n -i -F conformance -- tools .github/workflows` → 무관한 browser-smoke 로그 1줄뿐 | **없다** |
| HTTP route | `api/` 어디에도 없다 | **없다** |

**대상 adapter가 무엇인지도 확인했다.** conformance는 `ProviderAdapter` 계약(`adapters/contract.py:39`)에 대해 돌고, `CliAdapter`(`adapters/cli.py:194`)가 그 계약을 만족한다 — cli.py의 첫 문장이 *"Claude Code, Codex, Gemini and Antigravity … satisfies the same `ProviderAdapter` contract as a hosted provider"*라 적는다. 즉 **`GET /v1/adapters`가 상태를 말하는 그 네 도구가 conformance의 대상**이다. `ReferenceAdapter`(`adapters/reference.py:82`)는 저장소 안의 기준 구현이다.

**정적으로 알 수 있는 것**: 계약 버전과 suite가 돌릴 **check 이름 15개**(`conformance.py:131-160`) — 무조건 12개(`declares_contract_version` · `implements_every_member` · `probe_without_credentials` · `install_reports_without_installing` · `authenticate_takes_a_reference` · `run_returns_a_usable_handle` · `collect_returns_redacted_content` · `redact_removes_known_secrets` · `redact_is_idempotent` · `cancel_returns_a_tri_state` · `cancel_after_completion_is_not_stopped` · `attest_does_not_overclaim`)와 capability로 갈리는 3개(`declared_server_cancel_actually_stops` · `declared_usage_is_reported` · `declared_model_pinning_returns_an_id`).

## 2. 그러므로 1단계는 `NOT_OBSERVED`다

기록이 없는 상태에서 API가 낼 수 있는 답은 셋뿐이고, 둘은 쓰면 안 된다.

| 후보 | 판단 |
|---|---|
| `conformancePassed: true` / `passed: N` | **금지.** 저장된 실행이 없으므로 그것은 측정이 아니라 **날조**다. #146이 FE에서 지운 바로 그것이다 |
| `conformancePassed: false` / `passed: 0` | **금지.** `false`와 `0`은 "돌렸고 실패했다"로 읽힌다. 미측정과 실패는 다른 사실이다 |
| **`status: "NOT_OBSERVED"` + 계약 표면** | **권고.** 서버가 "이 플랫폼은 conformance를 기록하지 않는다"를 스스로 말하고, 정적으로 참인 것(계약 버전·check 이름·대상 adapter)만 낸다 |

boolean을 아예 두지 않는 것이 핵심이다 — `conformant: bool`에는 제3의 값이 없으므로 미측정을 표현할 자리가 없다. 그래서 응답은 **`status` enum**(`NOT_OBSERVED` | `RECORDED`)을 쓰고, `RECORDED`일 때만 counts가 존재한다. 1단계는 항상 `NOT_OBSERVED`이며, 그 사실을 부정 시험이 고정한다(§8-1).

## 3. 두 단계

| 단계 | 무엇 | migration |
|---|---|---|
| **1단계 (이 설계)** | 읽기 route 하나. `status: "NOT_OBSERVED"` + 계약 버전 + check 이름 + 대상 adapter 목록. 실행하지 않고 저장하지 않는다 | **없음** |
| **2단계 (별 카드)** | 누가·언제 실행해 무엇이 나왔는지 기록하고 그 기록을 노출 | **필요** — §7 |

**왜 1단계에서 실행하지 않는가**: `run_conformance()`는 adapter의 `install`·`authenticate`·`run`·`collect`·`cancel` 경로를 실제로 호출한다. `CliAdapter`에서 그것은 **호스트의 CLI 프로세스를 구동**하는 일이고, 요청마다 그것을 하면 (i) 읽기 route가 호스트에 부작용을 만들고, (ii) 시간이 경계 없이 늘어나고, (iii) 요청을 보낸 사람이 다른 사람의 측정을 촉발한다. 읽기 route가 할 일이 아니다. 실행 주체·주기는 2단계의 결정이다.

## 4. #158에서 물려받는 결정 (출처 `git grep -n -F`)

| 결정 | 출처 | 이 설계에서 |
|---|---|---|
| **live 권한 재확인** — snapshot을 쓰지 않는다 | `src/saintvision/services/projects.py:204` `def require_project_access(`; snapshot 경고는 `src/saintvision/identity/principal.py:43` *"**Not what authorisation rests on.** It is a snapshot, and it is wrong in both directions"* | `require_project_access()`를 조회 시점에 부른다. `principal.require_project`를 쓰지 않는다 |
| **읽기 등급은 membership** | 같은 함수가 membership 없으면 이미 거부한다 | `canRequest`·`canApprove`를 **요구하지 않는다**. 두 flag는 행위 등급이다 |
| **존재 비노출 404/거부 동형** | `services/projects.py:209` *"Reports the same denial whether the project does not exist or the caller simply cannot see it"* | 없는 project와 안 보이는 project가 **같은 거부**다. 알 수 없는 adapter 이름은 `RES-0004` 404 |
| **정본 `ProblemDetails`는 공유 모듈이 낸다** | `src/saintvision/api/problem.py` — **현재 integration에 없다**(`ls` 결과 `No such file or directory`). #167이 owner다 | **선행 의존**: 이 route의 오류는 그 모듈이 낸다. 병합 순서는 **#167 → 이 구현 PR**이고, #167이 먼저 들어가지 않으면 구현이 시작될 수 없다 |
| **strict 응답 모델** | `src/saintvision/api/schemas.py:20` `class Strict(BaseModel)`(`extra="forbid"`) | 응답 타입을 `Strict` 파생으로 선언한다(§6) |
| **path→row 결속** | #158 §6-4의 원칙 | **1단계에는 결속할 row가 없다** — 그것이 `NOT_OBSERVED`의 내용이다. path에서 확인하는 것은 project 접근뿐이고, 2단계에서 `(project, adapter, run)` 결속이 생긴다. 이 차이를 숨기지 않는다 |

### 4-1. 물려받되 뜻이 달라지는 것 하나 — project 범위

conformance는 **tenant의 데이터가 아니다.** 호스트에 설치된 adapter가 계약을 만족하는지는 project마다 다르지 않다. 그래서 두 후보가 있었다.

| 후보 | 판단 |
|---|---|
| (a) `GET /v1/adapters/conformance` — 호스트 수준, 인증만 | `/v1/adapters`와 같은 자리라 일관되지만, #158의 권한 결정을 물려받지 못한다 |
| **(b) `GET /v1/projects/{project_id}/adapters/conformance`** — project 아래, live membership | **권고.** #158의 권한 결정을 글자 그대로 물려받고, FE가 이 값을 보여 주는 화면(`ModelLineageView`)이 project 안이다 |

(b)를 고르면서 **payload가 project 범위 데이터인 척하지 않는다** — 응답에 `scope: "control-plane-host"`를 둔다. `GET /v1/adapters`가 이미 `measurementScope: "control-plane-host"`(`api/v1/adapters.py:46`)로 같은 말을 하므로 어휘도 같다. path의 project는 **누가 볼 수 있는지의 경계**이고 데이터의 소유자가 아니라는 것을 설계와 응답이 함께 말한다.

## 5. route와 응답

```
GET /v1/projects/{project_id}/adapters/conformance
```

`ConformanceStatusResponse`(`Strict`, `extra="forbid"`):

| 필드 | 1단계 값 | 근거 |
|---|---|---|
| `status` | `"NOT_OBSERVED"` | `Literal["NOT_OBSERVED", "RECORDED"]`. 2단계가 `RECORDED`를 쓴다 |
| `reason` | 고정 문구 — *"No conformance run is recorded; this platform does not persist conformance results yet."* | 왜 미측정인지 |
| `scope` | `"control-plane-host"` | §4-1. `/v1/adapters`와 같은 어휘 |
| `contractVersion` | `"1.0.0"` (`contract.py:35`) | 정적으로 참 |
| `adapters[]` | `["claude-code", "codex-cli", "gemini-cli", "antigravity"]` — suite가 돌 대상 | `agents.TOOLS`에서 파생. **상태·결과가 아니라 대상 목록**이다 |
| `checks[]` | check **이름 15개**와 `capabilityGated: bool` | `conformance.py:131-160`에서 파생 |
| `recordedAt` | `null` | 기록이 없다 |

**counts를 두지 않는다.** `total`·`passed`·`failed`·`skipped`는 `RECORDED`일 때만 의미가 있고, 1단계 응답에 `0`으로 넣으면 §2가 금지한 그것이 된다. 2단계에서 `status: "RECORDED"`와 함께 **한 묶음으로** 추가한다 — 그것이 계약 변경임을 2단계 카드가 적는다.

단건 조회(`…/adapters/{name}/conformance`)는 **1단계에 두지 않는다**: 기록이 없으므로 adapter별로 다를 것이 없고, 지금 만들면 2단계에서 뜻이 바뀐다.

## 6. 계약 변경 범위와 gate

| 무엇 | 바뀌는가 | 근거 |
|---|---|---|
| `contracts/v1alpha1/core.schema.json` | **아니다** | business 응답 타입은 정본 `$defs`가 아니라 `api/schemas.py`의 `Strict` 클래스다 |
| `api/schemas.py` | **예** — `ConformanceStatusResponse` 1개 |  |
| `contracts/conformance-status-response.schema.json` | **예**(생성물) | `tools/export_schemas.py`가 `Strict` 파생 중 **이름이 `Request`/`Response`로 끝나는 것**을 찾는다(`:60`). 그래서 타입 이름이 `…Response`여야 생성된다 — #167에서 `ModelReleaseResult`가 이 규칙에 걸리지 않아 schema가 생성되지 않던 사례가 있었다 |
| `export_schemas --check` | **잡는다** | 모델과 생성물이 어긋나면 `backend.yml`의 `--check`가 실패한다 |
| openapi | 자동 — route 등록으로 `/v1/openapi.json`에 들어간다. 별도 파일 편집 없음 |  |
| route coverage | `tools/route_coverage.py` 대상. 새 서빙 경로 1개 |  |
| **route 등록 위치** | `projects` router에 `add_api_route`로 넣는다 | `inv.business_surface.BusinessDispatch`가 `projects`·`settings`·`adapters` router의 `routes`를 읽으므로 새 top-level router는 도달하지 않고, `include_router`는 지연 placeholder만 남긴다(#167 실측) |

계약 변경 = **route 1 + 응답 타입 1 = 2건**, 새 오류 code **0개**(`VAL-0003`·`AUTH-0030`·`RES-0004` 재사용).

## 7. persistence·index 판정

- **1단계: 필요 없다(확정).** 쓰는 것이 없고 읽는 것도 정적 상수와 `TOOLS`뿐이다. table·column·index·migration 어느 것도 생기지 않는다. 그래서 **이 카드에서 migration 번호를 요청하지 않는다.**
- **2단계: 필요하다.** 실행 기록을 남기려면 최소한 `(tenant_id, adapter, contract_version, recorded_at, report JSONB)` 한 table이 필요하고, "이 adapter의 최신 기록"을 읽으려면 `(tenant_id, adapter, recorded_at DESC)` 조회가 생긴다 — **#174가 바로 그 반례다**: #175의 역조회는 route만으로 끝나지 않고 `dataset_versions(tenant_id, content_sha256)` index가 필요했다. 그러므로 2단계 카드는 **설계 단계에서 멈추고 migration 번호를 먼저 요청해야 한다**(현재 `0051`까지 배정).

이 설계는 2단계를 **설계하지 않는다** — 기록의 주체·주기·보존이 owner 결정이기 때문이다. 필요한 것을 여기 적어 두는 데까지가 이 카드다.

## 8. 부정 시험 — 되돌리면 실패해야 하는 것

### 8-1. `NOT_OBSERVED`를 지키는 것 (PG-free)

1. `status`를 `"RECORDED"`로 바꾸거나 `conformant: true`를 넣으면 → "저장된 실행이 없는데 결과를 주장한다" 단언이 실패한다.
2. `passed`/`failed`/`total`/`skipped` 중 하나라도 응답에 넣으면(값이 `0`이어도) → **counts 금지** 단언이 실패한다. `0`이 "돌렸고 0개 통과"로 읽히는 것이 금지 이유다.
3. `recordedAt`에 현재 시각을 넣으면 → `null`이어야 한다는 단언이 실패한다(지금 응답을 만든 시각은 **측정 시각이 아니다**).
4. `reason`을 지우면 → 왜 미측정인지 말하지 않는 응답이 된다.
5. `scope`를 지우거나 `"project"`로 바꾸면 → payload가 project 범위 데이터인 척하게 된다(§4-1).
6. route가 `run_conformance()`를 부르면 → **읽기 route가 호스트 프로세스를 구동한다.** 호출 없음을 단언한다(§3).
7. `checks[]`와 `adapters[]`가 소스에서 파생되지 않고 하드코딩되면 → `conformance.py`의 check 목록·`agents.TOOLS`와 비교하는 단언이 실패한다. **판정 논리를 복제하지 않고 이름만 가져온다.**

### 8-2. 권한·존재 비노출 (PG-free + 실 PG)

8. `require_project_access`를 `principal.require_project`로 바꾸면 → 회수된 membership이 조회에 성공한다.
9. 읽기에 `canRequest`/`canApprove`를 요구하면 → membership만 가진 principal이 403을 받는다(잘못된 경계).
10. **비회원**: 접근 권한 없는 project id로 조회 → `AUTH-0030` 403이고 body에 `projectId`가 없다.
11. **없는 project id** → 10번과 **같은 거부**(존재 비노출). 두 응답이 구분되면 실패다.
12. **다른 tenant의 project id** → 같은 거부(실 PG, RLS).
13. 알 수 없는 adapter 이름을 경로에 넣는 변형(2단계 단건 조회가 생겼을 때) → `RES-0004` 404.

### 8-3. 계약 (PG-free)

14. 응답의 **exact key set**과 `status`의 `Literal` 위반 거부(`extra="forbid"`).
15. 오류 3종(`VAL-0003`·`AUTH-0030`·`RES-0004`)의 정본 `ProblemDetails` 10키·`about:blank`·code별 status/retryable, top-level 임의 key 없음.
16. 응답 타입 이름이 `…Response`가 아니면 `export_schemas`가 schema를 만들지 않는다 → 생성물 존재와 `--check` drift 0을 단언한다(§6의 #167 사례 재발 방지).
17. route가 `projects` router의 `routes`에 실제로 있다(= `BusinessDispatch`가 서빙한다). `include_router`로 되돌리면 지연 placeholder만 남아 도달하지 않는다.

**실 PG는 12번 하나**이고(다른 tenant), 나머지는 PG-free다. 로컬은 메모리 규칙상 단일 파일만 돌리고, 실 PG 근거는 hosted Backend에 둔다.

## 9. #146 FE 어휘 대응표

#146이 FE에서 정직화한 문구·필드와 이 API의 어휘를 맞춘다. FE 쪽 출처는 `apps/web/src/features/mlops/mlopsEngine.ts`(정적 예시 생산자 `verifyProviderConformances()`), `apps/web/src/features/mlops/ModelLineageView.tsx`(표시 문구), `apps/web/src/contracts/types.ts:444` `ProviderAdapterConformance`다.

| FE 현재 | API 1단계 | 판단 |
|---|---|---|
| `미측정 (모의/정적 예시 · 검증 아님)` | `status: "NOT_OBSERVED"` | **같은 뜻을 서버가 말한다.** FE가 스스로 붙이던 라벨이 응답 필드가 된다 |
| `실제 conformance API 부재 · … 스키마 예시` | `reason`(고정 문구) | API가 생기면 "부재"는 더 이상 참이 아니므로, FE는 `reason`을 그대로 보여 주는 쪽으로 바꾼다 |
| `provider: 'Codex' \| 'Claude' \| 'Local-vLLM'` | `adapters[]` = `claude-code`·`codex-cli`·`gemini-cli`·`antigravity` | **이름이 다르다.** 백엔드의 대상은 `agents.TOOLS`의 네 CLI이고 `Local-vLLM`은 백엔드에 존재하지 않는다. FE는 API 목록을 써야 한다 |
| `conformancePassed: boolean` | **없음** | boolean에는 미측정을 담을 자리가 없다(§2). `status`로 대체 |
| `contractVersion: 'v1.0.0-ADR-004'` | `contractVersion: "1.0.0"` | **값이 다르다.** 정본은 `contract.py:35`의 `"1.0.0"`이고 `v…-ADR-004`는 FE의 장식이다 |
| `avgLatencyMs`, `tokensPerSec` | **없음 — 백엔드가 만들 수 없다** | conformance suite는 **지연·처리율을 측정하지 않는다**(`conformance.py`의 15 check 어디에도 없다). 이 두 필드는 생산자가 없으므로 API에 두지 않고, FE도 제거해야 한다. 남겨 두면 "API가 생겼는데도 이 숫자는 여전히 날조"인 상태가 된다 |
| `supportedProtocols: string[]` | **없음(1단계)** | 백엔드에 대응 개념은 `Capability` enum이고 `SSE-v2`·`W3C-TraceContext` 같은 값이 아니다. capability 노출은 2단계 후보로 남긴다 |
| `data-testid="conformance-status-${provider}"` | 유지 가능 | provider 이름만 API 목록으로 바꾸면 된다 |

**FE 변경은 이 카드의 범위가 아니다**(디자인·Frontend는 Gemini 책임). 이 표는 **API가 무엇을 주고 무엇을 주지 않는지**를 명시해 FE가 무엇을 지워야 하는지 알 수 있게 하는 것이 목적이고, `avgLatencyMs`·`tokensPerSec`·`Local-vLLM`·`v1.0.0-ADR-004`는 **백엔드에 근거가 없다**는 사실을 여기 못 박는다.

## 10. 경계 · 미해결

- **선행 의존**: `api/problem.py`가 integration에 없다. 병합 순서는 **#167 → 이 구현 PR**이다.
- **2단계를 설계하지 않았다.** 실행 주체(CI job / 운영 명령 / 요청)·주기·보존 기간이 owner 결정이고, 그것이 정해지지 않은 상태에서 table을 그리면 잘못된 스키마가 남는다. 2단계는 **migration 번호 요청부터** 시작한다.
- **`compare_reports()`(AC-10 "계약 동일")도 노출하지 않는다** — 두 adapter의 실행 기록이 있어야 비교가 성립하므로 2단계 이후다.
- `run_conformance`의 `credential_ref` 기본값은 `"conformance://dummy"`다. 실제 credential로 도는 conformance는 통합 분류표의 **G-25**(BLOCKED_EXTERNAL)다 — 1단계가 `NOT_OBSERVED`라고 말하는 것은 "기록이 없다"까지이고 "실 credential로 검증됐다"를 뜻하지 않는다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 전부 `git grep -n -F`·정독이다.
