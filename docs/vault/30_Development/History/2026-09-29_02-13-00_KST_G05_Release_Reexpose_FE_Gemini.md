---
doc_id: "HIST-GEMINI-G05-RELEASE-REEXPOSE-001"
title: "G-05 모델 릴리스 쓰기 UI 재노출 및 서버 멱등성 계약 연동 (카드 118)"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-29T02:13:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-FE", "G-05", "CARD-118"]
tags: ["s10-fe", "g-05", "card-118", "model-release", "idempotency", "re-exposure", "gemini"]
---

# G-05 모델 릴리스 쓰기 UI 재노출 및 서버 멱등성 계약 연동 (카드 118)

## 1. 개요

- **작업 배경**:
  - PR #219에서 백엔드 release route(`model_release.py`)의 `Idempotency-Key` 미소비로 인해 Codex r4 (F1) 지침에 따라 release 쓰기 UI를 fail-closed로 미노출(`disabled={true}`, 배너 표출) 처리함.
  - Claude PR #229(`agent/claude/release-idempotency`, commit `fa04b9d8` ~ `41fe5c3c`)에서 필수 `Idempotency-Key` 처리, 정본 바디 해시, 동일 키·바디 replay 응답, 다른 바디 409 GRAPH-0002 거부, live canApprove 권한 검증, mirror intent 중복 0 계약이 구현되고 Codex 승인(`236e8219`) 완료됨.
  - 본 카드 118은 PR #229의 서버 멱등성 계약에 맞추어 프런트엔드 릴리스 쓰기 UI를 안전하게 재노출하고 W2/W4와 동일한 멱등키 수명주기 및 replay 응답 정직화 표시를 구현함.
- **기반 브랜치**:
  - base: `agent/claude/release-idempotency` (head `41fe5c3c`).
  - PR #219 (`f23c0423`) 순수 머지 (`70b410f5`)로 최신 프런트엔드 변경사항 통합.
  - 작업 브랜치: `agent/gemini/g05-fe-release-reexpose`.

## 2. 주요 구현 내용

1. **`releaseModelVersion` API 클라이언트 멱등키 복원 (`shared/api/modelRegistryObservation.ts`)**:
   - `ReleaseModelVersionOptions` 인터페이스에 `idempotencyKey?: string` 옵션 복원.
   - 요청 헤더에 `Idempotency-Key`를 1:1로 설정하여 서버 계약 요구사항을 충족.
2. **릴리스 쓰기 UI 재노출 및 멱등키 수명주기 완결 (`features/mlops/ModelLineageView.tsx`)**:
   - 카드 113 대기 배너(`banner-release-pending-idempotency`) 제거 및 릴리스 제출 버튼 활성화 (`canApprove === true`일 때 정상 작동).
   - 권한 부재 시 fail-closed 방어(`canApprove === false` 또는 `undefined` 시 버튼 비활성화 및 폼 서밋 차단).
   - **W2/W4 3단 멱등키 수명주기**:
     - 동일 제출 실패 후 재시도 시: 동일한 `relIdempotencyKey` 보존 (서버 재시도 일관성 보장).
     - 입력값 변경 시 (`relLicensePolicy`, `relClassification`, 또는 모델/버전 변경 시): 새 `rel_...` 키로 즉시 회전하여 이전 요청과 다른 페이로드 충돌(409 GRAPH-0002) 방지.
     - 성공 수신 후: 다음 릴리스 작업을 위해 새 `rel_...` 키로 자동 회전.
3. **Replay 응답 정직화 표시 (Zero Deception)**:
   - 서버 레저에서 기존 키에 의해 재현된 replay 응답을 신규 릴리스 완료인 것처럼 오인하지 않도록 `release-replay-indicator` 배지 추가.
   - 클라이언트 제출 이력 추적(`submittedRelKeysRef`)을 통해 신규 릴리스(`신규 릴리스 완료 (Fresh)`)와 재현 응답(`재생(Replay) 응답: 기존 멱등성 키에 의해 저장된 릴리스 결과입니다.`)을 명확히 구분하여 사용자 및 스크린 리더(`aria-live`)에 안내.
4. **계약 스키마 1:1 일치 (`contracts/model-release-request`, `model-release-response`)**:
   - 요청: `licensePolicy` (1~200자), `classification` (`public | internal | restricted`).
   - 응답: `modelVersionId`, `modelId`, `version`, `stage: 'released'`, `contentSha256`.
5. **되돌리면 실패하는 엄격한 회귀 시험 체계 (`tests/model-registry-business-routes.test.tsx`)**:
   - **Test 4**: `releaseModelVersion` 클라이언트 호출 시 `Idempotency-Key` 헤더 전송 및 200 응답 파싱 검증.
   - **Test 20**: 릴리스 쓰기 UI 재노출 검증 (버튼 활성화, 배너 미노출, Idempotency-Key 헤더 전송, 신규 릴리스 indicator 확인, 성공 후 키 회전 실측).
   - **Test 21**: 릴리스 실패(503 SYS-0001) 재시도 시 동일 Idempotency-Key 보존 및 재현 응답 검증.
   - **Test 22**: `licensePolicy` 또는 `classification` 입력 변경 시 Idempotency-Key 즉시 회전 실측.
   - **Test 23**: `canApprove === false` 또는 `undefined` 시 fail-closed 방어 (버튼 disabled, 안내 문구, 폼 서밋 시 0 network calls, alert 표출).

## 3. 실측 검증 증거

- **단위/통합 테스트 (Vitest)**:
  - `tests/model-registry-business-routes.test.tsx`: **23 passed** (2312ms, 0 failures)
  - 웹 전체: **80 test files / 757 passed** (24.12s, 0 failures)
- **TypeScript 타입 컴파일 & 프로덕션 번들 빌드**:
  - `cd apps/web && npx tsc -b`: **0 errors** (exit 0)
  - `npm run build`: dist/ 번들 생성 성공 (`dist/assets/index-BQ0CZaki.js` 881.08 kB, exit 0)
- **파이썬 라우트 커버리지 게이트**:
  - `pytest tests/test_route_coverage.py`: **40 passed** (2.12s, exit 0)
- **무결성 및 정합성 검사 도구**:
  - `python tools/check_frontend_integrity.py`: 88 files 0 violations (exit 0)
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 bound types PASS (exit 0)
  - `python tools/check_docs.py`: 24 hashes, 933 docs PASS (exit 0)
  - `python tools/sync_obsidian.py --check`: 1780 files, 0 conflicts PASS (exit 0)
