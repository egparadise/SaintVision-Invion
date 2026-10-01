# 2026-10-02 04:30:00 KST — Card 199: 관리자 보안 콘솔 (AdminSecurityConsole) 색상 리터럴 inventory 전수(186→0), 대비 표본/DOM 결속 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD199-ADMIN-SECURITY-CONTRAST
- **작업 branch**: agent/gemini/c199-admin-security-contrast
- **Base commit**: 67df36e8b4e723224b422ee5ec671d467972054c (PR #296 r3 HEAD)
- **KST 시각**: 2026-10-02 04:30:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 시스템 보안 및 제어 평면 비상 통제를 담당하는 관리자 보안 콘솔(`apps/web/src/features/admin/AdminSecurityConsole.tsx`, 긴급 비상 정지 Kill Switch 모달 및 노드 격리 Drain UI 포함)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/admin/AdminSecurityConsole.tsx` (기존 baseline 리터럴: **186건**)
  - `apps/web/src/index.css` (`--color-bg-backdrop: rgba(0, 0, 0, 0.75);` 디자인 토큰 등록)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9e, Test 9e-2, Probes 44~48, 래칫 갱신)
- **감사 및 조치 결과**:
  - 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (186건 $\rightarrow$ 0건 감축).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 `AdminSecurityConsole.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 갱신.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 292건에서 **317건**(+25건)으로 증가하였으며, 사용 파일 수가 23개에서 **24개**(`AdminSecurityConsole.tsx` 신규 편입)로 래칫 단언 갱신.
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 강화:
    - `#30363d`: 116건(14개 파일) $\rightarrow$ **92건 이하(13개 파일 이하)**
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9e), 동적 AST 스타일 쌍 대비 계산기(Test 9e-2, 142개 style 속성 전수 검증), Revert-Fail Probes 44~48을 신설하여 10종 뮤테이션 전원 사살 실측.

---

## 2. 명도 대비 실측 및 개선 결과표

### 2.1 실제 렌더 배경 기반 실측치 비교 (Before vs After)

> **배경 실측 기준**:
> - Light 테마: Surface = `#ffffff`, Subtle = `#f1f5f9`
> - Dark 테마 (index.css 정본 토큰): Surface (`--color-bg-surface`) = `#111827`, Subtle (`--color-bg-subtle`) = `#1f2937`
>
> *주*: 기존 소스 코드는 다크 전용 하드코딩 리터럴로 작성되어 있었으므로, 아래 '이전 대비율'의 Light 테마 수치는 동일한 리터럴이 Light 테마 캔버스/서피스에 배치되었을 때의 **가상 비교(Virtual Comparison)** 수치입니다. Dark 테마의 Before 수치는 `index.css` 정본 배경(`#111827`, `#1f2937`) 위에서 렌더링된 실측치입니다.

