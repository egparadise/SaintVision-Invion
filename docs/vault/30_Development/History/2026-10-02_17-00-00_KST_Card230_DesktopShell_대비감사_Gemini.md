# 2026-10-02 17:00:00 KST — Card 230: 데스크톱 셸 (DesktopShell) 색상 리터럴 전수 토큰화(49건→0), 상태 색 정합성 및 접근성 승격

## 1. 개요 및 변경 목적
- **작업 ID**: Card 230 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory)
- **대상 화면**: pps/web/src/features/desktop/DesktopShell.tsx
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: gent/gemini/c230-desktop-shell-contrast
- **기반 커밋 (Base)**: 6426f970 (PR #325 head)
- **PR 대상 베이스 (Target Base)**: gent/gemini/c228-nl-run-contrast (PR #325)
- **KST 시각**: 2026-10-02 17:00:00 KST

### 1.1 주요 작업 내역
1. **색상 리터럴 전수 해소 (49 occurrences -> 0건, 100% 토큰화)**:
   - pps/web/src/features/desktop/DesktopShell.tsx: 베이스에 존재하던 총 49건의 하드코딩 색상 리터럴(Hex 23건, RGBA 26건) 전수를 pps/web/src/index.css 정본 디자인 토큰(ar(--color-...))으로 100% 치환.
   - 셸 크롬 상단 바(desktop-topbar), 시작 메뉴(desktop-start-menu), 활성 창 제목 및 구분선, 패브릭 상태 표시기, RTT 지연시간 텍스트, 모드 전환기(desktop-mode-switcher), 테마 토글 버튼, 알림 드로어 트리거 및 안 읽은 알림 점(unread-dot), 시스템 시계, 바탕화면 바로가기 아이콘 및 레이블, 하단 플로팅 독 툴바(desktop-dock-toolbar), 앱 타일(desktop-dock-tile-*) 및 실행 인디케이터 점(desktop-dock-running-*), 알림 센터 드로어(desktop-notification-drawer) 및 알림 배지(desktop-notification-badge) 전수 토큰화.
   - 하드코딩된 어두운 배경 그라데이션(
adial-gradient(...))을 정본 토큰 그라데이션(
adial-gradient(circle at 50% 30%, var(--color-brand-subtle) 0%, var(--color-bg-surface) 50%, var(--color-bg-canvas) 100%))으로 정합하여 라이트 테마에서도 일관된 심미성과 고대비를 보장.
2. **Wire 계약 Enum 일치 및 알림 레벨 설정 객체 정립**:
   - DesktopNotification['level'] wire 계약과 NOTIFICATION_LEVEL_CONFIG의 key set을 100% 일치: info, success, warning, error 정확히 4개 레벨로 한정.
   - expect(Object.keys(NOTIFICATION_LEVEL_CONFIG).sort()).toEqual(['error', 'info', 'success', 'warning']) 불변식 고정.
   - getNotificationLevelConfig: Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level) 기반 own-key 검사를 적용하여 계약 외 임의 상태(critical, debug, ogus), prototype key(	oString, constructor, __proto__) 및 null/''/undefined 입력 시 ar(--color-status-unknown) 및 UNKNOWN 대문자 레벨로 fail-closed 격리 단언.
3. **AST 가드 (Test 9j-2) 조건식/AsExpression 가드 확장 및 엄밀 래칫**:
   - pps/web/tests/acc09-contrast-tokens.test.tsx의 Test 9j-2 정적 AST 검사기에 DesktopShell.tsx 정합 등록 및 객체 리터럴(NOTIFICATION_LEVEL_CONFIG) 검증 연동.
   - AST 커버리지 래칫:
     - 	otalStyleAttrs: 50
     - checkedObjects: 8
     - checkedPairs: 22
     - unboundColorObjects: 14
     - coveredColorObjects: 22
     - checkedBorderObjects: 13
     - checkedBorderPairs: 14
     - iolations: [] (0건, 클린 패스)
4. **키보드 접근성 및 포커스 링 보존**:
   - 인라인 outline: none, outline: 0, outlineWidth: 0 억제를 일체 배제하고 pps/web/src/index.css 전역 :focus-visible 키보드 포커스 링 스타일 온전 보존.
   - DOM 단언에서 계산된 outlineStyle, outlineWidth 및 outline !== 'none' 검증.
5. **Fail-Closed Multiset Baseline 래칫 강제**:
   - COLOR_LITERAL_MULTISET_BASELINE에서 eatures/desktop/DesktopShell.tsx의 허용 리터럴 인벤토리를 {} (0건)으로 전면 래칫 고정.
   - ar(--color-border-subtle) 사용 횟수: 442건/30개 파일 -> **451건/31개 파일**로 엄밀 래칫 갱신.
6. **37종 전수 변이 실측 사살 (tools/test_c230_mutations.py Y1~Y37 100% 사살)**:
   - fg==bg 충돌, border==bg 충돌, text token as bg, 불투명도 저하, 주석 decoy, 토큰 되돌림, 상태 색 붕괴, 라벨/아이콘 제거, outline: none/0 억제, prototype key 탈취, 계약 외 값 주입, 명명 색상 주입 등 37종 변이를 컴파일 가능한 단일 유효 코드로 작성하여 전원 사살 실측.

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 수치는 python tools/reproduce_c230_contrast.py 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before (Hex/RGBA on Canvas/Surface) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 상단 헤더 텍스트 | header text / surface | #ffffff on #090d16 (하드코딩 어두운 테마) | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 상단 헤더 테두리 | header border / surface | 
gba(255,255,255,0.08) on #090d16 | 1.13:1 (FAIL) / 1.13:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 시작 메뉴 트리거 | start menu trigger / surface | #38bdf8 on #090d16 | 2.14:1 (FAIL) / 10.66:1 | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 활성 창 제목 | active window title / surface | #ffffff on #090d16 | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 활성 창 구분선 | active window sep / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 패브릭 온라인 상태 | fabric status online / surface | #34d399 on #090d16 | 1.92:1 (FAIL) / 11.08:1 | --color-status-online on --color-bg-surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| RTT 지연시간 텍스트 | rtt latency text / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 모드 전환기 텍스트 | mode switcher text / brand-subtle | #38bdf8 on rgba(56,189,248,0.12) | 2.14:1 (FAIL) / 9.16:1 | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 4.5:1 | PASS |
| 모드 전환기 테두리 | mode switcher border / brand-subtle | 
gba(56,189,248,0.3) on subtle | 1.34:1 (FAIL) / 1.34:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 테마 토글 아이콘 | theme toggle icon / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 알림 트리거 아이콘 | notif trigger icon / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 알림 미확인 점 | notif unread dot / surface | #f87171 on #090d16 | 3.19:1 / 5.92:1 | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| 시스템 시계 | system clock / surface | #ffffff on #090d16 | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 제목 | start menu title / surface | #ffffff on #090d16 | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 사용자 ID | start menu user id / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 시작 메뉴 테두리 | start menu border / surface | 
gba(255,255,255,0.12) on #090d16 | 1.20:1 (FAIL) / 1.20:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 시작 메뉴 바로가기 | start menu shortcut / surface | #ffffff on #090d16 | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 시작 메뉴 종료 링크 | start menu exit link / surface | #60a5fa on #090d16 | 2.53:1 (FAIL) / 8.58:1 | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 알림 센터 제목 | notif center title / surface | #ffffff on #090d16 | 1.00:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 알림 닫기 버튼 | notif close btn / surface | #94a3b8 on #090d16 | 2.53:1 (FAIL) / 7.02:1 | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 알림 항목 테두리 | notif item border / surface | 
gba(255,255,255,0.08) on #090d16 | 1.13:1 (FAIL) / 1.13:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 알림 메시지 본문 | notif message text / subtle | #94a3b8 on rgba(255,255,255,0.03) | 2.53:1 (FAIL) / 6.75:1 | --color-text-secondary on --color-bg-subtle | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 알림 INFO 배지 | notif badge INFO / subtle | #38bdf8 on subtle | 2.14:1 (FAIL) / 9.16:1 | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 알림 SUCCESS 배지 | notif badge SUCCESS / subtle | #34d399 on subtle | 1.92:1 (FAIL) / 11.08:1 | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 알림 WARNING 배지 | notif badge WARNING / subtle | #fbbf24 on subtle | 1.48:1 (FAIL) / 12.01:1 | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 알림 ERROR 배지 | notif badge ERROR / subtle | #f87171 on subtle | 3.19:1 (FAIL) / 5.92:1 | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 알림 UNKNOWN 배지 | notif badge UNKNOWN / subtle | #94a3b8 on subtle | 2.53:1 (FAIL) / 7.02:1 | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 바탕 바로가기 테두리 | surface shortcut border / canvas | 
gba(255,255,255,0.12) on canvas | 1.20:1 (FAIL) / 1.20:1 (FAIL) | --color-border-subtle on --color-bg-canvas | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| 바탕 바로가기 레이블 | surface shortcut label / canvas | #ffffff on canvas | 1.05:1 (FAIL) / 18.89:1 | --color-text-primary on --color-bg-canvas | 17.06:1 | 18.59:1 | >= 4.5:1 | PASS |
| 독 툴바 테두리 | dock toolbar border / canvas | 
gba(255,255,255,0.15) on canvas | 1.26:1 (FAIL) / 1.26:1 (FAIL) | --color-border-subtle on --color-bg-canvas | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| 독 활성 타일 테두리 | dock tile active border / brand-subtle | 
gba(56,189,248,0.5) on subtle | 1.87:1 (FAIL) / 1.87:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 독 비활성 타일 테두리 | dock tile inactive border / surface | 
gba(255,255,255,0.12) on surface | 1.20:1 (FAIL) / 1.20:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| 독 활성 실행 점 | dock running active dot / surface | #38bdf8 on surface | 2.14:1 (FAIL) / 10.66:1 | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 3.0:1 | PASS |
| 독 비활성 실행 점 | dock running inactive dot / surface | 
gba(255,255,255,0.2) on surface | 1.37:1 (FAIL) / 1.37:1 (FAIL) | --color-border-strong on --color-bg-surface | 7.58:1 | 6.99:1 | >= 3.0:1 | PASS |

---

### 2.2 독립 재현 스크립트 실행 콘솔 결과

`ash
$ python tools/reproduce_c230_contrast.py
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
`

---

## 3. 정적 AST 가드 검증 결과 (§3 AST 메트릭 래칫)

pps/web/tests/acc09-contrast-tokens.test.tsx의 Test 9j-2 정적 AST 검사기에 의해 단언되는 DesktopShell.tsx 메트릭:

| 메트릭 명칭 | 실측치 | 가드 판정 기준 | 결과 |
| :--- | :--- | :--- | :--- |
| 	otalStyleAttrs | 50 | 파일 내 전체 인라인 style 속성 개수 | PASS |
| checkedObjects | 8 | 전경-배경 쌍 동시 보유 style 객체 수 | PASS |
| checkedPairs | 22 | 전경-배경 유효 검사 쌍 개수 | PASS |
| unboundColorObjects | 14 | 단일 색상 속성 style 객체 수 | PASS |
| coveredColorObjects | 22 | 컨텍스트 추적으로 커버된 색상 객체 수 | PASS |
| checkedBorderObjects | 13 | 테두리 스타일 보유 객체 수 | PASS |
| checkedBorderPairs | 14 | 테두리-배경 유효 검사 쌍 개수 | PASS |
| iolations | [] (0건) | 1:1 충돌, 테두리 충돌, 명도비 미달 등 위반 목록 | PASS (0건) |

---

## 4. 37종 변이 실측 사살 기록 (§4 뮤테이션 테스트)

	ools/test_c230_mutations.py를 통해 총 37종(Y1~Y37)의 유효 컴파일 변이를 주입하여 테스트 스위트의 감지력을 실측 검증했습니다.

| 변이 ID | 변이 명칭 / 내용 | 사살 검증 계층 (Guard) | 결과 |
| :--- | :--- | :--- | :--- |
| Y1 | error notification config bg -> status-offline (fg==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y2 | success notification config bg -> status-online (fg==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y3 | info notification config bg -> brand-hover (fg==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y4 | warning notification config bg -> status-degraded (fg==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y5 | mode switcher text color -> brand-subtle (fg==bg 충돌) | Test 9j-2 (1:1 collision) | KILLED |
| Y6 | unknown fallback color -> bg-subtle (fg==bg 충돌) | Test 9n (unknown DOM) | KILLED |
| Y7 | error notification border -> bg-subtle (border==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y8 | success notification border -> bg-subtle (border==bg 충돌) | Test 9j-2 / Test 9n | KILLED |
| Y9 | notification badge border -> notifCfg.bg (border==bg 충돌) | Test 9n (badge DOM) | KILLED |
| Y10 | dock tile inactive border -> bg-subtle (border==bg 충돌) | Test 9j-2 (border collision) | KILLED |
| Y11 | notification item background -> text-secondary (text token as bg) | Test 9j-2 (text token as bg) | KILLED |
| Y12 | header background -> text-primary (text token as bg) | Test 9j-2 (text token as bg) | KILLED |
| Y13 | notification badge opacity degraded to 0.4 | Test 9n (opacity !== 1) | KILLED |
| Y14 | mode switcher button opacity degraded to 0.45 | Test 9n (opacity !== 1) | KILLED |
| Y15 | success color with comment decoy literal | Test 9n / Test 9j-2 | KILLED |
| Y16 | unknown fallback border with comment decoy literal | Test 9n | KILLED |
| Y17 | topbar border token revert to literal rgba(255,255,255,0.08) | Test 10 (Inventory Multiset) | KILLED |
| Y18 | start menu exit link token revert to literal #60a5fa | Test 10 (Inventory Multiset) | KILLED |
| Y19 | wallpaper gradient token revert to literal #090d16 | Test 10 (Inventory Multiset) | KILLED |
| Y20 | success notification color collapsed to status-offline | Test 9n (semantic distinctness) | KILLED |
| Y21 | warning notification color collapsed to status-online | Test 9n (semantic distinctness) | KILLED |
| Y22 | error notification color collapsed to brand-hover | Test 9n (semantic distinctness) | KILLED |
| Y23 | notification badge label text removed | Test 9n (badge textContent) | KILLED |
| Y24 | notification badge role status removed | Test 9n (badge role status) | KILLED |
| Y25 | topbar start button outline: 'none' suppression | Test 9j-2 / Test 9n | KILLED |
| Y26 | dock tile outline: 'none' suppression | Test 9j-2 / Test 9n | KILLED |
| Y27 | notification close button outline: 0 suppression | Test 9j-2 / Test 9n | KILLED |
| Y28 | start button outline: 'none' as const suppression | Test 9j-2 (AsExpression unwrap) | KILLED |
| Y29 | unknown fallback defaulted to info instead of UNKNOWN | Test 9n (fail-closed contract) | KILLED |
| Y30 | null/undefined fallback defaulted to info | Test 9n (nullish fallback) | KILLED |
| Y31 | Object.hasOwn bypassed via in operator (prototype key vulnerable) | Test 9n (toString / constructor) | KILLED |
| Y32 | config allows out-of-contract critical key | Test 9n (contract key set equality) | KILLED |
| Y33 | config allows out-of-contract debug key | Test 9n (contract key set equality) | KILLED |
| Y34 | out-of-contract level rendered as known config | Test 9n (out-of-contract isolation) | KILLED |
| Y35 | start menu exit link color -> named color red | Test 9j-2 (named color guard) | KILLED |
| Y36 | notification badge background -> named color lime | Test 9j-2 (named color guard) | KILLED |
| Y37 | dock active dot -> named color deepskyblue | Test 9j-2 (named color guard) | KILLED |

**최종 변이 사살율**: 37/37 (100.0% 사살 실측 완료, exit code 0)

---

## 5. 로컬 검증 실측치 요약

| 검증 항목 | 실행 명령 | 실측 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| Vitest ACC-09 스위트 | 
px vitest run tests/acc09-contrast-tokens.test.tsx | **31 passed (31)** (100%) | Test 9n, Test 9j-2, Test 10 신설/갱신 |
| Vitest 형제 스위트 (1) | 
px vitest run tests/desktop-shell-a11y.test.tsx | **10 passed (10)** (100%) | A11y 셸 회귀 0건 |
| Vitest 형제 스위트 (2) | 
px vitest run tests/browser-matrix-acceptance.test.tsx | **12 passed (12)** (100%) | 브라우저 매트릭스 인수 회귀 0건 |
| Vitest 형제 스위트 (3) | 
px vitest run tests/desktop-layout.test.tsx | **10 passed (10)** (100%) | 데스크톱 레이아웃 회귀 0건 |
| Vitest 형제 스위트 (4) | 
px vitest run tests/s05-s06-defect-fixes.test.tsx | **16 passed (16)** (100%) | S05/S06 결함 회귀 0건 |
| Vitest 형제 스위트 (5) | 
px vitest run tests/s11-defect-fixes.test.tsx | **16 passed (16)** (100%) | S11 결함 회귀 0건 |
| TypeScript 타입 검사 | 
px tsc -b | **0 errors** (exit code 0) | 타입 안전성 100% |
| Vite 프로덕션 빌드 | 
pm run build | **Built successfully** (exit code 0) | 번들 생성 정상 |
| 파이썬 라우트 커버리지 | pytest tests/test_route_coverage.py | **41 passed** (exit code 0) | 화면-백엔드 계약 불변식 유지 |
| 프런트엔드 무결성 검사 | python -X utf8 tools/check_frontend_integrity.py | **0 violations** (PASS) | 9대 무결성 불변식 유지 |
| 계약 바인딩 검사 | python -X utf8 tools/check_contract_bindings.py | **PASS** (exit code 0) | 계약 서빙 앵커 유지 |
| 문서 무결성 검사 | python tools/check_docs.py | **PASS** (exit code 0) | 문서 링크/ID 정상 |
| 옵시디언 동기화 검사 | python tools/sync_obsidian.py --check | **0 conflicts** (exit code 0) | vault 충돌 없음 |
| Git 차분 위생 검사 | git diff --check | **clean** (exit code 0) | 공백/CR 위반 0건 |
