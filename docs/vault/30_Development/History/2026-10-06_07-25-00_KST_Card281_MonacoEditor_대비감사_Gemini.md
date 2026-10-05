---
doc_id: "HIST-20261006-CARD281-GEMINI"
title: "Card 281 Monaco 에디터 화면 색상 리터럴 전수 토큰화 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-06T07:25:00+09:00"
updated: "2026-10-06T07:25:00+09:00"
source_of_truth: "Git"
---

# Card 281 Monaco 에디터 화면 색상 리터럴 전수 토큰화 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 에디터 핵심 컴포넌트인 `MonacoWorkspaceEditor.tsx`에 잔존하던 86 occurrences / 29 distinct 색상 리터럴 전수 토큰화(86건→0건), 상태 계약 무결성 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/editor/MonacoWorkspaceEditor.tsx`: 베이스(`4fed3dca`, Card 280 Commit C)에 잔존하던 86 occurrences / 29 distinct 색상 리터럴 (`#070a0e`: 1, `#090d13`: 3, `#0d1117`: 4, `#161b22`: 4, `#1f242c`: 1, `#21262d`: 6, `#2ea043`: 1, `#30363d`: 7, `#3fb950`: 4, `#484f58`: 2, `#58a6ff`: 9, `#79c0ff`: 1, `#8b949e`: 9, `#c9d1d9`: 6, `#e3b341`: 6, `#f0f6fc`: 5, `#f85149`: 3, plus multiple rgba literals) 전수 제거 및 디자인 토큰 전면 승격 (86건→0건).
  2. **Monaco 에디터 구현 구조 및 테마 아키텍처 정합성**:
     - `MonacoWorkspaceEditor.tsx`는 파일명에 Monaco가 포함되어 있으나, 내부 구현은 React JSX 기반의 인메모리 커스텀 에디터(custom gutter row, line numbering, textarea, Myers diff visualizer, embedded terminal emulator)로 구현되어 있습니다.
     - 코드베이스 전반에 걸쳐 `monaco-editor` npm 패키지 의존성이나 `editor.defineTheme` API 호출이 존재하지 않으며, 모든 에디터/터미널/거터 UI 요소는 JSX 인라인 스타일의 CSS 변수 `var(--color-...)`를 직접 참조하여 렌더링됩니다.
     - 따라서 테마 동기화는 별도의 Monaco Theme JSON 없이 `apps/web/src/index.css`의 CSS 변수 체계에 완전히 종속되며, 라이트/다크 테마 전환 시 DOM 레벨에서 CSS 변수가 즉각 재계산되어 일관된 대비를 보장합니다.
  3. **Fail-Closed 상태 계약 체계 확립**:
     - `WorkspaceTerminalStatus` ('connected' | 'recovered' | 'reconnecting' | 'disconnected')를 엄밀히 지원하는 `WORKSPACE_TERMINAL_STATUS_CONFIG satisfies Record<WorkspaceTerminalStatus, WorkspaceTerminalStatusConfigItem>` 설정 표 구축.
     - `getWorkspaceTerminalStatusConfig` 헬퍼 함수에 `Object.hasOwn` 기반 fail-closed 룩업을 강제하여 `toString`, `constructor`, `__proto__`, `valueOf` 등 프로토타입 오염 공격 및 계약 외 미등록 상태를 `UNKNOWN (<key>)` 및 `var(--color-status-unknown)` 토큰으로 안전 강등하도록 봉인.
  4. **명도 대비 및 접근성 규격 승격 (WCAG 2.2 AA SC 1.4.3 & SC 1.4.11)**:
     - `--color-brand-subtle` (`#dbeafe` / `#1e293b`) 배경 위 텍스트는 4.24:1로 WCAG 4.5:1 기준을 미달하는 `--color-brand-primary` 대신 `--color-brand-hover` (`#1d4ed8` / `#93c5fd`)를 채택하여 라이트 5.49:1, 다크 8.11:1 (>= 4.5:1 PASS) 달성.
     - 경계선(border)은 `--color-brand-primary`를 사용하여 라이트 4.24:1, 다크 5.75:1 (>= 3.0:1 PASS) 달성.
     - 에디터 거터, 터미널 툴바, 탭 바, 탐색기 사이드바, 동결 스냅샷 배너 등 69개 감사 항목 전수 WCAG 2.2 AA 충족 (PASS: 54, INFO: 15, FAIL: 0).
  5. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `MonacoWorkspaceEditor.tsx` 등록:
       - totalStyleAttrs: 69, checkedObjects: 15, checkedPairs: 42, unboundColorObjects: 26, coveredColorObjects: 41, checkedBorderObjects: 21, checkedBorderPairs: 22, violations: 0.
  6. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/editor/MonacoWorkspaceEditor.tsx: {}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 484건, 35개 파일 래칫 보존 (Test 10 통과).
  7. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9ae 신설: `MonacoWorkspaceEditor` 컴포넌트 렌더링, 색상 토큰 바인딩, 동적 명도 대비 계산, 프로토타입 오염 격리 전수 단언.
     - Revert-Fail Probes 161~165 신설: 베이스의 결함 조합이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  8. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c281_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A `e425e4ff` 기반, Commit B `e5e01958` 봉인, 바이너리 read_bytes/write_bytes 복원 및 fail-closed clean-tree 무결성 검증 통과).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `4fed3dca`(Card 280 Commit C)의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba` 및 실제 조상 underlay를 적용하여 산출하였습니다. After 값은 `python tools/reproduce_c281_contrast.py` 실행 결과(69개 전 항목)와 100% 일치합니다.

| ID | 항목 명칭 | 역할 | 적용 토큰 | 라이트 대비 | 다크 대비 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| MWE-1 | Root editor container | fill | --color-bg-canvas | 1.00:1 | 1.00:1 | INFO |
| MWE-2 | Root editor boundary border | boundary | --color-border-subtle | 3.33:1 | 4.08:1 | PASS |
| MWE-3 | Root editor base text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| MWE-4 | Unexposed notice connected background | fill | --color-diff-added-bg | 1.05:1 | 1.30:1 | INFO |
| MWE-5 | Unexposed notice connected border | boundary | --color-diff-added-border | 3.00:1 | 6.54:1 | PASS |
| MWE-6 | Unexposed notice connected text | text | --color-status-online | 4.57:1 | 6.54:1 | PASS |
| MWE-7 | Unexposed notice unconnected background | fill | --color-brand-subtle | 1.17:1 | 1.33:1 | INFO |
| MWE-8 | Unexposed notice unconnected border | boundary | --color-brand-primary | 4.24:1 | 5.75:1 | PASS |
| MWE-9 | Unexposed notice unconnected text | text | --color-brand-hover | 5.49:1 | 8.11:1 | PASS |
| MWE-10 | Save error banner background | fill | --color-risk-l3-bg | 1.17:1 | 1.19:1 | INFO |
| MWE-11 | Save error banner border | boundary | --color-risk-l3-border | 5.30:1 | 5.90:1 | PASS |
| MWE-12 | Save error banner text | text | --color-status-offline | 5.30:1 | 5.90:1 | PASS |
| MWE-13 | Save warning notice background | fill | --color-bg-subtle | 1.05:1 | 1.32:1 | INFO |
| MWE-14 | Save warning notice border | boundary | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-15 | Save warning notice text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-16 | Save success notice background | fill | --color-diff-added-bg | 1.05:1 | 1.30:1 | INFO |
| MWE-17 | Save success notice border | boundary | --color-diff-added-border | 3.00:1 | 6.54:1 | PASS |
| MWE-18 | Save success notice text | text | --color-status-online | 4.57:1 | 6.54:1 | PASS |
| MWE-19 | Top main toolbar background | fill | --color-bg-surface | 1.05:1 | 1.10:1 | INFO |
| MWE-20 | Top main toolbar border | boundary | --color-border-subtle | 3.48:1 | 3.73:1 | PASS |
| MWE-21 | Top main toolbar workspace label | text | --color-text-primary | 17.85:1 | 16.98:1 | PASS |
| MWE-22 | Top main toolbar workspace ID code | text | --color-brand-hover | 6.70:1 | 9.84:1 | PASS |
| MWE-23 | Top main toolbar simulate conflict label | text | --color-text-muted | 5.75:1 | 6.99:1 | PASS |
| MWE-24 | Explorer sidebar background | fill | --color-bg-canvas | 1.00:1 | 1.00:1 | INFO |
| MWE-25 | Explorer sidebar border | boundary | --color-border-subtle | 3.33:1 | 4.08:1 | PASS |
| MWE-26 | Explorer header label | text | --color-text-muted | 5.50:1 | 7.65:1 | PASS |
| MWE-27 | Explorer inactive file item text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| MWE-28 | Explorer active file item background | fill | --color-brand-subtle | 1.17:1 | 1.33:1 | INFO |
| MWE-29 | Explorer active file item text | text | --color-brand-hover | 5.49:1 | 8.11:1 | PASS |
| MWE-30 | Explorer dirty file indicator dot | text | --color-brand-warning | 5.81:1 | 6.81:1 | PASS |
| MWE-31 | Explorer Git summary commit ID | text | --color-brand-hover | 6.41:1 | 10.78:1 | PASS |
| MWE-32 | Explorer Git summary commit message | text | --color-text-secondary | 7.24:1 | 15.69:1 | PASS |
| MWE-33 | Frozen snapshot banner background | fill | --color-brand-subtle | 1.17:1 | 1.33:1 | INFO |
| MWE-34 | Frozen snapshot banner border | boundary | --color-brand-primary | 4.24:1 | 5.75:1 | PASS |
| MWE-35 | Frozen snapshot banner title | text | --color-brand-hover | 5.49:1 | 8.11:1 | PASS |
| MWE-36 | Frozen snapshot banner attempt text | text | --color-text-secondary | 6.21:1 | 11.82:1 | PASS |
| MWE-37 | Frozen snapshot read-only badge background | fill | --color-bg-subtle | 1.10:1 | 1.21:1 | INFO |
| MWE-38 | Frozen snapshot read-only badge border | boundary | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-39 | Frozen snapshot read-only badge text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-40 | Editor line number gutter background | fill | --color-bg-subtle | 1.05:1 | 1.32:1 | INFO |
| MWE-41 | Editor line number gutter border | boundary | --color-border-subtle | 3.18:1 | 3.08:1 | PASS |
| MWE-42 | Editor line number gutter text | text | --color-text-muted | 5.25:1 | 5.78:1 | PASS |
| MWE-43 | Frozen snapshot textarea text | text | --color-text-secondary | 7.24:1 | 15.69:1 | PASS |
| MWE-44 | Normal editor tab bar background | fill | --color-bg-surface | 1.05:1 | 1.10:1 | INFO |
| MWE-45 | Normal editor tab bar border | boundary | --color-border-subtle | 3.48:1 | 3.73:1 | PASS |
| MWE-46 | Normal editor tab active file text | text | --color-text-primary | 17.85:1 | 16.98:1 | PASS |
| MWE-47 | Normal editor tab modified text | text | --color-status-degraded | 5.02:1 | 8.26:1 | PASS |
| MWE-48 | Normal editor code textarea text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| MWE-49 | Terminal container border | boundary | --color-border-subtle | 3.33:1 | 4.08:1 | PASS |
| MWE-50 | Terminal title bar background | fill | --color-bg-surface | 1.05:1 | 1.10:1 | INFO |
| MWE-51 | Terminal title bar border | boundary | --color-border-subtle | 3.48:1 | 3.73:1 | PASS |
| MWE-52 | Terminal title text | text | --color-text-primary | 17.85:1 | 16.98:1 | PASS |
| MWE-53 | Terminal mock notice text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-54 | Terminal mock notice border | boundary | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-55 | Terminal status connected text | text | --color-status-online | 4.57:1 | 6.54:1 | PASS |
| MWE-56 | Terminal status connected border | boundary | --color-diff-added-border | 3.00:1 | 6.54:1 | PASS |
| MWE-57 | Terminal status recovered text | text | --color-brand-hover | 5.49:1 | 8.11:1 | PASS |
| MWE-58 | Terminal status recovered border | boundary | --color-brand-primary | 4.24:1 | 5.75:1 | PASS |
| MWE-59 | Terminal status reconnecting text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| MWE-60 | Terminal status disconnected text | text | --color-status-offline | 5.30:1 | 5.90:1 | PASS |
| MWE-61 | Terminal status disconnected border | boundary | --color-risk-l3-border | 5.30:1 | 5.90:1 | PASS |
| MWE-62 | Terminal prompt command text | text | --color-brand-primary | 4.94:1 | 7.64:1 | PASS |
| MWE-63 | Terminal command output text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| MWE-64 | Terminal resume report background | fill | --color-brand-subtle | 1.17:1 | 1.33:1 | INFO |
| MWE-65 | Terminal resume report accent border | boundary | --color-brand-primary | 4.24:1 | 5.75:1 | PASS |
| MWE-66 | Terminal resume report text | text | --color-text-primary | 14.63:1 | 14.00:1 | PASS |
| MWE-67 | Terminal resume report code text | text | --color-brand-hover | 5.49:1 | 8.11:1 | PASS |
| MWE-68 | Terminal command form prompt $ symbol | text | --color-status-online | 4.79:1 | 8.53:1 | PASS |
| MWE-69 | Terminal command form input text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |

---

## 2.2 독립 재현 검증 스크립트 실행 결과 (`reproduce_c281_contrast.py`)

```text
Machine verification: All 19 token declarations match apps/web/src/index.css exactly.
================================================================================
ACC-09 Card 281: MonacoWorkspaceEditor Contrast Audit Table
================================================================================
ID      | Element                             | Role     | Token                     | Light CR  | Dark CR   | Status
-------------------------------------------------------------------------------------------------------------------
MWE-1   | Root editor container               | fill     | --color-bg-canvas         |   1.00:1  |   1.00:1  | INFO
MWE-2   | Root editor boundary border         | boundary | --color-border-subtle     |   3.33:1  |   4.08:1  | PASS
MWE-3   | Root editor base text               | text     | --color-text-primary      |  17.06:1  |  18.59:1  | PASS
MWE-4   | Unexposed notice connected background | fill     | --color-diff-added-bg     |   1.05:1  |   1.30:1  | INFO
MWE-5   | Unexposed notice connected border   | boundary | --color-diff-added-border |   3.00:1  |   6.54:1  | PASS
MWE-6   | Unexposed notice connected text     | text     | --color-status-online     |   4.57:1  |   6.54:1  | PASS
MWE-7   | Unexposed notice unconnected background | fill     | --color-brand-subtle      |   1.17:1  |   1.33:1  | INFO
MWE-8   | Unexposed notice unconnected border | boundary | --color-brand-primary     |   4.24:1  |   5.75:1  | PASS
MWE-9   | Unexposed notice unconnected text   | text     | --color-brand-hover       |   5.49:1  |   8.11:1  | PASS
MWE-10  | Save error banner background        | fill     | --color-risk-l3-bg        |   1.17:1  |   1.19:1  | INFO
MWE-11  | Save error banner border            | boundary | --color-risk-l3-border    |   5.30:1  |   5.90:1  | PASS
MWE-12  | Save error banner text              | text     | --color-status-offline    |   5.30:1  |   5.90:1  | PASS
MWE-13  | Save warning notice background      | fill     | --color-bg-subtle         |   1.05:1  |   1.32:1  | INFO
MWE-14  | Save warning notice border          | boundary | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-15  | Save warning notice text            | text     | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-16  | Save success notice background      | fill     | --color-diff-added-bg     |   1.05:1  |   1.30:1  | INFO
MWE-17  | Save success notice border          | boundary | --color-diff-added-border |   3.00:1  |   6.54:1  | PASS
MWE-18  | Save success notice text            | text     | --color-status-online     |   4.57:1  |   6.54:1  | PASS
MWE-19  | Top main toolbar background         | fill     | --color-bg-surface        |   1.05:1  |   1.10:1  | INFO
MWE-20  | Top main toolbar border             | boundary | --color-border-subtle     |   3.48:1  |   3.73:1  | PASS
MWE-21  | Top main toolbar workspace label    | text     | --color-text-primary      |  17.85:1  |  16.98:1  | PASS
MWE-22  | Top main toolbar workspace ID code  | text     | --color-brand-hover       |   6.70:1  |   9.84:1  | PASS
MWE-23  | Top main toolbar simulate conflict label | text     | --color-text-muted        |   5.75:1  |   6.99:1  | PASS
MWE-24  | Explorer sidebar background         | fill     | --color-bg-canvas         |   1.00:1  |   1.00:1  | INFO
MWE-25  | Explorer sidebar border             | boundary | --color-border-subtle     |   3.33:1  |   4.08:1  | PASS
MWE-26  | Explorer header label               | text     | --color-text-muted        |   5.50:1  |   7.65:1  | PASS
MWE-27  | Explorer inactive file item text    | text     | --color-text-primary      |  17.06:1  |  18.59:1  | PASS
MWE-28  | Explorer active file item background | fill     | --color-brand-subtle      |   1.17:1  |   1.33:1  | INFO
MWE-29  | Explorer active file item text      | text     | --color-brand-hover       |   5.49:1  |   8.11:1  | PASS
MWE-30  | Explorer dirty file indicator dot   | text     | --color-brand-warning     |   5.81:1  |   6.81:1  | PASS
MWE-31  | Explorer Git summary commit ID      | text     | --color-brand-hover       |   6.41:1  |  10.78:1  | PASS
MWE-32  | Explorer Git summary commit message | text     | --color-text-secondary    |   7.24:1  |  15.69:1  | PASS
MWE-33  | Frozen snapshot banner background   | fill     | --color-brand-subtle      |   1.17:1  |   1.33:1  | INFO
MWE-34  | Frozen snapshot banner border       | boundary | --color-brand-primary     |   4.24:1  |   5.75:1  | PASS
MWE-35  | Frozen snapshot banner title        | text     | --color-brand-hover       |   5.49:1  |   8.11:1  | PASS
MWE-36  | Frozen snapshot banner attempt text | text     | --color-text-secondary    |   6.21:1  |  11.82:1  | PASS
MWE-37  | Frozen snapshot read-only badge background | fill     | --color-bg-subtle         |   1.10:1  |   1.21:1  | INFO
MWE-38  | Frozen snapshot read-only badge border | boundary | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-39  | Frozen snapshot read-only badge text | text     | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-40  | Editor line number gutter background | fill     | --color-bg-subtle         |   1.05:1  |   1.32:1  | INFO
MWE-41  | Editor line number gutter border    | boundary | --color-border-subtle     |   3.18:1  |   3.08:1  | PASS
MWE-42  | Editor line number gutter text      | text     | --color-text-muted        |   5.25:1  |   5.78:1  | PASS
MWE-43  | Frozen snapshot textarea text       | text     | --color-text-secondary    |   7.24:1  |  15.69:1  | PASS
MWE-44  | Normal editor tab bar background    | fill     | --color-bg-surface        |   1.05:1  |   1.10:1  | INFO
MWE-45  | Normal editor tab bar border        | boundary | --color-border-subtle     |   3.48:1  |   3.73:1  | PASS
MWE-46  | Normal editor tab active file text  | text     | --color-text-primary      |  17.85:1  |  16.98:1  | PASS
MWE-47  | Normal editor tab modified text     | text     | --color-status-degraded   |   5.02:1  |   8.26:1  | PASS
MWE-48  | Normal editor code textarea text    | text     | --color-text-primary      |  17.06:1  |  18.59:1  | PASS
MWE-49  | Terminal container border           | boundary | --color-border-subtle     |   3.33:1  |   4.08:1  | PASS
MWE-50  | Terminal title bar background       | fill     | --color-bg-surface        |   1.05:1  |   1.10:1  | INFO
MWE-51  | Terminal title bar border           | boundary | --color-border-subtle     |   3.48:1  |   3.73:1  | PASS
MWE-52  | Terminal title text                 | text     | --color-text-primary      |  17.85:1  |  16.98:1  | PASS
MWE-53  | Terminal mock notice text           | text     | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-54  | Terminal mock notice border         | boundary | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-55  | Terminal status connected text      | text     | --color-status-online     |   4.57:1  |   6.54:1  | PASS
MWE-56  | Terminal status connected border    | boundary | --color-diff-added-border |   3.00:1  |   6.54:1  | PASS
MWE-57  | Terminal status recovered text      | text     | --color-brand-hover       |   5.49:1  |   8.11:1  | PASS
MWE-58  | Terminal status recovered border    | boundary | --color-brand-primary     |   4.24:1  |   5.75:1  | PASS
MWE-59  | Terminal status reconnecting text   | text     | --color-status-degraded   |   4.58:1  |   6.83:1  | PASS
MWE-60  | Terminal status disconnected text   | text     | --color-status-offline    |   5.30:1  |   5.90:1  | PASS
MWE-61  | Terminal status disconnected border | boundary | --color-risk-l3-border    |   5.30:1  |   5.90:1  | PASS
MWE-62  | Terminal prompt command text        | text     | --color-brand-primary     |   4.94:1  |   7.64:1  | PASS
MWE-63  | Terminal command output text        | text     | --color-text-primary      |  17.06:1  |  18.59:1  | PASS
MWE-64  | Terminal resume report background   | fill     | --color-brand-subtle      |   1.17:1  |   1.33:1  | INFO
MWE-65  | Terminal resume report accent border | boundary | --color-brand-primary     |   4.24:1  |   5.75:1  | PASS
MWE-66  | Terminal resume report text         | text     | --color-text-primary      |  14.63:1  |  14.00:1  | PASS
MWE-67  | Terminal resume report code text    | text     | --color-brand-hover       |   5.49:1  |   8.11:1  | PASS
MWE-68  | Terminal command form prompt $ symbol | text     | --color-status-online     |   4.79:1  |   8.53:1  | PASS
MWE-69  | Terminal command form input text    | text     | --color-text-primary      |  17.06:1  |  18.59:1  | PASS
-------------------------------------------------------------------------------------------------------------------
Summary: 69 items evaluated.
  PASS: 54 (all WCAG SC 1.4.3 & SC 1.4.11 criteria met)
  INFO: 15 (non-boundary fills / surface backgrounds)
  FAIL: 0