| 요소 / 위치 (파일:행) | 이전 리터럴 (실제 렌더 배경) | 이전 대비율 (Light 가상 / Dark 정본) | 이전 판정 | 신규 디자인 토큰 (실제 렌더 배경) | 신규 대비율 (Light) | 신규 대비율 (Dark) | WCAG AA 충족 여부 |
|---|---|---|---|---|---|---|---|
| **KPI 카드 테두리**<br>(AdminSecurityConsole:698) | `#30363d` on `#ffffff` (Light 가상)<br>`#30363d` on `#111827` (Dark) | 12.20:1 / **1.45:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-surface)` | **3.48:1** | **3.73:1** | **PASS** (>= 3.0:1) |
| **KPI 카드 라벨**<br>(AdminSecurityConsole:699) | `#8b949e` on `#ffffff` (Light 가상)<br>`#8b949e` on `#111827` (Dark) | **3.08:1** / 5.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-surface)` | **7.58:1** | **6.99:1** | **PASS** (>= 4.5:1) |
| **KPI 카드 정상치 수치**<br>(AdminSecurityConsole:700) | `#3fb950` on `#ffffff` (Light 가상)<br>`#3fb950` on `#111827` (Dark) | **2.54:1** / 6.98:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-surface)` | **5.02:1** | **10.18:1** | **PASS** (>= 4.5:1) |
| **KPI 카드 GPU 수치**<br>(AdminSecurityConsole:716) | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#111827` (Dark) | **2.53:1** / 7.02:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **6.98:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 활성 배너 텍스트**<br>(AdminSecurityConsole:642) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | **3.06:1** / **4.38:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 활성 배너 테두리**<br>(AdminSecurityConsole:633) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | 3.06:1 / 4.38:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 3.0:1) |
| **관리자 미인증 안내 배너 텍스트**<br>(AdminSecurityConsole:665) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | **3.06:1** / **4.38:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **관리자 미인증 안내 배너 테두리**<br>(AdminSecurityConsole:663) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | 3.06:1 / 4.38:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 3.0:1) |
| **Kill Switch 모달 타이틀**<br>(AdminSecurityConsole:1450) | `#f85149` on `#ffffff` (Light 가상)<br>`#f85149` on `#111827` (Dark) | **3.35:1** / 5.29:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 모달 컨테이너 테두리**<br>(AdminSecurityConsole:1442) | `#f85149` on `#ffffff` (Light 가상)<br>`#f85149` on `#111827` (Dark) | 3.35:1 / 5.29:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 3.0:1) |
| **Kill Switch 모의 안내 텍스트**<br>(AdminSecurityConsole:1479) | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#1f2937` (Dark) | **2.30:1** / 5.82:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **8.79:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 모의 안내 테두리**<br>(AdminSecurityConsole:1478) | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#1f2937` (Dark) | **2.30:1** / 5.82:1 | **FAIL**<br>(Light < 3.0:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **8.79:1** | **PASS** (>= 3.0:1) |
| **승인 ID 입력 필드 텍스트**<br>(AdminSecurityConsole:811) | `#c9d1d9` on `#f1f5f9` (Light 가상)<br>`#c9d1d9` on `#1f2937` (Dark) | **1.41:1** / 9.51:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **승인 ID 입력 필드 테두리**<br>(AdminSecurityConsole:811) | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#1f2937` (Dark) | 11.14:1 / **1.20:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |
| **파라미터 요약 텍스트**<br>(AdminSecurityConsole:1525) | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#1f2937` (Dark) | **2.81:1** / 4.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-subtle)` | **6.92:1** | **5.78:1** | **PASS** (>= 4.5:1) |
| **파라미터 요약 테두리**<br>(AdminSecurityConsole:1529) | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#1f2937` (Dark) | 11.14:1 / **1.20:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/admin/AdminSecurityConsole.tsx`
- **리터럴 감축**: 186건 -> **0건** (전수 제거, 186건 전원 해소).
- **상세 변경 사항**:
  - 모달 백드롭 오버레이: `rgba(0, 0, 0, 0.75)` 리터럴 대신 `var(--color-bg-backdrop)` 디자인 토큰으로 승격.
  - KPI 카드 및 테이블 컨테이너: `var(--color-bg-surface)` 배경 및 `var(--color-border-subtle)` 테두리 결속.
  - 비상 정지(Kill Switch) 및 노드 격리(Drain) 경고 배너: `var(--color-bg-subtle)` 배경, `var(--color-status-offline)` 텍스트 및 테두리 결속 (Light 5.91:1, Dark 5.31:1).
  - 모의 시뮬레이션 고지 배너: `var(--color-bg-subtle)` 배경, `var(--color-status-degraded)` 텍스트 및 테두리 결속 (Light 4.58:1, Dark 8.79:1).
  - 입력 필드 및 셀렉트 박스: `var(--color-bg-subtle)` 배경, `var(--color-text-primary)` 텍스트, `var(--color-border-subtle)` 테두리 결속.
  - 텍스트 강조 및 코드 블록: subtle 배경 위 다크 모드 대비 저하(3.99:1)를 원천 차단하기 위해 `var(--color-brand-primary)` 대신 `var(--color-brand-hover)` 채택 (Light 6.12:1, Dark 5.77:1).

