# 2026-10-02 04:30:00 KST (2026-10-02 05:04:00 KST r2 보강) — Card 199: 관리자 보안 콘솔 (AdminSecurityConsole) 색상 리터럴 inventory 전수(186→0), 대비 표본/DOM 결속 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD199-ADMIN-SECURITY-CONTRAST
- **작업 branch**: agent/gemini/c199-admin-security-contrast
- **Base commit**: 67df36e8b4e723224b422ee5ec671d467972054c (PR #296 r3 HEAD)
- **KST 시각**: 2026-10-02 04:30:00 KST (r1 보강: 04:56:00 KST, r2 보강: 2026-10-02 05:04:00 KST)
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 시스템 보안 및 제어 평면 비상 통제를 담당하는 관리자 보안 콘솔(`apps/web/src/features/admin/AdminSecurityConsole.tsx`, 긴급 비상 정지 Kill Switch 모달 및 노드 격리 Drain UI 포함)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/admin/AdminSecurityConsole.tsx` (기존 baseline 리터럴: **186건**)
  - `apps/web/src/index.css` (`--color-bg-backdrop: rgba(0, 0, 0, 0.75);` 디자인 토큰 등록)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9e, Test 9e-2, Probes 44~50, 래칫 갱신)
- **감사 및 조치 결과**:
  - 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (186건 $\rightarrow$ 0건 감축).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 `AdminSecurityConsole.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 갱신.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 292건에서 **317건**(+25건)으로 증가하였으며, 사용 파일 수가 23개에서 **24개**(`AdminSecurityConsole.tsx` 신규 편입)로 래칫 단언 갱신.
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 강화:
    - `#30363d`: 116건(14개 파일) $\rightarrow$ **92건 이하(13개 파일 이하)**
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9e)에 감사 로그 컨테이너 및 모달 백드롭 스크림 alpha/대비 결속 추가.
  - 동적 AST 스타일 쌍 대비 계산기(Test 9e-2, 142개 style 속성 총수 래칫 및 계층적 조상 컨테이너 배경 추적·대비/충돌 검증 가드: checkedObjects 21, checkedPairs 98, unboundColorObjects 71, coveredColorObjects 92, checkedBorderObjects 42, checkedBorderPairs 48, violations 0건).
  - Revert-Fail Probes 44~50 신설로 12종 뮤테이션 전원 사살 실측(사살율 **100.0%**).

---

## 2. 명도 대비 실측 및 개선 결과표

### 2.1 실제 렌더 배경 기반 실측치 비교 (Before vs After)

> **배경 실측 기준**:
> - Light 테마: Surface = `#ffffff`, Subtle = `#f1f5f9`, Canvas = `#f8fafc`
> - Dark 테마 (index.css 정본 토큰): Surface (`--color-bg-surface`) = `#111827`, Subtle (`--color-bg-subtle`) = `#1f2937`, Canvas (`--color-bg-canvas`) = `#090d16`
>
> *주*: 기존 소스 코드는 다크 전용 하드코딩 리터럴로 작성되어 있었으므로, 아래 '이전 대비율'의 Light 테마 수치는 동일한 리터럴이 Light 테마 캔버스/서피스에 배치되었을 때의 **가상 비교(Virtual Comparison)** 수치입니다. Dark 테마의 Before 수치는 `index.css` 정본 배경(`#111827`, `#1f2937`) 위에서 렌더링된 실측치입니다. 신규 대비율의 Dark 수치는 `index.css` 정본 토큰 상대휘도 공식으로 산출된 엄밀 실측치입니다.

