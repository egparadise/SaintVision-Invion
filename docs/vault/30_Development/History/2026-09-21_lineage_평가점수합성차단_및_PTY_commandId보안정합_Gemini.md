---
doc_id: "GEMINI-HIST-20260921-006"
title: "모델 계보 및 평가 점수 가상 합성 차단과 PTY commandId 보안 인가 정합"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["mlops", "lineage", "pty", "terminal-ticket", "anti-synthesis", "gemini"]
---

# 모델 계보 및 평가 점수 가상 합성 차단과 PTY commandId 보안 인가 정합

## 1. 개요 및 배경

Claude의 무결성·복제본 백엔드 능력 지도(`2026-09-21_무결성_복제본_백엔드능력지도_Claude.md`) 및 가짜 값 감사(`2026-09-21_계약이_못잡는_가짜값_목록_Claude.md`), 그리고 사용자 지시에 따라 프론트엔드에 잔존하던 두 가지 중대 결함을 전면 치유했다:

1. **모델 계보(Model Lineage) 가짜 평가 점수 합성 차단**:
   - `ModelLineageView.tsx`가 `mlopsEngine.ts`의 하드코딩된 `INITIAL_LINEAGES`(`evalAccuracy: 0.812`, `evalF1Score: 0.845` 등)를 로컬에서 합성하여 실존하지 않는 평가 지표를 표출하고 있었다.
   - 실제 모델 계보 데이터는 saintvision 백엔드 내부 서비스(`services/lineage.py`)에만 존재하며, 외부 HTTP 서빙 엔드포인트가 제공되지 않는다.
   - 사용자가 `0.812`와 같은 가상 수치를 보고 모델을 선택하는 것은 프로덕션 의사결정을 심각하게 왜곡(decision poisoning)하므로, `INITIAL_LINEAGES`를 테스트 전용 픽스처(`TEST_FIXTURE_LINEAGES`)로 격리하고 기본 생성자를 빈 배열(`[]`)로 전환했다.
   - 화면에 `data-testid="lineage-unexposed-notice"`(`role="status"`) 및 `data-testid="lineage-empty-state"`를 신설하여 백엔드 HTTP API 부재 사실을 정직하게 고지하고, HTTP 엔드포인트 신설을 Codex 레인으로 명시 인계했다.
2. **PTY 일회용 티켓 가짜 `commandId` 자리표시자 제거 및 보안 인가 경계 수립**:
   - `WebTerminal.tsx:16`과 `TerminalSessionView.tsx:389`가 가짜 자리표시자 UUID `'11111111-1111-4111-8111-111111111111'`를 하드코딩하고, `App.tsx:504`가 이를 그대로 폴백 소비하고 있었다.
   - PTY 티켓은 승인된 프로세스에 대한 인가 실행 자격증명(authorized execution credential)이다. Codex가 추가한 백엔드 권한 시험(`tests/core/test_terminal_ticket_authority.py`)에서 증명되었듯, 백엔드는 승인 기록이 없는 자리표시자 UUID에 대해 `403 AUTH-0070` ProblemDetails로 거부한다.
   - 클라이언트 불변식 확립: 유효한 승인 명령 신원(`commandId`)이 없으면 **티켓 발급 요청(POST /terminal-tickets)을 일절 수행하지 않는다 (0 network calls)**.
   - 유효한 승인 명령 부재 시 `data-testid="terminal-command-required-notice"`(`role="alert"`) 안내 배너를 표출하고 연결 상태를 `disconnected`로 유지한다.
   - Codex가 구축한 정본 어댑터(`issueTerminalTicket`, `terminalTicketHandshake` from `@/shared/api/terminalTicket`)를 전면 도입하여 응답 페이로드의 엄격한 유효성(64자 16진수 ticket, UUID sessionId, 매칭 websocketPath)을 런타임 검증한다.
   - `TerminalSessionView`, `DesktopShell`, `App`의 상위 파이프라인에서 실제 승인된/예정된 `commandId`를 배선하고 수동 입력 필드(`terminal-command-id-input`)를 제공한다.

---

