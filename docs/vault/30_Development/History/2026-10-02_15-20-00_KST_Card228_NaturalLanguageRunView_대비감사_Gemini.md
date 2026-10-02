# 2026-10-02 15:20:00 KST — Card 228: 자연어 실행 화면 (NaturalLanguageRunView) 색상 리터럴 전수 토큰화(~70 occurrences→0), 상태 색 정합성 및 접근성 승격

## 1. 개요 및 변경 목적
- **작업 ID**: Card 228 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory)
- **대상 화면**: `apps/web/src/features/agent/NaturalLanguageRunView.tsx`
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: `agent/gemini/c228-nl-run-contrast`
- **기반 커밋 (Base)**: `46773e20` (PR #324 / Card 226 r2 최종 반영 head)
- **KST 시각**: 2026-10-02 15:20:00 KST

### 1.1 주요 작업 내역
1. **색상 리터럴 전수 해소 (~70 occurrences -> 0건)**:
   - `NaturalLanguageRunView.tsx`: 기존 하드코딩 색상 리터럴(Hex, RGBA) 전수를 `apps/web/src/index.css` 정본 디자인 토큰(`var(--color-...)`)으로 100% 치환.
   - 미노출 안내 배너(`agent-unexposed-notice`), 4대 KPI 카드, 액션 알림 배너(`agent-action-notice`), 프리셋 버튼, 자연어 폼 입력/textarea, Context 파일 선택 칩, 토큰/비용 프리뷰 박스, 제안 Diff 검토 패널 및 상태 배지(`agent-status-badge`) 전수 토큰화.
2. **상태 설정 객체 정립 및 비색상 식별 수단 100% 보존**:
   - `AGENT_RUN_STATUS_CONFIG` 최상단 정의 및 export: `draft`, `planning`, `evaluating`, `ready`, `running`, `executing`, `awaiting_approval`, `repairing`, `completed`, `rejected`, `failed`, `blocked`, `idle` 13개 상태 지원.
   - 상태별 고유 색상 및 비색상 기호/한글 레이블 부여: `planning`🧭, `evaluating`⏳, `ready`/`running`⚡, `awaiting_approval`⏸️, `repairing`🔄, `completed`✔, `rejected`🛑, `failed`❌, `blocked`🚫.
   - 수명주기 상태 간 고유성 및 대비 보장: `ready`(`var(--color-brand-hover)`), `repairing`(`var(--color-status-degraded)`), `completed`(`var(--color-status-online)`), `rejected`/`failed`/`blocked`(`var(--color-status-offline)`).
3. **Fail-Closed Own-Key 방어 체계 확립 (Codex F1 선제 적용)**:
   - `getAgentRunStatusConfig`: `Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)` own-key 검사 적용.
   - `toString`, `constructor`, `__proto__` 등 prototype key 또는 미정의 상태(`invalid_corrupted_state`) 입력 시 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)`로 fail-closed 매핑.
4. **키보드 접근성 및 포커스 링 보존 (비색상 동작 변경 금지)**:
   - Refine 버튼(`agent-refine-btn`) 및 제안 Diff/프리셋 버튼에 인라인 `outline: none/0` 억제 배제.
   - 전역 `:focus-visible` 링 보존 및 computed outline-style/width 단언(Test 9m)으로 `outline: 0` 및 `outline: none` 변이 사살.
5. **Fail-Closed Multiset Baseline 래칫 강제**:
   - `acc09-contrast-tokens.test.tsx`의 `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/agent/NaturalLanguageRunView.tsx`의 허용 인벤토리를 `{}` (0건)으로 전면 고정.

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 수치는 `python tools/reproduce_c228_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before (Hex/RGBA) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 미노출 공지 헤더 | notice header / surface | `#93c5fd on #161b22` | 9.59:1 / 9.59:1 | `--color-brand-hover` on `--color-bg-surface` | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 미노출 공지 본문 | notice text / surface | `#94a3b8 on #161b22` | 6.75:1 / 6.75:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 미노출 공지 테두리 | notice border / canvas | `#30363d on #0d1117` | 1.55:1 / 1.55:1 (FAIL) | `--color-border-subtle` on `--color-bg-canvas` | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| KPI 1 프롬프트 유효율 라벨 | kpi 1 label / surface | `#8b949e on #161b22` | 5.62:1 / 5.62:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| KPI 1 유효율 수치 | kpi 1 valid rate / surface | `#3fb950 on #161b22` | 6.81:1 / 6.81:1 | `--color-status-online` on `--color-bg-surface` | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| KPI 2 코딩 표준 준수율 라벨 | kpi 2 label / surface | `#8b949e on #161b22` | 5.62:1 / 5.62:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| KPI 2 준수율 수치 | kpi 2 coding rate / surface | `#3fb950 on #161b22` | 6.81:1 / 6.81:1 | `--color-status-online` on `--color-bg-surface` | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| KPI 3 샌드박스 유출 라벨 | kpi 3 label / surface | `#8b949e on #161b22` | 5.62:1 / 5.62:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| KPI 3 유출 0건 수치 | kpi 3 zero leaks / surface | `#3fb950 on #161b22` | 6.81:1 / 6.81:1 | `--color-status-online` on `--color-bg-surface` | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| KPI 3 유출 감지 수치 | kpi 3 leaks detected / surface | `#f85149 on #161b22` | 5.16:1 / 5.16:1 | `--color-status-offline` on `--color-bg-surface` | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| KPI 4 잔여 예산 라벨 | kpi 4 label / surface | `#8b949e on #161b22` | 5.62:1 / 5.62:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| KPI 4 잔여 예산 수치 | kpi 4 budget / surface | `#58a6ff on #161b22` | 6.85:1 / 6.85:1 | `--color-brand-hover` on `--color-bg-surface` | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| KPI 카드 테두리 | kpi card border / canvas | `#30363d on #0d1117` | 1.55:1 / 1.55:1 (FAIL) | `--color-border-subtle` on `--color-bg-canvas` | 3.33:1 | 4.08:1 | >= 3.0:1 | PASS |
| 액션 알림 에러 텍스트 | action notice error text / subtle | `#f85149 on rgba(248, 81, 73, 0.15)` | 4.85:1 / 4.85:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 액션 알림 성공 텍스트 | action notice success text / subtle | `#3fb950 on rgba(46, 160, 67, 0.15)` | 6.27:1 / 6.27:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 액션 알림 안내 텍스트 | action notice info text / subtle | `#58a6ff on rgba(56, 139, 253, 0.15)` | 6.26:1 / 6.26:1 | `--color-brand-hover` on `--color-bg-subtle` | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 프리셋 1 버튼 텍스트 | preset 1 button text / subtle | `#58a6ff on #0d1117` | 7.49:1 / 7.49:1 | `--color-brand-hover` on `--color-bg-subtle` | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 프리셋 2 버튼 텍스트 | preset 2 button text / subtle | `#f85149 on #0d1117` | 5.65:1 / 5.65:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 폼 라벨 자연어 목표 | form label objective / surface | `#8b949e on #161b22` | 5.62:1 / 5.62:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 폼 텍스트영역 텍스트 | form textarea text / subtle | `#c9d1d9 on #0d1117` | 12.26:1 / 12.26:1 | `--color-text-primary` on `--color-bg-subtle` | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| Context 태그 선택 상태 | context tag selected / subtle | `#58a6ff on rgba(56, 139, 253, 0.15)` | 5.65:1 / 5.65:1 | `--color-brand-hover` on `--color-bg-subtle` | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| Context 태그 비선택 상태 | context tag unselected / subtle | `#8b949e on #0d1117` | 6.15:1 / 6.15:1 | `--color-text-secondary` on `--color-bg-subtle` | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 토큰/비용 예상 토큰 | token cost preview tokens / subtle | `#f0f6fc on #0d1117` | 17.39:1 / 17.39:1 | `--color-text-primary` on `--color-bg-subtle` | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 토큰/비용 예상 비용 | token cost preview cost / subtle | `#3fb950 on #0d1117` | 7.45:1 / 7.45:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 상태 배지 READY | status badge ready / subtle | `#58a6ff on rgba(56, 139, 253, 0.2)` | 5.21:1 / 5.21:1 | `--color-brand-hover` on `--color-bg-subtle` | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 상태 배지 COMPLETED | status badge completed / subtle | `#3fb950 on rgba(46, 160, 67, 0.2)` | 5.22:1 / 5.22:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 상태 배지 REJECTED | status badge rejected / subtle | `#ff7b72 on rgba(248, 81, 73, 0.15)` | 5.82:1 / 5.82:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 상태 배지 UNKNOWN | status badge unknown / subtle | `#8b949e on #0d1117` | 6.15:1 / 6.15:1 | `--color-status-unknown` on `--color-bg-subtle` | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |

