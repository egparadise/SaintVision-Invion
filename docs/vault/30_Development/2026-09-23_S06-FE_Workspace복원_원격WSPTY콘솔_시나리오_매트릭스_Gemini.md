---
doc_id: "GEMINI-S06-FE-SCENARIO-MATRIX-20260923"
title: "S06-FE Workspace 복원·원격 WS/PTY 콘솔 UI 시나리오 매트릭스 (Gemini)"
version: "1.1.1"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-23T07:15:00+09:00"
source_of_truth: "Git"
tags: ["s06-fe", "acceptance-matrix", "workspace", "recovery", "restore", "checkout", "pty-console", "gemini"]
---

# S06-FE Workspace 복원·원격 WS/PTY 콘솔 UI 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[S06 개발 작업공간]] (OUT-06 / AC-06)
> - [[Frontend 최종 개발 계획]]
> - [[Codex Workspace 공개 API와 실행 커널 통합 계약]]
> - [[설계 충돌 정정 및 ADR]] (ADR-005, ADR-028, ADR-041, ADR-100)
> - `apps/web/src/features/workspaces/WorkspaceList.tsx`
> - `apps/web/src/features/workspaces/WorkspaceCreateModal.tsx`
> - `apps/web/src/features/desktop/TerminalSessionView.tsx`
> - `apps/web/src/features/terminal/WebTerminal.tsx`
> - `services/control-plane/src/inv/workspace_recovery.py`
> - `services/control-plane/src/inv/app.py`
> - `packages/contracts-ts/src/index.ts`
> - `tests/test_route_coverage.py`

---

## 1. 개요 및 수용 목표 (OUT-06 / AC-06)

본 문서는 SaintVision 격리 실행 및 작업공간 제어 평면의 **S06-FE (Workspace 복원·원격 WS/PTY 콘솔 UI)** 트랙을 완결하기 위해, 코디네이터 지시 및 Codex 카드 6 착지(`a4bf2cee`, workspace restore/checkout 라우트 및 `replayed: boolean` 필드), `apps/web` Workspace/Terminal 화면 실제 코드를 기준으로 수립한 **docs-only 시나리오 매트릭스 정본 초안(v1.1.1)**이다.

본 문서는 `WorkspaceList`(5대 상태), `WorkspaceCreateModal`(2단계 생성 안내), `TerminalSessionView`/`WebTerminal`(30초 일회용 PTY 티켓 및 노드 OS 분기) 화면의 사용자 여정별 기대를 **실제 프런트엔드 컴포넌트 셀렉터(`data-testid`, `role`, 태그)** 및 **커널 오류 코드(`VAL-SCHEMA`, `AUTH-PROJECT-SCOPE`, `LEASE-0003`, `GRAPH-0003`, `IDEM-0001` 등)**와 1:1로 엄격히 대응시키며, 존재하지 않는 셀렉터나 임의 합성 값의 기재를 전면 금지(Zero Fake Selectors / Zero Fake Values)한다.

### 1.1 합격 기준 (AC-06)
- **정직한 5대 수명주기 상태 렌더링**:
  - `WorkspaceList`는 `ready`, `provisioning`, `suspended`, `deleting`, `deleted` 5개 상태를 명확한 시각적/접근성 스타일로 표기하며, 빈 작업공간 상태(0개)를 `role="status"` 및 `aria-live="polite"`로 정직하게 고지한다.
- **프로비저닝과 커널 prepare 단계의 엄격한 분리**:
  - 작업공간 생성 모달(`WorkspaceCreateModal`)은 작업공간 생성이 `provisioning` 레코드 등록일 뿐이며, 물리 노드 배치·자원 할당·체크아웃은 커널 `prepare` 단계임을 안내 배너(`workspace-create-phase-notice`)로 정직 고지한다.
