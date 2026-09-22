---
doc_id: "HIST-GEMINI-2026-09-23-S02-FE-REAL-API"
title: "S02-FE 실제 API Chrome 로그인·Node 0대·401/403 수용 실측 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-23T00:10:00+09:00"
source_of_truth: "Git"
tags: ["s02-fe", "real-api", "chrome", "acceptance", "evidence", "gemini", "zero-mock"]
---

# S02-FE 실제 API Chrome 로그인·Node 0대·401/403 수용 실측 보고

- 작업 일시: 2026-09-23T00:10:00+09:00
- 배정: Gemini (Frontend & Browser Acceptance Owner)
- 검토 대상/기준: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[Frontend 최종 개발 계획]], [[설계 충돌 정정 및 ADR]], [[공통 계약 요구사항과 완료 기준]]
- 선행 작업 및 브랜치: `agent/gemini/s02-fe-real-api` (base: `a4bf2cee`, tip: `b3f6db05`)
- 증거 정본: `docs/vault/30_Development/Evidence/s02_fe_real_api_acceptance.json`

---

## 1. 개요 및 배경

1. **코디네이터 지시 사항 (2026-09-22 22:38 KST)**:
   - S02-FE '실제 API Chrome 로그인·Node·401/403' 카드 착수:
     - 실 백엔드 Uvicorn 8080, 실 Dev IdP 8090 (`.work/dev/dev_idp.py`), Vite 3005 개발 서버 환경에서 Google Chrome 실제 브라우저로 4대 유저 저니 수용 실측.
     - (1) 로그인 성공 경로 (OIDC Code Flow 교환 및 세션 수립).
     - (2) 토큰 만료 401 ProblemDetails 및 재로그인 경로.
     - (3) 권한 없는 프로젝트 403 ProblemDetails (`application/problem+json`) 및 `role="alert"` 표출.
     - (4) Node 목록 실데이터 (0대면 0대 정직 표기).
   - 단언은 실 DOM 및 네트워크 응답 코드로만 수행하며, 증거 JSON은 실행 시 실측값만 기록 (상수 배제, Zero Mock).

---

## 2. 실행 환경 및 무목(Zero Mock) 불변식

- **OS / 플랫폼**: Windows 11 (nt), Python 3.14.7
- **실제 브라우저**: Google Chrome Official Build 153.0.7070.0 (Blink 엔진, Headless 실행)
- **실제 백엔드 제어 평면**: FastAPI / Uvicorn (`http://127.0.0.1:8080`, 실제 DB/제어평면 결속)
- **실제 Dev IdP**: `.work/dev/dev_idp.py` (`http://127.0.0.1:8090`, 실제 OIDC `/auth/authorize`, `/auth/token`, `/.well-known/jwks.json` 서빙)
- **실제 웹 프런트엔드**: Vite Dev Server (`http://localhost:3005`, `apps/web`)
- **실측 러너 스크립트**: `tools/run_s02_real_api_acceptance.py`
- **Zero Mock 원칙**:
  - `msw`, `fetch` 모킹, 프런트엔드 가짜 인메모리 데이터 전면 배제.
  - 브라우저 CDP(Chrome DevTools Protocol) 세션을 통해 실제 네트워크 왕복 HTTP 상태 코드 및 실제 렌더링된 DOM 요소만을 단언.

---

## 3. 4대 시나리오 실측 결과 상세

| 시나리오 ID | 시나리오 명칭 | 판정 | 핵심 검증 항목 및 실측 관측치 | 증거 스크린샷 |
|---|---|:---:|---|---|
| **`s02-login-success`** | 로그인 성공 경로 (OIDC Code Flow + Session 검증) | **PASS** | - `/auth/authorize` ➔ 302 Found 리다이렉트<br>- `POST /auth/token` ➔ 200 OK (Bearer 토큰, expiresIn 3600)<br>- `GET /v1/auth/session` ➔ 200 OK<br>- DOM `header[role="banner"]` 및 `로그아웃` 버튼 노출 실측 | `s02_01_login_success.png` |
| **`s02-nodes-real-data`** | Node 목록 실데이터 (0대 정직 표기) | **PASS** | - `GET /v1/projects/.../nodes` ➔ 200 OK<br>- Wire 상 실제 반환 데이터 `items: []`, `total: 0`<br>- DOM `[data-testid="node-list-empty-state"]` 렌더링<br>- 정직한 빈 상태 문구 `등록된 Node가 없습니다` 실측 | `s02_04_nodes_empty_state.png` |
| **`s02-project-403`** | 미인가 프로젝트 403 ProblemDetails 및 alert 표출 | **PASS** | - 미인가 프로젝트 `prj_01M33NGQEZTB2QD1CWV97Y7999` 조회<br>- Wire 상 403 Forbidden (`application/problem+json`)<br>- RFC 9457 코드: `AUTH-0030`, 상세: `Project permission is unavailable`<br>- `traceId: 57f91043886c7c3f4fe0734ffcf428f7`<br>- DOM `div[role="alert"]` 내 `[AUTH-0030]` 에러 텍스트 표출 실측 | `s02_03_project_403.png` |
| **`s02-token-expired-401`** | 토큰 만료 401 ProblemDetails 및 재로그인 경로 | **PASS** | - 만료 토큰 요청 시 Wire 401 Unauthorized (`application/problem+json`)<br>- RFC 9457 코드: `AUTH-0050`<br>- DOM `div[role="alert"]` 내 `[AUTH-0050]` 표출 후 로그인 화면 자동 전이<br>- Dev IdP 재로그인 인터랙션 성공 ➔ 새 토큰 교환 ➔ 포털 복귀 실측 | `s02_02_token_expired_401.png`<br>`s02_02_relogin_success.png` |

