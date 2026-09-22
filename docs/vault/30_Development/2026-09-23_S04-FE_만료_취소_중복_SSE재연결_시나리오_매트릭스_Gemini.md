---
doc_id: "GEMINI-S04-FE-SCENARIO-MATRIX-20260923"
title: "S04-FE 만료·취소·중복·SSE 재연결 시나리오 매트릭스 (Gemini)"
version: "1.1.1"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-23T02:05:00+09:00"
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
> - `apps/web/src/features/approvals/ApprovalDetail.tsx`
> - `apps/web/src/features/runs/RunDetail.tsx`
> - `apps/web/src/shared/api/kernelMutations.ts` (decideApproval, cancelKernelRun)
> - `apps/web/src/shared/api/client.ts` (apiClient, ApiError, ProblemDetails)
> - `services/control-plane/src/inv/control.py`, `approvals.py`, `app.py`
> - `contracts/v1alpha1/core.schema.json` (RunCancelInput, ProblemDetails, ControlRunDetail)

---

## 1. 개요 및 수용 목표 (OUT-04 / AC-04)

본 문서는 SaintVision 거버넌스 및 실행 엔진의 **S04-FE (승인 화면·Run SSE 타임라인)** 트랙을 완결하기 위해, 코디네이터 지시 및 Claude(UI 경로/셀렉터)·Codex(백엔드 계약/불변식) 독립 검토 결과를 전면 반영하여 수립한 **만료(Expiration)·취소(Cancellation)·중복(Idempotency)·SSE 재연결(Reconnection)** 의 4대 핵심 축에 대한 실브라우저 및 단위 수용 시나리오 매트릭스 정본 계획서(v1.1.0)이다.

### 1.1 합격 기준 (AC-04)
- **승인 전 실행 0 (Zero Execution Before Approval)**:
  - 거버넌스 승인(`approved`) 없이 `awaiting_approval` 상태에서 `scheduled` 또는 `running`으로 전이되는 경로 0건.
- **중복 요청 부수 효과 0 (Zero Side-Effects on Duplicate Requests)**:
  - 더블클릭, 동일 Nonce 재전송, 기취소/기완료 작업에 대한 재취소/재승인 요청 시 멱등성 보장 및 단일 부수 효과만 발생.
- **전송 재개 및 이벤트 무결성 (Stream Resume & Integrity)**:
  - 네트워크 단절 및 백엔드 재시동 시 `{recoveryEpoch}:{runId}:{sequence}` 커서 기반 `Last-Event-ID` 재연결, 1,000건 링버퍼 중복 제거, 엄격한 시퀀스 번호 단조 증가($seq_{i} > seq_{i-1}$) 보장.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **EXP** | **만료 및 시효 방어**<br>(Expiration & Timeout) | `client.ts`<br>`ApprovalDetail.tsx`<br>`ApprovalCenter.tsx` | • 만료 Bearer 토큰 401 ProblemDetails (`AUTH-0050`)<br>• 만료 안건 승인 차단 (`isExpired`, `canApprove=false`, `disabled=true`)<br>• 폴링 지연 스냅샷 시각 정직 고지 (`Silent Aging` 방어)<br>• 서버 안건 시효 만료 시 403 `AUTH-0031` 거부 (410/AUTH-0040 아님) |
