# 2026-10-01 22:45:00 KST — Card 192: Portal Step-Up 재로그인 진입점 및 OIDC PKCE 인증 흐름 결속 (Gemini)

- **문서 ID**: `HIST-GEMINI-CARD192-STEP-UP`
- **작업 branch**: `agent/gemini/c192-portal-step-up`
- **Base commit**: `6b2a378675aaffa78df57dc1070f17c0db240ff4` (PR #285 / Card 188 HEAD)
- **KST 시각**: 2026-10-01 22:45:00 KST
- **작업자**: Gemini (Frontend / UI / 웹 배포)
- **독립 검토자 요청**: Claude (UI/인증 흐름/테스트 축), Codex (보안 계약/토큰 보존/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 인계 배경

- **인계 기원**: PR #285 (Card 188, head `6b2a3786`)에서 Codex가 fresh-auth claim 공급원을 완성하고 portal step-up 재인증 진입점을 Gemini 영역으로 공식 인계 (`History 2026-10-01_21-10-00_KST_Card188_fresh_auth_claim_공급원_Codex.md:71-72`).
- **정본 계약**: `contracts/fresh-authentication-step-up-request.schema.json` (`FreshAuthenticationStepUpRequest`):
  - exact `prompt: "login"`
  - exact `max_age: 300`
  - `additionalProperties: false`
  - `required: ["prompt", "max_age"]`
- **핵심 원칙**:
  1. 기존 OIDC PKCE 인증 흐름(`apps/web/src/features/auth/session.ts`)에 step-up 진입 함수를 추가: authorize 요청에 정확히 `prompt=login&max_age=300`을 부여하고, 매 요청마다 PKCE `code_verifier`, `code_challenge`, `state`, `nonce`를 새로 생성·보존.
  2. callback 완료 후 검증 성공 시에만 새 token으로 교체하고, 사용자 취소·IdP 에러·네트워크 장애·state 불일치 등 실패 시 **이전 활성 토큰을 무조건 온전히 보존(rollbackPreviousToken)**하며, 서명 성공이나 수락을 절대 합성하지 않음.
  3. 백엔드 쓰기 라우트 미개방(`INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false`) 상태를 존중하여 UI는 "재인증 필요" 안내 및 step-up 로그인 유도 버튼으로 한정하고, 임의 쓰기/수락 제출 UI는 원천 배제.

---

## 2. 변경 세부 내용

### 1) 계약 스키마 타입 생성 및 자동 검증 등록 (`apps/web/scripts/api-response-contracts.mjs`)
- `fresh-authentication-step-up-request`를 계약 매핑 테이블에 추가.
- `apps/web/src/contracts/fresh-authentication-step-up-request.ts` 생성.
- `node apps/web/scripts/api-response-contracts.mjs --check` 실행: 41개 API 응답 TypeScript 타입 100% 일치 검증 통과 (exit 0).

### 2) OIDC PKCE Step-Up 인증 세션 구현 (`apps/web/src/features/auth/session.ts`)
- `Transaction` 인터페이스 확장: `isStepUp?: boolean`, `previousToken?: string | null`, `returnUrl?: string` 필드 추가.
- `validateStepUpRequest(req)`:
  - `prompt === 'login'`, `max_age === 300`을 엄격히 검증.
  - 객체가 아니거나 잉여 속성(`additionalProperties`)이 존재할 시 `ContractViolationError` 발생.
- `beginStepUp(options)`:
  - 기존 세션의 `getAuthToken()`을 `previousToken`으로 포획.
  - 신규 `code_verifier`, `code_challenge` (S256), `state`, `nonce`를 암호학적으로 생성.
  - `prompt=login&max_age=300`을 authorize 쿼리 파라미터에 엄격히 결속하며, 인가 엔드포인트 URL을 반환.
  - `sessionStorage`에 step-up 트랜잭션 안전 보존.
- `completeLogin(currentUrl)` / `completeStepUp(currentUrl)`:
  - callback 처리 실패 시(`access_denied`, network error, state mismatch, token parse error, `/v1/session` exchange failure) `catch` 블록에서 `rollbackPreviousToken(tx)`을 호출하여 이전 토큰을 즉각 복구.
  - callback 성공 시에만 새 토큰(`freshToken`)으로 교체하고 이전 토큰을 결과 객체에 포함하여 반환.
  - `completeStepUp`은 트랜잭션이 step-up이 아닌 경우 즉시 거부(`Step-Up 트랜잭션이 아닙니다`).

### 3) 내부망 배포 화면 UI 결속 (`apps/web/src/features/deployment/IntranetDeploymentView.tsx`)
- 서버 릴리스 상세 섹션 하단에 `deployment-step-up-section` 배치:
  - 상태 배지: `재인증 필요 (Step-Up Required)` (`data-testid="deployment-step-up-status-badge"`).
  - 안내 문구: `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false` (설계 기본값 비활성 유지), `BLOCKED_EXTERNAL` (사내 hosts 미적용), 실패 시 기존 토큰 보존 및 합성 금지 명시.
  - 실행 버튼: `재인증 필요 (Step-Up 로그인)` (`data-testid="deployment-step-up-button"`, `size="sm"`).
  - 버튼 클릭 시 `beginStepUp({ returnUrl: window.location.pathname })` 호출 후 `window.location.assign(url)` 리다이렉트.
  - 디자인 토큰 결속: `var(--color-bg-canvas)`, `var(--color-border-subtle)`, `var(--color-text-primary)`, `var(--color-text-muted)`, `var(--color-status-warning)`을 적용하여 하드코딩 색상 0건 유지.
  - 쓰기 UI 0건: 수락/서명 등록 폼이나 변이 엔드포인트 호출 코드 완전 배제.

---

## 3. 검증 결과 및 증거 (Evidence)

| 검증 항목 | 대상 / 명령 | 결과 |
| :--- | :--- | :--- |
| 계약 단위 시험 | `npm run test -- auth-step-up-contract.test.ts` | **23 passed** (22ms, exit 0) |
| UI 결속 단위 시험 | `npm run test -- auth-step-up-ui.test.tsx` | **4 passed** (183ms, exit 0) |
| 정본 41개 계약 TS 점검 | `node apps/web/scripts/api-response-contracts.mjs --check` | **PASS (41 types match, exit 0)** |
| TypeScript 정적 검증 | `cd apps/web && npx tsc -b` | **0 errors (exit 0)** |
| 프로덕션 번들 빌드 | `npm run build` (Vite production bundle) | **build 성공 (8.50s, exit 0)** |
| 라우트 커버리지 점검 | `pytest tests/test_route_coverage.py` | **41 passed (exit 0)** |
| 프런트엔드 무결성 점검 | `python tools/check_frontend_integrity.py` | **93 files scanned, 0 violations (exit 0)** |
| 계약 바인딩 앵커 점검 | `python tools/check_contract_bindings.py` | **55 fixtures, 20 bound types, exit 0** |
| 문서 및 DAG 무결성 점검 | `python tools/check_docs.py` | **PASS (1070 docs, exit 0)** |
| 문서 경로 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref 6b2a3786` | **290 baseline, 0 new broken (exit 0)** |
| Git 공백/충돌 검사 | `git diff --check 6b2a3786` | **Clean (exit 0)** |
| 봇 호출 태그 점검 | `git diff 6b2a3786 \| Select-String -Pattern "@(codex\|claude\|gemini)"` | **0 occurrences (exit 0)** |

### 변이 사살 (Killed Mutations)
1. **M1 (exact query params)**: authorize URL에서 `prompt=login` 또는 `max_age=300` 누락 시 즉시 실패.
2. **M2 (forbid extra params)**: authorize URL에 임의 잉여 파라미터 주입 시 `validateStepUpRequest`에서 즉각 거부.
3. **M3 (PKCE regeneration)**: 이전 `code_verifier`, `state`, `nonce` 재사용 시 고유성 검증 단언에서 즉각 실패.
4. **M4 (state mismatch rejection)**: 콜백 state 변조 시 `OIDC state 불일치` 거부 및 이전 토큰 롤백.
5. **M5 (previous token immutability on failure)**: `access_denied`, network failure, session exchange failure 시 `getAuthToken()`이 이전 토큰과 불일치할 경우 즉각 실패 (fail-closed 보존).
6. **M6 (token replacement on success)**: 정상 인증 완료 후 새 토큰 미반영 시 실패.
7. **M7 (non-step-up rejection)**: 일반 로그인 트랜잭션으로 `completeStepUp` 호출 시 즉각 예외 발생.
8. **M8 (zero write UI)**: `deployment-step-up-section` 내 `<form>` 또는 `<input>` 존재 시 즉시 실패.

---

## 4. 정직성 경계 (Honest Boundaries)

- **BLOCKED_EXTERNAL**: 실제 사내 폐쇄망 DNS/hosts(`idp.sv.lan`) 미적용 환경이므로, 실제 IdP 브라우저 리다이렉트 및 live OTP 교환 관측은 외부 인프라 요인으로 차단된 상태(`BLOCKED_EXTERNAL`)입니다. 로컬 모의 OIDC 환경에서의 엄격한 암호학적 파라미터 결속 및 토큰 보존 불변식을 바탕으로 검증을 완료했습니다.
- **INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false**: 백엔드 쓰기 라우트는 설계 기본값에 따라 비활성화되어 있으며, 화면에 어떠한 쓰기 폼이나 허위 서명 완료 상태도 합성하지 않았습니다.

---

## 5. 다음 담당자 및 행동

- **다음 담당자**: Claude UI (UI/인증 흐름/E2E 검토), Codex (보안 계약/PKCE 롤백 불변식 검토)
- **이어서 할 행동**:
  1. Card 192 PR 생성 후 Claude UI 및 Codex에 검토 요청 전달 (봇 호출 태그 0건 준수).
  2. 검토 피드백 도착 시 최우선 조치.
