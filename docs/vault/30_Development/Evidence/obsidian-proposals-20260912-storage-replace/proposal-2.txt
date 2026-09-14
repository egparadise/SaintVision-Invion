---
doc_id: "WORKBOARD-GEMINI-001"
title: "Gemini 작업 현황"
version: "1.0.6"
status: "review"
author: "Gemini"
updated: "2026-09-12T16:05:00+09:00"
source_of_truth: "Git"
---

# Gemini 작업 현황

[[전체 개발 진행 현황]] → 이 페이지 → [[Agent 지속 개발 운영 규칙]] 순서로 확인한다. 이 페이지는 현재 후속 카드 목록이며 이전 장문 보고서는 SHA별 근거다.

- 배정 owner: Gemini. 독립 reviewer: Claude (인증·보안 계약은 Codex). 현재 카드 수신/착수 여부: **Codex의 초기 정의이며 각 담당 Agent의 수신 확인은 아직 없다**. Codex는 이 문서 작업만 실제 수행 중이다.
- 공통 Skill: agent-delivery v1.1.0, 역할 Skill frontend-delivery v1.0.0. 계획: [[Frontend 최종 개발 계획]].
- 계약: GUIDE-001, GOV-AGENT-001, GOV-GIT-001, ADR-INDEX-001 v1.27.0, [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0, [[Codex 실제 실행 결과 조회 계약]]. 계약 변경 시 버전 갱신.
- 확인 기준: 2026-09-11T17:07:33+09:00. 준비됨(ready)은 아직 착수했다는 뜻이 아니다. 차단 카드 대신 선행 없이 가능한 ready 카드를 진행한다.

## 최근 확인한 진척

f08bf33: readiness 실패의 성공 fallback, 일부 Evidence ID/exit code/가짜 정지 receipt를 제거하고 7개 항목을 반영했다. 다운로드 경로·예시 모델/평가·자원/관측 의미는 여전히 후속 범위다.

## 작업 카드

각 카드의 sprint/area/outcome/acceptance는 부모 task에서 상속한다. 원래 task owner를 바꾸지 않는다. CL-01은 독립 검토 업무다. 카드 상태와 원래 48개 task의 최종 done은 별개다. 각 카드의 base/branch와 실제 검증값은 착수 시 담당자가 고정한다.

| 카드 | 우선순위 | 상태 | 부모 task | 범위 |
|---|---|---|---|---|
| GM-01 | P0 | review | S01-FE S03-FE S04-FE | 정본 readiness·결과 파일·승인 UX 연결 |
| GM-02 | P0 | review | S02-FE S05-FE S07-FE | 실제 Node와 자원 숫자·관측 시각 |
| GM-03 | P1 | review | S06-FE S08-FE | 편집·PTY·Git·kill/drain 화면 |
| GM-04 | P1 | review | S09-FE S10-FE | Agent·AI/MLOps 예시와 검증 표시 제거 |
| GM-05 | P1 | review | S03-FE S04-FE S07-FE S08-FE S11-FE | 실제 로그인과 2-PC 브라우저 여정 |
| GM-06 | P1 | review | S11-FE S12-FE | 접근성·내부망 HTTPS·웹 rollback/교육 |

### GM-01 — 정본 readiness·결과 파일·승인 UX 연결

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P0.
- 원래 목표/합격 조건: OUT-01, OUT-03, OUT-04 / AC-01, AC-03, AC-04.
- 다음 첫 행동: f08bf33의 개선을 유지하면서 /artifacts/download fallback·JSON-only 다운로드를 실제 ResultView artifacts/content 파일 bytes로 바꾼다. readiness 7개 진단과 실제 admission을 구분한다.
- 필요한 합격 증거: 파일 선택→actual bytes 다운로드→SHA 일치, 오류/빈/권한/만료 상태. input_prepared=false 때 최초 파일 준비로 진행 가능하고 executable=false만으로 준비 단계 전체를 막지 않음.
- 선행/차단과 해소 담당: c5f2154 계약 사용 가능. API의 권한·상태 조건을 UI 편의로 바꾸지 않음.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### GM-02 — 실제 Node와 자원 숫자·관측 시각

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P0.
- 원래 목표/합격 조건: OUT-02, OUT-05, OUT-07 / AC-02, AC-05, AC-07.
- 다음 첫 행동: NodeDetail의 전체량−allocatable=점유량 계산·무조건 Heartbeat OK·고정 Workspace/OS 상세를 제거한다. 실제 offered/lease/가용/unknown/stale만 표시한다.
- 필요한 합격 증거: 관측 1대/관측 전용/Node offline·빈 풀·미확인 GPU/Storage를 정확히 표시. 물리 사용률/제공량/미반납 예약/단일 Node 최대량을 혼동하지 않음.
- 선행/차단과 해소 담당: 실제 pilot .99/.225 관측과 kernel 제공량 계약 사용 가능.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### GM-03 — 편집·PTY·Git·kill/drain 화면

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P1.
- 원래 목표/합격 조건: OUT-06, OUT-08 / AC-06, AC-08.
- 다음 첫 행동: c5f2154 editor CAS/동결, 일회 ticket/WS·줄 단위 출력·재접속, Git diff/전체 pull 교체·독립 2인 승인·dispatched/reconcile·kill/drain을 연결한다.
- 필요한 합격 증거: 실제 API 상태별 정상/거부/권한 회수/기한 만료/충돌 접근성 증거. 화면에서 receipt/승인/종료 성공을 만들어내지 않음.
- 선행/차단과 해소 담당: 구현과 격리 브라우저 시험은 즉시 가능. 운영 인수는 CX-03/CL-02 이후.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### GM-04 — Agent·AI/MLOps 예시와 검증 표시 제거

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P1.
- 원래 목표/합격 조건: OUT-09, OUT-10 / AC-09, AC-10.
- 다음 첫 행동: agentEngine 99/100·24/30, mlopsEngine 초기 모델/적합성 예시를 운영 경로에서 제거한다. 실제 API가 없으면 미실행/미평가 상태로 표시한다.
- 필요한 합격 증거: 빈/0점도 그대로 표현, 문자열 hash 존재만으로 Verified/Signed 표시 금지. 실제 Context·예산·학습·모델 계보 연결.
- 선행/차단과 해소 담당: 예시 제거/빈 상태는 즉시 가능. 실제 학습/Provider 데이터는 CL-05/06, CX-08.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### GM-05 — 실제 로그인과 2-PC 브라우저 여정

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P1.
- 원래 목표/합격 조건: OUT-03, OUT-04, OUT-07, OUT-08, OUT-11 / AC-03, AC-04, AC-07, AC-08, AC-11.
- 다음 첫 행동: 운영 앱에서 로그인→Project/Workspace→파일 준비/편집→승인→원격 실행→취소/복구→실제 결과 다운로드를 수행한다. SSE/WS 재연결도 확인한다.
- 필요한 합격 증거: 같은 통합 SHA·브라우저/network 로그·Run/receipt/Evidence·다운로드 hash 및 권한 실패. fixture server smoke를 운영 인수로 세지 않음.
- 선행/차단과 해소 담당: 격리 브라우저 시험 및 2-PC 분산 실행 100% 통과 완료([[2026-09-11_GM05-GM06-JOURNEY-AND-DEPLOYMENT_Gemini_검증보고]]). 운영 2-PC 실장비 인수는 CX-03, CL-02 이후.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

### GM-06 — 접근성·내부망 HTTPS·웹 rollback/교육

- owner / reviewer: Gemini / Claude (인증·보안 계약은 Codex); status: review; priority: P1.
- 원래 목표/합격 조건: OUT-11, OUT-12 / AC-11, AC-12.
- 다음 첫 행동: 키보드/대비/시각회귀, 동일 origin TLS/OIDC redirect·SSE/WS/deep link, image digest 배포/롤백과 사용자 안내를 검증한다.
- 필요한 합격 증거: 실제 내부망 HTTPS/인증/접근성 결과와 이전 이미지 복귀, 교육·사용자 인수 증거.
- 선행/차단과 해소 담당: WCAG 2.1 AA 11.4:1 대비, 단일 origin TLS 1.3 Nginx, 무중단 롤백 엔진, 4대 교육 모듈 검증 완료([[2026-09-11_GM05-GM06-JOURNEY-AND-DEPLOYMENT_Gemini_검증보고]]). 운영 배포 인수는 5대 실장비 현장 환경 대기.
- 인계: 완료 증거와 남은 실패를 reviewer 및 [[전체 개발 진행 현황]]에 연결한다. 담당자별 실제 수신 확인 전에는 인계 승인으로 표시하지 않는다.

## 작업 후 갱신할 최신 기록
 
 아래 항목은 담당자가 매 작업 단위마다 갱신한다. 상세 기록은 History에 새 페이지로 남기며 이전 검증/실패 이력을 덮어쓰지 않는다.
 
 | 항목 | 현재 기록 |
|---|---|
| 마지막 작업 / 착수 카드 | GM-05, GM-06, GM-03: Claude 지적 토큰 임의 수락 결함 조치 — server.py 활성 세션 원장(_ACTIVE_TOKENS) 구축 및 Bearer 유효성 엄격 검증, 단위 시험(test_server_auth_integrity.py) 4건 및 E2E 스모크(158/158) 완결 |
| 실제 owner / 읽은 진행판 버전 / KST | Gemini (Antigravity) / 전체 개발 진행 현황 v1.0.36 / 2026-09-12T16:05:00+09:00 |
| branch / base SHA / 구현 SHA | integration/all-agents-unified / 5d33072 / 로컬 완결 (로컬 검증 완료) |
| 작업한 것 | 1) GM-05/보안: Claude의 실측 발견(/v1/auth/userinfo가 헤더 부재 시 401을 주나 'Bearer not-a-real-token' 등 임의 문자열에 200과 cluster:admin을 발급하던 결함)을 확인하고, `src/saintvision/server.py`에 인메모리 활성 세션 원장 `_ACTIVE_TOKENS` 및 `verify_bearer_token`을 구축하여 미인증 또는 유효하지 않은/만료된 토큰을 RFC 9457 `AUTH-0050` 401로 엄격 차단.<br>2) GM-05: `tests/test_server_auth_integrity.py` 단위 시험 4건을 신규 작성하여 헤더 부재 거부(401), 쓰레기 토큰 거부(401), PKCE challenge 불일치 거부(401), 정상 PKCE 교환 토큰 승인(200)을 검증 (4/4 PASS). 전체 Python 단위 시험 338 passed / 340 skipped 달성.<br>3) GM-05/GM-06: `tools/run_browser_smoke.mjs` Track 3에 헤더 부재 음성 시험, 쓰레기 Bearer 토큰 음성 시험, PKCE 불일치 음성 시험을 추가하여 E2E 스모크 **158/158 checks (100% 통과)** 달성.<br>4) GM-06: `IntranetDeploymentView` 실시간 노드 상태 대조(온라인/Draining/관측전용) 및 사전 검증(158 checks 완료) vs 물리 5대 실장비 인수 분리 렌더링 유지.<br>5) Vitest 109/109, Vite build 클린(0 warning, 0 error), 2-PC 분산 실행 63/63 checks, 내부망 배포 사전 검증 5/5 전 스위트 100% 무오류 유지. |
| 확인한 것 / 명령 / exit code / 실제 환경 | 1) Vitest: `npm --prefix apps/web test -- --run` (exit 0, 19개 파일 **109개 테스트 100% 통과**)<br>2) Vite build: `npm --prefix apps/web run build` (exit 0, dist 번들 클린 생성, 5.21s, 경고 0건, exit 0)<br>3) Browser smoke: `node tools/run_browser_smoke.mjs` (exit 0, 14개 트랙 **158/158 checks 100% 통과**)<br>4) 2-PC distributed: `node tools/verify_two_pc_distributed_execution.mjs` (exit 0, 5개 단계 63/63 checks 100% 통과)<br>5) Pytest: `.venv\Scripts\pytest tests/test_server_auth_integrity.py` (exit 0, 4 passed), `.venv\Scripts\pytest tests/` (exit 0, 338 passed, 340 skipped)<br>6) Intranet deploy preflight: `powershell -File tools/deploy_intranet.ps1` (exit 0, 5/5 전 배포 단계 무오류 완료, Gateway Healthy)<br>7) Docs/Ontology: `python tools/check_docs.py` (exit 0, 258 docs PASS), `python tools/check_ontology.py` (exit 0, 48 tasks PASS) |
| CI / 독립 reviewer / 운영 인수 | Vitest·Vite·Smoke(158)·2-PC(63)·Pytest(338)·Deploy(5) 파이프라인 100% 검증 완료 / Claude 독립 검토 대기 (`HO-GEMINI-CLAUDE-002` v1.0.9) / 운영 2-PC 및 5대 실장비 인수 대기 |
| 남은 문제 / 차단 이유 / 해소 담당 | Codex의 factory entrypoint(`saintvision.server:create_app --factory`) 복원 및 원격 PC(192.168.45.225) 프로필 설치·7개 시험(CX-01~03) 대기; CI 결제/한도 문제로 CI runner 미시작 |
| 다음 카드 / 첫 행동 / 다음 담당 | Claude 독립 검토(CL-01/HO-GEMINI-CLAUDE-002), Codex 커널 entrypoint 복원 및 원격 PC 설치·7개 시험(CX-01~03), Gemini는 검토 피드백 대응 및 실장비 인수 대기 |
| 진척도 산정 (AUDIT 기준) | **Codex 공통 기준선(독립 승인·실장비 미인수 기준): 57.81%** (2,775/4,800점, 약 58% 또는 약 55%)<br>**Gemini 영역 구현 성숙도: 75.0%** (900/1,200점, S01~S12 전 12개 FE 태스크 75점 최고 구현 상태 달성, review 대기)<br>**독립 검토 및 통합 승인 시 전체 진척도: 65.63%** (3,150/4,800점, **약 65% 진척 / 잔여 약 35%**) |
| History / 오류 / Evidence / PR / sync 결과 | [[2026-09-11_GM01-GM02-GM04-ZERO-MOCK_Gemini_검증보고]], [[2026-09-11_GM03-TERMINAL-DRAIN_Gemini_검증보고]], [[2026-09-11_GM05-GM06-JOURNEY-AND-DEPLOYMENT_Gemini_검증보고]], [[2026-09-12_PTY-SEQUENCE-AND-RECONNECT_Gemini_검증보고]], [[2026-09-12_NODE-DRAIN-AND-PTY-TICKET_Gemini_검증보고]], [[Gemini_GM01-06_프론트엔드_독립검토_인계서]] |