### 2.2 `python tools/reproduce_c228_contrast.py` 실제 실행 콘솔 출력
```text
==============================================================================================================
 CARD 228: NaturalLanguageRunView CONTRAST AUDIT (WCAG 2.2 AA)
==============================================================================================================
Item Description                       | Light Mode         | Dark Mode          | Min CR   | Status
--------------------------------------------------------------------------------------------------------------
notice header / surface                |  6.70:1 (OK)       |  9.84:1 (OK)       | >=4.5    | PASS
notice text / surface                  |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
notice border / canvas                 |  3.33:1 (OK)       |  4.08:1 (OK)       | >=3.0    | PASS
kpi 1 label / surface                  |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
kpi 1 valid rate / surface             |  5.02:1 (OK)       |  7.79:1 (OK)       | >=4.5    | PASS
kpi 2 label / surface                  |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
kpi 2 coding rate / surface            |  5.02:1 (OK)       |  7.79:1 (OK)       | >=4.5    | PASS
kpi 3 label / surface                  |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
kpi 3 zero leaks / surface             |  5.02:1 (OK)       |  7.79:1 (OK)       | >=4.5    | PASS
kpi 3 leaks detected / surface         |  6.47:1 (OK)       |  6.41:1 (OK)       | >=4.5    | PASS
kpi 4 label / surface                  |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
kpi 4 budget / surface                 |  6.70:1 (OK)       |  9.84:1 (OK)       | >=4.5    | PASS
kpi card border / canvas               |  3.33:1 (OK)       |  4.08:1 (OK)       | >=3.0    | PASS
action notice error text / subtle      |  5.91:1 (OK)       |  5.31:1 (OK)       | >=4.5    | PASS
action notice success text / subtle    |  4.58:1 (OK)       |  6.44:1 (OK)       | >=4.5    | PASS
action notice info text / subtle       |  6.12:1 (OK)       |  8.14:1 (OK)       | >=4.5    | PASS
preset 1 button text / subtle          |  6.12:1 (OK)       |  8.14:1 (OK)       | >=4.5    | PASS
preset 2 button text / subtle          |  5.91:1 (OK)       |  5.31:1 (OK)       | >=4.5    | PASS
form label objective / surface         |  7.58:1 (OK)       | 14.33:1 (OK)       | >=4.5    | PASS
form textarea text / subtle            | 16.30:1 (OK)       | 14.05:1 (OK)       | >=4.5    | PASS
context tag selected / subtle          |  6.12:1 (OK)       |  8.14:1 (OK)       | >=4.5    | PASS
context tag unselected / subtle        |  6.92:1 (OK)       | 11.86:1 (OK)       | >=4.5    | PASS
token cost preview tokens / subtle     | 16.30:1 (OK)       | 14.05:1 (OK)       | >=4.5    | PASS
token cost preview cost / subtle       |  4.58:1 (OK)       |  6.44:1 (OK)       | >=4.5    | PASS
status badge ready / subtle            |  6.12:1 (OK)       |  8.14:1 (OK)       | >=4.5    | PASS
status badge completed / subtle        |  4.58:1 (OK)       |  6.44:1 (OK)       | >=4.5    | PASS
status badge rejected / subtle         |  5.91:1 (OK)       |  5.31:1 (OK)       | >=4.5    | PASS
status badge unknown / subtle          |  6.47:1 (OK)       |  5.82:1 (OK)       | >=4.5    | PASS
--------------------------------------------------------------------------------------------------------------
Total Audit Items: 28 | Passed: 28 | Failed: 0

[SUCCESS] All 28 items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.
```

