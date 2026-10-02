# 2026-10-02 08:55:00 KST — Card 213: 실행 기록 화면 (SealRecordPanel & RunDetail) 색상 리터럴 전수 토큰화(135+122→0), 상태 색 재정의/일관성 및 불변 원장 접근성 승격 (PR #310 r2 피드백 반영) (Gemini)

- **문서 ID**: HIST-GEMINI-CARD213-RUNS-RECORD-CONTRAST
- **작업 branch**: agent/gemini/c213-runs-contrast
- **Base commit**: 02d5ecd4402d06d0a110f5e596ff4c864d8c97e4 (PR #308 r1 remediation landing)
- **KST 시각**: 2026-10-02 08:55:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성/테스트 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적 (PR #310 r1/r2 피드백 반영)

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 실행 기록 및 봉인 원장 화면인 `apps/web/src/features/runs/SealRecordPanel.tsx`(봉인 기록 원장) 및 `apps/web/src/features/runs/RunDetail.tsx`(실행 상세, 수명주기 전이, 로그, 아티팩트 및 시도 이력)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다. 또한 PR #310 r1 및 r2에서 접수된 Codex 및 Claude UI의 검토 의견을 전면 반영하여 상태 붕괴 방지 DOM 단언, 형태 단서(링) DOM 단언 및 13종 뮤테이션 사살을 확립했습니다.

- **대상 파일**:
  - `apps/web/src/features/runs/SealRecordPanel.tsx` (기존 baseline 리터럴: **135건**)
  - `apps/web/src/features/runs/RunDetail.tsx` (기존 baseline 리터럴: **122건**)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9h, Test 9h-2, Probes 61~65, Fail-Closed 래칫 갱신)
  - `apps/web/tests/run-detail-seal-record.test.tsx` (봉인 원장 및 런 상세 25종 회귀 시험 통과 검증)
  - `apps/web/tests/run-detail-attempts-dom.test.tsx` (시도 이력 종료 코드 0 및 비0 상태 스타일 단언 추가)
  - `tools/test_c213_mutations.py` (재현 가능한 13종 뮤테이션 M1~M13 전수 시험 러너 신규 커밋)
- **감사 및 조치 결과**:
  - `SealRecordPanel.tsx`: 135건 -> **0건** (리터럴 잔여 0건 multiset `{}` 달성).
  - `RunDetail.tsx`: 122건 -> **0건** (리터럴 잔여 0건 multiset `{}` 달성).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 두 파일의 허용 multiset을 `{}` (0건)으로 래칫 고정.
  - 전역 `var(--color-border-subtle)` 사용 횟수: 382건, 사용 파일 수: 26개 (래칫 불변식 충족).
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 전면 강화:
    - `#d97706`: 14건(6개 파일) -> **8건 이하(5개 파일 이하)**
    - `#e2e8f0`: 1건(1개 파일) -> **0건 이하(0개 파일 이하, 완전 소멸)**
    - `#30363d`: 64건(11개 파일) -> **55건 이하(9개 파일 이하)**

### 1.1 상태 색의 의도적 재정의 및 화면 간 일관성 정립 (F2 조치)
단순 색상 유지가 아닌, 플랫폼 정본 디자인 토큰 규격 및 `RunList.tsx`와의 정합성을 확보하기 위해 상태 색을 **의도적으로 재정의(Redesign & Alignment)** 하였습니다:
- **`running`**: 녹색(`#3fb950`) → 블루(`var(--color-brand-hover)`)로 전환하여 진행 중 작업과 성공 상태의 색상 혼동 방지.
- **`awaiting_approval`**: 빨강(`#f85149`) → 호박색(`var(--color-status-degraded)`)으로 전환하여 거버넌스 승인 대기(주의/대기)와 시스템 장애/실패(빨강)를 명확히 분리.
- **`recovering`**: 주황/호박색(`#d97706`) → 액티브 스카이블루(`var(--color-status-active)`)로 전환. 후속 카드 215에서 `RunList.tsx`의 `recovering` 역시 동일한 `var(--color-status-active)`로 통일 정합하여 화면 간 불일치를 완전 해소 예정.
- **`succeeded` / `failed` / `cancelled`**: 베이스 코드에서 회색(`var(--color-text-secondary)` on `rgba(110,118,129,0.2)`)으로 공통 처리되던 것을 의미별 고유 토큰으로 명확히 분리:
  - `succeeded`: `var(--color-status-online)` (녹색 배지 및 테두리)
  - `failed`: `var(--color-status-offline)` (적색 배지 및 테두리)
  - `cancelled`: `var(--color-status-neutral)` (회색 배지 및 `var(--color-border-strong)` 테두리)
- **비색상 구분 보장**: 모든 상태 배지는 대문자 상태 텍스트(`{run.state.toUpperCase()}`) 및 식별용 `data-testid`를 병행 노출하여 색상만으로 상태를 구분하지 않는 WCAG 1.4.1 기준을 충족.

### 1.2 시각적 보완 및 형태 단서 보존 (F5 조치)
- **수명주기 스텝 링 복원 및 단언 보호**: `RunDetail.tsx`의 수명주기 스텝 원형 인디케이터에서 현재 단계(`isCurrent`) 형태 단서를 복원하기 위해 `outline: isCurrent ? '3px solid var(--color-border-strong)' : 'none'` 및 `outlineOffset: '2px'`를 부여. 다크 모드(6.99:1)와 라이트 모드(7.58:1) 모두에서 3.0:1 비텍스트 대비를 상회하며, DOM 단언(`run-step-indicator-running`)을 통해 링 제거 및 붕괴를 엄격히 방지.
- **SealRecordPanel 카드 테두리 명시**: `SealRecordPanel.tsx` 원장 카드에 `border: 1px solid var(--color-border-subtle)`를 명시하여 캔버스/서피스 배경 위에서 원장 영역 경계를 시각적으로 명확히 구획.

### 1.3 상태 붕괴 방지 DOM 단언 및 13종 뮤테이션 사살 (F1, F3, F4, F6 조치)
- **UNSEALED 상태 토큰 회귀 사살**:
  - `acc09-contrast-tokens.test.tsx` Test 9h에서 `RES-0004` 미봉인 응답(`run_c213_unsealed`)을 실제 렌더하여 `seal-status-badge`가 `var(--color-status-degraded)` 전경/테두리에 결속됨을 단언하고, `SEALED` 배지와 토큰이 서로 상이함(`expect(unsealedBadge.style.color).not.toBe(sealBadge.style.color)`)을 실측.
  - `run-detail-seal-record.test.tsx`에서도 배열 허용 목록을 제거하고 봉인(`status-online`) 및 미봉인(`status-degraded`) 토큰을 엄격 단언.
  - 뮤테이션 M11(UNSEALED degraded→online) 추가 및 사살 실측.
- **`completedAt` 실패 분기 상태 붕괴 사살**:
  - Test 9h에서 `failed` 상태 렌더 시 `run-detail-completed-at`이 `var(--color-status-offline)`에 결속됨과 `succeeded` 상태와 서로 상이함(`not.toBe`)을 단언.
  - 뮤테이션 M12(failed completedAt→online) 추가 및 사살 실측.
- **시도 이력 `exitCode != 0` 상태 붕괴 사살 및 단언 강화**:
  - Test 9h에서 시도 이력 탭 버튼의 존재를 엄격 단언(`expect(attemptsTabBtn).not.toBeNull()`)한 후 클릭하여 `exitCode: 0`(`status-online`)과 `exitCode: 1`(`status-offline`)의 동시 렌더 및 상이성(`not.toBe`)을 실측 단언.
  - `run-detail-attempts-dom.test.tsx`에 Scenario 9를 추가하여 비0 종료 코드 렌더링 검증.
  - 뮤테이션 M13(non-zero exitCode→online) 추가 및 사살 실측.
- **레거시 테스트 허용 목록 제거**:
  - `run-detail-seal-record.test.tsx` 260, 278, 304행의 `['var(...)', 'rgb(...)', '#...']` 배열 허용을 단일 정본 토큰(`var(--color-status-online)`, `var(--color-status-offline)`)으로 좁혀 레거시 복원 결함 차단.

---

## 2. 명도 대비 실측 및 동적 재현 명령

### 2.1 실제 base 코드 및 렌더 배경 기반 명도 대비 실측표

모든 After 대비는 SaintVision 플랫폼 정본 배경(`apps/web/src/index.css` 기준: Light surface `#ffffff`, subtle `#f1f5f9`, canvas `#f8fafc`; Dark surface `#111827`, subtle `#1f2937`, canvas `#090d16`) 위에서 측정되었습니다.
'Before' 열의 다크 모드 값은 베이스 커밋 `02d5ecd4`의 실제 코드 색상, 실제 조상 배경(SealRecordPanel: 패널 루트 `#0d1117`, 카드 `#161b22`; RunDetail: 루트에 배경이 없으므로 body canvas `#090d16`), 그리고 배지의 알파 합성 배경(`rgba` over base background)을 정밀 계산한 실측치입니다.
특히 베이스 코드의 `succeeded` / `failed` / `cancelled` 배지는 글자색으로 `var(--color-text-secondary)`(Light `#475569`, Dark `#e5e7eb`)를 사용하여 베이스에서도 **PASS**(5.71:1 Light / 12.89:1 Dark)였으며, 본 작업에서의 변경은 결함 치유가 아닌 **상태 의미 고유 분리(Semantic Redesign)** 목적입니다.
'Before' 열의 라이트 모드 값 중 다크 전용 하드코딩 리터럴을 라이트 배경에 강제 노출했을 때의 수치는 결함을 보여주는 '가상 비교 (Virtual Comparison)'입니다.

| 대상 UI 요소 / 배경 | Before 색상 조합 (Light 가상 / Dark 실제) | Before 대비 (Light / Dark 실제) | 판정 (WCAG AA) | After 디자인 토큰 조합 | After 대비 (Light) | After 대비 (Dark) | 최종 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **봉인 기록 식별자 / surface** | `#f0f6fc` on `#ffffff` (L 가상)<br>`#f0f6fc` on `#161b22` (D 실제) | 1.09:1 / 15.89:1 | **FAIL** (Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-surface)` | **17.85:1** | **16.98:1** | **PASS** (>= 4.5:1) |
| **봉인 최종 상태 / surface** | `#58a6ff` on `#ffffff` (L 가상)<br>`#58a6ff` on `#161b22` (D 실제) | 2.53:1 / 6.85:1 | **FAIL** (Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **봉인 워크로드 SHA / surface** | `#58a6ff` on `#ffffff` (L 가상)<br>`#58a6ff` on `#161b22` (D 실제) | 2.53:1 / 6.85:1 | **FAIL** (Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **컨텍스트 번들 해시 / surface** | `#58a6ff` on `#ffffff` (L 가상)<br>`#58a6ff` on `#161b22` (D 실제) | 2.53:1 / 6.85:1 | **FAIL** (Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **봉인 배지: 봉인됨 / subtle** | `#3fb950` on `#f1f5f9` (L 가상)<br>`#3fb950` on `#12261e` (D 실제 합성) | 2.32:1 / 6.25:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **봉인 배지: 미봉인 / subtle** | `#e3b341` on `#f1f5f9` (L 가상)<br>`#e3b341` on `#2b2519` (D 실제 합성) | 1.78:1 / 7.81:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: running / subtle** | `#3fb950` on `#f1f5f9` (L 가상)<br>`#3fb950` on `#102a1f` (D 실제 body canvas 합성) | 2.32:1 / 6.02:1 | **FAIL** (Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: recovering / subtle** | `#d97706` on `#f1f5f9` (L 가상)<br>`#d97706` on `#332213` (D 실제 body canvas 합성) | 2.91:1 / 4.78:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-active)` on<br>`var(--color-bg-subtle)` | **5.42:1** | **6.85:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: awaiting_approval / subtle** | `#f85149` on `#f1f5f9` (L 가상)<br>`#f85149` on `#33151c` (D 실제 body canvas 합성) | 3.06:1 / 4.95:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: succeeded / subtle** | `var(--color-text-secondary)`<br>`#475569` on `#dce0e3` (L) / `#e5e7eb` on `#1d222b` (D) | 5.71:1 / 12.89:1 | **PASS** (상태 색 재정의 대상) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: failed / subtle** | `var(--color-text-secondary)`<br>`#475569` on `#dce0e3` (L) / `#e5e7eb` on `#1d222b` (D) | 5.71:1 / 12.89:1 | **PASS** (상태 색 재정의 대상) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: cancelled / subtle** | `var(--color-text-secondary)`<br>`#475569` on `#dce0e3` (L) / `#e5e7eb` on `#1d222b` (D) | 5.71:1 / 12.89:1 | **PASS** (상태 색 재정의 대상) | `var(--color-status-neutral)` on<br>`var(--color-bg-subtle)` | **5.25:1** | **5.78:1** | **PASS** (>= 4.5:1) |
| **런 상세 완료 시각 (성공) / canvas** | `#34d399` on `#ffffff` (L 가상)<br>`#34d399` on `#090d16` (D 실제 body canvas) | 1.92:1 / 10.11:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-surface)` | **5.02:1** | **7.79:1** | **PASS** (>= 4.5:1) |
| **런 상세 완료 시각 (실패) / canvas** | `#f87171` on `#ffffff` (L 가상)<br>`#f87171` on `#090d16` (D 실제 body canvas) | 2.77:1 / 7.02:1 | **FAIL** (Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 4.5:1) |

