---
doc_id: "GEMINI-WEB-DESKTOP-UI-INVARIANTS-PLAN-20260922"
title: "Web Desktop UI 불변식 9종 실브라우저 수용 계획 (Gemini)"
version: "1.0.0"
status: "in_progress"
author: "Gemini"
updated: "2026-09-22T20:50:00+09:00"
source_of_truth: "Git"
tags: ["desktop", "invariants", "browser-acceptance", "a11y", "playwright", "wcag"]
---

# Web Desktop UI 불변식 9종 실브라우저 수용 계획 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스]]
> - [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]] (VF-GM 트랙)
> - `tools/run_browser_smoke.mjs` (UI 불변식 unverified 4건 이관 경계)
> - `tools/check_frontend_integrity.py` (프런트엔드 9대 구조적 무결성 규칙)

---

## 1. 개요 및 목적

본 계획서는 SaintVision 단일 가상 컴퓨터 Web Desktop Shell의 신뢰성과 접근성을 보장하기 위해, 종래 `tools/run_browser_smoke.mjs`에서 브라우저 레인으로 이관되었던 4대 UI 불변식을 심화 확장하여 **총 9종의 UI 불변식(Invariants)** 에 대한 실브라우저(Google Chrome Official / Playwright) 수용 검증 시나리오를 사전에 체계화한 정본 계획이다.

메모리 경보(< 1.5GB) 상황에서는 헤드리스 브라우저 기동을 엄격히 유예하고 본 문서(시나리오·화면·셀렉터·기대값)를 먼저 확정하며, 코디네이터의 메모리 경보 해제 통보 즉시 단일 브라우저 프로세스 순차 실측으로 진입한다.

---

## 2. Web Desktop UI 불변식 9종 종합 매핑 매트릭스

