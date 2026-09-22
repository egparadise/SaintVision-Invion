---
doc_id: "GEMINI-S04-FE-SCENARIO-MATRIX-20260923"
title: "S04-FE 만료·취소·중복·SSE 재연결 시나리오 매트릭스 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-23T00:25:00+09:00"
source_of_truth: "Git"
tags: ["s04-fe", "acceptance-matrix", "approval", "cancellation", "idempotency", "sse-reconnect", "gemini"]
---

# S04-FE 만료·취소·중복·SSE 재연결 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[S04 단일 노드 여정]] (OUT-04 / AC-04)
> - [[Frontend 최종 개발 계획]]
> - [[설계 충돌 정정 및 ADR]] (ADR-001, ADR-027, ADR-040, ADR-042)
> - `apps/web/src/shared/realtime/sse-client.ts` (SseStreamManager, RingBuffer)
> - `apps/web/src/features/approvals/ApprovalCenter.tsx`
> - `apps/web/src/features/approvals/ApprovalReviewPanel.tsx`
> - `apps/web/src/features/runs/RunDetail.tsx`
> - `apps/web/tests/approval-timeline.test.ts`

---

## 1. 개요 및 수용 목표 (OUT-04 / AC-04)

본 문서는 SaintVision 거버넌스 및 실행 엔진의 **S04-FE (승인 화면·Run SSE 타임라인)** 트랙을 완결하기 위해, 코디네이터 지시에 따라 **만료(Expiration)·취소(Cancellation)·중복(Idempotency)·SSE 재연결(Reconnection)** 의 4대 핵심 축에 대한 실브라우저 및 단위 수용 시나리오 매트릭스를 docs-only 초안으로 정의한 정본 계획서이다.

### 1.1 합격 기준 (AC-04)
- **승인 전 실행 0 (Zero Execution Before Approval)**:
  - 거버넌스 승인(`approved`) 없이 `awaiting_approval` 상태에서 `scheduled` 또는 `running`으로 전이되는 경로 0건.
- **중복 요청 부수 효과 0 (Zero Side-Effects on Duplicate Requests)**:
  - 더블클릭, 동일 Nonce 재전송, 기취소/기완료 작업에 대한 재취소/재승인 요청 시 멱등성 보장 및 단일 부수 효과만 발생.
- **전송 재개 및 이벤트 무결성 (Stream Resume & Integrity)**:
  - 네트워크 단절 및 백엔드 재시동 시 `Last-Event-ID` 커서 기반 재연결, 1,000건 링버퍼 중복 제거, 엄격한 시퀀스 번호 단조 증가($seq_{i} > seq_{i-1}$) 보장.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 규격 |
|:---:|---|---|---|
| **EXP** | **만료 및 시효 방어**<br>(Expiration & Timeout) | `ApprovalCenter.tsx`<br>`ApprovalReviewPanel.tsx`<br>`RunDetail.tsx` | • TTL 만료 안건 승인 차단 (`disabled=true`)<br>• 폴링 지연 스냅샷 시각 정직 고지 (`Silent Aging` 방어)<br>• 서버 410 Gone / ProblemDetails 대응 |
| **CNC** | **원자적 취소 및 자원 회수**<br>(Cancellation & Cleanup) | `RunDetail.tsx`<br>`kernelMutations.ts` | • 단말 상태(`succeeded`/`failed`/`cancelled`) 취소 차단<br>• ADR-001 표준 사유 4종 필수 선택 모달<br>• ADR-040/042 분산 자원 회수 대기 배너 노출 |
| **DUP** | **중복 클릭 및 2인 규칙 방어**<br>(Idempotency & Two-Person) | `ApprovalCenter.tsx`<br>`ApprovalReviewPanel.tsx`<br>`client.ts` | • 원클릭 즉시 `disabled` + 스피너 전이<br>• 1회용 Nonce 및 백엔드 409 Conflict 방어<br>• 2인 승인 규칙 (요청자 자가승인 및 1차 승인자 자가2차승인 차단) |
| **SSE** | **SSE 재연결 및 무결성**<br>(Reconnection & Dedup) | `sse-client.ts`<br>`RunDetail.tsx` (Timeline/Logs) | • 1,000-entry RingBuffer at-least-once 중복 제거<br>• 지터 포함 지수 백오프 자동 재연결<br>• `Last-Event-ID` 복원 커서 및 시퀀스 단조 증가 |