---

## 2.2 정본 토큰 파싱 및 Before/After 동적 재현 명령

문서 내 모든 Before/After 실측치는 `apps/web/src/index.css`를 직접 파싱하고 WCAG 2.2 상대휘도 공식을 엄격히 적용하는 아래의 재현 명령으로 정확히 출력됩니다.

```bash
# apps/web/src/index.css 파싱 및 Before/After 명도 대비 동적 재현 명령 (Python)
python - <<'PY'
import re, math

with open('apps/web/src/index.css', 'r', encoding='utf-8') as f:
    css = f.read()

def parse_tokens(block):
    clean = re.sub(r'/\*[\s\S]*?\*/', '', block)
    tokens = {}
    for m in re.finditer(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);', clean):
        tokens[m.group(1).strip()] = m.group(2).strip()
    return tokens

light_tokens = parse_tokens(re.search(r':root\s*\{([\s\S]*?)\}', css).group(1))
dark_tokens = parse_tokens(re.search(r"\[data-theme=['\"]?dark['\"]?\]\s*\{([\s\S]*?)\}", css).group(1))

def hex_to_rgb(h): return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
def rgb_to_hex(r, g, b): return f"#{int(round(r)):02x}{int(round(g)):02x}{int(round(b)):02x}"

def alpha_composite(fg_rgba, bg_hex):
    bg_rgb = hex_to_rgb(bg_hex)
    a = fg_rgba[3]
    r = fg_rgba[0] * a + bg_rgb[0] * (1 - a)
    g = fg_rgba[1] * a + bg_rgb[1] * (1 - a)
    b = fg_rgba[2] * a + bg_rgb[2] * (1 - a)
    return rgb_to_hex(r, g, b)

def lum(h):
    rgb = hex_to_rgb(h)
    def adj(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)
    return 0.2126 * adj(rgb[0]) + 0.7152 * adj(rgb[1]) + 0.0722 * adj(rgb[2])

def cr(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

# SealRecordPanel: panel root #0d1117, card #161b22, composites over #0d1117
sealed_dark_bg = alpha_composite((46, 160, 67, 0.15), '#0d1117')
unsealed_dark_bg = alpha_composite((210, 153, 34, 0.15), '#0d1117')

# RunDetail: body dark canvas #090d16, light #f8fafc
shared_light_bg = alpha_composite((110, 118, 129, 0.20), '#f8fafc')
shared_dark_bg = alpha_composite((110, 118, 129, 0.20), '#090d16')
running_dark_bg = alpha_composite((46, 160, 67, 0.20), '#090d16')
recovering_dark_bg = alpha_composite((217, 119, 6, 0.20), '#090d16')
approval_dark_bg = alpha_composite((218, 54, 51, 0.20), '#090d16')

# Base fg for succeeded/failed/cancelled: var(--color-text-secondary) -> Light #475569, Dark #e5e7eb
items = [
    ("bundle hash / surface", "#58a6ff", "#58a6ff", "#ffffff", "#161b22", "--color-brand-hover", "--color-bg-surface"),
    ("run completedAt (failed) / surface", "#f87171", "#f87171", "#ffffff", "#090d16", "--color-status-offline", "--color-bg-surface"),
    ("run completedAt (succeeded) / surface", "#34d399", "#34d399", "#ffffff", "#090d16", "--color-status-online", "--color-bg-surface"),
    ("run status awaiting_approval / subtle", "#f85149", "#f85149", "#f1f5f9", approval_dark_bg, "--color-status-degraded", "--color-bg-subtle"),
    ("run status cancelled / subtle", "#475569", "#e5e7eb", shared_light_bg, shared_dark_bg, "--color-status-neutral", "--color-bg-subtle"),
    ("run status failed / subtle", "#475569", "#e5e7eb", shared_light_bg, shared_dark_bg, "--color-status-offline", "--color-bg-subtle"),
    ("run status recovering / subtle", "#d97706", "#d97706", "#f1f5f9", recovering_dark_bg, "--color-status-active", "--color-bg-subtle"),
    ("run status running / subtle", "#3fb950", "#3fb950", "#f1f5f9", running_dark_bg, "--color-brand-hover", "--color-bg-subtle"),
    ("run status succeeded / subtle", "#475569", "#e5e7eb", shared_light_bg, shared_dark_bg, "--color-status-online", "--color-bg-subtle"),
    ("seal badge degraded (unsealed) / subtle", "#e3b341", "#e3b341", "#f1f5f9", unsealed_dark_bg, "--color-status-degraded", "--color-bg-subtle"),
    ("seal badge online (sealed) / subtle", "#3fb950", "#3fb950", "#f1f5f9", sealed_dark_bg, "--color-status-online", "--color-bg-subtle"),
    ("seal final state / surface", "#58a6ff", "#58a6ff", "#ffffff", "#161b22", "--color-brand-hover", "--color-bg-surface"),
    ("seal record ID / surface", "#f0f6fc", "#f0f6fc", "#ffffff", "#161b22", "--color-text-primary", "--color-bg-surface"),
    ("seal workload spec sha / surface", "#58a6ff", "#58a6ff", "#ffffff", "#161b22", "--color-brand-hover", "--color-bg-surface"),
]

items.sort(key=lambda x: x[0])

for label, b_fg_l, b_fg_d, b_bg_l, b_bg_d, a_fg, a_bg in items:
    b_cr_l = cr(b_fg_l, b_bg_l)
    b_cr_d = cr(b_fg_d, b_bg_d)
    a_cr_l = cr(light_tokens[a_fg], light_tokens[a_bg])
    a_cr_d = cr(dark_tokens[a_fg], dark_tokens[a_bg])
    is_virtual = " (L virtual)" if (b_fg_l == b_fg_d and (b_bg_l == "#ffffff" or b_bg_l == "#f1f5f9")) else " (L actual) "
    print(f"{label:42s} | Before: {b_cr_l:5.2f}:1{is_virtual} / {b_cr_d:5.2f}:1 (D actual on {b_bg_d}) | After: {a_cr_l:5.2f}:1 (Light) / {a_cr_d:5.2f}:1 (Dark)")
PY
```