---

## 4. 정본 증거 데이터 요약 (`s02_fe_real_api_acceptance.json`)

- **JSON 스키마**: `https://saintvision.ai/evidence/s02-fe-real-api.schema.json` (v1.0.0)
- **실측 커밋 SHA**: `b3f6db051a8fd2ddb8f87911bea3a69270b10b8d` (Git HEAD 조상 관계 검증 완료)
- **실행 타임스탬프**: `2026-09-22T23:58:30.182187+09:00`
- **종합 결과**:
  - `totalScenarios`: 4
  - `passed`: 4
  - `failed`: 0
  - `mockApiUsed`: `false`
  - `realUvicornUsed`: `true`
  - `realDevIdPUsed`: `true`
  - `assessment`: `"ACCEPTANCE_PASSED"`
  - `operationalAcceptanceAssessed`: `true`

---

## 6. Claude 독립 검토 지적사항 (F1~F4) 조치 내역

1. **F1 (재현성 및 환경 결합도 해소)**:
   - `dev_idp.py`에 `--port` 및 `PORT` 환경변수 처리 추가.
   - `tools/run_s02_real_api_acceptance.py`에 `--dev-dir`, `--idp-script`, `--server-env` CLI 인자 추가.
   - `.work/dev` 파일 부재(clean worktree/CI) 환경에서는 비정상 크래시 대신 `UNMEASURED`로 우아하게 종료하도록 게이트 보강.
2. **F2 (프로덕션 코드 무결성 및 실제 만료 토큰 실측)**:
   - `App.tsx` 내 `window.__chooseProject`, `window.__setActiveTab`, `window.__simulateTokenExpired` 훅 전량 삭제.
   - `console.log` 및 하드코딩 dev project id(`prj_01M33NGQEZTB2QD1CWV97Y7DSN`) 삭제.
   - Scenario 4 토큰 만료는 Dev IdP 단축 TTL(`/dev/set-ttl?ttl=6`) 발급 후 실제 7초 경과에 의한 유기적 만료 및 실제 만료된 RS256 서명 JWT Wire 단언(401 `AUTH-0050`)으로 실측.
3. **F3 (계약 복원 및 RULE-9 위반 0건 달성)**:
   - `projectObservation.ts` 내 `apiClient<any>` 및 `|| new Date()`/기본값 합성 전량 제거, 엄격한 `ProjectListResponse` generated 계약 타입 복원.
   - `check_frontend_integrity.py` 9개 규칙 전체 무결점 통과 (RULE-9 0건).
   - `client.ts`의 `isRouteNotFoundError`에서 `HTTP-0001`/`Request unavailable` 폴백 과잉 매핑 제거, 미매핑 404에만 한정.
4. **F4 (증거 상수의 실측값 동적 유도)**:
   - `tools/run_s02_real_api_acceptance.py`의 `assessment`, `operationalAcceptanceAssessed`, `realUvicornUsed`, `realDevIdPUsed` 필드를 하드코딩 상수 대신 런타임 관측치와 프로세스 생존 상태로부터 동적 유도.

---

## 7. 검증 게이트 통과 내역 (최종 실측)

1. **Frontend 무결성 검사**:
   - `python -X utf8 tools/check_frontend_integrity.py`: **PASS** (83개 소스 파일 스캔, 9개 규칙 0 violations)
2. **TypeScript 컴파일 및 프로덕션 번들 생성**:
   - `cd apps/web && npx tsc -b`: **exit code 0** (타입 에러 0건)
   - `npm run build`: **exit code 0** (Vite 100 modules 프로덕션 번들 정상 생성)
3. **Frontend Vitest 전체 스위트**:
   - `npm run test`: **77/77 test files passed, 673/673 tests passed** (exit code 0)
4. **화면-백엔드 라우트 커버리지 및 불변식 게이트**:
   - `pytest tests/test_route_coverage.py`: **39 passed** (exit code 0)
5. **문서 정합성 게이트**:
   - `python tools/check_docs.py`: **PASS** (834 versioned documents, exit code 0)
6. **S02-FE 실브라우저 4대 시나리오 실측**:
   - `.venv\Scripts\python.exe -X utf8 tools/run_s02_real_api_acceptance.py`: **ACCEPTANCE_PASSED** (4/4 passed, 0 mocks, exit code 0)

---

## 8. 결론 및 Claude 독립 재검토 인계

- Claude 독립 검토 지적 4건(F1~F4)을 프로덕션 코드 정리, 계약 복원, 동적 관측치 유도, 실제 exp 경과 토큰 실측을 통해 완벽히 조치하였습니다.
- 코디네이터 지침에 따라 Claude에게 PR #77 재검토를 요청합니다.