| **CNC** | **원자적 취소 및 자원 회수**<br>(Cancellation & Cleanup) | `RunDetail.tsx`<br>`kernelMutations.ts`<br>`control.py` | • 단말 상태(`succeeded`/`failed`) 취소 409 `GRAPH-0002`<br>• 버전 불일치 409 `GRAPH-0003`, 이미 취소된 안건 200 Replay (부수효과 0)<br>• ADR-001 사유 4종은 UI 로컬 수집, wire는 strict `RunCancelInput={expectedVersion}` 및 `Idempotency-Key` 전송 (추가 필드 시 422 `VAL-0003`)<br>• 200 응답 내 `resourceReleasePending` 관측 및 재조회 |
| **DUP** | **중복 클릭 및 2인 규칙 방어**<br>(Idempotency & Two-Person) | `ApprovalDetail.tsx`<br>`kernelMutations.ts`<br>`approvals.py` | • `ApprovalDetail.tsx`의 `isSubmitting` 가드로 원클릭 즉시 비활성화<br>• 동일 `Idempotency-Key`+동일 body는 200 Replay (단일 부수 효과)<br>• 동일 `Idempotency-Key`+다른 body는 409 `IDEM-0001`<br>• 무효/만료/소비 Nonce는 403 `AUTH-0034`, 기결정 행위자 재투표는 403 `AUTH-0033`<br>• 프로덕션 `isSelfApprovalBlocked` 2인 승인 규칙 (요청자 및 1차 승인자 차단) |
| **SSE** | **SSE 재연결 및 무결성**<br>(Reconnection & Dedup) | `sse-client.ts`<br>`RunDetail.tsx`<br>`control.py` (`control.events`) | • 1,000-entry RingBuffer at-least-once 중복 제거<br>• 이벤트 ID 규격: `{recoveryEpoch}:{runId}:{sequence}`<br>• `Last-Event-ID` 커서 기반 `sequence > last` 재연결 (오름차순 최대 200건)<br>• 유효하지 않거나 앞선 커서는 409 `STREAM-0001`<br>• 최상위 JSON `sequence` 단조 증가 및 타임라인 렌더링 |

---

## 3. 세부 시나리오 매트릭스 (13대 시나리오)

### 3.1 만료 (Expiration & Timeout, EXP-00 ~ EXP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **EXP-00** | **만료/무효 Access Token 보호 라우트 차단** | `client.ts`<br>전체 보호 라우트 | Access Token의 `exp` 시각이 경과한 만료 토큰 보유 | 임의의 보호 API (`GET /v1/projects`) 호출 | • 요청 헤더: `Authorization: Bearer <expired-jwt>`<br>• 응답 헤더: `WWW-Authenticate: Bearer`<br>• 응답 규격: HTTP 401, `application/problem+json`<br>• 본문: `ProblemDetails` (`code="AUTH-0050"`, `category="AUTH"`, `status=401`, safe `detail`, `retryable: false`, `traceId`) | • 백엔드가 401 ProblemDetails 반환.<br>• 프런트엔드 `clearAuthToken()` 호출 및 로그인 화면 전이.<br>• 로그인 에러 배너(`[data-testid="login-error-alert"]`)에 `[AUTH-0050]` 문구 표출. |
| **EXP-01** | **승인 안건 만료 상태 전이 및 액션 차단** | `ApprovalDetail.tsx`<br>`ApprovalCenter.tsx` | 승인 안건의 `expiresAt` 시각 경과 또는 서버 상태 `expired` (Run은 `failed` 전이) | 화면 렌더링 및 만료 안건 선택 | • 안건 식별: `code:has-text("${approval.id}")`<br>• 승인 버튼: `button:has-text("승인 확정")`<br>• 반려 버튼: `button:has-text("반려")`<br>• 내부 상태: `ApprovalDetail.tsx`의 `isExpired` 불린 | • `isExpired === true`로 계산되어 `canApprove === false` 불변식 만족.<br>• `button:has-text("승인 확정")`이 `disabled=true` 상태 유지.<br>• 클릭 시 어떠한 HTTP mutation (`/decision`)도 발생하지 않음 ($0$ requests).<br>• 서버 reconciler는 만료 안건을 `expired`로 확정하고 Run을 `failed`로 전이. |
| **EXP-02** | **폴링 지연 침묵 노화 방어 배너** | `ApprovalCenter.tsx` | 승인 목록 폴링 실패 (`approvalsState === 'error'` 또는 `approvalError != null`) | 5초 자동 갱신 실패 시점 | • 경보 배너: `div[role="alert"][data-testid="approval-stale-warning"]`<br>• 신선도: `div[role="status"][data-testid="approval-freshness-indicator"]`<br>• 새로고침: `button[data-testid="approval-refresh-btn"]` | • `⚠️ 승인 목록 동기화 실패` 문구 렌더링.<br>• 마지막 확인 시각(`lastFetchedAt.toLocaleTimeString('ko-KR')`)을 정직 명시하여 사용자 오도 방지.<br>• 새로고침 버튼 클릭 시 `onRefresh()` 정상 호출. |
| **EXP-03** | **승인 시효 만료 서버 403 AUTH-0031 거부 표출** | `ApprovalDetail.tsx`<br>`App.tsx` | 클라이언트 화면 로드 후 백엔드 원장에서 안건 만료 확정 | `handleConfirmApprove` 호출 시 백엔드 검증 | • 응답 규격: HTTP 403, `application/problem+json`<br>• 본문: `ProblemDetails` (`code="AUTH-0031"`, `detail="Approval is expired, stale, or unavailable"`)<br>• 에러 배너: `div[role="alert"]` (App 레벨 알림) | • 410 Gone 또는 AUTH-0040이 아닌 정본 **HTTP 403 `AUTH-0031`** 반환.<br>• `role="alert"` 경보가 마운트되고 만료 에러 문구 표시.<br>• 화면 새로고침 유도 및 승인 버튼 즉시 비활성화. |

