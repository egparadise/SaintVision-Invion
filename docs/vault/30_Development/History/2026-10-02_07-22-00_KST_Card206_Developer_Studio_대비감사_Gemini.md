# 2026-10-02 07:22:00 KST — Card 206: 개발 스튜디오 화면 (DeveloperStudio) 색상 리터럴 inventory 전수(174→0), 대비 표본/DOM 결속 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD206-DEVELOPER-STUDIO-CONTRAST
- **작업 branch**: agent/gemini/c206-developer-studio-contrast
- **Base commit**: b78b3b041b142caa298470af8f0e8f88b797f6f5 (PR #301 HEAD with Train 14 tip d0b2a4c6 merged)
- **KST 시각**: 2026-10-02 07:22:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 개발 스튜디오 화면(`apps/web/src/features/studio/DeveloperStudio.tsx`, 코드 에디터·diff 뷰어·배치 시뮬레이터·실행 세션 터미널 및 승인 워크플로 포함)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/studio/DeveloperStudio.tsx` (기존 baseline 리터럴: **174건**)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9g, Test 9g-2, Probes 58~60, 래칫 갱신)
  - `tools/test_c206_mutations.py` (재현 가능한 10종 뮤테이션 M1~M10 전수 시험 러너 신규 커밋)
- **감사 및 조치 결과**:
  - 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (174건 -> 0건 감축, 리터럴 잔여 0건).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 `DeveloperStudio.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 고정.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 346건에서 **356건**(+10건)으로 증가하였으며, 사용 파일 수는 **25개** 유지.
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 강화:
    - `#30363d`: 66건(12개 파일) -> **64건 이하(11개 파일 이하)**
  - 결함 시정:
    - 배치 비적격 노드 카드의 `opacity: isNodeSchedulable ? 1 : 0.75`를 제거하여 subtle 배경 위 muted 텍스트 명도 저하(3.94:1 < 4.5:1) 원천 차단. 비적격 안내는 `var(--color-status-degraded)` 경고 배지로 시맨틱 및 명도 대비 동시 보장.
    - 활성 탭의 `borderBottom: '1px solid var(--color-bg-surface)'`가 surface 배경과 1:1 충돌(대비 1.0:1)하던 결함을 `borderBottom: '1px solid transparent'`로 교정하여 1:1 충돌 원천 차단.
    - `projects = React.useMemo(() => [project], [project])` 메모이제이션으로 매 렌더마다 새 참조 생성으로 인한 `useEffect` 무한 재렌더링 루프 원천 차단.
    - `readiness.blockedBy?.join(', ') || '없음'` safe navigation 적용으로 Step 2 미서명/블록 사유 미정의 시 런타임 TypeError 원천 차단.
    - Step 4 실행 세션 배지의 완료 시각 판정에 `currentRun?.completedAt`을 추가하여 liveRun 폴링 완료 시각 실시간 동기화.
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9g):
    - Stepper 4단계 진행 및 활성/완료 상태 단언.
    - 실행 세션 상태 배지(running, succeeded, failed, awaiting_approval)의 전경색/배경색/테두리색 및 dynamic 명도 대비 단언 (텍스트 >= 4.5:1, 테두리 >= 3.0:1).
    - 노드 칩 및 배치 비적격 카드 경고 배지 단언.
    - Step 2 readiness warning 배너 단언.
    - Step 4 터미널 탭 및 출력 텍스트 단언.
  - 계층적 조상 컨테이너 추적 및 불투명도(opacity) 합성 기반 동적 AST 스타일-쌍 대비 계산기(Test 9g-2):
    - totalStyleAttrs: 252개
    - checkedObjects: 36개
    - checkedPairs: 156개
    - unboundColorObjects: 92개
    - coveredColorObjects: 128개 (36 + 92)
    - checkedBorderObjects: 68개
    - checkedBorderPairs: 92개
    - violations: 0건
  - Revert-Fail Probes 58~60 신설 및 `tools/test_c206_mutations.py` 신규 커밋으로 10종 뮤테이션(M1~M10) 전원 사살 실측 (사살율 **100.0%**, exit code 0).

