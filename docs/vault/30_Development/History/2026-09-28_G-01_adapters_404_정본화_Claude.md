---
doc_id: "HIST-CLAUDE-G01-ADAPTERS-CANONICAL-404-001"
title: "G-01 후속 — /v1/adapters/{name} unknown adapter 404를 정본 ProblemDetails로, 이름 echo 제거, 단건 응답에 strict 모델 도입(목록은 두 모양이라 보류)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:49:34+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-01", "adapter", "problem-details", "contract", "claude"]
---

# G-01 후속 — adapters 404 정본화 (카드 76)

`#180`이 **의도적으로 pin해 둔 것을 의도적으로 갱신**하는 카드다. base는 `#180` head `9c4ea18b`이고, 정본 body가 있는 `#184` head `c47811b2`(= `#167` `problem.py` + `#189` bounded action + `#195` denial 경계)를 merge했다 — **해소만**. 로컬 실 PG·Docker·전체 suite 없음. migration 없음.

## 1. #180이 남긴 문장을 그대로 이행했다

`#180`의 시험 docstring은 이렇게 적혀 있었다 — *"이 route는 FastAPI `HTTPException` body(`{"detail": ...}`)를 내고 정본 `ProblemDetails`가 아니다. 그것이 이 표면의 기존 모양이고 바꾸는 것은 공개 계약 변경이다 … 그래서 이 시험은 **마땅한 것이 아니라 서빙되는 것**을 기록하며, 정본화는 별 카드다."* 그리고 마지막 줄이 *"Named so a future canonicalisation has to update this test on purpose."* 였다.

이 카드가 그 카드다. 그래서 시험을 **지우지 않고 갱신**했다: 이제 정본 10키·`about:blank`·`RES-0004`·404·`category: RES`·`retryable: false`·`detail: "No such adapter."` 를 단언한다.

## 2. 이름을 더 이상 echo하지 않는다

옛 detail은 `f"unknown adapter: {name}"` 이었다 — **path에 넣은 caller 텍스트를 화면이 렌더하는 body에 그대로** 넣는다. 정본 detail은 고정 문구이고, 이름은 호출자가 이미 가진 요청에 있다. 부정 시험이 `<img src=x onerror=alert(1)>` 를 보내 응답에 `img`·`onerror`가 없음을 단언한다.

## 3. #180의 두 번째 관찰 — 절반은 닫고 절반은 근거를 적었다

`#180`은 *"두 route가 `-> dict`라 생성되는 schema가 없고 `export_schemas --check`가 모양 변화를 알아차릴 수 없다"* 고 기록했다. 조정자가 strict 응답 모델 도입 여부를 판단하라고 했고, **실측으로 갈랐다.**

`agents.readiness()`를 실제로 돌려 행을 읽었다(이 기계에서 `claude-code`는 설치·로그인 상태였고 version `2.1.283 (Claude Code)`였다):

| 모양 | 키 |
|---|---|
| 정상 행 (**11키**, 네 tool 모두 같은 키 집합) | `adapter`·`executable`·`installed`·`path`·`installedElsewhere`·`version`·`loginState`·`loginDetail`·`headless`·`missing`·`instructions` |
| **오류 행 (5키)** — 한 tool이 raise할 때 | `adapter`·`executable`·`installed`·`loginState`·`error` |

- **단건 route는 모델을 도입했다**: 행이 하나이고 모양이 하나다. `AdapterReadinessResponse`(11키 + `probe()`의 `reachable`·`latencyMs` = **13키**, `extra="forbid"`)이고 `contracts/adapter-readiness-response.schema.json`이 생성돼 `--check`가 이제 모양 변화를 잡는다. 타입은 추측이 아니라 관찰이다(`probe()`도 실제로 돌려 `reachable: bool`, `latency_ms: int`를 확인했다).
- **목록 route는 `-> dict`를 유지했다**: 행이 **두 모양**이므로 응답 모델은 없는 키를 default로 채워 **깨진 tool에 대해 화면이 보는 wire 모양을 바꾼다.** 그것은 404 정본화의 부작용으로 할 일이 아니라 **Frontend가 소유한 공개 변경**이다. 시험이 그 근거(오류 행에 `headless`가 없다는 소스 사실)와 현재 상태(`response_model is dict` — annotation에서 온 열린 타입이라 아무것도 고정하지 않는다)를 함께 단언한다.

**남긴 것 하나**: `loginDetail`은 `login_state()`가 돌려준 것이고 그 내용은 **CLI 출력**이다. 열린 mapping으로 선언해 사실을 숨기지 않았지만, 그것을 좁히는 것 — 그리고 tool 출력이 화면용 응답에 있어도 되는지 — 은 이 카드가 답하지 않는 별 질문이다.

## 4. 404는 denial이 아니다

`#195` 경계는 AUTH/SEC의 401·403만 감사한다. 시험이 **unknown adapter 404가 denial을 기록하지 않음**을 단언한다 — not-found를 denial로 적으면 AC-02 trail이 거부당하지 않은 요청으로 가득 찬다. 실 PG에서는 `audit_events` 전체가 0행임을 확인한다.

무토큰은 `#195`가 기록한다. 실 PG 시험이 두 route 각각에서 **401 + anonymous denial 정확히 1행**을 확인하고, action이 **template**(`GET /v1/adapters`, `GET /v1/adapters/{name}`)이며 path 값이 들어 있지 않음을, project가 없으므로 target이 `(NULL, NULL)`임을 단언한다. 이 route들은 테이블을 건드리지 않으므로 실 PG로 확인할 것은 그 행뿐이고, CLI도 실행되지 않는다(무토큰은 route에 닿지 않고, 모르는 이름은 `probe()` 앞에서 거부된다).

## 5. 검증

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_adapters_route.py -q` | **20 passed**(#180의 16에서) |
| `pytest … test_canonical_denial_audit.py test_audit_action.py -q` | 합계 **62 passed** |
| `export_schemas --check` · `check_contract_bindings` · `check_response_freshness` | PASS |
| `check_docs` · `check_doc_single_source --ratchet` | exit 0 |

실 PG 3건은 hosted Backend에서 실행된다.

**작업 중 관찰 하나**: 이 카드에서 `agents.readiness()`를 실제로 돌리자 worktree에 `%SystemDrive%/ProgramData/Microsoft/Windows/Caches/` 가 생겼다 — CLI 하나가 환경변수를 확장하지 않은 채 상대 경로로 캐시를 쓴 것이다. 저장소 내용이 아니므로 지웠고, 명시 staging 규칙 덕분에 commit에는 들어가지 않았다. 제품 코드가 만든 것이 아니라 내가 진단용으로 CLI를 부른 결과다.

## 6. 다음 첫 행동

Codex 검토. 병합 순서는 `#167`·`#189`·`#195`(= `#184`) → 이 PR. 목록 route의 응답 모델과 `loginDetail` 좁히기는 Frontend owner 결정이 필요한 후속이다.
