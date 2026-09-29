---
doc_id: "HIST-GEMINI-CARD153-001"
title: "History: Card 153 사내 IdP(Keycloak) 연동 FE 점검·수정 및 OIDC PKCE·토큰 만료·로그아웃 검증"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T00:05:00+09:00"
source_of_truth: "Git"
---

# History: Card 153 사내 IdP(Keycloak) 연동 FE 점검·수정 및 OIDC PKCE·토큰 만료·로그아웃 검증

## 1. 개요 및 배경

- **카드 번호**: Card 153 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/card153-idp-login` (Base: `origin/integration/all-agents-unified` `6fc0428b`)
- **목적**: 사내 IdP(Claude Card 152가 노드 `192.168.45.143`에 배포한 Keycloak)로 웹 포털 로그인이 실제로 원활히 구동될 수 있도록 프런트엔드 인증 및 세션 아키텍처 전면 점검 및 조치:
  1. 표준 OIDC Authorization Code Flow + PKCE (RFC 7636 S256 verifier/challenge, state, nonce).
  2. 동적 OIDC Issuer(`issuer`) 및 클라이언트 ID(`clientId`) 설정 해석 (하드코딩 금지, Keycloak 표준 엔드포인트 자동 도출 및 엔드포인트 개별 오버라이드 지원).
  3. 로컬/dev IdP 가정 및 비안전 원격 HTTP 폴백 전면 제거 (Fail-closed 보안 아키텍처).
  4. 제어 평면 서버 계약 준수 토큰 유효기간(`0 < exp - iat <= 3600`) 클라이언트-서버 이중 가드 및 능동 세션 만료 타이머·재로그인 안내 배너(`[AUTH-0050]`).
  5. 표준 OIDC RP-Initiated 로그아웃 엔드포인트 지원, 인메모리 토큰/만료타이머/트랜잭션스토리지 무결 청소.
  6. Mock OIDC 서버 기반 종합 자동화 검증 스위트(`apps/web/tests/auth-oidc-contract.test.ts`, 20 passed) 신설.

---

## 2. 세부 구현 내역

### 1) 동적 Issuer 및 클라이언트 ID 설정 (`apps/web/src/features/auth/session.ts`)
- `authConfig()`가 `window.__SAINTVISION_CONFIG__`로부터 `issuer`와 `clientId`를 동적으로 읽어 Keycloak/OIDC 표준 엔드포인트를 자동 도출하도록 구현:
  - `idpAuthorizeUrl`: `${cleanIssuer}/protocol/openid-connect/auth`
  - `idpTokenUrl`: `${cleanIssuer}/protocol/openid-connect/token`
  - `idpLogoutUrl`: `${cleanIssuer}/protocol/openid-connect/logout`
  - `scope`: 기본값 `'openid inv.api'` (운영자 설정 시 커스텀 scope 우선)
  - `redirectUri`: 기본값 `${window.location.origin}/callback`
- 명시적 `idpAuthorizeUrl`, `idpTokenUrl`, `idpLogoutUrl` 지정 시 이를 우선 적용하여 역방향 프록시 및 커스텀 경로 지원.
- 설정 누락(`clientId` 부재, `issuer` 및 엔드포인트 쌍 전무) 시 임의의 dev IdP로의 묵시적 폴백을 원천 차단하고 `throw new Error(...)`로 fail-closed.

### 2) dev IdP 가정 및 비안전 원격 HTTP 전면 제거
- `endpoint()` 및 `cleanIssuerUrl()` 검증기:
  - `http://` 프로토콜은 오직 로컬 개발 루프백(`127.0.0.1`, `localhost`, `[::1]`)에만 제한 허용.
  - 사내망 원격 IP(`192.168.45.143`) 및 도메인은 반드시 `https://` 암호화 채널을 강제.
  - URL 내 자격증명(`user:pass@...`) 및 해시 프래그먼트(`#...`) 포함 시 즉각 거부.

### 3) 표준 OIDC Authorization Code Flow + PKCE (RFC 7636)
- `beginLogin()`:
  - 고엔트로피 `verifier` (43~128자 base64url) 및 SHA-256 S256 `code_challenge` 생성.
  - CSRF 방어용 `state` (32자 16진수 hex) 및 재전송 방지용 `nonce` (32자 16진수 hex) 생성.
  - `sessionStorage` (`saintvision.oauth.transaction`)에 트랜잭션 안전 저장.
  - IdP 인가 엔드포인트로 인가 요청 URL 조립 및 리다이렉트.
