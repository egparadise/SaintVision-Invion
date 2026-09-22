---
doc_id: "DESIGN-GEMINI-20260922-MODEL-RETRY-UI"
title: "RunDetail Model Retry(결정 #6 6a) UI 설계 메모"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-22T19:40:00+09:00"
source_of_truth: "Git"
---

# RunDetail Model Retry (결정 #6 6a) UI 설계 메모

- 작성 일시: 2026-09-22T19:40:00+09:00 (KST)
- 작성자: Gemini (Frontend & Design Owner)
- 참조 계약: Codex 커널 착지 `563c54ce` (`ModelRetryPrepareInput`, `ModelRetryPrepareResult`)
- 참조 문서: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[Codex 실제 실행 결과 조회 계약]]

---

## 1. 개요 및 결정 #6 6a 계약 정합

결정 #6 6a에 따라 Codex가 제어 평면에 착지한 정본 계약(`563c54ce`)은 **일반 Run의 임의 재시도가 아닌, 오직 모델 학습/추론 파이프라인의 실패에 대해 정식 거버넌스 승인 절차를 거치는 `Model Retry` 계약**을 노출한다.

- **엔드포인트**: `POST /v1/projects/{project}/runs/{parent}/model-retries`
- **상태 코드**: `201 Created`
- **입력 스키마**: `ModelRetryPrepareInput` (`cpuMillis`, `memoryBytes`, `gpuCount`, `minVramBytes`, `requiredBytes`, `maxHostLoad`, `runtime`, `policyVersion`, `ttlSeconds`)
- **출력 스키마**: `ModelRetryPrepareResult` (`rootRunId`, `parentRunId`, `generation`, `run: ControlRunView`, `placement: ModelRetryPlacementResult`, `requiresFrozenInputAndApproval: true`)

본 문서는 프런트엔드 `RunDetail` 컴포넌트에서 실패한 모델 파이프라인의 재시도 준비 액션을 안전하고 정직하게 제공하기 위한 상세 UI/UX 명세를 확립한다.

---

## 2. 노출 조건 (Strict Terminal failed Guard)

1. **상태 불변식**:
   - `run.state === 'failed'` 종단 상태일 때만 헤더 상단 액션 버튼 그룹에 `🔄 Model Retry 준비` 버튼을 노출한다.
   - `succeeded`, `running`, `cancelled`, `timeout`, `draft`, `validated`, `planned`, `awaiting_approval`, `scheduled`, `verifying`, `recovering` 등 **`failed` 이외의 모든 상태에서는 버튼을 완전히 렌더링하지 않는다 (DOM 미노출)**.
2. **프로젝트 식별자 바인딩 가드**:
   - `run.projectId`가 존재하지 않거나 빈 문자열인 경우, 위조 식별자 합성 방지 규칙에 따라 버튼을 비활성화(`disabled`)하고 `"프로젝트 미지정 실행 (재시도 불가)"` 툴팁을 표출한다.
3. **기존 액션 버튼과의 배치 질서**:
   - [헤더 우측 액션 영역]: `[🔍 불변 증거 열람]` | `[⚡ Developer Studio에서 열기]` 옆에 `[🔄 Model Retry 준비]` 버튼을 `variant="primary"`로 배치한다.

---

## 3. Idempotency-Key 생성 및 상호작용 UX

1. **멱등성 키 발급 규칙**:
   - HTTP 헤더 `Idempotency-Key`를 필수 전달한다.
   - 키 형식: `idmp_model_retry_${run.projectId}_${run.id}_${Date.now()}`
   - 중복 클릭으로 인한 다중 예약 발행을 방지하기 위해 요청 시작 즉시 로컬 상태 `isPreparingRetry(true)`를 활성화하고 버튼을 즉시 `disabled` 처리한다.
2. **입력 페이로드 기본값 프로토콜**:
   - `cpuMillis`: 부모 run 요구량 또는 기본 500
   - `memoryBytes`: 부모 run 요구량 또는 1073741824 (1 GB)
   - `gpuCount`: 부모 run 사양 연동 (기본 0)
   - `minVramBytes`: 0
   - `requiredBytes`: 0
   - `maxHostLoad`: 0.8
   - `runtime`: "container"
   - `policyVersion`: "model-retry:1"
   - `ttlSeconds`: 30 (서버 기본 바운드 수용)
3. **상호작용 피드백**:
   - 버튼 텍스트 전이: `"🔄 Model Retry 준비"` ➔ `"⏳ 배치 예약 준비 중..."`

---

## 4. requiresFrozenInputAndApproval 정직 고지 문구

백엔드 계약의 `requiresFrozenInputAndApproval: true`는 불변 제약이며, UI는 이를 결코 "즉시 재실행"으로 왜곡해서는 안 된다.

- **성공 안내 배너 (`role="status"`, `data-testid="model-retry-success-banner"`)**:
  > **✓ Model Retry (세대: Generation {result.generation}) 준비 완료**
  >
  > 부모 Run(`{result.parentRunId}`)의 입력 파일, 체크포인트 및 환경 설정이 **불변 동결(Frozen)**되었으며, 신규 자식 Run(`{result.run.runId}`)에 대한 노드 배치 예약(`{result.placement.nodeId}`)이 체결되었습니다.
  >
  > ⚠️ **정직 고지**: 본 재시도는 자동 실행되지 않으며, 인공지능 거버넌스 2인 규칙에 따라 **거버넌스 승인 센터(S04)의 정식 검토 및 승인이 완료된 후** 스케줄링됩니다.