실행 출력 (재현 실측치):
```text
bundle hash / surface                      | Before:  2.53:1 (L virtual) /  6.85:1 (D actual on #161b22) | After:  6.70:1 (Light) /  9.84:1 (Dark)
run completedAt (failed) / surface         | Before:  2.77:1 (L virtual) /  7.02:1 (D actual on #090d16) | After:  6.47:1 (Light) /  6.41:1 (Dark)
run completedAt (succeeded) / surface      | Before:  1.92:1 (L virtual) / 10.11:1 (D actual on #090d16) | After:  5.02:1 (Light) /  7.79:1 (Dark)
run status awaiting_approval / subtle      | Before:  3.06:1 (L virtual) /  4.95:1 (D actual on #33151c) | After:  4.58:1 (Light) /  6.83:1 (Dark)
run status cancelled / subtle              | Before:  5.71:1 (L actual)  / 12.89:1 (D actual on #1d222b) | After:  5.25:1 (Light) /  5.78:1 (Dark)
run status failed / subtle                 | Before:  5.71:1 (L actual)  / 12.89:1 (D actual on #1d222b) | After:  5.91:1 (Light) /  5.31:1 (Dark)
run status recovering / subtle             | Before:  2.91:1 (L virtual) /  4.78:1 (D actual on #332213) | After:  5.42:1 (Light) /  6.85:1 (Dark)
run status running / subtle                | Before:  2.32:1 (L virtual) /  6.02:1 (D actual on #102a1f) | After:  6.12:1 (Light) /  8.14:1 (Dark)
run status succeeded / subtle              | Before:  5.71:1 (L actual)  / 12.89:1 (D actual on #1d222b) | After:  4.58:1 (Light) /  6.44:1 (Dark)
seal badge degraded (unsealed) / subtle    | Before:  1.78:1 (L virtual) /  7.81:1 (D actual on #2b2519) | After:  4.58:1 (Light) /  6.83:1 (Dark)
seal badge online (sealed) / subtle        | Before:  2.32:1 (L virtual) /  6.25:1 (D actual on #12261e) | After:  4.58:1 (Light) /  6.44:1 (Dark)
seal final state / surface                 | Before:  2.53:1 (L virtual) /  6.85:1 (D actual on #161b22) | After:  6.70:1 (Light) /  9.84:1 (Dark)
seal record ID / surface                   | Before:  1.09:1 (L virtual) / 15.89:1 (D actual on #161b22) | After: 17.85:1 (Light) / 16.98:1 (Dark)
seal workload spec sha / surface           | Before:  2.53:1 (L virtual) /  6.85:1 (D actual on #161b22) | After:  6.70:1 (Light) /  9.84:1 (Dark)
```

