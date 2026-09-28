---
doc_id: "HIST-CLAUDE-G01-ADAPTERS-ROUTE-HTTP-001"
title: "G-01 구현 — GET /v1/adapters·/{name}의 HTTP 레벨 시험 15건, 서빙 표면 첫 검증(시험만, 제품 변경 0)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:44:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["s10-be", "adapters", "route", "test", "evidence-gap", "claude"]
---

# G-01 — adapter 상태 route의 HTTP 레벨 시험

PR #179의 통합 분류표(`Evidence 공백 통합 분류와 구현 순서.md`)의 **G-01** 행을 닫는다. 제품 코드는 **한 줄도 바꾸지 않았다** — 시험 파일 하나(`tests/core/test_adapters_route.py`, 15 test)다.

## 1. 무엇이 비어 있었는가

`GET /v1/adapters`와 `GET /v1/adapters/{name}`은 S03부터 `BusinessDispatch`가 서빙해 왔다. 그런데 `tests/`에서 `v1/adapters` grep이 **0건**이었다 — `tests/test_cli_adapters.py`는 `adapters/agents.py`를 직접 부른다. 즉 **route 층이 한 번도 실행된 적이 없다**: 자격증명 검사, 응답 키 집합, `unknown adapter` 404, `readyCount` 산식 전부가 서빙 경로를 통과해 나온 적이 없으므로, route 층의 회귀(의존성 주입 실수, 응답 모양 변경)가 어떤 시험도 깨뜨리지 않았다.

## 2. 담은 것 (15건)

| 무엇 | 왜 |
|---|---|
| 목록 응답의 **정확한 키 집합**과 `measurementScope: "control-plane-host"`·`remoteNodeReadiness: "unknown"` | 이 둘이 "이것은 fleet의 상태가 아니라 control-plane 호스트가 자기를 본 것"이라고 말하는 장치다. 통합 분류표가 G-12를 "정직성은 이미 확보"라고 적은 근거를 **시험으로 고정**한다 |
| adapter 순서 보존 | route docstring이 "Ordered, so a status screen does not reshuffle between refreshes"라 적는다 |
| `readyCount` = `installed and headless and loginState == "logged_in"` | near-miss 4종(미설치 / headless 아님 / logged_out / unknown)을 각각 0으로, 완전 충족 1종을 1로 확인한다. 양성 대조가 없으면 네 부정 시험이 공허하게 통과할 수 있다 |
| 한 tool이 깨져도 **요청이 실패하지 않는다** | `agents.readiness()`가 per-tool 실패를 `error` 키가 있는 행으로 바꾼다. route가 그것을 통과시키는지, 그리고 `headless` 키가 없는 행에서 `readyCount` 계산이 터지지 않는지 본다 |
| 단건 조회가 readiness에 probe를 **더한다**(덮지 않는다) | `reachable`·`latencyMs`가 붙고 `installed`·`loginState`가 남는다 |
| 도달 불가도 **200**이고 `reachable: false` | 도구에 대한 답이고 요청에 대한 오류가 아니다 |
| 알 수 없는 이름은 404 | **현재 동작을 pin한다**(§3) |
| 두 route 모두 자격증명 없으면 401 | 기존 `AUTH-MISSING-CREDENTIAL` body와 `WWW-Authenticate: Bearer` |
| 두 route가 `BusinessDispatch` 선택 목록에 있다 | 배포 토폴로지에서 도달하지 않는 route는 서빙되는 route가 아니다. 이 파일의 나머지가 의존하는 성질이라 함께 pin한다 |
| 목록 응답에 **선언된 타입이 없다**는 사실 | §4 |

`agents.readiness()`·`adapter_for()`는 **stub한다.** 대상은 route이고, 실 CLI 바이너리 탐지는 통합 분류표의 **G-11**(hosted provisioning)이다. 둘을 한 시험에 섞으면 route 회귀와 바이너리 부재가 같은 실패로 보인다.

## 3. 정본 `ProblemDetails`가 아닌 404를 그대로 pin한 이유

이 route는 `HTTPException(404)`를 던져 `{"detail": "unknown adapter: …"}`를 낸다 — 정본 `ProblemDetails`가 아니다. **이 PR에서 바꾸지 않는다.** #167이 새 route에만 정본을 적용하고 기존 표면은 건드리지 않기로 한 결정과 같은 이유이고, 공개 오류 body를 바꾸는 것은 계약 변경이다. 시험은 **서빙되는 것을 기록**하고(`code`·`type` 키가 **없음**까지 단언), 정본화가 필요하면 별 카드다. 그렇게 하면 나중의 정본화가 이 시험을 **의도적으로** 고쳐야 한다.

## 4. 관찰 하나 — 이 응답에는 선언된 타입이 없다

business 요청·응답 계약은 `api/schemas.py`에 있고 `tools/export_schemas.py`가 JSON Schema를 생성한다. 그런데 이 두 route는 `-> dict`로 선언돼 **생성되는 schema가 없고 `export_schemas --check`가 모양 변화를 알아차릴 수 없다.** 지금은 위 시험이 유일한 고정 장치다. 응답 타입을 추가하는 것은 **계약 변경**이므로 이 공백(G-01)의 범위가 아니고, 시험 하나로 사실만 기록한다(`test_the_list_response_has_no_declared_type_yet`). 후속 후보다.

## 5. 검증 증거 (실행)

- `pytest tests/core/test_adapters_route.py -q` → **15 passed**.
- `pytest tests/core -q` → **1047 passed, 4 skipped**.
- `check_docs`·`check_doc_single_source --ratchet` → exit 0.
- 제품 코드·계약·migration **무변경**. 로컬 실 PG·Docker·전체 suite **미실행**.

## 6. 다음 첫 행동

Codex 검토. 그 뒤 통합 분류표의 2순위(G-02 live archiver hosted 실행)는 접근 경로 결정이 먼저이므로 짧은 설계 문서를 올린다.
