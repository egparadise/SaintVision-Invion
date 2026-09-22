---
doc_id: "HIST-GEMINI-2026-09-22-MODEL-RETRY-UI"
title: "RunDetail 모델 재시도(model-retries, 결정 #6 6a) UI 구현 및 계약 결속 보고"
version: "1.1.0"
status: "review"
author: "Gemini"
updated: "2026-09-22T21:05:00+09:00"
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
---

## 4. Claude 독립 검토 수정 요청 3건 반영 내역 (2026-09-22T21:05:00+09:00)

Claude의 독립 검토 코멘트에 따라 다음 3건의 수정 요구 및 1건의 경미 권고사항을 100% 반영 완료했다:

1. **입력 사양 합성 차단 (Zero-Mock 위반 원천 치유)**:
   - 부모 Run의 실제 workload/자원 요구(`run.resourceRequest?.cpuMillis > 0`, `memoryBytes > 0`)가 관측된 경우에만 버튼을 활성화.
   - 사양이 미관측된 경우 버튼을 비활성화(`disabled`)하고 버튼 라벨을 `'입력 사양 미관측'`으로 정직 고지하며, 툴팁으로 재시도 배치 예약 불가 사유를 투명하게 안내.
   - 어댑터(`modelRetry.ts`)에서 `?? 500`, `?? 1073741824` 류의 기본값 합성을 전면 제거하고 필수 `ModelRetryPrepareInput`을 엄격히 강제.
2. **부모 Run당 안정 Idempotency-Key 발급 (`Date.now()` 제거)**:
   - 매 클릭마다 타임스탬프가 달라져 멱등성을 상실하고 재요청 시 409 MODEL-0003을 유발하던 문제를 해결.
   - `model-retry:${projectId}:${parentRunId}:${runVersion}` 안정 키를 생성하여 중복 클릭 및 재시도 시 동일 자식 Run을 반환받도록 보장.
3. **성공 배너 과장 문구 정정**:
   - 커널 계약상 `requiresFrozenInputAndApproval: true`는 "입력 동결과 승인이 아직 필요함"을 의미하므로, 기존 "입력 파일이 동결되었으며 예약이 체결되었습니다" 과장 문구를 "배치 예약만 준비됨 (신규 자식 Run: PLANNED) — 입력 동결과 거버넌스 승인은 별도 단계가 필요합니다"로 정직하게 정정.
4. **RFC 9457 Problem Details `problem.code` 분기 정밀화**:
   - `status` 단독 분기에서 `problem.code` 우선 분기(`MODEL-0003`, `MODEL-0001`, `IDEM-0001`, `AUTH-0030`, `MODEL-0007`/`LEASE-0003`/`MODEL-0002`, `VAL-000x`/422)로 고도화하여 백엔드 에러 원인을 정확히 한국어로 표출.
5. **단위 테스트 확장 (9/9 passed)**:
   - `Test 9: test_model_retry_disabled_when_resource_specs_unobserved` 추가.
   - `apps/web/tests/model-retry-action.test.tsx` 9개 시험 전수 통과 (292ms).