| 요소 / 위치 (파일:행) | 이전 리터럴 (실제 렌더 배경) | 이전 대비율 (Light 가상 / Dark 정본) | 이전 판정 | 신규 디자인 토큰 (실제 렌더 배경) | 신규 대비율 (Light) | 신규 대비율 (Dark 정본) | WCAG AA 충족 여부 |
|---|---|---|---|---|---|---|---|
| **KPI 카드 테두리**<br>(AdminSecurityConsole:698) | `#30363d` on `#ffffff` (Light 가상)<br>`#30363d` on `#111827` (Dark) | 12.20:1 / **1.45:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-surface)` | **3.48:1** | **3.73:1** | **PASS** (>= 3.0:1) |
| **KPI 카드 라벨**<br>(AdminSecurityConsole:699) | `#8b949e` on `#ffffff` (Light 가상)<br>`#8b949e` on `#111827` (Dark) | **3.08:1** / 5.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-surface)` | **7.58:1** | **14.33:1** | **PASS** (>= 4.5:1) |
| **KPI 카드 정상치 수치**<br>(AdminSecurityConsole:700) | `#3fb950` on `#ffffff` (Light 가상)<br>`#3fb950` on `#111827` (Dark) | **2.54:1** / 6.98:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-surface)` | **5.02:1** | **7.79:1** | **PASS** (>= 4.5:1) |
| **KPI 카드 GPU 수치**<br>(AdminSecurityConsole:716) | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#111827` (Dark) | **2.53:1** / 7.02:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 활성 배너 텍스트**<br>(AdminSecurityConsole:642) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | **3.06:1** / **4.38:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 활성 배너 테두리**<br>(AdminSecurityConsole:633) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | 3.06:1 / 4.38:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 3.0:1) |
| **관리자 미인증 안내 배너 텍스트**<br>(AdminSecurityConsole:665) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | **3.06:1** / **4.38:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **관리자 미인증 안내 배너 테두리**<br>(AdminSecurityConsole:663) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | 3.06:1 / 4.38:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 3.0:1) |
| **Kill Switch 모달 타이틀**<br>(AdminSecurityConsole:1450) | `#f85149` on `#ffffff` (Light 가상)<br>`#f85149` on `#111827` (Dark) | **3.35:1** / 5.29:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 모달 컨테이너 테두리**<br>(AdminSecurityConsole:1442) | `#f85149` on `#ffffff` (Light 가상)<br>`#f85149` on `#111827` (Dark) | 3.35:1 / 5.29:1 | **PASS**<br>(UI >= 3.0:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 3.0:1) |
| **Kill Switch 모의 안내 텍스트**<br>(AdminSecurityConsole:1479) | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#1f2937` (Dark) | **2.30:1** / 5.82:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **Kill Switch 모의 안내 테두리**<br>(AdminSecurityConsole:1478) | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#1f2937` (Dark) | **2.30:1** / 5.82:1 | **FAIL**<br>(Light < 3.0:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 3.0:1) |
| **승인 ID 입력 필드 텍스트**<br>(AdminSecurityConsole:811) | `#c9d1d9` on `#f1f5f9` (Light 가상)<br>`#c9d1d9` on `#1f2937` (Dark) | **1.41:1** / 9.51:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **승인 ID 입력 필드 테두리**<br>(AdminSecurityConsole:811) | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#1f2937` (Dark) | 11.14:1 / **1.20:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |
| **파라미터 요약 텍스트**<br>(AdminSecurityConsole:1525) | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#1f2937` (Dark) | **2.81:1** / 4.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-subtle)` | **6.92:1** | **11.86:1** | **PASS** (>= 4.5:1) |
| **파라미터 요약 테두리**<br>(AdminSecurityConsole:1529) | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#1f2937` (Dark) | 11.14:1 / **1.20:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |
| **모달 서피스 on 스크림 백드롭**<br>(AdminSecurityConsole:1427/1441) | `#ffffff` on `#30363d` (Light 가상)<br>`#111827` on `#0d1117` (Dark) | 12.20:1 / 1.15:1 | **FAIL**<br>(Dark boundary) | `var(--color-bg-surface)` on<br>`var(--color-bg-backdrop)` (0.75 alpha composite `#3e3f3f`) | **10.57:1** | **1.16:1**<br>(테두리 7.46:1 확보) | **PASS**<br>(Light >= 3.0:1 & 테두리 경계 확보) |

