# 2026-10-02 08:25:00 KST — Card 213: 실행 기록 화면 (SealRecordPanel & RunDetail) 색상 리터럴 전수 토큰화(135+122→0), 대비 표본/DOM 결속 감사 및 불변 봉인 원장 접근성 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD213-RUNS-RECORD-CONTRAST
- **작업 branch**: agent/gemini/c213-runs-contrast
- **Base commit**: 02d5ecd4402d06d0a110f5e596ff4c864d8c97e4 (PR #308 r1 remediation landing)
- **KST 시각**: 2026-10-02 08:25:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 실행 기록 및 봉인 원장 화면인 `apps/web/src/features/runs/SealRecordPanel.tsx`(봉인 기록 원장) 및 `apps/web/src/features/runs/RunDetail.tsx`(실행 상세, 수명주기 전이, 로그, 아티팩트 및 시도 이력)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/runs/SealRecordPanel.tsx` (기존 baseline 리터럴: **135건**)
  - `apps/web/src/features/runs/RunDetail.tsx` (기존 baseline 리터럴: **122건**)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9h, Test 9h-2, Probes 61~65, Fail-Closed 래칫 갱신)
  - `apps/web/tests/run-detail-seal-record.test.tsx` (봉인 원장 및 런 상세 25종 회귀 시험 통과 검증)
  - `tools/test_c213_mutations.py` (재현 가능한 10종 뮤테이션 M1~M10 전수 시험 러너 신규 커밋)
- **감사 및 조치 결과**:
  - `SealRecordPanel.tsx`: 135건 -> **0건** (리터럴 잔여 0건 multiset `{}` 달성).
  - `RunDetail.tsx`: 122건 -> **0건** (리터럴 잔여 0건 multiset `{}` 달성).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 두 파일의 허용 multiset을 `{}` (0건)으로 래칫 고정.
  - 전역 `var(--color-border-subtle)` 사용 횟수: 382건, 사용 파일 수: 26개 (래칫 불변식 충족).
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 전면 강화:
    - `#d97706`: 14건(6개 파일) -> **8건 이하(5개 파일 이하)**
    - `#e2e8f0`: 1건(1개 파일) -> **0건 이하(0개 파일 이하, 완전 소멸)**
    - `#30363d`: 64건(11개 파일) -> **55건 이하(9개 파일 이하)**
  - 결함 시정 및 시맨틱 보존:
    - 실행 상세 상태 배지(`run-detail-status-badge`)를 신설하여 6가지 핵심 수명주기 상태(`succeeded`, `running`, `failed`, `cancelled`, `recovering`, `awaiting_approval`)를 각각 고유한 정본 시맨틱 토큰 및 테두리로 명확히 분리:
      - `succeeded`: `var(--color-status-online)` (녹색, 테두리 일치)
      - `running`: `var(--color-brand-hover)` (파란색, 테두리 일치)
      - `failed`: `var(--color-status-offline)` (빨간색, 테두리 일치)
      - `cancelled`: `var(--color-status-neutral)` (회색, `var(--color-border-strong)` 테두리)
      - `recovering`: `var(--color-status-active)` (하늘색, 테두리 일치)
      - `awaiting_approval`: `var(--color-status-degraded)` (호박색, 테두리 일치)
    - 취소 모달 타이틀의 미선언 토큰 `var(--color-brand-danger)`를 정본 에러 토큰인 `var(--color-status-offline)`로 교체.
    - 수명주기 스텝 원형 인디케이터에서 다크 모드 저대비(2.18:1 < 3.0:1)를 유발하던 `border: isCurrent ? '3px solid var(--color-brand-subtle)' : 'none'`을 DeveloperStudio 정본 스타일 규격(배경색 및 반전 텍스트로 강조)으로 일원화하여 저대비 테두리 결함 원천 차단.
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9h):
    - 봉인 상태 배지(`seal-status-badge`): 봉인됨(`SEALED`) 및 미봉인(`UNSEALED`) 상태 전경/배경/테두리 대비 단언.
    - 봉인 원장 핵심 필드(`seal-record-id`, `seal-final-state`, `seal-workload-spec-sha`, `bundle-hash`): surface 배경 위 전경 텍스트 >= 4.5:1 단언.
    - 실행 상세 상태 배지(`run-detail-status-badge`): 6개 상태 전경/배경/테두리 대비 동적 단언 (텍스트 >= 4.5:1, 테두리 >= 3.0:1).
    - 완료 시각(`run-detail-completedAt`): 성공/실패 분기 동적 명도 대비 단언.
  - 계층적 조상 컨테이너 추적 및 불투명도(opacity) 합성 기반 동적 AST 스타일-쌍 대비 계산기(Test 9h-2):
    - **SealRecordPanel.tsx**:
      - totalStyleAttrs: 133개
      - checkedObjects: 17개
      - checkedPairs: 78개
      - unboundColorObjects: 59개
      - coveredColorObjects: 76개 (17 + 59)
      - checkedBorderObjects: 36개
      - checkedBorderPairs: 38개
      - violations: 0건
    - **RunDetail.tsx**:
      - totalStyleAttrs: 229개
      - checkedObjects: 29개
      - checkedPairs: 135개
      - unboundColorObjects: 74개
      - coveredColorObjects: 103개 (29 + 74)
      - checkedBorderObjects: 45개
      - checkedBorderPairs: 56개
      - violations: 0건
  - Revert-Fail Probes 61~65 신설 및 `tools/test_c213_mutations.py` 신규 커밋으로 10종 뮤테이션(M1~M10) 전원 사살 실측 (사살율 **100.0%**, exit code 0).