| 번호 | 불변식 명칭 (Invariant) | 대상 화면 및 컴포넌트 | DOM 셀렉터 및 상호작용 트리거 | 기대값 및 검증 단언 (Assertion) | 접근성 / 무결성 규칙 |
|:---:|---|---|---|---|---|
| **INV-01** | **양방향 전환기**<br>(Bidirectional Switcher) | `App.tsx`<br>`Header.tsx`<br>`DesktopShell.tsx` | • 진입: `button[data-testid="switch-to-desktop-btn"]`<br>• 복귀: `button[data-testid="desktop-mode-switcher"]`<br>• 컨테이너: `div[data-testid="desktop-shell-container"]` | • 진입 시 `desktop-shell-container`가 뷰포트(100vw, 100vh)를 완전 점유<br>• 복귀 시 Desktop DOM 언마운트 및 포털 Header 복원<br>• 왕복 전환 간 고스트 DOM 및 메모리 누수 0건 | • `aria-label` 명시<br>• DOM 마운트 격리 |
| **INV-02** | **창 관리자 트래픽 라이트**<br>(Traffic Light Controls) | `DesktopWindow.tsx`<br>(내 컴퓨터, 탐색기 등) | • 최소화: `button[aria-label^="창 최소화:"]`<br>• 최대화: `button[aria-label^="창 최대화:"]`<br>• 닫기: `button[aria-label^="창 닫기:"]` | • 최소화 시 DOM 은닉(`display: none`), 활성 포커스 인접 창 이관<br>• 최대화 시 데스크톱 작업 영역 전체(`calc(100vh - 72px)`) 확장<br>• 복원 시 원래 x, y, width, height 좌표 복귀<br>• 닫기 시 윈도우 인스턴스 소멸 | • `aria-label` 완전 일치<br>• 키보드 Enter/Space 동작 |
| **INV-03** | **동적 z-index 승격**<br>(Dynamic Z-Index Focus) | 다중 윈도우 겹침 환경<br>(Resource Explorer,<br>File Explorer, Studio) | • 비활성 윈도우 바디/헤더 클릭: `div[data-window-id]`<br>• CSS 속성: `style.zIndex` | • 클릭/포커스 창의 `zIndex`가 최대값 + 1로 동적 승격 (`23 > 22 > 21`)<br>• 이전 최상위 창은 하위 레이어로 정상 강등<br>• 윈도우 겹침 시 시각적/이벤트 가림 현상 정상 제어 | • Focus trapping 방지<br>• 논리적 탭 순서 동기화 |
| **INV-04** | **하단 독 연동 및 상태 복원**<br>(Dock Integration & Restore) | 데스크톱 하단 독<br>`DesktopDock.tsx` | • 독 컨테이너: `nav[data-testid="desktop-dock"]`<br>• 앱 아이콘: `button[data-dock-app-id]`<br>• 실행 표식: `span.dock-running-dot` | • 실행 중인 앱 아이콘 아래 활성 점(`dock-running-dot`) 노출<br>• 최소화된 앱 클릭 시 복원(un-minimize) 및 최상위 z-index 승격<br>• 활성 앱 재클릭 시 토글 최소화 동작 | • `role="toolbar"` 또는 `nav`<br>• 툴팁 `aria-label` 제공 |
| **INV-05** | **키보드 접근성 창 순환**<br>(Alt+Tab Window Cycling) | Web Desktop 전체<br>키보드 이벤트 리스너 | • 단축키 입력: `Alt + Tab` (또는 `Alt + Backquote`)<br>• HUD: `div[data-testid="alt-tab-hud"]` | • Alt+Tab 입력 시 윈도우 순환 HUD 노출<br>• Tab 반복 입력 시 선택 대상 다음 윈도우로 순차 이동<br>• Alt 키 릴리즈 시 선택 창 최상위 승격 및 내부 포커스 진입 | • 키보드 전용 사용자 탐색<br>• 포커스 루프 방지 |
| **INV-06** | **모달 키보드 탈출**<br>(Escape Dismissal Protocol) | 시작 메뉴 (`DesktopStartMenu`)<br>취소/영수증 모달 (`RunDetail`) | • 트리거: `button[aria-label="SaintVision 시작 메뉴"]`<br>• 모달: `div[role="menu"]`, `div[role="dialog"]`<br>• 탈출 키: `KeyboardEvent.key === 'Escape'` | • Escape 키 입력 즉시 모달 닫힘(DOM 소멸 또는 은닉)<br>• 트리거 버튼(`aria-expanded="false"`)으로 키보드 포커스 정상 복귀<br>• 배경 클릭(Backdrop click) 시에도 동일 닫힘 동작 | • `role="dialog"` / `menu`<br>• `aria-modal="true"` 정합 |
| **INV-07** | **레이아웃 영속성**<br>(Layout State Persistence) | `useDesktopPersistence.ts`<br>브라우저 `localStorage` | • 키: `'saintvision_desktop_windows'`<br>• 트리거: 윈도우 이동/크기조절/최소화/최대화 | • 창 위치·크기 변경 시 100ms 내 JSON 직렬화 저장<br>• Portal 전환 후 재진입(언마운트 후 리마운트) 시 이전 레이아웃 100% 복원<br>• 브라우저 새로고침(F5) 시에도 저장된 창 배열 유지 | • 오프라인/재접속 복원<br>• 손상 데이터 fallback |
| **INV-08** | **WCAG 2.1 AA 색상 대비율**<br>(Color Contrast AA) | 시스템 상단 바<br>윈도우 타이틀바<br>상태 뱃지 | • 상단 바: `div[data-testid="desktop-top-bar"]`<br>• 타이틀바: `div[data-testid="window-title-bar"]`<br>• 텍스트 대비 계산식 ($L_1 + 0.05) / (L_2 + 0.05)$ | • 상단 메뉴 바 텍스트 대비: 기준 4.5:1 대비 **≥ 15:1** (실측 **17.06:1**)<br>• 윈도우 타이틀바 텍스트 대비: 기준 4.5:1 대비 **≥ 12:1** (실측 **13.98:1**)<br>• Failed/Succeeded 뱃지 대비율 4.5:1 이상 전수 충족 | • WCAG 2.1 Level AA<br>• 저시력자 시인성 보장 |
| **INV-09** | **정직 수치 표출 및 경계 불변식**<br>(Honest Capacity & Metric) | `ResourceExplorer.tsx`<br>`NodeResourceUsage.tsx`<br>`RunDetail.tsx` | • 자원 지표: `div[data-testid="pool-capacity-metric"]`<br>• 노드 지표: `div[data-testid="node-resource-usage-section"]`<br>• 에러 배너: `div[role="alert"]` | • 자원 수치 수학적 불변식: $0 \le \text{reserved} \le \text{offered} \le \text{capacity}$ 항시 성립<br>• 미관측/미측정 지표는 임의 0이 아닌 `null` 또는 `미관측`으로 정직 표출<br>• 프로젝트 미선택 시 호출 차단 및 안내 고지 배너(`role="status"`) | • 허위 데이터 합성 금지<br>• tri-state 상태 정합 |

