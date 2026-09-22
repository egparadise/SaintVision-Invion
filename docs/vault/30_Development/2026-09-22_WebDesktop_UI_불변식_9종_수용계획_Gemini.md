---
doc_id: "GEMINI-WEB-DESKTOP-UI-INVARIANTS-PLAN-20260922"
title: "Web Desktop UI 불변식 9종 실브라우저 수용 계획 (Gemini)"
version: "1.3.0"
status: "in_progress"
author: "Gemini"
updated: "2026-09-22T23:05:00+09:00"
source_of_truth: "Git"
tags: ["desktop", "invariants", "browser-acceptance", "a11y", "wcag", "playwright"]
---

# Web Desktop UI 불변식 9종 실브라우저 수용 계획 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스]]
> - [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]] (VF-GM 트랙)
> - [[2026-09-22_WebDesktop_4대UI불변식_및_A11y실측검증_Gemini]] (19:40 Track 15 4대 불변식 실측 보고)
> - `tools/run_browser_smoke.mjs` (UI 불변식 unverified 4건 이관 경계)
> - `tools/check_frontend_integrity.py` (프런트엔드 9대 구조적 무결성 규칙)

---

## 1. 개요 및 정본 정합 (4종 ↔ 9종 대응 체계)

본 계획서는 SaintVision Web Desktop Shell의 신뢰성과 접근성을 보장하기 위해, 2026-09-22 19:40 실측 보고([[2026-09-22_WebDesktop_4대UI불변식_및_A11y실측검증_Gemini]])에서 1차 검증되었던 **Track 15 4대 UI 불변식**을 프로덕션 코드(`apps/web/src`)의 실제 구현에 1:1 대응하도록 재분할 및 신규 항목을 보강하여 **총 9종의 UI 불변식(Invariants)** 으로 체계화한 정본 계획이다.

### 1.1 Track 15 4대 불변식 ↔ 9대 불변식 매핑 대응표

| 종래 4대 불변식 (19:40 실측) | 재분할 및 신규 9대 불변식 | 대상 컴포넌트 | 비고 및 변경 사유 |
|---|---|---|---|
| **1. 양방향 전환기** | **INV-01 (양방향 전환기)** | `Header.tsx`<br>`DesktopShell.tsx` | Portal ↔ Web Desktop 왕복 마운트 격리 |
| **2. 창 관리자** | **INV-02 (트래픽 라이트 제어)**<br>**INV-03 (동적 z-index 승격)**<br>**INV-04 (하단 작업표시줄 연동)** | `DesktopWindow.tsx`<br>`DesktopShell.tsx` | 단일 '창 관리자' 항목을 최소화/최대화/닫기(02), z-index 단조증가(03), 작업표시줄 토글(04)의 3개 독립 불변식으로 정밀 분할 |
| **3. 키보드 접근성** | **INV-05 (Alt+Tab 창 순환)**<br>**INV-06 (Escape 모달 탈출)** | `DesktopShell.tsx` | 키보드 내비게이션을 전역 리스너 Alt+Tab 창 전환(05)과 시작 메뉴 Escape 닫기(06)로 분할 |
| **4. 레이아웃 영속성** | **INV-07 (localStorage 영속성)** | `desktopLayout.ts`<br>`DesktopShell.tsx` | 8개 창 상태의 `saintvision_desktop_windows` 직렬화 및 리마운트 복원 |
| *(신규 보강)* | **INV-08 (WCAG 2.1 AA 대비율)** | `DesktopShell.tsx`<br>`DesktopWindow.tsx` | WCAG 2.1 AA 기준($\ge 4.5:1$) 충족 여부 실측 (상단바 17.26:1, 활성 타이틀 13.98:1, 비활성 타이틀 6.99:1) |
| *(신규 보강)* | **INV-09 (정직 수치 및 고지)** | `ResourceExplorer.tsx` | 논리 패브릭 한계($0 \le \text{allocatable} \le \text{total}$) 및 Anti-Magic Bus 고지 배너 노출 |

---

## 2. Web Desktop UI 불변식 9종 매핑 매트릭스 (실제 프로덕션 코드 1:1 대조)

> [!IMPORTANT]
> 본 매트릭스는 `apps/web/src`에 실제 존재하는 DOM 속성, 셀렉터, 컴포넌트 소스 코드의 실제 동작만을 기반으로 작성되었다. 가상 셀렉터나 미구현 기능은 명시적으로 분리 표기한다.