- **후속 행동 버튼 제공**:
  - `[🛡️ 승인 센터로 이동 (S04)]` (`onNavigateApproval(result.run.runId)`)
  - `[📄 신규 Run 상세 보기]` (`onNavigateRun(result.run.runId)`)

---

## 5. Child Run & Lineage (계보) 표시

재시도 준비 성공 시 `RunDetail` 메타데이터 및 계보 뷰에 다음 정보를 실시간 추가한다:

1. **계보 뱃지 및 메타데이터 필드**:
   - **루트 실행 (Root Run)**: `{result.rootRunId}`
   - **부모 실행 (Parent Run)**: `{result.parentRunId}`
   - **재시도 세대 (Generation)**: `Gen {result.generation}`
   - **신규 자식 실행 (Child Run)**: `{result.run.runId}` (상태: `PLANNED`, 버전: `{result.run.version}`, 시도: `{result.run.attempt}`)
   - **예약 노드 및 리스**: `{result.placement.nodeId}` (리스 {result.placement.leases.length}건 체결, 만료 시각 표기)
2. **Tab 1 타임라인 또는 Tab 6 시도 목록 연동**:
   - Attempt/Lineage 목록에 `Child Run (Gen {result.generation}) [Awaiting Approval]` 항목을 정직하게 렌더링.

---

## 6. 오류 응답(409/403/503/400) 처리 및 RFC 9457 Problem Details 표출

오류 발생 시 화면 상단 또는 액션 영역 하단에 `role="alert"` 경보 배너(`data-testid="model-retry-error-alert"`)를 표출하고 원인별 구체적 안내를 제공한다:

| HTTP 상태 코드 | 도메인 오류 코드 | UI 표출 메시지 및 대응 안내 |
|---|---|---|
| **409 Conflict** | `RUN-4091` / `RES-4092` | **재시도 충돌 (409)**: 부모 Run이 실패 종단 상태가 아니거나, 이미 활성 자식 Run 또는 유효한 배치 예약이 존재합니다. |
| **403 Forbidden** | `AUTH-4030` | **권한 거부 (403)**: 현재 사용자 계정은 프로젝트 `{projectId}`에 대한 Model Retry 생성 권한이 없습니다. 관리자에게 문의하십시오. |
| **503 Unavailable** | `MODEL-0002` / `RES-5031` | **서비스 이용 불가 (503)**: 제어 평면의 Model Retry 스케줄러가 구성되지 않았거나, 클러스터 내 요구 사양을 만족하는 가용 노드가 없습니다. |
| **400 Bad Request** | `VAL-4000` | **요청 규격 오류 (400)**: 요청 파라미터가 `ModelRetryPrepareInput` 계약 규격에 부합하지 않습니다. |

---

## 7. Vitest 단위/회귀 시험 케이스 명세

`apps/web/tests/model-retry-action.test.tsx` 파일에 구현할 8대 회귀 시험 명세:

1. **Test 1 (`test_model_retry_button_visibility_terminal_failed_only`)**:
   - `run.state === 'failed'`일 때 버튼이 DOM에 렌더링되고, `succeeded`, `running`, `cancelled` 등 타 상태에서는 렌더링되지 않음을 단언.
2. **Test 2 (`test_model_retry_request_wire_contract_and_headers`)**:
   - 버튼 클릭 시 `POST /v1/projects/{prj}/runs/{parent}/model-retries` 경로로 `Idempotency-Key` 헤더 및 `ModelRetryPrepareInput` 규격 바디가 전송됨을 단언.
3. **Test 3 (`test_model_retry_button_loading_state`)**:
   - 요청 진행 중 버튼이 `disabled`되고 "준비 중..." 문구로 전이되어 다중 클릭이 차단됨을 단언.
4. **Test 4 (`test_model_retry_success_banner_and_honest_approval_notice`)**:
   - `201 Created` 응답 수신 시 `requiresFrozenInputAndApproval: true`에 따른 "자동 실행 없음 / 승인 센터 승인 필요" 정직 고지 배너(`role="status"`) 표출 단언.
5. **Test 5 (`test_model_retry_child_lineage_metadata_rendering`)**:
   - 자식 `runId`, `generation`, `placement.nodeId`가 화면에 정확히 투영됨을 단언.
6. **Test 6 (`test_model_retry_409_conflict_handling`)**:
   - 409 Conflict Problem Details 수신 시 `role="alert"`와 함께 충돌 안내 문구가 표출됨을 단언.
7. **Test 7 (`test_model_retry_503_unavailable_handling`)**:
   - 503 Problem Details 수신 시 스케줄러 미구성/자원 부족 경보 표출 단언.
8. **Test 8 (`test_model_retry_navigation_handlers_triggered`)**:
   - 성공 배너의 `승인 센터 이동` 버튼 클릭 시 `onNavigateApproval(childRunId)` 콜백이 호출됨을 단언.

---

## 8. 결론 및 구현 준비 상태

본 설계는 Codex 커널 계약(`563c54ce`)과 ADR-044/045 거버넌스 원칙을 100% 충족하며, 프런트엔드가 임의로 자동 승인을 가정하거나 일반 Run 재시도로 호도하는 결함을 원천 차단한다.

코디네이터의 메모리 경보 해제 통보 즉시 상기 명세에 따라 `RunDetail.tsx` 수정, `modelRetry.ts` API 어댑터 구축, Vitest 8대 회귀 시험 작성 및 `tools/run_real_browser_acceptance.py` 검속으로 착지할 준비를 완료하였다.