- **스냅샷 복원 및 멱등 Replay 무결성 (Codex a4bf2cee 결속)**:
  - `POST /v1/projects/{project}/runs/{run_id}/restores/{restore_id}`는 초기 요청 시 `replayed: false`, 동일 요청 시 `replayed: true`를 반환한다.
  - Replay 시에도 프로젝트 인가 권한이 재검증되며, 권한 폐기 시 저장 응답 재사용 없이 403 `AUTH-PROJECT-SCOPE`로 엄격 차단된다.
- **체크아웃과 물리 자원 반환 가드 (LEASE-0003)**:
  - 체크아웃(`POST .../checkouts/{id}`)은 물리 리스가 반환되지 않았을 때 409 `LEASE-0003`으로 거절되며, `recovering` 상태가 아닐 때 409 `GRAPH-0003`으로 차단된다.
- **원격 WS/PTY 30초 일회용 티켓 및 관측 가드**:
  - PTY 터미널은 승인된 `commandId` 없이는 티켓 발급 및 웹소켓 연결을 일체 시도하지 않으며 ($0$ network calls), 관측 전용 노드(`schedulable: false`) 편입 시도를 차단한다.
  - **원격 WS/PTY 실 5노드 양방향 스트리밍 실측 항목은 '5노드 랩 후' UNMEASURED로 표기**한다.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **WSP** | **작업공간 인벤토리 및 5대 수명주기**<br>(Workspace Inventory & Lifecycle) | `WorkspaceList.tsx`<br>`WorkspaceCreateModal.tsx`<br>`types.ts` | • 5대 상태(`ready`, `provisioning`, `suspended`, `deleting`, `deleted`) 배지<br>• 정상 조회 0개 빈 상태 고지 (`workspaces-empty-state`, `aria-live="polite"`)<br>• 명칭 2–128자 클라이언트/백엔드 스키마 제약 (`VAL-SCHEMA`)<br>• 2단계 생성 안내 배너 (`workspace-create-phase-notice`) |
| **REC** | **스냅샷 복원 및 멱등 Replay**<br>(Snapshot Restore & Replay) | `services/control-plane/src/inv/workspace_recovery.py`<br>`contracts-ts/src/index.ts` | • `POST /v1/projects/{p}/runs/{r}/restores/{id}` 불변 복원<br>• 최초 요청: 201 Created (`replayed: false`)<br>• 동일 요청 Replay: 201 Created (`replayed: true`)<br>• Replay 권한 재검사: 권한 회수 시 403 `AUTH-PROJECT-SCOPE`<br>• 타 프로젝트/테넌트 격리: 404 ProblemDetails |
| **CHK** | **작업공간 체크아웃 및 자원 해제 가드**<br>(Workspace Checkout & Lease Guard) | `workspace_recovery.py`<br>`contracts-ts/src/index.ts` | • `POST .../restores/{r_id}/checkouts/{c_id}`<br>• 물리 리스 미반환 시 409 `LEASE-0003` ("Checkout awaits physical resource release")<br>• 비-recovering 상태 시 409 `GRAPH-0003`<br>• 체크아웃 식별자 충돌 시 409 `IDEM-0001`<br>• 소스 체크포인트 해시 불일치 시 422 `VERIFY-0023` |
| **PTY** | **원격 WS/PTY 콘솔 및 티켓 경계**<br>(Remote WS/PTY Console & Tickets) | `TerminalSessionView.tsx`<br>`WebTerminal.tsx`<br>`terminalTicket.ts` | • 30초 암호학적 일회용 PTY 티켓 발급 (`POST /terminal-tickets`)<br>• 승인 `commandId` 부재 시 네트워크 요청 완전 차단 ($0$ requests)<br>• 관측 전용 노드(`schedulable: false`) PTY 차단 (`terminal-session-error-alert`)<br>• 오프라인 명령 전송 차단 (`terminal-disconnected-cmd-alert`)<br>• **5노드 랩 실측 항목: UNMEASURED ('5노드 랩 후')** |

---

## 3. 세부 시나리오 매트릭스 (14대 시나리오)

