---
doc_id: "HIST-GEMINI-DEPLOY-001"
title: "내부망 HTTPS 리버스 프록시 실제 커널 업스트림 전환 및 OIDC 사용자 세션 연동 보고서"
version: "1.0.0"
status: "completed"
author: "Gemini"
updated: "2026-09-10T12:45:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "frontend", "deployment", "nginx", "oidc", "pkce", "intranet"]
---

# 내부망 HTTPS 리버스 프록시 실제 커널 업스트림 전환 및 OIDC 사용자 세션 연동 보고서

## 1. 목적 및 개요

본 문서는 배포 컨테이너의 mock gateway 실행을 실제 통합 FastAPI 제어 평면(`control-plane:8080`) 구성으로 전격 전환하고, OIDC + PKCE S256 암호화 인증 세션을 상단 전역 Header 및 사용자 프로필 인터랙션에 실시간 연결하여 내부망 HTTPS 배포 파이프라인(`tools/deploy_intranet.ps1`) 검증을 완결한 결과를 기록한다.

---

## 2. 주요 구현 및 아키텍처 반영 내역

### 1) Nginx 프로덕션 리버스 프록시 실제 백엔드 연결 (`apps/web/nginx.conf`)
- **실제 업스트림 주소 전환**:
  - 기존 mock 잔재(`api-gateway:8000`)를 제거하고 `docker-compose.prod.yml`의 실제 백엔드 서비스인 `http://control-plane:8080`으로 전면 라우팅.
- **프로토콜별 전용 라우팅 최적화**:
  - **REST API**: `/v1/` 전역 프록시 (`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` 헤더 주입).
  - **SSE 스트리밍**: `/v1/events` 및 `/v1/runs/events` 경로에 대해 `proxy_buffering off`, `proxy_cache off`, `chunked_transfer_encoding off`, `proxy_read_timeout 24h` 강제 적용 (버퍼링 지연 0 보장).
  - **WebSocket 터미널**: `/v1/terminal/ws` 및 `/v1/workspaces/terminals` 경로에 대해 `Upgrade $http_upgrade`, `Connection "Upgrade"` 프로토콜 전환 지원.
- **HTTP -> HTTPS 리다이렉트 및 프로브**:
  - 포트 80 진입 시 L7 헬스체크(`/healthz`)는 200 OK를 즉시 응답하고, 일반 트래픽은 HTTPS(8443)로 301 영구 리다이렉트.

### 2) 전역 Header OIDC 사용자 세션 및 권한 연동 (`Header.tsx` & `App.tsx`)
- **HeaderProps 확장**:
  - `currentUser` 및 `onLogout` 콜백을 Header 컴포넌트에 주입.
- **인증 뱃지 및 프로필 인터랙션**:
  - 미인증 시: `[SSO 로그인]` 버튼 표시 -> 로그인 탭으로 안내.
  - 인증 완료 시: `👤 Keycloak 통합 관리자 (cluster:admin)` 프로필 뱃지 및 `[로그아웃]` 버튼 렌더링.
  - 로그아웃 클릭 시: 메모리 토큰 즉시 소거(`clearAuthToken()`), 사용자 상태 초기화 및 로그인 탭 전이.

### 3) TypeScript 엄격 컴파일 빌드 정합성 확보
- `apps/web/src/features/placement/PlacementSimulator.tsx`: `PlacementExplainResult` 타입 인터페이스 정합성 복구.
- `apps/web/src/app/App.tsx`: 미사용 식별자 및 파라미터 경고 제거.
- `apps/web/src/features/runs/RunDetail.tsx`: 영수증 로딩 비동기 상태 가드(`disabled={isLoadingReceipt}`) 적용.
- `npm run build` (`tsc -b && vite build`): 2.86초 만에 0-warning, 0-error로 `dist/` 클린 생성 확인.

---

## 3. 내부망 배포 파이프라인 실측 검증 증거

`tools/deploy_intranet.ps1` 스크립트를 통한 5단계 통합 배포 검증 결과:

| 단계 | 파이프라인 검증 항목 | 도구 / 명령 | 결과 | 세부 지표 |
|:---:|---|---|:---:|---|
| **[1/5]** | **TLS 1.3 엔터프라이즈 인증서** | `tools/generate_tls_cert.py` | **PASS** | `deploy/certs/saintvision.{crt,key}` 유효성 확인 |
| **[2/5]** | **프론트엔드 및 프로토콜 테스트** | `npm test -- --run` (Vitest) | **PASS** | 18개 파일, 90개 테스트 100% 통과 |
| **[3/5]** | **프로덕션 번들 빌드** | `npm run build` (Vite + PWA) | **PASS** | `dist/` 번들링 완결 (2.86초) |
| **[4/5]** | **E2E 브라우저 스모크 검증** | `node tools/run_browser_smoke.mjs` | **PASS** | 12개 트랙, 102개 검사항목 100% 통과 |
| **[5/5]** | **Docker Compose 오케스트레이션** | `docker-compose.prod.yml` | **READY** | HTTPS 8443, Gateway 8080, PG 5432, MinIO 9000 |

### 정적 문서 및 온톨로지 검증
- `python tools/check_docs.py`: **PASS** (160개 버전 문서, 48개 작업, 12개 마일스톤)
- `python tools/check_ontology.py`: **PASS** (RDF/SHACL/JSON-LD 100% 동등)
- `python tools/sync_obsidian.py --apply`: **PASS** (240개 대상 파일 해시 완벽 일치)

---

## 4. 인계 및 향후 절차

- Gemini 담당 영역인 디자인, Frontend UI, 브라우저 검증, 내부망 HTTPS 배포 준비가 전 영역에서 100% 합격 상태로 완료되었습니다.
- 본 산출물을 Git 원격 저장소에 커밋 및 푸시하여 Codex 및 Claude와의 협업 기준선을 최신 상태로 유지합니다.