---

## 3. 정적 AST 검사 및 커버리지 래칫 (Test 9j-2)

- **Target File**: `features/agent/NaturalLanguageRunView.tsx`
- **Total Style Attributes**: `63` (100% 정합)
- **Checked Objects (Explicit style objects)**: `19`
- **Checked Pairs (Evaluated color-background pairings)**: `49`
- **Unbound Color Objects**: `27`
- **Covered Color Objects**: `46`
- **Checked Border Objects**: `26`
- **Checked Border Pairs**: `27`
- **Violations**: `[]` (0건)
- **Hardcoded Color Literal Residual**: `0건`

---

## 4. 변이 테스트 (18종 M1~M18 전원 사살 실측)

`python tools/test_c228_mutations.py` 실행 결과:
```text
================================================================================
 Card 228 (ACC-09): Reproducible Mutant Test Suite (18 Mutants: M1-M18)
 Target: NaturalLanguageRunView.tsx
================================================================================

[Baseline Check] Testing unmutated code...
[Baseline Check] Clean pass (exit code 0).

[01/18] M1 (A1): KILLED in 8.5s -- NaturalLanguageRunView: unexposed-notice text color -> bg-surface (fg==bg 1:1 collision)
         Reason: AssertionError: expected 'var(--color-bg-surface)' to be 'var(--color-text-primary)' /
[02/18] M2 (A2): KILLED in 10.1s -- NaturalLanguageRunView: AGENT_RUN_STATUS_CONFIG.completed.bg -> status-online (fg==bg collision)
         Reason: AssertionError: Agent status completed light text >= 4.5:1: expected 1 to be greater t
[03/18] M3 (A3): KILLED in 10.2s -- NaturalLanguageRunView: form textarea background -> text-primary (text token as bg)
         Reason: AssertionError: NaturalLanguageRunView violations:
[04/18] M4 (A4): KILLED in 10.7s -- NaturalLanguageRunView: KPI 1 container border -> bg-surface (border==bg collision)
         Reason: AssertionError: NaturalLanguageRunView violations:
[05/18] M5 (B1): KILLED in 11.8s -- NaturalLanguageRunView: refine button outline ring suppressed with outline: none
         Reason: AssertionError: Refine button must not suppress focus ring with outline-style none: ex
[06/18] M6 (B2): KILLED in 9.7s -- NaturalLanguageRunView: refine button outline ring suppressed with outline: 0 (Claude Low 1)
         Reason: AssertionError: Refine button must not suppress focus ring with outline-width 0: expec
[07/18] M7 (C1): KILLED in 9.8s -- NaturalLanguageRunView: status badge opacity degraded to 0.4
         Reason: AssertionError: Status badge must not have degraded opacity: expected '0.4' to be '1' 
[08/18] M8 (D1): KILLED in 10.8s -- NaturalLanguageRunView: KPI 1 valid rate color reverted to legacy literal #3fb950
         Reason: AssertionError: Evaluated pairs in NaturalLanguageRunView must be exactly 49: expected
[09/18] M9 (D2): KILLED in 9.1s -- NaturalLanguageRunView: action notice error border reverted to legacy literal #f85149
         Reason: AssertionError: expected 'var(--color-brand-hover)' to be 'var(--color-status-offline)
[10/18] M10 (D3): KILLED in 6.8s -- NaturalLanguageRunView: token/cost preview border reverted to legacy literal #30363d
         Reason: AssertionError: Border objects in NaturalLanguageRunView must be exactly 26: expected 
[11/18] M11 (F1): KILLED in 8.5s -- NaturalLanguageRunView: ready status color collapsed to rejected status-offline
         Reason: AssertionError: expected 'var(--color-status-offline)' to be 'var(--color-brand-hover)
[12/18] M12 (F2): KILLED in 8.4s -- NaturalLanguageRunView: completed status color collapsed to rejected status-offline
         Reason: AssertionError: expected 'var(--color-status-offline)' not to be 'var(--color-status-o
[13/18] M13 (G1): KILLED in 8.3s -- NaturalLanguageRunView: status badge icon element removed from DOM
         Reason: AssertionError: Status icon must render: expected null not to be null
[14/18] M14 (G2): KILLED in 10.0s -- NaturalLanguageRunView: status badge label element removed from DOM
         Reason: AssertionError: expected '⚡' to contain 'READY'
[15/18] M15 (H1): KILLED in 9.6s -- NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns completed config (fail-closed bypass)
         Reason: AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-unknow
[16/18] M16 (H2): KILLED in 8.1s -- NaturalLanguageRunView: getAgentRunStatusConfig uses prototype-inclusive in operator (Codex F1)
         Reason: AssertionError: expected undefined to be 'var(--color-status-unknown)' // Object.is eq
[17/18] M17 (I1): KILLED in 8.2s -- NaturalLanguageRunView: preset 1 button color injected with named color lightgray
         Reason: AssertionError: Explicit style objects in NaturalLanguageRunView must be exactly 19: e
[18/18] M18 (I2): KILLED in 7.6s -- NaturalLanguageRunView: unexposed notice title injected with comment decoy and literal
         Reason: AssertionError: Evaluated pairs in NaturalLanguageRunView must be exactly 49: expected

================================================================================
 Summary: 18/18 mutants killed (100.0%)
================================================================================
 [PASS] KILLED    | NaturalLanguageRunView: unexposed-notice text color -> bg-surface (fg==bg 1:1 collision)
 [PASS] KILLED    | NaturalLanguageRunView: AGENT_RUN_STATUS_CONFIG.completed.bg -> status-online (fg==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: form textarea background -> text-primary (text token as bg)
 [PASS] KILLED    | NaturalLanguageRunView: KPI 1 container border -> bg-surface (border==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: refine button outline ring suppressed with outline: none
 [PASS] KILLED    | NaturalLanguageRunView: refine button outline ring suppressed with outline: 0 (Claude Low 1)
 [PASS] KILLED    | NaturalLanguageRunView: status badge opacity degraded to 0.4
 [PASS] KILLED    | NaturalLanguageRunView: KPI 1 valid rate color reverted to legacy literal #3fb950
 [PASS] KILLED    | NaturalLanguageRunView: action notice error border reverted to legacy literal #f85149
 [PASS] KILLED    | NaturalLanguageRunView: token/cost preview border reverted to legacy literal #30363d
 [PASS] KILLED    | NaturalLanguageRunView: ready status color collapsed to rejected status-offline
 [PASS] KILLED    | NaturalLanguageRunView: completed status color collapsed to rejected status-offline
 [PASS] KILLED    | NaturalLanguageRunView: status badge icon element removed from DOM
 [PASS] KILLED    | NaturalLanguageRunView: status badge label element removed from DOM
 [PASS] KILLED    | NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns completed config (fail-closed bypass)
 [PASS] KILLED    | NaturalLanguageRunView: getAgentRunStatusConfig uses prototype-inclusive in operator (Codex F1)
 [PASS] KILLED    | NaturalLanguageRunView: preset 1 button color injected with named color lightgray
 [PASS] KILLED    | NaturalLanguageRunView: unexposed notice title injected with comment decoy and literal

SUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.
```

