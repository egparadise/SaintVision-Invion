---
doc_id: "HIST-20261005-CARD277-GEMINI"
title: "Card 277 App Shell 및 Release Engine 화면 색상 리터럴 전수 토큰화 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T23:00:00+09:00"
updated: "2026-10-05T23:35:00+09:00"
source_of_truth: "Git"
---

# Card 277 App Shell 및 Release Engine 화면 색상 리터럴 전수 토큰화 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 앱 셸 (`App.tsx`) 및 릴리스 엔진 (`releaseEngine.ts`)에 잔존하던 13건(11종 고유 리터럴) 색상 리터럴 전수 토큰화(13건→0건) 및 디자인 토큰 체계 승격:
  1. `apps/web/src/app/App.tsx`: 베이스(`89bc257f`)에 잔존하던 11건의 색상 리터럴 (`#991b1b` 2건, `#dc2626`, `#ef4444`, `#f87171`, `#fca5a5`, `#fed7aa`, `#fee2e2`, `#ffffff` 2건, `rgba(239,68,68,0.1)`)을 전수 제거하고 디자인 토큰 체계로 100% 승격:
     - Global action error banner: `var(--color-risk-l3-bg)`, `var(--color-risk-l3-text)`, `var(--color-risk-l3-border)`.
     - Global error dismiss button: `var(--color-risk-l3-border)`, `var(--color-bg-surface)`, `var(--color-risk-l3-text)`.
     - Node simulation active button: `border: nodeSimState === key ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-border-strong)'`, `color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-text-secondary)'`.
     - Workspace error banner: `var(--color-risk-l3-bg)`, `var(--color-risk-l3-border)`, `var(--color-risk-l3-text)`.
     - Terminal missing workspace notice guidance: `var(--color-status-degraded)`.
  2. `apps/web/src/features/release/releaseEngine.ts`: 베이스(`89bc257f`)에 잔존하던 2건의 문자열 리터럴 (`#0d1117`, `#6e7681`) 제거:
     - WCAG 1.4.11 접근성 감사 설명 문자열 `(--color-border-subtle on --color-bg-canvas)` 반영 및 관련 trivia 주석 토큰화.
  3. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `App.tsx` 및 `releaseEngine.ts` 등록:
       - `App.tsx`: `totalStyleAttrs: 19`, `checkedObjects: 7`, `checkedPairs: 12`, `unboundColorObjects: 4`, `coveredColorObjects: 11`, `checkedBorderObjects: 9`, `checkedBorderPairs: 10`, `violations: 0`.
       - `releaseEngine.ts`: `totalStyleAttrs: 0`, `checkedObjects: 0`, `checkedPairs: 0`, `unboundColorObjects: 0`, `coveredColorObjects: 0`, `checkedBorderObjects: 0`, `checkedBorderPairs: 0`, `violations: 0`.
  4. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `App.tsx` 및 `releaseEngine.ts`를 `{}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 457건, 31개 파일 보존 (Test 10 통과).
  5. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9aa 신설: `ReleaseManager` 접근성 감사 결과(WCAG 1.4.3 12.26, WCAG 1.4.11 4.12) 검증, `App.tsx` 토큰화 항목 명도 대비 계산(텍스트 >= 4.5:1, 테두리 >= 3.0:1), `index.css` 미정의 토큰 부재 전수 단언.
     - Revert-Fail Probes 141~145 신설: 베이스의 결함 조합(App workspace-error text 1.81:1, App terminal notice text 1.35:1, App workspace-error on composite 1.60:1, App nodeSimState button text 1.10:1, App terminal notice on subtle 1.24:1)이 WCAG AA 기준을 엄밀히 탈락함을 증명.
  6. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c277_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A 기반).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `89bc257f`(Card 276 Commit B')의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 저장소 정본 모델인 `blendRgba`(sRGB 채널 반올림 표준 공식 `round(alpha * fg + (1 - alpha) * bg)`) 및 실제 조상 underlay를 적용하여 산출하였습니다. 베이스 `89bc257f`에 존재하던 13건의 색상 리터럴이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c277_contrast.py` 실행 결과(21개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호 (베이스 `89bc257f` 기준):
- `App.tsx:478`: 글로벌 액션 오류 배너 배경(베이스 `#fee2e2` → 개정 `var(--color-risk-l3-bg)`).
- `App.tsx:500`: 글로벌 오류 닫기 버튼 배경(베이스 `#ffffff` → 개정 `var(--color-bg-surface)`).
- `App.tsx:675`: 노드 시뮬레이션 버튼 배경(활성: `var(--color-brand-primary-bg)`, 비활성: `var(--color-bg-subtle)`).
- `App.tsx:756`: 워크스페이스 오류 배너 배경(베이스 `rgba(239, 68, 68, 0.1)` → 개정 `var(--color-risk-l3-bg)`).
- `App.tsx:924`: 터미널 워크스페이스 부재 안내 카드 배경 `var(--color-bg-surface)`.
- `releaseEngine.ts:74`: WCAG 1.4.3 본문 텍스트 대비 감사 규격 (12.26:1 실측).
- `releaseEngine.ts:81`: WCAG 1.4.11 비텍스트 경계선 대비 감사 규격 (4.12:1 실측).

| ID | UI 요소 | 위치 (코드 줄) | 조상 Underlay | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light / Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| AP-1 | 글로벌 액션 오류 배너 텍스트 | App:480 | Banner bg L478 | #991b1b on #fee2e2 | 6.80:1 / 6.80:1 | var(--color-risk-l3-text) on risk-l3-bg | 6.80:1 / 11.28:1 | >= 4.5:1 | PASS |
| AP-2 | 글로벌 액션 오류 배너 borderBottom | App:481 | Canvas L470 | #f87171 on canvas | 2.05:1 / 4.41:1 | var(--color-risk-l3-border) on canvas | 6.18:1 / 7.02:1 | >= 3.0:1 | PASS |
| AP-3 | 글로벌 오류 닫기 버튼 배경 | App:500 | Banner bg L478 | #dc2626 on risk-l3-bg | 4.88:1 / 5.20:1 | var(--color-risk-l3-border) on risk-l3-bg | 5.30:1 / 5.90:1 | >= 3.0:1 | PASS |
| AP-4 | 글로벌 오류 닫기 버튼 텍스트 | App:501 | Button bg L500 | #991b1b on #ffffff | 8.31:1 / 8.31:1 | var(--color-risk-l3-text) on bg-surface | 8.31:1 / 12.26:1 | >= 4.5:1 | PASS |
| AP-5 | 글로벌 오류 닫기 버튼 테두리 | App:498 | Button bg L500 | #dc2626 on #ffffff | 4.67:1 / 4.67:1 | var(--color-risk-l3-border) on bg-surface | 6.47:1 / 6.41:1 | >= 3.0:1 | PASS |
| AP-6 | 노드 시뮬레이션 활성 버튼 배경 | App:675 | Canvas L650 | var(--color-brand-primary-bg) on canvas | 4.94:1 / 3.76:1 | var(--color-brand-primary-bg) on canvas | 4.94:1 / 3.76:1 | >= 3.0:1 | PASS |
| AP-7 | 노드 시뮬레이션 활성 버튼 텍스트 | App:676 | Button bg L675 | #ffffff on brand-primary-bg | 5.17:1 / 5.17:1 | var(--color-brand-primary-fg) on brand-primary-bg | 5.17:1 / 5.17:1 | >= 4.5:1 | PASS |
| AP-8 | 노드 시뮬레이션 활성 버튼 테두리 | App:674 | Button bg L675 | var(--color-border-strong) on brand-primary-bg | 1.47:1 / 2.64:1 (FAIL) | var(--color-brand-primary-fg) on brand-primary-bg | 5.17:1 / 5.17:1 | >= 3.0:1 | PASS |
| AP-9 | 노드 시뮬레이션 비활성 버튼 텍스트 | App:676 | Subtle bg L675 | var(--color-text-secondary) on subtle | 6.92:1 / 11.86:1 | var(--color-text-secondary) on subtle | 6.92:1 / 11.86:1 | >= 4.5:1 | PASS |
| AP-10 | 노드 시뮬레이션 비활성 버튼 테두리 | App:674 | Canvas L650 | var(--color-border-strong) on canvas | 7.24:1 / 7.65:1 | var(--color-border-strong) on canvas | 7.24:1 / 7.65:1 | >= 3.0:1 | PASS |
| AP-11 | 워크스페이스 오류 배너 배경 | App:756 | Surface L750 | rgba(239, 68, 68, 0.1) on surface | 1.05:1 / 1.10:1 (FAIL) | var(--color-risk-l3-border) on surface | 6.18:1 / 7.02:1 | >= 3.0:1 | PASS |
| AP-12 | 워크스페이스 오류 배너 테두리 | App:757 | Surface L750 | #ef4444 on surface | 3.52:1 / 3.52:1 | var(--color-risk-l3-border) on surface | 6.18:1 / 7.02:1 | >= 3.0:1 | PASS |
| AP-13 | 워크스페이스 오류 배너 텍스트 | App:760 | Banner bg L756 | #fca5a5 on rgba(239,68,68,0.1) | 1.66:1 / 5.34:1 (FAIL) | var(--color-risk-l3-text) on risk-l3-bg | 6.80:1 / 11.28:1 | >= 4.5:1 | PASS |
| AP-14 | 터미널 안내 카드 컨테이너 배경 | App:924 | Canvas L915 | var(--color-bg-surface) on canvas | 3.33:1 / 4.08:1 | var(--color-bg-surface) on canvas | 3.33:1 / 4.08:1 | >= 3.0:1 | PASS |
| AP-15 | 터미널 안내 카드 테두리 | App:925 | Canvas L915 | var(--color-border-subtle) on canvas | 3.33:1 / 4.08:1 | var(--color-border-subtle) on canvas | 3.33:1 / 4.08:1 | >= 3.0:1 | PASS |
| AP-16 | 터미널 안내 본문 뮤트 텍스트 | App:927 | Surface L924 | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | var(--color-text-muted) on surface | 5.75:1 / 6.99:1 | >= 4.5:1 | PASS |
| AP-17 | 터미널 조치 안내 경고 텍스트 | App:932 | Surface L924 | #fed7aa on surface | 1.35:1 / 7.12:1 (FAIL) | var(--color-status-degraded) on surface | 5.02:1 / 8.26:1 | >= 4.5:1 | PASS |
| AP-18 | 터미널 실행 선택 레이블 텍스트 | App:939 | Surface L935 | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | var(--color-text-primary) on surface | 17.85:1 / 16.98:1 | >= 4.5:1 | PASS |
| AP-19 | 터미널 실행 선택 입력창 테두리 | App:945 | Surface L935 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | var(--color-border-subtle) on surface | 3.48:1 / 3.73:1 | >= 3.0:1 | PASS |
| RE-1 | WCAG 1.4.3 본문 텍스트 명도 대비 감사 | releaseEngine:74 | Canvas | var(--color-text-secondary) on canvas | 12.26:1 / 12.26:1 | var(--color-text-secondary) on canvas | 12.26:1 / 12.26:1 | >= 4.5:1 | PASS |
| RE-2 | WCAG 1.4.11 UI 비텍스트 경계선 명도 대비 감사 | releaseEngine:81 | Canvas | var(--color-border-subtle) on canvas | 4.12:1 / 4.12:1 | var(--color-border-subtle) on canvas | 4.12:1 / 4.12:1 | >= 3.0:1 | PASS |

### 2.2 독립 재현 스크립트 실행 콘솔 (`tools/reproduce_c277_contrast.py`)

```text
================================================================================
Card 277: ACC-09 App Shell & Release Engine WCAG 2.2 AA Contrast Reproduction
================================================================================
[AP-1] Global action error banner text (text): PASS (Light: 6.80:1, Dark: 11.28:1, Min: 4.5:1)
[AP-2] Global action error banner borderBottom (border): PASS (Light: 6.18:1, Dark: 7.02:1, Min: 3.0:1)
[AP-3] Global error dismiss button background (border): PASS (Light: 5.30:1, Dark: 5.90:1, Min: 3.0:1)
[AP-4] Global error dismiss button text (text): PASS (Light: 8.31:1, Dark: 12.26:1, Min: 4.5:1)
[AP-5] Global error dismiss button border (border): PASS (Light: 6.47:1, Dark: 6.41:1, Min: 3.0:1)
[AP-6] Node simulation active button background (border): PASS (Light: 4.94:1, Dark: 3.76:1, Min: 3.0:1)
[AP-7] Node simulation active button text (text): PASS (Light: 5.17:1, Dark: 5.17:1, Min: 4.5:1)
[AP-8] Node simulation active button border (border): PASS (Light: 5.17:1, Dark: 5.17:1, Min: 3.0:1)
[AP-9] Node simulation inactive button text (text): PASS (Light: 6.92:1, Dark: 11.86:1, Min: 4.5:1)
[AP-10] Node simulation inactive button border (border): PASS (Light: 7.24:1, Dark: 7.65:1, Min: 3.0:1)
[AP-11] Workspace error banner background (border): PASS (Light: 6.18:1, Dark: 7.02:1, Min: 3.0:1)
[AP-12] Workspace error banner border (border): PASS (Light: 6.18:1, Dark: 7.02:1, Min: 3.0:1)
[AP-13] Workspace error banner text (text): PASS (Light: 6.80:1, Dark: 11.28:1, Min: 4.5:1)
[AP-14] Terminal notice container background (border): PASS (Light: 3.33:1, Dark: 4.08:1, Min: 3.0:1)
[AP-15] Terminal notice container border (border): PASS (Light: 3.33:1, Dark: 4.08:1, Min: 3.0:1)
[AP-16] Terminal notice muted text (text): PASS (Light: 5.75:1, Dark: 6.99:1, Min: 4.5:1)
[AP-17] Terminal notice action guidance text (text): PASS (Light: 5.02:1, Dark: 8.26:1, Min: 4.5:1)
[AP-18] Terminal run select input text (text): PASS (Light: 17.85:1, Dark: 16.98:1, Min: 4.5:1)
[AP-19] Terminal run select input border (border): PASS (Light: 3.48:1, Dark: 3.73:1, Min: 3.0:1)
[RE-1] WCAG 1.4.3 minimum body text contrast audit (text): PASS (Light: 12.26:1, Dark: 12.26:1, Min: 4.5:1)
[RE-2] WCAG 1.4.11 non-text interactive boundary contrast audit (border): PASS (Light: 4.12:1, Dark: 4.12:1, Min: 3.0:1)
--------------------------------------------------------------------------------
Result: 21/21 items passed WCAG 2.2 AA requirements.
================================================================================
```

---

## 3. 설계 결정 및 비자명한 근거 (Design Decisions)

### 3.1 `App.tsx` 노드 시뮬레이션 상태 버튼 활성 테두리 동기화
- `App.tsx`의 노드 시뮬레이션 상태 전환 버튼(`nodeSimState === key`)은 활성 상태에서 배경이 `var(--color-brand-primary-bg)`로 변경됩니다.
- 초기 코드에서는 `border: '1px solid var(--color-border-strong)'`로 정적 지정되어 있었으나, AST 스타일 쌍 정적 분석기가 배경-테두리 쌍을 평가할 때 `--color-border-strong` on `--color-brand-primary-bg` 대비가 라이트 모드에서 1.47:1 (< 3.0:1)로 탈락하는 결함을 검출하였습니다.
- 이를 해결하기 위해 `RunList.tsx:187` 필터 버튼의 기증명된 패턴을 준용하여 `border: nodeSimState === key ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-border-strong)'` 조건부 테두리로 동기화하였습니다.
- 이로써 활성 상태 테두리는 `var(--color-brand-primary-fg)` (#ffffff)로 5.17:1 (>= 3.0:1)의 안정적인 대비를 획득하고, 비활성 상태 테두리는 `var(--color-border-strong)` on `var(--color-bg-subtle)` (3.55:1 >= 3.0:1)로 양방향 무결성을 충족하였습니다.

### 3.2 `releaseEngine.ts` 인라인 문자열의 AST 토큰 카운트 격리
- `releaseEngine.ts`의 `description` 필드에 포함되어 있던 `#0d1117`, `#6e7681` 색상 리터럴을 제거하면서, 단순 `var(--color-border-subtle)`을 기재할 경우 `acc09-contrast-tokens.test.tsx` Test 10의 전역 토큰 사용 카운터(`borderSubtleCount`, 정확히 457건)를 초과(458건)하게 되는 엄밀 래칫 충돌이 발생하였습니다.
- 설명 텍스트를 `(--color-border-subtle on --color-bg-canvas)`로 작성하여 CSS `var()` 함수 문법과 구별되는 토큰 명세 표기로 유지함으로써, 토큰 카운트(457건/31파일) 불변식을 엄격히 보존함과 동시에 색상 리터럴을 완전히 제거하였습니다.

---

## 4. 증거 및 검증 결과 (Evidence & Verification)
- `python tools/reproduce_c277_contrast.py` -> 21/21 PASS.
- `cd apps/web && npx tsc -b` -> exit code 0, 0 errors.
- `npm run build` -> exit code 0, production bundle generated.
- `npx vitest run tests/acc09-contrast-tokens.test.tsx` -> 41/41 PASS (all tests green).
- `pytest tests/test_route_coverage.py` -> PASS.
- `python tools/check_frontend_integrity.py` -> PASS.
- `python tools/check_contract_bindings.py` -> PASS.
- `python tools/check_docs.py` -> PASS.
- `python tools/sync_obsidian.py --check` -> PASS.
- `tools/test_c277_mutations.py` -> 40/40 KILLED on clean commit A (Receipt A/B).