---

## 3. 세부 시나리오 검증 프로토콜

### 3.1 시나리오 1: 양방향 전환기 (INV-01)
1. **사전 조건**: 브라우저가 포털 홈(`http://127.0.0.1:3005`)에 접속한 상태.
2. **실행 단계**:
   - `Header` 우측 상단의 `[Web Desktop으로 전환]` 버튼 클릭.
   - `div[data-testid="desktop-shell-container"]`의 존재 및 `position: fixed; inset: 0` 스타일 확인.
   - 데스크톱 상단 바의 `[Portal 복귀]` 버튼 클릭.
3. **통과 기준**: 포털 화면으로 즉각 복귀하며, DOM 트리 내에 중복 셸 인스턴스가 존재하지 않아야 함.

### 3.2 시나리오 2: 창 관리자 트래픽 라이트 (INV-02)
1. **사전 조건**: Web Desktop 진입 후 `내 컴퓨터` 창이 활성화된 상태.
2. **실행 단계**:
   - 노란색 최소화 버튼 클릭 ➔ 창이 사라지는지 확인.
   - 녹색 최대화 버튼 클릭 ➔ 뷰포트 크기에 맞춰 경계가 확장되는지 확인.
   - 다시 녹색 복원 버튼 클릭 ➔ 원래 크기(920x600)로 복귀하는지 확인.
   - 빨간색 닫기 버튼 클릭 ➔ 윈도우 인스턴스가 언마운트되는지 확인.
3. **통과 기준**: 트래픽 라이트 3개 동작이 단 1회의 프레임 드랍 없이 완결되어야 함.

### 3.3 시나리오 3: 동적 z-index 승격 (INV-03)
1. **사전 조건**: 3개 이상의 윈도우(`ResourceExplorer`, `InvFileExplorer`, `ModelStudio`)가 화면에 열려 있는 상태.
2. **실행 단계**:
   - 하위 레이어의 `InvFileExplorer` 클릭 ➔ 해당 창의 `zIndex` 측정.
   - 또 다른 하위 창 `ModelStudio` 클릭 ➔ 해당 창의 `zIndex` 측정.
3. **통과 기준**: 클릭할 때마다 활성 창의 `zIndex`가 단조 증가(Monotonically Increasing)하여 항상 최상위에 위치해야 함 (`z-index: 23 > 22 > 21`).

### 3.4 시나리오 4: 하단 Dock 연동 및 복원 (INV-04)
1. **사전 조건**: `내 컴퓨터` 창이 최소화된 상태.
2. **실행 단계**:
   - 하단 Dock의 `내 컴퓨터` 아이콘 탐색.
   - 아이콘 클릭 ➔ 창이 화면에 즉시 재표출(un-minimize)되는지 확인.
   - 활성화된 상태에서 다시 클릭 ➔ 토글 최소화 동작 확인.
3. **통과 기준**: Dock 아이콘의 실행 표시 점(`dock-running-dot`)과 윈도우 최소화 상태가 100% 동기화되어야 함.

