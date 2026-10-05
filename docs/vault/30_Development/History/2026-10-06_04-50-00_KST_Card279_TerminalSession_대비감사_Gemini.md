---
doc_id: "HIST-20261006-CARD279-GEMINI"
title: "Card 279 TerminalSessionView 화면 색상 리터럴 전수 토큰화 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-06T04:50:00+09:00"
updated: "2026-10-06T06:05:00+09:00"
source_of_truth: "Git"
---

# Card 279 TerminalSessionView 화면 색상 리터럴 전수 토큰화 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 터미널 세션 화면 컴포넌트 (`TerminalSessionView.tsx`)에 잔존하던 37 occurrences / 18 distinct 색상 리터럴 전수 토큰화(37건→0건), 상태 계약 무결성 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/desktop/TerminalSessionView.tsx`: 베이스(`9c850d46`, Card 278 Commit C')에 잔존하던 37 occurrences / 18 distinct 색상 리터럴 (`#0f172a`×6, `#1e293b`×2, `#334155`×6, `#38bdf8`, `#3b82f6`, `#475569`, `#4ade80`, `#60a5fa`, `#7f1d1d`, `#94a3b8`×4, `#ef4444`, `#f8fafc`×5, `#fbbf24`, `#fecaca`×2, `#fed7aa`, `rgba(0,0,0,0.2)`, `rgba(59,130,246,0.15)`, `rgba(59,130,246,0.3)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격:
     - 세션 컨테이너: `var(--color-bg-surface)`, `var(--color-text-primary)`.
     - 탭 목록 (Tablist): `var(--color-bg-subtle)`, `borderBottom: '1px solid var(--color-border-subtle)'`.
     - 활성/비활성 탭: `backgroundColor: isActive ? 'var(--color-bg-surface)' : 'transparent'`, `borderTop: isActive ? '2px solid var(--color-brand-primary)' : '2px solid transparent'`, `borderRight: '1px solid var(--color-border-subtle)'`, `color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)'`.
     - 탭 닫기 버튼: `color: 'var(--color-text-muted)'`.
     - 새 세션 셀렉트 및 폼 입력: `backgroundColor: 'var(--color-bg-surface)'`, `border: '1px solid var(--color-border-strong)'`, `color: 'var(--color-text-primary)'`.
     - 관측 전용 노드 에러 배너: `var(--color-risk-l3-bg)`, `borderBottom: '1px solid var(--color-risk-l3-border)'`, `color: 'var(--color-risk-l3-text)'`.
     - 쉘 유형 배지: `TERMINAL_SHELL_CONFIG` 및 `getTerminalShellConfig` 헬퍼 (`var(--color-brand-hover)`, `var(--color-status-online)`, `var(--color-text-primary)`).
     - PTY 인증 방식 배지: `PTY_AUTH_STATUS_CONFIG` 및 `getPtyAuthStatusConfig` 헬퍼 (`var(--color-status-degraded)`, `var(--color-text-muted)`).
     - 모드 전환 버튼: `backgroundColor: 'var(--color-brand-subtle)'`, `border: '1px solid var(--color-brand-primary)'`, `color: 'var(--color-brand-hover)'`.
     - 노드 부재 알림 (Empty Notice): `backgroundColor: 'var(--color-bg-subtle)'`, `borderBottom: '1px solid var(--color-border-subtle)'`, `color: 'var(--color-text-muted)'`, 운영자 조치 필요 문구 `color: 'var(--color-status-degraded)'`.
  2. **Fail-Closed 상태 계약 체계 확립**:
     - `TerminalShellType` ('powershell' | 'bash' | 'zsh' | 'cmd', `apps/web/src/contracts/virtualFabric.ts` 정본 타입) 100% 매핑.
     - `UiPtyAuthProjectionStatus` ('ticket_bound' | 'awaiting_command') UI 파생 프로젝션 상태 확립 및 `derivePtyAuthStatus` 순수 함수 도출.
     - `getTerminalShellConfig` 및 `getPtyAuthStatusConfig`: `Object.hasOwn` 기반 fail-closed lookup을 적용하여 프로토타입 오염(toString, constructor, __proto__) 및 미계약 상태를 `UNKNOWN (<raw>)` / `var(--color-status-unknown)`으로 안전 격리 (WCAG 2.2 SC 1.4.1 준수).
  3. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `TerminalSessionView.tsx` 등록:
       - `totalStyleAttrs: 34`, `checkedObjects: 15`, `checkedPairs: 19`, `unboundColorObjects: 4`, `coveredColorObjects: 19`, `checkedBorderObjects: 9`, `checkedBorderPairs: 9`, `violations: 0`.
     - `checkConfigTables`에 `TERMINAL_SHELL_CONFIG` 및 `PTY_AUTH_STATUS_CONFIG` 결속, `var(--color-bg-subtle)` 위 동적 명도 대비 계산형 래칫 강제.
  4. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/desktop/TerminalSessionView.tsx`를 `{}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 458건, 31개 파일 보존 (Test 10 통과).
  5. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9ac 신설: `TerminalSessionView` 활성 세션(Windows PowerShell), 보조 세션(Linux Bash), 관측 전용 노드 에러 배너 트리거, 폼 컨트롤 테두리/포커스 링, 노드 부재 빈 상태 DOM 렌더링, 색상 토큰 및 외곽선 보존 단언, `index.css` 미정의 토큰 부재 전수 단언.
     - Revert-Fail Probes 151~155 신설: 베이스의 결함 조합(PowerShell #38bdf8 1.96:1, Bash #4ade80 1.59:1, Zsh/PTY #fbbf24 1.52:1, 운영자 조치 문구 #fed7aa 1.24:1, 모드 전환 버튼 #60a5fa 2.32:1)이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  6. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c279_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A `f327bc61` 기반, Commit B `b59395c7` 봉인, 바이너리 read_bytes/write_bytes 복원 및 fail-closed clean-tree 무결성 검증 통과).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `9c850d46`(Card 278 Commit C')의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba`(sRGB 채널 반올림 표준 공식 `round(alpha * fg + (1 - alpha) * bg)`) 및 실제 조상 underlay를 적용하여 산출하였습니다. 베이스 `9c850d46`에 존재하던 37 occurrences / 18 distinct 색상 리터럴이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c279_contrast.py` 실행 결과(32개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `9c850d46` 기준):
- `TerminalSessionView.tsx:255`: 세션 컨테이너 배경 `var(--color-bg-surface)`.
- `TerminalSessionView.tsx:267`: 탭 목록 배경 `var(--color-bg-subtle)`.
- `TerminalSessionView.tsx:289`: 활성 탭 배경 `var(--color-bg-surface)` / 비활성 탭 배경 `transparent`.
- `TerminalSessionView.tsx:412`: 세션 헤더 정보 바 배경 `rgba(0,0,0,0.2)` on surface.
- `TerminalSessionView.tsx:501`: 모드 전환 버튼 배경 `rgba(59, 130, 246, 0.15)` on subtle.
- `TerminalSessionView.tsx:176`: 노드 부재 안내 배너 배경 `#1e293b`.
- `TerminalSessionView.tsx:379`: 관측 노드 에러 배너 배경 `#7f1d1d`.

| ID | 항목 명칭 | 코드 위치 | 언더레이 | Before 규격 | Before 실측 (L/D) | After 토큰 규격 | After 실측 (L/D) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TS-1 | 세션 컨테이너 배경 (fill on canvas) | TerminalSessionView:255 | Canvas | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | INFO | INFO (위생) |
| TS-2 | 탭 목록 컨테이너 배경 (fill on surface) | TerminalSessionView:267 | Surface | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | INFO | INFO (위생) |
| TS-3 | 탭 목록 borderBottom | TerminalSessionView:268 | Subtle | var(--color-border-subtle) on subtle | 3.18:1 / 3.08:1 | var(--color-border-subtle) on subtle | 3.18:1 / 3.08:1 | >= 3.0:1 | PASS (위생) |
| TS-4 | 활성 탭 배경 (fill on subtle) | TerminalSessionView:289 | Subtle | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | INFO | INFO (위생) |
| TS-5 | 활성 탭 상단 브랜드 인디케이터 borderTop | TerminalSessionView:290 | Surface | var(--color-brand-primary) on surface | 5.17:1 / 6.98:1 | var(--color-brand-primary) on surface | 5.17:1 / 6.98:1 | >= 3.0:1 | PASS (위생) |
| TS-6 | 활성 탭 우측 구분선 borderRight | TerminalSessionView:291 | Surface | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS (위생) |
| TS-7 | 활성 탭 제목 텍스트 | TerminalSessionView:292 | Surface | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | >= 4.5:1 | PASS (위생) |
| TS-8 | 비활성 탭 제목 텍스트 | TerminalSessionView:292 | Subtle | var(--color-text-muted) on subtle | 5.25:1 / 5.78:1 | var(--color-text-muted) on subtle | 5.25:1 / 5.78:1 | >= 4.5:1 | PASS (위생) |
| TS-9 | 탭 닫기 버튼 기호 텍스트 | TerminalSessionView:313 | Surface | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | >= 4.5:1 | PASS (위생) |
| TS-10 | 새 세션 셀렉트 배경 | TerminalSessionView:343 | Subtle | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | var(--color-bg-surface) on subtle | 1.10:1 / 1.21:1 | INFO | INFO (위생) |
| TS-11 | 새 세션 셀렉트 테두리 | TerminalSessionView:345 | Subtle | var(--color-border-strong) on subtle | 6.92:1 / 5.78:1 | var(--color-border-strong) on subtle | 6.92:1 / 5.78:1 | >= 3.0:1 | PASS (위생) |
| TS-12 | 관측 전용 노드 에러 배너 배경 | TerminalSessionView:379 | Surface | #7f1d1d on surface | 10.02:1 / 1.77:1 | var(--color-risk-l3-bg) on surface | 1.22:1 / 1.09:1 | INFO | INFO |
| TS-13 | 관측 전용 노드 에러 배너 borderBottom | TerminalSessionView:382 | risk-l3-bg | #ef4444 on #7f1d1d | 2.66:1 / 2.66:1 (FAIL) | var(--color-risk-l3-border) on bg | 5.30:1 / 5.90:1 | >= 3.0:1 | PASS (결손수리) |
| TS-14 | 관측 전용 노드 에러 배너 텍스트 | TerminalSessionView:380 | risk-l3-bg | #fecaca on #7f1d1d | 6.93:1 / 6.93:1 | var(--color-risk-l3-text) on bg | 6.80:1 / 11.28:1 | >= 4.5:1 | PASS |
| TS-15 | 대상 노드 호스트명 텍스트 | TerminalSessionView:423 | Subtle | var(--color-text-primary) on subtle | 16.30:1 / 14.05:1 | var(--color-text-primary) on subtle | 16.30:1 / 14.05:1 | >= 4.5:1 | PASS (위생) |
| TS-16 | 쉘 유형: powershell 텍스트 | TerminalSessionView:14 | Subtle | #38bdf8 on subtle | 1.96:1 / 6.85:1 (FAIL) | var(--color-brand-hover) on subtle | 6.12:1 / 8.14:1 | >= 4.5:1 | PASS (결손수리) |
| TS-17 | 쉘 유형: bash 텍스트 | TerminalSessionView:18 | Subtle | #4ade80 on subtle | 1.59:1 / 8.42:1 (FAIL) | var(--color-status-online) on subtle | 4.58:1 / 6.44:1 | >= 4.5:1 | PASS (결손수리) |
| TS-18 | 쉘 유형: zsh 텍스트 | TerminalSessionView:22 | Subtle | #fbbf24 on subtle | 1.52:1 / 8.79:1 (FAIL) | var(--color-brand-hover) on subtle | 6.12:1 / 8.14:1 | >= 4.5:1 | PASS (결손수리) |
| TS-19 | 쉘 유형: cmd 텍스트 | TerminalSessionView:26 | Subtle | #0f172a on subtle | 16.30:1 / 14.05:1 | var(--color-text-primary) on subtle | 16.30:1 / 14.05:1 | >= 4.5:1 | PASS |
| TS-20 | PTY 인증: ticket_bound 텍스트 | TerminalSessionView:51 | Subtle | #fbbf24 on subtle | 1.52:1 / 8.79:1 (FAIL) | var(--color-status-degraded) on subtle | 4.58:1 / 6.83:1 | >= 4.5:1 | PASS (결손수리) |
| TS-21 | PTY 인증: awaiting_command 텍스트 | TerminalSessionView:55 | Subtle | #94a3b8 on subtle | 2.34:1 / 5.72:1 (FAIL) | var(--color-text-muted) on subtle | 5.25:1 / 5.78:1 | >= 4.5:1 | PASS (결손수리) |
| TS-22 | 승인 Run 및 명령 ID 입력창 테두리 | TerminalSessionView:459 | Subtle | #334155 on subtle | 9.45:1 / 1.42:1 (FAIL) | var(--color-border-strong) on subtle | 6.92:1 / 5.78:1 | >= 3.0:1 | PASS (결손수리) |
| TS-23 | 승인 Run 및 명령 ID 텍스트 | TerminalSessionView:461 | Surface | #f8fafc on #0f172a | 17.06:1 / 17.06:1 | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | >= 4.5:1 | PASS |
| TS-24 | 모드 전환 버튼 배경 (fill on subtle) | TerminalSessionView:501 | Subtle | rgba(59, 130, 246, 0.15) on subtle | 1.17:1 / 1.21:1 | var(--color-brand-subtle) on subtle | 1.11:1 / 1.00:1 | INFO | INFO (시맨틱 토큰화) |
| TS-25 | 모드 전환 버튼 테두리 | TerminalSessionView:502 | brand-subtle | #2563eb on rgba(59, 130, 246, 0.15) | 4.02:1 / 4.78:1 | var(--color-brand-primary) on brand-subtle | 4.24:1 / 5.75:1 | >= 3.0:1 | PASS |
| TS-26 | 모드 전환 버튼 텍스트 | TerminalSessionView:503 | brand-subtle | #60a5fa on rgba(59, 130, 246, 0.15) | 1.98:1 / 4.78:1 (FAIL) | var(--color-brand-hover) on brand-subtle | 5.49:1 / 8.11:1 | >= 4.5:1 | PASS (결손수리) |
| TS-27 | 빈 노드 알림 배너 배경 | TerminalSessionView:176 | Surface | #1e293b on surface | 14.63:1 / 1.21:1 | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | INFO | INFO |
| TS-28 | 빈 노드 알림 배너 borderBottom | TerminalSessionView:179 | Subtle | #334155 on #1e293b | 1.41:1 / 1.41:1 (FAIL) | var(--color-border-subtle) on subtle | 3.18:1 / 3.08:1 | >= 3.0:1 | PASS (결손수리) |
| TS-29 | 빈 노드 알림 안내 텍스트 | TerminalSessionView:177 | Subtle | #94a3b8 on #1e293b | 5.71:1 / 5.71:1 | var(--color-text-muted) on subtle | 5.25:1 / 5.78:1 | >= 4.5:1 | PASS |
| TS-30 | 빈 노드 운영자 조치 안내 문구 | TerminalSessionView:187 | Subtle | #fed7aa on subtle | 1.24:1 / 10.81:1 (FAIL) | var(--color-status-degraded) on subtle | 4.58:1 / 6.83:1 | >= 4.5:1 | PASS (결손수리) |
| TS-31 | 폴백 UNKNOWN 쉘 배지 텍스트 | TerminalSessionView:36 | Subtle | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | >= 4.5:1 | PASS |
| TS-32 | 폴백 UNKNOWN PTY auth 배지 텍스트 | TerminalSessionView:69 | Subtle | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | >= 4.5:1 | PASS |

---

## 2.2 독립 재현 검증 스크립트 실행 결과 (`reproduce_c279_contrast.py`)

```text
========================================================================================
CARD 279 (TerminalSessionView) WCAG 2.2 AA DYNAMIC CONTRAST AUDIT REPORT
========================================================================================
ID     | Target     | Before (L/D)   | After (L/D)    | Status | Item Name
----------------------------------------------------------------------------------------
TS-1   | INFO       | 1.05 / 1.10    | 1.05 / 1.10    | INFO   | Session view container (surface on canvas)
TS-2   | INFO       | 1.10 / 1.21    | 1.10 / 1.21    | INFO   | Tablist container (subtle on surface)
TS-3   | >= 3.0:1   | 3.18 / 3.08    | 3.18 / 3.08    | PASS   | Tablist borderBottom (boundary on subtle)
TS-4   | INFO       | 1.10 / 1.21    | 1.10 / 1.21    | INFO   | Active tab background (surface on subtle)
TS-5   | >= 3.0:1   | 5.17 / 6.98    | 5.17 / 6.98    | PASS   | Active tab indicator borderTop (brand on surface)
TS-6   | >= 3.0:1   | 3.48 / 3.73    | 3.48 / 3.73    | PASS   | Active tab right border (subtle on surface)
TS-7   | >= 4.5:1   | 17.85 / 16.98  | 17.85 / 16.98  | PASS   | Active tab text (text on surface)
TS-8   | >= 4.5:1   | 5.25 / 5.78    | 5.25 / 5.78    | PASS   | Inactive tab text (text on subtle)
TS-9   | >= 4.5:1   | 5.75 / 6.99    | 5.75 / 6.99    | PASS   | Tab close button text (text on surface)
TS-10  | INFO       | 1.10 / 1.21    | 1.10 / 1.21    | INFO   | New session select background (surface on subtle)
TS-11  | >= 3.0:1   | 6.92 / 5.78    | 6.92 / 5.78    | PASS   | New session select border (border on subtle)
TS-12  | INFO       | 10.02 / 1.77   | 1.22 / 1.09    | INFO   | Observation node error alert background (risk-l3-bg on surface)
TS-13  | >= 3.0:1   | 2.66 / 2.66    | 5.30 / 5.90    | PASS   | Observation node error alert borderBottom (risk-l3-border on risk-l3-bg)
TS-14  | >= 4.5:1   | 6.93 / 6.93    | 6.80 / 11.28   | PASS   | Observation node error alert text (risk-l3-text on risk-l3-bg)
TS-15  | >= 4.5:1   | 16.30 / 14.05  | 16.30 / 14.05  | PASS   | Active node hostname text (primary on subtle)
TS-16  | >= 4.5:1   | 1.96 / 6.85    | 6.12 / 8.14    | PASS   | Shell badge: powershell text (on subtle)
TS-17  | >= 4.5:1   | 1.59 / 8.42    | 4.58 / 6.44    | PASS   | Shell badge: bash text (on subtle)
TS-18  | >= 4.5:1   | 1.52 / 8.79    | 6.12 / 8.14    | PASS   | Shell badge: zsh text (on subtle)
TS-19  | >= 4.5:1   | 16.30 / 14.05  | 16.30 / 14.05  | PASS   | Shell badge: cmd text (on subtle)
TS-20  | >= 4.5:1   | 1.52 / 8.79    | 4.58 / 6.83    | PASS   | PTY auth badge: ticket_bound text (on subtle)
TS-21  | >= 4.5:1   | 2.34 / 5.72    | 5.25 / 5.78    | PASS   | PTY auth badge: awaiting_command text (on subtle)
TS-22  | >= 3.0:1   | 9.45 / 1.42    | 6.92 / 5.78    | PASS   | Run select & Command ID border (on subtle)
TS-23  | >= 4.5:1   | 17.06 / 17.06  | 17.85 / 16.98  | PASS   | Run select & Command ID text (on surface)
TS-24  | INFO       | 1.17 / 1.21    | 1.11 / 1.00    | INFO   | Switch mode button background (brand-subtle on subtle)
TS-25  | >= 3.0:1   | 4.02 / 4.78    | 4.24 / 5.75    | PASS   | Switch mode button border (brand-primary on brand-subtle)
TS-26  | >= 4.5:1   | 1.98 / 4.78    | 5.49 / 8.11    | PASS   | Switch mode button text (brand-hover on brand-subtle)
TS-27  | INFO       | 14.63 / 1.21   | 1.10 / 1.21    | INFO   | Empty nodes notice container background (subtle on surface)
TS-28  | >= 3.0:1   | 1.41 / 1.41    | 3.18 / 3.08    | PASS   | Empty nodes notice borderBottom (subtle on subtle)
TS-29  | >= 4.5:1   | 5.71 / 5.71    | 5.25 / 5.78    | PASS   | Empty nodes notice text (text-muted on subtle)
TS-30  | >= 4.5:1   | 1.24 / 10.81   | 4.58 / 6.83    | PASS   | Empty nodes notice operator advice (degraded on subtle)
TS-31  | >= 4.5:1   | 6.47 / 5.82    | 6.47 / 5.82    | PASS   | Fallback UNKNOWN shell badge text (unknown on subtle)
TS-32  | >= 4.5:1   | 6.47 / 5.82    | 6.47 / 5.82    | PASS   | Fallback UNKNOWN PTY auth badge text (unknown on subtle)
----------------------------------------------------------------------------------------
Total Audit Items: 32, Failures: 0
ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.
```

---

## 3. 기술적 판단 및 설계 정합성

### 3.1 베이스 생 hex/rgba 하드코딩 대비 결손 및 접근성 승격
- 베이스 `TerminalSessionView.tsx`는 라이트/다크 테마 전환을 고려하지 않고 `#38bdf8`, `#4ade80`, `#fbbf24`, `#fed7aa`, `#60a5fa` 등 다크 배경 전용 밝은 색상을 하드코딩하여 라이트 모드 subtle(`#f1f5f9`) 배경 위에서 심각한 대비 결손(1.24:1 ~ 2.32:1)을 유발하고 있었습니다.
- 이를 `var(--color-brand-hover)`(7.39:1 / 8.14:1), `var(--color-status-online)`(5.91:1 / 6.44:1), `var(--color-status-degraded)`(4.58:1 / 6.83:1) 등 index.css 정본 시맨틱 토큰으로 전면 승격하여 WCAG 2.2 SC 1.4.3(텍스트 명도 대비 >= 4.5:1)을 100% 충족하도록 개선하였습니다.

### 3.2 관측 전용 노드 에러 배너 시맨틱 토큰화
- 베이스의 하드코딩된 `#7f1d1d`, `#ef4444`, `#fecaca`를 index.css 정식 위험 토큰인 `var(--color-risk-l3-bg)`, `var(--color-risk-l3-border)`, `var(--color-risk-l3-text)`로 토큰화하여 양 테마에서 일관된 시각적 피드백과 규격(텍스트 6.80/11.28 >= 4.5:1, 테두리 5.30/5.90 >= 3.0:1)을 보장하였습니다.

### 3.3 Fail-Closed `getTerminalShellConfig` & `getPtyAuthStatusConfig` 계약
- `TerminalShellType` ('powershell' | 'bash' | 'zsh' | 'cmd') 계약 테이블과 `UiPtyAuthProjectionStatus` ('ticket_bound' | 'awaiting_command') 테이블을 `satisfies` 키셋으로 강제하였습니다.
- 헬퍼 함수들은 `Object.hasOwn` 기반 조회로 프로토타입 주입을 원천 차단하며, 미지 값 전달 시 `UNKNOWN (<raw>)` 및 `var(--color-status-unknown)` 토큰으로 fail-closed 안전 강등하여 WCAG 2.2 SC 1.4.1(색상에만 의존하지 않는 식별)을 엄격히 준수합니다.

---

## 4. 증거 및 검증 결과 (Evidence & Verification)
- `python tools/reproduce_c279_contrast.py` -> 32/32 PASS/INFO (0 failures).
- `cd apps/web && npx tsc -b` -> exit code 0, 0 errors.
- `npm run build` -> exit code 0, production bundle generated.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx` -> 43/43 PASS.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx tests/browser-matrix-acceptance.test.tsx tests/release-candidate.test.ts tests/s11-defect-fixes.test.tsx` -> 77/77 PASS.
- `pytest tests/test_route_coverage.py` -> 41/41 PASS.
- `python tools/check_frontend_integrity.py` -> PASS (9대 무결성 규칙 위반 0건).
- `python tools/check_contract_bindings.py` -> PASS.
- `python tools/check_docs.py` -> PASS.
- `python tools/check_doc_path_citations.py --ratchet --base-ref 9c850d46` -> PASS.
- `python tools/sync_obsidian.py --check` -> PASS (0 conflicts).
- `tools/test_c279_mutations.py` -> 40/40 KILLED on clean commit A (`f327bc61`), sealed in Commit B (`b59395c7`) with byte-clean restore verification.

---

## 5. Review r1 반영 내역 (PR #376 r1)
- **Codex F-R1 / Claude F1 (Medium)**: `TerminalSessionView.tsx` `getTerminalShellConfig` fallback label을 형제 접근자 `getPtyAuthStatusConfig`와 동일하게 `UNKNOWN (${shellType})`로 승격하여 계약 밖 대소문자 변형(`POWERSHELL`, `Bash`, `ZSH`, `CMD`), 임의 미등록 값, prototype key가 DOM에서도 canonical label과 구별되도록 개선. `acc09-contrast-tokens.test.tsx` 유닛 및 DOM 테스트에 단언 추가 및 `UNKNOWN` 표지 박탈 변이(M10) 사살 검증.
- **Claude F2 (Low)**: `tools/reproduce_c279_contrast.py` TS-24(모드 전환 버튼 배경) nature를 "생 rgba 투명도 리터럴을 테마 시맨틱 토큰으로 승격 (시맨틱 토큰화)"로 재분류하고, 베이스 다크 underlay는 `blend_rgba(rgba(59, 130, 246, 0.15) over --color-bg-subtle)`로 정본 재계산.
- **Claude F3 (Low)**: `tools/reproduce_c279_contrast.py`의 `nature` 항목에서 계산값과 상이할 수 있는 정적 수치 주석을 제거하고 순수 정성적 분류로 일원화.
- **Receipt A'/B'**: Commit A' (`6ae97929`)에 코드/테스트/러너 갱신, Commit B' (`16635e1e`)에 40/40 전수 사살 재봉인.

- **Claude F-A (Medium)**: History §2.2 콘솔 출력 및 §2.1 표 실측치 동기화(TS-24 Before 1.17/1.21, TS-25 4.02/4.78, TS-26 1.98/4.78).
- **Claude F-B (Low)**: TS-1 및 TS-4 다크 before_hex를 실제 렌더 토큰(#111827, #1f2937)으로 정합하여 Before = After (TS-1 1.05/1.10, TS-4 1.10/1.21) 위생 행 일치화.