### 3.2 `apps/web/src/index.css`
- `:root` 및 `[data-theme='dark']` 양 테마 블록에 모달 백드롭 정본 토큰 추가:
  ```css
  --color-bg-backdrop: rgba(0, 0, 0, 0.75);
  ```

### 3.3 `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **Test 9e 신설**: `AdminSecurityConsole` 컴포넌트 DOM 렌더링 검증.
  - `backend-kill-switch-status`: `var(--color-text-secondary)` on surface (Light 7.58:1, Dark 6.99:1).
  - `input-kill-switch-approval-id`: `var(--color-text-primary)` on subtle (Light 16.30:1, Dark 14.05:1), border `var(--color-border-subtle)` (Light 3.18:1, Dark 3.08:1).
  - `kill-switch-modal`: overlay `var(--color-bg-backdrop)`, title `var(--color-status-offline)` on surface (Light 6.47:1, Dark 6.41:1).
  - `kill-switch-approval-required-notice`: `var(--color-status-offline)` on subtle (Light 5.91:1, Dark 5.31:1).
  - `kill-switch-mock-notice`: `var(--color-status-degraded)` on subtle (Light 4.58:1, Dark 8.79:1).
  - `kill-switch-params-summary`: `var(--color-text-secondary)` on subtle, border `var(--color-border-subtle)`.
  - `admin-auth-required-notice`: `var(--color-status-offline)` on subtle.
- **Test 9e-2 신설**: 동적 AST 스타일 쌍 대비 계산기 및 엄격 커버리지 래칫.
  - `totalStyleAttrs`: **142**
  - `checkedObjects`: **21** (명시적 bg-fg 쌍)
  - `checkedPairs`: **244** (조건 분기 및 컨테이너 상속 조합 평가)
  - `unboundColorObjects`: **71** (컨테이너 배경 상속)
  - `coveredColorObjects`: **92** (`21 + 71`)
  - `layoutWrappers`: **50** (`142 - 92`)
  - `checkedBorderObjects`: **42**
  - `checkedBorderPairs`: **52**
  - `violations`: **0건**
- **Revert-Fail Probes 44~48 추가**:
  - Probe 44: 과거 구형 `#58a6ff`가 라이트 서피스(2.53:1) 및 서브틀(2.31:1)에서 4.5:1 미달 실측.
  - Probe 45: 과거 구형 `#8b949e`가 라이트 서피스(3.08:1) 및 서브틀(2.81:1)에서 4.5:1 미달 실측.
  - Probe 46: 과거 구형 `#f85149`가 라이트 서피스(3.35:1) 및 서브틀(3.06:1)에서 4.5:1 미달 실측.
  - Probe 47: 모달 타이틀 전경을 서피스 배경으로 치환(1:1 충돌) 시 1.0:1로 즉각 실패 실측.
  - Probe 48: 안내 배너 테두리를 서브틀 배경으로 치환(1:1 테두리 충돌) 시 1.0:1로 즉각 실패 실측.
- **Fail-Closed 래칫 갱신**:
  - `AdminSecurityConsole.tsx` multiset baseline: `{}` (0건)
  - `var(--color-border-subtle)` count / files: **317건 / 24개 파일**
  - `#30363d` upper bound: **92건 이하 / 13개 파일 이하**

---

## 4. 검증 결과

- `npx vitest run tests/acc09-contrast-tokens.test.tsx`: **18 passed (100%)**
- `npx vitest run tests/admin-security-kill-switch-wiring.test.tsx tests/admin-security.test.ts tests/defect-recovery-admin-recovery-editor.test.tsx`: **59 passed (100%)**
- `npx tsc -b`: **0 errors**
- `npm run build`: **성공 (dist production bundle 생성)**
- `pytest tests/test_route_coverage.py`: **41 passed**
- `python tools/check_frontend_integrity.py`: **0 violations**
- `python tools/check_contract_bindings.py`: **55 fixtures passed**
- `git diff --check`: **Clean (공백/줄바꿈 결함 0건)**