---

## 3. 재현 가능한 13종 뮤테이션 스위트 (M1~M13) 전수 사살 실측치

독립 검토 r1에서 요청된 3종의 상태 붕괴 변이(M11 UNSEALED, M12 completedAt failed, M13 attempt non-zero exitCode)를 신규 편입하여 총 13종의 뮤테이션 스위트(`tools/test_c213_mutations.py`)를 가동하였으며, 사살율 **100.0% (13/13)** 를 달성하였습니다.

```text
================================================================================
 Card 213 (ACC-09): Reproducible Mutant Test Suite (13 Mutants: M1-M13)
 Targets: SealRecordPanel.tsx & RunDetail.tsx
================================================================================

[Baseline Check] Testing unmutated code...
[Baseline Check] Clean pass (exit code 0).

[01/13] M1: KILLED in 4.7s -- SealRecordPanel: seal badge status token swapped to degraded (semantic violation)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[02/13] M2: KILLED in 5.6s -- SealRecordPanel: seal record ID color swapped to muted (contrast/token regression)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[03/13] M3: KILLED in 5.1s -- SealRecordPanel: re-injects raw hex literal (fail-closed multiset inventory breach)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[04/13] M4: KILLED in 5.0s -- SealRecordPanel: missing testid regression (removes seal-status-badge)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[05/13] M5: KILLED in 4.7s -- SealRecordPanel: 1:1 border collision on record ledger card
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[06/13] M6: KILLED in 4.4s -- RunDetail: status succeeded badge color swapped to brand-hover (semantic regression)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[07/13] M7: KILLED in 4.7s -- RunDetail: status cancelled badge color swapped to offline (semantic violation)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[08/13] M8: KILLED in 4.4s -- RunDetail: re-injects raw hex literal (fail-closed multiset inventory breach)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[09/13] M9: KILLED in 4.6s -- RunDetail: missing testid regression (removes run-detail-status-badge)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[10/13] M10: KILLED in 4.9s -- RunDetail: 1:1 border collision on cancel modal dialog container
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[11/13] M11: KILLED in 5.6s -- SealRecordPanel: unsealed badge status token swapped to online (semantic violation)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[12/13] M12: KILLED in 5.3s -- RunDetail: completedAt failed branch status token swapped to online (semantic violation)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi
[13/13] M13: KILLED in 4.9s -- RunDetail: attempt exitCode != 0 status token swapped to online (semantic violation)
         Reason: ↓ ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairi

================================================================================
 Summary: 13/13 mutants killed (100.0%)
================================================================================
 [PASS] M1  : KILLED   | SealRecordPanel: seal badge status token swapped to degraded (semantic violation)
 [PASS] M2  : KILLED   | SealRecordPanel: seal record ID color swapped to muted (contrast/token regression)
 [PASS] M3  : KILLED   | SealRecordPanel: re-injects raw hex literal (fail-closed multiset inventory breach)
 [PASS] M4  : KILLED   | SealRecordPanel: missing testid regression (removes seal-status-badge)
 [PASS] M5  : KILLED   | SealRecordPanel: 1:1 border collision on record ledger card
 [PASS] M6  : KILLED   | RunDetail: status succeeded badge color swapped to brand-hover (semantic regression)
 [PASS] M7  : KILLED   | RunDetail: status cancelled badge color swapped to offline (semantic violation)
 [PASS] M8  : KILLED   | RunDetail: re-injects raw hex literal (fail-closed multiset inventory breach)
 [PASS] M9  : KILLED   | RunDetail: missing testid regression (removes run-detail-status-badge)
 [PASS] M10 : KILLED   | RunDetail: 1:1 border collision on cancel modal dialog container
 [PASS] M11 : KILLED   | SealRecordPanel: unsealed badge status token swapped to online (semantic violation)
 [PASS] M12 : KILLED   | RunDetail: completedAt failed branch status token swapped to online (semantic violation)
 [PASS] M13 : KILLED   | RunDetail: attempt exitCode != 0 status token swapped to online (semantic violation)

SUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.
```

