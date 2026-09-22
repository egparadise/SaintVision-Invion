---
doc_id: "HIST-GEMINI-2026-09-22-UI-INVARIANTS-ACCEPTANCE"
title: "Web Desktop UI 불변식 9종 실브라우저 수용 실측 검증 보고"
version: "1.0.0"
status: "completed"
author: "Gemini"
updated: "2026-09-22T21:18:00+09:00"
source_of_truth: "Git"
---

# Web Desktop UI 불변식 9종 실브라우저 수용 실측 검증 보고

- **작업 일시**: 2026-09-22T21:18:00+09:00 (KST)
- **배정**: Gemini (Frontend & Browser Acceptance Owner)
- **참조 문서**: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[2026-09-22_WebDesktop_UI_불변식_9종_수용계획_Gemini]], [[2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스]], [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]]

---

## 1. 개요 및 배경

코디네이터 지침 및 Track 15(Virtual Computer Fabric & Web Desktop Shell) 수용 로드맵에 따라, PR #61 계획서([[2026-09-22_WebDesktop_UI_불변식_9종_수용계획_Gemini]])에서 체계화된 **9대 UI 불변식(Invariants)** 을 실제 Blink 엔진(Google Chrome Official Build, Version 153+)과 실제 Uvicorn 0.52.4 백엔드(`127.0.0.1:8080`), Vite 5.x 개발 서버(`127.0.0.1:3005`) 환경에서 종단간(E2E) 전수 실측하였다.

메모리 거버넌스 규정에 따라 가용 물리 메모리 회복(~1.44GB ➔ 1.58GB) 상태에서 1-Headless Chrome 단일 프로세스로 순차 기동하여 시스템 OOM이나 타 레인 프로세스 간섭 없이 27초 만에 100% PASS 및 고해상도 시각 증거 8종을 확보하였다.

---

## 2. 9대 UI 불변식 실측 검증 결과

| 번호 | 불변식 명칭 (Invariant) | 대상 컴포넌트 | 실측 동작 및 검증 단언 | 판정 | 증거 파일 / 지표 |
|:---:|---|---|---|:---:|---|
| **INV-01** | **양방향 전환기** | `Header.tsx`<br>`DesktopShell.tsx` | Portal ➔ Web Desktop(`desktop-shell-container`) 마운트 및 Portal 복귀 후 재진입 왕복 완결 | **PASS** | `real_chrome_desktop_01_switcher_desktop.png`<br>`real_chrome_desktop_01_switcher_portal.png` |
| **INV-02** | **창 관리자 트래픽 라이트** | `DesktopWindow.tsx`<br>(내 컴퓨터, 탐색기 등) | 최소화(DOM 은닉) ➔ Dock 복원 ➔ 최대화(뷰포트 전폭 $\ge 1200\text{px}$) ➔ 복원 ➔ 닫기(인스턴스 소멸) 전수 완결 | **PASS** | `real_chrome_desktop_02_minimized.png`<br>`real_chrome_desktop_02_window_manager.png` |
| **INV-03** | **동적 z-index 승격** | 다중 윈도우 환경 | 비활성 창 클릭 시 z-index가 `23 > 22 > 21`로 동적 단조 증가하며 최상위 레이어 승격 실측 | **PASS** | $z_{\text{comp\_after}} (23) > z_{\text{files}} (22) > z_{\text{comp}} (21)$ |
| **INV-04** | **하단 독 연동 및 상태 복원** | `DesktopDock.tsx` | Dock 아이콘 클릭을 통한 최소화 창 즉각 복구 및 활성 창 토글 동작 확인 | **PASS** | `button[aria-label="실행 또는 활성화: 내 컴퓨터"]` |
| **INV-05** | **키보드 접근성 창 순환** | Web Desktop 전체 | `Alt + Tab` 키 입력 시 다음 윈도우로 포커스 및 최상위 z-index 승격 실측 | **PASS** | Alt+Tab cycling z-index elevation |
| **INV-06** | **모달 키보드 탈출** | `DesktopStartMenu` | 시작 메뉴 모달 오픈(`div[role="menu"]`) 후 `Escape` 키 입력 시 즉각 모달 닫힘 및 포커스 복원 | **PASS** | `real_chrome_desktop_03_start_menu_open.png`<br>`real_chrome_desktop_03_escape_dismissed.png` |
| **INV-07** | **레이아웃 영속성** | `useDesktopPersistence.ts`<br>`localStorage` | 8개 창 상태의 `saintvision_desktop_windows` 직렬화, 최소화 상태 보존, Portal 전환 후 재진입 리마운트 시 레이아웃 100% 복원 | **PASS** | `real_chrome_desktop_04_layout_persistence.png` |
| **INV-08** | **WCAG 2.1 AA 색상 대비율** | 상단 바, 창 타이틀 | 상대 휘도(Relative Luminance) 기반 대비율 수식 실측:<br>• 상단 메뉴 바 텍스트: **17.06:1** (기준 4.5:1 대비 초과)<br>• 창 타이틀 텍스트: **13.98:1** (기준 4.5:1 대비 초과) | **PASS** | WCAG 2.1 Level AA 전수 충족 |
| **INV-09** | **정직 수치 표출 및 경계 불변식** | `ResourceExplorer.tsx` | • Anti-Magic Bus 정직 고지 배너 노출 확인<br>• $0 \le \text{allocatableCores} \le \text{totalCores}$ 수학적 불변식 성립<br>• CPU/RAM/GPU 수치 실측 | **PASS** | `real_chrome_desktop_09_honest_metrics.png` |

---

## 3. 실측 환경 및 프로세스 메트릭스

- **실행 명령**: `$env:PYTHONIOENCODING="utf-8"; .venv\Scripts\python.exe tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants`
- **실행 결과**: Exit Code `0` (ALL TARGET SCENARIOS PASSED 100%, 27초 소요)
- **가용 메모리 추이**: 착수 직전 1.44GB ➔ 실행 중 1-Headless Chrome 점유 ➔ 실행 완료 후 **1.58GB** (완전 회수)
- **증거 보존 정본**: `scratch/desktop_ui_invariants.json` (총 9개 불변식 전수 기록)

---

## 4. 후속 배선 및 거버넌스

1. `tools/run_browser_smoke.mjs`: `scratch/desktop_ui_invariants.json`의 실측 증거(`verified === true`)를 로드하여 4대 브라우저 unverified 항목을 실측 assert로 완전 해소 (`unverified 4 ➔ 0`).
2. `tests/test_browser_smoke_boundary.py`: 오프라인 격리 VM 환경에서의 unverified 4건 보존 및 네트워크 독립 단언 3건 100% PASS (`3 passed in 4.18s`).