SUCCESS: Card 281 MonacoWorkspaceEditor contrast reproduction 100% verified.
```

---

## 3. 기술적 판단 및 설계 정합성

### 3.1 MonacoWorkspaceEditor의 React JSX 인라인 스타일링과 Monaco Theme API
- `MonacoWorkspaceEditor.tsx`는 외부 monaco-editor 번들을 주입받는 웹뷰가 아니며, 순수 React JSX 기반으로 줄 번호 거터, Myers diff 알고리즘 기반 변경점 하이라이트, 그리고 가상 터미널 뷰를 렌더링하는 인메모리 에디터입니다.
- 따라서 `monaco.editor.defineTheme` API 대신 `apps/web/src/index.css`의 표준 CSS 커스텀 프로퍼티(`var(--color-...)`) 체계를 직접 소비하여 라이트/다크 테마 및 시스템 고대비 모드와 완벽하게 동기화됩니다.

### 3.2 brand-subtle 배경 위 brand-hover 텍스트 및 brand-primary 테두리 채택 근거
- `--color-brand-subtle` (`#dbeafe` / `#1e293b`) 배경 위에서 기본 브랜드 색상인 `--color-brand-primary` (`#2563eb`)는 라이트 모드에서 4.24:1의 대비를 보여 SC 1.4.3 텍스트 기준(4.5:1)을 미달합니다.
- 이에 따라 텍스트 요소에는 더 깊은 명도를 제공하는 `--color-brand-hover` (`#1d4ed8` 라이트 / `#93c5fd` 다크)를 적용하여 라이트 5.49:1, 다크 8.11:1의 넉넉한 텍스트 대비를 확보하였습니다.
- 반면 경계선(boundary) 요소는 SC 1.4.11(Non-text Contrast >= 3.0:1)이 적용되므로, `--color-brand-primary`를 사용하여 라이트 4.24:1, 다크 5.75:1로 규격을 완벽하게 충족하도록 정합하였습니다.