---

## 3. 세부 시나리오 매트릭스 (12대 시나리오)

### 3.1 만료 (Expiration & Timeout, EXP-01 ~ EXP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **EXP-01** | **승인 안건 만료 후 액션 차단** | `ApprovalCenter.tsx`<br>`ApprovalDetail.tsx` | 승인 안건의 `expiresAt` 시각이 현재 시각 경과 (`Date.now() > expiresAt`) | 화면 렌더링 및 만료 안건 클릭 | • 안건 카드: `div[data-testid="approval-item-${id}"]`<br>• 상태 배지: `span[data-testid="approval-status-badge"]`<br>• 승인 버튼: `button[data-testid="approve-btn"]` | • 상태 배지가 `만료` 또는 `rejected`로 표출됨.<br>• 승인 버튼이 존재하지 않거나 `disabled=true` 상태 유지.<br>• 클릭 시 어떠한 HTTP mutation도 발생하지 않음 ($0$ requests). |
| **EXP-02** | **폴링 지연 침묵 노화 방어 배너** | `ApprovalCenter.tsx` | 승인 목록 폴링 실패 (`approvalsState === 'error'` 또는 통신 타임아웃) | 5초 자동 갱신 실패 시점 | • 경보 배너: `div[role="alert"][data-testid="approval-stale-warning"]`<br>• 신선도: `div[data-testid="approval-freshness-indicator"]`<br>• 새로고침: `button[data-testid="approval-refresh-btn"]` | • `⚠️ 승인 목록 동기화 실패` 문구 렌더링.<br>• 마지막 확인 시각(`lastFetchedAt.toLocaleTimeString`)을 정직 명시하여 사용자 오도 방지.<br>• 새로고침 버튼 클릭 시 재조회 시도. |
| **EXP-03** | **서버 410 만료 에러 표출** | `ApprovalReviewPanel.tsx` | 승인 검토 패널 로드 상태에서 승인 클릭 직전 서버 측 만료 확정 | `onApprove` 호출 시 백엔드가 HTTP 410 Gone 반환 | • 에러 배너: `div[role="alert"][data-testid="approval-error-banner"]`<br>• 상태 문구: `[AUTH-0040]` 또는 만료 메시지 | • `role="alert"` 경보가 마운트되고 승인 버튼 즉시 비활성화.<br>• 화면이 닫히지 않고 만료 사유를 사용자에게 명확히 전달. |

---

### 3.2 취소 (Cancellation & Cleanup, CNC-01 ~ CNC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **CNC-01** | **단말 상태 취소 버튼 완전 은닉** | `RunDetail.tsx` | `run.state`가 `succeeded`, `failed`, `cancelled` 중 하나 | Run 상세 화면 진입 | • 취소 버튼: `button:has-text("⛔ Run 취소 (S04)")`<br>• `canCancel` 불린 가드: `run.state !== 'succeeded' && ...` | • DOM 상에 취소 버튼이 일체 렌더링되지 않음 (`expect(cancelBtn).toBeNull()`).<br>• 콘솔/API 호출로도 단말 상태 취소 불가 불변식 유지. |
| **CNC-02** | **ADR-001 표준 사유 취소 모달** | `RunDetail.tsx` | `run.state === 'running'` 또는 `awaiting_approval` | `⛔ Run 취소 (S04)` 클릭 ➔ 모달 오픈 | • 모달: `div[role="dialog"][aria-modal="true"]`<br>• 사유 셀렉트: `select` (4대 표준 사유 옵션)<br>• 확인 버튼: `button:has-text("즉시 취소 실행")` | • 4대 표준 사유(`user_requested`, `timeout`, `budget_exceeded`, `security_concern`)만 선택 가능.<br>• 제출 시 `isCancelling === true`로 버튼 비활성화 및 스피너 표시.<br>• 백엔드로 `reason` 인자가 정확히 전달됨. |
| **CNC-03** | **자원 반환 대기 배너 및 샤드 동기화** | `RunDetail.tsx` | 취소 완료 직후 백엔드가 `resourceReleasePending: true` 반환 | 취소 성공 후 화면 재렌더링 | • 대기 배너: `run.resourceReleasePending && div`<br>• 헤더: `⏳ 자원 반환 대기 중 (Resource Release Pending - ADR-040/042)`<br>• 동기화 버튼: `button:has-text("자원 회수 상태 동기화")` | • 분산 노드의 물리적 영수증(`NodeStopReceipt`) fsync 대기 상태 정직 안내.<br>• 동기화 버튼 클릭 시 `refreshShardState()` 정상 호출. |

