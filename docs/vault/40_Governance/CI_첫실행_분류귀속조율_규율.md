---
doc_id: "GOV-CI-FIRST-RUN-TRIAGE-TEMP-001"
title: "CI 첫 실행 분류·귀속·조율 규율 (임시; 첫 실행 안정화까지)"
status: "active-temporary"
version: "1.0.0"
author: "Claude (governance owner)"
retire_when: "다섯 workflow가 같은 SHA에서 안정 green + 사용자 확인 (아래)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["governance", "ci", "first-run", "triage", "attribution", "coordination", "temporary"]
---

# CI 첫 실행 분류·귀속·조율 규율

> **임시.** CI 개방 승인(결제 복구). 이 CI는 한 번도 안 돌았다. 첫 실행이 triage되어 안정 green이 되면 이 문서를 **삭제**한다(담당·트리거 아래). 실행 결과 읽기는 gh 인증 후. **Codex=워크플로 machinery**(무엇이 언제 도나·증거 수집), **Claude=이 triage/조율.**

## 왜 이걸 미리 세우나
오늘 밤 전수 검증에서 **PG 부재로 1008건 skip**이었다. CI엔 실제 PG가 붙으니 그것들이 **전부 깨어난다.** Go도 처음 컴파일되고 브라우저 레인도 처음 돈다. 즉 **첫 실행에 red가 대량**일 수 있다 — 이는 나쁜 신호가 아니라 **미검증이 검증되는 순간**이다. 그러나 대량이면 조율 문제가 생긴다: 셋이 동시에 달려들어 같은 것을 고치거나 남의 레인을 건드린다. 오늘 밤 착지 30건에도 공유-index 충돌이 5회 날 뻔했고 규칙으로 막았다 — red가 수백이면 그 위험이 커진다. 그래서 **먼저 본다·먼저 나눈다·먼저 멈출 선**을 정해둔다.

## (1) 분류 — 첫 실행에도 baseline은 있다
"처음 실패"와 "돌던 게 깨짐(회귀)"은 다르고 회귀가 급하다. 첫 실행엔 CI 이력이 없지만 **baseline이 있다: 오늘 밤 내 로컬 전수 run**(마감 `8090330c` / 재검증 `0b7d51ed`, working_tree_clean=YES). 거기서 **ran-passed 집합**(CI-스코프 백엔드 1622·vitest 652·tsc·build)과 **not_run 집합**(PG 1008·Go·브라우저·docker)을 정직히 갈라 적어뒀다. 이걸로 첫 CI red를 셋으로 나눈다:
- **A — 새로 드러난 미검증**: 로컬에서 **skip/never-ran**이던 것(PG·Go·브라우저)이 red. **예상됨**(CI의 목적). 회귀 아님 → 레인별 triage 대상.
- **B1 — 회귀**: 로컬에서 **ran-passed**였는데 CI red **이고** 내 run SHA(0b7d51ed)↔CI SHA 사이 그 파일이 **변경됨**. WAS working → **급함**.
- **B2 — 환경차(env-diff)**: 로컬 ran-passed·CI red인데 파일 **미변경**. Python matrix(3.12/3.14)·LF/CRLF·타임존·서비스 설정 차이 → **machinery/config**(Codex) 몫.
- **판별자**: (i) 실패 시험이 내 로컬 **pass-set인가 skip-set인가**, (ii) `git diff 0b7d51ed <CI-SHA> -- <파일>`. 이게 "돌던 게 없었는데 어떻게 구별하나"의 답이다 — 내가 밤새 지킨 ran/not_run 분리가 그대로 첫-실행 분류기가 된다.

## (2) 묶기 — 개수 아니라 원인으로 센다
수백 red라도 원인은 몇 개다. 하나 무너지면 딸려 죽는다.
- **1원인 N실패의 전형**: PG 서비스 기동 실패/마이그레이션 실패 → **모든** postgres 시험 error(1원인). Go 컴파일 실패 → 모든 Go 시험(1원인). 공유 conftest/session-fixture error → 그 사용자 전부. import/collection error → 그 모듈 전부.
- **묶는 법**: (a) **최초-체인-오류 우선**(collection>setup>fixture>assertion) — cascade의 뿌리 하나를 찾으면 수백이 설명된다, (b) 공통 **에러 시그니처**(같은 예외/메시지), (c) 공통 **모듈/파일/레인**.
- **먼저 볼 것**: 각 workflow의 **setup/service/collection 오류**(인프라). 그 하나가 대량을 설명하면, 낱개 assertion을 보기 전에 그것부터. **카운트 = 원인 수(distinct root), 시험 수 아님.**

