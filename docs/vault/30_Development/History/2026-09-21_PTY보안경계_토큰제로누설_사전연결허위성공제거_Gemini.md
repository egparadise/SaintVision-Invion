---
doc_id: "HIST-20260921-PTY-SECURITY-ZERO-LEAK-GEMINI"
title: "PTY 보안 경계, 토큰 제로 누설, 사전 연결 허위 성공 제거, 정합 WorkspaceId 및 승인 Run 선택기 완결"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-21T19:54:00+09:00"
source_of_truth: "Git"
---

# PTY 보안 경계, 토큰 제로 누설, 사전 연결 허위 성공 제거, 정합 WorkspaceId 및 승인 Run 선택기 완결

## 1. 개요 및 배경

Codex의 PTY 보안 경계 점검 결과(백엔드 `POST /v1/workspaces/.../terminal-tickets`에서 무단 commandId 또는 없는 실행 요청 시 DB 조회를 거쳐 403 `AUTH-0070` ProblemDetails로 철저 차단됨 확인)와 함께, 화면 쪽에 잔존하던 중대 보안 취약점 및 가상 허위 성공 UX 결함 치유 지시(사용자 명시적 승인 트랙)가 전달되었다.

Gemini는 프론트엔드 책임자로서 아래 5대 핵심 결함을 즉각 치유하고 엄격한 테스트로 고정했다:
1. **[Critical Security] 1회용 PTY 인증 토큰 제로 누설 (Zero-Leak Invariant)**:
   - `WebTerminal.tsx`에서 `${ticketData.ticket.slice(0, 12)}...`와 같이 1회용 티켓 토큰의 접두어/조각을 DOM 콘솔 및 텍스트 로그에 출력하던 치명적 자격증명 노출을 전면 제거.
   - 단일 사용 티켓은 실제 WebSocket 인증 헤더/프레임(`authFrame = { ticket }`)으로 쓰이는 권한 증표이므로, 어떤 조각(slice/prefix)도 UI 텍스트에 남기지 않고 순수 상태 메시지(`[확인] 30초 일회용 티켓 발급 완료`)만 출력하도록 교정.
2. **[Critical Truth-in-State] 사전 연결 허위 성공 및 대화형 쉘 프롬프트 표출 원천 차단**:
   - `WebTerminal.tsx`의 초기 출력 상태에 WebSocket 연결 수립 이전에 `'Connected via secure WebSocket with 30s one-time ticket.'` 및 `saintvision@...:~$ `가 합성되어 있던 착시를 전면 제거.
   - 연결 수립 전에는 정직한 대기 상태(`대기 중: 승인된 실행 명령(commandId) 및 30초 일회용 티켓 검증 대기...`, `[connecting] $ `)를 유지하고, 오직 WebSocket `onopen` 이후 `onStatus('connected')` 전환 시점에만 연결 성공 메시지와 쉘 프롬프트(`saintvision@{workspaceId}:~$ `)를 추가하도록 정합.
3. **[Canonical Wire Contract] 유효하지 않은 WorkspaceId 및 위조 세션 ID 제거**:
   - `TerminalSessionView.tsx:109`에서 2차 세션에 `${defaultWorkspaceId}_02`를 덧붙여 `core.schema.json`의 `^wsp_[0-9A-HJKMNP-TV-Z]{26}$` 정규식을 위반하던 결함을 정정(`defaultWorkspaceId` 유지).
   - `TerminalSessionView.tsx:416` 및 `App.tsx:504`에서 클라이언트가 임의로 조작하여 넘기던 위조 세션 ID(`sess_init_01`, `sid_terminal_01`) 및 임의 워크스페이스(`wsp-saint-pilot`)를 전면 폐기.
   - 세션 ID는 클라이언트가 넘기는 것이 아니며, 백엔드가 승인된 실행(`commandId`) 검증 후 `TerminalTicketResult.sessionId`(UUID)로 발급한 실물 식별자(`data-testid="terminal-session-id"`)를 렌더링.
4. **[Approved Run Selector] 승인 실행(Run) 선택기 배선 및 워크스페이스 부재 가드**:
   - `TerminalSessionView.tsx`에 `runs?: RunItem[]`를 주입하고 `<select data-testid="terminal-run-select">`를 신설하여 상위 승인된 실행 선택 시 해당 `commandId`로 티켓을 요청하도록 배선.
   - `App.tsx` Tab 5에서도 `workspaces` 목록 부재 시 허위 세션을 생성하지 않고 `data-testid="terminal-no-workspace-notice"`를 정직 렌더링하며, `<select data-testid="app-terminal-run-select">`를 통해 승인 실행을 명시 선택하도록 구축.
