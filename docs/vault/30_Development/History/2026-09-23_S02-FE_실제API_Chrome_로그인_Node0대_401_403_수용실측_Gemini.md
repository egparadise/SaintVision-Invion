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

## 5. 검증 게이트 통과 내역

1. **TypeScript 컴파일 및 프로덕션 번들 생성**:
   - `cd apps/web && npx tsc -b`: **exit code 0** (타입 에러 0건)
   - `npm run build`: **exit code 0** (Vite 100 modules 프로덕션 번들 정상 생성)
2. **화면-백엔드 라우트 커버리지 및 불변식**:
   - `pytest tests/test_route_coverage.py`: **38 passed** (exit code 0)
3. **문서 정합성 게이트**:
   - `python tools/check_docs.py`: **PASS** (829 versioned documents, exit code 0)
4. **Git Diff 무결성**:
   - `git diff --check`: **CLEAN** (0 whitespace/formatting errors)

---

## 6. 결론 및 Claude 독립 검토 인계

- S02-FE 요구사항(실제 백엔드/IdP 연동, OIDC 로그인 성공, Node 0대 정직 표출, 401/403 RFC 9457 ProblemDetails 에러 표출 및 재로그인 복구)에 대해 실제 Chrome 153 브라우저를 통한 무목(Zero Mock) 수용 실측을 100% 완료하였습니다.
- 코디네이터 지침에 따라 리뷰어 Claude에게 PR 독립 검토를 인계합니다.
