---
doc_id: "HIST-GEMINI-G05-W3-W5-FE-ROUTES-001"
title: "G-05 W3 Verify 및 W5 Eval Run FE 비즈니스 라우트 화면 연동 및 무결성 불변식 검증"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-29T00:33:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-05", "CARD-101"]
tags: ["s10-fe", "g-05", "card-101", "model-verify", "eval-runs", "trusted-worker", "rfc9457", "idempotency", "gemini"]
---

# G-05 W3 Verify 및 W5 Eval Run FE 비즈니스 라우트 화면 연동 및 무결성 불변식 검증 (카드 101)

## 1. 개요 및 배경

- **목적**: `ModelLineageView` 화면에 W3 모델 검증(Verify) 및 W5 평가 실행(Eval Run) 비즈니스 라우트를 연동하고, 정직성(Zero Fake Measurements / Zero Fake Verification), 엄격한 계약 타입 및 런타임 가드, 접근성(a11y), 멱등성 및 fail-closed 불변식을 확립한다.
- **대상 Business Routes (서버 구현 실재)**:
  1. `POST /projects/{project_id}/models/{model_id}/versions/{version}/verify` (W3 커널 측정 검증, `src/saintvision/api/v1/model_verify.py:103`)
  2. `POST /projects/{project_id}/eval/suites/{suite_id}/runs` (W5 평가 실행 시작, `src/saintvision/api/v1/eval_runs.py:72`)