---

### 3.2 취소 (Cancellation & Cleanup, CNC-01 ~ CNC-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **CNC-01** | **단말 상태 취소 차단 및 기취소 안건 멱등 200 Replay** | `RunDetail.tsx`<br>`kernelMutations.ts`<br>`control.py` | Case A: `run.state === 'succeeded' \| 'failed'`<br>Case B: `run.state === 'cancelled'` | Run 상세 화면 진입 및 취소 API 호출 | • 취소 버튼: `button:has-text("⛔ Run 취소 (S04)")`<br>• `canCancel` 불린 가드: `run.state !== 'succeeded' && ...`<br>• API 경로: `POST /v1/projects/{project}/runs/{run}/cancel` | • Case A: DOM 상에 취소 버튼 일체 미렌더링 (`canCancel === false`). 백엔드 직접 호출 시 HTTP 409 `GRAPH-0002` ("Terminal run cannot be modified") 반환.<br>• Case B: 이미 `cancelled` 상태에서 현재 버전 재취소 요청 시 부수 효과 없이 **HTTP 200 Replay** (`state: 'cancelled'`) 반환. |
| **CNC-02** | **ADR-001 표준 사유 모달 및 엄격한 RunCancelInput 전송** | `RunDetail.tsx`<br>`kernelMutations.ts` | `run.state === 'running'` 또는 `awaiting_approval` | `⛔ Run 취소 (S04)` 클릭 ➔ 모달 오픈 ➔ 사유 선택 후 `즉시 취소 실행` 클릭 | • 모달: `div[role="dialog"][aria-modal="true"]`<br>• 사유 셀렉트: `select` (4대 표준 사유: `user_requested`, `timeout`, `budget_exceeded`, `security_concern`)<br>• 확인 버튼: `button:has-text("즉시 취소 실행")`<br>• 요청 헤더: `Idempotency-Key: <traceId>` (X- prefix 없음)<br>• 요청 본문: strict `RunCancelInput = { expectedVersion: number }` | • 4대 표준 사유는 UI 로컬 감사용으로 선택.<br>• wire 전송 시 `expectedVersion`만 엄격히 전달되어 schema validation 통과 (사유 필드 포함 시 HTTP 422 `VAL-0003` 발생 검증).<br>• 권한 부재 시 403 `AUTH-0030`, 미존재 Run 시 404 `RES-0004` 반환. |
| **CNC-03** | **자원 반환 대기 배너 노출 및 관측 재조회** | `RunDetail.tsx` (샤드 영역) | 취소 성공 응답에 required boolean `resourceReleasePending: true` 포함 | 취소 완료 후 화면 재렌더링 및 `자원 회수 상태 동기화` 클릭 | • 대기 배너: `run.resourceReleasePending` 렌더 블록<br>• 헤더 문구: `⏳ 자원 반환 대기 중 (Resource Release Pending - ADR-040/042)`<br>• 동기화 버튼: `button:has-text("자원 회수 상태 동기화")` | • 분산 노드의 물리적 `NodeStopReceipt` fsync 및 안전한 Lease 반환 대기 상태를 정직하게 안내.<br>• 동기화 버튼 클릭 시 `refreshShardState()` 및 `onRefreshRun()`을 통한 관측 재조회 수행 (UI 클릭 자체가 fsync를 보장하는 것이 아닌 관측 동기화임 명시). |