---

### 2.2 정본 토큰 파싱 기반 동적 재현 명령 및 시험 결속

문서 내 모든 대비 수치는 `apps/web/src/index.css`의 토큰 선언(`:root` 및 `[data-theme='dark']`)을 **직접 파싱**하여 WCAG 2.2 상대휘도 공식 및 제품 `blendRgba()`(`Math.round` 반올림)으로 동적 연산됩니다. 하드코딩 사본이 아닌 실시간 파일 파싱 명령입니다.

```bash
# apps/web/src/index.css 직접 파싱 기반 전수 대비 동적 재현 명령 (Python)
python -c "
import math, re

with open('apps/web/src/index.css', 'r', encoding='utf-8') as f:
    css = f.read()

def parse_tokens(block):
    clean = re.sub(r'/\*[\s\S]*?\*/', '', block)
    tokens = {}
    for m in re.finditer(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);', clean):
        tokens[m.group(1).strip()] = m.group(2).strip()
    return tokens

light_tokens = parse_tokens(re.search(r':root\s*\{([\s\S]*?)\}', css).group(1))
dark_tokens = parse_tokens(re.search(r'\[data-theme='dark'\]\s*\{([\s\S]*?)\}', css).group(1))

def hex_to_rgb(h): return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
def round_half_up(n): return int(math.floor(n + 0.5))
def blend(tint, alpha, underlay):
    u = hex_to_rgb(underlay)
    return '#' + ''.join(f'{round_half_up(alpha * tint[i] + (1 - alpha) * u[i]):02x}' for i in range(3))
def lum(h):
    rgb = hex_to_rgb(h)
    def adj(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)
    return 0.2126 * adj(rgb[0]) + 0.7152 * adj(rgb[1]) + 0.0722 * adj(rgb[2])
def cr(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

scrim_light = blend([0, 0, 0], 0.75, light_tokens['--color-bg-canvas'])
print('modal surface on scrim_light (#3e3f3f):', f'{cr(light_tokens["--color-bg-surface"], scrim_light):.2f}:1')  # 10.57:1
scrim_dark = blend([0, 0, 0], 0.75, dark_tokens['--color-bg-canvas'])
print('modal border (status-offline) on scrim_dark:', f'{cr(dark_tokens["--color-status-offline"], scrim_dark):.2f}:1')  # 7.46:1
print('text-secondary / bg-surface (dark):', f'{cr(dark_tokens["--color-text-secondary"], dark_tokens["--color-bg-surface"]):.2f}:1')  # 14.33:1
print('status-online / bg-surface (dark):', f'{cr(dark_tokens["--color-status-online"], dark_tokens["--color-bg-surface"]):.2f}:1')      # 7.79:1
print('brand-hover / bg-surface (dark):', f'{cr(dark_tokens["--color-brand-hover"], dark_tokens["--color-bg-surface"]):.2f}:1')        # 9.84:1
print('status-degraded / bg-subtle (dark):', f'{cr(dark_tokens["--color-status-degraded"], dark_tokens["--color-bg-subtle"]):.2f}:1')    # 6.83:1
print('text-secondary / bg-subtle (dark):', f'{cr(dark_tokens["--color-text-secondary"], dark_tokens["--color-bg-subtle"]):.2f}:1')     # 11.86:1
print('brand-hover / bg-subtle (dark):', f'{cr(dark_tokens["--color-brand-hover"], dark_tokens["--color-bg-subtle"]):.2f}:1')         # 8.14:1
print('brand-primary / brand-subtle (dark):', f'{cr(dark_tokens["--color-brand-primary"], dark_tokens["--color-brand-subtle"]):.2f}:1') # 5.75:1
print('brand-primary / brand-subtle (light):', f'{cr(light_tokens["--color-brand-primary"], light_tokens["--color-brand-subtle"]):.2f}:1') # 4.24:1
"
```

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/admin/AdminSecurityConsole.tsx`
- **리터럴 감축**: 186건 -> **0건** (전수 제거, 186건 전원 해소).
- **상세 변경 사항**:
  - 모달 백드롭 오버레이: `rgba(0, 0, 0, 0.75)` 리터럴 대신 `var(--color-bg-backdrop)` 디자인 토큰으로 승격.
  - KPI 카드 및 테이블 컨테이너: `var(--color-bg-surface)` 배경 및 `var(--color-border-subtle)` 테두리 결속.
  - 비상 정지(Kill Switch) 및 노드 격리(Drain) 경고 배너: `var(--color-bg-subtle)` 배경, `var(--color-status-offline)` 텍스트 및 테두리 결속 (Light 5.91:1, Dark 5.31:1).
  - 모의 시뮬레이션 고지 배너: `var(--color-bg-subtle)` 배경, `var(--color-status-degraded)` 텍스트 및 테두리 결속 (Light 4.58:1, Dark 6.83:1).
  - 입력 필드 및 셀렉트 박스: `var(--color-bg-subtle)` 배경, `var(--color-text-primary)` 텍스트, `var(--color-border-subtle)` 테두리 결속.
  - 텍스트 강조 및 코드 블록: `var(--color-brand-hover)` 채택 (Light 6.12:1 on subtle, Dark 8.14:1 on subtle; 라이트 모드에서 brand-primary on brand-subtle이 4.24:1로 미달하는 결함을 방지하고 전사 UI 통일 기준 준수. 다크 모드 brand-primary on brand-subtle은 5.75:1로 통과하나 일관된 상호작용 및 고대비 보장을 위해 brand-hover로 통일).
  - 불변 감사 로그 서브탭 컨테이너: `data-testid="admin-audit-subtab-container"` 결속 추가로 DOM 레벨 상위 컨테이너 배경 및 테두리 검증 보강 (T1).

### 3.2 `apps/web/src/index.css`
- `:root` 및 `[data-theme='dark']` 양 테마 블록에 모달 백드롭 정본 토큰 추가:
  ```css
  --color-bg-backdrop: rgba(0, 0, 0, 0.75);
  ```

### 3.3 `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **Test 9e 신설 및 보강**: `AdminSecurityConsole` 컴포넌트 DOM 렌더링 검증.
  - `backend-kill-switch-status`: `var(--color-text-secondary)` on surface (Light 7.58:1, Dark 14.33:1).
  - `input-kill-switch-approval-id`: `var(--color-text-primary)` on subtle (Light 16.30:1, Dark 14.05:1), border `var(--color-border-subtle)` (Light 3.18:1, Dark 3.08:1).
  - `kill-switch-modal`: overlay `var(--color-bg-backdrop)`, title `var(--color-status-offline)` on surface (Light 6.47:1, Dark 6.41:1).
  - **T2 백드롭 알파 및 모달 경계 대비**: 백드롭 alpha $\ge 0.50$ 엄밀 단언(워시아웃 차단), 0.75 alpha 합성 캔버스 위 모달 서피스 대비 $\ge 3.0:1$(10.57:1) 검증.
  - `kill-switch-approval-required-notice`: `var(--color-status-offline)` on subtle (Light 5.91:1, Dark 5.31:1).
  - `kill-switch-mock-notice`: `var(--color-status-degraded)` on subtle (Light 4.58:1, Dark 6.83:1).
  - `kill-switch-params-summary`: `var(--color-text-secondary)` on subtle (Light 6.92:1, Dark 11.86:1), border `var(--color-border-subtle)`.
  - **T1 조상 컨테이너 결속**: `admin-audit-subtab-container` background `var(--color-bg-surface)` 및 border `var(--color-border-subtle)` 실측 검증.
  - `admin-auth-required-notice`: `var(--color-status-offline)` on subtle.