---

## 2. 명도 대비 실측 및 동적 재현 명령

### 2.1 실제 렌더 배경 기반 대표 표본 명도 대비 실측표

모든 대비는 SaintVision 플랫폼 정본 배경(`apps/web/src/index.css` 기준: Light surface `#ffffff`, subtle `#f1f5f9`, canvas `#ffffff`; Dark surface `#111827`, subtle `#1f2937`, canvas `#030712`) 위에서 측정되었습니다. 'Before' 열의 라이트 모드 값은 이전 코드가 다크 전용 하드코딩 색상을 라이트 배경에 강제 노출했을 때의 결함을 보여주는 '가상 비교 (Virtual Comparison)'입니다.

| 대상 UI 요소 | Before 색상 조합 (Light / Dark) | Before 명도 대비 (Light / Dark) | 판정 (WCAG AA) | After 디자인 토큰 조합 | After 명도 대비 (Light) | After 명도 대비 (Dark) | 최종 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **스텝퍼 활성 테두리** | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 3.0:1) | `var(--color-brand-primary)` on<br>`var(--color-bg-canvas)` | **4.94:1** | **7.64:1** | **PASS** (>= 3.0:1) |
| **스텝퍼 비활성 원형 글자** | `#30363d` on `#ffffff` (Light 가상)<br>`#30363d` on `#0d1117` (Dark) | 12.20:1 / 1.45:1 | **FAIL**<br>(Dark < 3.0:1) | `var(--color-text-inverse)` on<br>`var(--color-border-strong)` | **7.58:1** | **7.03:1** | **PASS** (>= 4.5:1) |
| **스튜디오 노드 칩 글자** | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#0d1117` (Dark) | 2.81:1 / 6.15:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **비적격 카드 경고 텍스트** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **비적격 카드 뮤트 텍스트 (opacity 0.75 제거)** | `#64748b` on `#f1f5f9` (opacity 0.75)<br>`#94a3b8` on `#1f2937` (opacity 0.75) | 3.94:1 / 4.41:1 | **FAIL**<br>(< 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-subtle)` (opacity 1.0) | **4.67:1** | **5.75:1** | **PASS** (>= 4.5:1) |
| **활성 탭 하단 테두리** | `#ffffff` on `#ffffff` (Light 충돌)<br>`#111827` on `#111827` (Dark 충돌) | 1.0:1 / 1.0:1 | **FAIL**<br>(1:1 충돌 < 3.0:1) | `transparent` | N/A (투명) | N/A (투명) | **PASS** (충돌 해소) |
| **상태 배지: running (진행중)** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **상태 배지: succeeded (성공)** | `#3fb950` on `#f1f5f9` (Light 가상)<br>`#3fb950` on `#0d1117` (Dark) | 2.45:1 / 7.45:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **상태 배지: failed (실패)** | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#0d1117` (Dark) | 3.06:1 / 5.65:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **상태 배지: awaiting_approval (승인대기)** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **Step 2 미준비 경고 배너 텍스트** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **Step 4 터미널 출력 텍스트** | `#f0f6fc` on `#f1f5f9` (Light 가상)<br>`#f0f6fc` on `#0d1117` (Dark) | 1.01:1 / 17.39:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-canvas)` | **17.06:1** | **18.59:1** | **PASS** (>= 4.5:1) |

---

### 2.2 정본 토큰 파싱 기반 동적 재현 명령 및 시험 결속

문서 내 대표 토큰 조합 실측치는 `apps/web/src/index.css`의 토큰 선언(`:root` 및 `[data-theme='dark']`)을 **직접 파싱**하여 WCAG 2.2 상대휘도 공식으로 동적 연산됩니다.