- `completeLogin()`:
  - `/callback` 호출 시 트랜잭션 1회성 인출 및 즉시 파기 (`sessionStorage.removeItem`).
  - state 일치, 10분 유효시간 검증, verifier 무결성 검증.
  - IdP 토큰 엔드포인트(`idpTokenUrl`)와 `authorization_code` 안전 교환 (`credentials: 'omit'`).
  - `Bearer` 토큰 타입 검증.

### 4) 서버 계약 준수 토큰 유효기간 검증 및 능동 만료·재로그인 처리
- **서버 계약 불변식**: `services/control-plane/src/inv/identity.py:157`의 `0 < exp - iat <= 3600` 계약.
- **클라이언트 검증**:
  - `parseJwtPayload()` 및 `validateTokenExpiration()`: 수신한 JWT의 클레임 중 `exp - iat > 3600`이거나 `exp <= iat`인 경우, 또는 이미 `exp <= now`인 경우 즉각 실패 차단(`throw new Error('인증 토큰 유효 기간이 서버 계약 허용치(최대 3600초)를 초과하거나 올바르지 않습니다.')`).
  - 리소스 서버 `GET /v1/session` 호출 후 `identity.expiresAt` 검증: 만료된 값이거나 현재 시각 대비 3600초 초과 시 fail-closed.
- **능동 세션 만료 타이머**:
  - `registerSessionExpiration(expiresAt)`: 토큰 만료 시점(Unix 초)에 맞추어 `setTimeout` 스케줄링.
  - 만료 도래 시 `triggerTokenExpired('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.')` 발행.
  - 인메모리 토큰 즉시 제거(`clearAuthToken()`).
  - `apps/web/src/app/App.tsx`의 `onTokenExpired` 리스너가 동작하여 `resetAuthenticatedState` 호출, 데스크톱 및 프로젝트 뷰 정리, `Login` 탭 복귀, `role="alert"` 경고 표출.
  - 사용자는 "조직 계정으로 로그인" 버튼을 눌러 즉시 새 PKCE 트랜잭션으로 재인증 가능.

### 5) OIDC 로그아웃 및 세션 정리 (`apps/web/src/shared/ui/Header.tsx`, `apps/web/src/app/App.tsx`)
- `buildLogoutUrl()`: OIDC RP-Initiated Logout 표준 규격에 따라 `client_id` 및 `post_logout_redirect_uri`를 조립한 IdP 엔드세션 URL 생성.
- `performLogout()`:
  - 만료 타이머 해제(`clearSessionExpiration()`).
  - 인메모리 토큰 제거(`clearAuthToken()`).
  - 미완료 OAuth 트랜잭션 청소(`sessionStorage.removeItem(STORAGE_KEY)`).
  - 필요 시 IdP 로그아웃 엔드포인트로 브라우저 리다이렉트 (`redirectIdp: true`).
- `Header`의 로그아웃 버튼 클릭 시 `performLogout()` 및 `resetAuthenticatedState(null)`가 연동되어 안전하고 무결하게 초기 상태로 전이.

---

## 3. 검증 결과

### 1) 단위 및 회귀 자동화 시험
- 신규 OIDC 종합 계약 시험: `apps/web/tests/auth-oidc-contract.test.ts`
  - 20 tests **100% PASS** (24ms)
- 기존 인증 시험: `apps/web/tests/auth-session.test.ts` (17 tests) & `apps/web/tests/auth-pkce.test.ts` (4 tests)
  - 21 tests **100% PASS** (27ms)
- `apps/web` 전체 Vitest 스위트:
  - **90 test files / 940 passed 100%** (0 failed, 0 errors)
- TypeScript 타입 점검:
  - `npx tsc -b` 에러 **0건**
- 프로덕션 번들 빌드:
  - `npm run build` 성공 (Vite v6.4.3 production bundle 생성 완료, 8.31s)

### 2) 제어 평면 및 프런트엔드 무결성 게이트 검증
- `python -X utf8 tools/check_frontend_integrity.py`:
  - 92개 소스 파일 스캔, 9대 무결성 규칙 만족, 위반 **0건** (exit 0)
- `python -X utf8 tools/check_contract_bindings.py`:
  - 55개 픽스처 전수 참조, 20개 커널 응답 타입 26개 서빙앵커 커버리지, 14개 리플레이 가드 PASS (exit 0)
- `pytest tests/test_route_coverage.py`:
  - 40 passed 100% (exit 0)
- `python tools/check_docs.py`:
  - PASS: 24 original hashes, 1035 versioned documents, wiki links, 48 tasks, 12 outcomes (exit 0)
- `python tools/check_doc_path_citations.py --ratchet --base-ref origin/integration/all-agents-unified`:
  - PASS check_doc_path_citations --ratchet: 290 broken citation(s), all in baseline, none stale (exit 0)