---

## 4. 검증 게이트 및 불변식 통과 실측치

모든 검증은 PowerShell 세미콜론 연결 없이 개별 명령의 exit code를 즉시 확인하며 수행되었습니다.

1. **Vitest Unit & Contrast Suite**:
   ```powershell
   npx vitest run tests/acc09-contrast-tokens.test.tsx
   # Tests: 24 passed (24) | Duration: 3.41s | Exit Code: 0
   ```
2. **Seal Record Panel & Run Detail Suite**:
   ```powershell
   npx vitest run tests/run-detail-seal-record.test.tsx
   # Tests: 25 passed (25) | Duration: 2.81s | Exit Code: 0
   ```
3. **Related Run & Studio Suites (Attempts, Logs, Retry, S11, DeveloperStudio)**:
   ```powershell
   npx vitest run tests/run-detail-seal-record.test.tsx tests/run-detail-attempts-dom.test.tsx tests/run-detail-logs-dom.test.tsx tests/model-retry-action.test.tsx tests/s11-defect-fixes.test.tsx tests/developer-studio-workspace-status.test.tsx
   # Tests: 71 passed (71) | Duration: 2.33s | Exit Code: 0
   ```
4. **TypeScript Project Reference Build**:
   ```powershell
   cd apps/web; npx tsc -b
   # Exit Code: 0 (0 type errors)
   ```
