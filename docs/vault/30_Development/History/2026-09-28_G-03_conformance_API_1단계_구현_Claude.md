---
doc_id: "HIST-CLAUDE-G03-CONFORMANCE-API-IMPL-001"
title: "G-03 conformance 결과 API 1단계 구현 — NOT_OBSERVED 단일값 read route, conformance.py CHECKLIST 단일 정본, 15-name 독립 set ratchet, live membership·정본 403 denial 1행"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:15:23+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-03", "conformance", "adapter", "api", "not-observed", "implementation", "claude"]
---

# G-03 conformance 결과 API 1단계 구현

승인된 설계 `#182` v1.2(head `50c7a33c`)를 그대로 구현했다. base는 그 설계 branch이고, 설계 §10이 적은 선행 의존 때문에 **`#167` head `b7866d63`**(정본 `api/problem.py`)과 **`#184` head `c47811b2`**(= `#195` 정본 403 denial audit)를 merge했다 — 둘 다 해소만. 로컬 실 PG·Docker·전체 suite는 돌리지 않았다. **migration 없음**(설계 §7의 1단계 판정 그대로).

## 1. 먼저 `CHECKLIST`를 만들었다 — 정본이 없었기 때문에

설계 §5-1이 정한 순서다. check 이름 15개는 `run_conformance()` **본문의 문자열 literal**이었고, suite를 실행하지 않고 읽을 public 상수가 없었다. 그 상태에서 route가 할 수 있는 것은 소스를 파싱하거나 이름을 복제하는 것뿐이고 둘 다 drift를 만든다.

`CheckSpec(name, capability, run)`과 `CHECKLIST: tuple[CheckSpec, ...]`을 추출하고 **`run_conformance()`가 그것을 돈다**. 기존 helper는 하나(`_authenticate`)만 `credential_ref`를 받으므로 `_ignoring_credential()`로 모양을 맞췄다 — 15개 시그니처를 바꾸지 않았다. `CHECKLIST`는 **파일 아래쪽**에 둔다(자기가 이름 부르는 함수들 뒤여야 import 시점에 해결된다).

**관측 가능한 동작 변화 0**이 조건이었고, 그 근거는 `tests/test_adapters.py` **27 passed 무변경**이다.

## 2. 15-name 독립 exact set ratchet (설계 v1.2의 7c)

`tests/core/test_conformance_checklist_ratchet.py`. 기대값은 `CHECKLIST` 정의에서 복사한 **시험 파일 literal**이고 **순서까지** 단언한다(응답 `checks[]`가 그 순서를 내므로 순서가 곧 화면 순서다). capability gate 3건의 `name → Capability` 대응도 단언한다.

정본이 둘이 되지 않는다 — 실행되는 것은 `CHECKLIST` 하나만 읽고 시험은 **정책 baseline**을 든다(`tools/definer-policy.json`의 revision과 같은 종류). 그리고 ratchet의 나머지 반쪽으로 **`run_conformance()`가 그 목록을 그대로 돌린다**는 것을 단언한다 — 자기 literal로 돌아간 `run_conformance`는 baseline 시험을 통과하고 이것에서 죽는다.

## 3. route — 보고하고, 측정하지 않는다

`GET /v1/projects/{project_id}/adapters/conformance`, `projects` router에 `add_api_route`(`BusinessDispatch`가 그 `routes`를 읽고 `include_router`는 지연 placeholder만 남긴다).

| 응답 필드 | 1단계 값 | 왜 |
|---|---|---|
| `status` | `Literal["NOT_OBSERVED"]` **하나** | 생성 schema가 `RECORDED`를 광고하지 않는다. 2단계가 counts와 함께 union으로 들여온다 |
| `reason` | 고정 문구 | 왜 미측정인지. 요청과 무관하므로 계산하지 않는다 |
| `scope` | `"control-plane-host"` | conformance는 tenant 데이터가 아니다. `GET /v1/adapters`와 같은 어휘 |
| `contractVersion` | `contract.py`의 `CONTRACT_VERSION` | 정적으로 참 |
| `adapters[]` | `agents.TOOLS`의 네 CLI | **대상 목록**이고 결과가 아니다 |
| `checks[]` | `CHECKLIST`에서 파생 | 개수를 계약에 고정하지 않는다 — 목록이 자라면 응답이 자란다 |
| `recordedAt` | `None` 타입, **required** | 정직한 값이 하나뿐이므로 계약이 그렇게 말한다. consumer는 키가 있다고 믿을 수 있다 |

**counts도 `conformant`도 없다.** `passed: 0`은 미측정이 아니라 0의 측정이고, boolean에는 미측정을 담을 자리가 없다.