### 3.1 작업공간 인벤토리 및 5대 수명주기 (Workspace Inventory, WSP-01 ~ WSP-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **WSP-01** | **작업공간 목록 조회 및 5대 상태 렌더링** | `WorkspaceList.tsx` | 프로젝트 내 5대 상태의 작업공간 데이터 인입 | 화면 마운트 및 렌더링 | • 상태 배지: `span[data-testid="wsp-status-${wsp.id}"]`<br>• 5대 상태: `ready`, `provisioning`, `suspended`, `deleting`, `deleted`<br>• 노드 정보: `strong:has-text("${nodeHostname}")` | • 각 작업공간의 상태가 지정된 색상/보더/텍스트(예: `준비 완료 (Ready)`, `프로비저닝 중 (Provisioning)`)로 렌더링됨.<br>• 타겟 노드 호스트명 및 격리 모드(`isolationMode`), 자원 한도(Cores/GB)가 정확히 표출됨. |
| **WSP-02** | **작업공간 부재 시 정상 0개 빈 상태 고지** | `WorkspaceList.tsx` | 프로젝트 내 등록된 작업공간이 0개 (`workspaces: []`) | 화면 마운트 | • 빈 상태 컨테이너: `div[data-testid="workspaces-empty-state"][role="status"][aria-live="polite"]`<br>• 안내 제목: `h3:has-text("등록된 작업공간이 없습니다 (정상 조회 결과: 0개).")`<br>• 생성 유도 버튼: `button:has-text("+ 새 Workspace 생성하기")` | • `role="status"` 및 `aria-live="polite"` 속성이 DOM 상에 존재하여 스크린리더 접근성 보장.<br>• 단순 네트워크 오류가 아닌 정상적인 0개 조회 결과임을 사용자에게 정직하게 고지. |
| **WSP-03** | **신규 작업공간 생성 모달 및 2단계 생성 안내 배너** | `WorkspaceCreateModal.tsx` | 작업공간 목록 화면에서 `+ 새 Workspace 생성` 클릭 | 모달 오픈 | • 모달 다이얼로그: `div[role="dialog"][aria-modal="true"]`<br>• 단계 안내 배너: `div[role="status"][data-testid="workspace-create-phase-notice"]`<br>• 명칭 입력창: `input[data-testid="workspace-name-input"]`<br>• 제출 버튼: `button[data-testid="workspace-submit-btn"]` | • `aria-modal="true"` 모달 오픈 확인.<br>• 생성 액션이 `provisioning` 레코드 등록일 뿐이며 실제 노드/자원 배치는 커널 `prepare` 단계임을 안내하는 배너 노출 확인.<br>• 기본 제출 버튼 문구 `Workspace 생성 (Provisioning)` 표출. |
| **WSP-04** | **작업공간 명칭 스키마 제약(2–128자) 위반 차단** | `WorkspaceCreateModal.tsx` | 생성 모달 오픈 상태 | Case A: 1글자 입력 후 제출<br>Case B: 129글자 초과 입력 | • 입력창: `input[data-testid="workspace-name-input"]`<br>• 에러 배너: `div[role="alert"]`<br>• 백엔드 스키마: `minLength: 2, maxLength: 128` | • 1글자 입력 시 `작업공간 명칭은 최소 2자 이상이어야 합니다` 에러 표출 및 API 요청 차단 ($0$ requests).<br>• 백엔드 직접 전송 시 HTTP 422 `VAL-SCHEMA` 반환 확인. |

---

