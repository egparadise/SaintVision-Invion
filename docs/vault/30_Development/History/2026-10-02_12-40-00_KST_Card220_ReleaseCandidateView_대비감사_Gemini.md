# 2026-10-02 14:03:00 KST — Card 220: 릴리스 후보 화면 (ReleaseCandidateView) 색상 리터럴 전수 토큰화(19종/84 occurrences→0), 상태 색 정합성 및 접근성 승격 (r3)

- **문서 ID**: HIST-GEMINI-CARD220-RELEASE-CONTRAST
- **작업 branch**: agent/gemini/c220-release-contrast
- **Base commit**: 23fbedae40ad62dd0a5ee8770b397fa6089ec006 (Card 218 PR #316 r5 head)
- **KST 시각**: 2026-10-02 14:03:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성/테스트 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 릴리스 후보 관리 및 무중단 롤백 제어기 화면인 `apps/web/src/features/release/ReleaseCandidateView.tsx`의 하드코딩 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다. 선행 Card 213(`RunDetail.tsx`), Card 215(`RunList.tsx`), Card 218(`DistributedRecoveryView.tsx`)에서 확립된 상태 색상 규격과 완벽한 정합성을 달성하고, 텍스트 >= 4.5:1 및 비텍스트/테두리 >= 3.0:1 대비 기준을 100% 충족하도록 개선하였습니다. r1 독립 검토(Claude UI)의 지적 사항을 전면 수용하여, fail-closed 미지 상태 처리(`getSloStatusConfig`, `getAuditStatusConfig`, `getCandidateStatusConfig`), 렌더된 배지 스타일-config 결속 및 20종 뮤테이션 전수 사살, 활성 후보 카드 상시 outline 제거(키보드 포커스 링 오인 차단 및 비색상 변경 배제), 실제 조상 컨테이너 기준 테두리 대비 검증을 완비하였습니다.

- **대상 파일**:
  - `apps/web/src/features/release/ReleaseCandidateView.tsx` (기존 baseline 리터럴: **19종(84 occurrences)** -> **0건**)
  - `apps/web/tests/acc09-contrast-tokens.test.tsx` (Test 9k, Test 9j-2, Probes 76~80 추가, Fail-Closed 래칫 고정, AST config inspection, 20종 결함 사살)
  - `tools/reproduce_c220_contrast.py` (25종 Before/After 명도 대비 동적 재현 스크립트, trailing whitespace 0)
  - `tools/test_c220_mutations.py` (재현 가능한 20종 뮤테이션 M1~M20 전수 시험 러너, 표준 힙 메모리 구동)
- **감사 및 조치 결과**:
  - `ReleaseCandidateView.tsx`: 19종(84 occurrences: hex 11종 74건, rgba 8종 10건) -> **0건** (리터럴 잔여 0건 multiset `{}` 달성).
  - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/release/ReleaseCandidateView.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 고정.
  - 전역 `var(--color-border-subtle)` 사용 횟수: **417건** (기존 402건 대비 +15건), 사용 파일 수: **28개** (기존 27개 대비 +1개, 정확 일치 래칫 통과).
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 전면 강화:
    - `#30363d`: 43건(8개 파일) -> **32건 (7개 파일 이하, 실측치 11건 감소, 상한 <= 34)**
  - 비색상 변경: 활성 후보 카드의 상시 outline 제거(base 상태 복원, `:focus-visible` 링 오인 배제), 롤백 버튼 포커스 링 보존, 알 수 없는 상태는 `UNKNOWN (<원문>)` 및 `var(--color-status-unknown)`으로 fail-closed 처리.

### 1.1 상태 색 정합성 및 화면 간 일관성 확보 (Card 213, 215, 218 정합)
`RunDetail.tsx`, `RunList.tsx`, `DistributedRecoveryView.tsx`에서 확립된 상태 색상 규격과 완벽히 일치하도록 `ReleaseCandidateView.tsx`의 3대 상태 설정 객체를 정비하고 export하였습니다:
- **`SLO_STATUS_CONFIG`**:
  - `met`: 전경/테두리 `var(--color-status-online)`, 배경 `var(--color-bg-subtle)`, 레이블 `모의 MET (미측정)`.
  - `unmeasured`: 전경/테두리 `var(--color-text-secondary)`, 배경 `var(--color-bg-subtle)`, 레이블 `UNMEASURED (미측정) · 모의 MET (미측정)`.
  - `breached`: 전경/테두리 `var(--color-status-offline)`, 배경 `var(--color-bg-subtle)`, 레이블 `BREACHED`.
- **`AUDIT_STATUS_CONFIG`**:
  - `pass`: 전경/테두리 `var(--color-status-online)`, 배경 `var(--color-bg-subtle)`, 레이블 `모의 PASS`.
  - `fail`: 전경/테두리 `var(--color-status-offline)`, 배경 `var(--color-bg-subtle)`, 레이블 `FAIL`.
- **`CANDIDATE_STATUS_CONFIG`**:
  - `active`: 전경/테두리 `var(--color-brand-hover)`, 배경 `var(--color-bg-subtle)`, 레이블 `모의 활성 (서버 API 미노출 · 실 인프라 미배포)`.
  - `waiting`: 전경/테두리 `var(--color-text-secondary)`, 배경 `var(--color-bg-subtle)`, 레이블 `모의 대기`.
- **미지 상태 Fail-Closed 헬퍼 함수**:
  - `getSloStatusConfig(status)`: 등록되지 않은 상태 전달 시 전경/테두리 `var(--color-status-unknown)`, 배경 `var(--color-bg-subtle)`, 레이블 `UNKNOWN (${status || 'UNKNOWN'})` 반환.
  - `getAuditStatusConfig(status)`: 등록되지 않은 상태 전달 시 전경/테두리 `var(--color-status-unknown)`, 배경 `var(--color-bg-subtle)`, 레이블 `UNKNOWN (${status || 'UNKNOWN'})` 반환.
  - `getCandidateStatusConfig(status)`: 등록되지 않은 상태 전달 시 전경/테두리 `var(--color-status-unknown)`, 배경 `var(--color-bg-subtle)`, 레이블 `UNKNOWN (${status || 'UNKNOWN'})` 반환.

### 1.2 기타 UI 컴포넌트 토큰화 및 테두리 대비 확보
- **API 미노출 시뮬레이션 고지 배너 (`release-unexposed-notice`)**:
  - 배경: `var(--color-bg-subtle)`, 테두리: `var(--color-border-subtle)`, 전경: `var(--color-text-secondary)`. Light 6.92:1 / Dark 11.86:1 (>= 4.5:1 PASS).
- **상단 KPI 카드군 (`kpi-vulns-card`, `kpi-slo-card`, `kpi-wcag-card`, `active-candidate-card`)**:
  - 카드 배경: `var(--color-bg-surface)`, 테두리: `var(--color-border-subtle)`.
  - 취약점 미완화 0건 / SLO 달성률 / WCAG 통과 수치: `var(--color-status-online)` on surface. Light 5.02:1 / Dark 7.79:1 (>= 4.5:1 PASS).
  - 경고 수치: `var(--color-status-offline)` on surface. Light 6.47:1 / Dark 6.41:1 (>= 4.5:1 PASS).
  - 활성 후보 카드 태그: `var(--color-brand-hover)` on surface. Light 6.70:1 / Dark 9.84:1 (>= 4.5:1 PASS).
  - 활성 후보 카드는 상시 outline을 제거하고 텍스트 레이블("현재 활성 릴리스 후보 (RC)")로 명확히 안내.
- **롤백 관리 및 즉시 롤백 검증 패널 (`rollback-management-card`)**:
  - 패널 배경: `var(--color-bg-surface)`, 테두리 `var(--color-border-subtle)`.
  - 후보 테이블 헤더: `var(--color-text-muted)` on surface, 하단 구분선 `var(--color-border-subtle)`.
  - 후보 테이블 본문 행 구분선: `var(--color-border-subtle)`.
  - 후보 상태 배지(`candidate-status-badge-*`): `getCandidateStatusConfig` 매핑 토큰.
- **액션 결과 알림창 (`release-action-notice`)**:
  - 배경: `var(--color-bg-subtle)`.
  - 에러: 전경/테두리 `var(--color-status-offline)`. Light 5.91:1 / Dark 5.31:1 (>= 4.5:1 PASS).
  - 성공/정보: 전경/테두리 `var(--color-status-online)`. Light 4.58:1 / Dark 6.44:1 (>= 4.5:1 PASS).

### 1.3 비색상 인지 단서 보존 (WCAG 1.4.1 준수)
모든 상태는 색상에만 의존하지 않고 명확한 다중 단서로 인지할 수 있도록 보장되었습니다:
- 상태 배지: 명시적 텍스트 레이블 (`모의 MET (미측정)`, `UNMEASURED (미측정) · 모의 MET (미측정)`, `BREACHED`, `모의 PASS`, `FAIL`, `모의 활성 ...`, `모의 대기`).
- 기호 및 접두사: 롤백 검증 `✔ 모의 검증 완료`, 실패 알림 `🛑`, 성공 알림 `✔`, 안내 배너 `ℹ️`.

---

## 2. 명도 대비 실측 및 동적 재현 명령

### 2.1 실제 base 코드 및 렌더 배경 기반 명도 대비 실측표

모든 After 대비는 SaintVision 플랫폼 정본 배경(`apps/web/src/index.css` 기준: Light surface `#ffffff`, subtle `#f1f5f9`, canvas `#f8fafc`; Dark surface `#111827`, subtle `#1f2937`, canvas `#090d16`) 위에서 측정되었습니다.
'Before' 열의 수치는 베이스 커밋 `23fbedae`(23fbedae40ad62dd0a5ee8770b397fa6089ec006)의 실제 코드 색상, 실제 조상 배경(카드 `#161b22`, audit 행 `#0d1117`, 알림은 투명한 main을 지나 body canvas), 그리고 알파 합성 배경을 정밀 계산한 실측치입니다.

| 대상 UI 요소 / 배경 | Before 조합 (Light 실제) | Before 대비 (Light) | Before 조합 (Dark 실제) | Before 대비 (Dark) | After 디자인 토큰 조합 | After 대비 (Light) | After 대비 (Dark) | 최종 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `unexposed notice banner / canvas` | `#58a6ff` on `#e1edfc` | 2.13:1 (FAIL) | `#58a6ff` on `#0f1c32` | 6.75:1 (PASS) | `--color-text-secondary` on `--color-bg-subtle` | **6.92:1** | **11.86:1** | PASS |
| `kpi critical vulns title / surface` | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `--color-text-muted` on `--color-bg-surface` | **5.75:1** | **6.99:1** | PASS |
| `kpi critical vulns count zero / surface` | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `--color-status-online` on `--color-bg-surface` | **5.02:1** | **7.79:1** | PASS |
| `kpi critical vulns count alert / surface` | `#f85149` on `#161b22` | 5.16:1 (PASS) | `#f85149` on `#161b22` | 5.16:1 (PASS) | `--color-status-offline` on `--color-bg-surface` | **6.47:1** | **6.41:1** | PASS |
| `kpi slo rate met / surface` | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `--color-status-online` on `--color-bg-surface` | **5.02:1** | **7.79:1** | PASS |
| `kpi slo rate degraded / surface` | `#d29922` on `#161b22` | 6.85:1 (PASS) | `#d29922` on `#161b22` | 6.85:1 (PASS) | `--color-status-degraded` on `--color-bg-surface` | **5.02:1** | **8.26:1** | PASS |
| `kpi wcag pass checklist / surface` | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `#3fb950` on `#161b22` | 6.81:1 (PASS) | `--color-status-online` on `--color-bg-surface` | **5.02:1** | **7.79:1** | PASS |
| `kpi active rc tag / surface` | `#58a6ff` on `#161b22` | 6.85:1 (PASS) | `#58a6ff` on `#161b22` | 6.85:1 (PASS) | `--color-brand-hover` on `--color-bg-surface` | **6.70:1** | **9.84:1** | PASS |
| `action notice error / canvas` | `#f85149` on `#f8e1e1` | 2.69:1 (FAIL) | `#f85149` on `#2d171e` | 5.00:1 (PASS) | `--color-status-offline` on `--color-bg-subtle` | **5.91:1** | **5.31:1** | PASS |
| `action notice success / canvas` | `#3fb950` on `#daece0` | 2.06:1 (FAIL) | `#3fb950` on `#0f231d` | 6.47:1 (PASS) | `--color-status-online` on `--color-bg-subtle` | **4.58:1** | **6.44:1** | PASS |
| `slo table header / surface` | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `--color-text-muted` on `--color-bg-surface` | **5.75:1** | **6.99:1** | PASS |
| `slo table item name / surface` | `#f0f6fc` on `#161b22` | 15.89:1 (PASS) | `#f0f6fc` on `#161b22` | 15.89:1 (PASS) | `--color-text-primary` on `--color-bg-surface` | **17.85:1** | **16.98:1** | PASS |
| `slo table target / surface` | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `#8b949e` on `#161b22` | 5.62:1 (PASS) | `--color-text-muted` on `--color-bg-surface` | **5.75:1** | **6.99:1** | PASS |
| `slo table actual / surface` | `#58a6ff` on `#161b22` | 6.85:1 (PASS) | `#58a6ff` on `#161b22` | 6.85:1 (PASS) | `--color-brand-hover` on `--color-bg-surface` | **6.70:1** | **9.84:1** | PASS |
| `badge slo met / surface` | `#3fb950` on `#1b3629` | 5.15:1 (PASS) | `#3fb950` on `#1b3629` | 5.15:1 (PASS) | `--color-status-online` on `--color-bg-subtle` | **4.58:1** | **6.44:1** | PASS |
| `badge slo unmeasured / surface` | `#8b949e` on `#2d333b` | 4.14:1 (FAIL) | `#8b949e` on `#2d333b` | 4.14:1 (FAIL) | `--color-text-secondary` on `--color-bg-subtle` | **6.92:1** | **11.86:1** | PASS |
| `badge slo breached / surface` | `#f85149` on `#43262a` | 4.04:1 (FAIL) | `#f85149` on `#43262a` | 4.04:1 (FAIL) | `--color-status-offline` on `--color-bg-subtle` | **5.91:1** | **5.31:1** | PASS |
| `audit item title / subtle` | `#f0f6fc` on `#0d1117` | 17.39:1 (PASS) | `#f0f6fc` on `#0d1117` | 17.39:1 (PASS) | `--color-text-primary` on `--color-bg-subtle` | **16.30:1** | **14.05:1** | PASS |
| `audit item level / subtle` | `#58a6ff` on `#0d1117` | 7.49:1 (PASS) | `#58a6ff` on `#0d1117` | 7.49:1 (PASS) | `--color-brand-hover` on `--color-bg-subtle` | **6.12:1** | **8.14:1** | PASS |
| `audit item desc / subtle` | `#8b949e` on `#0d1117` | 6.15:1 (PASS) | `#8b949e` on `#0d1117` | 6.15:1 (PASS) | `--color-text-secondary` on `--color-bg-subtle` | **6.92:1** | **11.86:1** | PASS |
| `badge audit pass / subtle` | `#3fb950` on `#142e20` | 5.74:1 (PASS) | `#3fb950` on `#142e20` | 5.74:1 (PASS) | `--color-status-online` on `--color-bg-subtle` | **4.58:1** | **6.44:1** | PASS |
| `badge audit fail / subtle` | `#f85149` on `#3c1e21` | 4.48:1 (FAIL) | `#f85149` on `#3c1e21` | 4.48:1 (FAIL) | `--color-status-offline` on `--color-bg-subtle` | **5.91:1** | **5.31:1** | PASS |
| `candidate table tag / surface` | `#f0f6fc` on `#161b22` | 15.89:1 (PASS) | `#f0f6fc` on `#161b22` | 15.89:1 (PASS) | `--color-text-primary` on `--color-bg-surface` | **17.85:1** | **16.98:1** | PASS |
| `badge candidate active / surface` | `#58a6ff` on `#1d314e` | 5.19:1 (PASS) | `#58a6ff` on `#1d314e` | 5.19:1 (PASS) | `--color-brand-hover` on `--color-bg-subtle` | **6.12:1** | **8.14:1** | PASS |
| `badge candidate waiting / surface` | `#8b949e` on `#22272e` | 4.88:1 (PASS) | `#8b949e` on `#22272e` | 4.88:1 (PASS) | `--color-text-secondary` on `--color-bg-subtle` | **6.92:1** | **11.86:1** | PASS |

### 2.2 대비 재현 스크립트 실행 콘솔 출력 (`tools/reproduce_c220_contrast.py`)

```text
unexposed notice banner / canvas         | Before:  2.13:1 (L actual on #e1edfc) /  6.75:1 (D actual on #0f1c32) | After:  6.92:1 (Light) / 11.86:1 (Dark)
kpi critical vulns title / surface       | Before:  5.62:1 (L actual on #161b22) /  5.62:1 (D actual on #161b22) | After:  5.75:1 (Light) /  6.99:1 (Dark)
kpi critical vulns count zero / surface  | Before:  6.81:1 (L actual on #161b22) /  6.81:1 (D actual on #161b22) | After:  5.02:1 (Light) /  7.79:1 (Dark)
kpi critical vulns count alert / surface | Before:  5.16:1 (L actual on #161b22) /  5.16:1 (D actual on #161b22) | After:  6.47:1 (Light) /  6.41:1 (Dark)
kpi slo rate met / surface               | Before:  6.81:1 (L actual on #161b22) /  6.81:1 (D actual on #161b22) | After:  5.02:1 (Light) /  7.79:1 (Dark)
kpi slo rate degraded / surface          | Before:  6.85:1 (L actual on #161b22) /  6.85:1 (D actual on #161b22) | After:  5.02:1 (Light) /  8.26:1 (Dark)
kpi wcag pass checklist / surface        | Before:  6.81:1 (L actual on #161b22) /  6.81:1 (D actual on #161b22) | After:  5.02:1 (Light) /  7.79:1 (Dark)
kpi active rc tag / surface              | Before:  6.85:1 (L actual on #161b22) /  6.85:1 (D actual on #161b22) | After:  6.70:1 (Light) /  9.84:1 (Dark)
action notice error / canvas             | Before:  2.69:1 (L actual on #f8e1e1) /  5.00:1 (D actual on #2d171e) | After:  5.91:1 (Light) /  5.31:1 (Dark)
action notice success / canvas           | Before:  2.06:1 (L actual on #daece0) /  6.47:1 (D actual on #0f231d) | After:  4.58:1 (Light) /  6.44:1 (Dark)
slo table header / surface               | Before:  5.62:1 (L actual on #161b22) /  5.62:1 (D actual on #161b22) | After:  5.75:1 (Light) /  6.99:1 (Dark)
slo table item name / surface            | Before: 15.89:1 (L actual on #161b22) / 15.89:1 (D actual on #161b22) | After: 17.85:1 (Light) / 16.98:1 (Dark)
slo table target / surface               | Before:  5.62:1 (L actual on #161b22) /  5.62:1 (D actual on #161b22) | After:  5.75:1 (Light) /  6.99:1 (Dark)
slo table actual / surface               | Before:  6.85:1 (L actual on #161b22) /  6.85:1 (D actual on #161b22) | After:  6.70:1 (Light) /  9.84:1 (Dark)
badge slo met / surface                  | Before:  5.15:1 (L actual on #1b3629) /  5.15:1 (D actual on #1b3629) | After:  4.58:1 (Light) /  6.44:1 (Dark)
badge slo unmeasured / surface           | Before:  4.14:1 (L actual on #2d333b) /  4.14:1 (D actual on #2d333b) | After:  6.92:1 (Light) / 11.86:1 (Dark)
badge slo breached / surface             | Before:  4.04:1 (L actual on #43262a) /  4.04:1 (D actual on #43262a) | After:  5.91:1 (Light) /  5.31:1 (Dark)
audit item title / subtle                | Before: 17.39:1 (L actual on #0d1117) / 17.39:1 (D actual on #0d1117) | After: 16.30:1 (Light) / 14.05:1 (Dark)
audit item level / subtle                | Before:  7.49:1 (L actual on #0d1117) /  7.49:1 (D actual on #0d1117) | After:  6.12:1 (Light) /  8.14:1 (Dark)
audit item desc / subtle                 | Before:  6.15:1 (L actual on #0d1117) /  6.15:1 (D actual on #0d1117) | After:  6.92:1 (Light) / 11.86:1 (Dark)
badge audit pass / subtle                | Before:  5.74:1 (L actual on #142e20) /  5.74:1 (D actual on #142e20) | After:  4.58:1 (Light) /  6.44:1 (Dark)
badge audit fail / subtle                | Before:  4.48:1 (L actual on #3c1e21) /  4.48:1 (D actual on #3c1e21) | After:  5.91:1 (Light) /  5.31:1 (Dark)
candidate table tag / surface            | Before: 15.89:1 (L actual on #161b22) / 15.89:1 (D actual on #161b22) | After: 17.85:1 (Light) / 16.98:1 (Dark)
badge candidate active / surface         | Before:  5.19:1 (L actual on #1d314e) /  5.19:1 (D actual on #1d314e) | After:  6.12:1 (Light) /  8.14:1 (Dark)
badge candidate waiting / surface        | Before:  4.88:1 (L actual on #22272e) /  4.88:1 (D actual on #22272e) | After:  6.92:1 (Light) / 11.86:1 (Dark)
```

---

## 3. 재현 가능한 뮤테이션 테스트 및 결함 사살 검증 (`tools/test_c220_mutations.py`)

`tools/test_c220_mutations.py`를 실행하여 20종의 단일 변이(A1~A4 배경/전경/테두리 충돌 및 텍스트 토큰 배경화, B1 롤백 버튼 포커스 링 억제, C1 배지 투명도 감쇠, D1~D2 레거시 리터럴 회귀, F1~F3 상태 붕괴 및 테두리 약화, G1~G2 배지 텍스트 레이블 제거, E1~E3 알림/지표/감사 배지 전경·테두리 스왑, H2-1~H2-3 렌더된 배지 색·테두리 충돌 및 투명도, H1 미지 상태 fail-closed 우회)를 시험하였으며, **20종 전수 사살(100.0% Kill Rate)**을 확인하였습니다.

```text
================================================================================
 Card 220 (ACC-09): Reproducible Mutant Test Suite (20 Mutants: M1-M20)
 Target: ReleaseCandidateView.tsx
================================================================================

[Baseline Check] Testing unmutated code...
[Baseline Check] Clean pass (exit code 0).

[01/20] M1 (A1): KILLED in 6.5s -- ReleaseCandidateView: notice banner bg -> text-secondary (fg==bg collision)
         Reason: AssertionError: expected 'var(--color-text-secondary)' to be 'var(--color-bg-subtle)' 
[02/20] M2 (A2): KILLED in 5.8s -- ReleaseCandidateView: SLO_STATUS_CONFIG.met.bg -> status-online (fg==bg collision)
         Reason: AssertionError: SLO status met light text contrast >= 4.5:1: expected 1 to be greater 
[03/20] M3 (A3): KILLED in 5.8s -- ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.waiting.bg -> text-secondary (text token as bg)
         Reason: AssertionError: Candidate status waiting light text contrast >= 4.5:1: expected 1 to b
[04/20] M4 (A4): KILLED in 7.4s -- ReleaseCandidateView: rollback card border -> bg-surface (border==bg collision)
         Reason: AssertionError: ReleaseCandidateView violations:
[05/20] M5 (B1): KILLED in 6.6s -- ReleaseCandidateView: rollback button injects inline outline: none suppressing focus ring
         Reason: AssertionError: Total style attributes in ReleaseCandidateView must be exactly 80: exp
[06/20] M6 (C1): KILLED in 5.8s -- ReleaseCandidateView: SLO status badge opacity degraded to 0.4
         Reason: AssertionError: SLO badge P95 배치 스케줄러 지연시간 must not have degraded opacity: expected '0
[07/20] M7 (D1): KILLED in 5.7s -- ReleaseCandidateView: SLO_STATUS_CONFIG.met.color reverted to legacy literal #3fb950
         Reason: AssertionError: Explicit style objects in ReleaseCandidateView must be exactly 9: expe
[08/20] M8 (D2): KILLED in 6.6s -- ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.active.color reverted to legacy literal #58a6ff
         Reason: AssertionError: Explicit style objects in ReleaseCandidateView must be exactly 9: expe
[09/20] M9 (F1): KILLED in 6.1s -- ReleaseCandidateView: candidate active color collapsed to text-secondary (waiting collision)
         Reason: AssertionError: expected 'var(--color-text-secondary)' not to be 'var(--color-text-sec
[10/20] M10 (F2): KILLED in 5.7s -- ReleaseCandidateView: SLO breached color collapsed to status-online (met collision)
         Reason: AssertionError: SLO met and breached must have distinct colors: expected 'var(--color-
[11/20] M11 (G1): KILLED in 6.1s -- ReleaseCandidateView: SLO status badge text label {statusCfg.label} removed
         Reason: AssertionError: SLO badge text for P95 배치 스케줄러 지연시간 must match config label: expected 
[12/20] M12 (G2): KILLED in 7.0s -- ReleaseCandidateView: candidate status badge text label {rcCfg.label} removed
         Reason: AssertionError: Candidate badge text for v1.0.0-rc.2 must match config label: expected
[13/20] M13 (E1): KILLED in 6.2s -- ReleaseCandidateView: action notice error border swapped to status-online
         Reason: AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-offlin
[14/20] M14 (E2): KILLED in 6.0s -- ReleaseCandidateView: KPI vulns title color swapped to bg-surface (invisible text)
         Reason: AssertionError: ReleaseCandidateView violations:
[15/20] M15 (E3): KILLED in 6.4s -- ReleaseCandidateView: WCAG audit fail badge color swapped to status-online
         Reason: AssertionError: expected 'var(--color-status-online)' not to be 'var(--color-status-on
[16/20] M16 (F3): KILLED in 6.1s -- ReleaseCandidateView: candidate active border token reverted from brand-hover to border-subtle
         Reason: AssertionError: var(--color-border-subtle) exact occurrence count in apps/web/src must
[17/20] M17 (H2-1): KILLED in 6.0s -- ReleaseCandidateView: SLO status badge color set to statusCfg.bg (rendered fg==bg collision)
         Reason: AssertionError: SLO badge color for P95 배치 스케줄러 지연시간 must match config color: expected
[18/20] M18 (H2-2): KILLED in 5.7s -- ReleaseCandidateView: Audit status badge border set to auditCfg.bg (rendered border==bg collision)
         Reason: AssertionError: Audit badge border for wcag21-1.4.3-contrast-minimum must match config
[19/20] M19 (H2-3): KILLED in 7.1s -- ReleaseCandidateView: Audit status badge opacity degraded to 0.4
         Reason: AssertionError: Audit badge wcag21-1.4.3-contrast-minimum must not have degraded opaci
[20/20] M20 (H1): KILLED in 5.8s -- ReleaseCandidateView: getSloStatusConfig unknown fallback changed to met (fail-closed bypass)
         Reason: AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-unknow

================================================================================
 Summary: 20/20 mutants killed (100.0%)
================================================================================
 [PASS] KILLED    | ReleaseCandidateView: notice banner bg -> text-secondary (fg==bg collision) (AssertionError: expected 'var(--color-text-secondary)' to be 'var(--color-bg-subtle)' )
 [PASS] KILLED    | ReleaseCandidateView: SLO_STATUS_CONFIG.met.bg -> status-online (fg==bg collision) (AssertionError: SLO status met light text contrast >= 4.5:1: expected 1 to be greater )
 [PASS] KILLED    | ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.waiting.bg -> text-secondary (text token as bg) (AssertionError: Candidate status waiting light text contrast >= 4.5:1: expected 1 to b)
 [PASS] KILLED    | ReleaseCandidateView: rollback card border -> bg-surface (border==bg collision) (AssertionError: ReleaseCandidateView violations:)
 [PASS] KILLED    | ReleaseCandidateView: rollback button injects inline outline: none suppressing focus ring (AssertionError: Total style attributes in ReleaseCandidateView must be exactly 80: exp)
 [PASS] KILLED    | ReleaseCandidateView: SLO status badge opacity degraded to 0.4 (AssertionError: SLO badge P95 배치 스케줄러 지연시간 must not have degraded opacity: expected '0)
 [PASS] KILLED    | ReleaseCandidateView: SLO_STATUS_CONFIG.met.color reverted to legacy literal #3fb950 (AssertionError: Explicit style objects in ReleaseCandidateView must be exactly 9: expe)
 [PASS] KILLED    | ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.active.color reverted to legacy literal #58a6ff (AssertionError: Explicit style objects in ReleaseCandidateView must be exactly 9: expe)
 [PASS] KILLED    | ReleaseCandidateView: candidate active color collapsed to text-secondary (waiting collision) (AssertionError: expected 'var(--color-text-secondary)' not to be 'var(--color-text-sec)
 [PASS] KILLED    | ReleaseCandidateView: SLO breached color collapsed to status-online (met collision) (AssertionError: SLO met and breached must have distinct colors: expected 'var(--color-)
 [PASS] KILLED    | ReleaseCandidateView: SLO status badge text label {statusCfg.label} removed (AssertionError: SLO badge text for P95 배치 스케줄러 지연시간 must match config label: expected )
 [PASS] KILLED    | ReleaseCandidateView: candidate status badge text label {rcCfg.label} removed (AssertionError: Candidate badge text for v1.0.0-rc.2 must match config label: expected)
 [PASS] KILLED    | ReleaseCandidateView: action notice error border swapped to status-online (AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-offlin)
 [PASS] KILLED    | ReleaseCandidateView: KPI vulns title color swapped to bg-surface (invisible text) (AssertionError: ReleaseCandidateView violations:)
 [PASS] KILLED    | ReleaseCandidateView: WCAG audit fail badge color swapped to status-online (AssertionError: expected 'var(--color-status-online)' not to be 'var(--color-status-on)
 [PASS] KILLED    | ReleaseCandidateView: candidate active border token reverted from brand-hover to border-subtle (AssertionError: var(--color-border-subtle) exact occurrence count in apps/web/src must)
 [PASS] KILLED    | ReleaseCandidateView: SLO status badge color set to statusCfg.bg (rendered fg==bg collision) (AssertionError: SLO badge color for P95 배치 스케줄러 지연시간 must match config color: expected)
 [PASS] KILLED    | ReleaseCandidateView: Audit status badge border set to auditCfg.bg (rendered border==bg collision) (AssertionError: Audit badge border for wcag21-1.4.3-contrast-minimum must match config)
 [PASS] KILLED    | ReleaseCandidateView: Audit status badge opacity degraded to 0.4 (AssertionError: Audit badge wcag21-1.4.3-contrast-minimum must not have degraded opaci)
 [PASS] KILLED    | ReleaseCandidateView: getSloStatusConfig unknown fallback changed to met (fail-closed bypass) (AssertionError: expected 'var(--color-status-online)' to be 'var(--color-status-unknow)

SUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.
```

---

## 4. 정적 분석 및 AST 스타일-쌍 명도 대비 가드 (Test 9j-2)

TypeScript 컴파일러 AST를 기반으로 `ReleaseCandidateView.tsx` 내의 모든 인라인 스타일 객체 및 상태 설정 객체(`SLO_STATUS_CONFIG`, `AUDIT_STATUS_CONFIG`, `CANDIDATE_STATUS_CONFIG`)를 전수 검사하여, 하드코딩 색상 리터럴 검출 시 위반 보고 및 명도 대비를 엄격히 단언합니다:

- `totalStyleAttrs`: **80**
- `checkedObjects`: **9** (상태 설정 항목 7개 + 인라인 객체 2개)
- `checkedPairs`: **52**
- `unboundColorObjects`: **35**
- `coveredColorObjects`: **44** (`checkedObjects` 9 + `unboundColorObjects` 35)
- `checkedBorderObjects`: **21**
- `checkedBorderPairs`: **22**
- `violations`: **0건 (`[]`)**

---

## 5. 로컬 검증 게이트 통과 기록

```powershell
# 1. Git diff check (against base 23fbedae)
git diff --check 23fbedae
# Exit code 0 (clean, 0 trailing whitespace)

# 2. Control characters (CR 0x0D) verification
python -c "for f in ['docs/vault/30_Development/Agent별 작업/Gemini 작업 현황.md', 'docs/vault/00_Index/전체 개발 진행 현황.md']: data = open(f, 'rb').read(); assert b'\r' not in data, f'{f} has CR'"
# Exit code 0 (clean, 0 CR bytes)

# 3. Vitest contrast tokens test suite
npx vitest run tests/acc09-contrast-tokens.test.tsx
# Exit code 0: 28 passed (28 tests)

# 4. TypeScript compilation & production build
cd apps/web; npx tsc -b; npm run build; cd ../..
# Exit code 0: tsc 0 errors, build success (dist generated)

# 5. Route coverage and frontend invariant guards
pytest tests/test_route_coverage.py
# Exit code 0: 41 passed

# 6. Frontend integrity guard
python tools/check_frontend_integrity.py
# Exit code 0: 0 violations

# 7. Contract bindings verification
python tools/check_contract_bindings.py
# Exit code 0: PASS

# 8. Documentation links & metadata validation
python tools/check_docs.py
# Exit code 0: PASS

# 9. Obsidian vault sync check
python tools/sync_obsidian.py --check
# Exit code 0: 0 conflicts
```

---

## 6. 결론 및 다음 작업 인계

`ReleaseCandidateView.tsx`의 19종 84건 색상 리터럴을 0건으로 완전 토큰화하였으며, `COLOR_LITERAL_MULTISET_BASELINE`에서 빈 객체 `{}`로 래칫 고정하였습니다.
20종의 다양한 결함 변이에 대해 100.0% 사살률(20/20)을 확보하였고, 25개 주요 UI 요소의 Before/After 명도 대비를 실제 렌더 배경 기반으로 정밀 실측하여 WCAG AA 규격을 완전히 충족함을 확인하였습니다. 미지 상태는 fail-closed helper를 통해 위험 경고(UNKNOWN)로 명시되며, 렌더된 모든 배지가 config와 완벽히 결속됨을 실측하였습니다.

- **작업 브랜치**: `agent/gemini/c220-release-contrast`
- **PR 대상 브랜치**: `agent/gemini/c218-recovery-contrast`
- **독립 검토 요청**: Claude UI (접근성/UI/테스트), Codex (계약/토큰/불변식)