| 번호 | 불변식 명칭 (Invariant) | 대상 컴포넌트 | 실제 DOM 셀렉터 / 트리거 | 실제 코드 기반 기대값 및 검증 단언 | 구현 현황 및 한계 정직 고지 |
|:---:|---|---|---|---|---|
| **INV-01** | **양방향 전환기** | `Header.tsx`<br>`DesktopShell.tsx`<br>`App.tsx` | • 진입: `Header`의 `button[aria-label="Web Desktop으로 전환"]`<br>• 복귀: `DesktopShell`의 `button[data-testid="desktop-mode-switcher"]` (title: `"📑 클래식 포털 뷰로 전환"`)<br>• 컨테이너: `div[data-testid="desktop-shell-container"]` | • 진입 시 `desktop-shell-container`가 뷰포트 전체 점유 (`fixed inset-0`)<br>• 복귀 클릭 시 `App.tsx`의 `setDesktop(false)`에 의해 Desktop 완전 언마운트 및 포털 Header 복원<br>• 왕복 전환 간 고스트 DOM 0건 | **구현 완료 (100%)**<br>(진입 버튼은 data-testid 없이 aria-label 사용) |
| **INV-02** | **창 관리자 트래픽 라이트** | `DesktopWindow.tsx`<br>(내 컴퓨터 등) | • 닫기: `button[aria-label="창 닫기: ${title}"]`<br>• 최소화: `button[aria-label="창 최소화: ${title}"]`<br>• 최대화/복원: `button[aria-label="최대화: ${title}"]` 및 `button[aria-label="원래 크기로 복원: ${title}"]` | • **최소화**: `display: none`이 아닌 `if (isMinimized) return null;`에 의한 **React 컴포넌트 언마운트**.<br>• **최대화**: `top: 36px`, `bottom: 68px`, `width: 100%`, `height: calc(100% - 104px)`.<br>• **복원**: 원래 저장된 좌표 및 크기로 즉시 복귀.<br>• **닫기**: `openWindows` 배열에서 제외되어 인스턴스 소멸. | **구현 완료 (100%)**<br>(최소화는 DOM 은닉이 아닌 React 언마운트임) |
| **INV-03** | **동적 z-index 승격** | 다중 윈도우 환경<br>(`DesktopShell.tsx`) | • 창 식별: `div[role="dialog"]` (`aria-labelledby="window-title-${id}"`)<br>• 마우스 클릭: `onMouseDown={() => onFocus(id)}` | • 비활성 창 포커스 시 `DesktopShell.tsx:206`의 `maxZ + 1` 로직에 의해 $z_{\text{active}} > z_{\text{prev}}$ 단조 증가 승격 ($23 > 22 > 21$).<br>• 최상위 창 아래로 타 윈도우가 정상 레이어 배치됨. | **구현 완료 (100%)**<br>(data-window-id 없음, role="dialog" 사용) |
| **INV-04** | **작업표시줄 연동 및 상태 복원** | `DesktopShell.tsx`<br>(하단 바) | • 작업표시줄: `div[role="toolbar"][data-testid="desktop-taskbar"]`<br>• 앱 버튼: `button[aria-label="실행 또는 활성화: ${item.title}"]`<br>• 실행 표시점: `isOpen && 인라인 4px 원 (rgb(56, 189, 248))` | • 실행 중인 창에 대해 하단에 시각적 활성 dot 노출.<br>• 최소화된 창의 버튼 클릭 시 `isMinimized = false` 및 활성 승격 복구.<br>• 최상위 활성 창의 버튼 재클릭 시 최소화(`isMinimized = true`) 토글 동작. | **구현 완료 (100%)**<br>(독 컴포넌트 분리 없음, DesktopShell 내부 인라인 구현) |
| **INV-05** | **키보드 접근성 창 순환** | `DesktopShell.tsx`<br>(전역 키보드 리스너) | • 단축키: `e.altKey && e.key === 'Tab'`<br>• 전역 리스너: `handleKeyDown` (`DesktopShell.tsx:220`) | • `Alt+Tab` keydown 시 HUD 오버레이나 Alt 릴리즈 감지 단계 없이, 열린 창 목록(`sorted[1]`)을 감지하여 즉시 `focusWindow(nextWin.id)` 호출.<br>• 타깃 창의 `zIndex`가 즉각 승격됨. | **구현 완료 (100%)**<br>⚠️ **한계 고지**: 시각적 `alt-tab-hud` 및 Alt 릴리즈 지연 선택은 미구현. keydown 즉시 전환됨. |
| **INV-06** | **Escape 모달 탈출** | `DesktopShell.tsx`<br>(시작 메뉴) | • 메뉴 버튼: `button[aria-label="SaintVision 시작 메뉴"]`<br>• 메뉴 모달: `div[role="menu"]`<br>• 탈출 키: `e.key === 'Escape'` (`DesktopShell.tsx:215`) | • 시작 메뉴 오픈(`isStartMenuOpen === true`) 상태에서 `Escape` 키 입력 시 `setIsStartMenuOpen(false)` 호출로 메뉴 닫힘.<br>• 배경 클릭 시에도 동일 닫힘 동작. | **부분 완료 (70%)**<br>⚠️ **한계 고지**: 메뉴 닫힘은 정상이나, **트리거 버튼으로의 자동 focus 복원 로직은 미구현** (포커스 복구 별도 a11y 카드 필요). |
| **INV-07** | **레이아웃 영속성** | `desktopLayout.ts`<br>`DesktopShell.tsx` | • 스토리지 키: `'saintvision_desktop_windows'`<br>• 복원 함수: `desktopLayout.ts`의 `restoreDesktopLayout()` | • 창 상태 변경 시 `localStorage`에 JSON 직렬화 저장.<br>• Portal 전환 후 Web Desktop 재진입(언마운트 후 리마운트) 시 이전 최소화 상태, 좌표, 크기가 동일하게 복원됨. | **구현 완료 (100%)**<br>(useDesktopPersistence.ts 없음, desktopLayout.ts 사용) |
| **INV-08** | **WCAG 2.1 AA 색상 대비율** | 상단 시스템 바<br>윈도우 타이틀바 | • 상단 바: 인라인 style (`rgba(15, 23, 42, 0.85)` 배경, `#f8fafc` 텍스트)<br>• 창 타이틀: `div#window-title-${id}` (활성창 `#1e293b` 배경, `#f8fafc` 텍스트; 비활성창 `#111827` 배경, `rgb(156, 163, 175)` 텍스트) | • WCAG 2.1 Level AA 일반 텍스트 기준 **$\ge 4.5:1$** 충족.<br>• 실측 측정치:<br>  - 상단 메뉴 바: **17.26:1** (AA 기준 초과 충족)<br>  - 활성 창 타이틀바: **13.98:1** (AA 기준 초과 충족)<br>  - 비활성 창 타이틀바: **6.99:1** (AA 기준 초과 충족) | **구현 완료 (100%)**<br>(4.5:1이 규격 기준이며 실측치 전수 충족) |
| **INV-09** | **정직 수치 및 Anti-Magic 고지** | `ResourceExplorer.tsx`<br>(내 컴퓨터) | • 고지 배너: `ResourceExplorer.tsx:252`<br>• 수치 카드: `data-testid="logical-vcpu-card"`, `"logical-ram-card"`, `"logical-gpu-card"` | • **고지 배너 원문 일치**: `⚠️ SaintVision 가상 컴퓨터 패브릭은 분산 노드들의 자원을 논리적으로 집약한 뷰입니다. 단일 하드웨어 버스로 마법처럼 병합된 것이 아니며...`<br>• **수학적 불변식**: $0 \le \text{allocatableCores} \le \text{totalCores}$ 항시 성립.<br>• 미관측 필드는 합성 0이 아닌 `null` 보존. | **구현 완료 (100%)**<br>⚠️ **정정**: ResourceExplorer에는 `reserved`/`offered`가 없음 (NodeDetail의 영역임). |

