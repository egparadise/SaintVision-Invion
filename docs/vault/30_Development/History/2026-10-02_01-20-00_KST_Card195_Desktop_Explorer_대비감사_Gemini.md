# 2026-10-02 01:20:00 KST — Card 195: 데스크톱 탐색기 (ResourceExplorer & InvFileExplorer) Light/Dark 명도 대비 전수 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD195-DESKTOP-EXPLORER-CONTRAST
- **작업 branch**: agent/gemini/c195-desktop-explorer-contrast
- **Base commit**: db37dbc53f2e45ed987b9ed0e0b81ed88f2a7644 (PR #290 HEAD)
- **KST 시각**: 2026-10-02 01:20:00 KST (r1 보강: 02:00:00 KST, r2 보강: 02:22:00 KST)
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 전수 적합화) 트랙의 일환으로, 데스크톱 UI에서 가장 빈번하게 조회 및 조작되는 양대 탐색기 화면의 색상 리터럴을 전수 감사하고 디자인 토큰으로 승격하였습니다.

- **대상 파일**:
  1. `apps/web/src/features/desktop/ResourceExplorer.tsx` (기존 baseline 리터럴: **390건**)
  2. `apps/web/src/features/desktop/InvFileExplorer.tsx` (기존 baseline 리터럴: **124건**)