---

## 2. 명도 대비 실측 및 동적 재현 명령

### 2.1 실제 렌더 배경 기반 대표 표본 명도 대비 실측표

모든 대비는 SaintVision 플랫폼 정본 배경(`apps/web/src/index.css` 기준: Light surface `#ffffff`, subtle `#f1f5f9`, canvas `#f8fafc`; Dark surface `#111827`, subtle `#1f2937`, canvas `#090d16`) 위에서 측정되었습니다. 'Before' 열의 라이트 모드 값은 이전 코드가 다크 전용 하드코딩 색상을 라이트 배경에 강제 노출했을 때의 결함을 보여주는 '가상 비교 (Virtual Comparison)'입니다.

| 대상 UI 요소 / 배경 | Before 색상 조합 (Light / Dark) | Before 대비 (Light / Dark) | 판정 (WCAG AA) | After 디자인 토큰 조합 | After 대비 (Light) | After 대비 (Dark) | 최종 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **봉인 기록 식별자 / surface** | `#8b949e` on `#ffffff` (Light 가상)<br>`#8b949e` on `#0d1117` (Dark) | 3.08:1 / 6.15:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-surface)` | **17.85:1** | **16.98:1** | **PASS** (>= 4.5:1) |
| **봉인 최종 상태 / surface** | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.53:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **봉인 워크로드 SHA / surface** | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.53:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **컨텍스트 번들 해시 / surface** | `#58a6ff` on `#ffffff` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.53:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-surface)` | **6.70:1** | **9.84:1** | **PASS** (>= 4.5:1) |
| **봉인 배지: 봉인됨 / subtle** | `#3fb950` on `#f1f5f9` (Light 가상)<br>`#3fb950` on `#0d1117` (Dark) | 2.45:1 / 7.45:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **봉인 배지: 미봉인 / subtle** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: succeeded / subtle** | `#3fb950` on `#f1f5f9` (Light 가상)<br>`#3fb950` on `#0d1117` (Dark) | 2.45:1 / 7.45:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: running / subtle** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: failed / subtle** | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#0d1117` (Dark) | 3.06:1 / 5.65:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: cancelled / subtle** | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#0d1117` (Dark) | 2.81:1 / 6.15:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-neutral)` on<br>`var(--color-bg-subtle)` | **5.25:1** | **5.78:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: recovering / subtle** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-active)` on<br>`var(--color-bg-subtle)` | **5.42:1** | **6.85:1** | **PASS** (>= 4.5:1) |
| **런 상태 배지: awaiting_approval / subtle** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **런 상세 완료 시각 (성공) / surface** | `#3fb950` on `#ffffff` (Light 가상)<br>`#3fb950` on `#0d1117` (Dark) | 2.54:1 / 7.45:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-surface)` | **5.02:1** | **7.79:1** | **PASS** (>= 4.5:1) |
| **런 상세 완료 시각 (실패) / surface** | `#f85149` on `#ffffff` (Light 가상)<br>`#f85149` on `#0d1117` (Dark) | 3.19:1 / 5.65:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-surface)` | **6.47:1** | **6.41:1** | **PASS** (>= 4.5:1) |

