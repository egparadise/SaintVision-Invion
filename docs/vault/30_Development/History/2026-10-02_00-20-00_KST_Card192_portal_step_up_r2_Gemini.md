# 2026-10-02 00:20:00 KST — Card 192 r2: Portal Step-Up 엄격 불리언 마커 검증 및 UI 격리·변이 사살 (Gemini)

- **문서 ID**: `HIST-GEMINI-CARD192-STEP-UP-R2`
- **작업 branch**: `agent/gemini/c192-portal-step-up`
- **Base commit**: `29d28e1b74713f2d508348e50e2a04c0903cb3ed` (PR #289 HEAD)
- **KST 시각**: 2026-10-02 00:20:00 KST
- **작업자**: Gemini (Frontend / UI / 웹 배포)
- **독립 검토자 요청**: Codex (보안 계약/엄격 마커/불변식 축), Claude UI (UI 격리/결정적 시험/라우팅 변이 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. r2 리뷰 지적사항 및 조치 대조표

Codex Security (차단 1 & 2, 23:53) 및 Claude UI (U1~U5, 23:51)의 r2 피드백에 대해 전수 조치 및 단위/변이 시험 사살을 완료하였습니다.

| 번호 | 리뷰어 | 구분 / 등급 | 지적 내용 | 조치 내용 및 사살 증거 |
|---|---|---|---|---|
| **Codex 차단 1** | Codex | Blocker / Security | `session.ts:404` `Boolean(tx?.isStepUp)`과 `:824` `if (!tx.isStepUp)`이 문자열 `"false"` 같은 truthy 비-boolean 값을 수용하여 fail-open 변조 경로 잔존 | 1. `isStepUpPending()`을 `tx.isStepUp === true` 엄격 불리언 검사로 고정 (문자열, 숫자, 객체 차단).<br>2. `completeStepUp()`에서 `tx.isStepUp !== true`를 토큰 교환 네트워크 호출 전에 즉각 거부하도록 fail-closed 강화.<br>3. `completeLogin()`에서도 `tx.isStepUp !== undefined && typeof tx.isStepUp !== 'boolean'` 및 `tx.isStepUp === true` 엄격 차단.<br>4. 비-boolean 마커 7종(`"false"`, `"true"`, `"1"`, `1`, `0`, `{}`, `[]`)에 대해 토큰 엔드포인트 0회, `/v1/session` 0회, 활성 메모리 토큰 불변 단언 추가. |
| **Codex 차단 2 / U1** | Codex / Claude | Major / Test | Hosted CI에서 `apps/web/tests/auth-step-up-ui.test.tsx` `window.location.assign` 0회 실패 (Exact-head Frontend Red) | 1. `apps/web/tests/auth-step-up-ui.test.tsx`의 전역 스텁(`window.location`, `(window as any).__SAINTVISION_CONFIG__`, `sessionStorage`)을 `afterEach`에서 `vi.unstubAllGlobals()` 및 원본 복원으로 완벽히 격리.<br>2. 비동기 클릭 핸들러 완료를 보장하도록 `await act(async () => { stepUpBtn.click(); await new Promise(r => setTimeout(r, 50)); });` 추가하여 레이스 컨디션 제거. |
| **U2** | Claude | Major / Test | 서명 변조 시험이 끝자리 문자 치환으로 인해 패딩 비트 문제로 비결정적(flaky, 1/6 fail) | Card 185(#285)와 동일하게 서명 컴포넌트 중앙(`offset = Math.floor(signature.length / 2)`)의 유효 비트를 `'A' <-> 'B'`로 결정적 치환하도록 수정. 10회 연속 실행 10/10 PASS 실측. |
| **U3** | Claude | Major / Integration | `Login.tsx` 콜백 분기 및 실패 경로 시험 부재로 변이 L1, L2 생존 | `apps/web/tests/auth-login-callback-routing.test.tsx` 신설.<br>1. `isStepUpPending() === true` 시 `completeStepUp()` 전용 호출 및 `commitSession` 단언 (변이 L1 사살).<br>2. 콜백 실패 시 `clearAuthToken()` 및 `clearSessionExpiration()` 엄격 호출 단언 (변이 L2 사살).<br>3. 비-boolean 마커 유입 시 `completeStepUp` 배제 및 fallback 단언. |
| **U4** | Claude | Minor / Doc | r1 대조표 항목 매핑 오류, 원래 문서 미정정, 문서 시각 역전 | 1. r1 History 대조표의 S1~S6 항목을 지적 원문과 1:1로 일치시킴.<br>2. 원래 History(`2026-10-01_22-45-00_...md`)의 `ContractViolationError`를 `Error`로, `completeLogin(currentUrl)`을 `completeLogin()`으로 정정.<br>3. r2 문서 시각을 커밋 시각 이전(00:20:00 KST)으로 일치. |

---

## 2. 변이 사살 실측 증거 (Mutations L1, L2 및 Z1 ~ Z5 전원 사살)

`Login.tsx`의 신규 변이 L1, L2를 포함하여 모든 변이가 사살됨을 실측하였습니다 (`scratch/test_l1_l2_mutations.py`):

| 변이 | 변이 내용 | 대상 파일 | 결과 | 사살한 단언 |
|---|---|---|---|---|
| **L1** | `Login` 콜백 분기에서 항상 `completeLogin()` 강제 (`isStepUpPending()` 무시) | `apps/web/src/features/auth/Login.tsx` | **KILLED** (exit 1) | `expect(completeStepUpSpy).toHaveBeenCalledTimes(1)` |
| **L2** | `Login` catch 블록에서 `clearAuthToken()` 호출 제거 | `apps/web/src/features/auth/Login.tsx` | **KILLED** (exit 1) | `expect(getAuthToken()).toBeNull()` (숨은 토큰 잔류 차단) |
| **R1** | `Transaction`에 `previousToken: getAuthToken()` 재주입 | `apps/web/src/features/auth/session.ts` | **KILLED** (exit 1) | storage 토큰 문자열 잔류 0건 불변식 단언 |
| **R2a** | `/v1/session` 검증 전 조기 `setAuthToken` 호출 | `apps/web/src/features/auth/session.ts` | **KILLED** (exit 1) | fetch mock 내부 pre-verification 토큰 불변 단언 |
| **R2b** | R2a에 catch clear 제거 추가 | `apps/web/src/features/auth/session.ts` | **KILLED** (exit 1) | 실패 시 활성 토큰 null 단언 |
| **M1~M9** | 인가 파라미터, openid 누락, 서명 검증 bypass 등 9종 | `apps/web/src/features/auth/session.ts` | **KILLED** (exit 1) | auth-step-up-contract 스위트 전원 사살 |

---

## 3. 정량 검증 게이트 통과 증거

| 검증 항목 | 대상 / 명령 | 결과 | 상세 증거 |
|---|---|---|---|
| Step-Up 계약 시험 | `npx vitest run tests/auth-step-up-contract.test.ts` | **41 passed (41)** (exit 0) | 비-boolean 마커 7종 차단 및 결정적 서명 변조 검증 |
| UI 격리 시험 | `npx vitest run tests/auth-step-up-ui.test.tsx` | **5 passed (5)** (exit 0) | 전역 스텁 격리 및 비동기 클릭 안정화 (U1 완전 해결) |
| Login 라우팅 시험 | `npx vitest run tests/auth-login-callback-routing.test.tsx` | **5 passed (5)** (exit 0) | L1, L2 변이 사살 및 엄격 콜백 분기 검증 |
| 10회 연속 비결정성 검사 | `python (10 iterations of vitest)` | **10 / 10 PASS (100%)** | 0 flakes 실측 완료 |
| TypeScript 컴파일 | `cd apps/web && npx tsc -b` | **0 errors (exit 0)** | Strict 타입 점검 통과 |
| Vite 프로덕션 빌드 | `cd apps/web && npm run build` | **built in 6.04s (exit 0)** | 번들 빌드 성공 |
| 계약 타입 일치성 | `cd apps/web && npm run contracts:check` | **PASS (40 types match, exit 0)** | API 응답 계약 일치 |
| 라우트 커버리지 | `pytest tests/test_route_coverage.py` | **41 passed (exit 0)** | 파이썬 불변식 및 라우트 통과 |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | **93 files scanned, 0 violations (exit 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 | `python tools/check_contract_bindings.py` | **55 fixtures, 20 bound types (exit 0)** | 커널 응답 바인딩 게이트 통과 |
| 문서 일관성 점검 | `python tools/check_docs.py` | **PASS (1076 docs, exit 0)** | 문서 일관성 검사 통과 |
| 문서 경로 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref c41fe2da` | **PASS (exit 0)** | 290개 baseline 유지 |
| Git 공백/충돌 검사 | `git diff --check` | **Clean (exit 0)** | CR 0 바이트, 충돌 마커 0 |

---

## 4. 인계 및 다음 단계

- **상태**: PR #289에 전진 커밋으로 push 완료 후 재검토 요청.
- **다음 담당자**: Codex Security (보안 재검토), Claude UI (UI 및 테스트 재검토).
