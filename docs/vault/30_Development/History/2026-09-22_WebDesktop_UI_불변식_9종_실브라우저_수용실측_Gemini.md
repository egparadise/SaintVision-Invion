---
doc_id: "HIST-GEMINI-2026-09-22-UI-INVARIANTS-ACCEPTANCE"
title: "Web Desktop UI 불변식 9종 실브라우저 수용 실측 검증 보고 (변이 M1/M2 살해 및 정량 실측 v1.3.1)"
version: "1.3.1"
status: "completed"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-22T23:46:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["gemini", "browser-acceptance", "ui-invariants", "web-desktop", "mutation-testing", "a11y", "real-chrome"]
---

# Web Desktop UI 불변식 9종 실브라우저 수용 실측 검증 보고 (v1.3.1)

- **작업 일시**: 2026-09-22T23:48:22+09:00 (KST)
- **배정**: Gemini (Frontend & Browser Acceptance Owner)
- **독립 검토**: Claude (PR #66 Claude 재검토 r3 지적 사항 전수 반영)
- **참조 문서**: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], PR #61 계획서 v1.3.0 (`2026-09-22_WebDesktop_UI_불변식_9종_수용계획_Gemini` (PR #61)), [[2026-09-22_WebDesktop_4대UI불변식_및_A11y실측검증_Gemini]], `2026-09-22_PR66_WebDesktop_UI불변식_9종_실측_독립검토_Claude` (head `f5ed5a61`)

---

## 1. 개요 및 Claude 독립 검토 지적 사항(M1/M2/R1~R4) 전수 조치

Claude 리뷰어의 PR #66 독립 검토 및 재검토 r3 지침에 따라, 스크립트와 증거 JSON의 상수 하드코딩 및 느슨했던 검증을 전면 배제하고, 실제 프로덕션 DOM 및 동작에 1:1 결속하는 **실브라우저 엄밀 재실측(8 PASS, 1 PARTIAL)** 을 완결하였다.

### [주요 조치 및 되살림(Mutation) 살해 내역]
1. **변이 M1 살해 (INV-08 real DOM `window.getComputedStyle` 실측)**:
   - 종래의 상수 RGB 계산 방식을 완전히 제거하고, Playwright를 통해 실제 DOM `<header>` 및 `div[id^="window-title-"]`의 `getComputedStyle`을 직접 호출하여 `color` 및 `backgroundColor`를 추출해 상대 휘도 및 대비율을 실측.
   - 상단 바: DOM 텍스트 `rgb(248, 250, 252)` vs 합성 배경 `rgba(15, 23, 42, 0.85)` ➔ **17.26:1** (WCAG AA $\ge 4.5:1$ PASS).
   - 활성 창 타이틀: DOM 텍스트 `rgb(249, 250, 251)` vs 배경 `rgb(31, 41, 55)` ➔ **14.05:1** (WCAG AA $\ge 4.5:1$ PASS).
   - 비활성 창 타이틀: DOM 텍스트 `rgb(156, 163, 175)` vs 배경 `rgb(17, 24, 39)` ➔ **6.99:1** (WCAG AA $\ge 4.5:1$ PASS).
   - 만약 글자 색상이 `#334155`로 변이될 경우 대비율이 1.41:1로 폭락하여 단언이 즉시 실패(FAIL)하므로, **변이 M1은 완전히 KILLED됨**.
2. **변이 M2 살해 (INV-04 활성 창 독 클릭 시 토글 최소화 실측)**:
   - 최상위 활성 창(Model Studio)의 독 버튼을 클릭했을 때 창이 최소화(`isMinimized === true`, React 언마운트, `div[role="dialog"]` 사라짐)됨을 실단언.
   - 다시 독 버튼을 클릭했을 때 창이 복원(`visible`)됨을 실단언.
   - 독 버튼의 실행 활성 표시점(active dot: `width: 4px, height: 4px, backgroundColor: rgb(56, 189, 248)`) 존재 및 스타일 실측.
   - 만약 독 클릭이 항상 `focusWindow`로 변이될 경우 최소화되지 않아 단언이 즉시 실패하므로, **변이 M2는 완전히 KILLED됨**.
3. **INV-06 모달 탈출 및 포커스 복원 한계 정직 고지 (PARTIAL)**:
   - `Escape` 키 입력 시 시작 메뉴 닫힘(`isStartMenuOpen === false`)은 실측 PASS.
   - 트리거 버튼 포커스 복원은 `DesktopShell.tsx`에 미구현되어 있음을 `document.activeElement` 실측으로 확인하고, 허위 PASS 없이 **PARTIAL (8 PASS / 1 PARTIAL)** 로 정직 고지.
4. **INV-07 레이아웃 영속성 형상(Geometry) 직렬화 및 복원 실측**:
   - `localStorage`의 `saintvision_desktop_windows`에서 Model Studio의 직렬화 형상($x=120, y=90, w=1000, h=640$)을 추출하여 검증.
   - Portal 언마운트 후 복귀 시 실제 창 크기가 $1000 \times 640$으로 100% 일치 복원됨을 바운딩 박스로 실단언.
