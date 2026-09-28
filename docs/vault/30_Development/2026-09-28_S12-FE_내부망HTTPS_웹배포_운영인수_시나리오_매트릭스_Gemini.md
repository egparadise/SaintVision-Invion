---
doc_id: "GEMINI-S12-FE-SCENARIO-MATRIX-20260928"
title: "S12-FE 내부망 HTTPS 웹 배포·운영 인수 시나리오 매트릭스 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T10:20:00+09:00"
source_of_truth: "Git"
tags: ["s12-fe", "acceptance-matrix", "https", "nginx", "tls", "release-manifest", "web-smoke", "recovery", "operator-training", "gemini"]
---

# S12-FE 내부망 HTTPS 웹 배포·운영 인수 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[2026-09-22_Codex_FE_review_map_S02-S12]] (33행: "배포 화면/manifest 단위 시험, 로컬 HTTPS smoke 골격과 manifest 일관성 검사")
> - [[2026-09-10_02-15-00_KST_S12-FE_Gemini_내부망HTTPS_웹배포_운영인수_개발과정]]
> - [[S12 파일럿]] (OUT-12 / AC-12)
> - [[설계 충돌 정정 및 ADR]]
> - `apps/web/src/features/deployment/IntranetDeploymentView.tsx`
> - `apps/web/src/features/deployment/deploymentEngine.ts`
> - `apps/web/tests/intranet-deployment.test.ts`
> - `apps/web/tests/deployment-release-integrity-wiring.test.tsx`
> - `apps/web/nginx.conf`
> - `apps/web/security-headers.conf`
> - `.github/workflows/desktop-browser.yml`
> - `tests/integration/test_web_container.py`
> - `tests/integration/test_studio_browser.py`
> - `tests/integration/test_desktop_browser.py`

---

## 1. 개요 및 수용 목표 (OUT-12 / AC-12)

본 문서는 SaintVision 제어 평면 및 릴리스 배포 서브시스템의 **S12-FE (내부망 HTTPS 웹 배포·운영자 인수·교육 화면)** 트랙을 체계적으로 검증하기 위해 수립된 **docs-only 시나리오 매트릭스 정본(v1.0.0)**이다.

