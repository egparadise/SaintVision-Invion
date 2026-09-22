---
doc_id: "HIST-GEMINI-2026-09-22-UI-INVARIANTS"
title: "Web Desktop 4대 UI 불변식 및 A11y 실측 검증 보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-22T19:40:00+09:00"
source_of_truth: "Git"
---

# Web Desktop 4대 UI 불변식 및 A11y 실측 검증 보고

- 작업 일시: 2026-09-22T19:40:00+09:00 (KST)
- 배정: Gemini (Frontend & Browser Acceptance Owner)
- 참조 문서: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스]], [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]]

---

## 1. 개요 및 배경

코디네이터 지침 및 Track 15 로드맵에 따라, 가상 컴퓨터 UI의 핵심 축인 Web Desktop 4대 UI 불변식(양방향 전환기, 창 관리자, 키보드 A11y, 레이아웃 영속성)의 `[UNVERIFIED]` 4건을 실제 Blink 엔진(Google Chrome Official Build) 및 실제 Uvicorn 8080 백엔드, Vite 3005 개발 서버 환경에서 종단간 실측하고 `tools/run_browser_smoke.mjs`의 미검증 항목을 0건(`unverified 4 -> 0`)으로 전환하였다.

또한 오늘 진행된 Gemini 레인의 PR 4건(#39, #40, #44, #36)의 처리 및 병합 거버넌스 현황을 정합 정리한다.

---

## 2. 오늘 Gemini PR 현황 요약

| PR 번호 | 대상 브랜치 / HEAD SHA | 성격 | 최종 상태 | 주요 내용 및 실측 내역 |
|---|---|---|---|---|
| **#39** | `agent/gemini/attribution-fix`<br>(HEAD: `b112b2e5`) | 거버넌스 / 저자 정정 | **병합 완료**<br>(병합: `ddf149e9`) | PR #37 History 및 PR #38 산출물의 작성자 명의(Claude ➔ Gemini)를 코디네이터 승인에 따라 공식 정정. `docs/task-registry.json` 및 frontmatter 완전 일치화. |
| **#40** | `agent/gemini/fix-locale-vitest`<br>(HEAD: `22ea36f5`) | 단위 테스트 정합 | **병합 완료**<br>(병합: `7b251bd6`) | `freshness-and-staleness-wiring.test.tsx`의 `toLocaleTimeString('ko-KR')` 로캘 명시로 Ubuntu CI 러너(`en-US`) 환경과의 시간 문자열 충돌 치유. hosted Frontend CI 통과. |
| **#44** | `agent/gemini/fix-desktop-studio-browser`<br>(HEAD: `8e4927a9`) | 브라우저 수용 / 보안 | **병합 완료**<br>(병합: `d651a52f`) | `InvFileExplorer` 정본 저장소 카탈로그 복원, 가상 패브릭/카탈로그 빈 상태 분리, Nginx CSP `frame-ancestors 'self'` 보안 헤더 검토 통과. hosted Browser Acceptance CI 통과. |
| **#36** | `agent/claude/node-usage-ui`<br>(HEAD: `c6094d71`) | UI 계약 / 노드 사용량 | **병합 완료**<br>(병합: `8f3c80c8`) | Claude 2차 지적 사항 3건 전면 수용(미서빙 글로벌 경로 제거·정직 tri-state 안내 고지·dev DB 0대 한계 정직 고지) 및 Claude 승인 후 코디네이터 병합 완료. NodeResourceUsage UI가 실제 서빙 라우트에 정상 연결됨. `tsc -b` 0, `build` 0, Vitest 9/9, route_coverage 37 passed. |

---

## 3. Web Desktop 4대 UI 불변식 실제 Chrome 실측 결과

실제 Chrome 브라우저(`--headless=new`, 1920x1080)와 Uvicorn 8080 백엔드(FastAPI `create_app`), Vite 3005 프런트엔드를 연동하여 `tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants`를 실행하고 4대 불변식을 전수 실측하였다.

### 3.1 [Invariant 1: PASS] 양방향 전환기 (Bidirectional Switcher)
- **검증 내용**: Portal 뷰(`Header` 상의 `Web Desktop으로 전환` 버튼) ➔ Web Desktop 컨테이너(`[data-testid="desktop-shell-container"]`) ➔ 데스크톱 상단 메뉴 바의 Portal 모드 복귀 버튼(`[data-testid="desktop-mode-switcher"]`) 왕복 전환.
- **실측 결과**:
  - Portal ➔ Web Desktop 진입 시 `desktop-shell-container` 정상 마운트 확인.
  - Web Desktop ➔ Portal 복귀 시 `desktop-shell-container` 언마운트 및 포털 메인 정상 표출 확인.
  - 재차 Desktop 진입 정상 확인.
- **증거 스크린샷**:
  - `scratch/real_chrome_desktop_01_switcher_desktop.png`
  - `scratch/real_chrome_desktop_01_switcher_portal.png`

### 3.2 [Invariant 2: PASS] 창 관리자 (Window Manager)
- **검증 내용**: 윈도우 트래픽 라이트(최소화, 최대화/복원, 닫기), 독(Dock)을 통한 창 복원, 활성 창 포커스 시 동적 z-index 승격.
- **실측 결과**:
  - `내 컴퓨터` 창의 최소화 버튼(`button[aria-label="창 최소화: 내 컴퓨터 (Resource Explorer)"]`) 클릭 시 DOM에서 은닉 확인.
  - 하단 Dock의 `내 컴퓨터` 아이콘 클릭 시 창 복원 확인.
  - 최대화 버튼 클릭 시 뷰포트 전체 확장 및 복원 버튼 클릭 시 원래 크기(920x600) 복원 확인.
  - 다중 창(`내 컴퓨터` 및 `inv:// 파일 탐색기`) 동시 구동 시, 새로 열린 창과 클릭된 창의 z-index가 `23 > 22 > 21`로 동적 승격됨을 실측 확인.
  - `inv:// 파일 탐색기` 닫기 버튼 클릭 시 창 언마운트 확인.
- **증거 스크린샷**:
  - `scratch/real_chrome_desktop_02_minimized.png`
  - `scratch/real_chrome_desktop_02_window_manager.png`

### 3.3 [Invariant 3: PASS] 키보드 접근성 (Keyboard A11y)
- **검증 내용**: Alt+Tab 단축키 창 순환(Cycling), 시작 메뉴 열기 및 Escape 키를 통한 모달 닫기 프로토콜.
- **실측 결과**:
  - Alt+Tab 입력 시 비활성 창(`win_my_computer`)이 활성 창(`win_model_studio`) 위로 포커스 승격됨을 확인.
  - 시작 메뉴 버튼(`button[aria-label="SaintVision 시작 메뉴"]`) 클릭 시 시작 메뉴 모달(`div[role="menu"]`) 정상 노출.
  - Escape 키 입력 시 시작 메뉴 모달이 즉시 닫히고 포커스 해제됨을 실측 확인.
- **증거 스크린샷**:
  - `scratch/real_chrome_desktop_03_start_menu_open.png`
  - `scratch/real_chrome_desktop_03_escape_dismissed.png`

### 3.4 [Invariant 4: PASS] 레이아웃 영속성 (Layout Persistence)
- **검증 내용**: `DesktopShell`의 창 상태(`position`, `size`, `isMinimized`, `isMaximized`, `zIndex`)의 `localStorage` 직렬화 및 컴포넌트 리마운트 시 `restoreDesktopLayout` 프로토콜을 통한 복원.
- **실측 결과**:
  - 초기 기동 시 8개 창 구성이 `localStorage.getItem('saintvision_desktop_windows')`에 배열로 정상 직렬화 확인.
  - `AI Model Studio` 창을 최소화한 뒤, `localStorage` 내 `model-studio` 항목의 `isMinimized`가 `true`로 갱신됨을 확인.
  - Portal 모드로 전환하여 `DesktopShell`을 완전히 언마운트한 후, 다시 Web Desktop으로 진입하여 리마운트 수행.
  - `restoreDesktopLayout`에 의해 `AI Model Studio` 창이 최소화 상태를 유지하여 DOM에 노출되지 않음을 확인.
  - 독 아이콘 클릭 시 저장된 위치/크기로 다시 활성화됨을 검증 완료.
- **증거 스크린샷**:
  - `scratch/real_chrome_desktop_04_layout_persistence.png`

---

## 4. WCAG AA 대비율 및 정량 측정

웹 데스크톱의 핵심 UI 구성요소에 대해 WCAG 2.1 AA 기준(텍스트 대비 최소 4.5:1 이상)을 실제 계산 엔진을 통해 검속하였다:

- **상단 시스템 메뉴 바 텍스트 (`rgb(248, 250, 252)` on `rgb(15, 23, 42)`)**:
  - 계산 대비율: **17.06:1** (기준치 4.5:1 대비 대폭 초과, **PASS**)
- **활성 창 타이틀 텍스트 (`rgb(248, 250, 252)` on `rgb(30, 41, 59)`)**:
  - 계산 대비율: **13.98:1** (기준치 4.5:1 대비 대폭 초과, **PASS**)

---

## 5. run_browser_smoke.mjs 미검증 해소 (unverified 4 -> 0)

`tools/run_browser_smoke.mjs`는 실제 브라우저 실측 증거(`scratch/desktop_ui_invariants.json`)가 존재하고 `verified: true`일 경우, 종래 `recordUnverified`로 처리되던 4대 UI 불변식을 직접 단언(Assert)하도록 배선되었다:

- 미검증 항목 잔여 수: **4건 ➔ 0건 (전수 해소 완료)**.

---

## 6. 산출물 및 증거 파일

1. `scratch/desktop_ui_invariants.json`: 실측 요약, 불변식 4종 통과 결과, 대비율 수치 및 스크린샷 경로.
2. `scratch/chrome_real_uvicorn_acceptance_result.json`: Uvicorn 0.52.4 + Chrome 종단간 합격 결과.
3. 스크린샷 7종(7개):
   - `scratch/real_chrome_desktop_01_switcher_desktop.png`
   - `scratch/real_chrome_desktop_01_switcher_portal.png`
   - `scratch/real_chrome_desktop_02_minimized.png`
   - `scratch/real_chrome_desktop_02_window_manager.png`
   - `scratch/real_chrome_desktop_03_start_menu_open.png`
   - `scratch/real_chrome_desktop_03_escape_dismissed.png`
   - `scratch/real_chrome_desktop_04_layout_persistence.png`