```bash
# apps/web/src/index.css 직접 파싱 기반 대표 토큰 대비 동적 재현 명령 (Python)
python - <<'PY'
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
dark_tokens = parse_tokens(re.search(r"\[data-theme='dark'\]\s*\{([\s\S]*?)\}", css).group(1))

def hex_to_rgb(h): return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]
def blend_rgba(tint, alpha, underlay):
    u = hex_to_rgb(underlay)
    r = round(alpha * tint[0] + (1 - alpha) * u[0])
    g = round(alpha * tint[1] + (1 - alpha) * u[1])
    b = round(alpha * tint[2] + (1 - alpha) * u[2])
    return f'#{r:02x}{g:02x}{b:02x}'

def lum(h):
    rgb = hex_to_rgb(h)
    def adj(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)
    return 0.2126 * adj(rgb[0]) + 0.7152 * adj(rgb[1]) + 0.0722 * adj(rgb[2])

def cr(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

print('stepper active border / canvas (light):', f'{cr(light_tokens["--color-brand-primary"], light_tokens["--color-bg-canvas"]):.2f}:1')
print('stepper active border / canvas (dark):', f'{cr(dark_tokens["--color-brand-primary"], dark_tokens["--color-bg-canvas"]):.2f}:1')
print('stepper inactive circle text / strong bg (light):', f'{cr(light_tokens["--color-text-inverse"], light_tokens["--color-border-strong"]):.2f}:1')
print('stepper inactive circle text / strong bg (dark):', f'{cr(dark_tokens["--color-text-inverse"], dark_tokens["--color-border-strong"]):.2f}:1')
print('node chip text / subtle (light):', f'{cr(light_tokens["--color-text-primary"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('node chip text / subtle (dark):', f'{cr(dark_tokens["--color-text-primary"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('status running badge / subtle (light):', f'{cr(light_tokens["--color-brand-hover"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('status running badge / subtle (dark):', f'{cr(dark_tokens["--color-brand-hover"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('status succeeded badge / subtle (light):', f'{cr(light_tokens["--color-status-online"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('status succeeded badge / subtle (dark):', f'{cr(dark_tokens["--color-status-online"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('status failed badge / subtle (light):', f'{cr(light_tokens["--color-status-offline"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('status failed badge / subtle (dark):', f'{cr(dark_tokens["--color-status-offline"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('status awaiting_approval badge / subtle (light):', f'{cr(light_tokens["--color-status-degraded"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('status awaiting_approval badge / subtle (dark):', f'{cr(dark_tokens["--color-status-degraded"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('readiness warning text / subtle (light):', f'{cr(light_tokens["--color-status-degraded"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('readiness warning text / subtle (dark):', f'{cr(dark_tokens["--color-status-degraded"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('terminal output text / canvas (light):', f'{cr(light_tokens["--color-text-primary"], light_tokens["--color-bg-canvas"]):.2f}:1')
print('terminal output text / canvas (dark):', f'{cr(dark_tokens["--color-text-primary"], dark_tokens["--color-bg-canvas"]):.2f}:1')
PY
```

**실제 실행 콘솔 출력 (exit code 0 실측)**:
```text
stepper active border / canvas (light): 4.94:1
stepper active border / canvas (dark): 7.64:1
stepper inactive circle text / strong bg (light): 7.58:1
stepper inactive circle text / strong bg (dark): 7.03:1
node chip text / subtle (light): 16.30:1
node chip text / subtle (dark): 14.05:1
status running badge / subtle (light): 6.12:1
status running badge / subtle (dark): 8.14:1
status succeeded badge / subtle (light): 4.58:1
status succeeded badge / subtle (dark): 6.44:1
status failed badge / subtle (light): 5.91:1
status failed badge / subtle (dark): 5.31:1
status awaiting_approval badge / subtle (light): 4.58:1
status awaiting_approval badge / subtle (dark): 6.83:1
readiness warning text / subtle (light): 4.58:1
readiness warning text / subtle (dark): 6.83:1
terminal output text / canvas (light): 17.06:1
terminal output text / canvas (dark): 18.59:1
```