### 3.2 스냅샷 복원 및 멱등 Replay (Snapshot Restore & Replay, REC-01 ~ REC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **REC-01** | **체크포인트 스냅샷 불변 복원 요청 및 receipt 수령** | `workspace_recovery.py`<br>`core.schema.json` | `recovering` 상태의 Run 및 `ready` 상태의 체크포인트 스토리지 객체 존재 | `POST /v1/projects/{project}/runs/{run_id}/restores/{restore_id}` 호출 | • 요청 본문: `WorkspaceRestoreInput = { workspaceId, sourceAttempt: 1, stepId, expectedVersion }`<br>• 응답 모델: `WorkspaceRestoreView`<br>• 응답 상태: HTTP 201 Created | • 백엔드가 체크포인트 바이트 해시 및 크기를 대조하여 불변 세대(`generation`) 생성.<br>• 응답 본문에 `replayed === false` 확인.<br>• `WorkspaceRestoreView` 스키마 계약 100% 충족. |
| **REC-02** | **동일 복원 요청 201 멱등 Replay 관측 (replayed: true)** | `workspace_recovery.py` | REC-01 복원 완료 후 동일한 `restore_id`와 본문으로 재요청 | 동일 복원 API 2차 호출 | • API 경로: 동일 `POST .../restores/{restore_id}`<br>• 응답 상태: HTTP 201 Created<br>• 응답 본문: `replayed: true` | • 스냅샷 저장소의 물리적 재발행이나 중복 디스크 I/O 없이 단일 부수 효과만 발생.<br>• 응답 내 `replayed === true` 반환 확인 (Codex a4bf2cee 계약). |
| **REC-03** | **프로젝트 권한 폐기 후 Replay 차단 (AUTH-PROJECT-SCOPE)** | `workspace_recovery.py` | 1차 복원 완료 후 사용자의 프로젝트 접근 권한(`project_grants`) 비활성화 | 동일 복원 API 재호출 | • 요청 헤더: `Authorization: Bearer <revoked-user>`<br>• 응답 규격: HTTP 403 Forbidden, `application/problem+json`<br>• 본문: `code: "AUTH-PROJECT-SCOPE"` | • 기발급된 복원 건이더라도 Replay 시점에 프로젝트 권한을 엄격히 재검증.<br>• 저장된 Replay 응답을 무단 반환하지 않고 **HTTP 403 `AUTH-PROJECT-SCOPE`** 거절. |

---

### 3.3 작업공간 체크아웃 및 자원 해제 가드 (Workspace Checkout, CHK-01 ~ CHK-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **CHK-01** | **복원 스냅샷 대상 가상 체크아웃 수행** | `workspace_recovery.py`<br>`core.schema.json` | 복원(`restore_id`) 완료 및 물리 자원 리스 정상 반환 완료 상태 | `POST .../restores/{restore_id}/checkouts/{checkout_id}` 호출 | • 요청 본문: `WorkspaceCheckoutInput = { expectedVersion }`<br>• 응답 모델: `WorkspaceCheckoutView`<br>• 응답 상태: HTTP 201 Created | • 작업용 쓰기 가능 세대(Working generation) 발행 및 파일시스템 무결성 검사 통과.<br>• `WorkspaceCheckoutView`(`checkoutId`, `generation`, `stepId`, `sha256`, `replayed: false`) 수령. |
| **CHK-02** | **물리 리스 미반환 시 체크아웃 거절 (LEASE-0003)** | `workspace_recovery.py` | 이전 실행의 물리 리스(`inv.resource_leases`)가 아직 반환되지 않음 (`released_at IS NULL`) | 체크아웃 API 호출 시도 | • 응답 규격: HTTP 409 Conflict, `application/problem+json`<br>• 본문: `code: "LEASE-0003"`<br>• 상세: `detail: "Checkout awaits physical resource release"` | • 노드의 잔여 실행이 완전히 종료되고 Lease가 회수되기 전까지 체크아웃 차단.<br>• HTTP 409 `LEASE-0003` 반환 및 화면에 자원 반환 대기 경보 표출. |
| **CHK-03** | **비-recovering 상태 또는 버전 불일치 거절 (GRAPH-0003)** | `workspace_recovery.py` | Run 상태가 `recovering`이 아니거나(예: `running`, `succeeded`), `expectedVersion` 불일치 | 체크아웃 API 호출 시도 | • 응답 규격: HTTP 409 Conflict, `application/problem+json`<br>• 본문: `code: "GRAPH-0003"`<br>• 상세: `detail: "Checkout requires current recovering attempt"` | • 실행 수명주기 불변식 위반으로 HTTP 409 `GRAPH-0003` 반환.<br>• 유효하지 않은 시점의 체크아웃 시도로부터 작업공간 파일시스템 오염 원천 방지. |