5. **INV-09 정직 수치 및 Anti-Magic Bus 경계 실측**:
   - `ResourceExplorer.tsx` DOM에서 `data-testid="logical-vcpu-card"`의 내부 텍스트를 정규식으로 파싱하여 실제 수치 추출: 총 $16$ Cores, 스케줄 가용 $12$ Cores, 실시간 점유 $4.8$ Cores.
   - 수학적 불변식 $0 \le \text{allocatable} (12) \le \text{total} (16)$ 성립을 실단언.
   - Anti-Magic Bus 고지 배너("단일 하드웨어 버스로 마법처럼 병합된 것이 아니며...") DOM 노출 확인.
6. **Claude 재검토 r3 요구 4건(R1~R4) 전수 조치**:
   - **R1 (gitCommitSha 동적 추출 및 상수 fallback 제거)**: `tools/run_real_browser_acceptance.py`에 `import subprocess`를 모듈 최상단에 배치하고 `subprocess.check_output(["git", "rev-parse", "HEAD"])`로 동적 추출, 실패 시 `None`(`null`)으로 처리하여 상수 SHA fallback을 원천 제거.
   - **R2 (vault 증거 매 실행 덮어쓰기 분리 및 러너 HEAD/조상 대조 가드)**:
     - 스크립트에 `--commit-evidence` 플래그를 신설하여 명시적 플래그가 주어졌을 때만 vault 파일(`docs/vault/.../desktop_ui_invariants.json`)을 갱신하도록 분리.
     - `tools/run_browser_smoke.mjs`에 `git rev-parse HEAD` 및 `git merge-base --is-ancestor` 대조 가드를 구축하여, 커밋된 증거의 SHA가 현재 HEAD 또는 조상 커밋이 아닐 경우 `[STALE-EVIDENCE]`로 격리하고 unverified 상태를 엄격히 유지.
   - **R3 ("Window Active Title Text"와 비활성 타이틀 분리 실측)**:
     - DOM `div[role="dialog"]`의 헤더 배경색(`#1e293b` ➔ `rgb(30, 41, 59)` / `rgb(31, 41, 55)`) 및 텍스트 색상(`rgb(249, 250, 251)`)을 통해 활성 창 타이틀(**14.05:1**)과 비활성 창 타이틀(`rgb(156, 163, 175)` on `rgb(17, 24, 39)`, **6.99:1**)을 정확히 분리 실측 및 단언.
   - **R4 (커밋된 스크립트로 증거 재생성)**:
     - 수정된 스크립트를 커밋(`cd2b54f4`)한 후 해당 스크립트를 직접 실행하여 증거 JSON 정본(`desktop_ui_invariants.json`)을 100% 실측치로 갱신.

---

## 2. 9대 UI 불변식 실측 단언 결과표 (8 PASS, 1 PARTIAL)

