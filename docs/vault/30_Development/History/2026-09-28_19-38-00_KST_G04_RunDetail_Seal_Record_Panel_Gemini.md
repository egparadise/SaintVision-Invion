---
title: "G-04 RunDetail 봉인 기록 읽기 전용 패널 및 무결성 검증 (카드 86)"
version: "1.0"
status: "review"
author: "Gemini"
updated: "2026-09-28T19:38:00+09:00"
---

# G-04 RunDetail 봉인 기록 읽기 전용 패널 및 무결성 검증 (카드 86)

- **작업 브랜치**: `agent/gemini/g04-fe-seal-record`
- **Base**: PR #201 head `9dfb2878` (W1 봉인 쓰기) + PR #188 head `dfb666a3` (R2 레코드 아티팩트 및 검증) 클린 머지 (`86c6909a`, 신규 편집 0건).
- **관련 카드**: 코디네이터 카드 86 (RunDetail 봉인 기록 R1·R2·R3 읽기 전용 패널 및 무결성 검증 연동).
- **리뷰어 지정**: Claude (UI·테스트 축), Codex (계약 축).

---

## 1. 구현 내용

### 1) TypeScript 계약 동기화 (`packages/contracts-ts` & `apps/web`)
- `apps/web/scripts/api-response-contracts.mjs`에 신규 4종 스키마 등록:
  - `run-record-response` (`contracts/run-record-response.schema.json`)
  - `run-record-artifact-page-response` (`contracts/run-record-artifact-page-response.schema.json`)
  - `artifact-pin-verification-response` (`contracts/artifact-pin-verification-response.schema.json`)
  - `context-bundle-response` (`contracts/context-bundle-response.schema.json`)
- `npm run contracts:check` 실행으로 20개 API 응답 계약 타입 검증 완료 (exit 0). `packages/contracts-ts/src/index.ts` 수동 편집 0건 준수.

### 2) Observation 계층 (`apps/web/src/shared/api/runSealObservation.ts`)
- 엄격 런타임 가드 함수 구현:
  - `isRunRecordResponse`: 허용 키 11종 화이트리스트 외 임의 추가 키 차단, `bundleHash`/`workloadSpecSha256` 64자리 16진수 엄격 검증, `sealedAt` ISO-8601 검증.
  - `isRunRecordArtifactPageResponse`: 허용 키 7종 화이트리스트 및 `RunRecordArtifactPin` 항목별 6종 키 화이트리스트 검사.
  - `isArtifactPinVerificationResponse`: `verified` boolean 필드 엄격 검사, `pinnedChecksumSha256` 64자리 16진수 검사.
  - `isContextBundleResponse`: 허용 키 12종 화이트리스트, `hashVerified` 및 `sealed` boolean 엄격 검사, `bundleHash` 64자리 16진수 검사.
- 4종 비즈니스 경로 API fetcher 함수 (`fetchRunRecord`, `fetchRunRecordArtifacts`, `verifyRunRecordArtifact`, `fetchContextBundle`).

### 3) 봉인 기록 패널 컴포넌트 (`apps/web/src/features/runs/SealRecordPanel.tsx`)
- **R1 RunRecord 상태 처리**:
  - 봉인 성공 시 봉인 배지(`✔ 봉인됨 (SEALED)`), 레코드 ID, 봉인 시각, 번들 ID/해시, 워크로드 스펙 해시, 에비던스 ID, 어댑터/커널 버전, 시도 횟수 표출.
  - 404 `RES-0004` ("No sealed record for this run.") 발생 시 가짜 PASS/수치 없이 정직한 `미봉인 (UNSEALED)` 배지 및 안내 배너 렌더링.
- **R2 Pinned Artifacts 목록 및 검증 (Pin Verify)**:
  - 아티팩트 목록 테이블 (Artifact ID, Role, Size, Object Version, SHA-256 체크섬).
  - 각 행별 '검증 (Verify)' 버튼: 클릭 시 `GET /v1/.../record/artifacts/{artifact_id}/verify` 호출.
  - `verified: false`는 시스템 오류가 아니라 변조/불일치 사실에 대한 정상 200 보고이므로, 에러 배너를 띄우지 않고 상태 컬럼에 `⚠️ 불일치 (Tampered/Mismatch)`로 정직 표기 (합격/PASS/녹색 위장 금지).
- **R3 Context Bundle 메타데이터 및 무결성**:
  - 최신 번들 ID, 총 바이트, 토큰 추정치, 빌드 시각 표출.
  - `hashVerified: true` 시 `✔ 해시 일치 (Hash Verified)`, `hashVerified: false` 시 `⚠️ 해시 불일치 (Hash Mismatch)` 사실 보고 표출.
  - 미봉인 실행의 경우 `최신 빌드 (Latest Build)` 배지 표출.
- **예외 및 무결성 방어**:
  - 401 (`AUTH-MISSING-CREDENTIAL`), 403 (`AUTH-0030`), 404 (`RES-0004`) canonical ProblemDetails 분기 격리.
  - 프록시/게이트웨이 HTML 502/504 에러 시 DOM 태그 누출을 차단하고 정제된 한국어 메시지 표출.
  - `role="status" aria-live="polite"` 라이브 리전 컨테이너를 조건부 렌더링하지 않고 DOM에 상시 유지하며 텍스트 노드만 갱신 (스크린리더 누락 방지).
  - 다크 테마 WCAG AA 명도 대비 4.5:1 이상 준수.

### 4) RunDetail 화면 탭 연동 (`apps/web/src/features/runs/RunDetail.tsx`)
- Tab 7 `7. 봉인 기록 (Seal Record)` (`data-testid="tab-seal"`) 추가.
- 탭 활성화 시 `<SealRecordPanel projectId={run.projectId} runId={run.id} />` 렌더링.

---

## 2. 검증 실측 결과

| 검증 항목 | 명령 | 결과 | 비고 |
| :--- | :--- | :---: | :--- |
| 패널 및 계약 바인딩 Vitest | `npm test -- run-detail-seal-record` | **PASS (12/12)** | R1/R2/R3, 404 미봉인, 403, 401, 502, revert-fail, a11y, 대비 실측 |
| Web 전체 Vitest 스위트 | `npm test` | **PASS (79/79 files, 687/687 tests)** | 회귀 0건 |
| TypeScript 엄격 컴파일 | `npx tsc -b` | **PASS (exit 0)** | 0 type errors |
| 프로덕션 번들 빌드 | `npm run build` | **PASS (exit 0)** | 4.83s, 번들 정상 생성 |
| 계약 스키마 동기화 검사 | `npm run contracts:check` | **PASS (exit 0)** | 20개 API 응답 타입 정합 |
| 화면-백엔드 라우트 커버리지 | `pytest tests/test_route_coverage.py` | **PASS (40/40)** | Python 백엔드 CI 게이트 통과 |
| 프런트엔드 무결성 스캐너 | `python tools/check_frontend_integrity.py` | **PASS (exit 0)** | 85개 소스 파일 9대 무결성 규칙 0 위반 |
| 계약 fixture & 서빙앵커 검사 | `python tools/check_contract_bindings.py` | **PASS (exit 0)** | 55개 fixture, 20개 타입 앵커 정합 |
