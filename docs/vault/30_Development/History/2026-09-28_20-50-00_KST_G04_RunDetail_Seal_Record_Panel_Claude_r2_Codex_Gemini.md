---
doc_id: "HIST-G04-002"
title: "2026-09-28 20:50:00 KST G-04 RunDetail 봉인 기록 패널 Claude UI r2 및 Codex 계약 축 검토 조치 완결 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T20:50:00+09:00"
source_of_truth: "Git"
---

# G-04 RunDetail 봉인 기록 패널 Claude UI r2 및 Codex 계약 축 검토 조치 완결 보고

## 1. 개요 및 배경
- PR #212 (`ef61133c`) 독립 검토 결과:
  - Claude UI·시험 축: 수정 요청 (F1~F9, 변이 4종 생존)
  - Codex 계약 축: 수정 요청 (F-R1~F-R4)
- 후행 브랜치 #188의 라우트 계측 충돌 해소 커밋(`5c34aaca`)을 선행 병합(`e1d593ce`)하고, UI 및 계약 지적 13개 항목을 전수 조치함.

---

## 2. 조치 내역

### 1) F1 [High, 병합 차단]: 백엔드 CI 실패 해소 (#188 선행 병합)
- #188 head `5c34aaca` ("test(run-records): count registered routes by (path, method), not by path")를 `agent/gemini/g04-fe-seal-record`에 순차 병합 (`e1d593ce`).
- 동일 경로에 POST를 등록하는 #201(W1)과의 중복 카운트 충돌 해소.
- 로컬 `pytest tests/core/test_run_record_artifacts_route.py tests/test_route_coverage.py` 실측: **88 passed** (exit 0).

### 2) F2 & F-R3 [High, 정직성]: R2 페이지 개수 및 `nextCursor` 페이지네이션 구현
- 스키마 정의(`count` = page 크기)에 따라 `SealRecordPanel.tsx` 문구를 "이 페이지 {count}건"으로 정정.
- `nextCursor` 존재 시 "(추가 항목 있음)" 배지 및 "다음 페이지 (더보기)" 버튼 렌더링 (`handleLoadNextPage`).
- 다음 페이지 호출 시 `cursor` 쿼리 파라미터 전달 및 결과 병합 확인.
- 시험 10 신설: `nextCursor` 전달, "총 N개" 부재, 다음 페이지 버튼 동작 단언.

### 3) F3 & F-R2 [High, 정직성]: R2/R3 오류 보존 및 무결성 사실 표출
- `Promise.allSettled` 실패 시 결과를 버리지 않고 섹션별 상태(`artifactsError`, `bundleError`, `bundleSpecialStatus`)로 보존:
  - R2 실패 시: `seal-artifacts-error` 배너 표출 및 라이브 리전에 "아티팩트 조회 실패" 공지 (가짜 "0건" 배제).
  - R3 409 `GRAPH-0002`: `seal-bundle-reproduction-failed` 배지("번들 재현 불가 (Snapshot Missing / GRAPH-0002)", `data-tone="mismatch"`) 표출 및 라이브 리전에 "번들 재현불가" 공지 (가짜 "번들 없음" 배제).
  - R3 404 + "No context bundle": "컨텍스트 번들 없음" 사실 표출.
  - 미봉인 경로에서도 에러 상태 정직 분리.
- 시험 11, 12, 13 추가로 각각 검증.

### 4) F4 [Medium, 정직성]: R1 404 "No such run." 분리
- `status === 404 && code === 'RES-0004' && detail === 'No sealed record for this run.'`인 경우에만 '미봉인'으로 판정.
- detail이 `'No such run.'` 등 다른 경우 일반 404 리소스 에러 배너로 분리.
- 시험 6 신설: `No such run.` 픽스처에서 미봉인 배지 부재 및 에러 배너 표출 단언.

### 5) F5 & F-R1 [High, 시험 실재성 & 계약]: 401 및 502 실제 fetch 경로 검증
- `apps/web/src/shared/api/client.ts`의 `isProblemDetails` 가드에 legacy 401 `AUTH-MISSING-CREDENTIAL` 예외 처리(optional `instance` key 및 legacy type `https://saintvision.invenio/problems/auth-missing-credential` 허용)를 정밀 추가하여 `NET-0401` 강등 없이 원형 보존.
- `cleanErrorMessage`에서 HTML 502/504 에러를 정제하여 태그 누출을 원천 차단하고 한국어 폴백 메시지 표출.
- 시험 8, 9에서 `globalThis.fetch` 스파이를 통해 실제 `apiClient` 파이프라인 전수 통과 실측.

### 6) F6 [Medium, 오래된 데이터 방어]: AbortSignal 및 세대 관리
- 비동기 전 구간에 `if (signal.aborted) return;` 가드 배치.
- Run ID 전환 시 이전 컨트롤러 즉시 abort 및 모든 섹션 상태 초기화.
- 검증 요청에 `generationRef` 연동하여 지연 응답에 의한 상태 오염 차단.
- 시험 15 신설: 비동기 지연 상태에서 Run B 전환 시 Run A 미봉인 공지 누출 차단 단언.

### 7) F7 [Low, 변이 사살]: 정직성 변이 전수 사살
- `verified: false` 배지에 `data-tone="mismatch"`, 색상 `#ff7b72` 단언 추가 (녹색 `#3fb950` 변이 사살).
- `hashVerified: false` 배지에 `data-tone="mismatch"`, 색상 `#ff7b72` 단언 추가 및 한글 regex `/✔|해시 일치 \(/` 무력화 버그 정정.
- Run 전환 시 이전 번들/아티팩트 잔존 차단 단언 (시험 14).

### 8) F8 & F-R4 [Medium, 정직성 & 계약]: 문구 정합 및 RFC 3339 날짜 검증
- 불일치 문구를 사실에 맞게 "⚠️ 불일치 (봉인 다이제스트와 다름·대상 없음)"으로 정합.
- `evidenceId`, `tokenEstimate`, `objectVersion`, `nextCursor` 실제 렌더링 구현.
- `runSealObservation.ts`에 `isValidIsoDateTime` 엄격 검증 함수를 도입하여 윤년·월별 일수·시분초·타임존 검증 (시험 18에서 `2026-02-30T12:00:00Z` 거부 실단언).

### 9) F9 [Low, 픽스처 정합]: 식별자 및 모델 규격화
- 번들 ID `bnd_` 접두사, 아티팩트 ID `art_` + 26자리 Crockford ULID 정합.
- `sampleRun`에서 `RunItem` 타입 외 필드(`status`, `targetNodeId`, `startedAt`) 제거.

---

## 3. 검증 실측 결과
- **Vitest**:
  - `tests/run-detail-seal-record.test.tsx`: **18 passed** in 351ms (전체 18건 전수 녹색).
  - Web 전체 스위트: **79 test files passed (79), 693 passed (693)** in 21.74s.
- **TypeScript & Build**:
  - `npx tsc -b`: 0 errors (exit 0).
  - `npm run build`: dist/ 번들 생성 성공 (9.02s, exit 0).
- **파이썬 게이트**:
  - `pytest tests/test_route_coverage.py tests/core/test_run_record_artifacts_route.py`: **88 passed** in 16.97s (exit 0).
  - `python tools/check_frontend_integrity.py`: 85 files 0 violations (PASS, exit 0).
  - `python tools/check_contract_bindings.py`: 55 fixtures / 20 types PASS (exit 0).
  - `python tools/check_docs.py`: 911 versioned documents PASS (exit 0).
  - `python tools/sync_obsidian.py --check`: 0 conflicts PASS (exit 0).
