---
doc_id: "HIST-20261001-C169-S08FE-001"
title: "Card 169 (S08-FE) 관리자 보안 콘솔 비상 정지(Kill Switch) 백엔드 제어 평면 실배선 및 202 Accepted 멱등 연동 기록"
version: "1.0.1"
status: "approved"
author: "Gemini"
created: "2026-10-01T12:57:03+09:00"
updated: "2026-10-01T13:17:15+09:00"
source_of_truth: "Git"
---

# Card 169 (S08-FE) 관리자 보안 콘솔 비상 정지(Kill Switch) 백엔드 실배선 및 202 Accepted 멱등 연동

## 1. 카드 선택 및 착수 배경 (Selection Rationale)
- **선행 및 현황 분석**:
  1. 병합 열차(`coord/train5-ci-1135`, `7851412d`)에서 카드 113 서버 멱등 계약(`fa04b9d8`)이 이미 착지 완료됨.
  2. 모델 레지스트리 Release 쓰기 UI의 fail-closed 해제는 이미 카드 118(PR #240, `0930de95`)에서 완비되어 8개 테스트 전원 통과 상태임을 확인.
  3. `task-registry.json` 및 `#264 v1.7` 진척표 내 Gemini Frontend 75% 카드(S02~S08) 중:
     - `S02-FE`: PR #259 (Card 162) 검토 진행 중 (사내 IdP 물리 live smoke는 외부 차단).
     - `S03-FE` ~ `S07-FE`: 5노드 물리 클러스터 실기 검증(`G-19`, `G-24`) 외부 전제 대기.
     - `S08-FE`: **외부 차단 전제(`—`) 없음**.
  4. S08 백엔드(`S08-BE`)에서 제어 평면 비상 정지 엔드포인트(`GET /v1/operations/kill-switch`, `POST /v1/operations/kill-switch` [202 Accepted], `POST /v1/operations/kill-switch/clear`, `require_execution()`) 및 계약 검증이 완료되었으나, 프론트엔드(`AdminSecurityConsole.tsx`)의 비상 정지 토글 버튼은 브라우저 메모리 로컬 보안 엔진 모의 시뮬레이션(`secManager.toggleEmergencyKillSwitch`)에 머물러 있었음.
- **착수 결정**: S08-FE 관리자 비상 정지(Kill Switch)를 백엔드 제어 평면 실엔드포인트와 실배선 연결하여, 모의 시뮬레이션에서 실제 제어 평면 멱등 쓰기/해제 및 RFC 9457 ProblemDetails 오류 처리로 승격하는 **Card 169: S08-FE Emergency Kill Switch Real Backend Wiring**에 착수.

## 2. 변경 내역 (Implementation Details)
1. **제어 평면 실배선 및 202 Accepted 처리 (`AdminSecurityConsole.tsx`)**:
   - `handleConfirmKillSwitch`:
     - 대상 엔드포인트: 활성화 시 `POST /v1/operations/kill-switch`, 해제 시 `POST /v1/operations/kill-switch/clear`.
     - 전송 규격: `ContainmentInput` (`expectedVersion`, `reasonCode`, `approvalId`) 및 HTTP 헤더 `Idempotency-Key` (단일 시도 고유 멱등키).
     - 응답 처리: 백엔드 202 Accepted 수신 시 `result.control.killSwitchActive` 및 `result.control.version`을 반영하여 `backendKillSwitch` 상태 갱신.
     - 로컬 보안 제어 엔진(`secManager`)과 제어 평면 상태 동기화 및 멱등키 자동 로테이션.
2. **접근성 및 포커스 트랩 불변식 보존 (`kill-switch-modal`)**:
   - `defect-recovery-admin-recovery-editor.test.tsx`의 2-요소 키보드 포커스 트랩(`cancelBtn` $\leftrightarrow$ `confirmBtn` 순환)을 훼손하지 않도록, `reasonCode` 선택 드롭다운과 `approvalId` 입력창을 상단 헤더 제어바(Drain 컨트롤과 대칭)에 배치.
   - 모달 내부에는 설정된 파라미터 요약(`kill-switch-params-summary`)과 실시간 RFC 9457 오류 배너(`kill-switch-error-banner`)를 배치하고 대화형 요소는 취소/확정 버튼 2개만 유지하여 포커스 트랩 통과.
3. **Fail-Closed 보안 및 입력 검증**:
   - `actor`(관리자 세션) 부재 시 토글 및 확정 버튼 원천 비활성화(`disabled`, `aria-disabled`), 위조 세션 합성 차단.
   - `approvalId`가 유효한 UUIDv4가 아닐 경우 네트워크 POST를 0회로 원천 차단하고 `[data-testid="kill-switch-error-banner"]`에 안내 표시.
   - 백엔드 403(`AUTH-0062`), 409(`GRAPH-0003`), 422 ProblemDetails 에러 수신 시 모달을 닫지 않고 에러 배너에 RFC 9457 코드 및 상세 내역 정직하게 표시.
4. **전용 검증 테스트 스위트 작성 (`admin-security-kill-switch-wiring.test.tsx`)**:
   - 긴급 발동 확정 시 `POST /v1/operations/kill-switch` 202 Accepted, `Idempotency-Key`, `expectedVersion`, `reasonCode`, `approvalId` 전송 및 `ACTIVE` 갱신 검증.
   - 해제 확정 시 `POST /v1/operations/kill-switch/clear` 202 Accepted 및 `INACTIVE` 복귀 검증.
   - 409 Conflict ProblemDetails 처리 및 모달 유지 검증.
   - 403 Forbidden ProblemDetails 처리 검증.
   - 무효 UUID 입력 시 네트워크 POST 0회 차단 검증.
   - `currentUser=null` 시 관리자 부재 배너 및 버튼 비활성화 검증.

## 3. PR #267 독립 검토(13:02) 지적사항 전수 조치 (Remediation Details)
1. **(1)[High] GET ContainmentView 계약 완전 검증 및 fail-closed 쓰기 차단**:
   - `isValidContainmentView(v: unknown): v is ContainmentView`: `nodeId` (string | null), 정수 `version >= 0`, boolean `killSwitchActive`, `nodeStatus` (string | null), 음수 아닌 정수 `activeLeases`, `pendingDeliveries`, `unsettledRuns`, boolean `settled`를 전수 검증.
   - 부분 응답(예: `{ killSwitchActive: false }`), 필드 누락, 로딩 중, 오류 응답 수신 시 `backendKillSwitch.status = 'error'`, `isKillSwitchReady = false`로 처리하여 쓰기 버튼(`kill-switch-confirm-btn`)을 원천 비활성화(`canConfirmKillSwitch = false`, fail-closed).
2. **(2)[High] POST ContainmentResult 정본 shape 검증, 상태 합성 제거 및 재조회**:
   - `isValidContainmentResult(r: unknown, expectedOperation, expectedApprovalId)`: `requestId` (비어있지 않은 문자열), `operation === expectedOperation`, `approvalId` 대소문자 무관 일치, `control`의 `isValidContainmentView` 만족 및 `control.killSwitchActive === (expectedOperation === 'kill')`를 엄격 검증.
   - 응답 위장 또는 `control` 누락 시 임의 상태 합성(`version ?? currentVersion + 1` 등)을 배제하고 `[CONTRACT-MISMATCH]` 오류 표시, 로컬 상태 미변경(불변), 즉시 제어 평면 상태 재조회(`fetchBackendKillSwitch()`) 실행.
3. **(3)[Medium] 승인 UUID 기본값 빈 문자열 초기화 및 사전 가드**:
   - 모의 승인 UUID(`00000000-0000-4000-8000-000000000001`) 기본값을 제거하고 `''`로 초기화.
   - 유효한 UUIDv4 입력 전에는 모달 내 `kill-switch-approval-required-notice` (role="alert")를 표출하고 확정 버튼을 비활성화(`canConfirmKillSwitch = false`), 클릭 시도 시에도 네트워크 호출을 0회로 원천 차단.
4. **(4)[Medium] Clear HTTP 200 OK 정본 규격 반영 및 상태 관측**:
   - 서버 `app.py:412` (`@api.post("/v1/operations/kill-switch/clear")`) 정본 기본 status인 `200 OK`를 시험 및 mock에 반영하고, mock이 실제 HTTP status를 관측/단언하도록 정합. (활성화는 202 Accepted, 해제는 200 OK).
   - 각 반례(부분 응답, 위장 응답, 모순 상태, 승인 ID 빈 값)에 대한 음성 시험 완비 (총 9개 시험).

## 4. 로컬 실측 검증 (Evidence)
- `npm test -- admin-security-kill-switch-wiring`: 9 passed (exit 0, 반례 부정 시험 전수 통과)
- `npm test -- defect-recovery-admin`: 26 passed (exit 0, 포커스 트랩 및 Kill Switch 회귀 100% 통과)
- `npm test -- write-actions`: 8 passed (exit 0)
- `npx tsc -b`: 타입 오류 0건 (exit 0)
- `npm run build`: Vite 프로덕션 번들 정상 생성 (exit 0, 7.12s)
- `pytest tests/test_route_coverage.py`: 40 passed 100% (exit 0)
- `python -X utf8 tools/check_frontend_integrity.py`: 92개 파일 스캔, 9대 규칙 위반 0건 (exit 0)
- `python tools/check_docs.py`: PASS (24 hashes, 1055 docs, 48 tasks, 12 outcomes)

## 5. 이어서 할 첫 행동 및 담당
- **담당**: Gemini (Frontend / UI 소유).
- **Reviewer**: Claude (UI·테스트 축), Codex 계약·보안 축.
- **다음 행동**: Git commit, origin push, PR #267 통합 조치표 코멘트 등록 및 재검토 요청.