### 3.3 Fail-Closed 터미널 연결 상태 룩업 및 프로토타입 오염 방어
- 에디터 내장 터미널의 상태 룩업 헬퍼인 `getWorkspaceTerminalStatusConfig`는 단순 `in` 연산자나 객체 속성 직접 접근 대신 `Object.hasOwn(WORKSPACE_TERMINAL_STATUS_CONFIG, status)`를 강제하여, `toString`, `constructor`, `__proto__`, `valueOf` 등 프로토타입 오염 키나 계약 외 미등록 상태를 `UNKNOWN (<key>)` 및 `var(--color-status-unknown)` 토큰으로 안전 강등하도록 봉인되었습니다 (변이 M39, M40 100% 사살).

---

## 4. 증거 및 검증 결과 (Evidence & Verification)
- `python tools/reproduce_c281_contrast.py` -> 69/69 PASS/INFO (0 failures).
- `cd apps/web && npx tsc -b` -> exit code 0, 0 errors.
- `npm run build` -> exit code 0, production bundle generated.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx` -> 45/45 PASS.
- `pytest tests/test_route_coverage.py` -> 41/41 PASS.
- `python tools/check_frontend_integrity.py` -> PASS (9대 무결성 규칙 위반 0건).
- `python tools/check_contract_bindings.py` -> PASS.
- `python tools/check_docs.py` -> PASS.
- `python tools/check_doc_path_citations.py --ratchet --base-ref 4fed3dca` -> PASS.
- `python tools/sync_obsidian.py --check` -> PASS (0 conflicts).
- `tools/test_c281_mutations.py` -> 40/40 KILLED on clean commit A (`e425e4ff`), sealed in Commit B (`e5e01958`) with byte-clean restore verification.
