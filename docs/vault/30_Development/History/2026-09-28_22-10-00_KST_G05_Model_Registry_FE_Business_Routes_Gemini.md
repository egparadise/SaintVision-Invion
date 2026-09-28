---
doc_id: "HIST-GEMINI-G05-FE-MODEL-REGISTRY-001"
title: "G-05 FE 모델 레지스트리 화면 실제 business route 연동 및 불변식 검증"
version: "1.1.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T22:38:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-05"]
tags: ["s10-fe", "g-05", "model-registry", "lineage", "retention-pin", "model-release", "rfc9457", "idempotency", "gemini"]
---

# G-05 FE 모델 레지스트리 화면 실제 business route 연동 및 불변식 검증 (카드 94)

## 1. 개요 및 배경

- **목적**: `ModelLineageView` 화면을 모의(mock) 데이터 수준에서 벗어나 실제 G-04 / G-05 business lane route 4종에 직접 연결하고, 계약 일치·정직성·접근성·멱등성 불변식을 확립한다.
- **대상 Business Routes (서버 구현 실재)**:
  1. `POST /projects/{project_id}/models/{model_id}/versions` (W2 모델 버전 등록, `model_versions.py:111`)
  2. `POST /projects/{project_id}/models/{model_id}/versions/{version}/retention-pin` (W4 보존 핀 연장, `model_retention.py:99`)
  3. `POST /projects/{project_id}/models/{model_id}/versions/{version}/release` (Release 릴리스 선언 및 전환, `model_release.py:332`)
  4. `GET /projects/{project_id}/models/{model_id}/versions/{version}/lineage` (Lineage trace 계보 질의, `lineage_query.py:68`)
