# 2026-10-02 05:24:00 KST — Card 202: 사내망 배포 화면 (IntranetDeploymentView) 색상 리터럴 inventory 전수(216→0), 대비 표본/DOM 결속 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD202-INTRANET-DEPLOY-CONTRAST
- **작업 branch**: agent/gemini/c202-intranet-deploy-contrast
- **Base commit**: dca1aa06fbeec7be4cbcc4a2d1d0799be44983fb (PR #298 r3 HEAD)
- **KST 시각**: 2026-10-02 05:24:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 내부망 HTTPS 배포 및 운영 인수 시뮬레이터 화면(`apps/web/src/features/deployment/IntranetDeploymentView.tsx`, #281 서버 릴리스 선언서 결속·운영자 2인 확인 표시·교육 훈련 워크스루 포함)의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/deployment/IntranetDeploymentView.tsx` (기존 baseline 리터럴: **216건**)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9f, Test 9f-2, Probes 51~55, 래칫 갱신)
- **감사 및 조치 결과**:
  - 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (216건 -> 0건 감축, 리터럴 잔여 0건).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 `IntranetDeploymentView.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 갱신.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 317건에서 **346건**(+29건)으로 증가하였으며, 사용 파일 수가 24개에서 **25개**(`IntranetDeploymentView.tsx` 신규 편입)로 래칫 단언 갱신.
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 강화:
    - `#30363d`: 92건(13개 파일) -> **66건 이하(12개 파일 이하)**
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9f)에 미노출 안내 배너, 서버 매니페스트 배너, 서버 릴리스 버전, 서버 수락 기록 건수, 미인증 경고 배너의 동적 명도 대비 및 테두리 대비 결속 추가.
  - 계층적 조상 컨테이너 추적 기반 동적 AST 스타일-쌍 대비 계산기(Test 9f-2): 193개 style 속성 총수 래칫 및 조상 컨테이너 배경 스택 추적 동적 AST 명도 대비 계산 및 커버리지 래칫 (checkedObjects 22, checkedPairs 143, unboundColorObjects 100, coveredColorObjects 122, checkedBorderObjects 34, checkedBorderPairs 36, violations 0건).
  - Revert-Fail Probes 51~55 신설로 10종 뮤테이션 전원 사살 실측(사살율 **100.0%**).

---

## 2. 전수 명도 대비 실측 및 동적 재현 명령

### 2.1 실제 렌더 배경 기반 전수 실측표

모든 대비는 SaintVision 플랫폼 정본 배경(`apps/web/src/index.css` 기준: Light surface `#ffffff`, subtle `#f1f5f9`; Dark surface `#111827`, subtle `#1f2937`) 위에서 측정되었습니다. 'Before' 열의 라이트 모드 값은 이전 코드가 다크 전용 하드코딩 색상을 라이트 배경에 강제 노출했을 때의 결함을 보여주는 '가상 비교 (Virtual Comparison)'입니다.

| 대상 UI 요소 | Before 색상 조합 (Light / Dark) | Before 명도 대비 (Light / Dark) | 판정 (WCAG AA) | After 디자인 토큰 조합 | After 명도 대비 (Light) | After 명도 대비 (Dark) | 최종 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **미노출 안내 텍스트** | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#0d1117` (Dark) | 2.81:1 / 6.15:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **미노출 안내 테두리** | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#0d1117` (Dark) | 11.14:1 / 1.55:1 | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |
| **인증 필요 알림 텍스트** | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#0d1117` (Dark) | 3.06:1 / 5.65:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **인증 필요 알림 테두리** | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#0d1117` (Dark) | 3.06:1 / 5.65:1 | **PASS** | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 3.0:1) |
| **서버 매니페스트 배너 텍스트** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **서버 매니페스트 배너 테두리** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 3.0:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 3.0:1) |
| **서버 릴리스 버전** | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#0d1117` (Dark) | 2.31:1 / 7.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-bg-subtle)` | **6.12:1** | **8.14:1** | **PASS** (>= 4.5:1) |
| **서버 릴리스 ID / SHA** | `#f0f6fc` on `#f1f5f9` (Light 가상)<br>`#f0f6fc` on `#0d1117` (Dark) | 1.01:1 / 17.39:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **운영자 미서명 경고** | `#d29922` on `#f1f5f9` (Light 가상)<br>`#d29922` on `#0d1117` (Dark) | 2.30:1 / 7.50:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **미서명 blockedBy 안내** | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#0d1117` (Dark) | 2.81:1 / 6.15:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-subtle)` | **6.92:1** | **11.86:1** | **PASS** (>= 4.5:1) |
| **운영자 확인 현황 (N/2)** | `#f0f6fc` on `#f1f5f9` (Light 가상)<br>`#f0f6fc` on `#0d1117` (Dark) | 1.01:1 / 17.39:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **서버 수락 기록 건수** | `#f0f6fc` on `#f1f5f9` (Light 가상)<br>`#f0f6fc` on `#0d1117` (Dark) | 1.01:1 / 17.39:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-subtle)` | **16.30:1** | **14.05:1** | **PASS** (>= 4.5:1) |
| **교육 Step 번호 완료** | `#ffffff` on `#238636` (Light 가상)<br>`#ffffff` on `#238636` (Dark) | 4.63:1 / 4.63:1 | **PASS** | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **교육 Step 배지 완료** | `#3fb950` on `#0d1117` (Light 가상)<br>`#3fb950` on `#0d1117` (Dark) | 7.45:1 / 7.45:1 | **PASS** | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **섹션 컨테이너 테두리** | `#30363d` on `#ffffff` (Light 가상)<br>`#30363d` on `#111827` (Dark) | 12.20:1 / 1.45:1 | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-surface)` | **3.48:1** | **3.73:1** | **PASS** (>= 3.0:1) |

