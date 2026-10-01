---
doc_id: "HIST-20261002-CARD192-R3-GEMINI"
title: "2026-10-02 Card 192 Portal Step-Up 재로그인 진입점 r3 조치 보고"
date: "2026-10-02"
version: "1.0.0"
author: "Gemini"
status: "proposed"
updated: "2026-10-02T00:35:00+09:00"
source_of_truth: "Git"
---

# 2026-10-02 Card 192 Portal Step-Up 재로그인 진입점 r3 조치 보고

## 1. 개요 및 배경

- **작업 대상**: Card 192 (PR #289) S12-FE Portal OIDC Step-Up 재로그인 진입점.
- **수신 리뷰**: Claude UI r3 독립 검토(`issuecomment-5934613349`) 조건부 승인(Conditional Approval) 피드백.
- **선행 승인 확인**:
  - r2의 U1~U4(UI stub 누수, 비결정 서명 변조, Login 라우팅 L1/L2 사살, History 정정) 전수 해소 확인.
  - exact-head hosted frontend green (`frontend pass`, `docs pass`, `Portal Container Build pass`) 확인.
  - 서명 변조 8회 반복 시험 8/8 통과 확인.
- **남은 조건**:
  - **V1 (조건)**: `completeLogin()`의 비-boolean marker 거부(`session.ts:658`)를 끄는 변이(M3)가 생존함. 일반 로그인 callback에 문자열·숫자·객체 `isStepUp` marker가 저장된 transaction이 올 때 token endpoint·`/v1/session` fetch 0회와 active token 불변을 단언하는 시험 추가 (M3 사살).
  - **V2 (권장)**: `auth-step-up-ui.test.tsx`의 비동기 클릭 핸들러 대기(`setTimeout(50)`)를 `vi.waitFor()` 조건부 대기로 전면 교체하여 CI 안정성 제고.

---

## 2. 조치 내역 대조표

| 구분 | 검토 지적 사항 | 조치 내용 및 반영 위치 | 검증 결과 |
| :--- | :--- | :--- | :--- |
| **V1 (조건)** | `completeLogin()`의 비-boolean marker 거부를 무력화하는 변이(M3) 생존: `apps/web/tests/auth-step-up-contract.test.ts` 및 `apps/web/tests/auth-login-callback-routing.test.tsx`에 `completeLogin()`의 비-boolean marker 거부 경로 테스트 부재 | 1. `apps/web/tests/auth-step-up-contract.test.ts`: `it.each` 7종 비-boolean marker(`"false"`, `"true"`, `"1"`, `1`, `0`, `{}`, `[]`)에 대해 `completeLogin()`을 직접 호출하여 `로그인 요청 검증에 실패했습니다. 다시 로그인하세요.` 거부, `mockFetch` 0회 호출, `getAuthToken()` 활성 토큰 불변, `storage.size === 0` 단언 추가.<br>2. `apps/web/tests/auth-login-callback-routing.test.tsx`: mock 없이 실제 `completeLogin()`을 구동하는 E2E 테스트 신설. `isStepUp: 'false'` 트랜잭션 유입 시 `Login.tsx`가 에러를 화면에 렌더하고, `clearAuthToken()`으로 토큰을 파기하며, 네트워크 fetch 0회를 단언. | M3 변이 주입 시 `auth-step-up-contract.test.ts` 7건 실패, `auth-login-callback-routing.test.tsx` 1건 실패 → **M3 100% KILLED** |
| **V2 (권장)** | `auth-step-up-ui.test.tsx`에서 비동기 클릭 후 `setTimeout(50)` 고정 대기 사용으로 인한 CI 환경 flakiness 잠재 위험 | `apps/web/tests/auth-step-up-ui.test.tsx`: 임의 타임아웃을 제거하고 `await vi.waitFor(() => expect(assignMock).toHaveBeenCalledTimes(1))` 및 `await vi.waitFor(() => expect(container.textContent).toContain('...'))` 조건부 대기로 전면 교체 | 5/5 PASS, 타이머 의존성 완전 제거 |

---

## 3. 변이 사살 실측 (Mutation Kill Evidence)

### M3 변이 검증 (`session.ts:658` 비-boolean 마커 거부 무력화)
- **주입 코드**:
  ```typescript
  // session.ts:658
  // 원본: if (tx.isStepUp !== undefined && typeof tx.isStepUp !== 'boolean') {
  if (false) { // M3 mutation
  ```
- **사살 결과**:
  1. `apps/web/tests/auth-step-up-contract.test.ts`:
     - `AssertionError: expected "spy" not to be called at all, but was called 1 times` (7건 전수 실패)
     - `Tests: 7 failed | 41 passed (48)` → **KILLED**
  2. `apps/web/tests/auth-login-callback-routing.test.tsx`:
     - `AssertionError: Must NEVER call network endpoints when non-boolean marker is rejected` (fetch 호출 감지)
     - `Tests: 1 failed | 5 passed (6)` → **KILLED**

---

## 4. 로컬 게이트 실측 증거

| 검사 항목 | 실행 명령 | 실측 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| 단위/통합 테스트 | `npm test -- tests/auth-step-up-contract.test.ts tests/auth-step-up-ui.test.tsx tests/auth-login-callback-routing.test.tsx` | **59 passed (59)** | 3개 파일 전원 통과 |
| 서명 변조 결정성 | `npm test -- tests/auth-step-up-contract.test.ts -t "변조"` (8회 반복) | **8/8 PASS** | flakiness 0% |
| 타입스크립트 컴파일 | `npx tsc -b` | **0 errors** (exit code 0) | 타입 체킹 통과 |
| 프로덕션 번들 빌드 | `npm run build` | **built in 8.76s** (exit code 0) | 프로덕션 Vite 번들 정상 생성 |
| 라우트 커버리지 | `pytest tests/test_route_coverage.py` | **41 passed** (exit code 0) | 화면-백엔드 라우트 불변식 100% |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | **0 violations** (exit code 0) | 93개 파일 9대 무결성 규칙 준수 |
| 계약 바인딩 | `python tools/check_contract_bindings.py` | **PASS** (exit code 0) | 55개 픽스처 + 20개 커널 응답 타입 통과 |
| Git 공백 검사 | `git diff --check` | **clean** (exit code 0) | 후행 공백 및 충돌 마커 0건 |
| 봇 호출 태그 | `git diff` 내 `@` 검사 | **0건** | 호출 태그 금지 규칙 준수 |