| 번호 | 불변식 명칭 (Invariant) | 대상 DOM 셀렉터 및 단언 기준 | 실측 동작 및 검증 단언 (Assertion) | 판정 | 세부 실측치 및 변이 살해 증거 |
|:---:|---|---|---|:---:|---|
| **INV-01** | **양방향 전환기** | `Header.tsx` `aria-label="Web Desktop으로 전환"`<br>`[data-testid="desktop-mode-switcher"]` | • Portal ➔ Web Desktop `desktop-shell-container` 마운트 실측<br>• 상단 바 복귀 버튼("📑 클래식 포털 뷰로 전환") 클릭 시 언마운트 및 왕복 복귀 실측 | **PASS** | 양방향 전환 완결<br>`real_chrome_desktop_01_switcher_desktop.png`<br>`real_chrome_desktop_01_switcher_portal.png` |
| **INV-02** | **창 관리자 트래픽 라이트** | `button[aria-label^="창 최소화:"]`<br>`button[aria-label^="최대화:"]`<br>`button[aria-label^="원래 크기로 복원:"]`<br>`button[aria-label^="창 닫기:"]` | • **최소화**: React 언마운트(`role="dialog"` DOM 소멸) 실측<br>• **최대화**: `height='calc(100% - 104px)'` (top 36px, bottom 68px, width 1920) 실측<br>• **복원**: 원래 크기($920 \times 600$) 복원 실측<br>• **닫기**: `openWindows` 소멸 실측 | **PASS** | 최대화 스타일 및 복원 크기 정밀 일치<br>`real_chrome_desktop_02_minimized.png`<br>`real_chrome_desktop_02_window_manager.png` |
| **INV-03** | **동적 z-index 승격** | 다중 창 (`role="dialog"`) | 창 포커스 시 `DesktopShell.tsx:206`에 의한 z-index 전이 실측: 초기 $21$ ➔ 새 창 $22$ ➔ 포커스 승격 $23$ ($23 > 22 > 21$ 단조 증가) | **PASS** | $23 > 22 > 21$ 단조 증가 성립 |
| **INV-04** | **작업표시줄 연동 및 토글** | `div[data-testid="desktop-taskbar"]`<br>`button[aria-label^="실행 또는 활성화:"]` | • 활성 창의 독 아이콘 클릭 시 **토글 최소화**(창 언마운트) 실측 (Kills M2)<br>• 최소화 상태에서 재클릭 시 창 복원 실측<br>• 활성 점(`width: 4px, height: 4px, bg: rgb(56, 189, 248)`) 스타일 실측 | **PASS** | **Mutation M2 KILLED**<br>토글 최소화 및 활성 점 연동 100% |
| **INV-05** | **Alt+Tab 창 순환** | 전역 keydown 리스너 | `Alt+Tab` 주입 시 시각적 HUD 없이 전역 keydown에서 즉시 다음 창 z-index 승격 실측: 내 컴퓨터($28$) > Model Studio($27$) | **PASS** | Alt+Tab keydown z-order 승격 완결 (HUD 부재 정직 반영) |
| **INV-06** | **Escape 모달 탈출** | `button[aria-label="SaintVision 시작 메뉴"]`<br>`div[role="menu"]` | • 시작 메뉴 오픈 후 `Escape` 입력 시 `div[role="menu"]` 즉시 닫힘 ➔ **PASS**<br>• **트리거 포커스 복원**: `document.activeElement` 검사 결과 React 셸에 미구현(ABSENT) 확인 ➔ **기술부채 정직 고지** | **PARTIAL**<br>(8/9 PASS) | 모달 닫힘 성공 / 포커스 복구 한계 고지<br>`real_chrome_desktop_03_start_menu_open.png`<br>`real_chrome_desktop_03_escape_dismissed.png` |
| **INV-07** | **레이아웃 영속성** | `saintvision_desktop_windows`<br>`desktopLayout.ts` | • `localStorage` 직렬화 형상($x=120, y=90, w=1000, h=640$) 실측<br>• 최소화 직렬화 및 셸 언마운트 후 재진입 시 $1000 \times 640$ 복원 실측 | **PASS** | 형상 직렬화 및 바운딩 박스 정합 완결<br>`real_chrome_desktop_04_layout_persistence.png` |
| **INV-08** | **WCAG 2.1 AA 색상 대비율** | `header`<br>`div[id^="window-title-"]` | **실제 DOM `window.getComputedStyle` 실측** (Kills M1):<br>• 상단 메뉴 바: 텍스트 `rgb(248, 250, 252)` vs `rgba(15, 23, 42, 0.85)` ➔ **17.26:1**<br>• 활성 창 타이틀: 텍스트 `rgb(249, 250, 251)` vs `rgb(31, 41, 55)` ➔ **14.05:1**<br>• 비활성 창 타이틀: 텍스트 `rgb(156, 163, 175)` vs `rgb(17, 24, 39)` ➔ **6.99:1**<br>• WCAG 2.1 Level AA 규격($\ge 4.5:1$) 전수 충족 (3개 항목 단언) | **PASS** | **Mutation M1 KILLED**<br>실제 DOM 스타일 실측 전수 합격 |
| **INV-09** | **정직 수치 및 Anti-Magic 고지** | `ResourceExplorer.tsx`<br>`[data-testid="logical-vcpu-card"]` | • DOM 텍스트 수치 실추출: 총 $16$ Cores, 가용 $12$ Cores, 점유 $4.8$ Cores<br>• 수학적 불변식 $0 \le 12 \le 16$ 성립 실단언<br>• Anti-Magic Bus 고지 배너 노출 실측 | **PASS** | $0 \le allocatable \le total$ 실단언 성립<br>`real_chrome_desktop_09_honest_metrics.png` |

---

## 3. 실측 실행 메트릭스 및 재현 명령

- **실행 명령**:
  ```powershell
  .venv\Scripts\python.exe -X utf8 tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants --commit-evidence
  ```
- **종료 코드 (Exit Code)**: `0`
- **소요 시간**: 28초
- **브라우저 엔진**: Google Chrome Official Build 153.0.7444.135 (Headless, 1920x1080)
- **서버 환경**: Uvicorn 0.52.4 on `http://127.0.0.1:8080`, Vite 5.x on `http://127.0.0.1:3005`
- **검증 게이트**:
  - `pytest tests/test_browser_smoke_boundary.py`: **3 passed** in 4.22s
  - `python tools/check_docs.py`: **PASS** (822 versioned documents, exit 0)

---

## 4. Git 영구 정본 증거

- **정본 증거 JSON**: [`docs/vault/30_Development/Evidence/desktop_ui_invariants.json`](file:///D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/docs/vault/30_Development/Evidence/desktop_ui_invariants.json)
  - `timestamp`: "2026-09-22T23:48:22+09:00"
  - `gitCommitSha`: "84700612ac780ca71dff8d50ec4ef26b9b9bc113"
  - `observedFrontendPort`: 3005
  - `summary`: `{"totalChecks": 9, "passedChecks": 8, "partialChecks": 1, "failedChecks": 0}`
  - 동적 관측치(실제 DOM 추출 텍스트/스타일/수치, 바운딩 박스, z-index 배열, 상대 파일명)만 수록.
