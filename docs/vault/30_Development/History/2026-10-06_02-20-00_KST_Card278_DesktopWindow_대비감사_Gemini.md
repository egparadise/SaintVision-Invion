---
doc_id: "HIST-20261006-CARD278-GEMINI"
title: "Card 278 DesktopWindow 화면 색상 리터럴 전수 토큰화 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-06T02:20:00+09:00"
updated: "2026-10-06T02:35:09+09:00"
source_of_truth: "Git"
---

# Card 278 DesktopWindow 화면 색상 리터럴 전수 토큰화 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 데스크톱 창 컴포넌트 (`DesktopWindow.tsx`)에 잔존하던 17 occurrences / 15 distinct (14 semantic colors) 색상 리터럴 전수 토큰화(17건→0건), 상태 계약 무결성 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/desktop/DesktopWindow.tsx`: 베이스(`e6488165`, Card 277 Commit C)에 잔존하던 17 occurrences / 15 distinct 색상 리터럴 (`#0f172a`, `#10b981`, `#1e293b`, `#333`, `#334155`, `#64748b`, `#94a3b8`, `#ef4444`, `#f59e0b`, `#f8fafc`, `rgba(0,0,0,0.25)`, `rgba(0,0,0,0.3)` 4건, `rgba(0,0,0,0.45)`, `rgba(0,0,0,0.5)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격:
     - Window container: `var(--color-bg-surface)`, `var(--color-border-subtle)` (maximized), `var(--color-border-strong)` (floating), `var(--color-brand-primary)` (active ring), `var(--shadow-sm)`, `var(--shadow-md)`, `var(--shadow-lg)`.
     - Titlebar: `backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)'`, `borderBottom: '1px solid var(--color-border-subtle)'`.
     - Traffic light control buttons: `WINDOW_CONTROL_CONFIG satisfies Record<WindowControlAction, WindowControlStyle>` 및 `getWindowControlConfig` fail-closed 헬퍼 신설 (`var(--color-status-offline)`, `var(--color-status-degraded)`, `var(--color-status-online)`).
     - Title text & AppId indicator: `color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)'` 및 `var(--color-text-muted)`.
  2. **Fail-Closed 상태 계약 체계 확립**:
     - `WindowControlAction` ('close' | 'minimize' | 'maximize') 정합 집합 도출.
     - `getWindowControlConfig`: `Object.hasOwn` 기반 fail-closed lookup을 적용하여 프로토타입 오염(toString, constructor, __proto__) 및 대소문자 변이(CLOSE, Close)를 `UNKNOWN (<raw>)` / `var(--color-status-unknown)`으로 안전 격리 (WCAG 2.2 SC 1.4.1 준수).
  3. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `DesktopWindow.tsx` 등록:
       - `totalStyleAttrs: 13`, `checkedObjects: 3`, `checkedPairs: 9`, `unboundColorObjects: 2`, `coveredColorObjects: 5`, `checkedBorderObjects: 6`, `checkedBorderPairs: 7`, `violations: 0`.
  4. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/desktop/DesktopWindow.tsx`를 `{}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 457건, 31개 파일 보존 (Test 10 통과).
  5. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9ab 신설: `DesktopWindowComponent` 활성 플로팅 창 및 비활성 최대화 창 DOM 렌더링, 색상 토큰 및 외곽선 보존 단언, `WINDOW_CONTROL_CONFIG` 엄밀 키셋/색상/레이블 검증, `index.css` 미정의 토큰 부재 전수 단언.
     - Revert-Fail Probes 146~150 신설: 베이스의 결함 조합(최소화 버튼 #f59e0b 1.96:1, 최대화 버튼 #10b981 2.32:1, 비활성 타이틀 #94a3b8 2.56:1, appId 텍스트 #64748b 4.34:1)이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  6. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c278_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A `637c21f4` 기반, Commit B `4ad183be` 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `e6488165`(Card 277 Commit C, 원 기준 `6d2203c7`)의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba`(sRGB 채널 반올림 표준 공식 `round(alpha * fg + (1 - alpha) * bg)`) 및 실제 조상 underlay를 적용하여 산출하였습니다. 베이스 `e6488165`에 존재하던 17 occurrences / 15 distinct 색상 리터럴이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c278_contrast.py` 실행 결과(21개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `e6488165` 기준):
- `DesktopWindow.tsx:67`: 최대화 창 컨테이너 배경 `var(--color-bg-surface)`.
- `DesktopWindow.tsx:71`: 최대화 창 컨테이너 테두리 `var(--color-border-subtle)`.
- `DesktopWindow.tsx:87`: 플로팅 창 컨테이너 배경 `var(--color-bg-surface)`.
- `DesktopWindow.tsx:92`: 플로팅 창 컨테이너 테두리 `var(--color-border-strong, #333)` (활성 시 `0 0 0 1px var(--color-brand-primary)` 링 중첩).
- `DesktopWindow.tsx:112`: 활성 타이틀바 배경 `var(--color-bg-subtle, #1e293b)`, 비활성 `var(--color-bg-surface, #0f172a)`.
- `DesktopWindow.tsx:113`: 타이틀바 구분 하단선 `var(--color-border-subtle, #334155)`.
- `DesktopWindow.tsx:134`: 신호등 닫기 버튼 `#ef4444`.
- `DesktopWindow.tsx:153`: 신호등 최소화 버튼 `#f59e0b`.
- `DesktopWindow.tsx:172`: 신호등 최대화/복원 버튼 `#10b981`.
- `DesktopWindow.tsx:191`: 창 제목 텍스트 (활성 `#f8fafc`, 비활성 `#94a3b8`).
- `DesktopWindow.tsx:200`: 창 appId 상태 레이블 `#64748b`.

| ID | UI 요소 | 위치 (코드 줄) | 조상 Underlay | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light / Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| DW-1 | 최대화 창 컨테이너 배경 (fill on canvas) | DesktopWindow:67 | Canvas | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | INFO | INFO |
| DW-2 | 최대화 창 컨테이너 테두리 | DesktopWindow:71 | Canvas | var(--color-border-subtle) on canvas | 3.33:1 / 4.08:1 | var(--color-border-subtle) on canvas | 3.33:1 / 4.08:1 | >= 3.0:1 | PASS |
| DW-3 | 플로팅 창 컨테이너 배경 (fill on canvas) | DesktopWindow:87 | Canvas | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | var(--color-bg-surface) on canvas | 1.05:1 / 1.10:1 | INFO | INFO |
| DW-4 | 플로팅 창 컨테이너 테두리 (focused) | DesktopWindow:92 | Canvas | #333333 on canvas | 12.08:1 / 1.54:1 (FAIL) | var(--color-border-strong) on canvas | 7.24:1 / 7.65:1 | >= 3.0:1 | PASS |
| DW-5 | 플로팅 창 포커스 링 외곽선 (brand-primary) | DesktopWindow:90 | Canvas | var(--color-brand-primary) on canvas | 4.94:1 / 7.64:1 | var(--color-brand-primary) on canvas | 4.94:1 / 7.64:1 | >= 3.0:1 | PASS |
| DW-6 | 활성 타이틀바 배경 (fill on surface) | DesktopWindow:112 | Surface | #1e293b on surface | 14.63:1 / 1.21:1 | var(--color-bg-subtle) on surface | 1.10:1 / 1.21:1 | INFO | INFO |
| DW-7 | 활성 타이틀바 borderBottom | DesktopWindow:113 | Subtle | #334155 on subtle | 10.35:1 / 1.71:1 (FAIL) | var(--color-border-subtle) on subtle | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS |
| DW-8 | 비활성 타이틀바 배경 (fill on surface) | DesktopWindow:112 | Surface | #0f172a on surface | 17.85:1 / 1.01:1 | var(--color-bg-surface) on surface | 1.00:1 / 1.00:1 | INFO | INFO |
| DW-9 | 비활성 타이틀바 borderBottom | DesktopWindow:113 | Surface | #334155 on surface | 10.35:1 / 1.71:1 (FAIL) | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS |
| DW-10 | 신호등 닫기 버튼 (on active subtle) | DesktopWindow:134 | Subtle | #ef4444 on subtle | 3.44:1 / 3.90:1 | var(--color-status-offline) on subtle | 5.91:1 / 5.31:1 | >= 3.0:1 | PASS |
| DW-11 | 신호등 닫기 버튼 (on inactive surface) | DesktopWindow:134 | Surface | #ef4444 on surface | 3.76:1 / 4.71:1 | var(--color-status-offline) on surface | 6.47:1 / 6.41:1 | >= 3.0:1 | PASS |
| DW-12 | 신호등 최소화 버튼 (on active subtle) | DesktopWindow:153 | Subtle | #f59e0b on subtle | 1.96:1 / 6.83:1 (FAIL) | var(--color-status-degraded) on subtle | 4.58:1 / 6.83:1 | >= 3.0:1 | PASS |
| DW-13 | 신호등 최소화 버튼 (on inactive surface) | DesktopWindow:153 | Surface | #f59e0b on surface | 2.15:1 / 8.26:1 (FAIL) | var(--color-status-degraded) on surface | 5.02:1 / 8.26:1 | >= 3.0:1 | PASS |
| DW-14 | 신호등 최대화 버튼 (on active subtle) | DesktopWindow:172 | Subtle | #10b981 on subtle | 2.32:1 / 5.79:1 (FAIL) | var(--color-status-online) on subtle | 4.58:1 / 6.44:1 | >= 3.0:1 | PASS |
| DW-15 | 신호등 최대화 버튼 (on inactive surface) | DesktopWindow:172 | Surface | #10b981 on surface | 2.54:1 / 6.99:1 (FAIL) | var(--color-status-online) on surface | 5.02:1 / 7.79:1 | >= 3.0:1 | PASS |
| DW-16 | 창 제목 텍스트 (active) | DesktopWindow:191 | Subtle | #f8fafc on subtle | 1.05:1 / 14.03:1 (FAIL) | var(--color-text-primary) on subtle | 16.30:1 / 14.05:1 | >= 4.5:1 | PASS |
| DW-17 | 창 제목 텍스트 (inactive) | DesktopWindow:191 | Surface | #94a3b8 on surface | 2.56:1 / 6.92:1 (FAIL) | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | >= 4.5:1 | PASS |
| DW-18 | 창 appId 상태 레이블 (active) | DesktopWindow:200 | Subtle | #64748b on subtle | 4.34:1 / 3.08:1 (FAIL) | var(--color-text-muted) on subtle | 5.25:1 / 5.78:1 | >= 4.5:1 | PASS |
| DW-19 | 창 appId 상태 레이블 (inactive) | DesktopWindow:200 | Surface | #64748b on surface | 4.76:1 / 3.73:1 (FAIL) | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | >= 4.5:1 | PASS |
| DW-20 | 창 컨트롤 폴백 UNKNOWN 배지 텍스트 | getWindowControlConfig | Subtle | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | >= 4.5:1 | PASS |
| DW-21 | 창 컨트롤 폴백 UNKNOWN 배지 테두리 | getWindowControlConfig | Subtle | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | var(--color-status-unknown) on subtle | 6.47:1 / 5.82:1 | >= 3.0:1 | PASS |

### 2.2 독립 재현 스크립트 실행 콘솔 (`tools/reproduce_c278_contrast.py`)

```text
========================================================================================
Card 278: ACC-09 DesktopWindow WCAG 2.2 AA Contrast Reproduction
========================================================================================
[PASS] Verified TOKENS table against apps/web/src/index.css declarations.

ID     | Target     | Before (L/D)   | After (L/D)    | Status | Item Name
----------------------------------------------------------------------------------------
DW-1   | INFO       | 1.05 / 1.10    | 1.05 / 1.10    | INFO   | Window container surface (maximized)
DW-2   | >= 3.0:1   | 3.33 / 4.08    | 3.33 / 4.08    | PASS   | Window container border (maximized)
DW-3   | INFO       | 1.05 / 1.10    | 1.05 / 1.10    | INFO   | Window container surface (floating)
DW-4   | >= 3.0:1   | 12.08 / 1.54   | 7.24 / 7.65    | PASS   | Window container border (floating focused)
DW-5   | >= 3.0:1   | 4.94 / 7.64    | 4.94 / 7.64    | PASS   | Window focus ring outline (floating focused)
DW-6   | INFO       | 14.63 / 1.21   | 1.10 / 1.21    | INFO   | Titlebar background (active)
DW-7   | >= 3.0:1   | 10.35 / 1.71   | 3.48 / 3.73    | PASS   | Titlebar borderBottom (active)
DW-8   | INFO       | 17.85 / 1.01   | 1.00 / 1.00    | INFO   | Titlebar background (inactive)
DW-9   | >= 3.0:1   | 10.35 / 1.71   | 3.48 / 3.73    | PASS   | Titlebar borderBottom (inactive)
DW-10  | >= 3.0:1   | 3.44 / 3.90    | 5.91 / 5.31    | PASS   | Traffic light close button (on active subtle)
DW-11  | >= 3.0:1   | 3.76 / 4.71    | 6.47 / 6.41    | PASS   | Traffic light close button (on inactive surface)
DW-12  | >= 3.0:1   | 1.96 / 6.83    | 4.58 / 6.83    | PASS   | Traffic light minimize button (on active subtle)
DW-13  | >= 3.0:1   | 2.15 / 8.26    | 5.02 / 8.26    | PASS   | Traffic light minimize button (on inactive surface)
DW-14  | >= 3.0:1   | 2.32 / 5.79    | 4.58 / 6.44    | PASS   | Traffic light maximize button (on active subtle)
DW-15  | >= 3.0:1   | 2.54 / 6.99    | 5.02 / 7.79    | PASS   | Traffic light maximize button (on inactive surface)
DW-16  | >= 4.5:1   | 1.05 / 14.03   | 16.30 / 14.05  | PASS   | Title text (active)
DW-17  | >= 4.5:1   | 2.56 / 6.92    | 5.75 / 6.99    | PASS   | Title text (inactive)
DW-18  | >= 4.5:1   | 4.34 / 3.08    | 5.25 / 5.78    | PASS   | Window appId status indicator (active)
DW-19  | >= 4.5:1   | 4.76 / 3.73    | 5.75 / 6.99    | PASS   | Window appId status indicator (inactive)
DW-20  | >= 4.5:1   | 6.47 / 5.82    | 6.47 / 5.82    | PASS   | Window control fallback UNKNOWN badge text
DW-21  | >= 3.0:1   | 6.47 / 5.82    | 6.47 / 5.82    | PASS   | Window control fallback UNKNOWN badge border
----------------------------------------------------------------------------------------
Total Audit Items: 21, Passed / Info: 21/21
ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.
```

---

## 3. 설계 결정 및 비자명한 근거 (Design Decisions)

### 3.1 신호등 창 조절 버튼(Traffic Light Controls) 색상 승격 및 명도 결손 해소
- 베이스 코드에서 최소화 버튼(`#f59e0b`)은 라이트 서브틀 타이틀바(`#f1f5f9`) 위에서 **1.96:1**, 서피스 위에서 **2.15:1**로 WCAG 2.2 SC 1.4.11 비텍스트 대비 기준(>= 3.0:1)을 심각하게 위반하고 있었습니다.
- 최대화 버튼(`#10b981`) 역시 라이트 타이틀바 위에서 **2.32:1** 및 **2.54:1**로 결손이 발생했습니다.
- 이를 시맨틱 상태 토큰인 `var(--color-status-degraded)` (`#b45309`, 라이트 대비 4.58:1 / 5.02:1) 및 `var(--color-status-online)` (`#15803d`, 라이트 대비 4.58:1 / 5.02:1)으로 승격하여, 양 테마에서 모두 3.0:1 이상의 명도비를 보장하였습니다.
- 닫기 버튼은 `var(--color-status-offline)` (`#b91c1c`, 5.91:1 / 6.47:1)으로 토큰화하여 시스템 전반의 위험/오프라인 시맨틱과 일관성을 확보했습니다.

### 3.2 그림자 효과(`box-shadow rgba`)의 시각적 심도와 WCAG SC 1.4.11 경계 식별 근거
- 베이스 `DesktopWindow.tsx`에는 창 심도를 위한 4종의 `boxShadow` 리터럴(`rgba(0, 0, 0, 0.25)`, `rgba(0, 0, 0, 0.3)`, `rgba(0, 0, 0, 0.45)`, `rgba(0, 0, 0, 0.5)`) 및 신호등 버튼 드롭 섀도(`rgba(0,0,0,0.3)`)가 존재했습니다.
- WCAG 2.2 SC 1.4.11 (Non-text Contrast) 지침에 따르면 드롭 섀도는 3차원적 입체감을 주는 장식적 표식(Elevation effect)이며, UI 대화형 컨트롤 및 컨테이너의 시각적 경계(Visual Boundary)는 요소에 명시된 1px 외곽선(`border: 1px solid var(--color-border-subtle)` / `var(--color-border-strong)`)에 의해 명확히 식별됩니다.
- 신호등 원형 버튼 역시 배경과의 명도 대비(>= 3.0:1)와 기하학적 형태에 의해 경계가 식별됩니다.
- 따라서 모든 `boxShadow` 리터럴을 `index.css` 정본 그림자 토큰(`var(--shadow-sm)`, `var(--shadow-md)`, `var(--shadow-lg)`)으로 100% 토큰화하였으며, 활성 창 포커스 링은 `0 0 0 1px var(--color-brand-primary)` (4.94:1 / 7.64:1 >= 3.0:1)으로 보존하여 접근성을 완벽히 만족하였습니다.

### 3.3 Fail-Closed `getWindowControlConfig` 계약 및 프로토타입 방어
- 신호등 조절 동작('close', 'minimize', 'maximize')을 관리하는 `WINDOW_CONTROL_CONFIG` 테이블을 정의하고 `satisfies Record<WindowControlAction, WindowControlStyle>`로 계약 무결성을 강제하였습니다.
- `getWindowControlConfig(action?: string | null)` 헬퍼는 `Object.hasOwn(WINDOW_CONTROL_CONFIG, action)`을 사용하여 `toString`, `constructor`, `__proto__` 등 프로토타입 주입을 원천 차단하고, 알 수 없는 값이 전달되면 `UNKNOWN (<raw>)` 레이블 및 `var(--color-status-unknown)` 토큰으로 fail-closed 안전 강등하여 WCAG 2.2 SC 1.4.1(색상에만 의존하지 않는 식별)을 엄격히 준수합니다.

---

## 4. 증거 및 검증 결과 (Evidence & Verification)
- `python tools/reproduce_c278_contrast.py` -> 21/21 PASS/INFO (0 failures).
- `cd apps/web && npx tsc -b` -> exit code 0, 0 errors.
- `npm run build` -> exit code 0, production bundle generated.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx` -> 42/42 PASS.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx tests/browser-matrix-acceptance.test.tsx tests/release-candidate.test.ts tests/s11-defect-fixes.test.tsx` -> 76/76 PASS.
- `pytest tests/test_route_coverage.py` -> 41/41 PASS.
- `python tools/check_frontend_integrity.py` -> PASS (9대 무결성 규칙 위반 0건).
- `python tools/check_contract_bindings.py` -> PASS.
- `python tools/check_docs.py` -> PASS.
- `python tools/check_doc_path_citations.py --ratchet --base-ref e6488165` -> PASS.
- `python tools/sync_obsidian.py --check` -> PASS (0 conflicts).
- `tools/test_c278_mutations.py` -> 40/40 KILLED on clean commit A (`637c21f4`), sealed in Commit B (`4ad183be`).