또한, 저장소에 신규 추가된 `tools/test_c206_mutations.py`를 실행하여 10종 뮤테이션(M1~M10)의 100% 사살을 언제든지 독립적으로 재현 검증할 수 있습니다:
```bash
python tools/test_c206_mutations.py
```

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/studio/DeveloperStudio.tsx`
- **리터럴 감축**: 174건 -> **0건** (전수 제거, 174건 전원 해소).
- **의도적 시맨틱 개선 및 불변식 준수**:
  - **스텝퍼 (1~4단계)**:
    - 활성 원형: `backgroundColor: var(--color-brand-primary)`, `color: var(--color-brand-primary-fg)`.
    - 활성 카드 테두리: `border: 2px solid var(--color-brand-primary)` (Light 4.94:1, Dark 7.64:1).
    - 완료 원형: `backgroundColor: var(--color-status-online)`, `color: var(--color-text-inverse)`.
    - 비활성 원형: `backgroundColor: var(--color-border-strong)`, `color: var(--color-text-inverse)` (Light 7.58:1, Dark 7.03:1).
  - **실행 세션 상태 배지 (`studio-execution-status-badge`)**:
    - `running`: `var(--color-brand-hover)` (Light 6.12:1, Dark 8.14:1).
    - `succeeded`: `var(--color-status-online)` (Light 4.58:1, Dark 6.44:1).
    - `failed`: `var(--color-status-offline)` (Light 5.91:1, Dark 5.31:1).
    - `awaiting_approval`: `var(--color-status-degraded)` (Light 4.58:1, Dark 6.83:1).
    - `recovering`: `var(--color-brand-hover)`.
  - **노드 칩 및 카드 결함 해소**:
    - `data-testid="studio-node-chip"`: `var(--color-bg-subtle)` 배경 위 `var(--color-text-primary)` (Light 16.30:1, Dark 14.05:1).
    - 비적격 노드 카드에서 `opacity: isNodeSchedulable ? 1 : 0.75`를 제거하여 명도 대비 3.94:1 저하 결함을 원천 차단. 비적격 시에는 `var(--color-status-degraded)` 경고 배지를 통해 시맨틱 제공.
  - **탭 바 1:1 충돌 교정**:
    - 활성 탭 `borderBottom`을 `'1px solid var(--color-bg-surface)'`에서 `'1px solid transparent'`로 교정하여 surface 배경과의 1:1 충돌(대비 1.0:1) 원천 차단.
  - **무한 재렌더링 방지 및 런타임 안정성**:
    - `projects = React.useMemo(() => [project], [project])` 메모이제이션으로 `useEffect` 무한 루프 차단.
    - `readiness.blockedBy?.join(', ') || '없음'` safe navigation 적용으로 미서명/블록 사유 미정의 시 런타임 TypeError 원천 차단.
    - Step 4 완료 시각 판정에 `currentRun?.completedAt`을 추가하여 liveRun 폴링 완료 시각 실시간 동기화.

### 3.2 `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **Test 9g 신설**:
  - `vi.mock('@/shared/api/client')` 모듈 모킹을 통해 실제 네트워크 요청 차단 및 안정적 렌더링 보장.
  - 스텝퍼 1~4단계 DOM 렌더링, 활성/완료 테두리 및 원형 배경 토큰 결속 단언.
  - 노드 칩 및 비적격 카드 경고 배지 단언.
  - Step 2 미준비 경고 배너 단언.
  - 실행 세션 상태 배지(running, succeeded, failed, awaiting_approval)의 전경색/배경색/테두리색 및 dynamic 명도 대비 단언 (텍스트 >= 4.5:1, 테두리 >= 3.0:1).
  - Step 4 터미널 탭 및 출력 텍스트 단언.
- **Test 9g-2 신설**:
  - 계층적 조상 컨테이너 추적 및 요소/조상 불투명도(opacity) 합성 기반 동적 AST 스타일-쌍 대비 계산기 구현.
  - 총 style 속성 수: **252개**.
  - 명시적 배경/전경 검사 객체: **36개**.
  - 평가된 전경-배경 쌍(분기 및 조상 컨테이너 포함): **156개**.
  - 상속 컨테이너 배경 대상 글자 객체: **92개**.
  - 총 커버된 색상 스타일 객체: **128개** (36 + 92).
  - 명시적 테두리 스타일 객체: **68개**.
  - 평가된 테두리-배경 쌍: **92개**.
  - 위반 건수: **0건** (전수 통과).