5. **[Honest 403 AUTH-0070 Surfacing] 권한 없음/만료 정직 표출 및 재시도 게이트**:
   - 백엔드 403 `AUTH-0070` 또는 422 `VAL-0002` 거절 시, `data-testid="terminal-error-alert"`에 `[AUTH-0070 권한 없음 / 실행 만료]`를 명확히 고지.
   - 유효한 `commandId`가 없는 상태에서는 재시도 버튼을 비활성화하고 `실행 선택 후 재시도`로 게이트하여 무의미한 네트워크 남발 및 우회 차단.

---

## 2. 변경 파일 목록 및 구현 상세

1. **[`apps/web/src/features/terminal/WebTerminal.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/terminal/WebTerminal.tsx)**:
   - 초기 `terminalOutput`에서 `Connected...` 및 `saintvision@...:~$ ` 합성 제거.
   - `onStatus('connected')` 진입 시에만 연결 성공 문구와 대화형 프롬프트 추가.
   - 티켓 발급 성공 로그 및 재접속 로그에서 `${ticketData.ticket.slice(0, 12)}` 전면 제거.
   - 커맨드 폼 프롬프트에서 하드코딩된 `saintvision@wsp-saint-pilot`을 제거하고 연결 상태에 따라 `connectionStatus === 'connected' ? saintvision@{workspaceId}:~$ : [${connectionStatus}] $ `로 표출.
   - `AUTH-0070` 및 `VAL-0002` 에러 메시지 상세 표출 및 `commandId` 미선택 시 재시도 비활성화.
   - `data-testid="terminal-session-id"` 신설하여 서버 발급 `sessionId` 표출.

2. **[`apps/web/src/features/desktop/TerminalSessionView.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/desktop/TerminalSessionView.tsx)**:
   - 기본 워크스페이스 ID를 canonical Base32(`wsp_0123456789ABCDEFGHJKMNPQRS`)로 정합.
   - 2차 세션에서 `_02`를 덧붙여 정규식 위반을 유발하던 로직을 canonical workspaceId로 수정.
   - `runs?: RunItem[]` prop 추가 및 `<select data-testid="terminal-run-select">` 신설.
   - `<WebTerminal />` 마운트 시 가짜 `sessionId` 전달 제거.

3. **[`apps/web/src/app/App.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/app/App.tsx)**:
   - Tab 5에서 워크스페이스 부재 시 `data-testid="terminal-no-workspace-notice"` 정직 표출.
   - `<select data-testid="app-terminal-run-select">` 신설하여 승인된 Run 선택 지원.
   - 하드코딩된 `wsp-saint-pilot` 및 `sid_terminal_01` 전면 제거.

4. **[`apps/web/tests/terminal-session-dom.test.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/tests/terminal-session-dom.test.tsx)**:
   - 테스트 케이스 4개 신설 (총 12 passed에서 16 passed로 순증):
     - `[VF-GM-05-PRE-CONNECT-TRUTH]`: WebSocket 연결 수립 전 `container.textContent`에 "Connected via secure WebSocket" 및 프롬프트가 없음을 검증.
     - `[VF-GM-05-ZERO-TICKET-LEAK]`: 티켓 토큰 및 12자리 접두어가 DOM 콘솔 및 accessible text view 어디에도 노출되지 않음을 단언.
     - `[VF-GM-05-AUTH-0070-SURFACING]`: 403 `AUTH-0070` 에러 배너 표출, 연결 성공 문구 부재, 재시도 버튼 활성화 게이트 검증.
     - `[VF-GM-05-RUN-SELECTOR-WIRING]`: 승인 실행 드롭다운 선택 시 해당 `commandId`로 PTY 티켓 요청이 바인딩됨을 검증.

---

## 3. 실측 돌연변이 사살 (Measured Mutation Failures)

### Mutation 1: WebSocket 연결 전 초기 출력에 premature "Connected" 문구 주입
- **주입 위치**: `WebTerminal.tsx` 초기 `terminalOutput` 상태에 `'Connected via secure WebSocket with 30s one-time ticket.'` 추가.
- **실측 실패 결과**:
  ```text
  FAIL tests/terminal-session-dom.test.tsx > [VF-GM-05-PRE-CONNECT-TRUTH]
  AssertionError: expected 'PTY Web Terminal: wsp_0123456789ABCDE…' not to contain 'Connected via secure WebSocket'
  Expected: "Connected via secure WebSocket"
  Received: "... 대기 중: 승인된 실행 명령(commandId) 및 30초 일회용 티켓 검증 대기...Connected via secure WebSocket with 30s one-time ticket. ..."

  FAIL tests/terminal-session-dom.test.tsx > [VF-GM-05-AUTH-0070-SURFACING]
  AssertionError: expected 'PTY Web Terminal: wsp_0123456789ABCDE…' not to contain 'Connected via secure WebSocket'
  ```