---

### 2.2 정본 토큰 파싱 기반 동적 재현 명령 및 시험 결속

문서 내 모든 대비 수치는 `apps/web/src/index.css`의 토큰 선언(`:root` 및 `[data-theme='dark']`)을 **직접 파싱**하여 WCAG 2.2 상대휘도 공식으로 동적 연산됩니다. 하드코딩 사본이 아닌 실시간 파일 파싱 명령입니다.

```bash
# apps/web/src/index.css 직접 파싱 기반 전수 대비 동적 재현 명령 (Python)
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
dark_tokens = parse_tokens(re.search(r'\[data-theme=[\'"]dark[\'"]\]\s*\{([\s\S]*?)\}', css).group(1))

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

print('unexposed notice text / subtle (light):', f'{cr(light_tokens["--color-brand-hover"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('unexposed notice text / subtle (dark):', f'{cr(dark_tokens["--color-brand-hover"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('unexposed notice border / subtle (light):', f'{cr(light_tokens["--color-border-subtle"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('unexposed notice border / subtle (dark):', f'{cr(dark_tokens["--color-border-subtle"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('auth notice text & border / subtle (light):', f'{cr(light_tokens["--color-status-offline"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('auth notice text & border / subtle (dark):', f'{cr(dark_tokens["--color-status-offline"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('server release version / subtle (light):', f'{cr(light_tokens["--color-brand-hover"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('server release version / subtle (dark):', f'{cr(dark_tokens["--color-brand-hover"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('server signoff warning / subtle (light):', f'{cr(light_tokens["--color-status-degraded"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('server signoff warning / subtle (dark):', f'{cr(dark_tokens["--color-status-degraded"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('server blockedBy text / subtle (light):', f'{cr(light_tokens["--color-text-secondary"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('server blockedBy text / subtle (dark):', f'{cr(dark_tokens["--color-text-secondary"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('server acceptance count / subtle (light):', f'{cr(light_tokens["--color-text-primary"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('server acceptance count / subtle (dark):', f'{cr(dark_tokens["--color-text-primary"], dark_tokens["--color-bg-subtle"]):.2f}:1')
print('training step online text / subtle (light):', f'{cr(light_tokens["--color-status-online"], light_tokens["--color-bg-subtle"]):.2f}:1')
print('training step online text / subtle (dark):', f'{cr(dark_tokens["--color-status-online"], dark_tokens["--color-bg-subtle"]):.2f}:1')
PY
```

