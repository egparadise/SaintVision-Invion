---
doc_id: "HIST-CLAUDE-PR61-UI-INVARIANTS-PLAN-REVIEW-001"
title: "PR #61 Web Desktop UI 불변식 9종 실브라우저 수용 계획(Gemini, df411756) 독립 검토 — 셀렉터 14건 부재·기대값 6건 코드 불일치·정본(4종 실측 완료) 중복·실측 명령 미명시 → 수정 요청"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Gemini"
updated: "2026-09-22T22:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-61", "web-desktop", "ui-invariants", "browser-acceptance", "gemini", "a11y"]
---

# PR #61 독립 검토 — Web Desktop UI 불변식 9종 수용 계획

대상 `agent/gemini/ui-invariants-plan` head **`df411756`**(docs 3파일: 계획서 신설, Gemini 작업 현황, 진행판 1줄). 검토 트리 `.worktrees/claude-rev61`(detached, clean). 방법: 계획서의 셀렉터·기대값·파일명·명령을 `apps/web/src`·`tools/`·기존 시험과 **grep 대조**(브라우저 기동 없음, 코드 읽기 전용). 코디네이터 카드 (o).

## 판정: **수정 요청** (F1~F4)

## 1. 대조 표 — 셀렉터·파일명 (계획 → 실제 코드)

| INV | 계획서 기술 | 실제(`apps/web/src`) | 상태 |
|---|---|---|---|
| 01 | `button[data-testid="switch-to-desktop-btn"]` | `shared/ui/Header.tsx` 버튼은 testid 없음, `aria-label="Web Desktop으로 전환"` | **부재** |
| 01 | `[Portal 복귀]` 버튼 | `desktop-mode-switcher` 텍스트 "📑 클래식 포털 뷰로 전환" | 라벨 불일치 |
| 01 | `desktop-mode-switcher`, `desktop-shell-container`, `position: fixed; 100vw/100vh` | `DesktopShell.tsx` 290~300 | 일치 |
| 02 | `aria-label^="창 최대화:"` | `최대화: ${title}` / `원래 크기로 복원: ${title}`(접두 "창" 없음) | **부재** |
| 02 | `창 최소화:` `창 닫기:` | `DesktopWindow.tsx` 100·119 | 일치 |
| 02 | 최대화 = `calc(100vh - 72px)` | `top 36px / bottom 68px / height calc(100% - 104px)` | **기대값 불일치** |
| 02 | 최소화 = `display: none` | `if (!isOpen \|\| isMinimized) return null` → **언마운트** | 기대값 불일치 |
| 03 | `div[data-window-id]` | 없음(`role="dialog"` + `aria-labelledby="window-title-{id}"`) | **부재** |
| 04 | `nav[data-testid="desktop-dock"]`, `DesktopDock.tsx` | `role="toolbar" data-testid="desktop-taskbar"`(DesktopShell 내부, 별도 파일 없음) | **부재** |
| 04 | `button[data-dock-app-id]`, `span.dock-running-dot` | 없음(`aria-label="실행 또는 활성화: {title}"`) | **부재** |
| 05 | `div[data-testid="alt-tab-hud"]`, `Alt+Backquote`, Alt 릴리즈 시 확정 | 없음 — `keydown`에서 Alt+Tab 즉시 `focusWindow`(HUD·릴리즈 단계 없음) | **부재·동작 불일치** |
| 06 | `DesktopStartMenu` 컴포넌트, Escape 후 **트리거로 포커스 복귀** | 시작 메뉴는 DesktopShell 내부 `role="menu"`; Escape는 `setIsStartMenuOpen(false)`만(포커스 복귀 코드 없음); RunDetail 대화상자에는 Escape 핸들러 없음 | 기대값이 구현을 초과 |
| 07 | `useDesktopPersistence.ts`, "100ms 내 저장" | 파일 없음 — `DesktopShell` `useEffect`+`desktopLayout.ts restoreDesktopLayout`; 시간 규격 없음 | **부재** |
| 08 | `desktop-top-bar`, `window-title-bar` | 없음(`#window-title-{id}`만) | **부재** |
| 09 | `pool-capacity-metric`, `node-resource-usage-section` | `pool-capacity-loading/error/retry`, `logical-*-card`; `node-resource-usage-unselected-notice/loading/error`(NodeDetail.tsx) | **부재** |
| 09 | `0 ≤ reserved ≤ offered ≤ capacity` | `ResourceExplorer.tsx`에 reserved/offered 0건; NodeDetail은 `reserved !== null ? … : '미측정'` | 지표 소재 불일치 |
| 09 | 배너 문구 `프로젝트를 선택하세요` | `프로젝트를 선택하면 Studio를 열 수 있습니다.`(App) / `node-resource-usage-unselected-notice` | 문구 불일치 |

