# 2026-10-02 17:00:00 KST — Card 230: 데스크톱 셸 (DesktopShell) 색상 리터럴 전수 토큰화(49건→0), 상태 색 정합성 및 접근성 승격 [r3]

## 1. 개요 및 변경 목적
- **작업 ID**: Card 230 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory)
- **대상 화면**: `apps/web/src/features/desktop/DesktopShell.tsx`
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: `agent/gemini/c230-desktop-shell-contrast`
- **기반 커밋 (Base)**: `f17a486f` (PR #325 head merge 후 실제 base)
- **PR 대상 (Target)**: PR #328 (`agent/gemini/c228-nl-run-contrast`)
- **KST 시각**: 2026-10-02 17:00:00 KST (r2 17:40:00 KST, r3 개정 2026-10-02 18:45:00 KST)

### 1.1 주요 작업 내역
1. **색상 리터럴 전수 해소 (49 occurrences -> 0건, 100% 토큰화)**:
   - `apps/web/src/features/desktop/DesktopShell.tsx`: 베이스에 존재하던 총 49건의 하드코딩 색상 리터럴(Hex 23건, RGBA 26건) 전수를 `apps/web/src/index.css` 정본 디자인 토큰(`var(--color-...)`)으로 100% 치환.
   - 셸 크롬 상단 바(`desktop-topbar`), 시작 메뉴(`desktop-start-menu`), 활성 창 제목 및 구분선, 패브릭 상태 표시기, RTT 지연시간 텍스트, 모드 전환기(`desktop-mode-switcher`), 테마 토글 버튼, 알림 드로어 트리거 및 안 읽은 알림 점(`desktop-unread-notif-dot`), 시스템 시계, 바탕화면 바로가기 아이콘 및 레이블, 하단 플로팅 독 툴바(`desktop-dock-toolbar`), 앱 타일(`desktop-dock-tile-*`) 및 실행 인디케이터 점(`desktop-dock-running-*`), 알림 센터 드로어(`desktop-notification-drawer`) 및 알림 배지(`desktop-notification-badge`) 전수 토큰화.
   - 하드코딩된 어두운 배경 그라데이션을 정본 토큰 그라데이션(`radial-gradient(circle at 50% 30%, var(--color-brand-subtle) 0%, var(--color-bg-surface) 50%, var(--color-bg-canvas) 100%)`)으로 정합하여 라이트/다크 양 테마 일관된 심미성과 고대비를 보장.
   - 바탕화면 바로가기 아이콘 hover 피드백(`transition: background-color 0.15s ease`, `onMouseEnter`/`onMouseLeave` via `var(--color-bg-subtle)`) 보존.
2. **Wire 계약 Enum 일치 및 알림 레벨 설정 객체 정립**:
   - `DesktopNotification['level']` wire 계약과 `NOTIFICATION_LEVEL_CONFIG`의 key set을 100% 일치: `info`, `success`, `warning`, `error` 정확히 4개 레벨로 한정.
   - `expect(Object.keys(NOTIFICATION_LEVEL_CONFIG).sort()).toEqual(['error', 'info', 'success', 'warning'])` 불변식 고정.
   - `getNotificationLevelConfig`: `Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)` 기반 own-key 검사를 적용하여 계약 외 임의 상태(`critical`, `debug`, `bogus`), 대소문자 변형(`ERROR`), prototype key(`toString`, `constructor`, `__proto__`) 및 null/''/undefined 입력 시 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 대문자 레벨(빈값은 `UNKNOWN`)로 fail-closed 격리 단언 (WCAG 1.4.1 준수).
3. **AST 가드 (Test 9j-2) borderTop 포함 조건식/AsExpression 가드 확장 및 엄밀 래칫**:
   - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Test 9j-2 정적 AST 검사기에 `DesktopShell.tsx` 정합 등록 및 `borderTop` 포함 객체 리터럴(`NOTIFICATION_LEVEL_CONFIG`) 검증 연동.
   - AST 커버리지 래칫:
     - `totalStyleAttrs`: 50
     - `checkedObjects`: 8
     - `checkedPairs`: 22
     - `unboundColorObjects`: 14
     - `coveredColorObjects`: 22
     - `checkedBorderObjects`: 14
     - `checkedBorderPairs`: 15
     - `violations`: [] (0건, 클린 패스)
4. **키보드 접근성 및 포커스 링 보존**:
   - 인라인 `outline: none`, `outline: 0`, `outlineWidth: 0` 억제를 일체 배제하고 `apps/web/src/index.css` 전역 `:focus-visible` 키보드 포커스 링 스타일 온전 보존.
   - mode switcher focus 이벤트 후 computed `outlineStyle`, `outlineWidth` 및 `outline !== 'none'` 검증, 나머지 버튼 및 아이콘은 정적 AST 가드(outline: none/0 배제)로 보호.
5. **Fail-Closed Multiset Baseline 래칫 강제**:
   - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/desktop/DesktopShell.tsx`의 허용 리터럴 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
   - `var(--color-border-subtle)` 사용 횟수: 442건/30개 파일 -> **451건/31개 파일**로 엄밀 래칫 갱신.
6. **40종 전수 변이 실측 사살 (tools/test_c230_mutations.py Y1~Y40 100% 사살)**:
   - fg==bg 충돌, border==bg 충돌, text token as bg, 불투명도 저하, 주석 decoy, 토큰 되돌림, 상태 색 붕괴, 라벨/아이콘 제거, outline: none/0 억제, prototype key 탈취, 계약 외 값 주입, 명명 색상 주입, UNKNOWN 접두어 제거, 원문 uppercase bypass, case-insensitive lookup 등 40종 변이를 컴파일 가능한 단일 유효 코드로 작성하여 전원 사살 실측.

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스의 실제 렌더링 합성값(어두운 캔버스 `#090d16` 위 상단 바 `rgba(15, 23, 42, 0.85)` 표면 합성 `#0e1627`, 시작 메뉴 `rgba(15, 23, 42, 0.95)` 합성 `#0f1629`, 독 `rgba(15, 23, 42, 0.75)` 합성 `#0e1425`)을 기준으로 하며, 텍스트는 다크 테마에서 충족되었으나 라이트 테마 전환 시 심각한 결손(Probes 91~95 실측)과 알파 테두리 명도비 결손(< 3.0:1)이 존재했습니다. After 값은 `python tools/reproduce_c230_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before 베이스 합성값 (Hex/RGBA on Canvas/Surface) | Before 명도비 (Dark 렌더 실측) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 상단 헤더 텍스트 | header text / surface | #f8fafc on #0e1627 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 상단 헤더 테두리 | header border / surface | rgba(255,255,255,0.1) on #0e1627 | 1.31:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 시작 메뉴 트리거 | start menu trigger / surface | #38bdf8 on #0e1627 | 8.43:1 (PASS) | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 활성 창 제목 | active window title / surface | #f8fafc on #0e1627 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 활성 창 구분선 | active window sep / surface | #94a3b8 on #0e1627 | 7.04:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 패브릭 온라인 상태 | fabric status online / surface | #34d399 on #0e1627 | 9.39:1 (PASS) | --color-status-online on --color-bg-surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| RTT 지연시간 텍스트 | rtt latency text / surface | #94a3b8 on #0e1627 | 7.04:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 모드 전환기 텍스트 | mode switcher text / brand-subtle | #60a5fa on rgba(59,130,246,0.2) | 5.46:1 (PASS) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 4.5:1 | PASS |
| 모드 전환기 테두리 | mode switcher border / brand-subtle | rgba(59,130,246,0.4) on subtle | 1.71:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 테마 토글 아이콘 | theme toggle icon / surface | #94a3b8 on #0e1627 | 7.04:1 (PASS) | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 알림 트리거 아이콘 | notif trigger icon / surface | #94a3b8 on #0e1627 | 7.04:1 (PASS) | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 알림 미확인 점 | notif unread dot / surface | #ef4444 on #0e1627 | 4.82:1 (PASS) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| 시스템 시계 | system clock / surface | #f8fafc on #0e1627 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 제목 | start menu title / surface | #f8fafc on #0f1629 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 사용자 ID | start menu user id / surface | #94a3b8 on #0f1629 | 7.04:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 시작 메뉴 테두리 | start menu border / surface | rgba(255,255,255,0.15) on #0f1629 | 1.56:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 시작 메뉴 바로가기 | start menu shortcut / surface | #f8fafc on #0f1629 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 종료 링크 | start menu exit link / surface | #60a5fa on #0f1629 | 7.08:1 (PASS) | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 알림 센터 제목 | notif center title / surface | #f8fafc on #0e1627 | 17.26:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 알림 닫기 버튼 | notif close btn / surface | #94a3b8 on #0e1627 | 7.04:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 알림 아이템 테두리 | notif item border / surface | (베이스 테두리 없음, bg만 rgba(255,255,255,0.05)) | N/A (경계 미식별) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 알림 메시지 텍스트 | notif message text / subtle | #94a3b8 on rgba(255,255,255,0.05) | 6.18:1 (PASS) | --color-text-secondary on --color-bg-subtle | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 알림 배지 INFO | notif badge INFO / subtle | (베이스 미구현, 미토큰화) | N/A (FAIL) | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 알림 배지 SUCCESS | notif badge SUCCESS / subtle | (베이스 미구현, 미토큰화) | N/A (FAIL) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 알림 배지 WARNING | notif badge WARNING / subtle | (베이스 미구현, 미토큰화) | N/A (FAIL) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 알림 배지 ERROR | notif badge ERROR / subtle | (베이스 미구현, 미토큰화) | N/A (FAIL) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 알림 배지 UNKNOWN | notif badge UNKNOWN / subtle | (베이스 미구현, 미토큰화) | N/A (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 바로가기 아이콘 테두리 | surface shortcut border / canvas | rgba(255,255,255,0.15) on #090d16 | 1.48:1 (FAIL) | --color-border-subtle on --color-bg-canvas | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| 바로가기 아이콘 레이블 | surface shortcut label / canvas | #ffffff on #090d16 | 19.43:1 (PASS) | --color-text-primary on --color-bg-canvas | 17.06:1 | 18.59:1 | >= 4.5:1 | PASS |
| 독 툴바 테두리 | dock toolbar border / canvas | rgba(255,255,255,0.15) on #090d16 | 1.55:1 (FAIL) | --color-border-subtle on --color-bg-canvas | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| 독 타일 활성 테두리 | dock tile active border / brand-subtle | #38bdf8 on rgba(59,130,246,0.3) over 독 (#1c3564) | 5.63:1 (PASS) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 독 타일 비활성 테두리 | dock tile inactive border / surface | rgba(255,255,255,0.1) on 독 (#0e1425) | 1.25:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 독 실행 활성 점 | dock running active dot / surface | #38bdf8 on 독 (#0e1425) | 8.43:1 (PASS) | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 3.0:1 | PASS |
| 독 실행 비활성 점 | dock running inactive dot / surface | rgba(255,255,255,0.5) on 독 (#0e1425) | 5.29:1 (PASS) | --color-border-strong on --color-bg-surface | 7.58:1 | 6.99:1 | >= 3.0:1 | PASS |

> [!NOTE]
> **라이트 테마 Revert-Fail Probes (Probes 91~95)**:
> 옛 다크 하드코딩 리터럴을 라이트 테마 표면 위에 적용할 경우의 심각한 명도 결손 실측:
> - Probe 91 (`#94a3b8` on light surface `#ffffff`): **2.56:1** (< 4.5:1 FAIL)
> - Probe 92 (`#38bdf8` on light surface `#ffffff`): **2.14:1** (< 4.5:1 FAIL)
> - Probe 93 (`#34d399` on light surface `#ffffff`): **1.92:1** (< 4.5:1 FAIL)
> - Probe 94 (`#60a5fa` on light surface `#ffffff`): **2.53:1** (< 4.5:1 FAIL)
> - Probe 95 (`#ffffff` on light canvas `#f8fafc`): **1.05:1** (< 4.5:1 FAIL)

### 2.2 tools/reproduce_c230_contrast.py 실행 결과
```text
==============================================================================================================
 CARD 230: DesktopShell CONTRAST AUDIT (WCAG 2.2 AA)
==============================================================================================================
Item Description                       | Light Mode         | Dark Mode          | Min CR   | Status
--------------------------------------------------------------------------------------------------------------
header text / surface                  | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
header border / surface                |  3.48:1 (OK)       |  3.73:1 (OK)       | >=3.0    | PASS
start menu trigger / surface           |  6.70:1 (OK)       |  9.84:1 (OK)       | >=4.5    | PASS
active window title / surface          | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
active window sep / surface            |  5.75:1 (OK)       |  6.99:1 (OK)       | >=4.5    | PASS
fabric status online / surface         |  5.02:1 (OK)       |  7.79:1 (OK)       | >=4.5    | PASS
rtt latency text / surface             |  5.75:1 (OK)       |  6.99:1 (OK)       | >=4.5    | PASS
mode switcher text / brand-subtle      |  5.49:1 (OK)       |  8.11:1 (OK)       | >=4.5    | PASS
mode switcher border / brand-subtle    |  5.49:1 (OK)       |  8.11:1 (OK)       | >=3.0    | PASS
theme toggle icon / surface            |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
notif trigger icon / surface           |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
notif unread dot / surface             |  6.47:1 (OK)       |  6.41:1 (OK)       | >=3.0    | PASS
system clock / surface                 | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
start menu title / surface             | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
start menu user id / surface           |  5.75:1 (OK)       |  6.99:1 (OK)       | >=4.5    | PASS
start menu border / surface            |  3.48:1 (OK)       |  3.73:1 (OK)       | >=3.0    | PASS
start menu shortcut / surface          | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
start menu exit link / surface         |  6.70:1 (OK)       |  9.84:1 (OK)       | >=4.5    | PASS
notif center title / surface           | 17.85:1 (OK)       | 16.98:1 (OK)       | >=4.5    | PASS
notif close btn / surface              |  5.75:1 (OK)       |  6.99:1 (OK)       | >=4.5    | PASS
notif item border / surface            |  3.48:1 (OK)       |  3.73:1 (OK)       | >=3.0    | PASS
notif message text / subtle            |  6.92:1 (OK)       | 11.86:1 (OK)       | >=4.5    | PASS
notif badge INFO / subtle              |  6.12:1 (OK)       |  8.14:1 (OK)       | >=4.5    | PASS
notif badge SUCCESS / subtle           |  4.58:1 (OK)       |  6.44:1 (OK)       | >=4.5    | PASS
notif badge WARNING / subtle           |  4.58:1 (OK)       |  6.83:1 (OK)       | >=4.5    | PASS
notif badge ERROR / subtle             |  5.91:1 (OK)       |  5.31:1 (OK)       | >=4.5    | PASS
notif badge UNKNOWN / subtle           |  6.47:1 (OK)       |  5.82:1 (OK)       | >=4.5    | PASS
surface shortcut border / canvas       |  3.33:1 (OK)       |  4.08:1 (OK)       | >=3.0    | PASS
surface shortcut label / canvas        | 17.06:1 (OK)       | 18.59:1 (OK)       | >=4.5    | PASS
dock toolbar border / canvas           |  3.33:1 (OK)       |  4.08:1 (OK)       | >=3.0    | PASS
dock tile active border / brand-subtle |  5.49:1 (OK)       |  8.11:1 (OK)       | >=3.0    | PASS
dock tile inactive border / surface    |  3.48:1 (OK)       |  3.73:1 (OK)       | >=3.0    | PASS
dock running active dot / surface      |  6.70:1 (OK)       |  9.84:1 (OK)       | >=3.0    | PASS
dock running inactive dot / surface    |  7.58:1 (OK)       |  6.99:1 (OK)       | >=3.0    | PASS
--------------------------------------------------------------------------------------------------------------
Total Audit Items: 34 | Passed: 34 | Failed: 0

[SUCCESS] All 34 items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.
```

---

## 3. 검증 결과 요약

### 3.1 로컬 검증 실행 기록
1. `npx vitest run tests/acc09-contrast-tokens.test.tsx`:
   - 결과: **31 passed** (100% 통과, 0 failed, Test 9n 및 Test 9j-2 AST 커버리지 래칫 통과)
2. `npx vitest run tests/desktop-shell-a11y.test.tsx`:
   - 결과: **14 passed** (100% 통과)
3. `npx vitest run tests/desktop-layout.test.tsx`:
   - 결과: **16 passed** (100% 통과)
4. `npx vitest run tests/browser-matrix-acceptance.test.tsx`:
   - 결과: **12 passed** (100% 통과)
5. `npx vitest run tests/s05-s06-defect-fixes.test.tsx`:
   - 결과: **16 passed** (100% 통과)
6. `npx vitest run tests/s11-defect-fixes.test.tsx`:
   - 결과: **16 passed** (100% 통과)
7. `npx tsc -b`:
   - 결과: exit code 0 (타입 에러 0건)
8. `npm run build`:
   - 결과: exit code 0 (프로덕션 번들 빌드 성공)
9. `pytest tests/test_route_coverage.py`:
   - 결과: **41 passed** (화면-백엔드 라우트 및 불변식 100% 통과)
10. `python -X utf8 tools/check_frontend_integrity.py`:
    - 결과: 0 violations (프런트엔드 9대 무결성 통과)
11. `python -X utf8 tools/check_contract_bindings.py`:
    - 결과: PASS (계약 바인딩 게이트 통과)
12. `python tools/check_docs.py`:
    - 결과: PASS (문서 정본 게이트 통과)
13. `python tools/sync_obsidian.py --check`:
    - 결과: 0 conflicts, 0 differences (동기화 정합)
14. `git diff --check`:
    - 결과: 클린 (trailing whitespace / merge marker 0건)

---

## 4. 변이 사살 표 (tools/test_c230_mutations.py 40종 전수 사살)

| 변이 ID | 변이 내용 | 사살 검증 게이트 |
| :--- | :--- | :--- |
| Y1 | DesktopShell: error notification config bg -> status-offline (fg==bg collision) | KILLED (Test 9j-2 (1:1 collision) & Test 9n) |
| Y2 | DesktopShell: success notification config bg -> status-online (fg==bg collision) | KILLED (Test 9j-2 (1:1 collision) & Test 9n) |
| Y3 | DesktopShell: info notification config bg -> brand-hover (fg==bg collision) | KILLED (Test 9j-2 (1:1 collision) & Test 9n) |
| Y4 | DesktopShell: warning notification config bg -> status-degraded (fg==bg collision) | KILLED (Test 9j-2 (1:1 collision) & Test 9n) |
| Y5 | DesktopShell: notification badge color -> notifCfg.bg (fg==bg collision in badge DOM) | KILLED (Test 9n (DOM badge fg/bg match)) |
| Y6 | DesktopShell: unknown fallback color -> bg-subtle (fg==bg collision on fallback) | KILLED (Test 9n (unknown level contrast check)) |
| Y7 | DesktopShell: error notification border -> bg-subtle (border==bg collision) | KILLED (Test 9j-2 (border collision) & Test 9n) |
| Y8 | DesktopShell: success notification border -> bg-subtle (border==bg collision) | KILLED (Test 9j-2 (border collision) & Test 9n) |
| Y9 | DesktopShell: notification badge border -> notifCfg.bg (border==bg collision in badge DOM) | KILLED (Test 9n (DOM badge border match)) |
| Y10 | DesktopShell: dock tile inactive border -> bg-subtle (border==bg collision in dock tile) | KILLED (Test 9j-2 (border collision in conditional style)) |
| Y11 | DesktopShell: notification item background -> text-secondary (text token as bg) | KILLED (Test 9j-2 (illegitimate background token derived from text token)) |
| Y12 | DesktopShell: header background -> text-primary (text token as bg) | KILLED (Test 9j-2 (illegitimate background token derived from text token)) |
| Y13 | DesktopShell: notification badge opacity degraded to 0.4 | KILLED (Test 9n (badge opacity assertion)) |
| Y14 | DesktopShell: mode switcher button opacity degraded to 0.45 | KILLED (Test 9n (mode switcher opacity assertion)) |
| Y15 | DesktopShell: success color with comment decoy literal | KILLED (Test 9n (strict token equality) & Test 9j-2) |
| Y16 | DesktopShell: unknown fallback border with comment decoy literal | KILLED (Test 9n (strict token equality)) |
| Y17 | DesktopShell: mode switcher button color reverted to legacy literal #60a5fa | KILLED (Test 10 (multiset baseline violation) & Test 9j-2) |
| Y18 | DesktopShell: notification unread dot backgroundColor reverted to legacy literal #ef4444 | KILLED (Test 10 (multiset baseline violation) & Test 9j-2) |
| Y19 | DesktopShell: start menu trigger color reverted to legacy literal #38bdf8 | KILLED (Test 10 (multiset baseline violation) & Test 9j-2) |
| Y20 | DesktopShell: warning notification color collapsed to status-online | KILLED (Test 9n (warning badge color assertion)) |
| Y21 | DesktopShell: error notification color collapsed to status-online | KILLED (Test 9n (error badge color assertion)) |
| Y22 | DesktopShell: info notification color collapsed to status-offline | KILLED (Test 9n (info badge color assertion)) |
| Y23 | DesktopShell: notification badge SUCCESS label changed to OK | KILLED (Test 9n (SUCCESS label exact equality)) |
| Y24 | DesktopShell: notification badge ERROR label changed to FAIL | KILLED (Test 9n (ERROR label exact equality)) |
| Y25 | DesktopShell: notification badge INFO label changed to 안내 | KILLED (Test 9n (INFO label exact equality)) |
| Y26 | DesktopShell: notification badge DOM altered with extra exclamation suffix | KILLED (Test 9n (badge label exact text)) |
| Y27 | DesktopShell: mode switcher button outline suppressed with outline: none | KILLED (Test 9j-2 (outline suppression guard) & Test 9n) |
| Y28 | DesktopShell: mode switcher button outline suppressed with outlineWidth: 0px | KILLED (Test 9j-2 (outlineWidth: 0 guard) & Test 9n) |
| Y29 | DesktopShell: start menu trigger outline suppressed with outline: none as const | KILLED (Test 9j-2 (AsExpression unwrap outline guard) & Test 9n) |
| Y30 | DesktopShell: dock button outline suppressed with outline: 0 | KILLED (Test 9j-2 (outline: 0 suppression guard)) |
| Y31 | DesktopShell: getNotificationLevelConfig null/empty returns info (fail-open fallback bypass) | KILLED (Test 9n (null fallback assertion)) |
| Y32 | DesktopShell: getNotificationLevelConfig unknown fallback returns info config | KILLED (Test 9n (unknown fallback assertion)) |
| Y33 | DesktopShell: getNotificationLevelConfig uses in operator instead of Object.hasOwn | KILLED (Test 9n (prototype key toString/constructor hijack defense)) |
| Y34 | DesktopShell: out-of-contract level (critical) added to NOTIFICATION_LEVEL_CONFIG | KILLED (Test 9n (key set equality assertion)) |
| Y35 | DesktopShell: contract level (error) bypassed in getNotificationLevelConfig (treated as unknown) | KILLED (Test 9n (ERROR badge exact token and label)) |
| Y36 | DesktopShell: success config border injected with named color green | KILLED (Test 9j-2 (named color guard)) |
| Y37 | DesktopShell: header text color injected with named color white | KILLED (Test 9j-2 (named color guard)) |
| Y38 | DesktopShell: getNotificationLevelConfig fallback label drops UNKNOWN prefix (raw level) | KILLED (Test 9n (UNKNOWN prefix guard on out-of-contract levels)) |
| Y39 | DesktopShell: getNotificationLevelConfig fallback label converts raw level to uppercase | KILLED (Test 9n (casing preservation and UNKNOWN wrapper guard)) |
| Y40 | DesktopShell: getNotificationLevelConfig normalizes case with toLowerCase() (case-insensitive bypass) | KILLED (Test 9n (case-insensitive lookup defense for non-canonical keys)) |

---

## 5. 다음 행동 및 인계
- **현재 상태**: Card 230 [r2] 구현 완료, 로컬 전체 게이트 100% 통과, 40종 변이 전원 사살 실측 완료, PR #328 반영 준비 완료.
- **다음 행동**: `agent/gemini/c230-desktop-shell-contrast` 브랜치 커밋 및 푸시, PR #328에 r2 리뷰 요청 코멘트 등록 (Zero bot tags `@...`).
- **다음 담당자**: Claude UI (기본 리뷰어) 및 Codex (보조 리뷰어).
