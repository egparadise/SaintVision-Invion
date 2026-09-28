---
doc_id: "HIST-CLAUDE-EVIDENCE-GAP-TRIAGE-001"
title: "Claude Evidence 대응표 6종 공백 통합 분류 v1.1 — 출처 29행을 distinct 23행으로, BLOCKED_EXTERNAL에서 2건 회수(MLflow·AC-09 runner), actionable 9·관찰 2·외부 12, Claude 큐 5순위 6공백"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:36:40+09:00"
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

## 8. v1.1 — Codex 검토 F-R1~F-R3 반영

세 건 모두 타당했다. **F-R1은 산술이 어긋난 것**이라 가장 부끄러운 쪽이다.

### 8-1. F-R1 — 세는 단위를 섞었다

v1.0이 세 군데에서 어긋났다.

- 표는 **22행**(G-01~06, G-11~14, G-15~26)인데 **21건**이라 적었다.
- BLOCKED_EXTERNAL은 **12행**인데 **11건**이라 적고, "G-19가 출처 둘을 합쳤다"는 각주로 12→11을 정당화했다. 그 합침은 **이미 G-19 한 행으로 표현돼 있으므로** 근거가 되지 못한다 — Codex 지적이 정확하다.
- G-12·G-13을 본문에서는 "공백이 아니다·작업 항목에서 제외"라 하면서 **4건 분류와 총계에는 계속 넣었다.**
- 서론의 "BLOCKED_EXTERNAL이던 것 중 둘을 옮겼다"도 실제로는 G-06 한 건만 가리켰다.

고친 방식: 세는 단위를 **다섯으로 명시**하고(출처 29 / distinct 23 / actionable 9 / 관찰만 2 / BLOCKED 12) 서론에 표로 박았다. `9 + 2 + 12 = 23`이고, 출처 → distinct 대응(합침 7·나눔 1)을 §1-4에 행 단위로 적어 **29 − 7 + 1 = 23**이 보이게 했다. actionable과 관찰을 §1-5에서 분리했으므로 "영원히 닫히지 않는 항목이 큐에 남는" 문제도 사라진다. 제목·frontmatter·두 작업판·이 History·PR 본문을 같은 수로 맞췄다.

### 8-2. F-R2 — G-26을 통째로 외부에 둔 것이 fail-closed가 아니었다

정본 차단 지도(`2026-09-22_21-55-00_KST_review_done_차단지도_Codex.md:42`)가 S09-FE `review`를 **"고정 SHA·원본 입력/출력·skip 0인 100 prompt/30 coding eval과 누출·금지행동 변이 도구 — Gemini … U1~U6 직접 입력 없음"** 으로 적고, FE review map(`:39`)도 "외부 환경이 없어도 가능한 가장 작은 독립 카드"라 부른다. **외부 전제가 없다고 정본이 말하는 것을 내가 BLOCKED_EXTERNAL에 넣었다.**

그래서 **G-07**(내부 runner·변이 도구)과 **G-26**(실제 모델·도구·credential 운영 인수)으로 나눴다. 같은 두 문서가 "합성 eval을 제품 인수로 세지 않음"을 함께 적으므로 인수는 G-26에 남는 것이 맞다.

**owner는 Gemini다.** 그래서 actionable 9에는 넣되 **Claude 큐(§3)에는 넣지 않았다** — 배정되지 않은 것을 내 큐에 넣는 것은 owner 경계를 넘는 일이다. 배정되면 **G-02 다음·G-03 앞**을 권고하고 근거 셋을 §3-0에 적었다. `agent/gemini/s09-fe-matrix`에 S09-FE 매트릭스 v1.1.1이 이미 있어 **owner 쪽에 설계가 선 공백**임도 적었다.

### 8-3. F-R3 — 겹침표가 #174를 놓치고, 비중복 근거가 없고, migration 없음을 확정했다

- **#174 추가**: 역조회 index migration `0050`이 #175와 한 쌍이다. G-04·G-05 설계가 **같은 index를 다시 만들지 않도록** 겹침표에 넣고, §3-4에도 "먼저 읽어야 한다"를 적었다.
- **#170·#177의 비중복 근거**: #170은 AC-11 증거 **집계** 축, #177은 migration **복원 예행**(`0045 snapshot restore → 0046`) 축이고, 둘 다 live archiver의 operational-RPO **비인증 생산자**를 실행 가능하게 만드는 일이 아니다. 표에 적었다.
- **migration 주장 축소**: G-01·G-02·G-11은 확정으로 "없음"이고, **G-03~G-05는 설계 전이므로 확정하지 않는다.** #174가 바로 반례다 — #175의 역조회는 route만으로 끝나지 않고 index가 필요했다. 그래서 "설계 단계에서 persistence·index 필요성을 재판정하고 필요하면 그때 번호를 요청한다"로 바꿨다.

### 8-4. 첫 구현(G-01)에 미치는 영향

없다. Codex도 **G-01 → G-02 순서는 합리적**이라고 확인했고, F-R2가 추가한 G-07은 owner가 다르다. 그래서 이미 작성한 `GET /v1/adapters` HTTP 시험은 그대로 1순위로 올린다.