---

### 3.3 중복 (Duplicate & Idempotency, DUP-01 ~ DUP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **DUP-01** | **승인 버튼 더블클릭 방어 및 200 Replay** | `ApprovalDetail.tsx`<br>`kernelMutations.ts` | 승인 검토 완료 (`canApprove === true`), 승인 버튼 활성화 | `button:has-text("승인 확정")` 초고속 더블클릭 (100ms 이내 2회 클릭) | • 승인 버튼: `button:has-text("승인 확정")` 또는 `button:has-text("2차 최종 승인 확정")`<br>• 로딩 상태: `isSubmitting === true` | • 첫 클릭 즉시 `isSubmitting === true` 전이로 버튼 `disabled` 및 로딩 스피너 표시.<br>• 두 번째 클릭 이벤트 무시되어 클라이언트 핸들러 1회만 트리거.<br>• 서버 측 방어: 동일 `Idempotency-Key`+동일 body 요청 시 저장된 응답 **HTTP 200 Replay**로 단일 부수 효과만 보장. |
| **DUP-02** | **Idempotency-Key 충돌 및 1회용 Nonce 재사용 차단 분리** | `kernelMutations.ts`<br>`approvals.py` | 1차 승인/취소 요청 완료 후 재요청 시도 | Case A: 동일 `Idempotency-Key` + 다른 본문 전송<br>Case B: 이미 소비된 1회용 Nonce로 새 `Idempotency-Key` 전송 | • 요청 헤더: `Idempotency-Key` (X- prefix 없음)<br>• 요청 본문: `ApprovalDecisionInput = { decision, nonce, actionDigest }` | • Case A: 멱등 키 충돌로 **HTTP 409 `IDEM-0001`** 반환.<br>• Case B: 소비/만료된 Nonce로 인해 **HTTP 403 `AUTH-0034`** (또는 기투표자 **`AUTH-0033`**) 반환.<br>• 서로 다른 두 방어가 분리 작동하며 클러스터 부수 효과 0건 ($0$ duplicate side-effect). |
| **DUP-03** | **2인 승인 규칙 자가승인 및 동일인 중복 승인 차단** | `ApprovalDetail.tsx`<br>`approvals.py` | Case A: `currentUserId === requestedBy`<br>Case B: `currentUserId === firstApprovedBy` (2차 승인 시) | 승인 안건 상세 확인 및 승인 시도 | • 컴포넌트: `ApprovalDetail.tsx`<br>• 불린 가드: `isSelfApprovalBlocked = (isWaitingSecondApproval && isFirstApprover) \|\| isRequester`<br>• 승인 버튼: `button:has-text("승인 확정")` 또는 `button:has-text("2차 최종 승인 확정")` | • Case A: 요청자는 `isSelfApprovalBlocked === true`로 `canApprove === false`, 승인 버튼 `disabled=true`.<br>• Case B: 1차 승인자는 2차 승인 버튼 비활성화.<br>• 백엔드 직접 호출 시에도 HTTP 403 `AUTH-0033` ("A distinct approver is required")로 엄격 거절. |

---

