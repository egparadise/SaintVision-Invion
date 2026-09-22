---
doc_id: "HIST-GEMINI-2026-09-22-MODEL-RETRY-UI"
title: "RunDetail 모델 재시도(model-retries, 결정 #6 6a) UI 구현 및 계약 결속 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-22T20:25:00+09:00"
source_of_truth: "Git"
---

# RunDetail 모델 재시도(model-retries, 결정 #6 6a) UI 구현 및 계약 결속 보고

- 작업 일시: 2026-09-22T20:25:00+09:00 (KST)
- 배정: Gemini (Frontend / Design / Browser Acceptance Owner)
- 검토 요청: Claude (독립 reviewer)
- 참조 문서: [[2026-09-22_RunDetail_재시도액션_model-retries_UI설계_Gemini]], [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[Codex Workspace 편집과 PTY 및 원격 Git 계약]]

---

## 1. 개요 및 목적

Codex 커널 계약(`563c54ce`) 및 코디네이터 지시([PR #54](https://github.com/egparadise/SaintVision-Invion/pull/54) 설계 메모 승인)에 따라, 실패한 모델 파이프라인 Run에 대해 안전하고 정직한 모델 재시도(Model Retry) 준비 액션을 프런트엔드 `RunDetail` 컴포넌트에 구현하고 백엔드 정본 서빙 라우트(`POST /v1/projects/{project}/runs/{parent}/model-retries`)와 결속하였다.

본 구현은 불변식과 거버넌스 원칙을 엄격히 준수한다:
1. **failed 종단 상태에서만 노출**: `run.state === 'failed'`일 때만 `[🔄 Model Retry 준비]` 버튼을 표출하며, 타 상태에서는 DOM에서 완전히 은닉.
2. **Idempotency-Key 발급 및 로딩 가드**: `idmp_model_retry_${prj}_${parent}_${timestamp}` 멱등성 헤더 전달 및 요청 중 버튼 비활성화(`disabled`)와 `⏳ 배치 예약 준비 중...` 텍스트 전이로 다중 발행 차단.
3. **`requiresFrozenInputAndApproval: true` 정직 고지**: 자동 실행 없음 및 S04 거버넌스 승인 센터 정식 승인 후 스케줄링됨을 정직 고지하는 안내 배너(`role="status"`, `data-testid="model-retry-success-banner"`) 완비.
4. **Child Run ID 및 계보(Lineage) 투영**: 루트, 부모, 세대(Generation), 신규 자식 Run ID(`planned`), 노드 예약 및 체결된 리스 건수 렌더링.
5. **RFC 9457 Problem Details 에러 대응**: 409 Conflict, 403 Forbidden, 503 Unavailable, 400 Bad Request에 대해 구체적 사유 및 대응 안내를 담은 경보 배너(`role="alert"`, `data-testid="model-retry-error-alert"`) 표출.

---

## 2. 변경 파일 및 구현 내역

### 2.1 `packages/contracts-ts/src/index.ts` 계약 타입 재수출
- `apps/web/src/contracts/types.ts`:
  - `ModelRetryPrepareInput`, `ModelRetryPlacementResult`, `ModelRetryPrepareResult` canonical 타입 re-export.
  - `RunItem` ViewModel 인터페이스에 선택적 `resourceRequest`(`cpuMillis`, `memoryBytes`, `gpuCount`, `minVramBytes`, `requiredBytes`) 필드 추가.

### 2.2 API 어댑터 신설: `apps/web/src/shared/api/modelRetry.ts`
- `prepareModelRetry(projectId, parentRunId, options)`:
  - 부모 Run의 요구량(`cpuMillis`, `memoryBytes`, `gpuCount`) 또는 안전 기본값(500m, 1GB, container runtime, ttl 30s)을 payload로 조립.
  - 정본 라우트 `/v1/projects/{project}/runs/{parent}/model-retries`로 `POST` 요청 발행.
  - `Idempotency-Key` 헤더 자동 주입.
- `formatModelRetryProblem(problem, projectId)`:
  - RFC 9457 Problem Details 응답의 상태 코드(409, 403, 503, 400)에 따른 한국어 사용자 안내 및 원인 문자열 포맷팅.

### 2.3 `RunDetail.tsx` UI 컴포넌트 실배선
- `handlePrepareModelRetry`: 프로젝트 부재 시 위조 식별자 합성 방지 가드 작동, API 통신 중 로딩 상태 제어, 결과 수신 시 계보 메타데이터 및 성공 배너 표출.
- 실패 종단 가드: `{run.state === 'failed' && <Button data-testid="model-retry-prepare-btn" ...>}`.
- 성공 배너: `role="status"` 배너 내부에 S04 승인 센터 이동(`onNavigateApproval`) 및 자식 Run 상세 이동(`onNavigateRun`) 후속 액션 버튼 제공.
- 계보 뷰: `retry-child-lineage-section`을 통해 신규 발급된 자식 Run(`PLANNED`)과 예약 노드 실시간 노출.

---

## 3. 검증 실측 결과

### 3.1 Vitest 8대 회귀 시험 전수 합격 (100% GREEN)
`apps/web/tests/model-retry-action.test.tsx` 신설 및 8대 시나리오 검증:
1. `Test 1`: `run.state === 'failed'`에서만 버튼 노출, `succeeded`/`running`/`cancelled`/`scheduled`/`draft`에서 완전 은닉 단언 (PASS).
2. `Test 2`: `POST /v1/projects/{prj}/runs/{parent}/model-retries` 경로, `Idempotency-Key` 헤더, `ModelRetryPrepareInput` 페이로드 전송 단언 (PASS).
3. `Test 3`: 요청 중 버튼 `disabled` 및 `배치 예약 준비 중...` 로딩 상태 전이 단언 (PASS).
4. `Test 4`: 201 Created 수신 시 `requiresFrozenInputAndApproval: true`에 따른 "자동 실행 없음 / 거버넌스 승인 센터(S04) 승인 필요" 정직 고지 배너(`role="status"`) 표출 단언 (PASS).
5. `Test 5`: 자식 Run ID, 세대(Generation 1), 노드 ID, 상태(`PLANNED`) 계보 메타데이터 렌더링 단언 (PASS).
6. `Test 6`: 409 Conflict Problem Details 수신 시 `role="alert"` 경보 및 충돌 안내 표출 단언 (PASS).
7. `Test 7`: 503 Unavailable Problem Details 수신 시 스케줄러 미구성 경보 표출 단언 (PASS).
8. `Test 8`: 성공 배너의 승인 센터 이동 및 자식 Run 상세 보기 클릭 시 각각 `onNavigateApproval(childRunId)`, `onNavigateRun(childRunId)` 콜백 호출 단언 (PASS).

**실행 결과**:
```
 ✓ tests/model-retry-action.test.tsx (8 tests) 306ms
 Test Files  1 passed (1)
      Tests  8 passed (8)
```

### 3.2 TypeScript 프로젝트 컴파일 실측 (`tsc -b`)
```powershell
npx tsc -b
# Exit code 0 (0 errors, 완벽한 타입 안전성 실측)
```

### 3.3 백엔드-프런트엔드 라우트 커버리지 회귀 시험 (`test_route_coverage.py`)
```powershell
pytest tests/test_route_coverage.py
# 38 passed in 1.31s (Exit code 0, unserved route 0건)
```

### 3.4 프런트엔드 무결성 검사 도구 (`check_frontend_integrity.py`)
```powershell
python -X utf8 tools/check_frontend_integrity.py
# ✔ Frontend Integrity Check Passed: All 9 integrity rules satisfied (0 violations). (Exit code 0)
```

### 3.5 Vite 프로덕션 번들 빌드 (`npm run build`)
```
✓ 100 modules transformed.
dist/index.html                   0.79 kB │ gzip:   0.41 kB
dist/assets/index-d374E-lm.css    2.09 kB │ gzip:   0.77 kB
dist/assets/index-8pgHru5U.js   779.82 kB │ gzip: 197.28 kB │ map: 2,455.94 kB
✓ built in 6.81s (Exit code 0)
```

---

## 4. 인계 및 후속 조치

- **작업 브랜치**: `agent/gemini/model-retry-ui` (기반: `b877c601`)
- **독립 검토자**: Claude
- **후속 연계**: 거버넌스 승인 센터(S04)에서 준비된 자식 Run(`requiresFrozenInputAndApproval`)의 승인 워크플로와 자연스럽게 연결됨.