## 2. 코드 감사 및 소스 변경 분석

### 2.1 `apps/web/src` 전역 `INITIAL_*` 및 Mock 패턴 전수 감사 결과
- `INITIAL_LINEAGES`: `mlopsEngine.ts` 내 모델 계보 및 평가 지표 -> **[치유 완료]** `TEST_FIXTURE_LINEAGES`로 테스트 격리, `MlopsManager` 기본값 `[]` 설정.
- `INITIAL_CODE_FILES`: `DeveloperStudio.tsx` -> 로컬 코드 에디터 신규 파일 버퍼 템플릿(서버 상태 사칭 아님, 로컬 UI 전용).
- `INITIAL_FILES`: `MonacoWorkspaceEditor.tsx` -> 로컬 스크래치패드 메모리 버퍼(서버 상태 사칭 아님).
- `DEFAULT_WINDOWS`: `DesktopShell.tsx` -> 데스크톱 윈도우 매니저 레이아웃 메타데이터.
- **감사 결론**: 이외에 서버 상태를 사칭하거나 가상 성공을 조작하는 잔여 `INITIAL_*` 상수는 존재하지 않음을 확인.

### 2.2 상세 변경 지점
1. [`apps/web/src/features/mlops/mlopsEngine.ts`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/mlops/mlopsEngine.ts):
   - `INITIAL_LINEAGES` -> `TEST_FIXTURE_LINEAGES` (테스트 픽스처 전용 export).
   - `MlopsManager` 생성자: `constructor(initialLineages: ModelLineage[] = []) { this.lineages = [...initialLineages]; }` (기본값 빈 배열, 제로 합성).
2. [`apps/web/src/features/mlops/ModelLineageView.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/mlops/ModelLineageView.tsx):
   - `data-testid="lineage-unexposed-notice"` (`role="status"`): 백엔드 HTTP API 부재 안내 고지.
   - `data-testid="lineage-empty-state"`: 모델 계보 0건 시 가상 파이프라인 그래프 및 허위 평가 점수(Acc 81.2% 등) 렌더링 억제.
   - 상단 통계 카드 정직 표출: "미노출 (API 부재)", "0개 모델 (미노출)".
3. [`apps/web/src/features/terminal/WebTerminal.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/terminal/WebTerminal.tsx):
   - 기본값 `'11111111-1111-4111-8111-111111111111'` 제거 -> `commandId?: string | null`.
   - `isAuthorizedCommandId(commandId)` 가드: 미전달 또는 자리표시자 UUID 전달 시 티켓 발급 요청 즉시 중단(0 network calls).
   - `data-testid="terminal-command-required-notice"` (`role="alert"`): 승인 명령 부재 보안 경고 배너 렌더링.
   - 정본 어댑터 `issueTerminalTicket` 및 `terminalTicketHandshake` 도입으로 런타임 정본 검증 결속.
4. [`apps/web/src/features/desktop/TerminalSessionView.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/desktop/TerminalSessionView.tsx):
   - Line 389 하드코딩 `'11111111-1111-4111-8111-111111111111'` 완전 제거.
   - `TerminalSessionViewProps`에 `commandId?: string | null` 추가 및 상태 동기화.
   - `data-testid="terminal-command-id-input"` 수동 명령 입력 필드 신설.
5. [`apps/web/src/features/desktop/DesktopShell.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/desktop/DesktopShell.tsx):
   - `commandId={runs.find((r) => r.state === 'scheduled' || r.state === 'verifying')?.id || runs[0]?.id || null}` 배선.