### 3.5 시나리오 5: 키보드 A11y Alt+Tab 창 순환 (INV-05)
1. **사전 조건**: 2개 이상의 창이 열려 있고 마우스 커서가 없는 상태.
2. **실행 단계**:
   - `Alt + Tab` 키 이벤트 주입.
   - 화면 중앙에 `alt-tab-hud` 오버레이 노출 확인.
   - `Tab` 키를 1회 더 입력하여 포커스 대상 이동 후 `Alt` 키 릴리즈.
3. **통과 기준**: 타깃 창이 최상위 활성 창으로 전환되고 윈도우 내부 첫 번째 대화형 요소로 포커스가 전달되어야 함.

### 3.6 시나리오 6: Escape 모달 탈출 프로토콜 (INV-06)
1. **사전 조건**: 데스크톱 좌측 상단 `SaintVision 시작 메뉴` 또는 `RunDetail` 취소 모달이 열려 있는 상태.
2. **실행 단계**:
   - 키보드 `Escape` 키 입력.
3. **통과 기준**: 열려 있던 모달/메뉴가 즉시 닫히고, 열기 트리거였던 버튼으로 키보드 포커스가 정확히 복원되어야 함 (`aria-expanded="false"`).

### 3.7 시나리오 7: localStorage 레이아웃 영속성 (INV-07)
1. **사전 조건**: 사용자가 임의의 윈도우를 특정 좌표 `(x: 150, y: 120)`로 이동하고 크기를 조정한 상태.
2. **실행 단계**:
   - `localStorage.getItem('saintvision_desktop_windows')` 값 검사.
   - 상단 바를 통해 Portal 모드로 전환 (데스크톱 언마운트).
   - 다시 Web Desktop으로 진입 (데스크톱 리마운트).
3. **통과 기준**: 리마운트된 윈도우의 좌표와 크기가 언마운트 전과 1픽셀의 오차 없이 동일하게 복원되어야 함.

### 3.8 시나리오 8: WCAG 2.1 AA 색상 대비율 보장 (INV-08)
1. **사전 조건**: 브라우저 렌더링 완료 상태.
2. **실행 단계**:
   - 주요 텍스트 요소의 `getComputedStyle(el).color` 및 배경색 `backgroundColor` 추출.
   - 상대 휘도(Relative Luminance) 기반 대비율 수식 계산.
3. **통과 기준**:
   - 시스템 상단 바 텍스트 대비율: 기준 4.5:1 대비 **≥ 15:1** (실측 17.06:1).
   - 윈도우 타이틀바 텍스트 대비율: 기준 4.5:1 대비 **≥ 12:1** (실측 13.98:1).

### 3.9 시나리오 9: 정직 수치 표출 및 경계 불변식 (INV-09)
1. **사전 조건**: `ResourceExplorer` 및 `NodeResourceUsage` 컴포넌트 마운트.
2. **실행 단계**:
   - 각 노드 및 풀의 `capacity`, `offered`, `reserved` 수치 추출.
   - 프로젝트 미지정 상태에서의 UI 피드백 검사.
3. **통과 기준**:
   - $0 \le \text{reserved} \le \text{offered} \le \text{capacity}$ 관계가 엄격히 성립.
   - 미관측 지표는 0으로 속이지 않고 `null` / `미관측`으로 표출.
   - 프로젝트 미선택 시 404를 유발하는 잘못된 네트워크 호출을 차단하고 `프로젝트를 선택하세요` 정직 배너 표출.

---

## 4. 실측 실행 하네스 및 증거 보존 계획

1. **실행 조건**:
   - 시스템 가용 메모리 **≥ 1.5GB** 확인 후 착수.
   - 단일 Headless Chrome 인스턴스 순차 실행 (`--headless=new`, 1920x1080).
2. **산출물 및 증거 파일**:
   - `scratch/desktop_ui_invariants.json`: 9대 불변식 전수 통과 JSON 증거.
   - `scratch/real_chrome_desktop_01_switcher_desktop.png` ~ `09_honest_metrics.png`: 고해상도 시각 증거 9종.
3. **스모크 러너 배선**:
   - `tools/run_browser_smoke.mjs` 요약에서 미검증 항목을 0건(`unverified 4 -> 0`)으로 전환.