### 3.4 SSE 재연결 (SSE Reconnect & Integrity, SSE-01 ~ SSE-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 네트워크 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **SSE-01** | **1,000건 링버퍼 at-least-once 중복 제거** | `sse-client.ts`<br>(RingBuffer, SseStreamManager) | SSE 스트림 연결 활성 상태 | 네트워크 재전송으로 동일 서버 ID (`{recoveryEpoch}:{runId}:{sequence}`) 2회 연속 인입 | • 이벤트 블록: `id: {epoch}:{runId}:1
event: inv.event
data: {...}`<br>• 링버퍼 단언: `ringBuffer.has(id)` | • 첫 번째 이벤트는 핸들러로 정상 디스패치.<br>• 두 번째 동일 ID 이벤트는 `ringBuffer.has(id)`에 걸려 즉시 드롭(`return`).<br>• 이벤트 수신 리스너 호출 횟수는 정확히 1회. |
| **SSE-02** | **Last-Event-ID 커서 기반 스트림 재개 및 범위 검증** | `sse-client.ts`<br>`control.py` (`control.events`) | 마지막 수신 이벤트 ID가 `"{epoch}:{runId}:42"`인 상태에서 연결 단절 | `scheduleReconnect`에 의한 자동 재연결 | • 요청 헤더: `Last-Event-ID: "{epoch}:{runId}:42"`<br>• `Accept: text/event-stream`<br>• 이벤트 경로: `GET /v1/projects/{project}/runs/{run}/events` | • 재연결 요청 헤더에 `Last-Event-ID`가 정확히 포함됨.<br>• 서버는 `sequence > 42`인 이벤트를 오름차순으로 최대 200건 재전송하며 동일 cursor 재연결 시 중복 0건.<br>• 잘못된 Run/epoch 형식 또는 ahead cursor 인입 시 서버는 **HTTP 409 `STREAM-0001`** 반환. |
| **SSE-03** | **이벤트 sequence 단조 증가 및 타임라인 렌더링** | `RunDetail.tsx`<br>(Timeline Tab)<br>`sse-client.ts` | 다수의 상태 전이 이벤트(`inv.run.cancel_requested` 등) 수신 | SSE 스트림 파싱 및 타임라인 렌더링 | • 수신 이벤트 데이터: 최상위 JSON `sequence: number`, `eventType: string`<br>• 타임라인 스텝: `LIFECYCLE_STEPS` 8단계 (`draft`, `validated`, `planned`, `awaiting_approval`, `scheduled`, `running`, `verifying`, `succeeded`) | • 수신된 모든 이벤트의 `sequence` 번호가 엄격한 단조 증가($seq_i > seq_{i-1}$)를 만족함.<br>• 현재 `run.state`에 따라 타임라인의 해당 단계 인덱스가 정확히 활성화/완료(`✓`) 표출. |

---

## 4. 돌연변이(Mutation) 방어 및 사살 계획 (프로덕션 심볼 타겟)

본 매트릭스의 유효성을 증명하기 위해, 시험 코드가 아닌 **실제 프로덕션 컴포넌트 및 모듈**에 의도적 결함을 주입하여 단위/통합 테스트에서 즉시 실패(KILLED)하는지 검증하는 돌연변이 사살 계획을 수립한다.

1. **MUT-01 (만료 검증 누락 돌연변이)**:
   - 대상: `apps/web/src/features/approvals/ApprovalDetail.tsx`
   - 주입: `isExpired` 계산을 영구 `false`로 우회 (`const isExpired = false;`).
   - 사살 단언: 만료된 안건에 대해 `expect(canApprove).toBe(false)` 단언 또는 `button:has-text("승인 확정")`의 `disabled` 상태 검사 시 실패 (KILLED).
2. **MUT-02 (자가승인 허용 돌연변이)**:
   - 대상: `apps/web/src/features/approvals/ApprovalDetail.tsx`
   - 주입: 프로덕션 심볼 `isSelfApprovalBlocked`를 영구 `false`로 우회 (`const isSelfApprovalBlocked = false;`).
   - 사살 단언: 요청자 ID(`requestedBy === currentUserId`)인 상태에서 `expect(canApprove).toBe(false)` 실패 (KILLED).
3. **MUT-03 (더블클릭 중복 허용 돌연변이)**:
   - 대상: `apps/web/src/features/approvals/ApprovalDetail.tsx`
   - 주입: `handleConfirmApprove`에서 `isSubmitting` 가드 제거 및 `setIsSubmitting(true)` 누락.
   - 사살 단언: 100ms 이내 초고속 2회 클릭 시 `onApprove` 호출 횟수가 2가 되어 `expect(onApproveMock).toHaveBeenCalledTimes(1)` 실패 (KILLED).
4. **MUT-04 (SSE 중복 제거 드롭 누락 돌연변이)**:
   - 대상: `apps/web/src/shared/realtime/sse-client.ts`
   - 주입: `parseBlock` 함수 내 `if (this.ringBuffer.has(id)) return;` 조기 리턴 로직 제거.
   - 사살 단언: 동일 ID 2회 연속 인입 시 리스너 호출 횟수가 2가 되어 `expect(eventHandler).toHaveBeenCalledTimes(1)` 실패 (KILLED).

---

## 5. 실측 검증 하네스 설계 및 재현성 원칙 (검토 승인 후 착수용)

> [!NOTE]
> 본 절은 Claude 및 Codex 독립 검토 승인 후 실제 실측 단계에서 사용할 하네스 및 환경 명세이다 (본 단계에서는 실행하지 않음).

### 5.1 재현성 보장 원칙 (#77 교훈 완벽 반영)
1. **유연한 매개변수 주입**:
   - `tools/run_s04_fe_matrix.py`는 `--chrome-path`, `--frontend-port`, `--backend-port`, `--idp-port`, `--dev-dir`, `--idp-script`, `--server-env`, `--dry-run` 옵션을 지원하여 특정 하드코딩 경로 및 포트에 의존하지 않는다.
   - Vite 프록시는 `VITE_API_PROXY_TARGET=http://127.0.0.1:{backend_port}`를 동적 전달한다.
   - 단, `frontend-port ≠ 3005` 사용 시 로컬 `dev_idp.py`의 `ALLOWED_REDIRECTS` 및 `api.json`의 `allowedOrigins`에 해당 origin이 사전 등록되어 있어야 하며, 미등록으로 인한 IdP `/authorize` 400 발생 시 `UNMEASURED` (사유: redirect allowlist mismatch)로 안전하게 종료한다.
