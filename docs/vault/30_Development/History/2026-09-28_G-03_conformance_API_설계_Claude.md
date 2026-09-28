---
doc_id: "HIST-CLAUDE-G03-CONFORMANCE-API-DESIGN-001"
title: "G-03 conformance 결과 API 노출 설계 v1.0 — 저장된 결과가 0건이라 1단계는 NOT_OBSERVED, counts·boolean 금지, 2단계는 migration 선요청 (docs-only)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:55:28+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["s10-be", "conformance", "api", "design", "not-observed", "claude"]
---

# G-03 conformance API 설계 (카드 55)

PR #179 §3-3의 G-03을 닫는 설계 1단계다. 산출물은 [[G-03_conformance_결과_API_노출_설계]] 하나이고 구현은 승인 뒤 별 PR이다.

## 1. 설계를 결정한 실측

`git grep -n -F`로 확인한 것이 설계를 거의 다 정했다.

- **생산자는 있다**: `adapters/conformance.py:121 run_conformance()`, 증거 shape `:91 to_dict()`("The shape recorded as AC-10 evidence"), 비교 `:327 compare_reports()`, 계약 버전 `contract.py:35 CONTRACT_VERSION = "1.0.0"`.
- **제품 호출부가 없다**: `run_conformance` grep이 정의 한 줄 + `tests/test_adapters.py` 11곳뿐이다.
- **저장이 없다**: `src/saintvision/db`·`migrations`에서 `conformance` grep **0건**. table·column·migration 어느 것도 없다.
- **CI 증거 산출물도 없다**: `tools`·`.github/workflows` grep에서 무관한 browser-smoke 로그 한 줄뿐.
- **대상은 `/v1/adapters`가 말하는 그 네 CLI다**: `CliAdapter`(`cli.py:194`)가 `ProviderAdapter` 계약을 만족한다고 cli.py 첫 문장이 적는다.
- **정적으로 아는 것**: 계약 버전과 check 이름 **15개**(무조건 12 + capability로 갈리는 3, `conformance.py:131-160`).

## 2. 그래서 1단계는 `NOT_OBSERVED`다 (counts·boolean 금지)

기록이 없을 때 낼 수 있는 답 셋 중 둘을 금지로 적었다 — `true`/`passed: N`은 **날조**이고, `false`/`passed: 0`은 "돌렸고 실패했다"로 읽힌다. 그래서 `conformant: bool`을 **아예 두지 않고** `status` enum(`NOT_OBSERVED` | `RECORDED`)을 쓴다. boolean에는 미측정을 담을 자리가 없다.

`total`·`passed`·`failed`·`skipped`도 1단계 응답에 **넣지 않는다**(값이 `0`이어도). 부정 시험 2번이 그것을 고정한다.

## 3. 두 단계로 나눈 이유

`run_conformance()`는 adapter의 `install`·`authenticate`·`run`·`collect`·`cancel`을 실제로 부른다. `CliAdapter`에서 그것은 **호스트의 CLI 프로세스를 구동**하는 일이므로, 읽기 route가 요청마다 하면 부작용·무경계 지연·타인 측정 촉발이 생긴다. 그래서 1단계는 실행도 저장도 하지 않고, 실행 주체·주기는 2단계의 owner 결정으로 남겼다. 부정 시험 6번이 "route가 `run_conformance()`를 부르지 않음"을 단언한다.

## 4. 물려받되 뜻이 달라진 것 — project 범위

conformance는 **tenant 데이터가 아니다.** 호스트 adapter가 계약을 만족하는지는 project마다 다르지 않다. 그래도 route를 `/v1/projects/{project_id}/adapters/conformance`로 둔 이유는 #158의 권한 결정(live `require_project_access`, 읽기는 membership)을 **글자 그대로 물려받기 위해서**이고, 대신 응답에 `scope: "control-plane-host"`를 넣어 **payload가 project 범위인 척하지 않게** 했다 — `GET /v1/adapters`가 이미 `measurementScope: "control-plane-host"`(`api/v1/adapters.py:46`)로 같은 말을 한다. path의 project는 **누가 볼 수 있는지의 경계**이고 데이터의 소유자가 아니다.

