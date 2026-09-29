---
doc_id: "HIST-GEMINI-CARD153-001"
title: "History: Card 153 사내 IdP(Keycloak) 연동 FE 점검·수정 및 OIDC PKCE·토큰 만료·로그아웃 검증"
version: "1.1.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T08:08:00+09:00"
source_of_truth: "Git"
---

# History: Card 153 사내 IdP(Keycloak) 연동 FE 점검·수정 및 OIDC PKCE·토큰 만료·로그아웃 검증

## 1. 개요 및 배경

- **카드 번호**: Card 153 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/card153-idp-login` (Base: `origin/integration/all-agents-unified` `6fc0428b`)
- **목적**: 사내 IdP(Claude Card 152가 노드 `192.168.45.143`에 배포한 Keycloak)로 웹 포털 로그인이 실제로 원활히 구동될 수 있도록 프런트엔드 인증 및 세션 아키텍처 전면 점검 및 조치:
  1. 표준 OIDC Authorization Code Flow + PKCE (RFC 7636 S256 verifier/challenge, state, nonce).
  2. 동적 OIDC Issuer(`issuer`) 및 클라이언트 ID(`clientId`) 설정 해석 (하드코딩 금지, Keycloak 표준 엔드포인트 자동 도출 및 동일 origin/path 결속 오버라이드 지원).
  3. 로컬/dev IdP 가정 및 비안전 원격 HTTP 폴백 전면 제거 (Fail-closed 보안 아키텍처).
  4. 제어 평면 서버 계약 준수 토큰 유효기간(`0 < exp - iat <= 3600`) 클라이언트-서버 이중 가드(120초 시계 오차 허용) 및 능동 세션 만료 타이머·재로그인 안내 배너(`[AUTH-0050]`).
  5. 표준 OIDC RP-Initiated 로그아웃 배선(`App.tsx:549`에서 `performLogout({ redirectIdp: true, postLogoutRedirectUri: origin })` 연동) 및 인메모리 토큰/만료타이머/트랜잭션스토리지 무결 청소.
  6. OIDC ID 토큰(id_token)의 nonce(트랜잭션 nonce와 일치), aud(clientId 일치), iss(issuer 일치) 클라이언트 검증 완비.
  7. Mock OIDC 서버 기반 종합 자동화 검증 스위트(`apps/web/tests/auth-oidc-contract.test.ts`, 33 passed), RFC 7636 벡터 시험(`auth-pkce.test.ts`, 5 passed), App 수준 로그아웃 및 만료 연동 시험(`auth-app-oidc-integration.test.tsx`, 2 passed) 신설.

---

## 2. 세부 구현 및 검토 조치 내역

### 1) 동적 Issuer 및 클라이언트 ID 설정 (`apps/web/src/features/auth/session.ts`)
- `authConfig()`가 `window.__SAINTVISION_CONFIG__`로부터 `issuer`와 `clientId`를 동적으로 읽어 Keycloak/OIDC 표준 엔드포인트를 자동 도출:
  - `idpAuthorizeUrl`: `${cleanIssuer}/protocol/openid-connect/auth`
  - `idpTokenUrl`: `${cleanIssuer}/protocol/openid-connect/token`
  - `idpLogoutUrl`: `${cleanIssuer}/protocol/openid-connect/logout`
  - `scope`: 기본값 `'openid inv.api'` (운영자 설정 시 커스텀 scope 우선)
  - `redirectUri`: `${window.location.origin}/callback` 정규화
- **[Codex Finding 1] Cross-Origin Token Override 원천 차단**:
  - `issuer`가 지정된 경우, 모든 커스텀 오버라이드(`idpAuthorizeUrl`, `idpTokenUrl`, `idpLogoutUrl`)는 반드시 `issuer`와 동일한 origin 및 하위 경로 계층(`isSubpathOf`) 내에 위치해야 함을 강제. 불일치 시 `authConfig()`에서 즉각 예외 발생 (부정 시험 완비).
  - `issuer` 없이 엔드포인트 쌍만 지정하는 경우에도 인가 엔드포인트와 토큰 엔드포인트가 서로 다른 origin을 가질 수 없도록 강제.
- **[Claude L4] redirectUri 정규화 및 strict path 검증**:
  - `redirectUri`가 문자열이 아니거나 빈 값인 경우 즉시 거부.
  - `new URL(raw, origin).href`로 안전하게 정규화하여 상대 경로(`/callback`) 지원.
  - 현재 웹 애플리케이션과 origin이 일치하지 않거나 pathname이 `/callback`이 아닌 경우 즉시 fail-closed 차단.

### 2) dev IdP 가정 및 비안전 원격 HTTP 전면 제거
- `endpoint()` 및 `cleanIssuerUrl()` 검증기:
  - `http://` 프로토콜은 오직 로컬 개발 루프백(`127.0.0.1`, `localhost`, `[::1]`)에만 제한 허용.
  - 사내망 원격 IP(`192.168.45.143`) 및 도메인은 반드시 `https://` 암호화 채널을 강제.
  - URL 내 자격증명(`user:pass@...`) 및 해시 프래그먼트(`#...`) 포함 시 즉각 거부.