---

### 3.3 중복 (Duplicate & Idempotency, DUP-01 ~ DUP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **DUP-01** | **승인 버튼 더블클릭 방어** | `ApprovalReviewPanel.tsx`<br>`ApprovalCenter.tsx` | 검토 내용 로드 완료 (`actionDigest` 일치, 승인 버튼 활성화) | 승인 확정 버튼 초고속 더블클릭 (100ms 이내 2회 클릭) | • 승인 버튼: `button[data-testid="confirm-approve-btn"]`<br>• 로딩 상태: `isSubmitting === true` | • 첫 클릭 즉시 `disabled=true` 및 `⏳ 승인 처리 중...` 텍스트 전이.<br>• 두 번째 클릭 이벤트 무시.<br>• 백엔드 네트워크 호출은 정확히 1회만 발생. |
| **DUP-02** | **동일 Nonce 재사용 차단** | `approvalReview.ts`<br>`ApprovalCenter.tsx` | 1회용 Nonce(`nonce_...`)가 이미 소비(Consumed)된 상태 | 변조된 스크립트로 동일 Nonce 재전송 | • 요청 헤더: `X-Idempotency-Key` 또는 페이로드 `nonce`<br>• 백엔드 응답: HTTP 409 Conflict | • 클라이언트 Nonce 캐시 또는 서버 응답에 의해 `중복 요청 거절` 에러 표출.<br>• 동일 승인이 중복 체결되지 않음 ($0$ duplicate side-effect). |
| **DUP-03** | **2인 승인 규칙 자가승인 차단** | `ApprovalCenter.tsx`<br>`approval-timeline.test.ts` | • Case A: `currentUserId === requestedBy`<br>• Case B: `currentUserId === firstApprovedBy` (2차 승인 시) | 승인 안건 상세 확인 및 승인 시도 | • 검토자 표시: `strong:has-text("${currentUserId}")`<br>• 승인 버튼 상태: `button[data-testid="approve-btn"]` | • Case A: 요청자는 승인 버튼 완전 비활성화 (`disabled=true`, 자가승인 금지 고지).<br>• Case B: 1차 승인자는 2차 승인 수행 불가 (별도 독립 검토자 계정 요구). |

---

### 3.4 SSE 재연결 (SSE Reconnect & Integrity, SSE-01 ~ SSE-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **SSE-01** | **1,000건 링버퍼 at-least-once 중복 제거** | `sse-client.ts`<br>(RingBuffer) | `SseStreamManager` 연결 활성 상태 | 네트워크 재전송으로 동일 `id: "evt_001"` 2회 연속 인입 | • `SseStreamManager.parseBlock()`<br>• `ringBuffer.has(id)` 단언 | • 첫 번째 이벤트는 핸들러로 정상 디스패치.<br>• 두 번째 동일 ID 이벤트는 링버퍼에 의해 즉시 드롭(`return`).<br>• UI 타임라인/로그에 중복 항목 렌더링 0건. |
| **SSE-02** | **Last-Event-ID 커서 기반 스트림 재개** | `sse-client.ts`<br>(SseStreamManager) | 마지막 수신 이벤트 ID가 `"evt_1042"`인 상태에서 연결 강제 종료 | `scheduleReconnect`에 의한 자동 재연결 | • 요청 헤더: `Last-Event-ID: "evt_1042"`<br>• `Accept: text/event-stream` | • 재연결 HTTP 요청 헤더에 `Last-Event-ID: evt_1042`가 정확히 포함됨.<br>• 백엔드가 `evt_1043`부터 스트림 재개하여 이벤트 유실 0건. |
| **SSE-03** | **타임라인 이벤트 시퀀스 단조 증가 보장** | `RunDetail.tsx`<br>(Timeline Tab) | 다수의 상태 전이 이벤트(`RUN_VALIDATED`, `RUN_PLANNED` 등) 수신 | SSE 스트림 파싱 및 타임라인 렌더링 | • 타임라인 스텝: `div[data-testid="timeline-step-${step}"]`<br>• 이벤트 객체: `event.data.seq`, `event.data.timestamp` | • 수신된 모든 이벤트의 시퀀스 번호가 엄격한 단조 증가($seq_i > seq_{i-1}$)를 만족함.<br>• 역전된 이벤트 인입 시 UI 뷰 정렬 또는 방어 로직 작동. |

