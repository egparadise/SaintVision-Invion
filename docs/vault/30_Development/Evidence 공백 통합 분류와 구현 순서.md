---
doc_id: "CLAUDE-EVIDENCE-GAP-TRIAGE-001"
title: "Claude Evidence 대응표 6종의 공백 통합 분류 v1.2 — 출처 29행을 distinct 23행으로(IMPLEMENTATION/DESIGN 7 · CI_LANE_GAP/NOT_OBSERVED 4 · BLOCKED_EXTERNAL 12), actionable 9 · 관찰 2, Claude 큐 5순위·6공백 (카드 bi, docs-only)"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T14:34:52+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S02-BE", "S02-ST", "S03-ST", "S09-DB", "S09-ST", "S10-BE", "S10-ST", "S12-ST"]
tags: ["evidence", "gap", "triage", "claude", "docs-only"]
---

# Evidence 공백 통합 분류와 구현 순서 (카드 bi)

대상은 Claude 소유 Evidence 대응표 여섯의 공백이다 — **#155**(S12-ST), **#160**(S10-ST), **#161**(S09-DB·ST), **#163**(S03-ST), **#164**(S02-BE·ST), **#166**(S10-BE). 각 표는 자기 범위 안에서 공백을 적었고, 표마다 기준이 조금씩 달랐다. 이 문서는 그것을 **한 자리에 모아 다시 분류**하고 무엇을 어떤 순서로 만들지 제안한다. 구현은 없다(docs-only).

분류 기준은 코디네이터 지시대로 셋이다.

| 분류 | 뜻 |
|---|---|
| **IMPLEMENTATION / DESIGN GAP** | 우리 코드로 메울 수 있다. 계약·route가 새로 필요하면 DESIGN이 먼저다 |
| **CI_LANE_GAP / NOT_OBSERVED** | 코드는 있고 **실행 lane**이 없다(또는 이 호스트에서만 실행되지 않는다) |
| **BLOCKED_EXTERNAL** | 사람의 결정·외부 서비스·물리 자산이 있어야 성립한다. 코드로 만들 수 없다 |

**가장 중요한 재분류 원칙**: *코드로 만들 수 있는 것을 BLOCKED_EXTERNAL로 두지 않는다.* 원래 표에서 BLOCKED_EXTERNAL이던 것 중 **두 건을 옮겼다** — **G-06**(MLflow adapter, §2-4)과 **G-07**(AC-09 고정 SHA eval runner, §2-5). v1.0은 G-06 하나만 옮기고 "둘"이라고 적었는데, 그 문장이 맞는 수가 되도록 G-07을 찾은 것이 아니라 **정본 차단 지도를 다시 읽고 G-26이 잘못 묶여 있었음을 확인**해서 나눈 것이다(Codex F-R2).

### 세는 단위 (v1.1에서 고정)

v1.0의 산술이 어긋나 있었다 — 표는 22행인데 21건이라 적고, BLOCKED_EXTERNAL은 12행인데 11건이라 적고("G-19가 출처 둘을 합쳤다"는 각주로 12→11을 정당화했는데 그 합침은 이미 한 행으로 표현돼 있으므로 근거가 되지 못한다), 그러면서 G-12·G-13은 "공백이 아니다"라고 하면서 4건과 총계에 계속 넣었다. 셋 다 Codex F-R1의 지적이 맞다. 이제 단위를 셋으로 나누고 문서·제목·frontmatter·작업판·History·PR 본문을 같은 수로 맞춘다.

| 단위 | 수 | 뜻 |
|---|---|---|
| **출처 행** | **29** | 표 6종이 각자 적은 공백 행의 합 |
| **distinct 행** | **23** | 중복 7건을 합치고 1건을 둘로 나눈 결과(§1-4의 대응) |
| **actionable** | **9** | 그중 우리 코드로 메울 수 있는 것 |
| **관찰만** | **2** | 분류는 남기되 **할 일이 없는** 것(G-12·G-13) |
| **BLOCKED_EXTERNAL** | **12** | 사람의 결정·물리 자산·외부 서비스 |

9 + 2 + 12 = 23이고, actionable 9 중 **Claude 큐에 들어가는 것은 6**이다(나머지 셋은 §3-0).

## 1. 통합 분류표