S07~S11 선행 시나리오 매트릭스(PR #116, #123, #113, #144, #154)의 거버넌스 체계를 완벽히 계승하며, 코디네이터 지침, task-registry의 `S12-FE` 요구 증거("Release manifest·사용자 인수·웹 smoke·복구 Evidence"), Codex FE Review Map 33행("배포 화면/manifest 단위 시험, 로컬 HTTPS smoke 골격과 manifest 일관성 검사"), S12 개발과정 History 및 `S12 파일럿.md`의 수용 기준(`AC-12: 5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록`)을 프런트엔드 소스코드(`apps/web`), Nginx 리버스 프록시 명세(`apps/web/nginx.conf`), 그리고 CI 컨테이너 검증 파이프라인(`.github/workflows/desktop-browser.yml`, `tests/integration/test_web_container.py`)과 1:1로 대조하여 작성되었다.

### 1.1 핵심 작성 및 거버넌스 원칙 (Zero Fake / Honest Boundary)

1. **서버 계약 부재의 정직한 명시 (Release Manifest 미연결)**:
   - `deploymentEngine.ts:128-142`에 정의된 `releaseManifest`는 순수 클라이언트 정적 픽스처(`REL-2026-R4-GA`, `sha256:7f8e9d0c1b...`, commit `c323f55`)이다.
   - 백엔드 제어 평면(`services/control-plane`)에는 릴리스 매니페스트를 발행·조회하는 REST API 엔드포인트(예: `/v1/release-manifest`, `/v1/deployments/manifest` 등)가 존재하지 않는다.
   - 운영자 인수 서명 함수(`DeploymentManager.signOffRelease`) 또한 클라이언트 인메모리 객체의 boolean 필드(`operatorSignOff = true`)만을 토글할 뿐 서버 원장(Audit Ledger)이나 데이터베이스에 영속화되지 않는다.
   - 따라서 본 문서에서는 릴리스 매니페스트 서빙을 **"미연결 (서버 API 부재 · 클라이언트 정적 픽스처)"**로 명확히 규정하며, 서버 계약과 연동된 것처럼 가장하지 않는다.
2. **Web Smoke & Recovery 실측 체계의 정직한 분류**:
   - Web Smoke는 Nginx 리버스 프록시 컨테이너 기반 TLS 1.3 Strict 협상, HSTS 헤더, 정적 SPA 불변 캐싱, OAuth/PKCE 로그인, 및 401/404/503 오류 상태 보존으로 구성된다.
   - 본 검증은 Hosted CI의 `desktop-browser` 잡(`tests/integration/test_web_container.py`, `tests/integration/test_studio_browser.py`)에서 Docker 컨테이너 및 Playwright Chromium을 통해 실측된다.
   - 복구(Recovery)는 업스트림 제어 평면 컨테이너 중단 시 Nginx의 Fail-Closed(502/504) 단언 및 업스트림 재기동 후 200 정상 복구, 운영자 세션 만료 시 인증 오류 배너 표출 및 서명 차단 가드로 검증된다.
3. **외부 장비 의존 항목의 정직한 `BLOCKED_EXTERNAL` 격리 (꾸밈 없는 경계)**:
   - 사내 온프레미스 물리 서버에 대한 실제 사내 Enterprise Root CA 발급 및 Nginx TLS 1.3 물리 배포는 외부 인프라가 필요하므로 `BLOCKED_EXTERNAL`로 격리한다.
   - 5대 물리 장비(Windows 3대, Linux 2대) 사내망 클러스터 및 NVIDIA RTX A4000 GPU 물리 환경에서의 E2E 분산 여정 검증은 연구소 물리 랩이 필요하므로 `BLOCKED_EXTERNAL`로 격리한다.
   - 현장 운영 총괄자(`usr_operator_lead`)의 최종 실물 인수 서명 및 GA 가동 승인은 실제 물리 장비 운영 단계에서만 가능하므로 `BLOCKED_EXTERNAL`로 격리한다.
4. **허위 상태 표출 결함 백로그 (DEF-S12-01 ~ DEF-S12-08) 수록**:
   - 화면에 노출되는 '프로덕션 가동 승인 완료', '운영자 인수 완료 (docker compose up -d 가능)', 5노드 100% PASSED 하드코딩, 202건 통과 리터럴, Live Region 누락, 교육 4개 모듈 기본 completed 표출 등 프런트엔드 제품 코드 상의 8대 결함을 결함 백로그로 명문화한다.
   - docs-only 원칙에 따라 소스코드 변경은 일절 수행하지 않으며, 본 매트릭스 승인 후 후속 제품 수정 카드에서 착수한다.

---

## 2. 4대 핵심 검증 영역 구조

```
+---------------------------------------------------------------------------------------------------+
|                   S12-FE 내부망 HTTPS 웹 배포·운영 인수 시나리오 매트릭스 (Gemini)                 |
+---------------------------------------------------------------------------------------------------+
|  [SMK] Web Smoke 검증 (5개)                                                                       |
|  - SMK-01: TLS 1.3 Strict 협상, HSTS 강제 및 HTTP(:80) -> HTTPS(:8443) 301 리다이렉트             |
|  - SMK-02: 정적 SPA 에셋 immutable 캐싱 및 index.html, /callback, auth-config.js no-store         |
|  - SMK-03: Synthetic IdP 연동 PKCE 브라우저 로그인, 인메모리 토큰 전달 및 스토리지 잔류 방지    |
|  - SMK-04: 주요 포털 화면 라이브 렌더링 무오류성 (Studio, 승인센터, Web Desktop, NodeList, 배포) |
|  - SMK-05: 게이트웨이 오류 상태코드 보존 (401 인증 거부, 404 미존재 경로, 503 readyz 프록시)      |
+---------------------------------------------------------------------------------------------------+
|  [RCV] 장애 복구 및 격리 검증 (3개)                                                               |
|  - RCV-01: 제어 평면 컨테이너 Stop 시 Fail-Closed(502/504) 및 재기동(Start) 후 200 정상 복구     |
|  - RCV-02: 운영자 세션 만료(401) 또는 무효화 시 배포 화면 격리 (Alert 배너 및 서명 비활성화)    |
|  - RCV-03: 네트워크 단절 및 오프라인 복귀 (SSE 재연결 백오프 및 체크포인트 복구 화면)            |
+---------------------------------------------------------------------------------------------------+
|  [MAN] 릴리스 매니페스트 및 운영자 서명 검증 (3개)                                                |
|  - MAN-01: 릴리스 R4 매니페스트 메타데이터 및 다이제스트 정합성 (클라이언트 정적 픽스처 한계)     |
|  - MAN-02: 비인가 운영자 계정 서명 차단 가드 (usr_operator_/usr_admin_ 접두사 및 권한 검증)      |
|  - MAN-03: 운영자 모의 서명 실행 및 시뮬레이션 고지 배너 표출 (백엔드 배포 API 미노출 명시)      |
+---------------------------------------------------------------------------------------------------+
|  [TRN] 운영자 교육 및 훈련 가이드 검증 (2개)                                                      |
|  - TRN-01: 4대 필수 훈련 모듈 (2인 승인, 자원배치, Kill Switch, 무중단 롤백) 명세 및 안내        |
|  - TRN-02: 단계별 재실습 완료 트리거 및 인메모리 완료 갱신 (초기 로드 조기 완료 결함 식별)       |
+---------------------------------------------------------------------------------------------------+
|  [EXT] 외부 물리 장비 의존 검증 (3개, BLOCKED_EXTERNAL)                                           |
|  - EXT-01: 온프레미스 물리 서버 실제 TLS 1.3 / Nginx 배포                                         |
|  - EXT-02: 5노드 물리 사내망 분산 환경 (Windows 3대 + Linux 2대) 실가동 여정                      |
|  - EXT-03: 현장 운영 책임자(usr_operator_lead) 최종 실물 인수 서명 및 GA 가동 선언                |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. 상세 시나리오 매트릭스 (13개 핵심 시나리오 + 3개 외부 장비 의존 항목)

### 3.1. SMK: Web Smoke 시나리오 (5개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 |
|---|---|---|---|---|---|---|---|---|
| **SMK-01** | TLS 1.3 Strict 협상 및 HTTP 리다이렉트 | `apps/web/nginx.conf:22-48`, `tests/integration/test_web_container.py:119, :175` | Nginx 컨테이너 기동, 포트 80 및 443(호스트 임의포트) 바인딩, 인증서 마운트 | HTTP 포트 요청 및 HTTPS TLS 핸드셰이크 | `http://127.0.0.1:<port>/`, `https://127.0.0.1:<port>/studio` | 1. HTTP 요청 시 HTTP 301 반환 및 `Location: https://$host:8443...` 헤더 확인.<br>2. HTTPS 핸드셰이크 시 `TLSv1.3` (또는 `TLSv1.2`) 협상 성공.<br>3. `strict-transport-security: max-age=31536000; includeSubDomains` 헤더 존재.<br>4. 임의의 신뢰할 수 없는 CA 연결 시 `httpx.ConnectError` 거부 확인. | `hosted desktop-browser job` (`test_web_container.py:119, :175`) | **구현됨** (합성 컨테이너) |
| **SMK-02** | 정적 SPA 에셋 immutable 캐싱 및 인증 설정 no-store | `apps/web/nginx.conf:51-87`, `tests/integration/test_web_container.py:103` | Nginx 정적 SPA 파일(`/usr/share/nginx/html`) 마운트 완료 | `/studio`, `/callback`, `/auth-config.js`, `/assets/*.js` GET 요청 | HTTP 응답 헤더 `cache-control`, `x-content-type-options`, `x-frame-options` | 1. `/assets/*.js`: HTTP 200, `cache-control: public, immutable`, `expires: 1y`.<br>2. `/studio`: HTTP 200, `<div id="root"></div>` 포함.<br>3. `/callback`: HTTP 200, `cache-control: no-store`.<br>4. `/auth-config.js`: HTTP 200, `cache-control: no-store`, `mounted-public-client` 포함.<br>5. 전역 보안 헤더 `nosniff`, `DENY`, `no-referrer` 준수. | `hosted desktop-browser job` (`test_web_container.py:103`) | **구현됨** (합성 컨테이너) |
| **SMK-03** | Synthetic IdP 연동 PKCE 브라우저 로그인 | `tests/integration/test_studio_browser.py:112`, `apps/web/src/features/auth/Login.tsx` | Synthetic IdP 가동, Control Plane 가동, PostgreSQL business seeding 완료 | `/studio` 진입 후 `조직 계정으로 로그인` 버튼 클릭 | Playwright Chromium: `get_by_role('heading', name='SaintVision 로그인')`, `get_by_role('button', name='조직 계정으로 로그인')` | 1. PKCE Code Challenge(S256) 생성 및 IdP 리다이렉트.<br>2. 1회용 Authorization Code 교환 완료 (`valid PKCE exchange`).<br>3. `/v1/session` 200 OK 수신 및 사용자 세션 활성화.<br>4. 브라우저 `localStorage` 및 `sessionStorage`에 인증 토큰/자격증명 잔류 0건 (`length == 0`). | `hosted desktop-browser job` (`test_studio_browser.py:112`) | **구현됨** (합성 IdP + 브라우저) |
| **SMK-04** | 주요 포털 화면 라이브 렌더링 무오류성 | `apps/web/src/features/desktop/DesktopShell.tsx`, `IntranetDeploymentView.tsx`, `NodeList.tsx` | 로그인 성공 세션 보유, 프로젝트 콘텍스트 설정 | 탭 네비게이션 및 Web Desktop 전환 버튼 클릭 | Playwright Chromium: `get_by_role('button', name='Web Desktop으로 전환')`, `get_by_role('dialog', name='내 컴퓨터 (Resource Explorer)')` | 1. 렌더링 도중 `pageerror` 발생 0건 (`browser_errors == []`).<br>2. DesktopWindow 및 ResourceExplorer 다이얼로그 정상 표출.<br>3. 포털 뷰 복귀 시 헤더 및 배포 탭 접근 가능.<br>4. DOM 파괴 또는 치명적 런타임 크래시 부재. | `hosted desktop-browser job` (`test_studio_browser.py:161`) & `vitest` | **구현됨** (합성 브라우저) |
| **SMK-05** | 게이트웨이 오류 상태코드 보존 (401, 404, 503) | `tests/integration/test_web_container.py:155`, `test_studio_browser.py:122` | Nginx 리버스 프록시 및 백엔드 프로브 가동 | 유효하지 않은 토큰 로그인, 미존재 라우트 요청, `/readyz` 프로브 | `/v1/session`, `/v1/unknown`, `/readyz`, Playwright `get_by_role('alert')` | 1. 유효하지 않은 토큰(aud 불일치): HTTP 401 및 alert `서버가 인증 토큰을 허용하지 않았습니다.` 표출.<br>2. `/v1/unknown`: HTTP 404 및 `FIXTURE-404` JSON 보존.<br>3. `/readyz`: HTTP 503 및 `transport-fixture` JSON 보존. 상태코드 은폐/왜곡 없음. | `hosted desktop-browser job` (`test_web_container.py:155`, `test_studio_browser.py:122`) | **구현됨** (합성 환경) |

---

### 3.2. RCV: 복구 및 장애 격리 시나리오 (3개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 |
|---|---|---|---|---|---|---|---|---|
| **RCV-01** | 제어 평면 컨테이너 중단 시 Fail-Closed 및 재기동 복구 | `tests/integration/test_web_container.py:185`, `apps/web/nginx.conf:45, :90` | Nginx 및 업스트림 `control-plane` 컨테이너 정상 가동 중 | `docker stop --time 2 <upstream>` 후 `docker start <upstream>` | Nginx 프록시 엔드포인트 `/v1/session`, `/readyz`, docker inspect health | 1. 업스트림 중단 직후: 요청이 무한 대기하지 않고 즉시 502 Bad Gateway 또는 504 Gateway Timeout 반환 (Fail-Closed).<br>2. 업스트림 재기동 후: 최대 5초 이내에 `/v1/session` 200 OK 복구.<br>3. Nginx 컨테이너 헬스체크가 `healthy` 상태로 정상 회복. | `hosted desktop-browser job` (`test_web_container.py:185`) | **구현됨** (Docker 컨테이너) |
| **RCV-02** | 운영자 세션 만료 및 인증 토큰 무효화 시 배포 화면 격리 | `apps/web/src/features/deployment/IntranetDeploymentView.tsx:76-93, :525-539`, `deployment-release-integrity-wiring.test.tsx:71` | 운영자 로그인 세션 부재 (`currentUser === null`) 또는 토큰 만료 | `IntranetDeploymentView` 컴포넌트 렌더링 | `[data-testid="deployment-auth-required-notice"]` (`role="alert"`), `[data-testid="deployment-signoff-btn"]` | 1. `role="alert"`, `aria-live="assertive"` 속성을 가진 인증 필요 경고 배너 표출.<br>2. 배너 텍스트에 "🛑 인증 필요: 로그인된 운영자 세션이 없습니다" 포함.<br>3. 운영자 ID 입력창이 빈 값(`""`)으로 초기화.<br>4. 서명 버튼이 즉시 비활성화(`disabled=true`, `aria-disabled="true"`)되어 비인가 모의 서명 원천 차단. | `vitest` (`deployment-release-integrity-wiring.test.tsx:71`) | **구현됨** (컴포넌트 렌더링) |
| **RCV-03** | 네트워크 단절 및 오프라인 복귀 (SSE 재연결 및 분산 복구) | `apps/web/src/features/recovery/DistributedRecoveryView.tsx`, `nginx.conf:101-109` | 활성 실행 세션 중 네트워크 일시 단절 발생 | SSE 이벤트 스트림 끊김 및 브라우저 온라인 복구 이벤트 | SSE 이벤트 채널 `/v1/projects/.../events`, `DistributedRecoveryView` | 1. Nginx `proxy_buffering off` 설정에 따라 SSE 청크 지연 없음.<br>2. 네트워크 단절 시 클라이언트가 지수 백오프로 재연결 시도.<br>3. `DistributedRecoveryView`에서 체크포인트 스냅샷 및 Fencing Lease 상태 조회 가능.<br>4. *물리적 사내망 스위치 차단 실측은 제외.* | `vitest` (`recovery.test.ts`) / 실장비 물리 단절은 `BLOCKED_EXTERNAL` | **구현됨** (모의) / 실장비는 `BLOCKED_EXTERNAL` |

---

### 3.3. MAN: 릴리스 매니페스트 및 운영자 서명 시나리오 (3개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 |
|---|---|---|---|---|---|---|---|---|
| **MAN-01** | 릴리스 R4 매니페스트 메타데이터 및 다이제스트 정합성 | `apps/web/src/features/deployment/deploymentEngine.ts:128-142`, `IntranetDeploymentView.tsx:543-579` | `DeploymentManager` 인스턴스 초기화 | 컴포넌트 마운트 및 `getReleaseManifest()` 호출 | `[data-testid="deployment-unexposed-notice"]`, Release Version, Image Digest, Commit SHA DOM | 1. 릴리스 ID `REL-2026-R4-GA`, 버전 `v1.0.0-final-GA` 표출.<br>2. 불변 이미지 다이제스트 `sha256:7f8e9d0c1b...` (64자 hex) 형식 준수.<br>3. Git Commit SHA `c323f55` 일치.<br>4. 상단에 `data-testid="deployment-unexposed-notice"` 배너가 위치하여 **(백엔드 배포 API 미노출)** 및 클라이언트 시뮬레이션임을 명확히 고지. | `vitest` (`intranet-deployment.test.ts:77`) | **구현됨** (정적 픽스처) / 서버 API 연동은 `미연결 (서버 API 부재)` |
| **MAN-02** | 비인가 운영자 계정 서명 차단 가드 | `apps/web/src/features/deployment/deploymentEngine.ts:253-290`, `intranet-deployment.test.ts:89-106` | 유효하지 않은 운영자 ID 입력 (빈 문자열, 일반 사용자, 비인가 토큰) | `signOffRelease(operatorId, options)` 호출 | `dm.signOffRelease('')`, `dm.signOffRelease('arbitrary-actor')`, `dm.signOffRelease('usr_operator_lead', {roles: ['viewer']})` | 1. 빈 운영자 ID: `success: false`, 에러에 `Operator ID is required` 반환.<br>2. 비인가 계정(`arbitrary-actor`): `success: false`, 에러에 `Unauthorized operator` 반환.<br>3. unprivileged 토큰: `success: false`, 권한 서버 거부 에러 반환.<br>4. 인메모리 `manifest.operatorSignOff`가 여전히 `false` 유지. | `vitest` (`intranet-deployment.test.ts:89`) | **구현됨** (엔진 가드 로직) |
| **MAN-03** | 운영자 모의 서명 실행 및 시뮬레이션 고지 배너 표출 | `apps/web/src/features/deployment/IntranetDeploymentView.tsx:28-43`, `deployment-release-integrity-wiring.test.tsx:33` | 유효한 운영자 로그인 세션 (`currentUser.id === 'usr_operator_lead_99'`) | 서명 버튼(`[data-testid="deployment-signoff-btn"]`) 클릭 | `[data-testid="deployment-signoff-btn"]`, `actionNotice` DOM 텍스트 | 1. 버튼 클릭 시 `handleSignOff` 실행.<br>2. 결과 메시지에 `✔ [모의 시뮬레이션]` 접두어 및 `(백엔드 배포 API 미노출)`이 명시적으로 표출.<br>3. 서명자 ID `usr_operator_lead_99`가 정확히 반영.<br>4. 서명 버튼 텍스트가 `✔ 서명 완료됨`으로 전환되고 비활성화. | `vitest` (`deployment-release-integrity-wiring.test.tsx:33`) | **구현됨** (컴포넌트 렌더링) / 백엔드 원장 저장은 `미구현` |

---

### 3.4. TRN: 운영자 교육 및 훈련 가이드 시나리오 (2개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 |
|---|---|---|---|---|---|---|---|---|
| **TRN-01** | 4대 필수 운영 훈련 모듈 구성 및 안내 명세 | `apps/web/src/features/deployment/deploymentEngine.ts:144-173`, `IntranetDeploymentView.tsx:593-676` | `IntranetDeploymentView` Section 4 렌더링 | 컴포넌트 마운트 및 `getTrainingSteps()` 호출 | Section 4 모듈 리스트 4건 | 1. Step 1: `L0~L3 거버넌스 및 2인 승인 절차 (Two-Person Rule)` 존재.<br>2. Step 2: `5-Node 자원 배치 가중치 및 제외 규칙 모니터링` 존재.<br>3. Step 3: `응급 Kill Switch 발동 및 비인가 자원 즉각 격리` 존재.<br>4. Step 4: `1-클릭 웹 무중단 롤백 및 캐시 무효화 확인` 존재.<br>5. 각 단계별 구체적 실습 행동(actionRequired) 명시. | `vitest` (`intranet-deployment.test.ts:110`) | **구현됨** (컴포넌트 명세) |
| **TRN-02** | 단계별 재실습 완료 트리거 및 인메모리 완료 갱신 | `apps/web/src/features/deployment/deploymentEngine.ts:300-307`, `IntranetDeploymentView.tsx:45-54, :670` | 훈련 모듈 렌더링 상태 | 각 모듈의 `재실습 완료` 버튼 클릭 | `handleCompleteStep(stepNumber)`, `actionNotice` DOM | 1. `completeTrainingStep(stepNumber)` 호출 시 `success: true` 반환.<br>2. `actionNotice`에 `✔ 운영 교육 모듈 Step X 이수가 확인되었습니다.` 성공 안내 표출.<br>3. 인메모리 `trainingSteps` 상태가 불변 객체로 갱신.<br>4. *단, 초기 로드 시 모든 단계가 completed로 설정되어 있는 결함은 DEF-S12-08로 격리.* | `vitest` (`intranet-deployment.test.ts:120`) | **구현됨** (인메모리 갱신) |

---

### 3.5. EXT: 외부 물리 장비 의존 검증 항목 (3개, BLOCKED_EXTERNAL)

| 항목 ID | 항목 명 | 필요 환경 및 외부 전제 | 미수행 / 차단 사유 | 현재 상태 판정 |
|---|---|---|---|---|
| **EXT-01** | 온프레미스 물리 서버 실제 TLS 1.3 / Nginx 배포 | 사내 실제 공인/내부 도메인 DNS, 기업 엔터프라이즈 Root CA 인증서 발급, 물리 방화벽 포트 8443 개방, 리눅스 호스트 시스템 프로비저닝 | 개발 Agent 환경(로컬/CI)에서는 물리 온프레미스 서버 인프라에 접근할 수 없으며, 컨테이너 합성 테스트(`test_web_container.py`)로만 골격이 검증됨. | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |
| **EXT-02** | 5노드 물리 사내망 분산 환경 (Windows 3대 + Linux 2대) 실가동 | 연구소 내 고정 IP 할당 물리 PC 5대 (`192.168.1.101` ~ `105`), Windows 11/Server 3대, Linux Ubuntu 22.04 2대, NVIDIA RTX A4000 GPU 실제 장착 환경 | 물리적 사내망 LAN 환경 및 5대의 실장비 클러스터가 부재하여 E2E 물리 여정 검증 불가 (`deploymentEngine.ts:80-126`은 가상 상수 배열임). | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |
| **EXT-03** | 현장 운영 책임자(usr_operator_lead) 최종 실물 인수 서명 및 GA 가동 선언 | 실제 운영 총괄 책임자의 현장 실사, 실물 하드웨어 검수, 실제 사내망 접속을 통한 최종 GA 인계 서명 | 실제 운영 인수는 인간 운영 리드의 법적·운영적 승인 행위이며, 클라이언트 인메모리 시뮬레이션 버튼 클릭으로 대체할 수 없음. | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |

---

## 4. 발견된 8대 제품 결함 목록 (Defect Backlog: DEF-S12-01 ~ DEF-S12-08)

본 시나리오 매트릭스 수립 과정에서 `apps/web/src/features/deployment` 소스코드 분석을 통해 도출된 **8대 제품 결함 목록**이다. docs-only 거버넌스 원칙에 따라 본 문서에는 결함 분석 및 해결 계획만 수록하며, 실제 소스코드 수정은 본 매트릭스가 검토자(Claude, Codex)에 의해 승인된 후 후속 제품 수정 카드에서 착수한다.

### DEF-S12-01: 인메모리 모의 서명 후 상단 메트릭 카드의 '프로덕션 가동 승인 완료' 허위 표기 결함
- **심각도**: **HIGH** (거버넌스 및 상태 정직성 위반)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:140`
- **결함 내용**:
  ```tsx
  <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
    {manifest.operatorSignOff ? '프로덕션 가동 승인 완료' : '운영자 확인 대기 중'}
  </div>
  ```
  `handleSignOff` 실행 시 실제 물리 장치나 백엔드 배포가 이루어지지 않은 클라이언트 시뮬레이션임에도 불구하고, 메트릭 카드 하단에 `'프로덕션 가동 승인 완료'`라는 단정적인 문구를 노출하여 실제 상용 가동이 승인된 것으로 오인하게 만듦.
- **수정 계획**:
  `manifest.operatorSignOff ? '로컬 시뮬레이션 서명 완료 (실 환경 미배포)' : '운영자 확인 대기 중'`으로 정정.

### DEF-S12-02: 사전 검증 배너 우측의 '운영자 인수 완료 (docker compose up -d 가능)' 허위 표기 결함
- **심각도**: **HIGH** (실장비 미인수 상태 왜곡)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:207-209`
- **결함 내용**:
  ```tsx
  {manifest.operatorSignOff
    ? '운영자 인수 완료 (docker compose up -d 가능)'
    : '현장 운영자 인수 대기 (Pending Acceptance)'}
  ```
  모의 서명이 완료되면 온프레미스 물리 실장비 기동 준비가 완료되어 즉시 도커 컴포즈 가동이 가능한 것처럼 안내함. 실제 물리 장비 검수와 엔터프라이즈 CA 설치가 진행되지 않았으므로 심각한 과장 표기임.
- **수정 계획**:
  `manifest.operatorSignOff ? '모의 인수 절차 확인됨 (온프레미스 실장비 기동 별도 필요)' : '현장 운영자 인수 대기 (Pending Acceptance)'`로 정정.

### DEF-S12-03: 5노드 여정 테이블의 하드코딩 'PASSED ✔' 및 모의 지연시간 표출 결함
- **심각도**: **HIGH** (무결성 및 정적 리터럴 과장)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:462, :474`, `deploymentEngine.ts:80-126`
- **결함 내용**:
  `nodeVerifications` 배열에 정의된 5개 노드(Node-01~05)가 실제 네트워크 핑이나 상태 진단 없이 하드코딩된 `smokeStatus: 'passed'`, `latencyMs: 11, 14, 9, 18, 16` 수치를 무조건적으로 표시함. `clusterNodes` prop이 없을 때 실제 측정이 아님을 알리는 배지나 고지가 없음.
- **수정 계획**:
  테이블 상단 또는 상태 열에 `[모의/아키텍처 규격 예시 (실측 아님)]` 고지 추가. 실시간 원격 측정치가 없는 경우 지연시간을 `미측정`으로 표기하거나 규격 설계치임을 명시.

### DEF-S12-04: 사전 검증 배너의 '202/202 Checks PASS' 하드코딩 리터럴 결함
- **심각도**: **MEDIUM** (정적 숫자 과장)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:187, :190`, `deploymentEngine.ts:321`
- **결함 내용**:
  `deploymentEngine.ts:321`에서 `smokeChecksCount: 202, smokePassedRatio: 100.0`을 하드코딩하여 반환하고, 화면에 `내부망 배포 사전 검증 파이프라인 무오류 통과 (202/202 Checks PASS)`라고 고정 표기함. 실제 202건의 동적 테스트 파이프라인이 브라우저에서 실행된 것이 아님.
- **수정 계획**:
  `내부망 배포 사전 규격 설계 기준 (202개 검증 항목 설계 규격 PASS)` 또는 `[설계 규격 예시]`로 표기 정정.

### DEF-S12-05: `actionNotice` 알림 배너의 WAI-ARIA Live Region 속성 누락 결함
- **심각도**: **MEDIUM** (접근성 WCAG 2.1 AA 위반)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:146-160`
- **결함 내용**:
  ```tsx
  {actionNotice && (
    <div style={{ ... }}>
      {actionNotice.text}
    </div>
  )}
  ```
  서명 성공/실패 및 교육 모듈 이수 시 동적으로 나타나는 알림 배너 div에 `role="status"` (성공 시, polite) 또는 `role="alert"` (실패 시, assertive) 속성 및 `aria-live` 속성이 결여되어 있어 스크린 리더 사용자에게 변경 사실이 낭독되지 않음.
- **수정 계획**:
  `role={actionNotice.type === 'error' ? 'alert' : 'status'}` 및 `aria-live={actionNotice.type === 'error' ? 'assertive' : 'polite'}` 속성 추가.

### DEF-S12-06: 릴리스 매니페스트 메타데이터의 '미연결 (서버 API 부재)' 고지 누락 결함
- **심각도**: **HIGH** (서버 계약 경계 불투명)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:543-579`
- **결함 내용**:
  `manifest.imageDigest`, `manifest.builtCommitSha` 등이 마치 백엔드 릴리스 레지스트리에서 페치된 것처럼 표시되고 있으나, 실제로는 `deploymentEngine.ts:128-142`의 하드코딩 상수임. 섹션 내에 서버 API 미연결 상태임을 알리는 안내가 없음.
- **수정 계획**:
  섹션 상단 또는 카드 내부에 `[정적 픽스처 / 백엔드 릴리스 매니페스트 API 미연결]` 라벨 명시.

### DEF-S12-07: 운영자 인수 서명의 백엔드 감사 원장 영속화 부재 결함
- **심각도**: **MEDIUM** (아키텍처 영속성 미구현)
- **발생 위치**: `apps/web/src/features/deployment/IntranetDeploymentView.tsx:509-540`, `deploymentEngine.ts:292`
- **결함 내용**:
  운영자 서명 완료 시 브라우저 인메모리 `this.releaseManifest.operatorSignOff = true`만 수행될 뿐, 백엔드로의 POST 요청이나 감사 로그(`inv.audit_events`) 기록이 전무하여 새로고침 시 서명 상태가 즉시 소멸됨.
- **수정 계획**:
  백엔드 API 미노출 상태에서는 클라이언트 시뮬레이션임을 명확히 유지하고, 차후 백엔드 계약(`POST /v1/deployments/sign-off`) 신설 시 실제 영속화 연동 계획 수립.

### DEF-S12-08: 운영 교육 훈련 4개 모듈의 초기 로드 시 조기 완료(Early Completed) 표출 결함
- **심각도**: **MEDIUM** (교육 이수 상태 왜곡)
- **발생 위치**: `apps/web/src/features/deployment/deploymentEngine.ts:150, 157, 164, 171`, `IntranetDeploymentView.tsx:668`
- **결함 내용**:
  `trainingSteps` 초기 배열에서 모든 스텝(Step 1~4)의 `status`가 이미 `'completed'`로 설정되어 있어 사용자가 화면에 처음 진입했을 때 아무런 훈련도 수행하지 않았음에도 모든 모듈에 `'COMPLETED ✔'` 뱃지가 부여되어 있음.
- **수정 계획**:
  초기 상태를 `'pending'`으로 설정하고, 사용자가 `재실습 완료` 또는 각 실습 액션을 수행했을 때에만 `'completed'`로 전이되도록 로직 정정.

---

## 5. 증거 추적성 및 거버넌스 대조표 (Evidence Traceability)

| 요구 문서 및 기준 | 요구 항목 / 증거 명세 | 본 매트릭스 대응 시나리오 | 실제 검증 도구 및 실행 위치 | 검증 결과 및 증거 아티팩트 |
|---|---|---|---|---|
| **task-registry.json** (`OUT-12` / `AC-12`) | "Release manifest·사용자 인수·웹 smoke·복구 Evidence" | `SMK-01` ~ `SMK-05`, `RCV-01` ~ `RCV-03`, `MAN-01` ~ `MAN-03`, `EXT-01` ~ `EXT-03` | Hosted CI: `desktop-browser` workflow, Local: `vitest` | `.work/web-container-tests.xml`, `.work/web-container-studio.png`, `.work/vf-desktop-browser-ci.json` |
| **Codex FE Review Map** (33행) | "배포 화면/manifest 단위 시험, 로컬 HTTPS smoke 골격과 manifest 일관성 검사" | `SMK-01`, `SMK-02`, `MAN-01`, `MAN-02` | `apps/web/tests/intranet-deployment.test.ts` (7 tests) | 7/7 tests passed in Vitest (`npm test -- intranet-deployment`) |
| **Codex FE Review Map** (33행 닫힘 조건) | "5노드 내부망, TLS/Nginx 실제 배포, 사용자 인수·복구. 장비·운영 인수 필요" | `EXT-01`, `EXT-02`, `EXT-03` | 온프레미스 연구소 물리 장비 5대 및 현장 운영 인계 | **BLOCKED_EXTERNAL** (거짓 PASS 배제, 장비 투입 시 실측 예정) |
| **S12 파일럿 계획** (`AC-12`) | "5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록" | `MAN-01` (Known Limitations), `TRN-01` (4대 교육 훈련), `DEF-S12-03` (5노드 상수 격리) | `deploymentEngine.ts:136-140` (Known Limitations 3종 단언) | `intranet-deployment.test.ts:86` (`expect(knownLimitations.length).toBeGreaterThanOrEqual(3)`) |
| **거버넌스 배선 무결성 가드** | 운영자 행위자 실배선 및 미인증 서명 차단 가드 | `RCV-02`, `MAN-02`, `MAN-03` | `apps/web/tests/deployment-release-integrity-wiring.test.tsx` (Priority 7-A tests) | 2/2 tests passed in Vitest (`IntranetDeploymentView 운영자 행위자 실배선`) |
| **Nginx 프록시 무결성** | 업스트림 장애 격리 (Fail-Closed) 및 자동 재연결 | `RCV-01`, `SMK-01` | `tests/integration/test_web_container.py:185` | pytest pass in Hosted GitHub Actions Linux runner |

---

## 6. 결론 및 후속 인계 (Handoff)

1. **매트릭스 수립 완결**:
   - 본 문서는 S12-FE 내부망 HTTPS 웹 배포·운영자 교육 화면의 실측 가능한 13개 소프트웨어 시나리오(Web Smoke 5개, Recovery 3개, Release Manifest 3개, Training 2개)와 3개 외부 물리 장비 의존 항목(`BLOCKED_EXTERNAL`)을 정직하게 수립하였다.
   - 백엔드 제어 평면과의 실제 라우트 연동 여부를 엄격히 검증하여, 배포 매니페스트 서빙이 `미연결 (서버 API 부재 · 클라이언트 정적 픽스처)` 상태임을 명시하였다.
   - 화면에 노출되는 8대 허위 상태 및 접근성 결함을 `DEF-S12-01` ~ `DEF-S12-08`로 체계화하여 결함 백로그를 확정하였다.
2. **독립 검토 요청 (Review Request)**:
   - **Claude (UI 경로 축)**:
     - `apps/web/src/features/deployment` 컴포넌트의 실제 DOM 셀렉터, 8대 제품 결함(특히 DEF-S12-01, DEF-S12-02의 허위 승인 문구 및 DEF-S12-05 ARIA 속성 누락)의 타당성 검토.
   - **Codex (계약 축)**:
     - Nginx 라우팅 매트릭스(`nginx.conf`) 및 TLS 1.3 Strict Mode 정합성 검토.
     - 배포 매니페스트의 백엔드 API 부재 판정 및 `signOffRelease` 인메모리 격리 구조 검토.
     - 5노드 물리 환경 및 실제 배포 항목의 `BLOCKED_EXTERNAL` 격리 적절성 검토.
3. **다음 착수 카드**:
   - 본 docs-only 매트릭스 PR 승인 후, 도출된 8대 결함을 치유하는 **S12-FE 제품 결함 수정 카드(apps/web 코드 수정, owner Gemini, reviewer Claude UI / Codex 계약)**로 전환한다.
