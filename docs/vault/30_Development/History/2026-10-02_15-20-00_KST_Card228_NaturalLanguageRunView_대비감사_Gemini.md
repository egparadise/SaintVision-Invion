# 2026-10-02 15:20:00 KST — Card 228: 자연어 실행 화면 (NaturalLanguageRunView) 색상 리터럴 전수 토큰화(18종/79건→0), 상태 색 정합성 및 접근성 승격 [r2]

## 1. 개요 및 변경 목적
- **작업 ID**: Card 228 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory)
- **대상 화면**: `apps/web/src/features/agent/NaturalLanguageRunView.tsx`
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: `agent/gemini/c228-nl-run-contrast` (PR #325)
- **기반 커밋 (Base)**: `02d5f969` (PR #324 / Card 226 r3 최종 반영 head 머지 `f27223df`)
- **KST 시각**: 2026-10-02 15:20:00 KST (r2 갱신 시각: 2026-10-02 16:25:00 KST)

### 1.1 주요 작업 내역
1. **색상 리터럴 전수 해소 (18종 / 79건 -> 0건)**:
   - `NaturalLanguageRunView.tsx`: 기존 하드코딩 색상 리터럴(Hex, RGBA 18종 79건) 전수를 `apps/web/src/index.css` 정본 디자인 토큰(`var(--color-...)`)으로 100% 치환.
   - 미노출 안내 배너(`agent-unexposed-notice`), 4대 KPI 카드, 액션 알림 배너(`agent-action-notice`), 프리셋 버튼, 자연어 폼 입력/textarea, Context 파일 선택 칩, 토큰/비용 프리뷰 박스, 제안 Diff 검토 패널 및 상태 배지(`agent-status-badge`) 전수 토큰화.
2. **Wire 계약 Enum 일치 및 상태 설정 객체 정립 (F-R1, Codex r1 지적 해소)**:
   - `apps/web/src/contracts/types.ts:420` 정본 wire 계약(`AgentRunRequest['status']`)과 `AGENT_RUN_STATUS_CONFIG`의 key set을 100% 일치: `draft`, `evaluating`, `ready`, `repairing`, `completed`, `rejected` 정확히 6개 상태로 한정.
   - 계약 외 임의 상태 7종(`planning`, `running`, `executing`, `awaiting_approval`, `failed`, `blocked`, `idle`)을 config 테이블에서 전면 제거하고 known 부당 승격 차단.
   - `expect(Object.keys(AGENT_RUN_STATUS_CONFIG).sort()).toEqual(['completed', 'draft', 'evaluating', 'ready', 'rejected', 'repairing'])` 불변식 고정.
3. **비색상 동작 및 배지 공개 계약 100% 복원 (F-R2, Claude UI r1 / Codex r1 지적 해소)**:
   - 형제 테스트 `tests/node-fetch-error-workspace-wiring.test.tsx:360` hosted frontend 실패 원인이었던 상태 배지 아이콘/한글 복합 DOM(`⚡준비 완료 (READY)`)을 wire 상태 대문자 원문(`READY`, `REPAIRING`, `COMPLETED`, `REJECTED`) 단일 span 렌더로 완전 복원.
   - `natural-language-run-view.test.tsx`의 exact equality(`toBe('COMPLETED')`, `toBe('READY')`) 회귀 복원 및 8/8 통과, 형제 배선 시험 10/10 전수 통과 실측.
4. **Fail-Closed Own-Key 방어 체계 확립 (Codex F1 선제 적용 및 X29 사살)**:
   - `getAgentRunStatusConfig`: `Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)` own-key 검사 적용.
   - 계약 밖 7개 값, 임의 미지 상태(`invalid_corrupted_state`, `bogus`), prototype key(`toString`, `constructor`, `__proto__`) 및 null/''/undefined 입력 시 `var(--color-status-unknown)` 및 `UNKNOWN` / 대문자 원문으로 fail-closed 격리.
5. **키보드 접근성 및 포커스 링 보존 (F9, F10)**:
   - Refine 버튼(`agent-refine-btn`)에 computed outline-style/width 단언 및 인라인 outline none/0 검사 적용. 프리셋 및 Diff 버튼은 정적 inline-outline 및 AST 규칙으로 보호.
   - AST 검사기에서 `ts.isAsExpression` (`outline: 'none' as const`, X25) unwrapping 지원으로 포커스 링 억제 우회 원천 차단.
6. **AST 가드 조건식 양 분기 평가 (Claude UI High 해소)**:
   - `traverseJsx` AST 분석기가 조건식 style(`actionNotice ? { ... } : undefined`)의 양쪽 분기를 재귀 평가하도록 확장하여 X3, X7, X10, X32 변이를 100% 포착 및 사살.
7. **실측 캔버스 합성 반영 및 Repro 바이트 정합 (F7, F8)**:
   - App `<main>` 무배경에 따른 body canvas (`#f8fafc` / `#090d16`) 실측 합성 반영 (base error 2.69:1, success 2.06:1, info 2.05:1 실제 Light 실패 표기 및 Probe 86~88 등록).
   - `reproduce_c228_contrast.py:145` `\n` 이스케이프 버그 수정으로 빈 줄 후 `[SUCCESS]` 출력과 문서 100% 바이트 일치.
8. **Fail-Closed Multiset Baseline 래칫 강제**:
   - `acc09-contrast-tokens.test.tsx`의 `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/agent/NaturalLanguageRunView.tsx`의 허용 인벤토리를 `{}` (0건)으로 전면 고정.
   - `var(--color-border-subtle)` 사용 횟수: `idle` 제거에 따른 443 -> 442건 30개 파일 엄밀 래칫 고정.

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 수치는 `python -X utf8 tools/reproduce_c228_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before (Hex/RGBA on Canvas) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
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
| 액션 알림 에러 텍스트 | action notice error text / subtle | `#f85149 on rgba(248,81,73,0.15) over body canvas` | 2.69:1 (FAIL) / 4.81:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 액션 알림 성공 텍스트 | action notice success text / subtle | `#3fb950 on rgba(46,160,67,0.15) over body canvas` | 2.06:1 (FAIL) / 6.25:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 액션 알림 안내 텍스트 | action notice info text / subtle | `#58a6ff on rgba(56,139,253,0.15) over body canvas` | 2.05:1 (FAIL) / 6.25:1 | `--color-brand-hover` on `--color-bg-subtle` | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
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
| 상태 배지 UNKNOWN | status badge unknown / subtle | base unknown config 부재 (`#58a6ff` on `#161b22`) | 6.85:1 / 6.85:1 | `--color-status-unknown` on `--color-bg-subtle` | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |

### 2.2 `python -X utf8 tools/reproduce_c228_contrast.py` 실제 실행 콘솔 출력
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
- **Total Style Attributes**: `56` (100% 정합)
- **Checked Objects (Explicit style objects)**: `13`
- **Checked Pairs (Evaluated color-background pairings)**: `45`
- **Unbound Color Objects**: `27`
- **Covered Color Objects**: `40`
- **Checked Border Objects**: `20`
- **Checked Border Pairs**: `23`
- **Violations**: `[]` (0건)
- **Hardcoded Color Literal Residual**: `0건`

---

## 4. 변이 테스트 (34종 X1~X34 전원 사살 실측)

`python -X utf8 tools/test_c228_mutations.py` 실행 결과:
```text
================================================================================
 Card 228 (ACC-09): Reproducible Mutant Test Suite (34 Mutants: X1-X34)
 Target: NaturalLanguageRunView.tsx
================================================================================

[Baseline Check] Testing unmutated code...
[Baseline Check] Clean pass (exit code 0).

[01/34] X1: KILLED in 8.5s -- NaturalLanguageRunView: repairing status config bg -> status-degraded (fg==bg collision)
         Reason: AssertionError: Agent status repairing light text >= 4.5:1: expected 1 to be greater t
[02/34] X2: KILLED in 6.4s -- NaturalLanguageRunView: status badge color -> statusCfg.bg (fg==bg collision)
         Reason: AssertionError: expected 'var(--color-bg-subtle)' to be 'var(--color-brand-hover)' // 
[03/34] X3: KILLED in 6.2s -- NaturalLanguageRunView: action notice success color -> bg-subtle (fg==bg collision on notice)
         Reason: AssertionError: expected 'var(--color-bg-subtle)' to be 'var(--color-status-online)' /
[04/34] X4: KILLED in 6.2s -- NaturalLanguageRunView: unknown fallback color -> bg-subtle (fg==bg collision on fallback)
         Reason: AssertionError: expected 'var(--color-bg-subtle)' to be 'var(--color-status-unknown)' 
[05/34] X5: KILLED in 6.6s -- NaturalLanguageRunView: draft status border -> bg-subtle (border==bg collision)
         Reason: AssertionError: Agent status draft light border >= 3.0:1: expected 1.0955171955711072 
[06/34] X6: KILLED in 6.0s -- NaturalLanguageRunView: status badge border -> statusCfg.bg (border==bg collision)
         Reason: AssertionError: expected 'var(--color-bg-subtle)' to be 'var(--color-brand-hover)' // 
[07/34] X7: KILLED in 6.0s -- NaturalLanguageRunView: action notice success border -> bg-subtle (border==bg collision on notice)
         Reason: AssertionError: expected 'var(--color-bg-subtle)' to be 'var(--color-status-online)' /
[08/34] X8: KILLED in 6.3s -- NaturalLanguageRunView: form textarea background -> text-inverse (text token as bg)
         Reason: AssertionError: NaturalLanguageRunView violations:
[09/34] X9: KILLED in 5.9s -- NaturalLanguageRunView: draft config bg -> text-secondary (text token as bg)
         Reason: AssertionError: Agent status draft light text >= 4.5:1: expected 1 to be greater than 
[10/34] X10: KILLED in 6.1s -- NaturalLanguageRunView: action notice opacity degraded to 0.45
         Reason: AssertionError: expected '0.45' to be '1' // Object.is equality
[11/34] X11: KILLED in 6.0s -- NaturalLanguageRunView: status badge opacity degraded to 0.4
         Reason: AssertionError: Status badge must not have degraded opacity: expected '0.4' to be '1' 
[12/34] X12: KILLED in 7.0s -- NaturalLanguageRunView: completed color with comment decoy literal
         Reason: AssertionError: expected '#3fb950' to be 'var(--color-status-online)' // Object.is equ
[13/34] X13: KILLED in 7.0s -- NaturalLanguageRunView: unknown fallback border with comment decoy literal
         Reason: AssertionError: expected '#8b949e' to be 'var(--color-status-unknown)' // Object.is eq
[14/34] X14: KILLED in 7.0s -- NaturalLanguageRunView: rejected config color reverted to legacy literal #ff7b72
         Reason: AssertionError: expected '#ff7b72' to be 'var(--color-status-offline)' // Object.is eq
[15/34] X15: KILLED in 6.2s -- NaturalLanguageRunView: diff code view color reverted to legacy literal #c9d1d9
         Reason: AssertionError: Explicit style objects in NaturalLanguageRunView must be exactly 13: e
[16/34] X16: KILLED in 5.8s -- NaturalLanguageRunView: evaluating status color collapsed to status-online
         Reason: AssertionError: expected 'var(--color-status-online)' not to be 'var(--color-status-on
[17/34] X17: KILLED in 5.9s -- NaturalLanguageRunView: repairing status color collapsed to status-online
         Reason: AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-degrad
[18/34] X18: KILLED in 5.8s -- NaturalLanguageRunView: draft status color collapsed to brand-hover
         Reason: AssertionError: expected 'var(--color-brand-hover)' not to be 'var(--color-brand-hover
[19/34] X19: KILLED in 6.2s -- NaturalLanguageRunView: completed label changed to DONE
         Reason: AssertionError: expected 'DONE' to be 'COMPLETED' // Object.is equality
[20/34] X20: KILLED in 6.1s -- NaturalLanguageRunView: rejected label changed to BLOCKED
         Reason: AssertionError: expected 'BLOCKED' to be 'REJECTED' // Object.is equality
[21/34] X21: KILLED in 6.1s -- NaturalLanguageRunView: draft label changed to 초안
         Reason: AssertionError: Agent status draft label must equal uppercase status: expected '초안' to
[22/34] X22: KILLED in 6.0s -- NaturalLanguageRunView: status badge DOM altered with extra exclamation suffix
         Reason: AssertionError: expected 'READY!' to be 'READY' // Object.is equality
[23/34] X23: KILLED in 6.0s -- NaturalLanguageRunView: preset 1 button outline suppressed with outline: none
         Reason: AssertionError: NaturalLanguageRunView violations:
[24/34] X24: KILLED in 6.0s -- NaturalLanguageRunView: preset 1 button outline suppressed with outlineWidth: 0px
         Reason: AssertionError: NaturalLanguageRunView violations:
[25/34] X25: KILLED in 6.2s -- NaturalLanguageRunView: apply-diff Button outline suppressed with outline: none as const (F10)
         Reason: AssertionError: Total style attributes in NaturalLanguageRunView must be exactly 56: e
[26/34] X26: KILLED in 6.1s -- NaturalLanguageRunView: context tag outline suppressed with outline: 0
         Reason: AssertionError: NaturalLanguageRunView violations:
[27/34] X27: KILLED in 6.0s -- NaturalLanguageRunView: getAgentRunStatusConfig null/empty returns draft (fail-open fallback bypass)
         Reason: AssertionError: expected 'DRAFT' to be 'UNKNOWN' // Object.is equality
[28/34] X28: KILLED in 6.3s -- NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns ready config
         Reason: AssertionError: expected 'var(--color-brand-hover)' to be 'var(--color-status-unknown)
[29/34] X29: KILLED in 6.3s -- NaturalLanguageRunView: getAgentRunStatusConfig uses in operator instead of Object.hasOwn
         Reason: AssertionError: expected undefined to be 'var(--color-status-unknown)' // Object.is eq
[30/34] X30b: KILLED in 6.0s -- NaturalLanguageRunView: out-of-contract status (planning) added to AGENT_RUN_STATUS_CONFIG
         Reason: AssertionError: expected [ 'completed', 'draft', …(5) ] to deeply equal [ 'completed',
[31/34] X31b: KILLED in 6.4s -- NaturalLanguageRunView: contract status (completed) removed from AGENT_RUN_STATUS_CONFIG
         Reason: AssertionError: expected 'var(--color-status-unknown)' to be 'var(--color-status-onlin
[32/34] X32: KILLED in 6.1s -- NaturalLanguageRunView: action notice success border injected with named color green
         Reason: AssertionError: expected 'green' to be 'var(--color-status-online)' // Object.is equal
[33/34] X33: KILLED in 5.8s -- NaturalLanguageRunView: draft config color injected with named color green
         Reason: AssertionError: Explicit style objects in NaturalLanguageRunView must be exactly 13: e
[34/34] X34: KILLED in 6.8s -- NaturalLanguageRunView: KPI 1 label injected with named color dimgray
         Reason: AssertionError: Evaluated pairs in NaturalLanguageRunView must be exactly 45: expected

================================================================================
 Summary: 34/34 mutants killed (100.0%)
================================================================================
 [PASS] KILLED    | NaturalLanguageRunView: repairing status config bg -> status-degraded (fg==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: status badge color -> statusCfg.bg (fg==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: action notice success color -> bg-subtle (fg==bg collision on notice)
 [PASS] KILLED    | NaturalLanguageRunView: unknown fallback color -> bg-subtle (fg==bg collision on fallback)
 [PASS] KILLED    | NaturalLanguageRunView: draft status border -> bg-subtle (border==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: status badge border -> statusCfg.bg (border==bg collision)
 [PASS] KILLED    | NaturalLanguageRunView: action notice success border -> bg-subtle (border==bg collision on notice)
 [PASS] KILLED    | NaturalLanguageRunView: form textarea background -> text-inverse (text token as bg)
 [PASS] KILLED    | NaturalLanguageRunView: draft config bg -> text-secondary (text token as bg)
 [PASS] KILLED    | NaturalLanguageRunView: action notice opacity degraded to 0.45
 [PASS] KILLED    | NaturalLanguageRunView: status badge opacity degraded to 0.4
 [PASS] KILLED    | NaturalLanguageRunView: completed color with comment decoy literal
 [PASS] KILLED    | NaturalLanguageRunView: unknown fallback border with comment decoy literal
 [PASS] KILLED    | NaturalLanguageRunView: rejected config color reverted to legacy literal #ff7b72
 [PASS] KILLED    | NaturalLanguageRunView: diff code view color reverted to legacy literal #c9d1d9
 [PASS] KILLED    | NaturalLanguageRunView: evaluating status color collapsed to status-online
 [PASS] KILLED    | NaturalLanguageRunView: repairing status color collapsed to status-online
 [PASS] KILLED    | NaturalLanguageRunView: draft status color collapsed to brand-hover
 [PASS] KILLED    | NaturalLanguageRunView: completed label changed to DONE
 [PASS] KILLED    | NaturalLanguageRunView: rejected label changed to BLOCKED
 [PASS] KILLED    | NaturalLanguageRunView: draft label changed to 초안
 [PASS] KILLED    | NaturalLanguageRunView: status badge DOM altered with extra exclamation suffix
 [PASS] KILLED    | NaturalLanguageRunView: preset 1 button outline suppressed with outline: none
 [PASS] KILLED    | NaturalLanguageRunView: preset 1 button outline suppressed with outlineWidth: 0px
 [PASS] KILLED    | NaturalLanguageRunView: apply-diff Button outline suppressed with outline: none as const (F10)
 [PASS] KILLED    | NaturalLanguageRunView: context tag outline suppressed with outline: 0
 [PASS] KILLED    | NaturalLanguageRunView: getAgentRunStatusConfig null/empty returns draft (fail-open fallback bypass)
 [PASS] KILLED    | NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns ready config
 [PASS] KILLED    | NaturalLanguageRunView: getAgentRunStatusConfig uses in operator instead of Object.hasOwn
 [PASS] KILLED    | NaturalLanguageRunView: out-of-contract status (planning) added to AGENT_RUN_STATUS_CONFIG
 [PASS] KILLED    | NaturalLanguageRunView: contract status (completed) removed from AGENT_RUN_STATUS_CONFIG
 [PASS] KILLED    | NaturalLanguageRunView: action notice success border injected with named color green
 [PASS] KILLED    | NaturalLanguageRunView: draft config color injected with named color green
 [PASS] KILLED    | NaturalLanguageRunView: KPI 1 label injected with named color dimgray

SUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.
```

---

## 5. 검증 요약
| 검증 항목 | 실행 명령 | 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| Vitest ACC-09 스위트 | `npx vitest run tests/acc09-contrast-tokens.test.tsx` | **30 passed (100%)** | Test 9m DOM 결속, Test 9j-2 AST 래칫, Probe 86~90 전수 통과 |
| Vitest 자연어 실행 단위시험 | `npx vitest run tests/natural-language-run-view.test.tsx` | **8 passed (100%)** | Bounded repair 루프 및 거절 전환 동작 불변식 100% 통과 |
| Vitest 형제 배선 시험 | `npx vitest run tests/node-fetch-error-workspace-wiring.test.tsx` | **10 passed (100%)** | Exact status badge text 복원으로 hosted 실패 완전 해소 |
| S11 결함 회귀 스위트 | `npx vitest run tests/s11-defect-fixes.test.tsx` | **16 passed (100%)** | DEF-S11-09 버튼 토큰 검증 통과 |
| 타입스크립트 정적 검사 | `npx tsc -b` | **0 errors (Exit Code 0)** | Strict types 100% 충족 |
| 프로덕션 번들 빌드 | `npm run build` | **Build Success (Exit Code 0)** | Vite 프로덕션 번들 정상 생성 (dist) |
| 라우트 커버리지 및 무결성 | `pytest tests/test_route_coverage.py` | **41 passed (100%)** | 불변식 및 라우트 계약 일치 |
| 프런트엔드 무결성 가드 | `python -X utf8 tools/check_frontend_integrity.py` | **0 violations (Exit Code 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 검사 | `python -X utf8 tools/check_contract_bindings.py` | **PASS (Exit Code 0)** | 55 fixtures, 20 types 커버리지 |
| 문서 검사 도구 | `python tools/check_docs.py` | **PASS (Exit Code 0)** | 1081 docs, link, DAG 무결성 |
| 명도 대비 동적 재현 | `python -X utf8 tools/reproduce_c228_contrast.py` | **28/28 passed (Exit Code 0)** | Light/Dark 전수 WCAG AA 충족, 바이트 정합 |
| 뮤테이션 테스트 스위트 | `python -X utf8 tools/test_c228_mutations.py` | **34/34 killed (100.0%)** | X1~X34 34종 전원 사살 실측 |