---

## 3. 세부 시나리오 검증 프로토콜

### 3.1 시나리오 1: 양방향 전환기 (INV-01)
1. **사전 조건**: 브라우저 포털 홈(`http://127.0.0.1:3005`) 마운트 상태.
2. **실행 단계**:
   - `Header.tsx`의 `button[aria-label="Web Desktop으로 전환"]` 클릭.
   - `div[data-testid="desktop-shell-container"]` 마운트 및 `fixed inset-0` 스타일 확인.
   - 상단 바의 `button[data-testid="desktop-mode-switcher"]` ("📑 클래식 포털 뷰로 전환") 클릭.
3. **통과 기준**: 포털 홈으로 복귀하며 Desktop Shell DOM 인스턴스가 0건으로 언마운트되어야 함.

### 3.2 시나리오 2: 창 관리자 트래픽 라이트 (INV-02)
1. **사전 조건**: Web Desktop 진입 후 `내 컴퓨터 (Resource Explorer)` 창이 열려 있는 상태.
2. **실행 단계**:
   - 최소화 버튼 `button[aria-label^="창 최소화: 내 컴퓨터"]` (또는 `button[aria-label="창 최소화: 내 컴퓨터 (Resource Explorer)"]`) 클릭 ➔ React 컴포넌트가 언마운트(`return null`)되어 `role="dialog"` 요소가 DOM에서 완전히 사라지는지 확인.
   - 하단 작업표시줄 버튼 클릭 ➔ 창이 다시 DOM에 마운트(un-minimize)되는지 확인.
   - 최대화 버튼 `button[aria-label^="최대화: 내 컴퓨터"]` (또는 `button[aria-label="최대화: 내 컴퓨터 (Resource Explorer)"]`) 클릭 ➔ 인라인 스타일이 `top: 36px`, `bottom: 68px`, `height: calc(100% - 104px)`로 적용되는지 확인.
   - 복원 버튼 `button[aria-label^="원래 크기로 복원: 내 컴퓨터"]` (또는 `button[aria-label="원래 크기로 복원: 내 컴퓨터 (Resource Explorer)"]`) 클릭 ➔ 기본 크기(920x600)로 복귀 확인.
   - 닫기 버튼 `button[aria-label^="창 닫기: 내 컴퓨터"]` (또는 `button[aria-label="창 닫기: 내 컴퓨터 (Resource Explorer)"]`) 클릭 ➔ `openWindows`에서 제거 확인.
