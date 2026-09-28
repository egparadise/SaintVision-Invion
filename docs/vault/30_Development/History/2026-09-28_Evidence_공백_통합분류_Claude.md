---
doc_id: "HIST-CLAUDE-EVIDENCE-GAP-TRIAGE-001"
title: "Claude Evidence 대응표 6종 공백 통합 분류 — 29행을 21건으로, BLOCKED_EXTERNAL에서 1건 회수, 작업 항목 2건 제외, 구현 순서 5단"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:26:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S02-BE", "S02-ST", "S03-ST", "S09-DB", "S09-ST", "S10-BE", "S10-ST", "S12-ST"]
tags: ["evidence", "gap", "triage", "claude", "docs-only"]
---

# Evidence 공백 통합 분류 (카드 bi)

#155·#160·#161·#163·#164·#166의 공백을 한 표로 모아 다시 분류했다. 산출물은 [[Evidence 공백 통합 분류와 구현 순서]] 하나이고 구현은 없다(docs-only). base `1e8baf04`.

## 1. 한 일

표 6종의 공백 **29행**을 중복 제거해 **21건**으로 모으고 세 분류로 다시 나눴다 — IMPLEMENTATION/DESIGN GAP **6**, CI_LANE_GAP/NOT_OBSERVED **4**, BLOCKED_EXTERNAL **11**. 중복 8건은 Windows 게이트 2, `audit_events` RLS 2, 실 Provider 2, MLflow 2였다.

## 2. 분류가 바뀐 것 세 가지

### 2-1. BLOCKED_EXTERNAL에서 회수한 1건 — MLflow adapter

#160 E2가 "MLflow"를 한 줄 BLOCKED_EXTERNAL로 적었다. 그런데 adapter·계약·canonical payload·migration은 **우리 코드**이고 지금 #172·#176에서 만들어지고 있다. 외부에 막힌 것은 실 endpoint·credential뿐이다. #166이 이미 G1a(내부)·G1b(외부)로 쪼개 둔 쪽이 옳았고, 통합 표는 그 구분을 따른다. **코디네이터 지시("코드로 만들 수 있는 것을 BLOCKED_EXTERNAL로 두지 마십시오")에 해당하는 실제 위반은 이 한 건이었다** — 나머지 11건은 사람의 결정·물리 자산·외부 서비스다.

### 2-2. 공백이 아닌 것 2건을 작업 항목에서 뺐다

- **Windows 사설 스토리지 게이트**(#161 G2·#163 G1): hosted Backend·Core(ubuntu)에서는 실행된다. 분류는 NOT_OBSERVED(로컬)로 두되 **메울 것이 없다.** hosted에서 도는 것을 공백으로 세면 분모가 부풀어 오른다.
- **`GET /v1/adapters`의 `remoteNodeReadiness: "unknown"`**: route가 스스로 "control-plane 호스트에서 본 것"이라 밝히므로 오독 위험이 이미 닫혀 있다. 실제 원격 측정은 물리 Node(BLOCKED_EXTERNAL) 항목이다.

### 2-3. 표마다 달랐던 기준을 하나로

#155는 "메울 수 있으나 이 카드에서 안 만듦"을 NOT_OBSERVED에, #166은 같은 성질을 CI_LANE_GAP에 넣었다 → **CI_LANE_GAP**으로 통일했다.

## 3. 실측으로 확인한 것

- **`GET /v1/adapters`에 HTTP 레벨 시험이 없다**: `tests/`에서 `v1/adapters` grep **0건**. `tests/test_cli_adapters.py`는 `adapters/agents.py`를 직접 부른다. 즉 인증·응답 shape·`unknown adapter` 404가 **서빙 표면에서** 확인된 적이 없다 → 구현 1순위.
- **live archiver skip의 원인**: 컨테이너가 `docker network create --internal`에 붙어 있고 host port를 publish하지 않으므로 host pytest가 Docker 이름으로 닿을 수 없다(`test_recovery_drill.py:190-197`의 정직한 skip, `:495-506`의 네트워크 생성). **port publish로 고치면 그 격리가 깨진다** — 격리가 `archive_command` 실패를 의미 있게 만드는 장치다. 그래서 짧은 설계가 먼저이고, 권고는 `docker exec` probe(판정 함수의 인자 모양만 바꾼다)다.
- 기존 `/v1/adapters` route는 `HTTPException(404)`를 던진다 — 정본 `ProblemDetails`가 아니다. 1순위 PR은 **현재 동작을 pin하고 바꾸지 않는다**(#167이 새 route에만 정본을 적용한 결정과 같은 이유).

## 4. 제안한 구현 순서

1. **G-01** `GET /v1/adapters`·`/{name}` HTTP 레벨 시험 — 설계 불필요, 계약 변경 0.
2. **G-02** live archiver hosted 실행 — 짧은 설계 먼저(접근 경로 후보 (a) `docker exec` / (b) 보조 네트워크, 권고 (a)).
3. **G-03** conformance 결과 API 노출 — 설계 먼저(#158 원칙 상속).
4. **G-04·G-05** 남은 business lane route 7개 — 한 설계로 묶고 구현 PR은 route별로 쪼갠다.
5. **G-11** hosted CLI 바이너리 provision — 가치/비용이 가장 나쁘다. 1~4 뒤 재판단 권고.

**가치 순서가 내 판단임을 문서에 적었다** — G-02가 G-01보다 가치가 크다고 보면서도 1순위를 G-01로 둔 이유는 G-02가 결정 하나를 먼저 필요로 해서다.

## 5. migration

**1~5순위 어디에도 migration이 없다.** 시험·도구 인자·새 route 계약(`api/schemas.py`, 정본 `core.schema.json`·DB 무변경)·CI 설정뿐이다. 그래서 이 카드에서 번호를 요청하지 않는다. 현재 순서는 `0047`(#128) → `0048`(#159) → `0049`(#172) → `0050`(#174) → `0051`(#176)이다.

## 6. 경계

- 여섯 대응표의 공백만 모았다. 그 표가 다루지 않은 범위는 대상이 아니다.
- 분류는 **base `1e8baf04` 기준**이다. #128·#159·#167·#172·#175가 병합되면 MLflow·`audit_events`·겹침 행이 해소되고 표를 갱신해야 한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 실측은 전부 `grep`·정독이다.
- `check_docs`·`check_doc_single_source --ratchet` exit 0.

## 7. 다음 첫 행동

Codex 검토를 받고, 승인되면 1순위(G-01)를 작은 구현 PR로 올린다. 그 PR은 base `integration/all-agents-unified`이고 진행 중인 것과 겹치지 않는다.
