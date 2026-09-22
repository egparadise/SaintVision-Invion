---
doc_id: "HIST-GEMINI-2026-09-22-DESKTOP-STUDIO-BROWSER"
title: "Desktop 및 Studio 브라우저 수용 검증 4건 전수 합격 및 InvFileExplorer 저장소 카탈로그 정합 보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-22T17:40:00+09:00"
source_of_truth: "Git"
---

# Desktop 및 Studio 브라우저 수용 검증 4건 전수 합격 및 InvFileExplorer 저장소 카탈로그 정합 보고

- 작업 일시: 2026-09-22T17:40:00+09:00 (KST)
- 배정: Gemini (Frontend & Browser Acceptance Owner)
- 작업 브랜치: `agent/gemini/fix-desktop-studio-browser`
- 참조 문서: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[검증 보고 provenance 규칙]]

---

## 1. 개요 및 배경

코디네이터 지침에 따라 hosted CI의 브라우저 수용 테스트 (`Auth and Desktop HTTP Browser Acceptance`) 및 프런트엔드 Vitest 로캘 불일치 실패를 전면 분석하고 치유를 완결하였다.

1. **Task B: Vitest Ubuntu CI 로캘 불일치 치유** (PR #40: `agent/gemini/fix-locale-vitest`):
   - `apps/web/tests/freshness-and-staleness-wiring.test.tsx`에서 `testTimestamp.toLocaleTimeString()`을 로캘 인자 없이 호출하여, Ubuntu CI 러너(`en-US`) 환경에서 `12:30:00 AM`이 생성되어 컴포넌트 내부의 `toLocaleTimeString('ko-KR')`(`오전 12:30:00`)과 불일치하던 결함을 `toLocaleTimeString('ko-KR')` 명시로 교정.
2. **Task A: Browser Acceptance Tests 4건 전수 합격 치유** (`agent/gemini/fix-desktop-studio-browser`):
   - `test_desktop_browser.py`: VF-GM-03 가상 패브릭 개편 과정에서 누락되었던 정본 저장소 카탈로그(`fabricObservation.locations`, `resolve`, `replicas`) UI 폼, 갱신 버튼, 상세 패널을 `InvFileExplorer`에 정합. 가상 패브릭 빈 상태 텍스트(`네임스페이스에 등록된 파일이 없습니다.`)와 실 저장소 카탈로그 빈 상태(`등록된 파일이 없습니다.`)를 엄격히 분리하여 Playwright `exact=True` strict mode 충돌 원천 차단.
3. **Task C: Nginx TLS Proxy 컨테이너 및 Service Worker 정합 (기존 Red 해소 — `test_web_container.py`)**:
   - **원인 분석**:
     - `nginx.conf`: `location /` 등에 `Cache-Control` 헤더를 추가하면서 Nginx 상속 규칙에 의해 상위 `add_header`가 누락되어 `X-Content-Type-Options: nosniff` 등이 누락됨. `Referrer-Policy`가 `strict-origin-when-cross-origin`으로 설정되어 테스트의 `no-referrer` 기대치와 불일치.
     - `log_format`: 쿼리스트링(`$request`)과 `$http_referer`를 기록하여 OAuth callback code/state가 로그에 남는 보안 결함 존재.
     - `index.html`: `<script src="/auth-config.js"></script>` 누락으로 `Login` 진입 시 `authConfig()` 에러로 `<p role="alert">`가 렌더되어 locator count 0 실패.
     - `sw.js`: `/auth-config.js`, `/callback` 등을 Service Worker가 캐시하는 결함.
     - Dockerfile: `HEALTHCHECK` 누락으로 container State에 Health가 없어 검증 실패.
   - **치유 내역**:
     - `apps/web/security-headers.conf` 신설 및 `nginx.conf` 내 필요 location마다 include 적용.
     - `nginx.conf`: `$request_method $uri $server_protocol` 쿼리/리퍼러 제외 로그 포맷 적용, `location = /callback`(access_log off, Cache-Control: no-store), `location = /auth-config.js`(Cache-Control: no-store), `location = /readyz`(proxy_pass) 및 `proxy_connect_timeout 2s;` 완비.
     - `apps/web/index.html`: `<script src="/auth-config.js"></script>` 태그 복원.
     - `apps/web/public/auth-config.js`: 공개 설정 템플릿 복원.
     - `apps/web/public/sw.js`: `/auth-config.js`, `/callback`, `/healthz`, `/readyz` 캐시 제외 가드 복원.
     - `apps/web/Dockerfile` 및 `.github/workflows/desktop-browser.yml`: `security-headers.conf` 복사 및 `HEALTHCHECK` 추가.

---

## 2. 검증 실측 결과

### 2.1 브라우저 통합 수용 검증 (실제 PostgreSQL 16 컨테이너 + Playwright Chromium)
```powershell
$env:INV_TEST_ADMIN_DSN="postgresql://invowner:***@127.0.0.1:55432/postgres"
$env:INV_BROWSER_TEST="1"
.venv\Scripts\python.exe -m pytest tests/integration/test_desktop_browser.py tests/integration/test_studio_browser.py
```
- **결과**: **4 passed**, 4 warnings in 40.74s (exit code 0)
  - `tests/integration/test_desktop_browser.py::test_browser_real_catalogue_owner_scope_and_revocation`: PASSED
  - `tests/integration/test_desktop_browser.py::test_browser_real_committed_model_and_current_permission`: PASSED
  - `tests/integration/test_studio_browser.py::test_full_studio_login_project_approval_and_logout[False]`: PASSED
  - `tests/integration/test_studio_browser.py::test_full_studio_login_project_approval_and_logout[True]`: PASSED

### 2.2 프런트엔드 웹 컨테이너 및 TLS 경계 실측 검증 (`test_web_container.py`)
```powershell
$env:INV_WEB_IMAGE="inv-web-test:local"
.venv\Scripts\python.exe -m pytest -q --strict-markers tests/integration/test_web_container.py
```
- **결과**: **7 passed in 17.55s (exit code 0, 100% PASS)**
  - `test_studio_callback_and_mounted_auth_config_have_security_headers`: PASSED
  - `test_unknown_ca_is_rejected_and_tls_is_negotiated`: PASSED
  - `test_built_studio_page_uses_mounted_config_without_caching_credentials`: PASSED
  - `test_real_proxy_preserves_authorization_errors_and_readiness`: PASSED
  - `test_canonical_run_events_are_not_buffered`: PASSED
  - `test_callback_secrets_are_absent_from_http_and_https_access_logs`: PASSED
  - `test_proxy_fails_closed_and_reconnects_after_upstream_restart`: PASSED

### 2.3 프런트엔드 무결성 및 번들 빌드
- `npx tsc -b`: exit code 0 (타입 에러 0건)
- `npm run build`: exit code 0 (`dist/assets/index-sXySVZL8.js` 765.47 kB, 4.09s)
- `python tools/check_frontend_integrity.py`: **All 9 integrity rules satisfied (0 violations)** (exit code 0)
- `pytest tests/test_route_coverage.py`: **30 passed in 1.01s** (exit code 0)
- `python tools/check_docs.py`: **PASS** (769 versioned documents)

### 2.4 Vitest 단위/통합 회귀 시험
- `npm --prefix apps/web test`: **75개 파일 655/655 passed 100%** (26.64s)