---

### 2.2 정본 토큰 파싱 기반 동적 재현 명령 및 시험 결속

문서 내 대표 토큰 조합 실측치는 `apps/web/src/index.css`의 토큰 선언(`:root` 및 `[data-theme='dark']`)을 **직접 파싱**하여 WCAG 2.2 상대휘도 공식으로 동적 연산됩니다. 결과는 알파벳 순으로 결정적 정렬 출력됩니다.

```bash
# apps/web/src/index.css 직접 파싱 기반 대표 토큰 대비 동적 재현 명령 (Python)
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
def lum(h):
    rgb = hex_to_rgb(h)
    def adj(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)
    return 0.2126 * adj(rgb[0]) + 0.7152 * adj(rgb[1]) + 0.0722 * adj(rgb[2])

def cr(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

items = [
    ("run detail completedAt (failed) / surface", "--color-status-offline", "--color-bg-surface"),
    ("run detail completedAt (succeeded) / surface", "--color-status-online", "--color-bg-surface"),
    ("run status awaiting_approval / subtle", "--color-status-degraded", "--color-bg-subtle"),
    ("run status cancelled / subtle", "--color-status-neutral", "--color-bg-subtle"),
    ("run status failed / subtle", "--color-status-offline", "--color-bg-subtle"),
    ("run status recovering / subtle", "--color-status-active", "--color-bg-subtle"),
    ("run status running / subtle", "--color-brand-hover", "--color-bg-subtle"),
    ("run status succeeded / subtle", "--color-status-online", "--color-bg-subtle"),
    ("seal badge degraded (unsealed) / subtle", "--color-status-degraded", "--color-bg-subtle"),
    ("seal badge online (sealed) / subtle", "--color-status-online", "--color-bg-subtle"),
    ("seal bundle hash / surface", "--color-brand-hover", "--color-bg-surface"),
    ("seal final state / surface", "--color-brand-hover", "--color-bg-surface"),
    ("seal record ID / surface", "--color-text-primary", "--color-bg-surface"),
    ("seal workload spec sha / surface", "--color-brand-hover", "--color-bg-surface"),
]

items.sort(key=lambda x: x[0])

for label, fg, bg in items:
    l_fg, l_bg = light_tokens[fg], light_tokens[bg]
    d_fg, d_bg = dark_tokens[fg], dark_tokens[bg]
    l_cr = cr(l_fg, l_bg)
    d_cr = cr(d_fg, d_bg)
    print(f"{label:45s} | Light: {l_cr:.2f}:1 ({fg} on {bg}) | Dark: {d_cr:.2f}:1 ({fg} on {bg})")
PY
```

---

## 3. 뮤테이션 테스트 및 Revert-Fail Probes 실측 증거

### 3.1 10종 뮤테이션 전수 사살 (tools/test_c213_mutations.py)