- **설계 및 계약 정본**:
  - `docs/vault/30_Development/G-04_G-05 business lane route 통합 설계 v1.0.md` (#183)
  - `docs/vault/30_Development/` W3 verify trusted-worker measurement seam 설계 (#209)
  - `contracts/model-verify-request.schema.json`
  - `contracts/model-verify-response.schema.json`
  - `contracts/eval-run-start-request.schema.json`
  - `contracts/eval-run-response.schema.json`
- **Zero Fake Measurement / Zero Fake Verification 불변식**:
  - W3 커널 검증 요청 바디는 오직 커널 측정 ID(`measurementId`: `mvm_...` 26자리 Crockford Base32)만 전송하며, 실제 측정 출처와 계보 스냅샷 일치 여부는 서버 커널 신뢰 워커가 판정한다.
  - 프런트엔드는 측정값을 임의로 지어내거나 자체적으로 "검증됨"을 판정하지 않으며, 서버의 응답(`verifiedAt`, `verifiedMeasurementId`, `newlyVerified`)만을 토대로 화면 배지와 상태를 정직하게 표출한다.
  - W5 평가 실행은 어댑터 식별자, 프롬프트/컨텍스트 버전, 모델 고정 요구(`requireModelPinning`)를 서버에 전달하고, 반환된 게이트 통과 여부(`passedGate`), 통과 케이스 수(`passedCases / totalCases`), 위반 건수(`violations`)를 가공 없이 정직하게 시각화한다.

## 2. 주요 구현 내용

### 2.1 계약 스키마 등록 및 자동 생성 동기화
- `apps/web/scripts/api-response-contracts.mjs`에 W3 / W5 관련 스키마 4종 추가 등록:
  - `model-verify-request.schema.json`
  - `model-verify-response.schema.json`
  - `eval-run-start-request.schema.json`
  - `eval-run-response.schema.json`
- `npm run contracts:generate --write`를 통해 엄격한 TypeScript 타입 인터페이스 생성 (수동 편집 0건).
- `npm run contracts:check` 실측 32개 전체 타입 완벽 일치 (exit 0).

### 2.2 Observation 계층 및 런타임 fail-closed 가드 (`modelRegistryObservation.ts`)
- `verifyModelVersion`, `startEvalRun` 2종 API fetcher 구현.
- 허용 key 화이트리스트 및 엄격한 런타임 가드 구현:
  - `isModelVerifyResponse`: 허용 key 화이트리스트 외 추가 속성(`additionalProperties: false`) fail-closed 차단, 필수 key(`modelVersionId`, `modelId`, `version`, `stage`, `verifiedAt`, `verifiedMeasurementId`, `contentSha256`, `newlyVerified`) 전수 검증, `mvm_` 26자리 Crockford Base32 정규식 검증, ISO-8601 시각 유효성 검증.
  - `isEvalRunResponse`: 허용 key 화이트리스트 외 추가 속성 차단, 필수 key 전수 검증, `status` enum (`running | completed | aborted`) 검증, `evr_` 26자리 Crockford Base32 검증, 케이스 경계 제약(`passedCases <= totalCases`, `violations >= 0`) 검증, ISO-8601 시각 유효성 검증.
- 멱등키 보존 및 회전: `verifyIdempotencyKey`, `evalIdempotencyKey`를 통해 실패 시 재시도는 동일 키를 재사용하여 이중 부수효과를 차단하고, 파라미터 변경 시 새 키로 회전.

### 2.3 UI 컴포넌트 강화 (`ModelLineageView.tsx`)
- **비즈니스 라우트 탭 확장 (총 6종)**:
  - `1. 계보 질의 (Lineage Trace)`
  - `2. 버전 등록 (W2 Register)`
  - `3. 보존 핀 (W4 Retention Pin)`
  - `4. 릴리스 (Release Model)`: Codex r4 F1에 따라 서버 멱등 계약 수립(카드 113) 전까지 쓰기 UI fail-closed 비활성화 및 안내 배너 유지.
  - `5. W3 검증 (W3 Verify)`: `POST /verify` 호출 폼, `measurementId` 클라이언트 사전 검증, 커널 측정 검증 상태 배지 및 결과 카드.
  - `6. W5 평가 실행 (W5 Eval Run)`: `POST /eval/suites/{suiteId}/runs` 호출 폼, 어댑터 및 컴포넌트 버전 지정, `GATE PASS` / `GATE FAIL` 정직한 결과 렌더링.
- **동시성 및 세대 분리 (Separate AbortControllers & Generations)**:
  - `verifyAbortControllerRef`, `evalAbortControllerRef`를 독립 할당하여 타 쓰기 작업의 간섭 및 로딩 영구 걸림 차단.
  - `verifyGenerationRef`, `evalGenerationRef`를 통해 폼 입력 변경 시 즉시 세대 증가 및 늦은 응답 무효화.
- **접근성 (a11y)**:
  - 성공/오류 발생 시 `aria-live="polite"` 라이브 리전으로 즉각 음성 안내 전달.
  - 결과 카드는 `role="status"`, 오류 알림은 `role="alert"`로 명확히 분리.
  - 권한 없는 사용자(`canApprove !== true`) 대상 모든 쓰기 버튼에 `disabled` 및 `aria-disabled="true"`와 fail-closed 안내문 부여.

## 3. 실측 검증 증거

- **Vitest 전용 및 전체 스위트 (`apps/web`)**:
  - `tests/model-verify-eval-routes.test.tsx`: 10 passed (406ms)
  - `tests/model-registry-business-routes.test.tsx`: 20 passed (860ms)
  - 웹 전체: 81 test files, 761 passed (30.98s)
- **TypeScript 타입 점검 및 빌드**:
  - `npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: 프로덕션 번들 정상 생성 (889.27 kB, 8.83s)
  - `npm run contracts:check`: 32 API response TypeScript types match (PASS)
- **프런트엔드 무결성 가드 (`tools/check_frontend_integrity.py`)**:
  - 88개 소스 파일 대상 9대 무결성 규칙 0 violations (PASS)
- **계약 바인딩 검사 (`tools/check_contract_bindings.py`)**:
  - 55 fixtures, 20 bound types, 14 replay guards (PASS)
- **파이썬 백엔드 라우트 스위트 (`pytest tests/test_route_coverage.py`)**:
  - 40 passed (4.61s)
- **문서 무결성 및 Obsidian 동기화 검사**:
  - `tools/check_docs.py`: 24 hashes, 930 documents, 48 tasks, 12 outcomes PASS (exit 0)
  - `tools/sync_obsidian.py --check`: 1778 managed files, 0 conflicts (PASS)

## 4. 변경 파일 목록

- `apps/web/scripts/api-response-contracts.mjs`: W3/W5 스키마 4종 추가 (총 32종 관리).
- `apps/web/src/contracts/model-verify-request.ts`: 자동 생성 인터페이스.
- `apps/web/src/contracts/model-verify-response.ts`: 자동 생성 인터페이스.
- `apps/web/src/contracts/eval-run-start-request.ts`: 자동 생성 인터페이스.
- `apps/web/src/contracts/eval-run-response.ts`: 자동 생성 인터페이스.
- `apps/web/src/shared/api/modelRegistryObservation.ts`: verifyModelVersion, startEvalRun, 런타임 가드 2종, 정규식/바운드 가드 구현.
- `apps/web/src/features/mlops/ModelLineageView.tsx`: Tab 5 (W3 Verify) 및 Tab 6 (W5 Eval Run) 연동, 접근성 및 결과 표시, 독립 Abort/세대 가드.
- `apps/web/tests/model-verify-eval-routes.test.tsx`: W3/W5 비즈니스 라우트 전용 통합 시험 10종 구현 (되돌리면 실패).
- `apps/web/tests/model-registry-business-routes.test.tsx`: PR #219 r4 정합 (20종 시험).
- `docs/vault/30_Development/History/2026-09-29_00-33-00_KST_G05_W3_Verify_W5_Eval_FE_Gemini.md`: 본 기록 문서.
- `docs/vault/30_Development/Agent별 작업/Gemini 작업 현황.md`: 작업 현황 v1.0.136 갱신.

## 5. 결론 및 향후 계획

- 카드 101 W3 Verify 및 W5 Eval Run 화면 연동이 성공적으로 완료되었으며 모든 불변식(정직성, 계약 일치, 멱등성, fail-closed 권한 가드, 웹 접근성)이 검증되었다.
- PR 발행 후 Claude / Codex 검토를 요청하고, 카드 113 서버 릴리스 멱등성 계약 추가 진행 상황을 추적한다.
