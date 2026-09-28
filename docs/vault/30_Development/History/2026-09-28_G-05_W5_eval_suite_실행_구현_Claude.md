---
doc_id: "HIST-CLAUDE-G05-W5-EVAL-RUN-IMPL-001"
title: "G-05 W5 eval suite 실행 route 구현 — canApprove·adapter는 구성 allowlist의 이름뿐·외부 호출 직전 권한 재확인, NULL project suite 404, IDEM 재생이 두 번째 청구를 막는다 (설계 #183 §8 PR 8/8)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T18:40:59+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-05", "evaluation", "idempotency", "problem-details", "implementation", "claude"]
---

# G-05 W5 eval suite 실행 route 구현 (카드 82, 설계 #183 §8의 마지막 PR)

승인된 설계 `#183` v1.2.1 §8의 **PR 8/8**이다. base는 조정자가 지정한 **#202 head `9c2733de`**(migration `0053`) 위에 **#191 head `9e9f1a0b`**(W2)를 merge한 것 — **충돌 0**(git이 board 2개를 깨끗하게 합쳤다). `run_suite` 시그니처는 **변경 0**이다. 로컬 실 PG·Docker·전체 suite는 돌리지 않았다. **migration 없음**(`0053`은 #202가 이미 넣었다).

설계 문구의 W5 번호는 **이미 `0053`으로 고쳐져 있었다**(#202가 §5-1과 §9를 함께 갱신) — 확인했고 이 PR에서 더 손대지 않았다.

## 1. 이 route는 돈을 쓴다 — 그것이 순서를 정했다

`run_suite`는 case마다 provider adapter를 구동한다. 그래서 읽기 route에서는 단정함의 문제였던 것들이 여기서는 기능이다.

```
permission → body-read → lock → permission → ledger-read → suite-get → adapter-for → permission → run-suite → audit → ledger-write
```

시험이 이 목록을 문자 그대로 단언한다. 권한 확인이 **세 번**인 이유:

| 위치 | 무엇을 막는가 |
|---|---|
| span 1 (body 앞) | 등급 없는 호출자가 **자기 body·키가 어떻게 판정되는지 배우지 못한다.** 초과 body에도 403이고 413이 아니다 |
| lock 뒤, 원장 조회 앞 | **재생을 지킨다** — 두 span 사이에 회수된 membership이 저장된 결과를 읽지 못한다 |
| adapter 해석 뒤, `run_suite` **직전** | **외부 호출이 돈을 쓴다.** 이 줄과 호출 사이에 있는 것은 전부 로컬 읽기다 |

세 번째를 지우는 변이에서 시험 3건이 죽는다(순서 단언 · 위치 단언 · "회수되면 아무것도 사지 않는다").

## 2. adapter는 **이름**이고 endpoint가 아니다

요청은 `adapter: str`(`^[a-z0-9-]+$`, 64자)이고 서버가 `agents.adapter_for`로 해석한다. 그 `BY_NAME`이 구성된 allowlist이므로 호출자가 할 수 있는 최악은 **플랫폼의 네 CLI 중 하나를 고르는 것**이다. 모르는 이름은 아무것도 실행하기 전에 `VAL-0003` 422다.

부정 시험이 `https://evil.example/v1`·`claude-code; curl x`·`../../etc/passwd`·대문자·빈 문자열·65자를 모두 422로 고정한다. **URL을 담을 수 있는 필드였다면 돈을 쓰는 route를 호출자가 고른 host로 조준할 수 있었다.**

## 3. `componentVersions` — 더할 수는 있고 위조할 수는 없다

run의 identity다("에이전트가 72% 받았다"는 어떤 prompt·context·model이 만든 것인지 없이는 뜻이 없다). 그런데 `run_suite`가 `versions.setdefault("adapter", adapter.name)` 식으로 **합치므로**, 호출자가 `{"adapter": "something-else"}`를 보내면 **그 값이 run의 identity로 기록된다** — `setdefault`는 덮어쓰지 않는다.

그래서 서비스가 스스로 채우는 세 키(`adapter`·`contractVersion`·`modelPinned`)를 **경계에서 거부**한다(`VAL-0003` 422, 어떤 키가 문제인지 detail에 적는다). 서비스 시그니처를 바꾸지 않고 막을 수 있는 유일한 자리다. 나머지 키는 통과하고 32개로 제한한다.

## 4. path→suite, 그리고 `0053`이 남긴 NULL

`eval_suites.project_id`는 `0053`이 nullable로 넣었다(그 전에 만든 suite에는 없다). 이 route는 **NULL을 "project 없음"으로 읽는다** — "모든 project의 것"으로 읽으면 `0053` 이전 suite 전부가 아무 project의 승인자에게 열린다. 부재·다른 tenant·다른 project·project 없음 **네 경우가 같은 404**이고 시험이 `traceId`만 뺀 body 4개가 동일함을 단언한다.

**정직하게 적는다**: 코드의 `suite.project_id is None` 검사는 옆의 `!=` 비교와 **중복**이다(path 값은 항상 문자열이라 `None`과 같을 수 없다). 그 줄을 지워도 시험은 통과한다. 결정을 코드가 말하게 두려고 남겼고, 그 사실을 주석과 시험 docstring에 함께 적었다 — 시험이 잡지 못하는 것을 잡는다고 적으면 그게 더 나쁘다.

## 5. IDEM — 재생이 두 번째 청구를 막는다

`deps.serialise_idempotent_write`(W2가 만든 공유 직렬화점) → 권한 재확인 → 원장. 같은 키·같은 body는 **저장된 응답을 재생하고 suite를 다시 돌리지 않는다**(시험이 `ran == []`을 단언). 같은 키·다른 body는 `GRAPH-0002` 409. 원장 payload에 path의 `suiteId`를 넣어 **같은 키를 다른 suite에 쓰면 재생이 아니라 충돌**이다.

키는 필수다(IDEM-1). 여기서는 특히 그렇다 — 응답이 도착하지 않은 요청을 재시도하면 **suite 전체를 다시 돌리고 다시 청구**할 수 있다.

## 6. 오류 번역

| 서비스 code | 정본 | 왜 |
|---|---|---|
| `AUTH_PROJECT_SCOPE` | `AUTH-0030` 403 | |
| `VAL_SCHEMA` | **`GRAPH-0002` 409** | `run_suite`가 "이 adapter는 어떤 model build가 결과를 만들었는지 말할 수 없다"로 raise한다 — 요청은 제대로 됐고 **고른 adapter의 상태**가 거부하는 것이다. `start_eval_run`의 "eval suite not found"도 같은 code인데 이 route는 suite를 먼저 결속하므로 그 분기에 닿지 않는다 |
| `GRAPH_IDEMPOTENCY_CONFLICT` | `GRAPH-0002` 409 | |

표가 세 함수(`run_suite`·`start_eval_run`·`require_project_access`)의 **AST를 읽어** 실제 raise하는 code를 덮는지 단언한다. 표 밖 code는 `SYS-0002` 500이고 내부 메시지가 새지 않는다.

## 7. 감사

성공은 `eval_run.execute` **allow 1건** — `projectId`·`suiteId`·`adapter`·`requireModelPinning`·`totalCases`·`passedGate`만 적는다. **case 내용도 model 출력도 없다**: eval 표는 널리 읽히고 거기 새어 나온 비밀도 비밀이다(ADR-014와 같은 이유). 403은 `#195` 공유 경계가 **denial 1행**을 남기고 action은 bounded template(`POST /v1/projects/{project_id}/eval/suites/{suite_id}/runs`, 62자)이며 식별자가 없다. **404·422·409는 denial이 아님**도 단언한다.

## 8. 검증

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_eval_run_route.py -q` | **64 passed** |
| `pytest tests/core/test_model_version_register_route.py -q` | 91 passed (W2 무회귀) |
| `export_schemas --check` · `check_contract_bindings` · `migration_graph` | PASS (head `0053` 단일) |
| `check_docs` · `check_doc_single_source --ratchet` | exit 0 |

**변이 3건이 죽었다**: 외부 호출 직전 권한 재확인 제거 **3건**, `componentVersions` 거부 제거 **3건**, 재생 분기 무효화 **1건**. 네 번째로 시도한 `project_id is None` 제거는 **죽지 않았고**, 그것이 §4에 적은 중복이다 — 행동이 같으므로 죽지 않는 것이 맞다.

실 PG **9건**은 hosted Backend에서 실행된다: 실행·기록·allow 1건, 재생(run 1건), 키 충돌, sibling project 404, **NULL project 404**(fixture가 실제로 NULL을 만들었는지 먼저 확인한다), 다른 tenant 404(RLS), 등급 없음 403 + denial 1행 전 컬럼, 비회원 403, 무토큰 401 + anonymous 1행. **provider는 한 번도 호출되지 않는다** — suite의 case가 0개라 `run_suite`가 실제 서비스를 끝까지 돌면서도 case loop에 들어가지 않고, adapter는 loop 앞에서 묻는 것만 답하는 stub이다. 빈 suite는 pass가 **아니므로**(`gate_passed`: "0의 0이 통과라는 것은 산술에 관한 사실") `passedGate: false`를 그대로 단언한다.

hosted가 fixture에서 죽지 않도록 **PG-free guard**를 넣었다 — 두 모양(project 결속 / 0053 이전 NULL)을 다 돌려 컬럼·id kind(`eval_suite` → `evs`)를 확인하고 stub adapter가 `MODEL_PINNING`을 든 것도 단언한다.

## 9. 다음 첫 행동

Codex 검토. 이것으로 설계 `#183` §8의 **여덟 중 일곱이 구현**됐다 — 남은 것은 **W3(verify)**이고, `verify_model_version`의 정본이 *"trusted worker hashed the actual weights"* 인데 `canApprove` 사용자가 DB의 digest를 그대로 제출할 수 있으므로 **trusted-worker identity + 실제 object read/hash Evidence 결속 seam**이 정해지기 전에는 구현하지 않는다(설계 §2, Codex F1).