**실제 실행 콘솔 출력 (exit code 0 실측)**:
```text
unexposed notice text / subtle (light): 6.12:1
unexposed notice text / subtle (dark): 8.14:1
unexposed notice border / subtle (light): 3.18:1
unexposed notice border / subtle (dark): 3.08:1
auth notice text & border / subtle (light): 5.91:1
auth notice text & border / subtle (dark): 5.31:1
server release version / subtle (light): 6.12:1
server release version / subtle (dark): 8.14:1
server signoff warning / subtle (light): 4.58:1
server signoff warning / subtle (dark): 6.83:1
server blockedBy text / subtle (light): 6.92:1
server blockedBy text / subtle (dark): 11.86:1
server acceptance count / subtle (light): 16.30:1
server acceptance count / subtle (dark): 14.05:1
training step online text / subtle (light): 4.58:1
training step online text / subtle (dark): 6.44:1
```

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/deployment/IntranetDeploymentView.tsx`
- **리터럴 감축**: 216건 -> **0건** (전수 제거, 216건 전원 해소).
- **상세 변경 사항**:
  - 미노출 안내 배너 및 릴리스 서버 배너: `var(--color-bg-subtle)` 배경, `var(--color-brand-hover)` 텍스트 및 테두리 결속 (Light 6.12:1, Dark 8.14:1).
  - 인증 필요 경고 배너: `var(--color-bg-subtle)` 배경, `var(--color-status-offline)` 텍스트 및 테두리 결속 (Light 5.91:1, Dark 5.31:1).
  - 섹션 컨테이너: `var(--color-bg-surface)` 배경 및 `var(--color-border-subtle)` 테두리 결속 (Light 3.48:1, Dark 3.73:1).
  - 서버 릴리스 상세 카드 그리드: `var(--color-bg-subtle)` 배경, `var(--color-border-subtle)` 테두리 결속.
  - #281 서버 릴리스 결속 상태 보존:
    - `operatorSignOff` 미서명 경고: `var(--color-status-degraded)` (Light 4.58:1, Dark 6.83:1).
    - `operatorSignOffBlockedBy`: `var(--color-text-secondary)` (Light 6.92:1, Dark 11.86:1).
    - `operatorQuorum` 사람 확인 (N/2): `var(--color-text-primary)` (Light 16.30:1, Dark 14.05:1).
    - 일치 수락 기록 건수 및 릴리스 ID: `var(--color-text-primary)`.
  - 교육 훈련 모듈 스텝 배지 및 번호 칩:
    - 완료 시: `var(--color-status-online)` 텍스트/테두리, `var(--color-bg-subtle)` 배경.
    - 미완료 시: `var(--color-text-secondary)` 텍스트, `var(--color-border-subtle)` 테두리, `var(--color-bg-subtle)` 배경.
    - 상태 필(Pill) 배지: 완료 `var(--color-status-online)`, 대기 `var(--color-text-secondary)`.

### 3.2 `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **Test 9f 신설**: `IntranetDeploymentView` 컴포넌트 DOM 렌더링 검증.
  - `deployment-unexposed-notice`: `var(--color-brand-hover)` on subtle (Light 6.12:1, Dark 8.14:1).
  - `deployment-manifest-server-banner`: `var(--color-brand-hover)` on subtle (Light 6.12:1, Dark 8.14:1).
  - `server-release-version`: `var(--color-brand-hover)` on subtle (Light 6.12:1, Dark 8.14:1).
  - `server-acceptance-count`: `var(--color-text-primary)` on subtle (Light 16.30:1, Dark 14.05:1).
  - `deployment-auth-required-notice`: `var(--color-status-offline)` on subtle (Light 5.91:1, Dark 5.31:1).
- **Test 9f-2 신설**: 동적 AST 스타일-쌍 명도 대비 계산기 및 계층적 조상 컨테이너 배경 스택 추적 가드.
  - 총 style 속성 수: **193개**.
  - 명시적 배경/전경 검사 객체: **22개**.
  - 평가된 전경-배경 쌍(분기 및 조상 컨테이너 포함): **143개**.
  - 상속 컨테이너 배경 대상 글자 객체: **100개**.
  - 총 커버된 색상 스타일 객체: **122개**.
  - 명시적 테두리 스타일 객체: **34개**.
  - 평가된 테두리-배경 쌍: **36개**.
  - 위반 건수: **0건**.
- **Revert-Fail Probes 51~55 신설**:
  - Probe 51: 이전 `#58a6ff` on subtle 결함 (2.31:1 < 4.5:1)
  - Probe 52: 이전 `#8b949e` on subtle 결함 (2.81:1 < 4.5:1)
  - Probe 53: 이전 `#d29922` on subtle 결함 (2.30:1 < 4.5:1)
  - Probe 54: 1:1 글자-배경 충돌 결함 (1.0:1 < 4.5:1)
  - Probe 55: 1:1 테두리-배경 충돌 결함 (1.0:1 < 3.0:1)
- **Test 10 래칫 갱신**:
  - `borderSubtleCount`: 317 -> **346건** (+29건)
  - `borderSubtleFiles.size`: 24 -> **25개** (`IntranetDeploymentView.tsx` 편입)
  - `#30363d` 상한: 92 -> **66건 이하 (12개 파일 이하)**
  - `COLOR_LITERAL_MULTISET_BASELINE`: `features/deployment/IntranetDeploymentView.tsx: {}`

---

## 4. 검증 실측 근거 (Evidence)

1. **단위 테스트 (Vitest)**:
   - `npx vitest run tests/acc09-contrast-tokens.test.tsx`: 20 passed (100%), exit 0.
   - `npx vitest run tests/deployment-release-integrity-wiring.test.tsx tests/intranet-deployment.test.ts`: 13 passed (100%), exit 0.
2. **뮤테이션 테스트**:
   - `python scratch/test_c202_mutations.py`: 10 / 10 mutants killed (100.0%), exit 0.
3. **타입 검사**:
   - `cd apps/web && npx tsc -b`: error 0건, clean pass (exit 0).
4. **프로덕션 빌드**:
   - `cd apps/web && npm run build`: built in 7.27s (dist 생성 정상, exit 0).
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
- **후속 작업**: PR 생성 및 검토 피드백 반영, 승인 시 후속 카드 착수.
