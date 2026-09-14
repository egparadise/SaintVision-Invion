---
doc_id: "REPORT-GEMINI-HIST-024"
title: "Gemini 외부 IdP PKCE 리다이렉트 콜백 구현 및 암호 프로토콜 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T21:45:00+09:00"
updated: "2026-09-14T21:45:00+09:00"
base_sha: "1e35815"
task_id: "S01-FE~S12-FE"
scope: "apps/web/src/features/auth/Login.tsx, apps/web/tests/auth-pkce.test.ts"
source_of_truth: "Git"
---

# Gemini 외부 IdP PKCE 리다이렉트 콜백 구현 및 암호 프로토콜 검증 보고

## 1. 개요 및 배경

Claude는 4956787에서 /v1/auth/token에 대한 'Decision 3'을 확정하였다:
- 전통적인 웹 브라우저 OIDC 흐름은 백엔드 mock 토큰 엔드포인트가 아니라 IdP 자체의 Authorization Server(/oauth2/authorize)로 리다이렉트되어 인가 코드를 발급받고, 토큰 교환을 수행하는 브라우저 직접 표준 프로토콜이다.
- 따라서 커널이 독자적인 /v1/auth/token을 별도 신규 서빙할 필요가 없으며, 현재의 게이트웨이 브로커는 로컬 격리 및 스모크 테스트를 위한 인프라 역할을 담당한다.

Gemini(Antigravity)는 이에 따라 pps/web/src/features/auth/Login.tsx에 실제 운영 환경의 외부 IdP 인가 서버 리다이렉트 및 RFC 7636 PKCE 콜백 교환 핸들러를 구현하고, 암호화 프로토콜 단위 테스트(pps/web/tests/auth-pkce.test.ts)를 추가하여 프로덕션 OIDC 아키텍처를 완결하였다.

---

## 2. 구현 내역

### 2.1 실제 외부 IdP 리다이렉트 & 세션 저장소 보존 (Login.tsx)
- (window as any).__SAINTVISION_CONFIG__?.idpAuthorizeUrl 환경 설정 감지 시:
  - RFC 7636 규격의 고엔트로피 codeVerifier (43자 이상) 및 codeChallenge (S256 base64url) 생성.
  - CSRF 방지를 위한 state, 재전송 공격 방지를 위한 
once 생성.
  - sessionStorage에 oidc_verifier, oidc_state 안전 임시 보관.
  - 외부 IdP (idpAuthorizeUrl)로 esponse_type=code, code_challenge, code_challenge_method=S256 쿼리와 함께 302/Location 리다이렉트.

### 2.2 인가 코드 콜백 자동 수신 및 교환 (Login.tsx)
- 마운트 시 useEffect를 통해 window.location.search의 ?code=...&state=... 파라미터 감지:
  - sessionStorage의 oidc_state와 IdP가 반환한 state가 일치하는지 엄격히 대조 (CSRF 공격 원천 차단).
  - 검증 성공 시 sessionStorage 토큰을 즉시 폐기하고 브라우저 주소창의 인가 코드를 history.replaceState로 은폐.
  - 저장된 code_verifier를 첨부하여 정식 토큰 교환 요청 수행 및 인메모리 Access Token 안전 저장 (setAuthToken).

### 2.3 로컬 독립망 / 스모크 테스트 호환성 유지
- 외부 IdP 미설정 환경(사내 폐쇄망 개발, CI, 자동화 브라우저 스모크 검증)에서는 기존의 검증된 게이트웨이 브로커(/v1/auth/token)로 직접 교환하여 모든 테스트가 무중단 통과되도록 보장.

### 2.4 RFC 7636 PKCE 암호 프로토콜 단위 테스트 (pps/web/tests/auth-pkce.test.ts)
- 엔트로피 및 유효 문자열 검증 (generateCodeVerifier): 43자 이상, [A-Za-z0-9_-] base64url 포맷 검증.
- 결정론적 SHA-256 해시 및 S256 챌린지 무결성 (generateCodeChallenge): 동일 verifier에 대한 동일 해시 출력 및 원본 은폐 확인.
- 고유 CSRF State 및 Nonce 생성 무결성 검증.

---

## 3. 검증 결과

### 3.1 자동화 테스트 파이프라인 전수 합격
1. **Vitest 유닛/통합 테스트**: **21개 테스트 파일 전수 합격**, **131/131 tests passed (100%)** (uth-pkce.test.ts 4개 신규 통과).
2. **Vite 프로덕션 빌드 (	sc -b && vite build)**: 75개 모듈 트랜스폼 완료, **0 errors, 0 warnings (3.29s)**.
3. **E2E 브라우저 스모크 검증 (	ools/run_browser_smoke.mjs)**: 14개 트랙, **181/181 checks passed (100%)**.
4. **2-PC 분산 실행/복구/GPU 스케일링 검증 (	ools/verify_two_pc_distributed_execution.mjs)**: 5개 단계, **67/67 checks passed (100%)**.
5. **라우트 커버리지 (python tools/route_coverage.py)**: 109 distinct served routes, 24 client paths, **0 unserved (100% 완전 커버리지, Exit Code 0)**.
6. **문서 및 온톨로지 무결성 검증**:
   - python tools/check_docs.py: **PASS** (276 versioned documents).
   - .venv\Scripts\python.exe tools/check_ontology.py: **PASS** (48 task mappings).

---

## 4. 인계 및 거버넌스 기록

- **진척도 (AUDIT 기준)**:
  - Codex 공통 기준선: **57.81%** (2,775 / 4,800점)
  - Gemini 영역 구현 성숙도: **75.0%** (900 / 1,200점, S01~S12 전 12개 FE 태스크 최고 구현 상태)
  - 독립 검토 및 통합 승인 시 전체 진척도: **65.63%** (3,150 / 4,800점, 약 65% 진척 / 잔여 약 35%)
- **Git 반영**: commit 96191cc (origin/integration/all-agents-unified)
- **다음 행동**: Claude 독립 검토(CL-01), Codex 원격 PC 프로필 설치 및 7대 시험(CX-01~03) 연계 대기.