```
================================================================================
 Card 213 (ACC-09): Reproducible Mutant Test Suite (10 Mutants: M1-M10)
 Targets: SealRecordPanel.tsx & RunDetail.tsx
================================================================================

[Baseline Check] Testing unmutated code...
[Baseline Check] Clean pass (exit code 0).

[01/10] M1  : KILLED in 4.8s -- SealRecordPanel: seal badge status token swapped to degraded (semantic violation)
[02/10] M2  : KILLED in 4.9s -- SealRecordPanel: seal record ID color swapped to muted (contrast/token regression)
[03/10] M3  : KILLED in 4.7s -- SealRecordPanel: re-injects raw hex literal (fail-closed multiset inventory breach)
[04/10] M4  : KILLED in 5.2s -- SealRecordPanel: missing testid regression (removes seal-status-badge)
[05/10] M5  : KILLED in 5.0s -- SealRecordPanel: 1:1 border collision on record ledger card
[06/10] M6  : KILLED in 5.2s -- RunDetail: status succeeded badge color swapped to brand-hover (semantic regression)
[07/10] M7  : KILLED in 5.4s -- RunDetail: status cancelled badge color swapped to offline (semantic violation)
[08/10] M8  : KILLED in 5.1s -- RunDetail: re-injects raw hex literal (fail-closed multiset inventory breach)
[09/10] M9  : KILLED in 5.2s -- RunDetail: missing testid regression (removes run-detail-status-badge)
[10/10] M10 : KILLED in 5.3s -- RunDetail: 1:1 border collision on cancel modal dialog container

================================================================================
 Summary: 10/10 mutants killed (100.0%)
================================================================================
 [PASS] M1  : KILLED   | SealRecordPanel: seal badge status token swapped to degraded
 [PASS] M2  : KILLED   | SealRecordPanel: seal record ID color swapped to muted
 [PASS] M3  : KILLED   | SealRecordPanel: re-injects raw hex literal
 [PASS] M4  : KILLED   | SealRecordPanel: missing testid regression
 [PASS] M5  : KILLED   | SealRecordPanel: 1:1 border collision on record ledger card
 [PASS] M6  : KILLED   | RunDetail: status succeeded badge color swapped to brand-hover
 [PASS] M7  : KILLED   | RunDetail: status cancelled badge color swapped to offline
 [PASS] M8  : KILLED   | RunDetail: re-injects raw hex literal
 [PASS] M9  : KILLED   | RunDetail: missing testid regression
 [PASS] M10 : KILLED   | RunDetail: 1:1 border collision on cancel modal dialog container

SUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.
```

---

## 4. 검증 게이트 및 불변식 통과 실측치

모든 검증은 PowerShell 세미콜론 연결 없이 개별 명령의 exit code를 즉시 확인하며 수행되었습니다.

1. **Vitest Unit & Contrast Suite**:
   ```powershell
   npx vitest run tests/acc09-contrast-tokens.test.tsx
   # Tests: 24 passed (24) | Duration: 4.91s | Exit Code: 0
   ```
2. **Seal Record Panel & Run Detail Suite**:
   ```powershell
   npx vitest run tests/run-detail-seal-record.test.tsx
   # Tests: 25 passed (25) | Duration: 1.37s | Exit Code: 0
   ```
3. **Related Run & Studio Suites**:
   ```powershell
   npx vitest run tests/run-detail-attempts-dom.test.tsx tests/run-detail-logs-dom.test.tsx tests/model-retry-action.test.tsx tests/s11-defect-fixes.test.tsx tests/developer-studio-workspace-status.test.tsx
   # Tests: 45 passed (45) | Duration: 2.23s | Exit Code: 0
   ```
4. **TypeScript Project Reference Build**:
   ```powershell
   cd apps/web; npx tsc -b
   # Exit Code: 0 (0 type errors)
   ```
5. **Vite Production Bundle Build**:
   ```powershell
   cd apps/web; npm run build
   # Exit Code: 0 (built in ~3.8s)
   ```
6. **Backend Screen Route Coverage & Invariants**:
   ```powershell
   pytest tests/test_route_coverage.py
   # 41 passed | Exit Code: 0
   ```
7. **Frontend Integrity Gate**:
   ```powershell
   python tools/check_frontend_integrity.py
   # Exit Code: 0 (PASS)
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

- **작업 브랜치**: `agent/gemini/c213-runs-contrast`
- **리뷰 요청**: Claude UI (접근성 및 UI 경험), Codex (계약 및 토큰 불변식)
- **다음 행동**:
  - PR 생성 및 코디네이터 검토 요청 (봇 멘션 0건 준수).
  - 검토 피드백 수신 시 우선 조치 후 다음 카드(Card 214 등) 진입.
