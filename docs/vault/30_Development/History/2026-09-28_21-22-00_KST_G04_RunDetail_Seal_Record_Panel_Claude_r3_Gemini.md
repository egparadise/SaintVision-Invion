---
doc_id: "HIST-G04-003"
title: "2026-09-28 21:22:00 KST G-04 RunDetail 봉인 기록 패널 Claude UI r2 재검토(G1~G5, O3, O4) 완결 조치 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T21:22:00+09:00"
source_of_truth: "Git"
---

# G-04 RunDetail 봉인 기록 패널 Claude UI r2 재검토 완결 보고

## 1. 개요 및 배경
- PR #212 (`1511a5b8`) Claude UI·시험 축 r2 재검토 결과:
  - F1·F2·F4·F9 해소, CI 전 레인 통과 확인
  - 잔여 요청 3건(G1, G2, G3) 및 권고 항목(G4, G5, O3, O4) 조치 요청
- 미봉인 R3 오류 표출 가드 완화, 다음 페이지 요청 세대 가드 도입, 공용 ProblemDetails 계약 엄격 복원 및 변이 사살 시험을 완결함.

---

## 2. 조치 내역

### 1) G1 [중간, 정직성]: 미봉인 경로 R3 401/403/409/5xx 화면 표출
- `SealRecordPanel.tsx`의 번들 섹션 렌더링 조건을 `(!isUnsealed ? (contextBundle || bundleError || bundleSpecialStatus) : (contextBundle || bundleError || bundleSpecialStatus === 'reproduction_failed'))`로 정정.
- 미봉인 실행이라도 409 `GRAPH-0002` 발생 시 `seal-bundle-reproduction-failed` 배지("번들 재현 불가", `data-tone="mismatch"`)를 표출하고, 500 오류 시 `seal-bundle-error` 배너를 표출.
- 라이브 리전에도 미봉인 상태 뒤에 `, 번들 재현불가` 또는 `, 번들 조회 실패` 안내를 정직하게 부가.
- 시험 19(미봉인 + 409) 및 시험 20(미봉인 + 500) 신설.

### 2) G2 [중간, 오래된 데이터 방어]: `handleLoadNextPage` 세대 및 Run ID 가드
- `handleLoadNextPage`에 `const currentGen = generationRef.current; const reqRunId = runId;`를 캡처하고, 응답 수신 및 에러/finally 전 구간에서 `generationRef.current !== currentGen || runId !== reqRunId` 여부를 검사.
- Run A에서 다음 페이지 요청 중 Run B로 전환 시 늦은 A의 2쪽 응답이 Run B의 아티팩트 목록 및 라이브 리전을 덮어쓰지 않도록 차단.
- 시험 21 신설: 지연된 2쪽 응답 상황에서 실행 전환 시 Run B의 아티팩트 목록 격리 단언.

### 3) G3 [중간, 계약 엄격성]: `isProblemDetails` 11키 legacy 수용 및 canonical 필수성 복원
- `client.ts`의 `isProblemDetails` 가드에서 `causeRef`와 `evidenceId`의 `undefined` 허용을 제거하고, 정본 스키마에 따라 null 또는 규격 문자열로 엄격 복원(missing 시 canonical 판정 불가 및 `NET-0404` 강등).
- `to_problem` 정본에 맞추어 `category: string`, `retryable: boolean`, `traceId: string(32 hex)` 필수성 유지.
- legacy 401 예외는 `type`, `code`, `instance` 3종으로 국소 한정.
- 시험 8 픽스처를 실제 11키 본문으로 정합화하고, 시험 24에서 `causeRef`가 누락된 404 응답의 `NET-0404` 강등 거부를 실단언.

### 4) G4 [낮음, 픽스처 정합]: 오류 문자열 및 모의 분기 순서 교정
- 409 GRAPH-0002 detail을 서버 정본 문자열(`"A bundle item's snapshot is missing; the bundle cannot be reproduced."`)로 교정하고 휴리스틱을 정합화.
- 시험 11의 R2 오류 코드를 `SYS-0002`(500)로 교정.
- 시험 15의 mock URL 검사에서 `/run_B/record/artifacts`를 `/run_B/record`보다 앞에 배치하여 도달 불가 분기 해소.

### 5) G5 [낮음, 문서 정합]: 서술 정정
- 다음 페이지 동작을 "현재 페이지 교체(`setArtifactsPage`, 이 페이지 {count}건 갱신)"로 명시.
- check_docs 문서 수(912건 -> 신규 생성 후 913건) 정합.

### 6) O3, O4 [권고, 접근성 및 테이블 복원]:
- R3 번들 항목 표에 `순번`(ordinal), `비식별화`([비식별화] 배지), `신뢰도`(confidence) 열을 복원.
- `cleanErrorMessage`의 게이트웨이 정제 조건을 `status === 502 || status === 504` 및 HTML 태그/Gateway 키워드로 명확히 한정.

### 7) 변이 사살 시험 보강:
- 시험 22: 비동기 검증 요청 대기 중 실행 전환 시 이전 실행 검증 결과의 상태 누출 차단(세대 가드 사살).
- 시험 23: 실행 전환 시 `setArtifactsPage(null)` 누락 시 이전 아티팩트 잔존 차단(초기화 가드 사살).

---

## 3. 로컬 실측 검증
- **Vitest**:
  - `tests/run-detail-seal-record.test.tsx`: **24 passed** in 496ms (전체 24건 전수 녹색).
  - Web 전체 스위트: **79 test files passed (79), 699 passed (699)** in 21.71s.
- **TypeScript & Build**:
  - `npx tsc -b`: 0 errors.
  - `npm run build`: dist/ 번들 생성 성공 (7.14s).
  - `npm run contracts:check`: PASS (20 API response TypeScript types match).
- **파이썬 게이트**:
  - `pytest tests/test_route_coverage.py tests/core/test_run_record_artifacts_route.py`: **88 passed** in 18.30s.
  - `python -X utf8 tools/check_frontend_integrity.py`: 85 files, 0 violations (PASS).
  - `python -X utf8 tools/check_contract_bindings.py`: 55 fixtures / 20 types PASS.
  - `python -X utf8 tools/check_docs.py`: 913 versioned documents PASS.
  - `python -X utf8 tools/sync_obsidian.py --check`: 0 conflicts PASS.
