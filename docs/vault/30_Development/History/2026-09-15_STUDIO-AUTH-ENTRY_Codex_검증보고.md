---
doc_id: "HIST-STUDIO-AUTH-ENTRY-REPORT-20260915"
title: "2026-09-15 STUDIO-AUTH-ENTRY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:54:21+09:00"
source_of_truth: "Git"
---

# 2026-09-15 STUDIO-AUTH-ENTRY Codex 검증보고

[[2026-09-15_STUDIO-AUTH-ENTRY_Codex_착수]]에서 이어 진행했다. 작업 CX-01 후속, owner Codex. 제품 SHA `33d63d52074e11f78065aabaf3af3678c02f8b82`, branch agent/codex/approval-browser. 구현·로컬 검증·commit·origin push 완료. Claude 독립 검토와 Gemini 화면 인수는 대기다.

## 구현과 확인

기존 `/` 관측 화면을 보존하고 `/studio`에서 실제 App 로그인으로 진입한다. `/callback`은 동일 인증 트랜잭션을 완료한다. 기존 가짜 auth_code와 미등록 `/v1/auth/token` fallback을 제거했다. 외부 token endpoint에는 form과 원래 redirect URI·PKCE verifier를 보내고 API Bearer/traceparent를 전달하지 않는다. state 중복·불일치·만료·설정 변경을 차단하고 한 번만 코드를 교환한다. StrictMode도 단일 교환을 공유한다. Access Token은 메모리에만 남으며 새로고침은 재로그인이 필요하다.

`GET /v1/session`과 SessionView 공통 계약을 추가했다. 실제 커널 RS256/JWKS 검증 결과에서 canonical subject·설정 tenant·만료 시각만 반환한다. 표시 사용자도 이 결과를 쓰므로 원시 JWT sub와 커널 subject의 불일치를 제거했다. 사용자별 역할·권한을 JWT payload에서 가져오지 않는다. 권한은 기존 DB 경계가 계속 강제한다.

프로젝트 조회는 configured kernel의 `items`와 optional business의 `projects` 응답을 명시적으로 구분한다. 커널 목록은 ID만 표시하며 business 이름·생성 시각·연결 상태를 지어내지 않는다. 상태 형식이 모호하면 거절한다. 로그아웃은 메모리 토큰과 선택 프로젝트·승인·실행 정보를 제거한다. 헤더의 초기 임의 RTT/Node 기본값도 제거하고 `/readyz`를 조회한다.

실제 전체 페이지에서 메뉴 줄바꿈 문제와 미수신 롤백 계획을 없다고 단정하는 문구를 발견해 수정했다. public auth-config.js는 비밀 없는 운영 설정 자리만 제공한다. Service Worker는 인증 설정·callback·API·외부 주소를 캐시하지 않게 했고 Nginx callback 로그 제외·설정 no-store·readyz proxy를 추가했다. **Nginx/TLS 실제 컨테이너 검증과 배포는 다음 작업이며 완료로 세지 않았다.**

## 검증 Evidence

- `npm test -- --reporter=dot`: 최종 27파일 233개 통과, 6.61초, exit 0.
- `npm run build`: TypeScript와 Vite 통과, Vite 8.07초, exit 0. 이번에는 전체 App lazy chunk도 빌드한다.
- `python tools/run_approval_browser_test.py`: 격리 Docker PostgreSQL·configured factory·실제 Edge, 최종 38개 통과/64.66초, exit 0. 이 중 브라우저 4여정(기존 component 2 + full App 2), 인증 검사 34개다. 관행적 TestClient 경고 2개가 남는다.
- 합성 IdP HTTP 서버가 단일 사용 code·client·redirect·S256을 검증한다. 실제 `/studio`→redirect→토큰 교환→서버 사용자 검증→허용 프로젝트→승인 DB 1표 저장→로그아웃 및 토큰/내용 제거를 확인했다. 다른 audience 토큰은 401, 프로젝트 접근/투표 없음으로 확인했다. Playwright 응답 가로채기 없음.
- `python -m pytest -q tests/core/test_approval_contracts.py`: 10개 통과/4.24초, exit 0. 잘못된 `tests/core/test_contracts.py` 경로 실행은 시험 0개/exit 1이라 통과 수에 넣지 않았다.
- `python tools/generate_contracts.py`: Python/TS/Go/schema 생성 exit 0. 생성 Go의 별도 compile은 이번 작업에서 수행하지 않았다.
- Evidence: `../Evidence/studio-auth-33d63d5.json`, 실제 화면 `../Evidence/studio-auth-33d63d5.png`.

## CI·외부 인계

동일 SHA CI: Backend 34865090701, Core 34865090758, Docs 34865090753, Frontend 34865090697. 모두 결제/한도 제한으로 job 미시작. `../Evidence/studio-auth-ci-33d63d5.json`. 로컬 통과를 CI 통과로 대체하지 않는다.

Obsidian 3파일의 외부 변경을 `../Evidence/obsidian-proposals-20260915-studio-auth/`에 원문·hash로 보존했다. 이전 보존본 대비 공통/Gemini는 동일, 인계 목록은 Claude의 578db00 auth 검토가 추가됐다. Claude는 payload decode가 UI 표현이고 커널은 검증된 토큰을 강제하므로 권한 상승이 아니라고 보고했다. 이 경계 설명은 현재 코드와 일치한다. 이번 수정의 동기는 실제 로그인 프로토콜/식별자/상태 연결이며 기존 변경을 백엔드 권한 우회 취약점으로 분류하지 않는다. Claude가 지적한 deploymentEngine의 표시용 signoff를 실제 운영 승인으로 믿지 말라는 내용도 인계한다. Claude 보고를 이번 33d63d5의 독립 검토로 간주하지 않는다.

## 다음 작업과 완료율

Codex: `/studio`의 실제 Nginx/TLS/설정 주입과 business 프로젝트 표면까지 격리 배포 검증 후, Workspace 생성·편집·실행·결과 흐름을 계약에 맞춰 연결한다. 운영 IdP 설정·원격 .225의 실행 프로필/7시험·운영 DB 업그레이드·CI·main 병합 인수는 별도 남아 있다. 이번에는 원격 장비 상태를 새로 관측하지 않았다.

Claude: 33d63d5 인증/session/프로젝트 계약 독립 검토, 운영 IdP·계정/프로젝트 권한 설정, 표시용 signoff의 backend 강제 경계 검토.

Gemini: 공유 브랜치로 후보를 검토·통합하고 전체 App 접근성/반응형/상태 표시를 인수한다. 기존 578db00 Login과 병행 정본을 만들지 않는다.

전체 공식 완료율 **57.8125% (2775/4800), 남은 42.1875%** 유지. 로컬 후보 검증 진전이며 독립 검토·운영 인수 완료가 없어 단계 가중치를 올리지 않았다. 문서 검사·Obsidian 동기화 결과는 아래에 후속 기록한다.