- **설계 및 계약 정본**:
  - `docs/vault/30_Development/G-04_G-05 business lane route 통합 설계 v1.0.md` (#183)
  - `contracts/model-version-register-request.schema.json`
  - `contracts/model-version-response.schema.json`
  - `contracts/retention-pin-request.schema.json`
  - `contracts/retention-pin-response.schema.json`
  - `contracts/model-release-request.schema.json`
  - `contracts/model-release-response.schema.json`
  - `contracts/model-lineage-trace-response.schema.json`
- **Base 브랜치**: `agent/claude/g04-w4-retention-pin` head `0b949454` (W2 #191 포함).

## 2. 주요 구현 내용

### 2.1 계약 스키마 등록 및 자동 생성 동기화
- `apps/web/scripts/api-response-contracts.mjs`에 G-04/G-05 관련 스키마 7종 추가 등록:
  - `model-version-register-request`, `model-version-response`, `retention-pin-request`, `retention-pin-response`, `model-release-request`, `model-release-response`, `model-lineage-trace-response`
- `npm run contracts:generate --write`를 통해 엄격한 TypeScript 타입 인터페이스 생성 (수동 편집 0건, `packages/contracts-ts` 오염 방지).
- `npm run contracts:check` 실측 23개 전체 타입 완벽 일치 (exit 0).

### 2.2 Observation 계층 및 런타임 fail-closed 가드 (`modelRegistryObservation.ts`)
- `fetchModelLineage`, `registerModelVersion`, `extendRetentionPin`, `releaseModelVersion` 4종 API fetcher 구현.
- 허용 key 화이트리스트 및 타입 가드(`isModelLineageTraceResponse`, `isModelVersionResponse`, `isRetentionPinResponse`, `isModelReleaseResponse`) 구현으로 정본 스키마와 불일치하는 악성/변조 응답을 런타임에 fail-closed 차단.
- RFC 3339 일시 및 달력 유효성 검증(`isValidIsoDateTime`): 2월 30일, 25시 61분 등 불가능한 시각 거부.
- 암호학적 UUID v4 기반 멱등키 생성(`generateIdempotencyKey`): `Idempotency-Key` 헤더로 전달하여 중복 제출 및 네트워크 재시도에 따른 이중 부수효과 방지.

### 2.3 UI 컴포넌트 강화 (`ModelLineageView.tsx`)
- **실제 Business Route 탭 구성**:
  - `1. 계보 질의 (Lineage Trace)`: 실 `GET /lineage` 질의 트리거 및 계보 노드/엣지 렌더링.
  - `2. 버전 등록 (W2 Register)`: `POST /versions` 호출 폼 및 버전 메타데이터 등록.
  - `3. 보존 핀 (W4 Retention Pin)`: `POST /retention-pin`을 통한 만료일 연장/설정.
  - `4. 릴리스 (Release Model)`: `POST /release`를 통한 라이선스 정책 및 타깃 환경 선언 후 릴리스 전환.
- **정직성 원칙 (Zero Fake Pass / Zero Fake Metrics)**:
  - 서버에서 관측되지 않은 수치/평가/인증에 대해 허위 100%나 가짜 정확도를 생성하지 않고 명시적으로 `NOT_OBSERVED (미측정)` 배지와 함께 "서버 계측 기록 없음"으로 정직하게 표기.
  - W3 솔기(seam)에 대한 명시적 안내: `"W3 검증: 미연결 (검증 앵커 #215 대기)"` 배지를 표출하여 미연결 상태를 위장하지 않음.
- **오류 및 상태 처리 (RFC 9457 ProblemDetails)**:
  - 401 (`AUTH-MISSING-CREDENTIAL`), 403 (`AUTH-0030`), 404 (`MODEL-0004`, `RES-0004`), 409 (`GRAPH-0002` 멱등성 충돌), 422 (`VAL-0003`) 등 표준 에러를 `role="alert"` 배너로 표출.
  - HTML 502/504 프록시 응답 시 마크업 누출을 차단하고 정제된 한국어 안내문 제공.
- **웹 접근성 (a11y)**:
  - `role="status" aria-live="polite"` 라이브 리전 컨테이너를 상시 DOM에 유지하여 스크린 리더 지원.
  - 다크 테마 기준 WCAG AA 대비 4.5:1 이상(주요 텍스트 5.5:1 이상) 실측 확보.

## 3. 실측 검증 증거

- **Vitest 전용 및 전체 스위트 (`apps/web`)**:
  - `tests/model-registry-business-routes.test.tsx`: 13 passed (456ms)
  - 웹 전체: 79 test files, 688 passed (21.33s)
- **TypeScript 타입 점검 및 빌드**:
  - `npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: 프로덕션 번들 정상 생성 (815.13 kB, 11.92s)
  - `npm run contracts:check`: 23 API response TypeScript types match (PASS)
- **프런트엔드 무결성 가드 (`tools/check_frontend_integrity.py`)**:
  - 84개 소스 파일 대상 9대 무결성 규칙 0 violations (PASS)
- **계약 바인딩 검사 (`tools/check_contract_bindings.py`)**:
  - 55 fixtures, 20 bound types, 14 replay guards (PASS)
- **파이썬 백엔드 라우트 스위트 (`.venv`, Python 3.14.7)**:
  - `tests/test_route_coverage.py`: 40 passed (4.39s)
  - `tests/core/test_model_release_route.py`: 59 passed (20.54s)
  - `tests/core/test_model_retention_pin_route.py` & `test_model_version_register_route.py`: 133 passed (27.04s)

## 4. Codex (F1~F5) 및 Claude (G1~G6) 1차 검토 반영 내역 (r2)

- **Codex F1 (canApprove fail-closed 엄격 적용)**:
  - `(currentUser as { canApprove?: boolean })?.canApprove === true`로 엄격화하여 `undefined`, `null`, `false` 및 전역 역할(`role: 'owner'`, `role: 'operator'`) fallback을 전면 배제.
  - 권한 미충족 시 전역 경고 배너(`banner-no-approve-permission`) 표출 및 W2 등록, W4 보존 연장, 릴리스 3개 쓰기 버튼을 `disabled` 및 `aria-disabled="true"` 처리 (시험 8).
- **Codex F2 & Claude G2 (Idempotency-Key 재시도 안정성 및 의도 단위 유지)**:
  - `ModelLineageView` 상태에 `regIdempotencyKey` 및 `pinIdempotencyKey`를 보존하여, 503/timeout 등 일시적 실패 후 사용자가 재시도할 때 정확히 동일한 key를 재전송하도록 보장.
  - 입력 필드 수정 시 또는 제출 성공 시에만 새 멱등키로 회전(rotate). Model Release 경로는 서버 계약(`model_release.py`)상 Idempotency-Key를 수신하지 않으므로 헤더 미전송 및 in-flight 가드로 이중 제출 방지 명시 (시험 13, 시험 4).
- **Codex F3 & Claude G4 (additionalProperties: false 및 컬렉션 상한 강제)**:
  - `isModelLineageTraceResponse`, `isModelVersionResponse`, `isRetentionPinResponse`, `isModelReleaseResponse` 4종 최상위 응답 및 3종 중첩 타입(`LineageDatasetVersion`, `LineageDeployment`, `LineageUnresolved`)에 허용 key whitelist Set을 적용하여 여분 속성 유입 시 fail-closed 거부.
  - `datasets`(<=200), `deployments`(<=200), `missing`(<=16), `unresolved`(<=16), `detailedKinds`(<=16), `countOnlyKinds`(<=16) 컬렉션 상한 강제 (시험 16).
- **Codex F4 & Claude G4 (Calendar round-trip 및 ByteSize 정수 검증)**:
  - `isValidIsoDateTime`에 윤년 및 월별 일수 검증을 추가하여 `2026-02-30T12:00:00Z`, `2026-04-31T12:00:00Z` 등 달력상 불가능한 일시 거부.
  - `regByteSize`는 정수 문자열(`/^\d+$/`)로 엄격 검증하여 소수점(`1.5`)이나 음수 입력 시 서버 요청 전 즉시 클라이언트 거부 및 안내 (시험 14).
- **Codex F5 (ProblemDetails HTTP status 결속)**:
  - `client.ts`의 `isProblemDetails(value, response.status)`를 통해 HTTP status와 body status 불일치 시 fail-closed로 거부 (시험 15).
- **Claude G1 & G5 (서버 kind 어휘 및 ID 접두 일치)**:
  - 픽스처 및 카드를 서버 실재 어휘(`dataset_version`, `deployment`, `code_commit`, `container_image`, `eval_run`, `approval`)와 접두(`mdv_`, `mdl_`, `dsv_`, `dpl_`, `apv_`)로 일치.
  - `countOnlyKinds`/`unresolved`로부터 카드를 동적으로 렌더링하고, 개수 관측 항목("상세 범위 외 (N건 관측)")과 정량 평가 지표(`accuracy`, `f1` -> "NOT_OBSERVED (미관측)")를 명확히 분리. 409 detail을 서버 `model_release.py:326` 문자열 형식으로 일치 (시험 1, 시험 5).
- **Claude G3 (쓰기 3종 abort 및 세대 가드)**:
  - `handleRegisterVersion`, `handleExtendPin`, `handleReleaseModel`에 `writeAbortControllerRef` 및 `writeGenerationRef`를 적용하여 unmount 시 요청 abort 및 늦은 응답 상태 오염 차단 (시험 17).
- **Claude G6 (문서 시각 정합성)**:
  - History 및 작업 현황 문서의 `updated` 시각을 커밋 이전 시각(`2026-09-28T22:38:00+09:00`)으로 정정.