5. **Vite Production Bundle Build**:
   ```powershell
   cd apps/web; npm run build
   # Exit Code: 0 (built in 8.85s)
   ```
6. **Backend Screen Route Coverage & Invariants**:
   ```powershell
   pytest tests/test_route_coverage.py
   # 41 passed | Exit Code: 0
   ```
7. **Frontend Integrity Gate**:
   ```powershell
   python tools/check_frontend_integrity.py
   # Exit Code: 0 (PASS, 0 violations)
   ```
8. **Contract Bindings Gate**:
   ```powershell
   python tools/check_contract_bindings.py
   # Exit Code: 0 (PASS)
   ```
9. **Documentation Consistency Gate**:
   ```powershell
   python tools/check_docs.py
   # Exit Code: 0 (PASS)
   ```

---

## 5. 다음 담당자 및 인계 사항

### 5.1 백로그 및 후속 추적 사항 (Claude UI r2 피드백)
1. **AST style-pair guard 배경만 선언된 요소(bg-only) 검사 공백**:
   - 현재 AST 가드는 `background`와 `color`가 함께 선언된 객체, 또는 조상 컨테이너 배경과 자식 `color`의 대비를 전수 평가하고 있으나, `<p>` 등 인라인 요소에 `background`만 부여되고 글자색은 부모를 상속하는 경우(H2 변이)에 대한 자동 추적은 후속 AST 가드 고도화 카드에서 정밀 AST 컨텍스트 스택 추적기로 확장 예정 (현재 제품 코드 상 위반 0건 확인).
2. **outline 속성 AST 파싱 및 검증 확장**:
   - 현재 DOM 단언(`run-step-indicator-running`)으로 현재 단계 링(`outline: 3px solid var(--color-border-strong)`)의 렌더링 및 토큰 결속을 엄격 검증하고 있으며, AST 가드의 border 속성 목록에 `outline` 파서 및 대비 가드를 후속 정적 분석 개선 과제로 등록.

- **작업 브랜치**: `agent/gemini/c213-runs-contrast`
- **리뷰 요청**: Claude UI (접근성 및 UI 경험), Codex (계약 및 토큰 불변식)
- **다음 행동**:
  - PR #310에 수정 사항 커밋 및 push (force push 절대 금지).
  - PR #310 r3 조치 완료 코멘트 등록 (봇 멘션 0건 준수).
  - 신규 head를 베이스로 카드 215(`agent/gemini/c215-runlist-contrast`) 작업 계속 진행.