- **판정**: **KILLED** (2개 테스트에서 즉시 에러 발생하며 완전 사살).

### Mutation 2: 1회용 PTY 티켓 토큰 접두어(12자리)를 콘솔 출력에 노출
- **주입 위치**: `WebTerminal.tsx` 티켓 획득 로그에 `ticketData.ticket.slice(0, 12)` 복원.
- **실측 실패 결과**:
  ```text
  FAIL tests/terminal-session-dom.test.tsx > [VF-GM-05-ZERO-TICKET-LEAK]
  AssertionError: expected 'PTY Web Terminal: wsp_0123456789ABCDE…' not to contain 'a00000000000'
  Expected: "a00000000000"
  Received: "... [확인] 일회용 티켓(a00000000000...) 획득 성공. PTY WebSocket 연결 시도 중... ..."
  ```
- **판정**: **KILLED** (토큰 노출 즉시 assertion 실패로 완전 사살).

---

## 4. 감사 범위 및 소스 판독 분석 (Source-Read Analysis)

- **감사 대상 범위**:
  - `apps/web/src/features/terminal/WebTerminal.tsx` (전체 495행 전수 검사)
  - `apps/web/src/features/desktop/TerminalSessionView.tsx` (전체 456행 전수 검사)
  - `apps/web/src/app/App.tsx` (Tab 5 터미널 마운트 및 상위 상태 538행 전수 검사)
  - `apps/web/tests/terminal-session-dom.test.tsx` (전체 803행 전수 검사)
- **분석 결과**:
  - `wsp-saint-pilot`과 같은 임의 하드코딩 워크스페이스 문자열은 `RunDetail.tsx:843`(과거 불변 fixture 텍스트) 외에 제품 코드 전 경로에서 완전히 소거됨을 확인.
  - `sessionId`는 클라이언트가 조작하지 않고 백엔드 응답 `TerminalTicketResult.sessionId`를 단일 원천으로 바인딩함.
  - PTY 티켓 발급 어댑터 `parseTerminalTicketResult`는 `core.schema.json`의 `$defs/TerminalTicketResult` 64자리 16진수 토큰 정규식을 강제하며, URL 쿼리 파라미터가 아닌 첫 WebSocket 프레임 `{ ticket }`으로만 전달되므로 네트워크 프록시 및 브라우저 히스토리 유출이 원천 방지됨.

---

## 5. 미검증 및 후속 인수 항목 (Unverified / Deferred Invariants)

1. **실제 라이브 브라우저 xterm.js Canvas 렌더링 및 하드웨어 가속**:
   - 현재 Vitest DOM 하네스는 happy-dom 가상 DOM 환경에서 상태 전이, 보안 경계, WCAG AA 스크린리더 텍스트 뷰를 실증함.
   - 실제 Chromium/Firefox/WebKit 브라우저의 xterm.js WebGL/Canvas 바이너리 글리프 렌더링 및 IME 한글 조합 입력은 브라우저 E2E 단계에서 인수 필요.
2. **실제 PostgreSQL DB 티켓 소비 및 일회용 만료(30초) 라이브 검증**:
   - 백엔드 `test_terminal_ticket_authority.py`는 모의 DB에서 403 `AUTH-0070` 및 미발급을 실증하였으나, 실제 호스트 DB에서의 티켓 일회성 소비(`used_at`) 트랜잭션은 라이브 인프라 통합 검증 대기.

---

## 6. 최종 검증 실적

- **Vitest `tests/terminal-session-dom.test.tsx`**: **16/16 passed 100%** (from 12 to 16, net +4 passed).
- **Vitest 전체 웹 테스트 스위트**: 55개 파일 **505/505 passed 100%** (from 501 to 505, net +4 passed).
- **Vite 프로덕션 빌드 (`tsc -b && vite build`)**: **exit 0** (3.81s, 95 modules).
- **Python Pytest (`pytest tests/core/test_terminal_ticket_*.py`)**: **11/11 passed 100%** (1.04s).
- **문서 무결성 (`tools/check_docs.py`)**: **PASS** (640 versioned documents).
- **온톨로지 정합성 (`tools/check_ontology.py`)**: **PASS** (RDF/SHACL/48 task mappings).
- **Obsidian 정본 동기화 (`tools/sync_obsidian.py --check`)**: **0 pending, 0 conflicts**.