## (3) 나누기 — 원인별 레인 귀속 (오늘 EvidenceViewer 방식의 다건판)
원인의 **파일/영역**이 레인을 정한다:
- backend Python: `src/saintvision`·`tests/core`·`contracts` = **Claude** / kernel `services/control-plane`·Go = **Codex** / Go 바이너리·operator 경로 = **Codex·운영자**.
- frontend `apps/web` = **Gemini**. CI config `.github/workflows`·서비스 = **Codex(machinery)**.
- **cross-lane 원인**(계약 변경이 양쪽을 깸)은 계약 소유자가 조율.
- **1원인 1소유**: 두 에이전트가 한 원인(같은 파일 집합)에 동시에 손대지 않는다. **개인 index 커밋 + 원인-소유 ledger**(누가 어느 원인 착수 중인지 한 곳에 기록)로 오늘 밤 5회 near-collision의 스케일판을 막는다. 내 레인 원인은 고치고, 남의 레인은 **짚어서 넘긴다**(EvidenceViewer 귀속처럼, 이번엔 다건).

## (4) 멈출 자리 — 첫 산출물은 수정이 아니라 지도
첫 실행이 크면 **한 번에 다 고치려 하지 않는다.**
- **첫 산출물 = triage map**: 원인 목록(개수 아닌 원인) × 레인 × 분류(A/B1/B2) × 딸린 실패 수. 낱개 수정 나열이 아니다.
- **자율로 진행**: (i) 인프라/서비스/config 원인(Codex machinery — 이게 대량을 지우면 재실행 후 재-triage), (ii) 명확·단일레인·**내 것**인 원인.
- **사용자에게 물음(멈출 선)**: (a) 서로 다른 **코드 원인이 다수**이거나 여러 레인에 걸침, (b) 원인이 **결정을 요구**(시험이 제품/계약 가정을 인코딩 — 예: reachability·도메인), (c) 규모가 커서 **우선순위**가 필요할 때. 이때는 map을 제시하고 "무엇부터"를 묻는다.
- 원칙: **map 먼저 · 안전하고 명확한 것만 자율 · 나머지는 우선순위 물음.** B2(env-diff)와 인프라는 대개 Codex가, B1(회귀)은 소유 레인이 급히, A(새 미검증)는 레인별로 순차.

## 종료 조건·담당 (임시가 임시로 지켜지게)
- **트리거**: 다섯 workflow(docs·backend·core·frontend·desktop-browser)가 **같은 SHA에서 안정적으로 green**(첫 대량 red가 triage되어 해소)이고 **사용자가 확인**.
- **담당**: governance/집계 owner(Orca; 세션 없으면 Codex)가 수행.
- **행동(한 커밋)**: 안정화 근거(run URL·SHA)를 History에 기록 + **이 문서 삭제**. 이후엔 [[검증규칙과_세축_canon]] 규칙 8(전수 검증)과 통상 per-push CI가 대신한다. 조건 충족 후에도 남아 있으면 그 자체가 규칙 위반(임시가 영구가 되는 것을 막는다 — [[CI개방전_임시_교차레인_검증절차]]와 같은 패턴).

## 경계
실행은 gh 인증 후. 이 문서는 triage/조율 규율이고, 무엇이 언제 도나·증거 수집은 Codex machinery. 첫 실행 전 세운 예측이므로, 실제 결과가 이 분류와 어긋나면 결과를 따르고 이 문서를 고친다(예측을 결과로 우기지 않는다). 관련: [[CI개방전_임시_교차레인_검증절차]] · [[2026-09-22_통합_전수검증_마무리_및_EvidenceViewer_가짜PASS_회귀_Claude]] · [[검증규칙과_세축_canon]].