3. **통과 기준**: 트래픽 라이트 4개 상태 전이가 코드 정의대로 완결되어야 함.

### 3.3 시나리오 3: 동적 z-index 승격 (INV-03)
1. **사전 조건**: 3개 창(`내 컴퓨터`, `파일 탐색기`, `모델 스튜디오`)이 겹쳐 열린 상태.
2. **실행 단계**:
   - 비활성 창 클릭 ➔ `style.zIndex` 추출.
   - 또 다른 비활성 창 클릭 ➔ `style.zIndex` 추출.
3. **통과 기준**: 클릭 시마다 `DesktopShell.tsx`의 `maxZ + 1` 로직에 의해 $z_{\text{active}} > z_{\text{prev}}$ 단조 증가가 엄격히 성립해야 함 ($23 > 22 > 21$).

### 3.4 시나리오 4: 작업표시줄 연동 및 상태 복원 (INV-04)
1. **사전 조건**: `내 컴퓨터` 창이 최소화(`isMinimized === true`)된 상태.
2. **실행 단계**:
   - `div[data-testid="desktop-taskbar"]` 내 `button[aria-label^="실행 또는 활성화: 내 컴퓨터"]` (또는 `button[aria-label="실행 또는 활성화: 내 컴퓨터 (Resource Explorer)"]`) 탐색.
   - 버튼 클릭 ➔ 창이 즉시 복구(un-minimize)되고 최상위 z-index로 승격되는지 확인.
   - 최상위 상태에서 동일 버튼 재클릭 ➔ 최소화 상태(`isMinimized === true`)로 토글되는지 확인.
3. **통과 기준**: 버튼 클릭에 따른 창 상태 토글 및 하단 시각 dot(인라인 4px 원 `rgb(56, 189, 248)`) 동기화 확인.

### 3.5 시나리오 5: 키보드 접근성 창 순환 (INV-05)
1. **사전 조건**: 2개 이상의 창이 열려 있는 상태.
2. **실행 단계**:
   - `Alt + Tab` 키다운 이벤트 주입.
3. **통과 기준**: 전역 리스너가 감지하여 `focusWindow(nextWin.id)`를 즉시 호출, 다음 대상 창의 z-index가 즉각 승격되어야 함 (HUD 부재 및 keydown 즉시 전환을 정직하게 단언).

