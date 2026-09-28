---
doc_id: "GEMINI-S12-FE-SCENARIO-MATRIX-20260928"
title: "S12-FE 내부망 HTTPS 웹 배포·운영 인수 시나리오 매트릭스 (Gemini)"
version: "1.0.3"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T11:09:00+09:00"
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
> - [[3 Agent 원격 실행과 운영 인수 확정]] (15행: 실제 원격 Node 1대 192.168.45.225 및 서버 192.168.45.99 기록)
> - [[설계 충돌 정정 및 ADR]]
> - [[2026-09-23_03-10-00_KST_CP호스트_Node겸임_ADR100_Codex]] (ADR-100: CP 호스트 겸임 Node 1 + 독립 Ubuntu Worker 4)
> - `apps/web/src/features/deployment/IntranetDeploymentView.tsx`
> - `apps/web/src/features/deployment/deploymentEngine.ts`
> - `apps/web/src/features/recovery/DistributedRecoveryView.tsx`
> - `apps/web/tests/intranet-deployment.test.ts`
> - `apps/web/tests/deployment-release-integrity-wiring.test.tsx`
> - `apps/web/nginx.conf`
> - `apps/web/security-headers.conf`
> - `.github/workflows/desktop-browser.yml`
> - `tests/fixtures/nginx_transport.py`
> - `tests/integration/test_web_container.py`
> - `tests/integration/test_studio_browser.py`
> - `tests/integration/test_desktop_browser.py`
> - `src/saintvision/db/models/operations_pilot.py` (ReleaseManifest:221, AcceptanceRecord:251)
> - `src/saintvision/services/pilot.py` (create_release_manifest:358, record_acceptance:396)

---

## 1. 개요 및 수용 목표 (OUT-12 / AC-12)

본 문서는 SaintVision 제어 평면 및 릴리스 배포 서브시스템의 **S12-FE (내부망 HTTPS 웹 배포·운영자 인수·교육 화면)** 트랙을 체계적으로 검증하기 위해 수립된 **docs-only 시나리오 매트릭스 정본(v1.0.3)**이다.