---

## 4. 돌연변이(Mutation) 방어 및 사살 계획

본 매트릭스의 유효성을 증명하기 위해, 실제 구현 및 단위 테스트에 의도적 결함을 주입하여 즉시 실패(KILLED)하는지 검증하는 돌연변이 사살 계획을 확립한다.

1. **MUT-01 (만료 검증 누락 돌연변이)**:
   - 주입: `ApprovalCenter.tsx`에서 `isExpired` 검사를 영구 `false`로 우회.
   - 사살 단언: `tests/approval-timeline.test.ts`에서 만료된 안건에 대해 승인 가능 여부 단언 시 즉시 `AssertionError: expected false to be true` 발생 (KILLED).
2. **MUT-02 (자가승인 허용 돌연변이)**:
   - 주입: `canUserApprove` 함수에서 `userId === requesterId` 가드 제거.
   - 사살 단언: `expect(canUserApprove('usr_requester_alice', ...)).toBe(false)` 실패 (KILLED).
3. **MUT-03 (더블클릭 중복 허용 돌연변이)**:
   - 주입: `ApprovalReviewPanel.tsx`에서 `isSubmitting` 로딩 가드 제거.
   - 사살 단언: 초고속 2회 클릭 시 `onApprove` 호출 횟수가 2가 되어 `expect(approveStub).toHaveBeenCalledTimes(1)` 실패 (KILLED).
4. **MUT-04 (SSE 중복 제거 드롭 누락 돌연변이)**:
   - 주입: `RingBuffer.has(id)` 체크 후 조기 리턴 로직 제거.
   - 사살 단언: 동일 ID 2회 인입 시 리스너 호출 횟수가 2가 되어 `expect(handler).toHaveBeenCalledTimes(1)` 실패 (KILLED).

---

## 5. 실측 검증 도구 및 환경 설계 (검토 승인 후 착수용)

> [!NOTE]
> 본 절은 Claude 독립 검토 승인 후 실제 실측 단계에서 사용할 하네스 및 환경 명세이다 (본 단계에서는 실행하지 않음).

- **실행 환경**:
  - Google Chrome 153 Headless (공식 빌드, Blink 엔진)
  - Uvicorn 백엔드 (포트 8080) + Dev IdP (포트 8090) + Vite (포트 3005)
- **전용 실측 스크립트**: `tools/run_s04_real_api_acceptance.py` (신규 제작 예정)
- **영구 증거 산출물 경로**:
  - `docs/vault/30_Development/Evidence/s04_fe_matrix_acceptance.json`
  - 스크린샷 6종: `s04_01_expired_blocked.png`, `s04_02_cancel_modal.png`, `s04_03_cancel_reclaim.png`, `s04_04_double_click_blocked.png`, `s04_05_two_person_rule.png`, `s04_06_sse_reconnect.png`

---

## 6. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (docs-only 초안 작성 완료)
- **독립 리뷰어**: Claude
- **다음 단계**:
  1. Claude 리뷰어의 매트릭스 타당성, 셀렉터 정합성, 불변식 엄밀성 독립 검토.
  2. 수정 요구 반영 또는 승인(APPROVED) 확인.
  3. 코디네이터 승인에 따른 실제 Chrome 실브라우저 및 Vitest 수용 실측 착수.