- **감사 및 조치 결과**:
  - 두 파일 모두 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (감소율: **100%**).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed COLOR_LITERAL_MULTISET_BASELINE에서 두 파일의 허용 multiset을 `{}` (0건)으로 전면 갱신하여 순수 감소 래칫을 강제.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 141건에서 **233건**(+92건)으로 증가하였으며, 사용 파일 수가 21개에서 **22개**(`InvFileExplorer.tsx` 신규 편입)로 래칫 단언 갱신.
  - primary 버튼을 `var(--color-brand-primary-bg)` 및 `var(--color-brand-primary-fg)` (#ffffff)로 결속하여 기존 DEF-S11-09 불변식을 완벽 준수.
  - 활성 칩 및 버전 배지 텍스트를 `var(--color-brand-hover)`(#1d4ed8 in light, #93c5fd in dark)로 결속하여 `var(--color-brand-subtle)` 배경 위에서 4.5:1 이상(Light 5.49:1, Dark 8.11:1)을 충족.
  - 비활성화(disabled) 버튼(`inv-canonical-lookup-btn`, `repair-replicas-btn`)의 경우 WCAG 2.2 SC 1.4.3(비활성 UI 컴포넌트 예외)에 해당하나, 시각적 일관성과 가독성을 위해 `var(--color-bg-subtle)` 배경, `var(--color-text-muted)` 텍스트(Light 5.25:1, Dark 5.78:1), `var(--color-border-subtle)` 테두리(Light 3.18:1, Dark 3.08:1)를 부여하여 비활성 상태에서도 가독 기준을 상회.
  - 과거 비표준 보라색 계열(`#c084fc`, `#a855f7`) 리터럴은 임의의 새 토큰을 난립시키지 않고 플랫폼의 표준 브랜드 토큰군(`var(--color-brand-primary)`, `var(--color-brand-subtle)`)으로 의도적으로 통합·정리.

---

## 2. 명도 대비 전수 실측 및 개선 결과표

### 2.1 실제 렌더 배경 기반 전수 실측치 비교 (Before vs After)

> **배경 실측 기준**:
> - Light 테마: Surface = `#ffffff`, Subtle = `#f1f5f9`
> - Dark 테마 (SaintVision 베이스 패널 정본): Surface = `#0f172a`, Subtle = `#1e293b`

| 요소 / 위치 (파일:행) | 이전 리터럴 (실제 렌더 배경) | 이전 대비율 (Light / Dark) | 이전 판정 | 신규 디자인 토큰 (실제 렌더 배경) | 신규 대비율 (Light) | 신규 대비율 (Dark) | WCAG AA 충족 여부 |
|---|---|---|---|---|---|---|---|
| **기본 액션 버튼 (Primary Button)**<br>(ResourceExplorer:1316, :1505, :1810, :1949, :2203;<br>InvFileExplorer:520, :635, :679, :834, :1025) | `#ffffff` on `#2563eb`<br>(단일 라인 `var(--color-brand-primary)`) | 5.17:1 / 5.17:1 | **FAIL**<br>(DEF-S11-09 위반) | `var(--color-brand-primary-fg)` on<br>`var(--color-brand-primary-bg)` | **5.17:1** | **6.70:1** | **PASS** (>= 4.5:1, DEF-S11-09 준수) |
| **활성 네임스페이스 칩 텍스트**<br>(InvFileExplorer:669-671) | `#2563eb` on `#dbeafe` (Light)<br>`#93c5fd` on `rgba(59, 130, 246, 0.2)` over `#0f172a` (Dark) | **4.24:1** / 7.23:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-brand-subtle)` | **5.49:1** | **8.11:1** | **PASS** (>= 4.5:1) |
| **활성 네임스페이스 칩 테두리**<br>(InvFileExplorer:668-669) | `#2563eb` on `#dbeafe` (Light)<br>`#3b82f6` on `rgba(59, 130, 246, 0.2)` over `#0f172a` (Dark) | **4.24:1** / 4.14:1 | PASS (>= 3.0:1) | `var(--color-brand-hover)` on<br>`var(--color-brand-subtle)` | **5.49:1** | **8.11:1** | **PASS** (>= 3.0:1) |
| **파일 버전/등급 배지 텍스트**<br>(InvFileExplorer:848-852) | `#2563eb` on `#dbeafe` (Light)<br>`#60a5fa` on `rgba(59, 130, 246, 0.15)` over `#1e293b` (Dark) | **4.24:1** / 6.88:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-hover)` on<br>`var(--color-brand-subtle)` | **5.49:1** | **8.11:1** | **PASS** (>= 4.5:1) |
| **비활성 버튼 텍스트**<br>(InvFileExplorer:531-532, :1202-1206) | `#ffffff` on `#7b8b9e` (Light)<br>`#0f172a` on `#64748b` (Dark) | **3.48:1** / **3.75:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-subtle)` | **5.25:1** | **5.78:1** | **PASS** (>= 4.5:1, SC 1.4.3 예외) |
| **비활성 버튼 테두리**<br>(InvFileExplorer:531, :1207) | `#7b8b9e` on `#f1f5f9` (Light)<br>`#64748b` on `#1e293b` (Dark) | 3.18:1 / 3.08:1 | PASS (>= 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |
| **부차/보조 텍스트 (Muted on Surface)**<br>(ResourceExplorer:1260, :1342; InvFileExplorer:465, :1097) | `#94a3b8` on `#ffffff` (Light)<br>`#94a3b8` on `#0f172a` (Dark) | **2.56:1** / 6.96:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-surface)` | **5.75:1** | **6.99:1** | **PASS** (>= 4.5:1) |
| **보조 텍스트 (Muted on Subtle)**<br>(노드 하트비트 ResourceExplorer:1285; 용량 카드 라벨 :832, :858; InvFileExplorer:1088) | `#94a3b8` on `#f1f5f9` (Light)<br>`#94a3b8` on `#1e293b` (Dark) | **2.34:1** / 5.71:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-subtle)` | **5.25:1** | **5.78:1** | **PASS** (>= 4.5:1) |
| **정상/가용 텍스트 (Online on Surface)**<br>(InvFileExplorer 복제본 상태 :1106; ResourceExplorer :1244) | `#34d399` on `#ffffff` (Light)<br>`#34d399` on `#0f172a` (Dark) | **1.92:1** / 9.29:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-surface)` | **5.02:1** | **7.79:1** | **PASS** (>= 4.5:1) |
| **정상 배지 텍스트 (Online on Subtle)**<br>(InvFileExplorer:1069; ResourceExplorer:754) | `#34d399` on `#f1f5f9` (Light)<br>`#34d399` on `#1e293b` (Dark) | **1.75:1** / 7.61:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-online)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.44:1** | **PASS** (>= 4.5:1) |
| **경고/장애 텍스트 (Offline on Surface)**<br>(ResourceExplorer:747; InvFileExplorer:985, :1004, :1054, :1125) | `#f87171` on `#ffffff` (Light)<br>`#f87171` on `#0f172a` (Dark) | **2.77:1** / 6.45:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-lost)` on<br>`var(--color-bg-surface)` | **5.86:1** | **6.45:1** | **PASS** (>= 4.5:1) |
| **장애 배너 텍스트 (Offline on Subtle)**<br>(ResourceExplorer 에러 배너 :780, :795; :1420) | `#ef4444` on `#f1f5f9` (Light)<br>`#ef4444` on `#1e293b` (Dark) | **3.44:1** / **3.89:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **강조/링크 텍스트 (Brand on Surface)**<br>(선택 탭, URI 강조 ResourceExplorer:620, :1375; InvFileExplorer:442) | `#60a5fa` on `#ffffff` (Light)<br>`#60a5fa` on `#0f172a` (Dark) | **2.53:1** / 7.02:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-primary)` on<br>`var(--color-bg-surface)` | **5.17:1** | **6.98:1** | **PASS** (>= 4.5:1) |
| **강조 텍스트 (Brand on Subtle)**<br>(신선도 고지, 계획 결과 메시지 ResourceExplorer:768, :795, :1150) | `#60a5fa` on `#f1f5f9` (Light)<br>`#60a5fa` on `#1e293b` (Dark) | **2.31:1** / 5.75:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-primary)` on<br>`var(--color-bg-subtle)` | **4.72:1** | **5.77:1** | **PASS** (>= 4.5:1) |
| **대화형 테두리 (Border on Surface)**<br>(노드 카드, 입력창, 컨테이너 ResourceExplorer:1235; InvFileExplorer:670) | `#334155` on `#ffffff` (Light)<br>`#334155` on `#0f172a` (Dark) | 10.35:1 / **1.72:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-surface)` | **3.48:1** | **3.73:1** | **PASS** (>= 3.0:1) |
| **대화형 테두리 (Border on Subtle)**<br>(용량 카드, 주소창, 배지 테두리 ResourceExplorer:830, :856; InvFileExplorer:625, :1088) | `#e2e8f0` on `#f1f5f9` (Light)<br>`#334155` on `#1e293b` (Dark) | **1.13:1** / **1.41:1** | **FAIL**<br>(양 테마 < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/desktop/ResourceExplorer.tsx`
- **리터럴 감축**: 390건 -> **0건** (전수 제거).
- **상세 변경 사항**:
  - `{node_id}` 엔티티가 정규식 헥사코드(#123, #125)로 오인식되던 문제를 `{'{node_id}'}`로 정정하여 불필요한 리터럴 오탐 제거.
  - 중복 선언되어 있던 4개 버튼의 redundant `border: 'none'` 속성 정리 (vite/esbuild 빌드 경고 0건 해소).
  - 버튼 요소 5곳(`:1316`, `:1505`, `:1810`, `:1949`, `:2203`)의 배경을 `var(--color-brand-primary-bg)` 및 `var(--color-brand-primary-fg)` (#ffffff)로 결속하여 DEF-S11-09 단일 라인 불변식을 완벽 준수.
  - 신선도 고지(`node-freshness-notice`): `var(--color-brand-primary)` 텍스트 및 테두리, `var(--color-bg-subtle)` 배경 결속.
  - 라이브니스 스윕 버튼(`liveness-sweep-btn`): `var(--color-bg-subtle)` 배경, `var(--color-status-offline)` 텍스트 및 테두리 결속 (Light 5.91:1, Dark 5.31:1).
  - 온라인 노드 배지: `var(--color-bg-subtle)` 배경, `var(--color-status-online)` 텍스트 및 테두리 결속 (Light 4.58:1, Dark 6.44:1).
  - 논리 용량 카드 4종(`logical-vcpu-card`, `logical-ram-card`, `logical-gpu-card`, `logical-storage-card`): `var(--color-bg-subtle)` 배경, `var(--color-border-subtle)` 테두리, `var(--color-text-primary)` 및 `var(--color-text-muted)` 텍스트 결속.
  - 필터 버튼(`filter-all-btn` 등): 활성 상태 `var(--color-bg-subtle)` 배경, `var(--color-brand-primary)` 텍스트 및 테두리 결속.
  - 물리 노드 카드(`node-card-...`): 선택 상태 `var(--color-brand-primary)` 테두리, 기본 상태 `var(--color-border-subtle)` 테두리.
  - 스토리지 기여도 테이블 및 관측 패널: `var(--color-border-subtle)` 테두리, `var(--color-bg-surface)` 헤더 및 바디 배경.
  - 배치 계획 생성 결과 메시지(`plan-result-message`): `var(--color-brand-primary)` 텍스트 (Light 4.72:1, Dark 5.77:1).
  - 노드 탐색 성공 알림 메시지(`discovery-action-success`): `var(--color-brand-primary)` 텍스트 및 테두리, `var(--color-bg-subtle)` 배경 결속 (Light 6.55:1, Dark 5.75:1).

### 3.2 `apps/web/src/features/desktop/InvFileExplorer.tsx`
- **리터럴 감축**: 124건 -> **0건** (전수 제거).
- **상세 변경 사항**:
  - 주소창 입력 필드(`inv-address-bar`): `var(--color-bg-subtle)` 배경, `var(--color-text-primary)` 텍스트, `var(--color-border-subtle)` 테두리.
  - 네비게이션 버튼(`inv-navigate-btn`): `var(--color-brand-primary-bg)` 배경, `var(--color-brand-primary-fg)` 텍스트.
  - 활성 네임스페이스 칩(`nav-namespace-...`): `var(--color-brand-subtle)` 배경, `var(--color-brand-hover)` 텍스트 및 테두리 (Light 5.49:1, Dark 8.11:1).
  - 파일 리스트 행: 선택 시 `var(--color-brand-subtle)` 배경, `var(--color-brand-primary)` 테두리.
  - 파일 무결성 배지(`integrity-badge`): 미검증/대기 상태 `var(--color-bg-subtle)` 배경, `var(--color-status-degraded)` 텍스트 및 테두리 (Light 4.58:1, Dark 6.83:1).
  - 복제본 헬스 배지: 정상 상태 `var(--color-bg-subtle)` 배경, `var(--color-status-online)` 텍스트 및 테두리.
  - 파일 버전/등급 배지(`file-version-badge`): `var(--color-brand-subtle)` 배경, `var(--color-brand-hover)` 텍스트 및 테두리 (Light 5.49:1, Dark 8.11:1).
  - 비활성화된 정규 조회 버튼(`inv-canonical-lookup-btn`) 및 복구 버튼(`repair-replicas-btn`): `var(--color-bg-subtle)` 배경, `var(--color-text-muted)` 텍스트 (Light 5.25:1, Dark 5.78:1), `var(--color-border-subtle)` 테두리.
  - 복구 실패 알림 배너(`repair-action-error`): `var(--color-bg-surface)` 배경, `var(--color-status-lost)` 텍스트 및 테두리 (Light 5.86:1, Dark 6.45:1).

---

## 4. 테스트 및 변이 사살 (Mutation Verification) 증거

`apps/web/tests/acc09-contrast-tokens.test.tsx`의 9c 테스트를 확장하여, 컴포넌트 렌더링 후 실제 DOM 노드의 스타일 프로퍼티에서 추출한 CSS 변수를 기반으로 런타임 명도 대비를 계산하고 단언하도록 구성하였습니다.

### 4.1 12종 변이 시험 결과 (100% 사살)

| 변이 ID | 변이 유형 | 변이 조작 대상 | 기대 동작 및 사살 결과 | 사살 여부 |
|---|---|---|---|---|
| **M1** | Background Substitution | ResourceExplorer `node-freshness-notice` 배경을 `var(--color-brand-primary)`로 치환 | 텍스트와 배경의 명도 대비 1.0:1 미달로 Test 9c 1.a Assertion 실패 | **KILLED** |
| **M2** | Token Reversion | InvFileExplorer 정상 복제본 배지 색상을 구형 리터럴 `#34d399`로 회귀 | F2 멀티셋 래칫 위반 및 Test 9c 2.d Assertion 실패 | **KILLED** |
| **M3** | Background Substitution | InvFileExplorer `inv-address-bar` 배경을 `var(--color-text-primary)`로 치환 | 텍스트와 배경의 명도 대비 1.0:1 미달로 Test 9c 2.a Assertion 실패 | **KILLED** |
| **M4** | Token Reversion | ResourceExplorer 노드 하트비트 색상을 구형 리터럴 `#94a3b8`로 회귀 | F2 멀티셋 래칫 위반 및 Test 9c 1.e Assertion 실패 | **KILLED** |
| **M5 (P2)** | Border Swap | ResourceExplorer `logical-ram-card` 테두리를 `transparent`로 치환 | DOM 테두리 토큰 바인딩 단언 실패로 Test 9c 1.g Assertion 실패 | **KILLED** |
| **M6 (P4)** | Foreground Swap | ResourceExplorer `plan-result-message` 색상을 `var(--color-text-muted)`로 치환 | DOM 전경 토큰 바인딩 단언 실패로 Test 9c 1.h Assertion 실패 | **KILLED** |
| **M7 (P5)** | Token Reversion | InvFileExplorer 활성 칩 텍스트를 `var(--color-brand-primary)`로 회귀 | 라이트 테마 대비 4.24:1로 4.5:1 미달 Assertion 실패 | **KILLED** |
| **M8 (Codex)** | Background Swap | InvFileExplorer 활성 칩 배경을 `var(--color-brand-primary)`로 치환 | 칩 배경 토큰 바인딩 단언 실패로 Test 9c 2.e Assertion 실패 | **KILLED** |
| **M9** | Token Reversion | InvFileExplorer 파일 버전 배지 텍스트를 `var(--color-brand-primary)`로 회귀 | 라이트 테마 대비 4.24:1로 4.5:1 미달 Assertion 실패 | **KILLED** |
| **M10** | Background Swap | InvFileExplorer 비활성 복구 버튼 배경을 `var(--color-brand-subtle)`로 치환 | 비활성 버튼 배경 바인딩 단언 실패로 Test 9c 2.h Assertion 실패 | **KILLED** |
| **M11 (Codex r2)** | Foreground Swap | ResourceExplorer `discovery-action-success` 텍스트를 `var(--color-bg-subtle)`로 치환 | 컨테이너 배경과 1:1 대비 결함으로 Test 9c 1.i 및 Probe 30 실패 | **KILLED** |
| **M12 (Codex r2)** | Background Swap | InvFileExplorer `repair-action-error` 배경을 `var(--color-status-lost)`로 치환 | 에러 텍스트/테두리와 1:1 대비 결함으로 Test 9c 2.i 및 Probe 31 실패 | **KILLED** |

---

## 5. 게이트 통과 증거

1. **Vitest Contrast & Token Ratchet**:
   - `npm test -- tests/acc09-contrast-tokens.test.tsx` -> **14 passed (14)**
   - `var(--color-border-subtle)` exact **233 / 22 files** PASS.
   - `ResourceExplorer.tsx` 및 `InvFileExplorer.tsx` multiset baseline: `{}` (0건) PASS.
2. **Defect Regression Suite**:
   - `npm test -- tests/s11-defect-fixes.test.tsx` -> **16 passed (16)**
   - DEF-S11-09 primary button rule (단일 라인 regex 준수 및 허용 파일 2개 엄격 유지) PASS.
3. **Desktop Layout Suite**:
   - `npm test -- tests/desktop-layout.test.tsx tests/desktop-shell-a11y.test.tsx tests/virtual-desktop.test.ts` -> **38 passed (38)**
4. **TypeScript Build & Bundle**:
   - `npx tsc -b` -> exit code **0** (에러 0건)
   - `npm run build` -> exit code **0** (프로덕션 번들 정상 생성)
5. **Python Back-end Invariants & Routes**:
   - `pytest tests/test_route_coverage.py` -> exit code **0** (라우트 및 EvidenceViewer 가드 PASS)
6. **Integrity & Contract Tools**:
   - `python tools/check_frontend_integrity.py` -> exit code **0**
   - `python tools/check_contract_bindings.py` -> exit code **0**
   - `python tools/check_docs.py` -> exit code **0**
   - `python tools/check_doc_path_citations.py --ratchet --base-ref c41fe2da` -> exit code **0**
