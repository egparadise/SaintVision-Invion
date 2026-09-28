---
doc_id: "HIST-GEMINI-G05-RELEASE-REEXPOSE-001"
title: "G-05 모델 릴리스 쓰기 UI 재노출 및 서버 멱등성 계약 연동 (카드 118)"
version: "1.0.3"
status: "active"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-29T03:05:00+09:00"
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
   - `npm run contracts:generate`를 통해 최신 schema 주석 동기화 및 `npm run contracts:check` 통과 확인.
5. **되돌리면 실패하는 엄격한 회귀 시험 체계 (`tests/model-registry-business-routes.test.tsx`)**:
   - **Test 4**: `releaseModelVersion` 클라이언트 호출 시 `Idempotency-Key` 헤더 전송 및 200 응답 파싱 검증.
   - **Test 20**: 릴리스 쓰기 UI 재노출 검증 (버튼 활성화, 배너 미노출, Idempotency-Key 헤더 전송, 신규 릴리스 indicator 확인, 성공 후 키 회전 실측).
   - **Test 21**: 릴리스 실패(503 SYS-0001) 재시도 시 동일 Idempotency-Key 보존 및 재현 응답 검증.
   - **Test 22**: `licensePolicy` 또는 `classification` 입력 변경 시 Idempotency-Key 즉시 회전 실측.
   - **Test 23**: `canApprove === false` 또는 `undefined` 시 fail-closed 방어 (버튼 disabled, 안내 문구, 폼 서밋 시 0 network calls, alert 표출).


### 2-1. Claude UI r1 독립 검토 조치 (M1, L1~L3 반영)

1. **M1: `release-replay-indicator` 재시도 응답 정직화**:
   - `ModelLineageView.tsx`에서 `submittedRelKeysRef.current.add(relIdempotencyKey)`의 호출 위치를 `await modelRegistryObservation.releaseModelVersion` **호출 직전(요청 전송 시점)**으로 이동.
   - 1차 시도가 네트워크 단절/오류로 실패한 후 동일한 `relIdempotencyKey`로 재제출하여 200 성공을 받을 때, 클라이언트가 이미 전송 이력이 있는 키임을 감지하여 `relIsReplay = true`로 정확히 전환.
   - 인디케이터 문구를 허위의 '신규 릴리스 완료 (Fresh)' 대신 정직한 `재시도 응답 — 서버 원장 결과 (저장된 응답일 수 있음)`로 표출하도록 수정.
   - **Test 21**: 503 오류 후 동일 키 재시도 시 성공 수신 후 indicator가 '신규 릴리스 완료 (Fresh)'가 아니며 '재시도 응답 — 서버 원장 결과'를 포함함을 단언 (되돌리면 실패).
2. **L1: classification 변경 시 멱등키 회전 시험 추가**:
   - **Test 22**: 배포 분류(`classification`) 셀렉트 값을 `public`으로 변경 시 새 `rel_...` 키로 즉시 회전함을 단언.
3. **L2: `canApprove === undefined` fail-closed 가드 시험 추가**:
   - **Test 23**: `canApprove: undefined`일 때 릴리스 버튼 비활성화 및 안내 문구 표출 검증.
4. **L3: 릴리스 요청 중 입력 변경 시 abort 및 로딩 해제 시험 추가**:
   - **Test 24**: 릴리스 요청 in-flight 상태에서 `licensePolicy` 입력값 변경 시 진행 중인 요청의 signal이 abort되고 버튼 로딩 상태가 즉시 해제되며 지연 응답이 안전하게 폐기됨을 검증.


### 2-2. Codex 계약 축 검토 조치 (C1, C2 반영)

1. **C1: Replay 확정/Fresh 단정 제거 및 재시도 응답 정직화**:
   - `ModelReleaseResponse` 스키마(`additionalProperties: false`, 5개 필드) 및 서버 원장(`model_release.py:479-480, 524-525`) 계약상 반환 바디에 replay 플래그가 없으며 서버는 저장 바디를 그대로 반환함.
   - 키 전송 시점을 네트워크 디스패치 시점으로 옮겨, 동일 키 재제출 200 수신 시 클라이언트가 허위의 '신규 릴리스 완료 (Fresh)' 대신 `재시도 응답 — 서버 원장 결과 (저장된 응답일 수 있음)`로 표출.
   - **Test 21**: 재시도 200 수신 시 indicator가 Fresh가 아니며 '재시도 응답 — 서버 원장 결과'를 포함함을 단언.
2. **C2: `releaseModelVersion` helper 필수 Idempotency-Key 전송 보장**:
   - `modelRegistryObservation.ts`의 `releaseModelVersion`에서 `options?.idempotencyKey`가 생략되더라도 `generateIdempotencyKey('rel')`를 통해 런타임 키를 자동 생성하여 `Idempotency-Key` 헤더가 항상 전송되도록 보장 (`apiClient`에 `idempotencyKey: key` 전달).
   - 호출자가 키 인자를 생략하더라도 서버 `VAL-0003/422` 오류가 발생하지 않도록 fail-closed 계약 완결.
   - **Test 4**: `releaseModelVersion` 호출 시 `options` 인자 생략 시에도 `capturedHeaders['idempotency-key']`가 정의되고 `rel_` 접두사를 가진 비어 있지 않은 헤더가 반드시 전송됨을 단언 (되돌리면 실패).

## 3. 실측 검증 증거

- **단위/통합 테스트 (Vitest)**:
  - `tests/model-registry-business-routes.test.tsx`: **24 passed** (2312ms, 0 failures)
  - 웹 전체: **80 test files / 758 passed** (24.12s, 0 failures)
- **TypeScript 타입 컴파일 & 프로덕션 번들 빌드**:
  - `cd apps/web && npx tsc -b`: **0 errors** (exit 0)
  - `npm run contracts:check`: **31 API response TypeScript types match schemas** (exit 0)
  - `npm run build`: dist/ 번들 생성 성공 (`dist/assets/index-BQ0CZaki.js` 881.08 kB, exit 0)
- **파이썬 라우트 커버리지 게이트**:
  - `pytest tests/test_route_coverage.py`: **40 passed** (2.12s, exit 0)
- **무결성 및 정합성 검사 도구**:
  - `python tools/check_frontend_integrity.py`: 88 files 0 violations (exit 0)
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 bound types PASS (exit 0)
  - `python tools/check_docs.py`: 24 hashes, 933 docs PASS (exit 0)
  - `python tools/sync_obsidian.py --check`: 1780 files, 0 conflicts PASS (exit 0)