원래 표 6종의 공백 **29행**을 **distinct 23행**으로 모았다 — 합친 것 7건, 나눈 것 1건이다(§1-4의 행 단위 대응). 서론의 세는 단위 표와 §1-5의 분류가 모두 같은 23을 쓴다.

### 1-1. IMPLEMENTATION / DESIGN GAP — 7건

| ID | 공백 | 출처 | 상태 | 근거·처리 |
|---|---|---|---|---|
| **G-01** | `GET /v1/adapters`·`GET /v1/adapters/{name}`의 **HTTP 레벨 시험이 없다**. `agents.readiness()`·`adapter_for()` 서비스 시험만 있다 | #166 G2 | **열림 · 설계 불필요** | 실측: `tests/`에서 `v1/adapters` grep **0건**. `tests/test_cli_adapters.py`는 `adapters/agents.py`를 직접 부른다. route는 `api/v1/adapters.py`(78행)이고 `BusinessDispatch`가 서빙한다. 인증·응답 shape·`unknown adapter` 404가 **서빙 표면에서** 한 번도 확인되지 않았다 → **구현 1순위**(§3) |
| **G-02** | 운영 점검 live archiver 2 케이스가 hosted에서 **항상 skip**이라 "운영 RPO 인증 불가" 단언이 실행되지 않는다 | #155 G1 | **열림 · 짧은 설계 필요** | 원인이 실측으로 확인된다: 컨테이너를 `docker network create --internal`(격리 목적)에 붙이고 host port를 publish하지 않으므로 host pytest가 Docker 이름으로 닿을 수 없다(`test_recovery_drill.py:190-197`의 정직한 skip). **port publish로 고치면 격리가 깨진다** — 그 격리가 `archive_command` 실패를 의미 있게 만드는 장치다. 그래서 접근 경로 결정이 먼저다(§3-2) |
| **G-03** | conformance 결과의 **API 노출이 없다**(#146이 FE에서 "미측정"으로 정직화) | #166 G3 | **열림 · 설계 먼저** | 새 route·정본 계약이 필요하다. #158 lineage read와 같은 lane이므로 그 설계의 결정(live `require_project_access`, 정본 `ProblemDetails`, strict 응답, 존재 비노출 404)을 그대로 물려받아야 한다 |
| **G-04** | S09 business lane route 부재 — Context bundle·RunRecord 봉인·pin 조회·eval 실행이 **서비스 함수로만** 있다 | #161 G1 | **열림 · 설계 먼저** | #175(lineage **읽기**)와 #167(release **쓰기** 한 지점)이 덮지 않는 범위다. 넷 다 계약이 새로 필요하고, 읽기/쓰기 등급이 서로 다르다(조회는 membership, 봉인은 승인 등급) |
| **G-05** | model-registry 쓰기 경로 — `register_model_version`·`verify_model_version`·`pin_retention`에 HTTP route 없음 | #160 G2 | **열림 · 설계 먼저** | #167이 **승격(release) 한 지점만** 열었다. 나머지 셋은 #167 History가 스스로 "여전히 HTTP 경로가 없다"고 적는다 |
| **G-06** | MLflow adapter·계약·설정·시험 부재 | #160 E2, #166 G1a | **진행 중(#172·#176)** | **원래 BLOCKED_EXTERNAL이던 것을 옮겼다.** adapter·계약·canonical payload·migration은 우리 코드이고 지금 구현되고 있다. 외부에 막힌 것은 G-16(실 endpoint)뿐이다 |
| **G-07** | **고정 SHA·원본 입력/출력·skip 0인 100 prompt / 30 coding eval runner**와 **누출·금지행동 변이 도구** | #161 E1(원래 G-26의 일부) | **열림 · owner Gemini** | **원래 BLOCKED_EXTERNAL이던 것을 옮겼다(Codex F-R2).** 정본 차단 지도(`2026-09-22_21-55-00_KST_review_done_차단지도_Codex.md:42`)가 이것을 S09-FE `review`의 **Gemini 몫**으로 적고 **"U1~U6 직접 입력 없음"** 이라 명시한다. FE review map(`2026-09-22_Codex_FE_review_map_S02-S12.md:39`)도 "외부 환경이 없어도 가능한 가장 작은 독립 카드"라 적는다. 즉 외부 전제가 없으므로 BLOCKED_EXTERNAL이 아니다. 같은 두 문서가 **합성 평가를 제품·운영 인수로 세지 말라**고 함께 적으므로, 실제 인수는 G-26에 남는다 |

### 1-2. CI_LANE_GAP / NOT_OBSERVED — 4건

| ID | 공백 | 출처 | 상태 | 근거·처리 |
|---|---|---|---|---|
| **G-11** | CLI 4종(claude-code·codex-cli·gemini-cli·antigravity) **실바이너리 적합성**이 hosted에서 `shutil.which` 부재로 skip 4 | #166 G5 | 열림 · 비용 판단 필요 | hosted runner에 바이너리를 provision하면 exact map의 skip 4가 실행 4로 바뀐다. 다만 **우리가 통제하지 않는 서드파티 바이너리를 CI에 설치**하는 것이고, 설치 실패가 CI 실패로 바뀐다. 가치/비용이 가장 나쁜 항목이라 마지막(§3-5) |
| **G-12** | `GET /v1/adapters` 응답의 `remoteNodeReadiness: "unknown"`·`measurementScope: "control-plane-host"`가 **원격 Node 실측이 아님** | #166(대응표 본문) | 열림(정직성은 이미 확보) | route가 스스로 "control-plane 호스트에서 본 것"이라 밝히므로 **오독 위험은 닫혀 있다.** 실제 원격 측정은 물리 Node가 필요하므로 그 부분은 G-19다. 여기서 할 일은 없다 |
| **G-13** | `test_results.py` 14 케이스가 **Windows 이 PC에서** Linux 사설 스토리지 게이트로 skip | #161 G2, #163 G1 | **작업 항목 아님** | hosted Backend·Core(ubuntu)에서는 실행된다(#131 collector가 게이트 사유를 `environment-gated:linux-private-storage`로 명시). 즉 **coverage 공백이 아니라 이 호스트의 사정**이다. 원래 표가 NOT_OBSERVED로 적은 것은 맞지만, 통합 분류에서는 메울 것이 없으므로 구현 후보에서 뺀다 |
| **G-14** | `public.audit_events` RLS ENABLE+FORCE 부재 | #163 G3, #164 G1 | **구현 완료 · 병합 대기(#128)** | `0047_audit_events_isolation`으로 구현·검증됐고 Codex 보안 재검토 승인·hosted 검증 완료. base `1e8baf04` 기준으로만 공백이다 → 병합으로 해소 |

### 1-3. BLOCKED_EXTERNAL — 12건

코드로 만들 수 없는 것만 남겼다. 각 행의 "이미 있는 것"은 **기록·비교 경로가 준비돼 있다**는 뜻이고, 없는 것은 사람의 결정이나 외부 자산이다.

| ID | 공백 | 출처 | 이미 있는 것 |
|---|---|---|---|
| **G-15** | 실 IdP issuer·JWKS·client id | #164 U2/E1 | synthetic issuer·JWKS 시험, Dev IdP(`.work/dev/dev_idp.py`) |
| **G-16** | 실 MLflow endpoint·credential 운영 실측 | #160 E2, #166 G1b | G-06 구현(#172·#176) 뒤에만 성립 |
| **G-17** | 운영 CA·Node client cert·`INV_NODE_MTLS_CA_BUNDLE` | #164 U3/E2 | synthetic PKI(`pki_support.py`), 파일럿 state 내부 CA |
| **G-18** | DNS·호스트명(CP·portal·IdP·Node) | #164 U4/E3 | #134 A2 사용자 결정 대기 |
| **G-19** | 물리 PC 5대 인벤토리·계정·허용 폴더 | #164 U5/E4, #155 G2 | `storage_check.py`·`record_storage_check`·`contributions_needing_attention` |
| **G-20** | Storage 제품 값(contribution 루트·storage-policy·아카이브 대상) | #164 U6/E5 | 체크리스트 §5 |
| **G-21** | verified off-site backup 선언·실 failure-domain bytes | #155 G3 | `record_backup(off_site=…)`·`verify_backup` |
| **G-22** | 실 PITR 복구·운영 RPO/RTO·전체 서비스 복원 | #155 G4 | dry-run·readiness·retention까지 관측(CX-09 Tier-A 결정 B 유예) |
| **G-23** | Release manifest·사용자 인수·물리 Node 브라우저 인수 | #155 G5 | 기록·비교 경로와 collector 항목 |
| **G-24** | 실 5노드 Node→CP Artifact 전송·볼륨 마운트 | #163 E1 | hosted는 synthetic Node·컨테이너(ADR-100) |
| **G-25** | 실 Provider adapter(CX-02)·실 로그인 계정 CLI 인수 | #160 E1, #161 E2, #166 E1 | 계약 적합 시험 20건(모의 프로세스) |
| **G-26** | AC-09 **운영 인수** — 실제 모델·허용 도구 adapter 실행 환경, Provider credential | #161 E1 | G-07의 runner가 만든 합성 결과는 **제품 인수로 세지 않는다**(정본 차단 지도의 조건). 실제 모델·도구·credential이 있어야 성립 |

### 1-4. 출처 29행 → distinct 23행 (대응)

합친 것 **7건**, 나눈 것 **1건**이다. 29 − 7 + 1 = 23.

| 조작 | 출처 | 결과 |
|---|---|---|
| 합침 | #161 G2 + #163 G1 | G-13 (Windows 게이트) |
| 합침 | #163 G3 + #164 G1 | G-14 (`audit_events` RLS) |
| 합침 | #160 E1 + #161 E2 + #166 E1 | G-25 (실 Provider·CLI 인수) — 출처 3 → 1행이라 **−2** |
| 합침 | #160 E2 + #166 G1a + #166 G1b | G-06 + G-16 (MLflow 내부/외부) — 출처 3 → 2행이라 **−1** |
| 합침 | #164 U5/E4 + #155 G2 | G-19 (물리 PC·허용 폴더) |
| 합침 | #160 G2 + #166 G4 | G-05 (model-registry 쓰기 route) |
| **나눔** | #161 E1 | **G-07**(내부 runner) + **G-26**(운영 인수) — **+1** |

### 1-5. actionable 9 · 관찰만 2 · BLOCKED_EXTERNAL 12

| 구분 | ID | 상태 |
|---|---|---|
| **actionable 9** | G-01 | Claude 큐 1순위 |
| | G-02 | Claude 큐 2순위 |
| | G-03 | Claude 큐 3순위 |
| | G-04·G-05 | Claude 큐 4순위(둘을 한 설계로) |
| | G-11 | Claude 큐 5순위 |
| | G-06 | **진행 중** #172·#176 — 새로 만들지 않는다 |
| | G-07 | **owner Gemini** (정본 차단 지도) — 내 큐가 아니다 |
| | G-14 | **구현 완료·병합 대기** #128 |
| **관찰만 2** | G-12 | route가 스스로 측정 범위를 밝혀 오독 위험이 닫혀 있다 |
| | G-13 | hosted(ubuntu)에서 실행된다 — 메울 것이 없다 |
| **BLOCKED_EXTERNAL 12** | G-15~G-26 | §1-3 |

G-04와 G-05를 한 순위로 묶었으므로 **Claude 큐는 5개 순위에 6개 공백**이다(§3).

## 2. 재분류에서 바뀐 것

### 2-1. 진행 중인 것과의 겹침 (새로 만들지 않는다)

| 원래 공백 | 지금 |
|---|---|
| #160 G2·#166 G4의 lineage 조회 route | **#175** (설계 #158 v1.2 구현, 승인) |
| #160 G2·#166 G4의 model-registry 승격 route | **#167** (설계 #152 v1.3 구현, 승인) |
| #163 G2의 S3 ObjectStore 제품 경로 | **#159·#173** |
| #166 G1a의 MLflow | **#172·#176** |
| #163 G3·#164 G1의 `audit_events` RLS | **#128** (승인·병합 대기) |
| **역조회 index migration `0050`** | **#174** (#172 위 stack) — G-04·G-05 설계가 **같은 index·migration을 다시 만들지 않도록** 여기 적는다. #175의 역조회 1단계(`dataset_versions.content_sha256`)가 이 index에 결속되므로 두 PR은 한 쌍이다 |

**비중복도 근거를 적는다** — 아래 둘은 G-02와 축이 다르다.

| PR | 무엇 | G-02와의 관계 |
|---|---|---|
| **#170** | AC-11 evidence aggregator (fail-closed) | 증거 **집계** 축이다. live archiver의 operational-RPO **비인증 생산자**를 실행 가능하게 만드는 일이 아니다 |
| **#177** | hosted migration restore rehearsal (`0045 snapshot restore → 0046`) | migration **복원 예행** 축이다. `archive_mode` 컨테이너를 host에서 도달 가능하게 만드는 문제와 무관하다 |

G-04·G-05는 그 겹침을 **뺀 나머지**다. #167이 승격 한 지점만 열었고 #175가 읽기 둘만 열었으므로, 등록·검증·pin과 S09의 네 범위는 여전히 열려 있다.

### 2-2. 표마다 달랐던 기준을 하나로

- #155는 "메울 수 있으나 이 카드에서 안 만듦"을 NOT_OBSERVED에 넣었고, #166은 같은 성질을 CI_LANE_GAP으로 적었다 → **CI_LANE_GAP**으로 통일했다(G-02, G-11).
- #161·#163은 Windows 게이트를 NOT_OBSERVED(로컬)로 적었다 → 분류는 유지하되 **작업 항목에서 뺐다**(G-13). hosted에서 실행되는 것을 공백으로 세면 분모가 부풀어 오른다.
- #160 G1은 그 PR에서 이미 시험을 추가했으므로 이 표에 없다. 남은 공백만 옮겼다.

### 2-3. 공백이 아닌 것을 공백에서 뺐다

G-12·G-13이다. 둘은 **distinct 23행에 남기고 actionable 9에서 뺀다**(§1-5) — 분류를 지우면 왜 공백이 아닌지가 사라지고, actionable에 두면 영원히 닫히지 않는 항목이 큐에 남는다. v1.0은 본문에서만 "제외"라 하고 수치에는 넣어 두어 둘이 어긋났다(Codex F-R1).

### 2-4. BLOCKED_EXTERNAL에서 옮긴 것

**G-06(MLflow adapter·계약·시험)**. #160 E2가 "MLflow"를 한 줄 BLOCKED_EXTERNAL로 적었고 #166이 G1a(내부 구현)와 G1b(외부 실측)로 쪼갰다. 쪼갠 쪽이 옳다 — adapter·계약·canonical payload·migration은 **우리 코드**이고 실제로 #172·#176에서 만들어지고 있다. 외부에 막힌 것은 실 endpoint·credential(G-16)뿐이다.

### 2-5. BLOCKED_EXTERNAL에서 옮긴 것 둘째 — AC-09 내부 runner (G-07)

v1.0은 #161 E1 "AC-09 제품 지표 3건"을 **통째로** BLOCKED_EXTERNAL에 두었다. 정본 차단 지도를 다시 읽으니 그것이 fail-closed 분류가 아니었다 — `2026-09-22_21-55-00_KST_review_done_차단지도_Codex.md:42`가 S09-FE `review`를 이렇게 적는다:

> 고정 SHA·원본 입력/출력·skip 0인 100 prompt/30 coding eval과 누출·금지행동 변이 도구 — **Gemini** … **U1~U6 직접 입력 없음**; 운영 모델/허용 도구 결정은 별도 … 실제 모델·도구 adapter 실행 환경; **합성 eval을 제품 인수로 세지 않음**

그리고 FE review map(`:39`)이 S09-FE를 "외부 환경이 없어도 가능한 **가장 작은 독립 카드**"라 부른다. 즉 runner·변이 도구는 **외부 전제가 없는 우리 몫**이고, 외부에 막힌 것은 실제 모델·도구·credential로 하는 **운영 인수**뿐이다. 그래서 G-07(내부)과 G-26(운영 인수)으로 나눴다.

**owner는 Gemini다**(정본 지도). 그래서 G-07은 actionable 9에 들어가지만 **§3의 Claude 큐에는 넣지 않았다** — 배정되지 않은 것을 내 큐에 넣는 것은 owner 경계를 넘는 일이다. 코디네이터가 나에게 배정하면 순위 근거는 §3-0에 적어 두었다. 참고로 `agent/gemini/s09-fe-matrix`에 S09-FE 시나리오 매트릭스 v1.1.1(100 prompt / 30 coding eval runner 정의)이 이미 있으므로, 이 항목은 "아무도 손대지 않은 공백"이 아니라 **owner 쪽에 설계가 선 공백**이다.

이 둘이 코디네이터 지시("코드로 만들 수 있는 것을 BLOCKED_EXTERNAL로 두지 마십시오")에 해당하는 실제 위반이었다. 나머지 BLOCKED_EXTERNAL 12건은 사람의 결정·물리 자산·외부 서비스이고, 각 행의 "이미 있는 것"이 우리 쪽 준비가 끝났음을 보인다.

## 3. 구현 순서 제안

한 PR에 한 공백. 설계가 필요한 것은 설계 문서를 먼저 올린다.

### 3-0. 이 순서는 Claude 큐다 (actionable 9 중 6)

G-06은 진행 중(#172·#176), G-14는 병합 대기(#128), **G-07은 owner Gemini**라 큐에 없다. G-07이 나에게 배정된다면 **G-02 다음, G-03 앞**을 권고한다 — 근거는 셋이다. (i) 외부 전제가 없어 지금 실행 가능하고(정본 지도의 "U1~U6 직접 입력 없음"), (ii) 새 route·계약이 필요 없어 G-03·G-04보다 작고, (iii) AC-09의 "금지 행동·누출" 축은 안전 성질이라 conformance 노출(G-03)보다 먼저 관측되는 편이 낫다. 다만 owner 쪽에 이미 설계(S09-FE 매트릭스 v1.1.1)가 있으므로 **중복 착수를 피하는 것이 우선**이고, 배정 없이 내가 시작하지 않는다.

### 3-1. 1순위 — G-01: `GET /v1/adapters` HTTP 레벨 시험 (구현 PR, 작음)

**왜 먼저인가**: 서빙되는 공개 route가 HTTP 표면에서 **한 번도 확인되지 않았다**. 인증 없는 호출, 응답 키 집합, `unknown adapter` 404, `readyCount` 산식이 route를 통과해 나온 적이 없으므로 route 층의 회귀(의존성 주입 실수, 응답 모양 변경)가 아무 시험도 깨지 않는다. 설계가 필요 없고 계약 변경도 없다.

담을 것: 두 route의 200 응답 키 집합과 `measurementScope`·`remoteNodeReadiness`가 응답에 있음(G-12의 정직성을 시험으로 고정), 알 수 없는 adapter 이름의 404, 인증 없는 호출의 거부, `readyCount`가 `installed and headless and loginState == "logged_in"`의 개수와 같음. `agents.readiness()`는 **stub한다** — 이 시험의 대상은 route이고 실 CLI 탐지는 G-11이다.

주의: 이 route는 현재 `HTTPException(404)`를 던진다(`api/v1/adapters.py:69-73`). 정본 `ProblemDetails`가 아니다. **이 PR에서 바꾸지 않는다** — #167이 새 route에만 정본을 적용하고 기존 표면은 건드리지 않기로 한 결정과 같은 이유다. 시험은 **현재 동작을 pin**하고, 정본화가 필요하면 별 카드로 적는다.

### 3-2. 2순위 — G-02: live archiver를 hosted에서 실행 (짧은 설계 → 구현)

**가치는 1순위보다 높다**(운영 RPO "인증 불가"라는 정직성 단언이 hosted에서 한 번도 실행되지 않는다). 그런데 **작고 독립적인 PR이 되기 전에 결정이 하나 필요**하다.

port publish로 고치면 안 된다: 컨테이너는 `docker network create --internal`에 붙어 있고, 그 격리가 `archive_command` 실패를 의미 있게 만드는 장치다. 후보는 둘이다.

| 후보 | 내용 | 대가 |
|---|---|---|
| (a) `docker exec`로 probe | host 도달성 없이 컨테이너 안에서 질의 | `drill._recovery_capability(dsn)`이 host DSN을 받으므로 **실행자를 주입받도록** 바꿔야 한다. 판정 논리를 시험에 복제하지 않으려면 이 쪽이다 |
| (b) 보조 네트워크 | 격리 네트워크는 유지하고 제어용 네트워크를 하나 더 붙인다 | 컨테이너가 두 네트워크에 속하므로 "격리"의 뜻이 약해진다. 무엇이 격리되는지 문서로 다시 정의해야 한다 |

권고는 **(a)**다 — 격리의 정의를 건드리지 않고, 바꾸는 것이 제품 판정 함수의 **인자 모양**뿐이다. 설계 문서 한 쪽을 먼저 올린다.

### 3-3. 3순위 — G-03: conformance 결과 API 노출 (설계 → 구현)

새 route·정본 계약이 필요하다. #158이 정한 원칙을 그대로 쓴다 — live `require_project_access`(읽기는 membership), 정본 `ProblemDetails`, strict 응답, path→row 결속, 존재 비노출 404, 공유 `api/problem.py`. #146이 FE에서 "미측정"으로 정직화한 것을 API가 같은 말로 하게 만드는 일이다.

### 3-4. 4순위 — G-04·G-05: 남은 business lane route (설계 → 구현, 가장 큼)

S09 네 범위(Context bundle·RunRecord 봉인·pin 조회·eval 실행)와 model-registry 셋(등록·검증·pin)이다. **#174의 `0050_dataset_digest_lookup`과 #175의 역조회를 먼저 읽어야 한다** — 조회 route를 더 여는 설계가 같은 index를 다시 만들거나 이미 있는 것을 모르고 지나치면 안 된다(§2-1). **한 설계로 묶는 것을 권고한다** — 읽기/쓰기 등급이 갈리는 방식이 같고(#158 읽기는 membership, #152 쓰기는 `canApprove`), 일곱 개를 따로 설계하면 그 경계가 어긋난다. 다만 구현 PR은 route별로 쪼갠다.

### 3-5. 5순위 — G-11: hosted에 CLI 바이너리 provision (CI 카드)

가치/비용이 가장 나쁘다. 얻는 것은 exact map의 skip 4 → 실행 4이고, 잃는 것은 **우리가 통제하지 않는 서드파티 설치가 CI 실패면으로 들어오는 것**이다. 4개 CLI의 배포 채널·버전 고정 방법을 먼저 조사해야 하고, pinned 이미지가 아니면 CI가 외부 릴리스에 흔들린다. 1~4순위가 끝난 뒤에 다시 판단하기를 권고한다.

## 4. migration 필요 여부

**현재 확인된 신규 migration은 없다. 다만 G-03~G-05는 설계 전이므로 확정하지 않는다**(Codex F-R3).

- **G-01**: 시험만. migration 없음(확정).
- **G-02**: 시험과 도구 함수의 인자 모양. migration 없음(확정).
- **G-11**: CI 설정. migration 없음(확정).
- **G-03·G-04·G-05**: 새 route·계약이고 스키마는 `api/schemas.py`이므로 정본 `core.schema.json`·DB는 바뀌지 않는다 — **지금까지 확인한 범위에서는** 그렇다. 그러나 **#174가 바로 반례다**: #175의 역조회는 route만으로 끝나지 않고 `dataset_versions(tenant_id, content_sha256)` index가 필요했다. 그래서 이 셋은 **설계 단계에서 persistence·index 필요성을 다시 판정하고, 필요하면 그때 번호를 요청한다.**

현재 배정은 `0047`(#128) → `0048`(#159) → `0049`(#172) → `0050`(#174) → `0051`(#176)이다.

## 5. 경계

- 이 문서는 **여섯 대응표의 공백만** 모았다. 대응표가 커버하지 않은 범위(S04~S08, S11 등)는 대상이 아니다.
- **세는 단위는 §서론의 표 하나로 고정했다** — 출처 29 / distinct 23 / actionable 9 / 관찰 2 / BLOCKED 12. v1.0은 이 단위를 섞어 22행을 21건으로, 12행을 11건으로 적었다.
- G-07의 owner는 Gemini다. 분류는 내가 고쳤지만 **착수는 배정받은 뒤**다.
- 각 행의 분류는 **base `1e8baf04` 기준**이다. #128·#159·#167·#172·#175가 병합되면 G-06·G-14와 §2-1의 겹침 행이 해소되고, 그때 이 표를 갱신해야 한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 전부 `grep`·정독이다 — `tests/`의 `v1/adapters` grep 0건, `test_recovery_drill.py:190-197`의 skip 사유와 `:495-506`의 `--internal` 네트워크 생성, `api/v1/adapters.py`의 78행·`HTTPException(404)`.
- **가치 순서는 내 판단이다.** G-02가 G-01보다 가치가 크다고 보면서도 1순위를 G-01로 둔 이유는 G-02가 결정 하나를 먼저 필요로 해서이고, 그 판단이 틀렸다면 순서를 바꾸는 것이 맞다. G-07의 위치 제안(§3-0)도 같은 성질이다.
