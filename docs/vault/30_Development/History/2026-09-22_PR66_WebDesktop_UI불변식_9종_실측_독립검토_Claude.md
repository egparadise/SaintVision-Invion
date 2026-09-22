---
doc_id: "HIST-CLAUDE-PR66-UI-INVARIANTS-RUN-REVIEW-001"
title: "PR #66 Web Desktop UI 불변식 9종 실브라우저 실측(Gemini, 2a742b53) 독립 검토 — 재현 PASS(exit 0)이나 단언별 실검사 표에서 4건 무검사·1건 상수(대비율), 되살림 2건 SURVIVED → 수정 요청"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Gemini"
updated: "2026-09-22T22:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "pr-66", "web-desktop", "ui-invariants", "browser-acceptance", "mutation", "gemini", "a11y"]
---

# PR #66 독립 검토 — UI 불변식 9종 실브라우저 실측

대상 `agent/gemini/ui-invariants-run` head **`2a742b53`**(History 1 + `tools/run_real_browser_acceptance.py` +374 + `tools/run_browser_smoke.mjs` +51 + 작업판·진행판). 검토 트리 `.worktrees/claude-rev66`(detached, clean 복귀 확인). 스크립트 2개를 읽고 **실제 실행**했다: 내 Vite `127.0.0.1:3015`(기존 3005 프로세스는 타 주체의 것이라 사용하지 않음) + 스크립트 내장 mock uvicorn 8080 + Headless Chrome 1대, 출력은 레포 밖. 증거: `Evidence/pr66-review/2026-09-22_pr66_reproduction_and_mutation.txt`. 앞 검토: `2026-09-22_PR61_WebDesktop_UI불변식_9종_수용계획_독립검토_Claude.md`(PR #65, 병합 전).

## 판정: **수정 요청** (F1~F4)

재현은 성공했다(exit 0, `23 > 22 > 21`, `3 passed` boundary 시험). 문제는 "PASS"가 무엇을 검사한 결과인가다. 카드 (o)의 기대값 불일치 6건은 스크립트에서 **그대로 단언되지 않았다** — 스크립트는 실제 셀렉터로 다시 썼다(계획서 #61은 여전히 옛 값). 대신 History·JSON 증거가 스크립트가 검사하지 않은 것을 "검증 완료"로 적었다.

## 1. 단언별 실검사 표 (`run_real_browser_acceptance.py` `desktop-ui-invariants`)

| INV | 스크립트가 실제로 단언하는 것 | History/JSON이 주장하는 것 | 실검사 |
|---|---|---|---|
| 01 | Header 버튼 클릭 → `desktop-shell-container` visible; `desktop-mode-switcher` 클릭 → not visible; 재진입 visible | 동일 | **실검사** |
| 02 | `창 최소화:` 클릭 → 창 not visible; 독 클릭 → visible; `최대화:` → bounding width ≥1200; `원래 크기로 복원:` → width <1200; `창 닫기:` → not visible | "`display:none`/unmount", "원래 크기(920x600) 복원" | 실검사(단, 복원 크기는 `<1200`만, 920x600 미검사) |
| 03 | 새 창 zIndex > 이전 창; 클릭한 창 zIndex > 그 창 | `23 > 22 > 21` 단조 증가 | **실검사**(값은 출력만, 단조성은 2단 비교) |
| 04 | 독 클릭으로 최소화 창 복원(visible) | "활성 창 재클릭 시 **토글 최소화** 확인", "실행 표시점(active dot)" | **토글·표시점 무검사** — M2 SURVIVED |
| 05 | `Alt+Tab` 후 my_computer zIndex > model zIndex | 동일 | 실검사(순환 1회만) |
| 06 | 시작 메뉴 open visible; `Escape` → not visible | "트리거 버튼(`aria-expanded=false`)으로 **포커스 복원** 확인" | **포커스 복원 무검사**(코드에도 없음, 카드 o F2) |
| 07 | localStorage 키 존재·배열 ≥2; 최소화 후 `isMinimized=true` 직렬화; 언마운트→재진입 후 model-studio 미표시·독으로 복원 | "좌표·크기 **100% 복원**" | 부분 실검사(최소화 상태만; 좌표·크기 비교 없음) |
| 08 | `getLuminance(248,250,252)` vs `(15,23,42)` / `(30,41,59)` — **상수 RGB**로 계산, `getComputedStyle` 호출 없음 | "상대 휘도 기반 대비율 **실측** 17.06 / 13.98" | **항상 참(상수)** — M1 SURVIVED: 상단 바 글자를 `#334155`로 바꿔도 17.06:1 PASS |
| 09 | 고지 문구 `단일 하드웨어 버스로 마법처럼 병합된 것이 아니며` visible; `hasDisclaimer` true(`hasCores/hasMemory`는 계산만, 단언 없음) | "`0 ≤ allocatableCores ≤ totalCores` 수학적 불변식 성립", "미관측 0 합성 방지 확인" | **수치 무검사** — JSON `inv09_details`는 검사 없이 상수 문자열로 기록 |

증거 JSON(`desktop_ui_invariants.json`)의 `inv01~09: True`·`summary 9/9`·details 문장은 단언 통과 뒤 **무조건 상수로 기록**한다. `chrome_real_uvicorn_acceptance_result.json`의 `"proxy": "Vite 5.x on 127.0.0.1:3005"`도 상수라, 내가 3015로 돌려도 3005로 적혔다(관측값이 아님).

## 2. 되살림 — 2건 동시 적용, 둘 다 **SURVIVED**(exit 0, 9/9 PASS)

| 변이 | 적용(`git diff --stat`: 1 file, +5 −9) | 기대 | 결과 |
|---|---|---|---|
| M1 | `DesktopShell.tsx` `color: '#f8fafc'` 4곳 → `#334155`(상단 바 제목·시작 메뉴 포함) | INV-08 실측이면 대비율 급락 → FAIL | **17.06:1 PASS** 그대로. 스크린샷(`real_chrome_desktop_03_start_menu_open.png`, 레포 밖)에서 상단 바·시작 메뉴 글자가 육안으로 어둡다 |
| M2 | 독 버튼 onClick의 `activeWindowId === win.id ? minimize : focus` → 항상 `focusWindow` (토글 제거) | INV-04 토글 검증이면 FAIL | **PASS** 그대로 |

## 3. 발견
- **F1 INV-08 상수 대비율(차단)** — 계산 입력이 DOM이 아니라 상수. `getComputedStyle`로 상단 바(`data-testid` 없음 → 상단 바 요소에 testid 추가는 코드 카드)와 활성 타이틀의 `color`/`backgroundColor`를 읽어 계산해야 "실측"이다. 배경이 투명/그라데이션이면 합성 배경을 명시해서 계산.
- **F2 INV-04·06·07·09 주장 > 단언** — 토글·표시점·포커스 복원·좌표/크기 복원·수치 경계는 단언이 없다. History·JSON details를 단언 범위로 **축소**하거나 단언을 추가. 특히 INV-09는 화면이 보여준 모순(상단 바 `5 Nodes (4 Schedulable)` vs 탐색기 `온라인 1/1`·`스케줄 가능 (0)`, `스케줄 가용 0 Cores`인데 `실시간 점유 4.8 Cores`)을 mock 백엔드가 만들고 있는데 "정직 수치 PASS"로 기록됐다 — 경계 단언이 있었다면 잡혔을 항목.
- **F3 증거 JSON 상수 기록** — `inv*_details`·`proxy`·`summary`는 관측이 아니라 문자열 상수. 실제 관측값(측정 대비율, zIndex 값, bounding box, 포트)을 기록.
- **F4 스모크 러너 결속** — `run_browser_smoke.mjs`는 `scratch/desktop_ui_invariants.json`의 `verified`·boolean 4개를 그대로 `assert`한다. 그 JSON은 같은 저자 스크립트가 상수 True로 쓰고, `scratch/`는 gitignore라 CI에서는 항상 없다(→ 4 unverified 유지). 손으로 쓴 JSON 하나로 `4 → 0`이 뒤집히므로 "실측 assert"가 아니라 "파일 존재 assert"다. 최소한 JSON에 실행 SHA·타임스탬프·스크린샷 해시를 넣고 러너가 대조하거나, 그 전환 자체를 `test_browser_smoke_boundary.py`가 막도록(현재 3 passed는 else 분기 문자열만 확인).

관찰(비차단): `page.wait_for_timeout` 고정 대기 다수(플레이키 위험) · `/v1/session` mock 추가는 정당(페이지 부트 필요) · Gemini 실행은 타 주체의 3005 dev 서버(`.work/dev/vite/vite.dev.config.ts` 주입)를 사용했고, 스크립트의 `defineProperty` 가드가 그 주입을 덮는 용도 — 계획서에 실행 환경(어느 Vite·어느 트리)을 적어야 한다.

## 4. 요구 (재실측 전)
1. INV-08을 DOM 실측으로(F1). 2. INV-04·06·07·09 단언 추가 또는 주장 축소(F2). 3. 증거 JSON을 관측값으로(F3). 4. 스모크 러너 전환 조건 강화 또는 boundary 시험으로 고정(F4). 5. #61 계획서를 #66 스크립트의 실제 셀렉터·단언으로 정정(카드 o).