**suite를 실행하지 않는다.** `run_conformance()`는 `CliAdapter`에서 호스트 CLI 프로세스를 구동한다. 시험이 그 함수를 **예외를 던지는 것으로 바꿔** 200이 나오는 것을 확인하고, AST로 module의 참조 이름에 `run_conformance`가 **없다**는 것도 단언한다(docstring이 그 이름을 설명으로 적기 때문에 문자열 검색으로는 안 된다).

`RES-0004`와 adapter-name path는 **2단계 deferred**다(설계 §5-2) — 기록이 없으면 adapter마다 다를 것이 없고, 지금 만들면 2단계에서 뜻이 바뀐다. 그래서 1단계에 그 path 변수가 없고 `RES-0004`도 없다.

## 4. 권한과 거부 — 그리고 denial 1행

live `require_project_access`(sign-in snapshot이 아니다), 읽기 등급은 **membership**뿐. 부재·비회원·다른 tenant가 **같은 403 body**다.

`#195`를 base에 merge했으므로 **정본 403이 denial을 남긴다**(내가 `#191`에서 공백으로 보고했던 것이다). 이 PR의 시험이 그것을 실제로 확인한다:

- PG-free: 공유 recorder를 stub해 **1건**이 기록되고 `actor_type`·`actor_id`·`tenant_id`·`reason_code`·`target(project)`·`trace_id`·빈 `detail`이 맞는지, **action에 식별자가 없는지**(#189의 bounded template) 단언한다. 성공한 읽기는 denial 0건이다. route가 스스로 기록하지 않는다는 것도 단언한다(`record_denial`·`record_event` 참조 0).
- 실 PG: `audit_events`에서 **정확히 1행**을 읽고 모든 컬럼을 단언한다. 거부 3종(비회원·없는 project·다른 tenant)이 **같은 body**이고 3행 모두 **호출자의 tenant**로 기록되며 다른 tenant에는 0행이다. 무토큰은 **401 + `anonymous`·tenant NULL 1행**이다.

무토큰 실 PG는 `#184`가 app-role engine에서 500을 보고했던 경로다. `#195`가 그 fix이므로 **401과 행을 단언**하며, hosted가 다르게 말하면 mock으로 우회하지 않고 **결과를 그대로 보고**한다.

## 5. 계약

`api/schemas.py`에 `ConformanceStatusResponse`와 `ConformanceCheckDescriptor`. 전자만 `contracts/conformance-status-response.schema.json`으로 생성된다 — `export_schemas`가 이름이 `Request`/`Response`로 끝나는 `Strict` 파생만 모으므로 descriptor는 `$defs`로 inline된다(`#167`의 `ModelReleaseResult`가 그 규칙에 걸려 schema가 생성되지 않던 사례). 시험이 생성물의 `status.const`·`recordedAt.type = null`·`additionalProperties: false`·required 집합을 직접 읽는다. 새 오류 code **0개**.

## 6. 검증

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_conformance_status_route.py -q` | **37 passed** |
| `pytest tests/core/test_conformance_checklist_ratchet.py -q` | **6 passed** |
| `pytest tests/test_adapters.py -q` | **27 passed, 무변경**(리팩터의 관측 가능한 결과 0) |
| `python tools/export_schemas.py --check` | PASS (64 contract schemas) |
| `check_docs` · `check_doc_single_source --ratchet` | exit 0 |
| openapi | `GET …/adapters/conformance` 노출 확인 |

**변이 5건이 죽었다**(제품을 변이시켜 돌린 뒤 복원, 매번 baseline 복원):

| 변이 | 죽은 시험 |
|---|---|
| `status` literal을 `RECORDED`까지 넓힘 | 1 |
| 응답에 `passed: 0` 추가 | 4 |
| `checks[]`를 `CHECKLIST[:3]`로 자름 | 1 |
| route가 `run_conformance()`를 호출 | 5+ |
| membership 확인 제거 | 5 |

실 PG **7건**은 hosted Backend에서 실행된다. hosted가 fixture에서 죽지 않도록 **PG-free guard**를 넣었다(`_seed`를 기록용 connection에 돌려 컬럼·id kind·기본 role을 확인한다 — 기본 role이 `requester`인 것도 단언한다. 읽기는 membership만 필요하므로 happy path를 approver로 seed하면 시험이 약해진다).

## 7. 다음 첫 행동

Codex 검토. 2단계(기록의 주체·주기·보존, 기록 table)는 **설계하지 않았고** migration 번호 선요청부터 시작한다. 병합 순서는 `#167` → `#184`(=`#195`) → 이 PR.
