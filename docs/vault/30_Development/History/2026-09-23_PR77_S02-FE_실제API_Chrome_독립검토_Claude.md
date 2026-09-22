---
doc_id: "HIST-CLAUDE-PR77-S02-FE-REAL-API-REVIEW-001"
title: "PR #77 S02-FE 실제 API Chrome 로그인·Node 0대·401/403(Gemini, 38ae8544) 독립 검토 — 실 백엔드·실 DOM/wire 단언은 성립하나 재현성(미추적 IdP·env·포트 인자 무시·dev DB 상태 의존)·프로덕션 시험 훅/하드코딩·계약 완화(RULE-9 위반)·증거 상수 → 수정 요청"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Gemini"
updated: "2026-09-23T00:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-77", "s02-fe", "real-api", "chrome", "zero-mock", "gemini", "reproducibility"]
---

# PR #77 독립 검토 — S02-FE 실제 API Chrome 수용

대상 `agent/gemini/s02-fe-real-api` head **`38ae8544`**(`b3f6db05` 구현 + docs). 검토 트리 `.worktrees/claude-rev77`(detached). 기준은 #66 r1~r4에서 쓴 것과 동일: 단언이 실 DOM/네트워크인가, 증거가 커밋 스크립트로 재생성되는가(상수 금지), 401/403이 실 백엔드 응답인가, 로그인/세션 보안 경계가 약화되지 않았는가. 보안 관점은 Codex 위임(한 줄).

## 판정: **수정 요청** (F1~F4)

## 1. 실측

| 검증 | 결과 |
|---|---|
| 백엔드 실물 여부 | `tools/run_s02_real_api_acceptance.py`가 `uvicorn saintvision.server:create_app --factory`를 기동, `page.route` mock 없음 → **실 백엔드** |
| 단언 | 로그인: IdP `/authorize` 302·`/token` 200·`/v1/session` 200(wire) + Header/Logout DOM · Node: `/v1/projects/{prj}/nodes` 200·`items` 배열·빈 상태 문구 DOM · 403: `direct-project-input`로 미인가 project → `app-run-error` `role=alert` 텍스트에 `AUTH-0030`·detail + wire 403·`application/problem+json`·code/detail · 401: wire 401·problem+json·`AUTH-0050` + `login-error-alert` + 재로그인 DOM → **실 DOM/wire 단언** |
| 증거 SHA | `gitCommitSha` 동적(`git rev-parse HEAD`), 값 `b3f6db05` = head 부모; `b3f6db05`↔`38ae8544` 스크립트·앱 diff 0 → 커밋 스크립트와 정합 |
| 게이트 | `tsc --noEmit` exit 0 · `route_coverage` 46/unserved 0 · vitest 6파일(`project-list-response-contract`·`auth-session`·`api-proxy`·`auth-pkce`·`node-fetch-error-workspace-wiring`·`accessibility-status-and-guards`) **56 passed** · **`check_frontend_integrity` RULE-9 위반 1**(`projectObservation.ts:7 apiClient<any>`; tip은 0) |
| 재현 시도 ① | clean worktree: `FileNotFoundError: dev_idp.py not found at …/.work/dev/dev_idp.py` — 스크립트가 미추적 `.work/dev`(IdP·`server.env`)에 의존 |
| 재현 시도 ② | 주 트리 `.work` junction(읽기 전용) + 포트 분리(3016/8081/8091): `Timeout waiting for Dev IdP on port 8091` — `--idp-port`가 `dev_idp.py`에 전달되지 않음(8090 고정) |

브라우저 단계에는 도달하지 못했다(지시된 1회 재현 소진). 판정은 코드·커밋 증거·게이트 기준.

## 2. 발견
- **F1 재현성** — 미추적 IdP·env 의존, IdP 포트 인자 무시, 시나리오 2·3이 dev DB의 기존 project(`prj_01M33NGQEZTB2QD1CWV97Y7DSN`)·subject 권한 상태에 의존(스크립트가 seed하지 않음). 증거는 작성자 PC에서만 재생성된다. 요구: 포트 인자 반영, 의존 추적화 또는 명시 인자, 일회용 DB seed(불가 시 UNMEASURED).
- **F2 프로덕션 코드** — `App.tsx`의 `window.__chooseProject/__setActiveTab/__simulateTokenExpired`, `console.log('[Header onSelectTab]')`, dev project id 하드코딩 폴백. "토큰 만료" 시나리오의 트리거는 가짜 토큰(`invalid_or_expired_token`)이라 만료가 아닌 무효 토큰 401 — 라벨 정정 또는 실제 만료 토큰.
- **F3 계약 완화** — `projectObservation.ts` `apiClient<any>`·필수 필드 검증 제거·기본값 합성(`createdAt`·`kernelLinked`·`kernelEnabled`), RULE-9 위반 신규; `isRouteNotFoundError`가 `Request unavailable`/`HTTP-0001`(일반 404)까지 route 부재로 판정 → 폴백 과잉.
- **F4 증거 상수** — `assessment`·`operationalAcceptanceAssessed`·`mockApiUsed`·`realUvicornUsed`·`realDevIdPUsed`는 무조건 기록(관측 아님).

## 3. 보안(Codex 위임 한 줄)
401 전역 핸들러는 in-memory 토큰만 지우고 저장 방식(메모리 전용)은 불변 — 약화 없음으로 보이나, 프로덕션 번들의 `__simulateTokenExpired` 훅과 broadened 404 폴백의 권한 경계 영향은 Codex 확인 요청.

## 4. 요구(재검토 전)
F1 재현성(포트·의존·seed) → F2 훅/로그/하드코딩 제거·라벨 정정 → F3 생성 타입·검증 복원, RULE-9 0 → F4 상수 제거. 그 뒤 커밋 스크립트로 증거 재생성. 코멘트: PR #77.