2. **우아한 미측정(UNMEASURED) 게이트 종료 (Exit Code 3)**:
   - 클린 CI 환경이나 로컬 워크트리에 `.work/dev` 파일, Dev DB, Dev IdP가 부재한 경우, 스크립트 크래시(예: `FileNotFoundError`)가 아닌 사유를 명시하고 `STATUS: UNMEASURED (exit code 3)`으로 게이트 종료한다 (Exit Code 0은 전 시나리오 실측 통과 전용으로 엄격 제한).
3. **격리된 자원 관리**:
   - 실행 시 백엔드 Uvicorn(8080), Dev IdP(8090/인자), Vite(3005)의 기동 및 종료를 `finally` 블록에서 완전하게 정리한다.

### 5.2 영구 증거 산출물 명세
- **증거 JSON**: `docs/vault/30_Development/Evidence/s04_fe_matrix_acceptance.json` (실측값 100% 동적 도출, 상수 금지)
- **실측 스크린샷 6종**:
  1. `s04_01_expired_blocked.png` (만료 안건 승인 버튼 비활성화)
  2. `s04_02_cancel_modal.png` (ADR-001 사유 선택 취소 모달)
  3. `s04_03_cancel_reclaim.png` (자원 반환 대기 배너)
  4. `s04_04_double_click_blocked.png` (더블클릭 방어 및 스피너)
  5. `s04_05_two_person_rule.png` (자가승인 차단 고지)
  6. `s04_06_sse_reconnect.png` (SSE Last-Event-ID 재연결)

---

## 6. 검토 인계 및 다음 단계

- **문서 상태**: `status: "review"` (Claude UI 경로 및 Codex 백엔드 계약 피드백 전면 반영 v1.1.0 완결)
- **독립 리뷰어**: Claude (Frontend/UI), Codex (Backend Contract)
- **다음 단계**:
  1. Claude 및 Codex 리뷰어의 v1.1.0 정합성 재검토.
  2. 승인(APPROVED) 확인 후 코디네이터 지시에 따라 실측 스크립트 작성 및 Chrome/Vitest 수용 실측 착수.