---

## 5. 검증 요약
| 검증 항목 | 실행 명령 | 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| Vitest ACC-09 스위트 | `npx vitest run tests/acc09-contrast-tokens.test.tsx` | **30 passed (100%)** | Test 9m DOM 결속, Test 9j-2 AST 래칫, Probe 86~90 전수 통과 |
| Vitest 자연어 실행 단위시험 | `npx vitest run tests/natural-language-run-view.test.tsx` | **8 passed (100%)** | Bounded repair 루프 및 거절 전환 동작 불변식 100% 통과 |
| S11 결함 회귀 스위트 | `npx vitest run tests/s11-defect-fixes.test.tsx` | **16 passed (100%)** | DEF-S11-09 버튼 토큰 검증 통과 |
| 타입스크립트 정적 검사 | `npx tsc -b` | **0 errors (Exit Code 0)** | Strict types 100% 충족 |
| 프로덕션 번들 빌드 | `npm run build` | **Build Success (Exit Code 0)** | Vite 프로덕션 번들 정상 생성 (dist) |
| 라우트 커버리지 및 무결성 | `pytest tests/test_route_coverage.py` | **41 passed (100%)** | 불변식 및 라우트 계약 일치 |
| 프런트엔드 무결성 가드 | `python -X utf8 tools/check_frontend_integrity.py` | **0 violations (Exit Code 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 검사 | `python -X utf8 tools/check_contract_bindings.py` | **PASS (Exit Code 0)** | 55 fixtures, 20 types 커버리지 |
| 문서 검사 도구 | `python tools/check_docs.py` | **PASS (Exit Code 0)** | 1081 docs, link, DAG 무결성 |
| 명도 대비 동적 재현 | `python tools/reproduce_c228_contrast.py` | **28/28 passed (Exit Code 0)** | Light/Dark 전수 WCAG AA 충족 |
| 뮤테이션 테스트 스위트 | `python tools/test_c228_mutations.py` | **18/18 killed (100.0%)** | M1~M18 전원 사살 실측 |