**path→row 결속은 1단계에 없다** — 결속할 row가 없는 것이 `NOT_OBSERVED`의 내용이다. 이 차이를 숨기지 않고 §4 표에 적었다.

## 5. #146 FE 어휘 대응표에서 나온 사실 셋

FE의 정적 예시(`mlopsEngine.ts::verifyProviderConformances()`, `contracts/types.ts:444`)와 맞춰 보니 **백엔드에 근거가 없는 필드·값**이 드러났다.

- **`avgLatencyMs`·`tokensPerSec`**: conformance suite는 지연·처리율을 **측정하지 않는다**(15 check 어디에도 없다). 생산자가 없으므로 API에 두지 않고, FE도 제거해야 한다 — 남기면 "API가 생겼는데 이 숫자는 여전히 날조"다.
- **`Local-vLLM`**: 백엔드 대상은 `agents.TOOLS`의 네 CLI(`claude-code`·`codex-cli`·`gemini-cli`·`antigravity`)이고 `Local-vLLM`은 존재하지 않는다.
- **`contractVersion: 'v1.0.0-ADR-004'`**: 정본은 `"1.0.0"`이다.

FE 변경은 Gemini 책임이므로 이 카드에서 하지 않고, **API가 무엇을 주고 무엇을 주지 않는지**를 표로 못 박아 FE가 무엇을 지워야 하는지 알 수 있게 했다.

## 6. persistence·index 판정

- **1단계: 필요 없다(확정).** 쓰는 것이 없고 읽는 것은 정적 상수와 `TOOLS`뿐이다. **그래서 이 카드에서 migration 번호를 요청하지 않는다.**
- **2단계: 필요하다.** 기록 table과 "최신 기록" 조회가 생긴다. **#174가 반례다** — #175의 역조회는 route만으로 끝나지 않고 index가 필요했다. 그러므로 2단계 카드는 **설계 전에 번호를 먼저 요청**해야 한다(현재 `0051`까지 배정).

## 7. 계약 변경과 gate

route 1 + 응답 타입 1 = **2건**, 새 오류 code **0개**. 정본 `core.schema.json`은 무변경(business 타입은 `api/schemas.py`의 `Strict`)이고 `export_schemas`가 `contracts/conformance-status-response.schema.json`을 생성하며 `--check`가 drift를 잡는다. **타입 이름이 `…Response`여야 생성된다** — `export_schemas.py:60`의 규칙이고, #167에서 `ModelReleaseResult`가 거기 걸리지 않아 schema가 생성되지 않던 사례를 근거로 적었다. route는 `projects` router에 `add_api_route`로 넣는다(`BusinessDispatch`가 그 `routes`를 읽고, `include_router`는 지연 placeholder만 남긴다).

## 8. 선행 의존

`api/problem.py`가 **integration에 없다**(`ls` → `No such file or directory`). #167이 owner이므로 병합 순서는 **#167 → 이 구현 PR**이다.

## 9. 검증 증거

- `check_docs` → PASS(893 versioned documents). `check_doc_single_source --ratchet` → PASS.
- 부정 시험 **17건**을 설계에 열거했다(NOT_OBSERVED 7 · 권한·존재 비노출 6 · 계약 4). 실 PG는 1건(다른 tenant)이고 나머지는 PG-free다.
- 실행 0건: 로컬 실 PG·Docker·전체 suite 없음. 실측은 전부 `git grep -n -F`·정독이다.

## 10. 다음 첫 행동

Codex 검토. 승인되면 구현 PR을 이 설계 위에 stack하고, **#167 병합 뒤**에 착지시킨다. 2단계(기록·노출)는 migration 번호 요청부터 시작하는 별 카드다.
