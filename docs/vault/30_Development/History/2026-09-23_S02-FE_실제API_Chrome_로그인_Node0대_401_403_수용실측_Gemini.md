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
- **실측 커밋 SHA**: `1ff1a016398b01ae7ad2e73b0411bb76b3d903c7` (Git HEAD 조상 관계 검증 성립)
- **실행 타임스탬프**: `2026-09-23T01:45:44.155623+09:00`
- **종합 결과**:
  - `totalScenarios`: 4
  - `passed`: 4
  - `failed`: 0
  - `unmeasured`: 0
  - `mockApiUsed`: `false` (Playwright 라우트 모의 0건 실측 동적 유도)
  - `realUvicornUsed`: `true` (8080 제어평면 프로세스 및 `/healthz` 200 실측)
  - `realDevIdPUsed`: `true` (8090 Dev IdP 프로세스 및 `/` 200 실측)
  - `assessment`: `"ACCEPTANCE_PASSED"`
  - `operationalAcceptanceAssessed`: `true`

---

## 5. Codex 보안 검토 지적 (S1) 및 관찰 (O1) 조치 내역

1. **S1 (401 teardown 시 tenant state 및 in-flight 요청 무효화)**:
   - `apps/web/src/app/App.tsx`에 `resetAuthenticatedState()` 단일 동기화 함수 신설:
     - `clearAuthToken()` 호출.
     - 6대 generation/request 카운터(`sessionRef`, `scopeRef`, `nodeRequest`, `runRequest`, `approvalRequest`, `workspaceRequest`)를 일괄 증가시켜 in-flight 비동기 응답 무효화.
     - `activeProject.current = ''` 초기화.
     - `currentUser`, `projectId`, `projects`, `nodes`, `workspaces`, `runs`, `approvals`, `nodeResourceUsage`, `evidenceRunId`, `studioStep/Id`, `actionError`, `desktop`을 동기적으로 전량 초기화.
   - `onUnauthorized` 및 Header `onLogout`이 이 함수를 공유하도록 일원화.
   - `fetchNodes`, `fetchRuns`, `fetchApprovals`, `fetchWorkspaces`, `fetchProjects`, `getNodeResourceUsage` 완료 시점(resolve/reject 모두)에 `sessionRef.current === currentSession` 및 `scopeRef.current === currentScope` 일치를 강제하여 이전 테넌트 데이터 재유입/레이스 컨디션 원천 차단.
2. **O1 (만료 관찰 한계 명시)**:
   - 클라이언트 만료 감지는 Request-driven(다음 인증 요청/폴링 시 401 ProblemDetails 반환)으로 동작하며, 토큰 자연 만료 후 최초 API 폴링 시 즉시 `onUnauthorized` ➔ `resetAuthenticatedState`가 트리거됨을 정직하게 명시함.

---

## 6. Claude 독립 검토 지적사항 (F1~F4 및 R1~R2) 조치 내역

1. **R1 (`--backend-port` SPA 도달)**:
   - `apps/web/vite.config.ts`의 `/v1` 프록시 대상에 `process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080'` 반영.
   - `tools/run_s02_real_api_acceptance.py`의 `start_frontend(port, backend_port)`에서 `VITE_API_PROXY_TARGET=http://127.0.0.1:{backend_port}` 환경변수를 주입하여 포트 변경 배치에서도 SPA `/v1` 호출이 정확한 백엔드 포트로 프록시되도록 완비.
2. **R2 (커밋 evidence의 도달 가능한 `gitCommitSha` 결속)**:
   - 코드 및 스크립트 수정사항을 먼저 Git에 커밋(`1ff1a016`)한 후, 해당 커밋 트리에서 커밋된 스크립트를 직접 실행하여 증거 JSON을 생성.
   - 생성된 evidence의 `gitCommitSha` (`1ff1a016...`)가 현재 HEAD의 조상(ancestor)으로 도달 가능함을 보장(#66 R4와 동일 기준 충족).
3. **관찰 권고 반영**:
   - `UNMEASURED` 종료 시 exit code 3 반환 (collector 2종과 통일).
   - `mockApiUsed`를 상수 false가 아닌 Playwright 라우트 등록 카운트(`mock_api_route_count > 0`)로부터 동적 유도.
   - 단언/타임아웃 예외 발생 시 `finally`/`except`에서 `FAILED` 증거 JSON을 남기도록 예외 핸들러 보강.

---

## 7. 검증 게이트 통과 내역 (최종 실측)

1. **Frontend 무결성 검사**:
   - `python -X utf8 tools/check_frontend_integrity.py`: **PASS** (83개 소스 파일 스캔, 9개 규칙 0 violations)
2. **TypeScript 컴파일 및 프로덕션 번들 생성**:
   - `cd apps/web && npx tsc -b`: **exit code 0** (타입 에러 0건)
   - `npm run build`: **exit code 0** (Vite 100 modules 프로덕션 번들 정상 생성)
3. **Frontend Vitest 전체 스위트**:
   - `npm test -- --run`: **77/77 test files passed, 673/673 tests passed** (exit code 0)
4. **화면-백엔드 라우트 커버리지 및 불변식 게이트**:
   - `pytest tests/test_route_coverage.py`: **39 passed** (exit code 0)
5. **문서 정합성 게이트**:
   - `python tools/check_docs.py`: **PASS** (844 versioned documents, exit code 0)
6. **S02-FE 실브라우저 4대 시나리오 실측**:
   - `.venv\Scripts\python.exe -X utf8 tools/run_s02_real_api_acceptance.py`: **ACCEPTANCE_PASSED** (4/4 passed, 0 mocks, exit code 0)

---

## 8. 결론 및 Claude / Codex 독립 재검토 인계

- Codex 보안 지적 S1(401 teardown 시 테넌트 상태 전량 초기화 및 generation 세대 검증)과 Claude 지적 R1(프록시 타겟 환경변수 연동), R2(도달 가능한 gitCommitSha 결속 및 exit 3/FAILED 기록)를 전면 완결하였습니다.
- 최신 tip 위에서 모든 게이트 통과를 실측 완료하였으므로 PR #77 재검토를 요청합니다.
