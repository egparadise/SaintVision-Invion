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
   - `test_studio_browser.py`: 프로젝트 콤보박스 및 PKCE 로그인 플로우 2건 정상 동작 재검증 완료.

---

## 2. 검증 실측 결과

### 2.1 브라우저 통합 수용 검증 (실제 PostgreSQL 16 컨테이너 + Playwright Chromium)
```powershell
$env:INV_TEST_ADMIN_DSN="postgresql://invowner:***@127.0.0.1:55432/postgres"
$env:INV_BROWSER_TEST="1"
.venv\Scripts\python.exe -m pytest tests/integration/test_desktop_browser.py tests/integration/test_studio_browser.py
```
- **결과**: **4 passed**, 4 warnings in 50.76s (exit code 0)
  - `tests/integration/test_desktop_browser.py::test_browser_real_catalogue_owner_scope_and_revocation`: PASSED
  - `tests/integration/test_desktop_browser.py::test_browser_real_committed_model_and_current_permission`: PASSED
  - `tests/integration/test_studio_browser.py::test_full_studio_login_project_approval_and_logout[False]`: PASSED
  - `tests/integration/test_studio_browser.py::test_full_studio_login_project_approval_and_logout[True]`: PASSED

### 2.2 프런트엔드 무결성 및 번들 빌드
- `npx tsc -b`: exit code 0 (타입 에러 0건)
- `npm run build`: exit code 0 (`dist/assets/index-sXySVZL8.js` 765.47 kB, 6.03s)
- `python tools/check_frontend_integrity.py`: **All 9 integrity rules satisfied (0 violations)** (exit code 0)
- `pytest tests/test_route_coverage.py`: **30 passed in 1.00s** (exit code 0)
- `python tools/check_docs.py`: **PASS** (768 versioned documents)

### 2.3 Vitest 단위/통합 회귀 시험
- `npm --prefix apps/web test`: **75개 파일 655/655 passed 100%** (16.76s)