---

### 3.4 원격 WS/PTY 콘솔 및 티켓 경계 (Remote WS/PTY Console, PTY-01 ~ PTY-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **PTY-01** | **30초 암호학적 1회용 PTY 티켓 발급 및 배지 표출** | `TerminalSessionView.tsx`<br>`WebTerminal.tsx` | 승인된 실행 `commandId` 입력 및 정상 노드 선택 | 세션 탭 활성화 | • 티켓 배지: `strong[data-testid="pty-ticket-badge"]`<br>• 배지 텍스트: `30초 암호학적 1회용 PTY 티켓 (mTLS 격리)`<br>• API 경로: `POST /v1/workspaces/{id}/terminal-tickets` | • 화면 상단에 30초 일회용 티켓 및 mTLS 격리 배지 표출.<br>• 백엔드 티켓 발급 성공 및 30초 시효 카운트다운 진입. |
| **PTY-02** | **관측 전용 노드(schedulable: false) 대화형 PTY 세션 생성 차단** | `TerminalSessionView.tsx` | 클러스터 내 관측 전용 노드(`Node-04`) 선택 | 새 세션 열기 드롭다운에서 관측 전용 노드 선택 | • 셀렉트 드롭다운: `select[data-testid="new-session-select"]`<br>• 옵션 라벨: `[관측 전용 - PTY 불가]` 및 `disabled=true`<br>• 에러 알림: `div[role="alert"][data-testid="terminal-session-error-alert"]` | • 드롭다운 상에 관측 전용 노드가 disabled 처리됨.<br>• 강제 세션 생성 시도 시 `노드 ...은(는) 관측 전용 노드로 대화형 PTY 세션을 생성할 수 없습니다.` 에러 배너 표출 및 세션 추가 차단. |
| **PTY-03** | **오프라인/미연결 상태 명령 전송 거절 및 경고 표출** | `WebTerminal.tsx` | PTY 웹소켓 연결이 끊어진 상태 (`connectionStatus !== 'connected'`) | 터미널 입력창에 명령어 입력 후 Enter | • 입력 폼: `form[data-testid="terminal-input-form"]`<br>• 입력창: `input[data-testid="terminal-command-input"]`<br>• 경고 배너: `div[role="alert"][data-testid="terminal-disconnected-cmd-alert"]` | • 가짜 성공이나 임의 로컬 에코를 전면 금지하고 `role="alert"` 경고 표출.<br>• 재접속 버튼(`button[data-testid="terminal-reconnect-btn"]`) 노출. |
| **PTY-04** | **5노드 랩 실측 항목 (원격 WS/PTY 실 양방향 스트리밍·OS 쉘 분기)** | `TerminalSessionView.tsx`<br>`WebTerminal.tsx` | 실제 물리/Docker 5노드 랩 환경 구성 완료 시점 | 원격 PTY 웹소켓 실연결 및 명령 송수신 | • 웹소켓 경로: `wss://.../v1/workspaces/{wsp}/terminals/{sess}`<br>• 쉘 분기: Windows 노드는 `POWERShell`, Linux 노드는 `BASH`<br>• 결과 상태: **UNMEASURED ('5노드 랩 후')** | • **[실측 판정: UNMEASURED]**<br>• 코디네이터 지시 및 Codex 카드 6 원칙에 따라, 물리 5노드 랩 구축 및 AC-06 종합 드릴 진행 후 실측 측정값으로 확정. |

---

## 4. 돌연변이(Mutation) 방어 및 사살 계획 (프로덕션 심볼 타겟)

본 매트릭스의 신뢰성을 검증하기 위해, **실제 프로덕션 프런트엔드 컴포넌트 및 백엔드 복원 모듈**에 의도적 결함을 주입하여 단위/통합 테스트에서 즉시 실패(KILLED)하는지 검증하는 돌연변이 사살 계획을 수립한다.