### 3.6 시나리오 6: Escape 모달 탈출 프로토콜 (INV-06)
1. **사전 조건**: 좌측 상단 시작 메뉴(`button[aria-label="SaintVision 시작 메뉴"]`) 클릭으로 `div[role="menu"]`가 열린 상태.
2. **실행 단계**:
   - 키보드 `Escape` 키 입력.
3. **통과 기준**:
   - `div[role="menu"]`가 즉시 닫힘 (`isStartMenuOpen === false`) ➔ **PASS**.
   - 트리거 버튼 포커스 복원 여부 검사 ➔ **UNVERIFIED (코드 미구현으로 인한 한계 정직 기록)**.

### 3.7 시나리오 7: localStorage 레이아웃 영속성 (INV-07)
1. **사전 조건**: 사용자가 특정 창을 최소화하거나 이동한 상태.
2. **실행 단계**:
   - `localStorage.getItem('saintvision_desktop_windows')` 값 추출 및 JSON 파싱.
   - 상단 모드 스위처(`data-testid="desktop-mode-switcher"`)를 통해 포털로 전환 (데스크톱 언마운트).
   - 다시 Web Desktop으로 진입 (데스크톱 리마운트).
3. **통과 기준**: `restoreDesktopLayout`에 의해 리마운트된 창 배열의 최소화 상태 및 좌표/크기가 언마운트 전과 동일하게 복원되어야 함.

### 3.8 시나리오 8: WCAG 2.1 AA 색상 대비율 (INV-08)
1. **사전 조건**: 브라우저 렌더링 완료 상태.
2. **실행 단계**:
   - 상단 시스템 바(인라인 `rgba(15, 23, 42, 0.85)`) 및 창 타이틀바(활성 `#1e293b`, 비활성 `#111827`)의 텍스트 색상(`getComputedStyle().color`)과 배경색(`backgroundColor`) 추출.
   - 상대 휘도(Relative Luminance) 공식 적용:
     $$L = 0.2126 R + 0.7152 G + 0.0722 B, \quad \text{Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$
3. **통과 기준**:
   - WCAG 2.1 Level AA 일반 텍스트 기준 **$\ge 4.5:1$** 전수 초과 달성 (실측치: 상단바 17.26:1, 활성 타이틀바 13.98:1, 비활성 타이틀바 6.99:1).

### 3.9 시나리오 9: 정직 수치 및 Anti-Magic Bus 고지 (INV-09)
1. **사전 조건**: `ResourceExplorer` 컴포넌트 마운트 (`내 컴퓨터`).
2. **실행 단계**:
   - `ResourceExplorer.tsx:252`의 고지 배너 DOM 노출 확인.
   - `overview` 탭의 총 코어(`totalCores`) 및 할당 가능 코어(`allocatableCores`) 수치 추출.
3. **통과 기준**:
   - 고지 배너가 원문 그대로 누락 없이 렌더링되어 하드웨어 버스 마법 병합 오해를 원천 차단해야 함.
   - $0 \le \text{allocatableCores} \le \text{totalCores}$ 관계가 엄격히 성립해야 함.

---

## 4. 실측 실행 명령 및 Git 영구 증거 경로

1. **단위 및 경계 검증 시험**:
   - Vitest 레이아웃 단위 시험: `npx --prefix apps/web vitest run apps/web/tests/desktop-layout.test.tsx`
   - 스모크 경계 불변식 시험: `pytest tests/test_browser_smoke_boundary.py`
   - 프런트엔드 무결성 게이트: `python -X utf8 tools/check_frontend_integrity.py`
2. **실브라우저 종단간(E2E) 수용 시험 명령**:
   - `.venv\Scripts\python.exe -X utf8 tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants`
   - (Google Chrome Official Build 153.0.7444.135 Headless, Uvicorn 8080, Vite 3005)
3. **Git 영구 증거 보존 경로 (F4)**:
   - Git 미추적 임시 경로(`scratch/`) 대신 Git 정본 증거 경로 **`docs/vault/30_Development/Evidence/desktop_ui_invariants.json`** 에 전수 커밋 보존.
   - 시각 스크린샷 8종은 `scratch/real_chrome_desktop_*.png`로 로컬에 보존하고 History 문서에 상대 경로 및 바이트 크기 명시.
