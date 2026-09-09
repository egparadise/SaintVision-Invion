---
doc_id: "PLAN-FRONTEND-001"
title: "Frontend 최종 개발 계획"
version: "1.0.0"
status: "baseline"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Frontend 최종 개발 계획

책임: **Gemini / Antigravity**. 공통 기준은 [[최종 개발 계획 - 모든 개발의 지침]], 주차별 작업은 [[24주 통합 실행 계획]]을 따른다.


## 구조와 책임

React·TypeScript·Vite SPA, TanStack Router/Query, UI 전용 Zustand, Monaco 편집·diff, xterm.js를 사용한다. 디자인·Frontend·웹 배포는 Gemini가 Antigravity에서 담당한다. 한국어 기본·영어 리소스 병행, light/dark, 의미 토큰과 키보드 탐색을 제공한다.

초기 화면은 로그인, `/nodes`, Node 상세, Project/Workspace, `/runs`, Run 상세·로그·Artifact·Explain, 승인·감사, 도구 설정·MLOps다. 모든 화면은 loading/empty/error/forbidden/partial-failure 상태를 가진다.

## API·상태

공통 JSON Schema에서 생성한 TS 타입과 런타임 검증을 사용한다. 서버 상태는 Query, 레이아웃·터미널 탭은 Zustand가 소유한다. 빈 화면을 권한 오류 대신 표시하지 않는다. 오류에는 안전한 message·code·traceId를 제공한다.

OIDC Code+PKCE, access token 메모리 저장, refresh httpOnly/Secure cookie, CSRF·Origin 검사, refresh single-flight를 적용한다. SSE는 fetch 스트림으로 Bearer와 last-event-id를 지원하고 cursor 만료 시 REST snapshot으로 재동기화한다. WS ticket은 1회·30초이며 URL/토큰을 로그에 남기지 않는다.

승인 화면은 대상·변경 diff·영향·비용·rollback·만료·정책 근거를 표시한다. diff 미조회·만료·권한 없음이면 제출 불가다. 같은 사람이 two-person 승인을 두 번 할 수 없고 서버에서도 검증한다.

## 배포

내부망 HTTPS 동일 origin으로 `/` 정적 SPA, `/v1` API/SSE/WS를 reverse proxy한다. TLS·DNS·IdP redirect 값은 S01 장비 조사에서 확정한다. 웹 bundle에 secret을 넣지 않는다. SSE buffering 비활성·WS upgrade·deep-link fallback·cache busting을 검증한다. Gemini는 immutable image digest와 이전 digest로 rollback하며 Codex가 보안 설정을 검토한다.

## 검증

Vitest/Testing Library: 승인 만료, 갱신 경합, 오류 상태, 이벤트 중복 제거. Playwright: 실제 compose 인증·SSE·WS·편집·승인·다운로드 종단간. 키보드·명도 대비·light/dark 시각 회귀를 포함한다. 단말은 접근 가능한 텍스트 로그 대체 뷰를 제공한다.