### 3) 표준 OIDC Authorization Code Flow + PKCE (RFC 7636) 및 Nonce/ID Token 검증
- `beginLogin()`:
  - 고엔트로피 `verifier` (43~128자 base64url) 및 SHA-256 S256 `code_challenge` 생성.
  - CSRF 방어용 `state` (32자 16진수 hex) 생성.
  - scope에 `openid` 포함 시 OIDC `nonce` (32자 16진수 hex) 생성 및 인가 요청 쿼리에 반영.
  - `sessionStorage` (`saintvision.oauth.transaction`)에 트랜잭션 안전 저장.
  - [auth-pkce.test.ts](file:///D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.worktrees/gemini-card153-idp-login/apps/web/tests/auth-pkce.test.ts)에 RFC 7636 Appendix B 공식 테스트 벡터 단언 추가 (5 passed).
- **[Codex Finding 2, Claude M2] ID Token(id_token) 검증 완비**:
  - `completeLogin()` 시 토큰 엔드포인트 응답에서 `result.id_token` 추출.
  - `tx.nonce`가 전송되었거나 `result.id_token`이 존재하는 경우:
    - ID 토큰 누락 시 즉시 거부 (`OIDC 인증 응답에 ID 토큰(id_token)이 누락되었습니다.`).
    - ID 토큰 페이로드 파싱 후 `idClaims.nonce === tx.nonce` 일치성 검증 (재전송 및 주입 방어).
    - `idClaims.iss === config.issuer` 일치성 검증.
    - `idClaims.aud === config.clientId` 일치성 검증.
    - `idClaims.exp` 만료 여부 검증 (120초 시계 오차 허용).
  - missing/mismatched nonce/mismatched aud/mismatched iss/expired 부정 시험 전수 추가.

### 4) 서버 계약 준수 토큰 유효기간 검증 및 능동 만료·재로그인 처리
- **서버 계약 불변식**: `services/control-plane/src/inv/identity.py:157`의 `0 < exp - iat <= 3600` 계약.
- **[Codex Finding 5] validateTokenExpiration fail-closed 강화**:
  - `validateTokenExpiration`은 JWT 토큰에 대해 malformed JWT, 누락/비정수형 exp/iat, 수명 `<= 0` 또는 `> 3600`, 만료 토큰을 전수 fail-closed 거부.
  - `completeLogin`에서는 하위 호환을 위해 3-part JWT에 대해 엄격 fail-closed 검증을 수행하고 opaque 토큰은 `/v1/session` 서버 검증에 위임.
- **[Claude M3] 120초 시계 오차 허용 (`CLOCK_SKEW_SEC = 120`)**:
  - 클라이언트 시계와 서버 시계 간 오차로 인한 부당한 거부를 방지하기 위해 120초 여유 적용 (`identity.expiresAt - nowSec > 3600 + CLOCK_SKEW_SEC` 및 `claims.exp + CLOCK_SKEW_SEC <= nowUnixSeconds`).
- **능동 세션 만료 타이머**:
  - `registerSessionExpiration(expiresAt)`: 토큰 만료 시점(Unix 초)에 맞추어 `setTimeout` 스케줄링.
  - 만료 도래 시 `triggerTokenExpired('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.')` 발행.
  - 인메모리 토큰 즉시 제거(`clearAuthToken()`).
  - `apps/web/src/app/App.tsx`의 `onTokenExpired` 리스너가 동작하여 `resetAuthenticatedState` 호출, 데스크톱 및 프로젝트 뷰 정리, `Login` 탭 복귀, `role="alert"` 경고 표출.
  - 사용자는 "조직 계정으로 로그인" 버튼을 눌러 즉시 새 PKCE 트랜잭션으로 재인증 가능.

### 5) OIDC RP-Initiated 로그아웃 배선 및 세션 정리 (`apps/web/src/app/App.tsx`, `session.ts`)
- **[Claude M1, Codex Finding 3] App 로그아웃 버튼 배선**:
  - `App.tsx:549`: `onLogout` 핸들러가 `performLogout({ redirectIdp: true, postLogoutRedirectUri: window.location.origin })`를 호출하여 Keycloak OIDC RP-Initiated 로그아웃 엔드포인트(`protocol/openid-connect/logout`)로 실제 브라우저 리다이렉트(`window.location.assign`) 수행.
  - 인메모리 토큰 제거, 만료 타이머 해제, 미완료 트랜잭션 스토리지 파기, 상태 초기화 완비.
  - [auth-app-oidc-integration.test.tsx](file:///D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.worktrees/gemini-card153-idp-login/apps/web/tests/auth-app-oidc-integration.test.tsx)를 신설하여 Header 로그아웃 클릭 시 `location.assign` 호출 및 세션 정리를 App 수준에서 실측 검증.

### 6) Tracked Public 예제 및 사내망 계약 정합 (`apps/web/public/auth-config.js`)
- **[Codex Finding 4]**:
  - `apps/web/public/auth-config.js`의 예제를 임시 private IP 대신 Card 152의 정본 계약인 `https://idp.sv.lan/realms/saintvision` 및 클라이언트 `sv-portal`로 일치.
  - 현재 상태는 FE OIDC PKCE 구현 및 모의/계약 검증 완료 상태이며, #250의 TLS 및 사내망 인벤토리 블로커 해결 전까지는 사내망 live HTTPS 운영 로그인 PASS로 단정하지 않고 독립 검토 및 착지 단계로 관리.

---

## 3. 검증 결과

### 1) 단위 및 회귀 자동화 시험
- 신규 OIDC 종합 계약 시험: `apps/web/tests/auth-oidc-contract.test.ts`
  - **33 tests 100% PASS** (32ms) (기존 20건 + 신규 13건)
- 기존 인증 시험: `apps/web/tests/auth-session.test.ts` (17 tests) & `apps/web/tests/auth-pkce.test.ts` (5 tests, RFC 벡터 포함)
  - **22 tests 100% PASS** (38ms)
- 신규 App 수준 OIDC 통합 시험: `apps/web/tests/auth-app-oidc-integration.test.tsx`
  - **2 tests 100% PASS** (256ms)
- `apps/web` 전체 Vitest 스위트:
  - **91 test files / 956 passed 100%** (0 failed, 0 errors)
- TypeScript 타입 점검:
  - `npx tsc -b` 에러 **0건**
- 프로덕션 번들 빌드:
  - `npm run build` 성공 (Vite v6.4.3 production bundle 생성 완료, 9.07s)

### 2) 제어 평면 및 프런트엔드 무결성 게이트 검증
- `python -X utf8 tools/check_frontend_integrity.py`:
  - 92개 소스 파일 스캔, 9대 무결성 규칙 만족, 위반 **0건** (exit 0)
- `python -X utf8 tools/check_contract_bindings.py`:
  - 55개 픽스처 전수 참조, 20개 커널 응답 타입 26개 서빙앵커 커버리지, 14개 리플레이 가드 PASS (exit 0)
- `pytest tests/test_route_coverage.py`:
  - 40 passed 100% (exit 0)
- `python tools/check_docs.py`:
  - PASS: 24 original hashes, 1036 versioned documents, wiki links, 48 tasks, 12 outcomes (exit 0)
- `python tools/check_doc_path_citations.py --ratchet --base-ref origin/integration/all-agents-unified`:
  - PASS check_doc_path_citations --ratchet: 290 broken citation(s), all in baseline, none stale (exit 0)
- `python tools/check_doc_single_source.py --ratchet`:
  - PASS check_doc_single_source --ratchet: 19 pairs, all in baseline, none stale (exit 0)

---

## 4. 인계 및 다음 단계
- **PR**: https://github.com/egparadise/SaintVision-Invion/pull/247
- **수정사항**: Claude UI (M1, M2, M3, L4, L5, L6) 및 Codex (1~5) 지적사항 전수 반영.
- **독립 검토 요청**: Claude (UI·테스트 축) 및 Codex (계약·보안 축) 재확인 요청.