- **Revert-Fail Probes 58~60 신설**:
  - Probe 58: DeveloperStudio 이전 하드코딩 `#d29922` on light subtle 결함 (2.30:1 < 4.5:1)
  - Probe 59: DeveloperStudio 비적격 카드 opacity 0.75 결함 (3.94:1 < 4.5:1)
  - Probe 60: DeveloperStudio 활성 탭 borderBottom 1:1 충돌 결함 (1.0:1 < 3.0:1)
- **Test 10 래칫 갱신**:
  - `borderSubtleCount`: 346 -> **356건** (+10건)
  - `borderSubtleFiles.size`: **25개** 유지
  - `#30363d` 상한: 66 -> **64건 이하 (11개 파일 이하)**
  - `COLOR_LITERAL_MULTISET_BASELINE`: `features/studio/DeveloperStudio.tsx: {}`

### 3.3 `tools/test_c206_mutations.py` 신규 커밋
- 10종의 회귀 뮤테이션(M1~M10)을 소스 파일에 순차 적용하고, ACC-09 테스트 스위트(`Card 206|Multiset Inventory`)를 통해 즉각 사살되는지 검증하는 독립 러너.
- 사살 실측 결과: 10 / 10 mutants killed (100.0%, exit code 0).
  - M1: status running token swapped to text-muted (grey) -> KILLED (Test 9g)
  - M2: status succeeded border swapped to text-primary -> KILLED (Test 9g)
  - M3: non-schedulable node card re-injects opacity 0.75 -> KILLED (Probe 59 / Test 9g-2)
  - M4: active tab borderBottom 1:1 collision with surface bg -> KILLED (Probe 60 / Test 9g-2)
  - M5: stepper active border swapped to subtle border -> KILLED (Test 9g)
  - M6: node chip background swapped to surface -> KILLED (Test 9g)
  - M7: multiset decoy literal reintroduced -> KILLED (Test 10)
  - M8: missing testid regression (removes studio-execution-status-badge testid) -> KILLED (Test 9g)
  - M9: status failed swapped to degraded token -> KILLED (Test 9g)
  - M10: stepper inactive circle background swapped to primary -> KILLED (Test 9g)

---

## 4. 검증 실측 근거 (Evidence)

1. **단위 테스트 (Vitest)**:
   - `npx vitest run tests/acc09-contrast-tokens.test.tsx`: 22 passed (100%), exit 0.
2. **뮤테이션 테스트**:
   - `python tools/test_c206_mutations.py`: 10 / 10 mutants killed (100.0%), exit 0.
3. **타입 검사**:
   - `cd apps/web && npx tsc -b`: error 0건, clean pass (exit 0).
4. **프로덕션 빌드**:
   - `cd apps/web && npm run build`: built in 9.94s (dist 생성 정상, exit 0).
5. **백엔드 라우트 커버리지 및 EvidenceViewer 무결성 불변식**:
   - `pytest tests/test_route_coverage.py`: 41 passed (100%), exit 0.
6. **프런트엔드 무결성 게이트**:
   - `python tools/check_frontend_integrity.py`: 93 files scanned, 0 violations, exit 0.
7. **계약 바인딩 게이트**:
   - `python tools/check_contract_bindings.py`: 55 fixtures, 20 bound types, exit 0.
8. **문서 일관성 게이트**:
   - `python tools/check_docs.py`: PASS (exit 0).
9. **Git 차분 포맷 검사**:
   - `git diff --check`: clean (exit 0, EOF/공백 결함 0건).

---

## 5. 다음 담당자 및 후속 과제

- **다음 담당자**: 코디네이터 및 독립 리뷰어 (Claude UI, Codex).
- **후속 작업**: PR 생성 및 검토 인계 -> ACC-09 후속 카드(Card 207) 진행 준비.