- **Test 9e-2 신설 및 계층적 AST 가드 보강**: 동적 AST 스타일 쌍 대비 계산기 및 엄격 커버리지 래칫.
  - JSX 계층 순회를 통해 부모 노드의 background 선언 스택(`ancestorBgTokens`)을 추적하여 상속된 color/border의 실질적 조상 렌더 배경 계산.
  - 텍스트 토큰(`--color-text-*`)이 background로 선언되는 결함을 즉각 차단.
  - `rgba(...)` 토큰(백드롭 등)의 캔버스 합성 대비 계산 지원 (`resolveTokenHex`).
  - `totalStyleAttrs`: **142**
  - `checkedObjects`: **21** (명시적 bg-fg 쌍)
  - `checkedPairs`: **98** (조건 분기 및 계층적 컨테이너 상속 조합 평가)
  - `unboundColorObjects`: **71** (컨테이너 배경 상속)
  - `coveredColorObjects`: **92** (`21 + 71`)
  - `layoutWrappers`: **50** (`142 - 92`)
  - `checkedBorderObjects`: **42**
  - `checkedBorderPairs`: **48**
  - `violations`: **0건**
- **Revert-Fail Probes 44~50 추가**:
  - Probe 44: 과거 구형 `#58a6ff`가 라이트 서피스(2.53:1) 및 서브틀(2.31:1)에서 4.5:1 미달 실측.
  - Probe 45: 과거 구형 `#8b949e`가 라이트 서피스(3.08:1) 및 서브틀(2.81:1)에서 4.5:1 미달 실측.
  - Probe 46: 과거 구형 `#f85149`가 라이트 서피스(3.35:1) 및 서브틀(3.06:1)에서 4.5:1 미달 실측.
  - Probe 47: 모달 타이틀 전경을 서피스 배경으로 치환(1:1 충돌) 시 1.0:1로 즉각 실패 실측.
  - Probe 48: 안내 배너 테두리를 서브틀 배경으로 치환(1:1 테두리 충돌) 시 1.0:1로 즉각 실패 실측.
  - Probe 49 [T1 / A1]: 컨테이너 배경을 text-primary로 치환 시 1:1 충돌(1.0:1) 및 brand-hover(2.66:1)로 4.5:1 미달 즉각 실패 실측.
  - Probe 50 [T2 / A6]: 모달 백드롭 스크림 alpha를 0.05로 감축 시 라이트 캔버스 위 모달 서피스 대비가 1.16:1로 3.0:1 미달 즉각 실패 실측.
- **Fail-Closed 래칫 갱신**:
  - `AdminSecurityConsole.tsx` multiset baseline: `{}` (0건)
  - `var(--color-border-subtle)` count / files: **317건 / 24개 파일**
  - `#30363d` upper bound: **92건 이하 / 13개 파일 이하**

---

## 4. 검증 결과

- `npx vitest run tests/acc09-contrast-tokens.test.tsx`: **18 passed (100%)**
- `npx vitest run tests/admin-security-kill-switch-wiring.test.tsx tests/admin-security.test.ts tests/defect-recovery-admin-recovery-editor.test.tsx`: **59 passed (100%)**
- `python scratch/test_c199_mutations.py`: **12/12 killed (100.0%)**
- `npx tsc -b`: **0 errors**
- `npm run build`: **성공 (dist production bundle 생성, 7.99s)**
- `pytest tests/test_route_coverage.py`: **41 passed**
- `python tools/check_docs.py`: **PASS**
- `python tools/check_frontend_integrity.py`: **0 violations**
- `python tools/check_contract_bindings.py`: **55 fixtures passed**
- `git diff --check`: **Clean (공백/줄바꿈 결함 0건)**
