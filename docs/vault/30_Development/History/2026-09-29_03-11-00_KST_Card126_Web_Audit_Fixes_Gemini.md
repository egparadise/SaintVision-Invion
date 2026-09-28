---
doc_id: "HIST-GEMINI-CARD126-001"
title: "Card 126 apps/web 전역 감사 지적사항(F1~F7) 시정 보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
date: "2026-09-29T03:11:00+09:00"
updated: "2026-09-29T03:11:00+09:00"
source_of_truth: "Git"
---

# Card 126 apps/web 전역 감사 지적사항(F1~F7) 시정 보고

- **작업 브랜치**: `agent/gemini/card126-audit-fixes` (worktree: `.worktrees/gemini-card126-audit-fixes`)
- **Base Commit**: `f23c0423` (PR #219 head)
- **담당 및 역할**: Gemini (Frontend / UI / 무결성 소유). Reviewer: Claude (감사자 및 UI 축), Codex (계약 축).
- **관련 PR/감사**: Claude 전역 감사 PR #235 (`apps/web` 7건 체계적 결함 지적)

---

## 1. 개요 및 목적

Claude의 전역 감사 PR #235(착지 후보 `b91ab72f`)에서 도출된 `apps/web` 영역의 체계적 결함 7건(F1~F7: 허위 SLO 7축 조작, 멱등키 미캐싱/미보존, 폼 리셋 시 잔류 상태, 가짜 용량 계산식, 형식불가 RFC 9457 코드, 부정확한 에러 헬퍼 독스트링)을 전수 시정하고, 엄격한 회귀 방지 시험을 배치하여 무결성을 확립한다.

---

## 2. 세부 조치 내역 (F1 ~ F7)

### F1 [High] `releaseEngine.ts` 서버 미제공 SLO 7축 허위 met 제거 및 NOT_OBSERVED 처리
- **현상**: 서버가 제공하지 않는 SLO 7축(p95, p99, errorRate, availability, throughput, cpuUtilization, memoryUtilization)을 하드코딩하여 전부 `met`로 반환하고 `tests/release-candidate.test.ts`가 이를 단언하고 있었음.
- **조치**:
  - `apps/web/src/features/release/releaseEngine.ts`: 실제 텔레메트리(`telemetry`)가 인자로 제공되지 않으면 `unmeasured`(`status: 'unmeasured'`) 및 `observedValue: null`을 반환하도록 전면 개정.
  - `apps/web/src/features/release/ReleaseCandidateView.tsx`: `unmeasured` 상태에 대해 `badge-warning` 및 `미측정 (NOT_OBSERVED)` 레이블을 표출.
  - `tests/release-candidate.test.ts`: 기존 허위 `met` 단언을 뒤집어 텔레메트리 부재 시 `unmeasured` 반환을 단언하고, 실제 텔레메트리 공급 시에만 계산된 평가 결과를 반환함을 입증.
  - `tests/browser-matrix-acceptance.test.tsx`: 텔레메트리 부재 시 `unmeasured` 단언 및 텔레메트리 전달 시의 `computeSloRecords` 검증으로 갱신.

### F2 [High] `kernelMutations.ts` 승인 결정 및 Run 취소 멱등키 캐싱 보장
- **현상**: `decideApproval` 및 `cancelKernelRun`이 매 호출마다 신규 `Idempotency-Key`를 자동 생성하여, 네트워크 실패 후 동일 의도로 재시도할 때 새 키가 나가 서버 409나 중복 처리 위험이 존재했음.
- **조치**:
  - `apps/web/src/shared/api/kernelMutations.ts`: 인자별 페이로드 해시/키를 기반으로 멱등키 캐시(`idempotencyKeyCache`)를 도입.
  - 호출자가 명시적인 `idempotencyKey`를 전달하면 이를 우선 사용하고, 생략된 경우 동일한 `(runId/approvalId + action/reason)` 재시도 시 캐시된 동일 키를 재사용. 다른 파라미터로 호출 시에만 새 키 생성.
  - `tests/kernel-mutations.test.ts`: 실패 재시도 시 동일 키 재사용 및 파라미터 변경 시 새 키 발행을 실측하는 회귀 시험 추가.

### F3 [Med-High] `ResourceExplorer.tsx` 및 `fabricControlApi.ts` 스토리지 기여 멱등키 보존
- **현상**: 스토리지 기여(`contributeStorage`) 재시도 시 이전 멱등키를 보존하지 않아 재시도 충돌 위험.
- **조치**:
  - `apps/web/src/features/desktop/fabricControlApi.ts`: `contributeStorage` 옵션에 `idempotencyKey?: string` 지원 추가.
  - `apps/web/src/features/desktop/ResourceExplorer.tsx`: `storageContributionKey` 상태를 관리하여 실패 후 동일 파라미터 재시도 시 동일 키 보존, 용량 입력값 변경 시 새 UUID v4로 회전, 성공 수신 후 새 키로 회전.
  - `tests/resource-explorer-dom.test.tsx`: 동일 실패 재시도 시 동일 멱등키 전송 및 입력값 변경 시 키 회전 실측.

### F4 [Med-High] `ModelStudioView.tsx` `clear()` 시 `repairState` 잔류 해소
- **현상**: 모델 스튜디오 폼 초기화(`clear()`) 호출 시 `repairState`가 초기화되지 않고 남아있어 다음 작업에 오염 유발.
- **조치**:
  - `apps/web/src/features/desktop/ModelStudioView.tsx`: `clear()` 메서드 내에서 `setRepairState(null)`을 호출하도록 보강.
  - `tests/model-studio-dom.test.tsx`: `clear()` 실행 시 `repairState`가 null로 정상 리셋됨을 검증하는 단언 추가.

### F5 [Med] `ResourceExplorer.tsx` 허위 `- 50` 가짜 여유 용량 계산식 제거 및 null 허용
- **현상**: 여유 용량 계산 시 `totalCapacity - 50`과 같은 근거 없는 하드코딩 수식을 적용하고 있었음.
- **조치**:
  - `apps/web/src/features/desktop/ResourceExplorer.tsx`: 허위 `- 50` 수식을 전면 제거하고 서버 원천값이 없을 경우 `availableBytes: null`을 명시적으로 전달 및 허용.
  - `apps/web/src/contracts/types.ts`: `availableBytes`에 `null` 타입 허용.
  - `tests/resource-explorer-dom.test.tsx`: 허위 수식 제거 및 null 안전성 검증.

### F6 [Med] 형식불가 RFC 9457 ProblemDetails 코드 8건 정정 및 무결성 시험 신설
- **현상**: 목 응답 및 테스트 픽스처에서 정규식 `/^[A-Z]+-[0-9]{4}$/` 형식을 위반하는 잘못된 코드(`RES-0004`, `AUTH-0030`, `NET-0500`, `NET-0401`, `NET-0403`, `SYS-0002` 등 3자리 숫자나 잘못된 코드) 사용.
- **조치**:
  - `apps/web/tests/developer-studio.test.ts`, `apps/web/tests/developer-studio-dom.test.tsx`, `apps/web/tests/alert-elimination-and-unimplemented-audit.test.tsx`, `apps/web/tests/node-journey.test.ts`, `apps/web/tests/late-mutation-generation-regression.test.tsx`: 형식 위반 코드 8건을 표준 4자리 접미사 코드로 정정.
  - `apps/web/tests/fixture-problem-codes-integrity.test.ts` 신설: 모든 테스트 픽스처 및 소스 내 RFC 9457 problem code가 `/^[A-Z]+-[0-9]{4}$/` 표준 패턴을 엄격히 준수함을 검증하는 전수 회귀 시험 추가.

### F7 [Low] `isRouteNotFoundError` fail-closed 헬퍼 정리 및 독스트링 정정
- **현상**: `apps/web/src/shared/api/client.ts`의 `isRouteNotFoundError` 헬퍼 함수가 부정확한 폴백 주석 및 복잡성을 가지고 있었음.
- **조치**:
  - `apps/web/src/shared/api/client.ts`: 404 상태 코드 및 RFC 9457 `RES-0004` (또는 `RES-0001`) ProblemDetails 구조를 fail-closed로 정확하게 판별하도록 간결화하고, 실제 라우트 부재 에러 판별 의미에 맞게 독스트링 정정.

---

## 3. 실측 검증 증거

- **단위/통합 테스트 (Vitest)**:
  - 전체 실행: **81 test files / 758 passed** (28.33s, 0 failures)
  - `fixture-problem-codes-integrity.test.ts`: **1 passed** (전체 픽스처 RFC 9457 규격 검증)
  - `release-candidate.test.ts`: **7 passed**
  - `kernel-mutations.test.ts`: **14 passed**
  - `resource-explorer-dom.test.tsx`: **27 passed**
  - `model-studio-dom.test.tsx`: **13 passed**
- **TypeScript 타입 컴파일 & 프로덕션 번들 빌드**:
  - `cd apps/web && npx tsc -b`: **0 errors** (exit 0)
  - `npm run contracts:check`: **28 API response TypeScript types match JSON schemas** (exit 0)
  - `npm run build`: dist/ 번들 생성 성공 (`dist/assets/index-8N-yiuFR.js` 874.31 kB, exit 0)
- **파이썬 라우트 커버리지 게이트**:
  - `pytest tests/test_route_coverage.py`: **40 passed** (1.94s, exit 0)
- **무결성 및 정합성 검사 도구**:
  - `python -X utf8 tools/check_frontend_integrity.py`: 88 files 0 violations (exit 0)
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 bound types PASS (exit 0)
  - `python tools/check_docs.py`: 24 hashes, 919 docs PASS (exit 0)
  - `python tools/sync_obsidian.py --check`: 1762 files, 0 conflicts PASS (exit 0)
