---
doc_id: "HIST-20261005-CARD273-GEMINI"
title: "Card 273 공용 및 소형 화면 (Shared & Minor UI) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격"
version: "1.1.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T16:25:00+09:00"
updated: "2026-10-05T18:00:00+09:00"
source_of_truth: "Git"
---

# Card 273 공용 및 소형 화면 (Shared & Minor UI) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 공용 컴포넌트 및 소형 작업공간 화면 묶음 4개 파일의 색상 리터럴 전수(8건→0건) 토큰화 및 디자인 토큰 체계 승격:
  1. `apps/web/src/shared/ui/Button.tsx`: `#ffffff` 2건 전수 제거 및 `var(--color-brand-primary-fg)` 토큰 승격. primary(`var(--color-brand-primary-bg)`), danger(`var(--color-status-offline-bg)`), secondary(`var(--color-bg-subtle)`/`var(--color-border-strong)`), ghost(`var(--color-text-secondary)`) 전 변형의 WCAG 2.2 AA (텍스트 >= 4.5:1, 테두리 >= 3.0:1) 달성. 포커스 링 보호(`outline` 억제 금지 불변식)를 AST 및 DOM 렌더 단언으로 이중 사살.
  2. `apps/web/src/shared/ui/RiskBadge.tsx`: 15% 반투명 리터럴 `rgba(16,185,129,0.15)`, `rgba(59,130,246,0.15)`, `rgba(245,158,11,0.15)`, `rgba(239,68,68,0.15)` 4건 전수 제거 및 `var(--color-bg-subtle)` 토큰 승격. 정본 wire 계약 enum `RiskLevel` 4종(`L0`, `L1`, `L2`, `L3`)과 100% 일치하고 컴파일 타임 완전성을 강제하는 `as const satisfies Record<RiskLevel, RiskConfigItem>` 선언.
  3. `getRiskLevelConfig` fail-closed own-key 방어: `Object.hasOwn` 기반 검사로 prototype key(`toString`, `constructor`, `__proto__`, `valueOf`, `hasOwnProperty`, `isPrototypeOf`), 대소문자 변형(`l0`), 계약 밖 임의 상태(`L4`, `HIGH`, `CRITICAL`)의 fail-open 승격을 원천 차단하고 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 형식으로 안전 강등 매핑 (WCAG 1.4.1 준수).
  4. `apps/web/src/features/workspaces/ExecutionResultView.tsx`: 종료 코드 성공 배지 `rgba(16,185,129,0.15)` 1건 제거 및 `var(--color-bg-subtle)` 토큰 승격. 베이스의 라이트 표면 합성 명도비 3.26:1 결손(FAIL < 4.5:1)을 해소.
  5. `apps/web/src/features/workspaces/WorkspaceCreateModal.tsx`: 모달 다이얼로그 백드롭 `rgba(0,0,0,0.65)` 1건 제거 및 `var(--color-bg-backdrop)` 토큰 승격. 모달 백드롭 스크림은 다이얼로그 서피스 뒤편의 비텍스트 오버레이 레이어이며, 모달 내부 텍스트는 불투명 다이얼로그 서피스(`var(--color-bg-surface)`) 위에서 평가됨.
  6. **F1 미정의 토큰 해소 (6개 토큰 양 테마 신설)**: `apps/web/src/index.css` 라이트/다크 테마에 `--color-brand-success`, `--color-brand-danger`, `--color-brand-warning`, `--color-risk-l3-bg`, `--color-risk-l3-border`, `--color-risk-l3-text` 6종 토큰을 정식 선언하여 기존 17곳의 미정의 토큰 사용을 전수 정식 토큰화. 대상 파일 내 모든 `var(--...)`가 `index.css`에 선언된 토큰의 부분집합임을 fail-closed 시험으로 강제.
  7. **F2 AST 정적 분석 래칫 (4개 파일 전수 확장)**: `apps/web/tests/acc09-contrast-tokens.test.tsx`의 9j-2 `analyzeFile` 스위트에 4개 파일 전수를 등록하고 통계 래칫 8줄을 고정. `ExecutionResultView` 1:1 색상 충돌 및 `Button` `baseStyle`의 `outline: 'none'` 포커스 링 억제 결함이 이 카드의 자체 시험으로 즉시 사살됨을 실측 검증.
  8. Multiset Baseline 래칫 강제: `COLOR_LITERAL_MULTISET_BASELINE`에서 4개 파일의 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
  9. 40종 전수 변이 실측 사살: `tools/test_c273_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 복원 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 PR 베이스(`ca54f53e`)의 실제 렌더링 합성값(라이트 캔버스 `#f8fafc` 위 카드 표면 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 베이스 `ca54f53e`에 존재하던 4개 파일의 색상 리터럴 8건(`Button.tsx`: `#ffffff`×2, `RiskBadge.tsx`: `rgba(16,185,129,0.15)`, `rgba(59,130,246,0.15)`, `rgba(245,158,11,0.15)`, `rgba(239,68,68,0.15)`, `ExecutionResultView.tsx`: `rgba(16,185,129,0.15)`, `WorkspaceCreateModal.tsx`: `rgba(0,0,0,0.65)`)이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c273_contrast.py` 실행 결과(32개 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호:
- `Button.tsx`: `btn-primary`(38행 `brand-primary-bg`), `btn-danger`(48행 `status-offline-bg`), `btn-secondary`(43행 `bg-subtle`), `btn-ghost`(53행 투명 → 부모 캔버스/서피스).
- `RiskBadge.tsx`: 23행, 30행, 37행, 44행, 58행, 78행 `config.bgVar` (`var(--color-bg-subtle)`).
- `ExecutionResultView.tsx`: 24행 `h2`(19행 루트 div에 배경 없음 → 조상 캔버스 body `#f8fafc`/`#090d16`), 47행/55행/88행/130행(42행 `var(--color-bg-surface)`), 67행(66행 `var(--color-bg-subtle)`), 215행/219행(214행 `var(--color-risk-l3-bg)`).
- `WorkspaceCreateModal.tsx`: 70행 백드롭(`var(--color-bg-backdrop)` — 비텍스트 스크림 오버레이), 91행/92행(80행 `var(--color-bg-surface)`), 118행(117행 `var(--color-bg-subtle)`), 143행/144행(142행 `var(--color-risk-l3-bg)`).

| UI 요소 | 식별자 / 위치 (코드 근거 줄) | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light/Dark 렌더 실측) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Primary 버튼 텍스트 | btn-primary text (Button.tsx:38) | #ffffff on var(--color-brand-primary-bg) | 5.17:1 (PASS) / 6.70:1 (PASS) | --color-brand-primary-fg on --color-brand-primary-bg | 5.17:1 | 6.70:1 | >= 4.5:1 | PASS |
| Danger 버튼 텍스트 | btn-danger text (Button.tsx:48) | #ffffff on var(--color-status-offline-bg) | 4.83:1 (PASS) / 4.83:1 (PASS) | --color-brand-primary-fg on --color-status-offline-bg | 4.83:1 | 4.83:1 | >= 4.5:1 | PASS |
| Secondary 버튼 텍스트 | btn-secondary text (Button.tsx:43) | var(--color-text-primary) on var(--color-bg-subtle) | 16.30:1 (PASS) / 14.05:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| Secondary 버튼 테두리 | btn-secondary border (Button.tsx:43) | var(--color-border-strong) on var(--color-bg-subtle) | 6.92:1 (PASS) / 5.78:1 (PASS) | --color-border-strong on --color-bg-subtle | 6.92:1 | 5.78:1 | >= 3.0:1 | PASS |
| Ghost 버튼 (캔버스) | btn-ghost text (Button.tsx:53 on canvas) | var(--color-text-secondary) on var(--color-bg-canvas) | 7.24:1 (PASS) / 15.69:1 (PASS) | --color-text-secondary on --color-bg-canvas | 7.24:1 | 15.69:1 | >= 4.5:1 | PASS |
| Ghost 버튼 (서피스) | btn-ghost text (Button.tsx:53 on surface) | var(--color-text-secondary) on var(--color-bg-surface) | 7.58:1 (PASS) / 14.33:1 (PASS) | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 위험 등급 L0 텍스트 | risk-l0 text (RiskBadge.tsx:23,78) | var(--color-risk-l0) on 15% tint (합성 #dbf4ec / #113034) | 6.65:1 (PASS) / 7.30:1 (PASS) | --color-risk-l0 on --color-bg-subtle | 7.01:1 | 7.64:1 | >= 4.5:1 | PASS |
| 위험 등급 L0 테두리 | risk-l0 border (RiskBadge.tsx:23,79) | var(--color-risk-l0) on 15% tint (합성 #dbf4ec / #113034) | 6.65:1 (PASS) / 7.30:1 (PASS) | --color-risk-l0 on --color-bg-subtle | 7.01:1 | 7.64:1 | >= 3.0:1 | PASS |
| 위험 등급 L1 텍스트 | risk-l1 text (RiskBadge.tsx:30,78) | var(--color-risk-l1) on 15% tint (합성 #e2ecfe / #172846) | 5.64:1 (PASS) / 5.78:1 (PASS) | --color-risk-l1 on --color-bg-subtle | 6.12:1 | 5.77:1 | >= 4.5:1 | PASS |
| 위험 등급 L1 테두리 | risk-l1 border (RiskBadge.tsx:30,79) | var(--color-risk-l1) on 15% tint (합성 #e2ecfe / #172846) | 5.64:1 (PASS) / 5.78:1 (PASS) | --color-risk-l1 on --color-bg-subtle | 6.12:1 | 5.77:1 | >= 3.0:1 | PASS |
| 위험 등급 L2 텍스트 | risk-l2 text (RiskBadge.tsx:37,78) | var(--color-risk-l2) on 15% tint (합성 #fef0da / #332c23) | 6.31:1 (PASS) / 6.41:1 (PASS) | --color-risk-l2 on --color-bg-subtle | 6.47:1 | 6.83:1 | >= 4.5:1 | PASS |
| 위험 등급 L2 테두리 | risk-l2 border (RiskBadge.tsx:37,79) | var(--color-risk-l2) on 15% tint (합성 #fef0da / #332c23) | 6.31:1 (PASS) / 6.41:1 (PASS) | --color-risk-l2 on --color-bg-subtle | 6.47:1 | 6.83:1 | >= 3.0:1 | PASS |
| 위험 등급 L3 텍스트 | risk-l3 text (RiskBadge.tsx:44,78) | var(--color-risk-l3) on 15% tint (합성 #fde3e3 / #321f2b) | 5.32:1 (PASS) / 5.56:1 (PASS) | --color-risk-l3 on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 위험 등급 L3 테두리 | risk-l3 border (RiskBadge.tsx:44,79) | var(--color-risk-l3) on 15% tint (합성 #fde3e3 / #321f2b) | 5.32:1 (PASS) / 5.56:1 (PASS) | --color-risk-l3 on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 위험 등급 UNKNOWN 텍스트 | risk-unknown text (RiskBadge.tsx:58,78) | base에 fallback 없음 (미정의) | 미정의 (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 위험 등급 UNKNOWN 테두리 | risk-unknown border (RiskBadge.tsx:58,79) | base에 fallback 없음 (미정의) | 미정의 (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| 실행 결과 헤더 제목 | exec-header text (ExecutionResultView.tsx:24) | var(--color-text-primary) on canvas (19행 배경없음) | 17.06:1 (PASS) / 18.59:1 (PASS) | --color-text-primary on --color-bg-canvas | 17.06:1 | 18.59:1 | >= 4.5:1 | PASS |
| 실행 결과 카드 라벨 | exec-card-label text (ExecutionResultView.tsx:47) | var(--color-text-muted) on surface (42행) | 5.75:1 (PASS) / 6.99:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 증거 봉투 ID | exec-envelope-id text (ExecutionResultView.tsx:88) | var(--color-brand-primary) on surface (80행) | 5.17:1 (PASS) / 6.98:1 (PASS) | --color-brand-primary on --color-bg-surface | 5.17:1 | 6.98:1 | >= 4.5:1 | PASS |
| 모달 제목 텍스트 | modal-title text (WorkspaceCreateModal.tsx:91) | var(--color-text-primary) on surface (80행) | 17.85:1 (PASS) / 16.98:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 모달 부제목 텍스트 | modal-subtitle text (WorkspaceCreateModal.tsx:92) | var(--color-text-muted) on surface (80행) | 5.75:1 (PASS) / 6.99:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 모달 안내 배너 테두리 | modal-notice border (WorkspaceCreateModal.tsx:118) | var(--color-border-subtle) on subtle (117행) | 3.18:1 (PASS) / 3.08:1 (PASS) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 실행 성공 텍스트 | exec-success text (ExecutionResultView.tsx:67) | 미정의 var(--color-brand-success) | 상속색 (FAIL) | --color-brand-success on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 실행 실패 텍스트 | exec-danger text (ExecutionResultView.tsx:67) | 미정의 var(--color-brand-danger) | 상속색 (FAIL) | --color-brand-danger on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 회수 상태 경고 텍스트 | exec-reclaimed-warning text (ExecutionResultView.tsx:130) | 미정의 var(--color-brand-warning) | 상속색 (FAIL) | --color-brand-warning on --color-bg-surface | 7.09:1 | 8.26:1 | >= 4.5:1 | PASS |
| 종료 코드 성공 텍스트 | exec-exitcode-success text (ExecutionResultView.tsx:55) | 미정의 var(--color-brand-success) | 상속색 (FAIL) | --color-brand-success on --color-bg-surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| 종료 코드 실패 텍스트 | exec-exitcode-danger text (ExecutionResultView.tsx:55) | 미정의 var(--color-brand-danger) | 상속색 (FAIL) | --color-brand-danger on --color-bg-surface | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| 종료 코드 L3 테두리 | exec-risk-l3-border border (ExecutionResultView.tsx:44) | 미정의 var(--color-risk-l3-border) | 투명 (FAIL) | --color-risk-l3-border on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| 거부 이벤트 카드 테두리 | exec-risk-l3-card-border border (ExecutionResultView.tsx:215) | 미정의 var(--color-risk-l3-border) | 투명 (FAIL) | --color-risk-l3-border on --color-risk-l3-bg | 5.30:1 | 5.90:1 | >= 3.0:1 | PASS |
| 거부 이벤트 L3 텍스트 | exec-risk-l3 text (ExecutionResultView.tsx:219) | 미정의 var(--color-risk-l3-text) | 상속색 (FAIL) | --color-risk-l3-text on --color-risk-l3-bg | 6.80:1 | 11.28:1 | >= 4.5:1 | PASS |
| 모달 경고 테두리 | modal-warning border (WorkspaceCreateModal.tsx:144) | 미정의 var(--color-risk-l3-border) | 투명 (FAIL) | --color-risk-l3-border on --color-risk-l3-bg | 5.30:1 | 5.90:1 | >= 3.0:1 | PASS |
| 모달 경고 텍스트 | modal-warning text (WorkspaceCreateModal.tsx:143) | 미정의 var(--color-risk-l3-text) | 상속색 (FAIL) | --color-risk-l3-text on --color-risk-l3-bg | 6.80:1 | 11.28:1 | >= 4.5:1 | PASS |

> [!NOTE]
> **모달 백드롭 스크림의 비텍스트 분류 및 불투명도 변화 (0.65 -> 0.75)**:
> `WorkspaceCreateModal.tsx:70`의 베이스 `rgba(0, 0, 0, 0.65)`는 기존 정본 디자인 토큰 `--color-bg-backdrop` (`rgba(0, 0, 0, 0.75)`, 양 테마 동일, `apps/web/src/index.css:7`·`:62`)으로 승격되면서 스크림 오버레이의 불투명도가 0.65에서 0.75로 소폭 짙어졌습니다. 이 요소는 고정 인셋(`position: 'fixed', inset: 0`) 다이얼로그 스크림 오버레이로서 텍스트를 직접 표출하지 않으며, 모달 내부 모든 텍스트 콘텐츠는 80행의 불투명 카드 서피스(`var(--color-bg-surface)`) 위에서 독립 렌더링되므로 비텍스트 스크림 레이어로 분류됩니다.

### 2.2 tools/reproduce_c273_contrast.py 실행 결과 (32개 지표 전수 통과)
```text
===================================================================================================================
ID     Element / Indicator                                          Req   Light    Dark     Status
===================================================================================================================
IT01   btn-primary text (on brand-primary-bg, Button.tsx:38)        4.5   5.17     6.70     PASS  
IT02   btn-danger text (on status-offline-bg, Button.tsx:48)        4.5   4.83     4.83     PASS  
IT03   btn-secondary text (on bg-subtle, Button.tsx:43)             4.5   16.30    14.05    PASS  
IT04   btn-secondary border (on bg-subtle, Button.tsx:43)           3.0   6.92     5.78     PASS  
IT05   btn-ghost text (on canvas, Button.tsx:53)                    4.5   7.24     15.69    PASS  
IT06   btn-ghost text (on surface, Button.tsx:53)                   4.5   7.58     14.33    PASS  
IT07   risk-l0 text (on bg-subtle, RiskBadge.tsx:23,78)             4.5   7.01     7.64     PASS  
IT08   risk-l0 border (on bg-subtle, RiskBadge.tsx:23,79)           3.0   7.01     7.64     PASS  
IT09   risk-l1 text (on bg-subtle, RiskBadge.tsx:30,78)             4.5   6.12     5.77     PASS  
IT10   risk-l1 border (on bg-subtle, RiskBadge.tsx:30,79)           3.0   6.12     5.77     PASS  
IT11   risk-l2 text (on bg-subtle, RiskBadge.tsx:37,78)             4.5   6.47     6.83     PASS  
IT12   risk-l2 border (on bg-subtle, RiskBadge.tsx:37,79)           3.0   6.47     6.83     PASS  
IT13   risk-l3 text (on bg-subtle, RiskBadge.tsx:44,78)             4.5   5.91     5.31     PASS  
IT14   risk-l3 border (on bg-subtle, RiskBadge.tsx:44,79)           3.0   5.91     5.31     PASS  
IT15   risk-unknown text (on bg-subtle, RiskBadge.tsx:58,78)        4.5   6.47     5.82     PASS  
IT16   risk-unknown border (on bg-subtle, RiskBadge.tsx:58,79)      3.0   6.47     5.82     PASS  
IT17   exec-header text (on canvas, ExecutionResultView.tsx:24)     4.5   17.06    18.59    PASS  
IT18   exec-card-label text (on surface, ExecutionResultView.tsx:47) 4.5   5.75     6.99     PASS  
IT19   exec-envelope-id text (on surface, ExecutionResultView.tsx:88) 4.5   5.17     6.98     PASS  
IT20   modal-title text (on surface, WorkspaceCreateModal.tsx:91)   4.5   17.85    16.98    PASS  
IT21   modal-subtitle text (on surface, WorkspaceCreateModal.tsx:92) 4.5   5.75     6.99     PASS  
IT22   modal-notice border (on bg-subtle, WorkspaceCreateModal.tsx:118) 3.0   3.18     3.08     PASS  
IT23   exec-success text (on bg-subtle, ExecutionResultView.tsx:67) 4.5   4.58     6.44     PASS  
IT24   exec-danger text (on bg-subtle, ExecutionResultView.tsx:67)  4.5   5.91     5.31     PASS  
IT25   exec-reclaimed-warning text (on surface, ExecutionResultView.tsx:130) 4.5   7.09     8.26     PASS  
IT26   exec-exitcode-success text (on surface, ExecutionResultView.tsx:55) 4.5   5.02     7.79     PASS  
IT27   exec-exitcode-danger text (on surface, ExecutionResultView.tsx:55) 4.5   6.47     6.41     PASS  
IT28   exec-risk-l3-border border (on surface, ExecutionResultView.tsx:44) 3.0   6.47     6.41     PASS  
IT29   exec-risk-l3-card-border border (on risk-l3-bg, ExecutionResultView.tsx:215) 3.0   5.30     5.90     PASS  
IT30   exec-risk-l3 text (on risk-l3-bg, ExecutionResultView.tsx:219) 4.5   6.80     11.28    PASS  
IT31   modal-warning border (on risk-l3-bg, WorkspaceCreateModal.tsx:144) 3.0   5.30     5.90     PASS  
IT32   modal-warning text (on risk-l3-bg, WorkspaceCreateModal.tsx:143) 4.5   6.80     11.28    PASS  
===================================================================================================================
Overall Result: ALL PASS
```

---

## 3. 계약 정합성 및 접근성 불변식 검증

1. **RiskLevel Wire 계약 일치**:
   - `RISK_CONFIG`는 `RiskLevel` (`apps/web/src/contracts/types.ts`)의 엄밀 집합인 `['L0', 'L1', 'L2', 'L3']` 4종 키만을 정의하며, `as const satisfies Record<RiskLevel, RiskConfigItem>` 선언을 통해 컴파일 타임에 완전성을 강제함 (신규 등급 추가 시 미정의 시 컴파일 에러 발생).
   - Test 9w에서 `Object.keys(RISK_CONFIG).sort()`와 wire enum의 동등성을 런타임에 단언함.

2. **Fail-Closed UNKNOWN 격하 방어**:
   - `getRiskLevelConfig`는 `Object.hasOwn(RISK_CONFIG, level)` 검사를 통해 프로토타입 체인 오염 키(`toString`, `constructor`, `__proto__`, `valueOf`, `hasOwnProperty`, `isPrototypeOf`)의 fail-open 조회를 원천 차단함.
   - 대소문자 변형(`l0`), 계약 외 값(`L4`, `HIGH`, `CRITICAL`), 빈 문자열/`null`/`undefined` 입력 시 안전하게 `UNKNOWN (<raw>)` (또는 원문 없을 시 `UNKNOWN`) 레이블 및 `var(--color-status-unknown)` 토큰으로 격하됨.

3. **F1 미정의 토큰 정의 및 apps/web/src 전수 영향도**:
   - `apps/web/src/index.css`에 신규 선언된 6개 토큰:
     - `--color-brand-success`: Light `#15803d` (4.58:1 on subtle, 5.02:1 on surface), Dark `#22c55e` (6.44:1 on subtle, 7.79:1 on surface).
     - `--color-brand-danger`: Light `#b91c1c` (5.91:1 on subtle, 6.47:1 on surface), Dark `#f87171` (5.31:1 on subtle, 6.41:1 on surface).
     - `--color-brand-warning`: Light `#92400e` (6.47:1 on subtle, 7.09:1 on surface), Dark `#f59e0b` (6.83:1 on subtle, 8.26:1 on surface).
     - `--color-risk-l3-bg`: Light `#fee2e2`, Dark `#3b1219` (컨테이너 배경).
     - `--color-risk-l3-border`: Light `#b91c1c` (5.30:1 on risk-l3-bg, 6.47:1 on surface), Dark `#f87171` (5.90:1 on risk-l3-bg, 6.41:1 on surface).
     - `--color-risk-l3-text`: Light `#991b1b` (6.80:1 on risk-l3-bg, 8.31:1 on surface), Dark `#fecaca` (11.28:1 on risk-l3-bg, 12.26:1 on surface).
   - 영향 범위 (grep 실측):
     - `ExecutionResultView.tsx`: 11개 위치에서 사용 (`brand-success` 6, `brand-danger` 2, `brand-warning` 1, `risk-l3-bg` 2, `risk-l3-border` 3, `risk-l3-text` 2).
     - `WorkspaceCreateModal.tsx`: 3개 위치에서 사용 (`risk-l3-bg` 1, `risk-l3-border` 1, `risk-l3-text` 1).
     - `PlacementExplainView.tsx`: 6개 위치 (Card 274 후속 화면 사전 해소).
     - `ResourceTopologyGraph.tsx`: 5개 위치 (Card 274 후속 화면 사전 해소).
   - Test 9w에 `var(--x) ⊆ index.css declared tokens` 전수 검사를 추가하여 향후 미선언 토큰 유입을 fail-closed로 차단.

4. **F2 AST 정적 분석 래칫 (9j-2 analyzeFile 전수 연동)**:
   - 4개 파일의 통계 래칫 고정:
     - `shared/ui/Button.tsx`: attrs 3, checkedObjects 0, checkedPairs 0, violations 0.
     - `shared/ui/RiskBadge.tsx`: attrs 6, checkedObjects 4, checkedPairs 4, borderObj 4, borderPairs 4, violations 0.
     - `features/workspaces/ExecutionResultView.tsx`: attrs 44, checkedObjects 2, checkedPairs 20, unbound 15, covered 17, borderObj 7, borderPairs 8, violations 0.
     - `features/workspaces/WorkspaceCreateModal.tsx`: attrs 15, checkedObjects 3, checkedPairs 8, unbound 5, covered 8, borderObj 4, borderPairs 4, violations 0.
   - 탐침 직접 실측:
     - `ExecutionResultView.tsx` 1:1 충돌: `color: var(--color-bg-surface)` 주입 시 `1:1 token collision between background and foreground (--color-bg-surface)` 검출로 즉시 사살.
     - `Button.tsx` `baseStyle` `outline: 'none'` 주입: `analyzeFile`의 변수 스타일 검사에서 `Inline outline: none suppressing focus ring` 검출 및 Test 9w DOM 단언(`btn.style.outline !== 'none'`)으로 자체 사살.

---

## 4. 변이 시험 및 사살 내역 (40종 W1~W40)

`tools/test_c273_mutations.py`를 통해 4개 대상 파일에 대한 40종의 유효 컴파일 변이(W1~W40)를 순차 검증하였으며, 100% (40/40) 사살을 달성하였습니다.
- Batch 1 (W1~W8): `RiskBadge` 계약, 색상 충돌, low-contrast, fail-closed prototype 방어 (8/8 사살)
- Batch 2 (W9~W16): `RiskBadge` 폴백 및 렌더링, 테두리 충돌, ARIA 속성 보존 (8/8 사살)
- Batch 3 (W17~W24): `Button` primary/danger/secondary 색상 충돌 및 low-contrast, `baseStyle` `outline: 'none'` 포커스 링 억제 변이 W19 사살 (8/8 사살)
- Batch 4 (W25~W32): `Button` & `ExecutionResultView` 리터럴 회귀, 1:1 충돌, 성공 텍스트 불변식 (8/8 사살)
- Batch 5 (W33~W40): `WorkspaceCreateModal` & `RiskBadge` 리터럴 회귀, 백드롭 토큰, ARIA role (8/8 사살)

---

## 5. 게이트 검증 및 체크리스트

| 검증 단계 | 명령 및 대상 | 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| Vitest ACC-09 | `npx vitest run tests/acc09-contrast-tokens.test.tsx` | PASS (37 tests) | Card 273 신설 시험, 6개 토큰 대비, 미정의 가드 및 래칫 전수 통과 |
| Vitest Full Suite | `npx vitest run` (apps/web) | PASS (99 files, 1138 passed) | 0건 회귀, 100% 통과 |
| TypeScript Check | `node node_modules/typescript/bin/tsc -b` (apps/web) | PASS (exit code 0) | 타입 에러 0건 |
| Production Build | `npm run build` (apps/web) | PASS (exit code 0) | 번들 생성 완료 |
| Route Coverage | `pytest tests/test_route_coverage.py` | PASS (41 passed) | 백엔드 라우트 및 불변식 통과 |
| Frontend Integrity | `python -X utf8 tools/check_frontend_integrity.py` | PASS (0 violations) | 9대 무결성 규칙 100% 만족 |
| Contract Bindings | `python -X utf8 tools/check_contract_bindings.py` | PASS (exit code 0) | 55개 픽스처 전수 바인딩 |
| Contrast Reproduce | `python tools/reproduce_c273_contrast.py` | PASS (32 items) | 6개 신규 토큰 포함 Light/Dark 32종 전 항목 PASS |
| Mutation Test | `python tools/test_c273_mutations.py --all` | PASS (40/40 killed) | 100% 사살 실측 (W19 Button outline 변이 포함) |
| Git Diff Check | `git diff --check` | PASS (clean) | 공백/줄바꿈 이상 없음 |
| Check Docs Gate | `python tools/check_docs.py` | PASS (exit code 0) | 정본 문서 게이트 통과 |
| Sync Obsidian Gate | `python tools/sync_obsidian.py --check` | PASS (0 conflicts) | 동기화 충돌 0건 |