1. **MUT-01 (빈 작업공간 상태 aria-live polite 누락 돌연변이)**:
   - 대상: `apps/web/src/features/workspaces/WorkspaceList.tsx`
   - 주입: `workspaces-empty-state` 컨테이너에서 `role="status"` 및 `aria-live="polite"` 속성 제거.
   - 사살 단언: Vitest DOM 접근성 회귀 시험에서 속성 부재로 즉시 실패 (KILLED).
2. **MUT-02 (작업공간 생성 2단계 안내 배너 제거 돌연변이)**:
   - 대상: `apps/web/src/features/workspaces/WorkspaceCreateModal.tsx`
   - 주입: `data-testid="workspace-create-phase-notice"` 렌더링 블록 삭제.
   - 사살 단언: `workspace-create-modal.test.tsx`에서 안내 배너 존재 단언 실패 (KILLED).
3. **MUT-03 (복원 Replay 권한 재검사 우회 돌연변이)**:
   - 대상: `services/control-plane/src/inv/workspace_recovery.py`
   - 주입: Replay 분기에서 `authorize(conn)` 검증 로직 주석 처리.
   - 사살 단언: `tests/integration/test_workspace_recovery_http.py`의 `assert revoked_replay.status_code == 403` 단언 실패 (KILLED).
4. **MUT-04 (관측 전용 노드 PTY 세션 생성 허용 돌연변이)**:
   - 대상: `apps/web/src/features/desktop/TerminalSessionView.tsx`
   - 주입: `handleCreateSession`에서 `node.observationOnly || node.schedulable === false` 조건 분기 제거.
   - 사살 단언: `terminal-session-view.test.tsx`에서 관측 전용 노드 세션 생성 차단 단언 실패 (KILLED).
5. **MUT-05 (오프라인 PTY 명령 전송 거절 누락 돌연변이)**:
   - 대상: `apps/web/src/features/terminal/WebTerminal.tsx`
   - 주입: `connectionStatus !== 'connected'` 시 `terminal-disconnected-cmd-alert` 표출 로직 제거 및 무단 성공 리턴.
   - 사살 단언: `web-terminal.test.tsx`에서 오프라인 경고 배너 표출 단언 실패 (KILLED).

---

## 5. 실측 검증 하네스 설계 및 재현성 원칙 (검토 승인 후 착수용)

> [!NOTE]
> 본 절은 Claude 및 Codex 독립 검토 승인 후 실제 실측 단계에서 사용할 하네스 및 환경 명세이다 (본 docs-only 단계에서는 일체 실행하지 않음; "실측은 승인 후").

### 5.1 재현성 보장 원칙
1. **정본 제어 평면 Uvicorn 8080 및 Vite 3005 실소켓 결속**:
   - 하네스는 mock fetch를 전면 금지하며 실제 제어 평면 서버와 프런트엔드 간의 실제 HTTP/WebSocket 통신을 검증한다.
2. **원격 WS/PTY 실측 유예**:
   - 물리 5개 노드에 걸친 원격 PTY 콘솔 실측은 코디네이터 지침에 따라 `UNMEASURED ('5노드 랩 후')` 상태를 유지하며 5노드 랩 착수 시 순차 실측한다.
3. **동적 집계 및 영구 증거 보존**:
   - 실측 증거는 `docs/vault/30_Development/Evidence/s06_fe_matrix_acceptance.json`에 동적으로 기록된다.

---

## 6. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (Claude UI 경로 및 Codex 백엔드 계약 피드백 전면 반영 v1.1.1 docs-only 초안 완결)
- **독립 리뷰어**: Claude (Frontend/UI 셀렉터 대조), Codex (커널 오류 코드 및 복원/체크아웃 계약 대조)
- **다음 단계**:
  1. Claude 및 Codex 리뷰어의 v1.1.1 정합성 독립 검토.
  2. 승인(APPROVED) 확인 후 코디네이터 지시에 따라 실측 스크립트 작성 및 실측 착수.