6. [`apps/web/src/app/App.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/app/App.tsx):
   - `commandId={selectedRunId || runs.find((r) => r.state === 'scheduled' || r.state === 'verifying')?.id || null}` 배선.

---

## 3. 실측 돌연변이 사살 기록 (Measured Mutation Failures)

### 3.1 돌연변이 1: `isAuthorizedCommandId` 가드 무력화 및 자리표시자 폴백 복원 시
- **돌연변이 내용**: `WebTerminal.tsx`에서 `isAuthorizedCommandId` 검사를 제거하고 기존의 `'11111111-1111-4111-8111-111111111111'` 기본값으로 되돌림.
- **실측 실패 에러**:
  ```
  FAIL tests/terminal-session-dom.test.tsx > [VF-GM-05-NO-COMMAND-NO-TICKET] rejects ticket issuance and suppresses network calls when commandId is absent or placeholder UUID
  AssertionError: expected "spy" not to be called at all, but was called 1 times
  ```
- **판정**: KILLED (0 network calls 불변식 검증 성공).

### 3.2 돌연변이 2: `parseTerminalTicketResult` 정본 와이어 검증기 규격 위반 (65자 티켓 토큰)
- **돌연변이 내용**: 64자 16진수 규격을 벗어난 65자 티켓 문자열 반환.
- **실측 실패 에러**:
  ```
  FAIL tests/terminal-session-dom.test.tsx > [VF-GM-05-TICKET-RETRY] surfaces honest role="alert" when ticket issuance fails and allows retry (Catches Mutation 2)
  AssertionError: expected <div role="alert" ...> to be null
  ❌ 신규 일회용 티켓 발급 및 재연결 실패: TerminalTicketResult response violates the canonical wire contract
  ```
- **판정**: KILLED (정본 어댑터가 비규격 티켓 응답을 즉시 차단함).

### 3.3 돌연변이 3: `MlopsManager` 기본값에 가상 계보(`INITIAL_LINEAGES`) 복원 시
- **돌연변이 내용**: `MlopsManager` 생성자 기본 인자에 과거의 가짜 81.2% 지표가 담긴 픽스처 주입.
- **실측 실패 에러**:
  ```
  FAIL tests/model-lineage.test.ts > ModelLineageView DOM & Anti-Synthesis Harness > [MLOPS-LINEAGE-EMPTY-DEFAULT] renders unexposed notice and safe empty state when no lineages provided by backend
  AssertionError: expected <div data-testid="lineage-empty-state"> to exist in DOM, but got null
  AssertionError: expected textContent not to contain "81.2%", but received "Acc: 81.2%"
  ```
- **판정**: KILLED (가상 평가 지표 합성 차단 불변식 검증 성공).

---

## 4. 미검증 및 후속 인계 경계 (Unverified / Deferred Invariants)

1. **백엔드 HTTP 모델 계보 엔드포인트 신설**:
   - `saintvision` 백엔드의 `services/lineage.py`는 내부 Python 서비스로만 동작하며 HTTP 서빙 라우트가 없음.
   - 해당 엔드포인트 신설 및 API 스키마 발행은 **Codex 레인**으로 인계됨.
2. **실제 PostgreSQL DB 연동 PTY 티켓 발급 및 실 브라우저 WebSocket 연결**:
   - 본 검증은 DOM 단위 및 모의 웹소켓/클라이언트 계약 단위로 실증되었으며, 실제 호스트 PostgreSQL DSN 및 백엔드 실행 환경에서의 실 브라우저 인수는 외부 의존성(PostgreSQL 실행 환경)이 준비된 뒤 수행된다.

---

## 5. 검증 실적 요약

- **Web Vitest 테스트**: 55개 테스트 파일 **501 passed 100%** (기존 499에서 net +2 tests 순증).
  - `tests/model-lineage.test.ts`: 6 passed.
  - `tests/terminal-session-dom.test.tsx`: 12 passed.
- **Web 프로덕션 빌드**: `npm --prefix apps/web run build` (`tsc -b && vite build`) **exit 0 (3.82s)**.
- **Python 코어 계약 테스트**: `.venv\Scripts\python -m pytest tests/core/` **742 passed, 3 skipped (37.75s)**.
  - `tests/core/test_terminal_ticket_authority.py`: 1 passed.
  - `tests/core/test_terminal_ticket_contract.py`: 10 passed.
- **문서 및 온톨로지 무결성 검증**:
  - `python tools/check_docs.py`: **PASS** (638 versioned documents, 48 tasks, 12 outcomes).
  - `python tools/check_ontology.py`: **PASS** (SHACL positive, RDF parsing, 48 task mappings).