부재 14건(굵게)은 그대로 실측하면 전부 timeout이다. 셀렉터를 실제 값으로 바꾸거나, testid 추가를 **코드 변경 카드**로 분리해야 한다(계획서는 docs-only).

## 2. 정본 정합 (F3)
- 정본은 `tools/run_browser_smoke.mjs`의 `recordUnverified` **4건**(전환기·창 관리자·키보드 A11y·영속성)이며, [[2026-09-22_WebDesktop_4대UI불변식_및_A11y실측검증_Gemini]](approved, 19:40)가 이미 **4건 PASS·대비율 17.06/13.98·`unverified 4 → 0` 완료**를 보고했다. 본 계획서는 같은 4→0 전환과 같은 대비율 값을 **미래 계획**으로 다시 적어 정본과 모순된다(이미 끝난 일인지, 재실측인지 불명).
- 9종은 4종의 재분할(02→02·03·04, 03→05·06) + 신규 2(08 대비율, 09 정직 수치)다. 계획서는 이 대응 관계와 "정본 4종 대비 무엇이 새로 추가되는가"를 명시해야 한다. 로드맵 앵커는 VF-GM-01 "responsive/accessibility tests".
- INV-08 통과 기준을 "≥15:1 / ≥12:1"로 잡으면 WCAG AA(4.5:1)를 만족하는 정상적 색 조정도 실패한다. 기준은 4.5:1, 실측값은 증거로만.

## 3. 실측 명령·증거 경로 (F4)
- 계획서에 실행 명령이 없다. 정본 보고는 `tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants`를 인용하나 그 스크립트의 scenario는 `verified`·`s02-auth-failure`·`evidence-failed`뿐(`desktop-ui-invariants` 분기 없음). 실제 사용할 러너·시험 파일을 명시해야 한다.
- 기존 시험을 인용하지 않는다: `apps/web/tests/virtual-desktop.test.ts` `[VF-GM-01]`·`[VF-GM-01-A11Y]`·`[VF-GM-01-STORAGE]`, `tests/desktop-layout.test.tsx`, `tests/browser/desktop.tsx`, `tests/test_browser_smoke_boundary.py`.
- `scratch/`는 `.gitignore`(20행) 대상이라 `scratch/desktop_ui_invariants.json`·PNG는 Git 증거가 아니다. 증거는 `docs/vault/30_Development/Evidence/` 아래로.

## 4. 요구 사항 (수정 후 재검토)
1. §2 매트릭스의 셀렉터·라벨·파일명을 실제 코드 값으로 교체(§1 표), 코드가 없는 훅(HUD·running-dot·data-window-id·testid 3종)은 "코드 변경 필요" 열로 분리.
2. 기대값 정정: 최대화 기하, 최소화=언마운트, Escape 포커스 복귀·RunDetail Escape는 현 구현 밖임을 명시(또는 코드 카드).
3. 정본 4종 실측 보고와의 관계(재실측/확장)와 4↔9 대응표, INV-08 기준 4.5:1.
4. 실행 명령·시험 파일·Git 내 증거 경로.

관찰(비차단): `DesktopWindow` `aria-modal="false"`인데 INV-06은 `aria-modal="true"` 정합을 요구 — 창은 모달이 아니므로 현 코드가 맞고 계획서 문구를 좁혀야 한다. PR 코멘트: https://github.com/egparadise/SaintVision-Invion/pull/61