S07~S11 선행 시나리오 매트릭스(PR #116, #123, #113, #144, #154)의 거버넌스 체계를 계승하며, 코디네이터 지침, task-registry의 `S12-FE` 요구 증거("Release manifest·사용자 인수·웹 smoke·복구 Evidence"), Codex FE Review Map 33행("배포 화면/manifest 단위 시험, 로컬 HTTPS smoke 골격과 manifest 일관성 검사"), S12 개발과정 History 및 `S12 파일럿.md`의 수용 기준(`AC-12: 5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록`), 그리고 ADR-100의 5노드 토폴로지(CP 호스트 겸임 Node 1 + 독립 Ubuntu Worker 4)를 프런트엔드 소스코드(`apps/web`), Nginx 리버스 프록시 명세(`apps/web/nginx.conf`), CI 컨테이너 검증 파이프라인(`.github/workflows/desktop-browser.yml`, `tests/integration/test_web_container.py`, `tests/integration/test_studio_browser.py`)과 1:1로 엄격히 대조하여 작성되었다.

### 1.1 핵심 작성 및 거버넌스 원칙 (Zero Fake / Honest Boundary)

1. **서버 도메인 모델 실재와 REST 라우트 부재의 정직한 명시 (Release Manifest 미연결)**:
   - 백엔드 제어 평면에는 이미 도메인 모델 및 서비스(`src/saintvision/db/models/operations_pilot.py:221` `ReleaseManifest`, `:251` `AcceptanceRecord`, `src/saintvision/services/pilot.py:358` `create_release_manifest`, `:396` `record_acceptance`)가 존재한다.
   - 그러나 `services/control-plane/src/inv/app.py`에 다수의 라우트 데코레이터가 존재함에도 불구하고, release manifest 및 acceptance 서명을 외부에 노출하는 REST API 라우트(`release-manifest`, `deployments/sign-off` 등) 검색 결과는 0건이다 (`app.py:268 /healthz`, `:272 /readyz`, `:297 /v1/session` 등 헬스·세션 계열만 존재).
   - 반면 `apps/web/src/features/deployment/deploymentEngine.ts:128-142`의 `releaseManifest`는 순수 클라이언트 정적 픽스처(`REL-2026-R4-GA`, `sha256:7f8e9d0c1b...`, commit `c323f55`)이다.
   - 운영자 인수 서명 함수(`DeploymentManager.signOffRelease`) 또한 클라이언트 인메모리 객체의 boolean 필드(`operatorSignOff = true`)만을 토글할 뿐 서버 원장이나 데이터베이스에 영속화되지 않는다.
   - 따라서 본 문서에서는 릴리스 매니페스트 서빙을 **"미연결 (UNMEASURED: 서버 도메인 모델 실재하나 REST 라우트 부재 · 클라이언트 정적 픽스처)"**로 명확히 규정하며, 서버 계약과 연동된 것처럼 가장하지 않는다.
2. **Nginx TLS 프로토콜 협상 규격의 정확한 반영 (F-R1 및 Claude 1 정정)**:
   - `apps/web/nginx.conf:42`의 실제 설정은 `ssl_protocols TLSv1.2 TLSv1.3;`이며, `:43`은 `ssl_ciphers HIGH:!aNULL:!MD5;`이다.
   - CI 시험 `tests/integration/test_web_container.py:124` 역시 `('TLSv1.2', 'TLSv1.3')` 협상을 수용한다.
   - 따라서 SMK-01은 **"TLS 1.2 이상 협상 (1.3 전용 아님)"**으로 바로잡으며, 화면의 `TLS 1.3 (STRICT)` 표출(`IntranetDeploymentView.tsx:106`, `:194`)은 결함(DEF-S12-09, DEF-S12-13)으로 기록한다. 엄격한 "TLS 1.3 단독 강제(Strict TLS 1.3-only)"는 현재 설정상 미강제 상태이며 미측정(`UNMEASURED`)으로 분리한다.
3. **관측 경로의 엄격한 분리: HTTPS Nginx 컨테이너 vs HTTP Vite 개발 서버 (Claude 2 정정)**:
   - **HTTPS·빌드된 Nginx 이미지 (transport fixture upstream)**: `tests/integration/test_web_container.py` 단 1개 파일만 이 경로를 검증하며, `:127`은 로그인 화면 렌더와 스토리지 0건만 검증한다 (로그인 미수행). 업스트림은 실 CP가 아닌 `tests/fixtures/nginx_transport.py`를 실행하는 전송 계층 픽스처(Transport Fixture)이다.
   - **HTTP Vite 개발 서버 + 실 control-plane + disposable PG**: `tests/integration/test_studio_browser.py:117`(`origin = f'http://127.0.0.1:{port}'`), `test_approval_browser.py:22-28`(`node_modules/vite/bin/vite.js`)은 HTTP Vite 포트로 접속하며, `.github/workflows/desktop-browser.yml:52` 스텝 명칭도 "Real browser, canonical HTTP and disposable PostgreSQL"이다.
   - 따라서 "HTTPS 경유 IdP 로그인"은 미관측(`UNMEASURED`)으로 정직하게 분리하며, SMK-05의 401 오류는 Vite에서 control-plane으로 직접 전달된 경로(`test_studio_browser.py:135-136`)이므로 Nginx 게이트웨이 검증 항목에서 분리한다.
4. **SMK-04 배포 화면 진입 미관측 명시 (Claude 3 정정)**:
   - hosted 브라우저 시험 4개 파일 전체에서 `내부망 배포` 또는 `deployment` 탭 진입은 0건이다.
   - 시험이 수행하는 것은 Studio·승인센터·Web Desktop 전환과 복귀(`test_studio_browser.py:161-164`)뿐이므로, SMK-04는 **"부분 측정 (Studio·승인센터·Web Desktop 한정)"**으로 낮춘다.
   - S12 본 화면 진입(`'내부망 배포 (S12)'` 탭 클릭 -> `deployment-unexposed-notice` 표출 -> pageerror 0건)은 현재 브라우저 시험 미구현(`UNMEASURED`)으로 명시한다.
5. **RCV-02 세션 만료 경로의 앱 구조적 한계 정정 (Claude 4 정정)**:
   - 전체 앱 수준(`apps/web/src/app/App.tsx:500`)은 `if (!currentUser) return <Login .../>`이므로 비로그인 상태에서는 배포 탭이 렌더링되지 않는다.
   - API 401 수신 시 `client.ts:211` -> `App.tsx:162 onUnauthorized` -> `App.tsx:113 resetAuthenticatedState(setCurrentUser(null))` -> 즉시 로그인 화면으로 강제 전환되며 `Login.tsx:43`의 `login-error-alert`가 표출된다 (`late-mutation-generation-regression.test.tsx:265`).
   - 따라서 `IntranetDeploymentView.tsx:76-93`의 `deployment-auth-required-notice`는 컴포넌트 단독 렌더(`deployment-release-integrity-wiring.test.tsx:71`, `currentUser={null}`)에서만 노출된다. "배포 탭 체류 중 세션 만료"는 미관측(`UNMEASURED`)으로 정정한다.
6. **RCV-03 시험 파일 부재 및 UI 미연결 분리 (F-R3 및 Claude 7 정정)**:
   - 인용되었던 `vitest (recovery.test.ts)` 파일은 존재하지 않으며, 실제 파일은 `distributed-recovery.test.ts` 및 `sse-stream.test.ts`이다.
   - `shared/realtime/sse-client.ts:204-206`에 지수 백오프 코드는 존재하나 이를 단언하는 vitest가 부재하고(`sse-stream.test.ts`는 RingBuffer·파싱·중복제거만 검사), `apps/web/src`에 `online`/`offline` 이벤트 리스너가 전무하다.
   - `DistributedRecoveryView.tsx`는 `/v1/projects/.../events`를 구독하지 않는 인메모리 시뮬레이션이며 컴포넌트 자체도 `:133` `recovery-unexposed-notice`를 표출한다.
   - 따라서 Nginx 비버퍼링(`proxy_buffering off`) 전송 계층(`nginx.conf:101 ~ ^/v1/projects/[^/]+/runs/[^/]+/events`)만 `MEASURED`로 두고, UI 실시간 재연결 및 복구 조회는 **"백오프 코드 존재·시험 부재 / 오프라인 복귀 미구현 (`UNMEASURED / 미연결`)"**으로 분리한다.
7. **MAN-02 운영자 서명 가드의 클라이언트 문자열 휴리스틱 한정 (F-R4, Codex 2, Claude 8 정정)**:
   - `DeploymentManager.signOffRelease`는 역할 문자열 및 `authToken` 내 `unauthorized`/`unprivileged` 포함 여부와 operator ID 접두사 정규식(`/^(usr_operator_|usr_admin_|admin|operator)/`)만 검사하는 클라이언트 인메모리 가드이다.
   - 실제 권한 서버 호출, Bearer 토큰 암호 검증, ProblemDetails, 감사 원장은 부재한다.
   - 시험 `intranet-deployment.test.ts:89-106`은 빈 ID, `arbitrary-actor`, 유효 prefix만 호출·단언하며, `authToken='unprivileged...'`나 `{roles: ['viewer']}`는 호출하지 않는다. 또한 실패 후 `operatorSignOff === false`를 단언하지 않는다.
   - 따라서 단언된 3개 항목만 `MEASURED (엔진 단위시험)`로 표기하고, `authToken`/`roles` 분기 및 실제 서버 인가는 **`UNMEASURED / 미연결`**로 둔다.
8. **실재 인벤토리 정합성 및 EXT-02 전제값 정정 (F-R5 및 Claude 11 정정)**:
   - 임의로 기재되었던 `192.168.1.101~105`, `NVIDIA RTX A4000 GPU` 등은 `deploymentEngine.ts:37-41, :121`의 클라이언트 픽스처에서 유래한 가공의 값이므로 삭제한다.
   - 저장소 기록의 실제 랩 기준은 `3 Agent 원격 실행과 운영 인수 확정.md:15` (원격 Node 1대 `192.168.45.225` 및 서버 `192.168.45.99`) 및 **ADR-100 (Windows CP 호스트 겸임 Node 1 + 별도 독립 Ubuntu Worker Node 4)**이며, 실제 물리 IP 및 장비 스펙은 **"미정 (BLOCKED_EXTERNAL)"**으로 격리한다.

---

## 2. 4대 핵심 검증 영역 구조

```
+---------------------------------------------------------------------------------------------------+
|                   S12-FE 내부망 HTTPS 웹 배포·운영 인수 시나리오 매트릭스 (Gemini)                 |
+---------------------------------------------------------------------------------------------------+
|  [SMK] Web Smoke 검증 (5개)                                                                       |
|  - SMK-01: TLS 1.2 이상 협상(1.3 전용 아님), HSTS 헤더 및 HTTP(:80) -> HTTPS(:8443) 301 리다이렉트  |
|  - SMK-02: 정적 SPA 에셋 immutable 캐싱, index.html no-cache/must-revalidate, /callback no-store  |
|  - SMK-03: Synthetic IdP 연동 PKCE 로그인 (HTTP Vite + 실 CP 경로, HTTPS 경유 로그인은 미관측)   |
|  - SMK-04: 주요 포털 화면 라이브 렌더링 무오류성 (Studio·승인센터·Web Desktop 한정, 배포탭 미관측)|
|  - SMK-05: Transport Fixture 프록시 오류 상태코드 보존 (404 FIXTURE-404, 503 not_ready)           |
+---------------------------------------------------------------------------------------------------+
|  [RCV] 장애 복구 및 격리 검증 (3개)                                                               |
|  - RCV-01: Transport Fixture 중단 시 Fail-Closed(502/504) 및 재기동 후 200 정상 복구             |
|  - RCV-02: 운영자 세션 만료 격리 (단독 렌더링: alert 배너 / 전체 앱: Login 화면 강제 전환)       |
|  - RCV-03: SSE 프록시 비버퍼링(MEASURED) 및 UI 재연결/복구(백오프 코드 실재·시험 부재, UNMEASURED)|
+---------------------------------------------------------------------------------------------------+
|  [MAN] 릴리스 매니페스트 및 운영자 서명 검증 (3개)                                                |
|  - MAN-01: 릴리스 R4 매니페스트 메타데이터 및 다이제스트 정합성 (클라이언트 정적 픽스처)         |
|  - MAN-02: 비인가 운영자 ID 접두사 차단 가드 (단위시험 실측: MEASURED / authToken·roles: UNMEASURED)|
|  - MAN-03: 운영자 모의 서명 실행 및 시뮬레이션 고지 배너 표출 (백엔드 배포 API 미노출 명시)      |
+---------------------------------------------------------------------------------------------------+
|  [TRN] 운영자 교육 및 훈련 가이드 검증 (2개)                                                      |
|  - TRN-01: 4대 필수 훈련 모듈 (2인 승인, 자원배치, Kill Switch, 무중단 롤백) 명세 및 안내        |
|  - TRN-02: 단계별 재실습 완료 트리거 및 인메모리 제자리 갱신 (초기 로드 조기 완료 결함 식별)     |
+---------------------------------------------------------------------------------------------------+
|  [EXT] 외부 물리 장비 의존 검증 (3개, BLOCKED_EXTERNAL)                                           |
|  - EXT-01: 온프레미스 물리 서버 실제 사내 인증서 TLS / Nginx 배포                                |
|  - EXT-02: ADR-100 5노드(CP 겸임 1 + Worker 4) 물리 사내망 분산 환경 실가동 (스펙 미정)          |
|  - EXT-03: 현장 운영 책임자(usr_operator_lead) 최종 실물 인수 서명 및 GA 가동 선언                |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. 상세 시나리오 매트릭스 (13개 핵심 시나리오 + 3개 외부 장비 의존 항목)

### 3.1. SMK: Web Smoke 시나리오 (5개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 판정 |
|---|---|---|---|---|---|---|---|---|
| **SMK-01** | TLS 1.2 이상 협상 (1.3 전용 아님) 및 HTTP 리다이렉트 | `apps/web/nginx.conf:22-48`, `tests/integration/test_web_container.py:119, :175, :180-181` | Nginx 컨테이너 기동, 포트 80 및 443(호스트 임의포트) 바인딩, 인증서 마운트 | HTTP 포트 요청 및 HTTPS TLS 핸드셰이크 | `http://127.0.0.1:<port>/`, `https://127.0.0.1:<port>/studio` | 1. HTTP 요청 시 HTTP 301 반환 및 `Location: https://$host:8443...` 확인 (`:180-181`).<br>2. HTTPS 핸드셰이크 시 `TLSv1.2` 또는 `TLSv1.3` 협상 성공 (`nginx.conf:42 ssl_protocols TLSv1.2 TLSv1.3;`, 시험 `:124`).<br>3. `strict-transport-security: max-age=...` 헤더 존재 (`security-headers.conf:4`, 시험은 `max-age=` 접두사만 검증).<br>4. 임의의 신뢰할 수 없는 CA 연결 시 거부 확인.<br>*(주의: 화면의 TLS 1.3 STRICT 표시는 DEF-S12-09 결함이며, Strict TLS 1.3-only는 미측정)* | `hosted desktop-browser job` (`test_web_container.py:119, :175`) (HTTPS Nginx 이미지) | **MEASURED** (합성 Nginx 컨테이너) |
| **SMK-02** | 정적 SPA 에셋 immutable 캐싱 및 인증 설정 no-store | `apps/web/nginx.conf:51-87`, `tests/integration/test_web_container.py:103` | Nginx 정적 SPA 파일(`/usr/share/nginx/html`) 마운트 완료 | `/studio`, `/callback`, `/auth-config.js`, `/assets/*.js` GET 요청 | HTTP 응답 헤더 `cache-control`, `x-content-type-options`, `x-frame-options` | 1. `/assets/*.js`: HTTP 200, `cache-control: public, immutable` (시험 `:116` 단언; `expires: 1y`는 설정 실재·시험 미단언).<br>2. `/index.html`: `cache-control: no-cache, must-revalidate` (`nginx.conf:77`).<br>3. `/callback`: HTTP 200, `cache-control: no-store` (`nginx.conf:56`).<br>4. `/auth-config.js`: HTTP 200, `cache-control: no-store`, `mounted-public-client` 포함.<br>5. 전역 보안 헤더 `nosniff`, `DENY`, `no-referrer` 준수. | `hosted desktop-browser job` (`test_web_container.py:103`) (HTTPS Nginx 이미지) | **MEASURED** (합성 Nginx 컨테이너) |
| **SMK-03** | Synthetic IdP 연동 PKCE 브라우저 로그인 (HTTP Vite 경로) | `tests/integration/test_studio_browser.py:112-136`, `apps/web/src/features/auth/Login.tsx:40, :44` | Synthetic IdP 가동, Control Plane 가동, PostgreSQL business seeding 완료 | `/studio` 진입 후 `조직 계정으로 로그인` 버튼 클릭 | Playwright Chromium: `get_by_role('heading', name='SaintVision 로그인')`, `get_by_role('button', name='조직 계정으로 로그인')` | 1. PKCE Code Challenge(S256) 생성 및 IdP 리다이렉트.<br>2. 1회용 Authorization Code 교환 완료 (`valid PKCE exchange`).<br>3. `/v1/session` 200 OK 수신 및 사용자 세션 활성화.<br>4. 브라우저 `localStorage` 및 `sessionStorage`에 인증 토큰 잔류 0건 (`length == 0`).<br>*(주의: 이 시험은 HTTP Vite 개발서버 origin=http://127.0.0.1:{port} 경로이며, HTTPS 경유 IdP 로그인은 미관측)* | `hosted desktop-browser job` (`test_studio_browser.py:112`) (HTTP Vite + 실 CP) | **MEASURED** (HTTP Vite 경로) / HTTPS 로그인은 `UNMEASURED` |
| **SMK-04** | 주요 포털 화면 라이브 렌더링 무오류성 (Studio·승인센터·Web Desktop) | `apps/web/src/features/desktop/DesktopShell.tsx:40`, `Header.tsx:237` | 로그인 성공 세션 보유, 프로젝트 콘텍스트 설정 | 탭 네비게이션 및 Web Desktop 전환 버튼 클릭 | Playwright Chromium: `get_by_role('button', name='Web Desktop으로 전환')`, `get_by_role('dialog', name='내 컴퓨터 (Resource Explorer)')` | 1. 렌더링 도중 `pageerror` 발생 0건 (`browser_errors == []`).<br>2. DesktopWindow 및 ResourceExplorer 다이얼로그 정상 표출.<br>*(주의: 브라우저 시험 4개 파일에서 '내부망 배포 (S12)' 탭 진입은 0건으로 미관측. 본 화면 진입 여정은 현재 미구현/미측정)* | `hosted desktop-browser job` (`test_studio_browser.py:161`) | **MEASURED** (Studio·Desktop 한정) / 배포탭 진입은 `UNMEASURED` |
| **SMK-05** | Transport Fixture 프록시 오류 상태코드 보존 | `tests/integration/test_web_container.py:155-162`, `tests/fixtures/nginx_transport.py:26, :30` | Nginx 리버스 프록시 및 transport fixture 업스트림 가동 | 미존재 라우트 요청, `/readyz` 프로브 | `/v1/unknown`, `/readyz` | 1. `/v1/unknown`: HTTP 404 및 `{"code": "FIXTURE-404", "scope": "transport-fixture"}` JSON 보존 (`tests/fixtures/nginx_transport.py:30`, `test_web_container.py:160`).<br>2. `/readyz`: HTTP 503 및 `{"status": "not_ready", "scope": "transport-fixture"}` JSON 보존 (`tests/fixtures/nginx_transport.py:26`, `test_web_container.py:162`). 상태코드 은폐/왜곡 없음.<br>*(주의: Nginx 경유 /v1/session은 fixture가 200 반환; 실 제어평면 401 오류는 test_studio_browser.py:135-136의 HTTP Vite 경로에서 별도 검증)* | `hosted desktop-browser job` (`test_web_container.py:155`) (HTTPS Nginx 이미지) | **MEASURED** (transport fixture) |

---

### 3.2. RCV: 복구 및 장애 격리 시나리오 (3개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 판정 |
|---|---|---|---|---|---|---|---|---|
| **RCV-01** | Transport Fixture 중단 시 Fail-Closed 및 재기동 복구 | `tests/integration/test_web_container.py:185-188`, `apps/web/nginx.conf:45, :90` | Nginx 및 업스트림 transport fixture 컨테이너 가동 중 | `docker stop --time 2 <upstream>` 후 `docker start <upstream>` | Nginx 프록시 엔드포인트 `/v1/session`, `/readyz`, docker inspect health | 1. 업스트림 fixture 중단 직후: 요청이 무한 대기하지 않고 502 Bad Gateway 또는 504 Gateway Timeout 반환 (Fail-Closed, `test_web_container.py:187-188`이 502/504 모두 허용).<br>2. 업스트림 fixture 재기동 후: 최대 5초 이내에 `/v1/session` 200 OK 복구.<br>*(주의: Nginx healthcheck /healthz는 upstream과 무관한 정적 200이므로 healthy 회복은 Nginx 자체 상태일 뿐 업스트림 복구 신호는 아님)* | `hosted desktop-browser job` (`test_web_container.py:185`) (HTTPS Nginx 이미지) | **MEASURED** (transport fixture 컨테이너) |
| **RCV-02** | 운영자 세션 만료 시 화면 격리 (단독 렌더 경고 배너 vs 전체 앱 로그인 전환) | `apps/web/src/features/deployment/IntranetDeploymentView.tsx:76-93`, `deployment-release-integrity-wiring.test.tsx:71`, `apps/web/src/app/App.tsx:500`, `Login.tsx:43` | 운영자 세션 부재 (`currentUser === null`) 또는 401 수신 | 컴포넌트 단독 마운트 또는 API 401 반환 | `[data-testid="deployment-auth-required-notice"]` (`role="alert"`), `[data-testid="login-error-alert"]` | 1. **단독 렌더 (`wiring.test.tsx:71`)**: `role="alert"`, `aria-live="assertive"` 경고 배너 표출 및 서명 버튼 비활성화 (단, wiring:79는 role만 단언).<br>2. **전체 앱 (`App.tsx:500`)**: 비로그인 시 Login 화면 강제 렌더링. API 401 시 `resetAuthenticatedState`에 의해 `Login.tsx`로 전환되어 `login-error-alert` 표출 (`late-mutation...test.tsx:265`).<br>*(주의: 배포 탭 체류 중 세션 만료 격리는 미관측)* | `vitest` (`wiring.test.tsx:71`) / 전체 앱은 `Login.tsx` 전환 | **MEASURED** (컴포넌트 단독 렌더 한정) / 체류 만료는 `UNMEASURED` |
| **RCV-03** | SSE 프록시 비버퍼링(MEASURED) 및 UI 복구 재연결(UNMEASURED) | `apps/web/nginx.conf:101-109, :112, :122`, `apps/web/src/features/recovery/DistributedRecoveryView.tsx:133, :144`, `apps/web/src/shared/realtime/sse-client.ts:204-206` | 활성 실행 세션 중 네트워크 단절 또는 지연 발생 | SSE 이벤트 스트림 요청 및 복구 화면 렌더링 | Nginx SSE 스트리밍 프록시 (`nginx.conf:101 ~ ^/v1/projects/[^/]+/runs/[^/]+/events`), `DistributedRecoveryView` | 1. **프록시 전송 계층**: Nginx `proxy_buffering off;` (`:105`) 청크 비버퍼링 유효 (`MEASURED`).<br>2. **UI 제품 결속**: `recovery.test.ts` 파일은 부재하며, `distributed-recovery.test.ts`와 `sse-stream.test.ts`는 백오프를 단언하지 않음. `apps/web/src`에 `online`/`offline` 리스너 부재. `DistributedRecoveryView`는 순수 시뮬레이션 고지 표출 (`:133`).<br>*(백오프 코드는 실재하나 단언 시험 부재 / 오프라인 복귀 미구현)* | Nginx 설정 대조 (`MEASURED`) / UI 재연결은 `UNMEASURED / 미연결` | **부분 측정** (프록시 전송만 MEASURED / UI는 UNMEASURED) |

---

### 3.3. MAN: 릴리스 매니페스트 및 운영자 서명 시나리오 (3개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 판정 |
|---|---|---|---|---|---|---|---|---|
| **MAN-01** | 릴리스 R4 매니페스트 메타데이터 및 다이제스트 정합성 | `apps/web/src/features/deployment/deploymentEngine.ts:128-142`, `IntranetDeploymentView.tsx:543-579`, `intranet-deployment.test.ts:77-87` | `DeploymentManager` 인스턴스 초기화 | `getReleaseManifest()` 호출 | `[data-testid="deployment-unexposed-notice"]`, Release Version, Image Digest | 1. 릴리스 ID `REL-2026-R4-GA`, 버전 `v1.0.0-final-GA` 표출.<br>2. 불변 이미지 다이제스트 `sha256:7f8e9d0c1b...` (64자 hex) 형식 준수.<br>3. 상단에 `data-testid="deployment-unexposed-notice"` 배너가 위치하여 (백엔드 배포 API 미노출) 고지.<br>*(주의: vitest는 c323f55를 단언하지 않고 DOM도 렌더하지 않음. 서버 도메인 모델은 실재하나 REST 라우트 부재)* | `vitest` (`intranet-deployment.test.ts:77`) (엔진 단위시험) | **MEASURED** (정적 픽스처) / 서버 라우트는 `UNMEASURED / 미연결` |
| **MAN-02** | 비인가 운영자 ID 접두사 차단 가드 | `apps/web/src/features/deployment/deploymentEngine.ts:253-290`, `intranet-deployment.test.ts:89-106` | 유효하지 않은 운영자 ID 입력 (빈 문자열, 비인가 접두사 arbitrary-actor) 또는 비인가 옵션 | `signOffRelease(operatorId, options)` 호출 | `dm.signOffRelease('')`, `dm.signOffRelease('arbitrary-actor')`, `dm.signOffRelease('usr_operator_lead', {roles: ['viewer']})` | 1. 빈 운영자 ID: `success: false`, `Operator ID is required` (단언 있음, :92).<br>2. 비인가 계정(`arbitrary-actor`): 접두사 불일치로 `success: false`, `Unauthorized operator` (단언 있음, :98).<br>3. 유효 계정(`usr_operator_lead_99`): `success: true`, `operatorSignOff === true` (단언 있음, :104).<br>4. 비인가 토큰(`unprivileged...`) 및 viewer 역할(`{roles: ['viewer']}`): 코드상 가드 로직(:268, :278)은 실재하나 `intranet-deployment.test.ts:89-106`에서 미호출·미시험 (코드 실재 · 시험 미단언, UNMEASURED).<br>5. 실패 뒤 `operatorSignOff === false` 미단언.<br>*(주의: authority server 호출, Bearer 암호 검증, 감사원장 없는 순수 클라이언트 문자열 휴리스틱 가드임)* | `vitest` (`intranet-deployment.test.ts:89`) (엔진 단위시험) | **부분 MEASURED** (빈 ID·비인가 prefix 단언은 MEASURED / authToken·roles 및 서버 인가는 UNMEASURED) |
| **MAN-03** | 운영자 모의 서명 실행 및 시뮬레이션 고지 배너 표출 | `apps/web/src/features/deployment/IntranetDeploymentView.tsx:28-43, :538`, `deployment-release-integrity-wiring.test.tsx:33` | 유효한 운영자 로그인 세션 (`currentUser.id === 'usr_operator_lead_99'`) | 서명 버튼(`[data-testid="deployment-signoff-btn"]`) 클릭 | `[data-testid="deployment-signoff-btn"]`, `actionNotice` DOM 텍스트 | 1. 버튼 클릭 시 `handleSignOff` 실행.<br>2. 결과 메시지에 `✔ [모의 시뮬레이션]` 접두어 및 `(백엔드 배포 API 미노출)` 명시적 표출.<br>3. 서명자 ID `usr_operator_lead_99` 반영.<br>4. 서명 버튼 disabled 전환 (단, `wiring.test.tsx:61-69`는 disabled 여부를 미단언, `✔ 서명 완료됨`(:538) 미단언).<br>*(주의: 백엔드 감사 원장 영속화는 미구현)* | `vitest` (`deployment-release-integrity-wiring.test.tsx:33`) | **MEASURED** (컴포넌트 렌더링) / 백엔드 원장은 `UNMEASURED / 미연결` |

---

### 3.4. TRN: 운영자 교육 및 훈련 가이드 시나리오 (2개)

| 시나리오 ID | 시나리오 명 | 대상 컴포넌트 / 모듈 | 사전 조건 (Preconditions) | 트리거 (Trigger) | DOM 셀렉터 / 검증 지점 | 검증 단언 및 기대 결과 | 관측 방법 | 현재 상태 판정 |
|---|---|---|---|---|---|---|---|---|
| **TRN-01** | 4대 필수 운영 훈련 모듈 구성 및 안내 명세 | `apps/web/src/features/deployment/deploymentEngine.ts:144-173`, `IntranetDeploymentView.tsx:593-676`, `intranet-deployment.test.ts:110` | `IntranetDeploymentView` Section 4 렌더링 | `getTrainingSteps()` 호출 | Section 4 모듈 리스트 4건 | 1. Step 1: `L0~L3 거버넌스 및 2인 승인 절차 (Two-Person Rule)` 존재.<br>2. Step 2: `5-Node 자원 배치 가중치 및 제외 규칙 모니터링` 존재.<br>3. Step 3: `응급 Kill Switch 발동 및 비인가 자원 즉각 격리` 존재.<br>4. Step 4: `1-클릭 웹 무중단 롤백 및 캐시 무효화 확인` 존재.<br>5. 각 단계별 구체적 실습 행동(actionRequired) 명시. | `vitest` (`intranet-deployment.test.ts:110`) (엔진 단위시험) | **MEASURED** (컴포넌트 명세) |
| **TRN-02** | 단계별 재실습 완료 트리거 및 인메모리 제자리 갱신 | `apps/web/src/features/deployment/deploymentEngine.ts:300-307`, `IntranetDeploymentView.tsx:45-54, :670`, `intranet-deployment.test.ts:120` | 훈련 모듈 렌더링 상태 | 각 모듈의 `재실습 완료` 버튼 클릭 | `handleCompleteStep(stepNumber)`, `actionNotice` DOM | 1. `completeTrainingStep(stepNumber)` 호출 시 `success: true` 반환.<br>2. `actionNotice`에 `✔ 운영 교육 모듈 Step X 이수가 확인되었습니다.` 표출.<br>3. 인메모리 `trainingSteps` 배열 내 해당 요소가 제자리 변경(`:303`).<br>*(주의: test:120-123은 Step 2가 처음부터 completed(:157)라 공허하며, 불변 객체 갱신이 아닌 제자리 변경임. DEF-S12-08, DEF-S12-17)* | `vitest` (`intranet-deployment.test.ts:120`) | **MEASURED** (인메모리 갱신) |

---

### 3.5. EXT: 외부 물리 장비 의존 검증 항목 (3개, BLOCKED_EXTERNAL)

| 항목 ID | 항목 명 | 필요 환경 및 외부 전제 (ADR-100 및 인벤토리 기준) | 미수행 / 차단 사유 | 현재 상태 판정 |
|---|---|---|---|:---:|
| **EXT-01** | 온프레미스 물리 서버 실제 사내 인증서 TLS / Nginx 배포 | 사내 실제 공인/내부 도메인 DNS, 기업 엔터프라이즈 Root CA 인증서 발급, 물리 방화벽 포트 8443 개방, 리눅스 호스트 시스템 프로비저닝 | 개발 Agent 환경(로컬/CI)에서는 물리 온프레미스 서버 인프라에 접근할 수 없으며, 컨테이너 합성 테스트(`test_web_container.py`)로만 골격이 검증됨. 엄격한 TLS 1.3 단독 강제 여부도 현장 검증 대상임. | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |
| **EXT-02** | ADR-100 5노드(CP 겸임 1 + Worker 4) 물리 사내망 분산 환경 실가동 | 정본 토폴로지 ADR-100 및 `3 Agent 원격 실행과 운영 인수 확정.md:15` 기록 기준 (물리 IP 및 하드웨어 스펙은 현장 배정 전까지 **미정**) | 물리적 사내망 LAN 환경 및 5대의 실장비 클러스터가 부재하여 E2E 물리 여정 검증 불가 (`deploymentEngine.ts:80-126`은 가상 상수 배열이며, 클라이언트 픽스처에서 복사된 임의 IP/GPU 할당은 삭제됨). | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |
| **EXT-03** | 현장 운영 책임자(usr_operator_lead) 최종 실물 인수 서명 및 GA 가동 선언 | 실제 운영 총괄 책임자의 현장 실사, 실물 하드웨어 검수, 실제 사내망 접속을 통한 최종 GA 인계 서명 | 실제 운영 인수는 인간 운영 리드의 법적·운영적 승인 행위이며, 클라이언트 인메모리 시뮬레이션 버튼 클릭으로 대체할 수 없음. | **BLOCKED_EXTERNAL** (절대 통과로 꾸미지 않음) |

---

## 4. 발견된 18대 제품 결함 목록 (Defect Backlog: DEF-S12-01 ~ DEF-S12-18)

본 시나리오 매트릭스 수립 과정에서 `apps/web/src/features/deployment` 소스코드와 테스트를 정밀 대조하여 도출된 **18대 제품 결함 목록**이다. docs-only 거버넌스 원칙에 따라 본 문서에는 결함 분석 및 해결 계획만 수록하며, 실제 소스코드 및 시험 수정은 본 매트릭스가 검토자(Claude, Codex)에 의해 승인된 후 후속 제품 수정 카드에서 착수한다.

| 결함 ID | 발생 파일 및 행 번호 | 결함 분류 | 심각도 | 결함 상세 내용 | 권고 조치 방안 (후속 제품 수정 카드용) |
|---|---|---|:---:|---|---|
| **DEF-S12-01** | `IntranetDeploymentView.tsx:140` | 상태 무결성 | **HIGH** | 인메모리 모의 서명 후 상단 메트릭 카드에 `'프로덕션 가동 승인 완료'`라는 단정적인 문구를 노출하여 실제 상용 가동이 승인된 것으로 오인하게 만듦. | `manifest.operatorSignOff ? '로컬 시뮬레이션 서명 완료 (실 환경 미배포)' : '운영자 확인 대기 중'`으로 정정. |
| **DEF-S12-02** | `IntranetDeploymentView.tsx:207-209` | 상태 무결성 | **HIGH** | 모의 서명 완료 시 `'운영자 인수 완료 (docker compose up -d 가능)'`을 노출하여 즉시 온프레미스 도커 가동이 가능한 것처럼 과장 안내함. | `manifest.operatorSignOff ? '모의 인수 절차 확인됨 (온프레미스 실장비 기동 별도 필요)' : '현장 운영자 인수 대기'`로 정정. |
| **DEF-S12-03** | `IntranetDeploymentView.tsx:462, :474`, `deploymentEngine.ts:80-126` | 상태 무결성 | **HIGH** | `:474 PASSED ✔` 및 지연시간 수치는 `node.smokeStatus`와 바인딩되지 않은 리터럴임. `App.tsx:844`가 항상 `clusterNodes={nodes}`를 넘기나, 실제 노드가 offline으로 매칭되어도 화면은 무조건 `PASSED ✔` 및 녹색 지연시간을 출력함. | 배지 텍스트를 실제 상태값에 바인딩하고, online이 아닌 실제 노드나 매칭 실패 노드는 PASSED를 숨기거나 `미측정`/`오프라인`으로 표출. 후속 카드에서 기존 시험(`intranet-deployment.test.ts:56-73`) 수정 포함. |
| **DEF-S12-04** | `IntranetDeploymentView.tsx:187, :190`, `deploymentEngine.ts:321` | 상태 무결성 | **MEDIUM** | 화면은 `getPreflightStatus`를 호출하지 않음에도(호출처 0건), 상단에 `'202/202 Checks PASS'`를 하드코딩 리터럴로 표출함. 기존 시험(`intranet-deployment.test.ts:128-143`)이 이 결함을 고정하고 있음. | 문구를 `[설계 규격 예시 (202개 검증 항목)]`으로 정정하고 기존 시험 단언 수정. |
| **DEF-S12-05** | `IntranetDeploymentView.tsx:146-160` | 접근성 (WCAG 2.1 AA) | **MEDIUM** | 동적 알림 배너 `actionNotice` div에 `role="status"`/`role="alert"` 및 `aria-live` 속성이 누락되어 스크린 리더에 낭독되지 않음. | 상시 마운트된 컨테이너에 `role={actionNotice.type === 'error' ? 'alert' : 'status'}` 및 `aria-live` 분리 부여. |
| **DEF-S12-06** | `IntranetDeploymentView.tsx:543-579` | 계약 경계 투명성 | **HIGH** | 릴리스 매니페스트 메타데이터가 백엔드에서 페치된 것처럼 표시되나 실제는 클라이언트 정적 픽스처임. 백엔드 도메인 모델(`ReleaseManifest`, `AcceptanceRecord`)은 실재하나 REST 라우트가 부재함. | 섹션 상단에 `[정적 픽스처 / 백엔드 릴리스 매니페스트 REST API 미연결]` 라벨 명시. |
| **DEF-S12-07** | `IntranetDeploymentView.tsx:509-540`, `deploymentEngine.ts:292` | 영속성 결여 | **MEDIUM** | 운영자 서명 시 인메모리 플래그만 변경될 뿐 백엔드 감사 원장 영속화가 부재함 (`inv.audit_events` 테이블은 없으며, 백엔드 도메인은 `AcceptanceRecord`임). | 클라이언트 시뮬레이션 고지를 강화하고, 백엔드 `AcceptanceRecord` 연동 REST 엔드포인트 신설 시 정식 결속 계획 수립. |
| **DEF-S12-08** | `deploymentEngine.ts:150, 157, 164, 171`, `IntranetDeploymentView.tsx:668` | 훈련 상태 왜곡 | **MEDIUM** | `:668 COMPLETED ✔`는 `step.status`와 연결되지 않은 리터럴이며, 엔진 초기값도 Step 1~4가 모두 completed라 첫 진입부터 훈련 완료로 노출됨. | `:668` 배지를 `step.status === 'completed' ? 'COMPLETED ✔' : 'PENDING'`으로 바인딩하고 초기값을 `'pending'`으로 정정. |
| **DEF-S12-09 (5-a)** | `IntranetDeploymentView.tsx:106, :108` | 보안 규격 왜곡 | **HIGH** | 화면에 `'TLS 1.3 (STRICT)'` 및 `'HSTS 365일 & 전용 Enterprise CA'`를 고정 표출하나, 실제 `nginx.conf:42`는 TLS 1.2를 허용하며 `docker-compose.prod.yml:16`은 dev cert, `generate_tls_cert.py`는 self-signed임. | 문구를 `'TLS 1.2/1.3 협상 (개발용 자체서명 CA)'`로 정정. |
| **DEF-S12-10 (5-b)** | `IntranetDeploymentView.tsx:230, :252` | 상태 무결성 | **MEDIUM** | `:230` `'내부망 전용 TLS 인증서 정보 (AC-12)'` 패널 및 `:252` HSTS `'활성화'`가 고정 픽스처(`deploymentEngine.ts:26-43`)임에도 실제 인증서 조회처럼 표출됨. | 패널에 `[정적 구성 예시 (실시간 인증서 조회 아님)]` 고지 추가. |
| **DEF-S12-11 (5-c)** | `IntranetDeploymentView.tsx:337`, `deploymentEngine.ts:183-242` | 아키텍처 괴리 | **HIGH** | 화면의 `'▶ 배포용 nginx.conf 구성 파일 전문 보기'`가 실제 `apps/web/nginx.conf`와 심각하게 괴리됨 (listen 8443 vs 443, TLS 1.3 vs 1.2/1.3, upstream pacs-backend:8080 vs control-plane:8080, 인증서 경로 /etc/nginx/ssl vs /etc/ssl/certs). 라우팅 표(:56)도 pacs-backend 사용. | `deploymentEngine.ts`의 생성 문자열 및 라우팅 표를 실제 `apps/web/nginx.conf` 및 `control-plane:8080`과 일치하도록 정정. |
| **DEF-S12-12 (5-d)** | `IntranetDeploymentView.tsx:114, :576` | 무결성 (허위 배지) | **HIGH** | `:114` `'100% (5/5 PASSED)'` 및 `:576` `'5/5 Nodes PASSED (100%)'`가 실제 클러스터 노드 상태와 무관하게 무조건 노출되는 하드코딩 리터럴 결함. | 클러스터 노드 실제 헬스 상태에 따라 동적 계산하여 표출하고 미측정 시 `'미측정'` 고지. |
| **DEF-S12-13 (5-e)** | `IntranetDeploymentView.tsx:194` | 과장 표기 | **MEDIUM** | `'… 제어 평면 게이트웨이 라이브 프로브(HTTP 200) 검증 완료'` 문구가 브라우저에서 실제 게이트웨이 프로브를 실행하지 않았음에도 무조건 표출됨. | 문구를 `[사전 규격 검증 항목]`으로 정정하거나 실제 헬스체크 연동 전까지 숨김 처리. |
| **DEF-S12-14 (5-f)** | `IntranetDeploymentView.tsx:388, :478`, `deploymentEngine.ts:88-124` | 관측 시각 왜곡 | **MEDIUM** | `'최근 검증 시각'`이 `Date.now()`에서 몇 분을 뺀 동적 계산값으로 생성되어 새로고침할 때마다 항상 "방금 전 검증"된 것처럼 왜곡 노출됨. | 실제 관측 타임스탬프가 없는 경우 고정 기준 시각을 명시하거나 `'미측정'`으로 표기. |
| **DEF-S12-15 (5-g)** | `IntranetDeploymentView.tsx:120, :137, :501`, `deploymentEngine.ts:129-130` | 릴리스 단계 왜곡 | **HIGH** | `'최종 프로덕션 릴리스 (R4)'`, `'SIGNED-OFF ✔'`, `'프로덕션 릴리스 선언서'`, `'REL-2026-R4-GA'`, `'v1.0.0-final-GA'` 등 파일럿/RC 단계에서 도달할 수 없는 GA/프로덕션 확정 라벨이 픽스처에 하드코딩됨. | 라벨을 `'파일럿 후보 릴리스 (Pilot RC)'`, `'모의 릴리스 선언서'` 등으로 정직하게 하향 정정. |
| **DEF-S12-16 (5-h)** | `deploymentEngine.ts:323`, `intranet-deployment.test.ts:140-142` | 물리 검수 왜곡 | **HIGH** | 클라이언트 서명 단 1회 실행으로 `physicalHardwareAcceptance: 'accepted'`로 전이되며, 기존 단위시험이 이를 고정하고 있음. 인간 운영자의 물리 실물 검수 없이 소프트웨어 버튼만으로 하드웨어 수락이 완료됨. | 물리 하드웨어 검수는 외부 전제(`BLOCKED_EXTERNAL`)로 분리하고 소프트웨어 서명으로 자동 승인되지 않도록 분리. |
| **DEF-S12-17 (5-i)** | `IntranetDeploymentView.tsx:51, :671` | 훈련 이수 왜곡 | **LOW** | `:671`의 `'재실습 완료'` 버튼 클릭만으로 `'✔ 운영 교육 모듈 Step X 이수가 확인되었습니다.'`가 자기보고식으로 확인 처리되는 무검증 구조. | 실제 실습 액션(모달 오픈, 콘솔 입력 등)과 결속하거나 `[자율 실습 확인]`으로 고지 정정. |
| **DEF-S12-18 (5-j)** | `IntranetDeploymentView.tsx:509-523`, `deploymentEngine.ts:283` | 권한 가드 우회 | **HIGH** | 운영자 ID 입력란이 `onChange`로 자유롭게 편집 가능하며, `signOffRelease(operatorId)` 호출 시 `currentUser.role`이나 토큰을 검증하지 않고, `deploymentEngine.ts:283` 정규식 `/^(usr_operator_|usr_admin_|admin|operator)/`가 단순 문자열 매칭이어서 일반 로그인 사용자도 'admin'이나 'operator'를 입력하면 모의 서명을 탈취할 수 있는 심각한 클라이언트 권한 우회 결함. | 운영자 ID를 현재 로그인된 `currentUser.id`로 고정(편집 불가)하고, `currentUser.role`이 실제 인가된 역할(`admin` 또는 `operator`)인지 검증하는 엄격 가드 도입. |

---

## 5. 증거 추적성 및 거버넌스 대조표 (Evidence Traceability)

| 요구 문서 및 기준 | 요구 항목 / 증거 명세 | 본 매트릭스 대응 시나리오 | 실제 검증 도구 및 실행 위치 | 검증 결과 및 상태 판정 |
|---|---|---|---|---|
| **task-registry.json** (`OUT-12` / `AC-12`) | "Release manifest·사용자 인수·웹 smoke·복구 Evidence" | `SMK-01` ~ `SMK-05`, `RCV-01` ~ `RCV-03`, `MAN-01` ~ `MAN-03`, `EXT-01` ~ `EXT-03` | Hosted CI: `desktop-browser` workflow, Local: `vitest` | `SMK-01~02` MEASURED, `SMK-03/04` 부분 MEASURED (SMK-03 HTTPS 로그인은 UNMEASURED, SMK-04 배포 탭 진입은 UNMEASURED), `SMK-05/RCV-01` MEASURED(transport fixture), `EXT-01~03` BLOCKED_EXTERNAL |
| **Codex FE Review Map** (33행) | "배포 화면/manifest 단위 시험, 로컬 HTTPS smoke 골격과 manifest 일관성 검사" | `SMK-01`, `SMK-02`, `MAN-01`, `MAN-02` | `apps/web/tests/intranet-deployment.test.ts` (9 tests) | 9/9 tests passed in Vitest (hosted frontend run `35795657531` 기준 9 tests; 단 c323f55 미단언, viewer 미단언, 제자리 갱신 등 시험 한계 식별) |
| **남는 전제·차단 (33행)** | "5노드 내부망, TLS/Nginx 실제 배포, 사용자 인수·복구. 장비·운영 인수 필요" | `EXT-01`, `EXT-02`, `EXT-03` | 온프레미스 연구소 물리 장비 5대(ADR-100) 및 현장 운영 인계 | **BLOCKED_EXTERNAL** (거짓 PASS 배제, 장비 투입 시 실측 예정) |
| **S12 파일럿 계획** (`AC-12`) | "5노드 전체 여정·정량 목표·알려진 제한·인수 확인 모두 기록" | `MAN-01` (Known Limitations), `TRN-01` (4대 교육 훈련), `DEF-S12-03` (5노드 상수 격리) | `deploymentEngine.ts:136-140` (Known Limitations 3종 단언) | `intranet-deployment.test.ts:86` (`expect(knownLimitations.length).toBeGreaterThanOrEqual(3)`) (단위 시험) |
| **거버넌스 배선 무결성 가드** | 운영자 행위자 실배선 및 미인증 서명 차단 가드 | `RCV-02`, `MAN-02`, `MAN-03` | `apps/web/tests/deployment-release-integrity-wiring.test.tsx` (Priority 7-A tests) | 2/2 tests passed in Vitest (`IntranetDeploymentView 운영자 행위자 실배선`; 단 서명완료 문구 및 disabled, aria-live는 미단언) |
| **Nginx 프록시 무결성** | 업스트림 장애 격리 (Fail-Closed) 및 자동 재연결 | `RCV-01`, `SMK-01` | `tests/integration/test_web_container.py:185-188` | pytest pass in Hosted GitHub Actions Linux runner (transport fixture 대상, 502/504 둘 다 허용) |

---

## 6. 결론 및 후속 인계 (Handoff)

1. **매트릭스 수립 완결**:
   - 본 문서는 S12-FE 내부망 HTTPS 웹 배포·운영자 교육 화면의 실측 가능한 13개 소프트웨어 시나리오(Web Smoke 5개, Recovery 3개, Release Manifest 3개, Training 2개)와 3개 외부 물리 장비 의존 항목(`BLOCKED_EXTERNAL`)을 정직하게 수립하였다.
   - Claude UI 축 검토 의견 11개 항목 및 Codex 계약 축 지적을 전수 반영하여:
     - Nginx의 TLS 1.2/1.3 협상 규격 정정 (Strict TLS 1.3-only는 미측정).
     - 관측 경로를 "HTTPS Nginx 컨테이너(transport fixture)"와 "HTTP Vite 개발서버(실 CP + PG)"로 엄격히 분리.
     - 배포 탭('내부망 배포 (S12)') 브라우저 진입이 미관측(`UNMEASURED`)임을 명시.
     - RCV-02 세션 만료 트리거를 컴포넌트 단독 렌더(`wiring.test.tsx:71`)로 정정하고, 전체 앱 수준에서는 401 시 `Login.tsx`의 `login-error-alert`로 강제 전환됨을 명시.
     - `recovery.test.ts` 부재 정정, 백오프 코드 실재하나 시험 부재 및 UI 미연결 명시.
     - `intranet-deployment.test.ts` 시험 수 9개(it 9개) 반영 및 단언 유무 구분.
     - 백엔드 서버 도메인 모델(`ReleaseManifest:221`, `AcceptanceRecord:251`, `pilot.py:358/396`)이 실재하며 REST 라우트만 미연결 상태임을 명시.
     - EXT-02의 임의 하드웨어/IP 값을 삭제하고 정본 ADR-100 토폴로지 및 `3 Agent 원격 실행과 운영 인수 확정.md:15` 참조로 정합화.
     - SMK-05의 fixture 응답을 `tests/fixtures/nginx_transport.py:26, :30` 실제 응답 규격(`{"code": "FIXTURE-404", "scope": "transport-fixture"}`, `{"status": "not_ready", "scope": "transport-fixture"}`)으로 일치화.
     - RCV-03의 SSE 프록시 경로를 실제 정규식 location인 `~ ^/v1/projects/[^/]+/runs/[^/]+/events` (`nginx.conf:101`)로 교정.
   - 화면에 노출되는 18대 허위 상태, 보안 왜곡, 권한 우회 및 접근성 결함을 `DEF-S12-01` ~ `DEF-S12-18`로 체계화하여 결함 백로그를 확충하였다.
2. **독립 검토 요청 (Review Request)**:
   - **Claude (UI 경로 축)**: C1~C8 전수 반영 및 18대 결함 백로그, RCV-02 단독 렌더 정정, 9개 시험 수 정정 확인 요청.
   - **Codex (계약 축)**: SMK-05 fixture JSON 원문 일치, MAN-02 시험 단언 범위 정밀 분리, 백엔드 REST 부재 표현 교정 확인 요청.
3. **다음 착수 카드**:
   - 본 docs-only 매트릭스 PR 승인 후, 도출된 18대 결함을 치유하는 **S12-FE 제품 결함 수정 카드(apps/web 코드 및 시험 수정, owner Gemini, reviewer Claude UI / Codex 계약)**로 전환한다.
