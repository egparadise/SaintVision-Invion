# 2026-10-02 02:57:25 KST — Card 197: 모델 계보 화면 (ModelLineageView) 색상 리터럴 inventory 전수(457→0), 대비 표본/DOM 결속 감사 및 디자인 토큰 승격 (Gemini)

- **문서 ID**: HIST-GEMINI-CARD197-MODEL-LINEAGE-CONTRAST
- **작업 branch**: agent/gemini/c197-model-lineage-contrast
- **Base commit**: ea82c6ae118173e0d590c2d017ab1734eda89141 (PR #293 r4 HEAD)
- **KST 시각**: 2026-10-02 02:57:25 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 감사 목적

ACC-09(접근성 명도 대비 적합화) 트랙의 후속 영역으로, 프런트엔드 소스 코드 중 색상 리터럴이 가장 밀집되어 있던 모델 레지스트리 및 계보 관리 화면(`apps/web/src/features/mlops/ModelLineageView.tsx`)의 색상 리터럴을 전수 감사하고 플랫폼 정본 디자인 토큰으로 전면 승격하였습니다.

- **대상 파일**:
  - `apps/web/src/features/mlops/ModelLineageView.tsx` (기존 baseline 리터럴: **457건**)
- **감사 및 조치 결과**:
  - 하드코딩 색상 리터럴을 **0건**으로 전수 해소 (감소율: **100%**).
  - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Fail-Closed `COLOR_LITERAL_MULTISET_BASELINE`에서 `ModelLineageView.tsx`의 허용 multiset을 `{}` (0건)으로 래칫 갱신.
  - 전역 `var(--color-border-subtle)` 사용 횟수가 233건에서 **292건**(+59건)으로 증가하였으며, 사용 파일 수가 22개에서 **23개**(`ModelLineageView.tsx` 신규 편입)로 래칫 단언 갱신.
  - 레거시 하드코딩 리터럴 잔여 상한 래칫 강화:
    - `#64748b`: 15건(6개 파일) $\rightarrow$ **5건 이하(4개 파일 이하)**
    - `#e2e8f0`: 3건(2개 파일) $\rightarrow$ **1건 이하(1개 파일 이하)**
    - `#30363d`: 169건(15개 파일) $\rightarrow$ **116건 이하(14개 파일 이하)**
  - 컴포넌트 DOM 렌더링 검증 시험(Test 9d) 및 Revert-Fail Probes 32~37을 신설하여 8종 변이 100% 사살 실측.

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
| **메인 헤더 타이틀**<br>(ModelLineageView:1031) | `#f0f6fc` on `#ffffff` (Light 가상)<br>`#f0f6fc` on `#111827` (Dark) | **1.09:1** / 16.30:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-primary)` on<br>`var(--color-bg-surface)` | **17.85:1** | **16.98:1** | **PASS** (>= 4.5:1) |
| **보조 설명 및 서브타이틀**<br>(ModelLineageView:1034) | `#c9d1d9` on `#ffffff` (Light 가상)<br>`#c9d1d9` on `#111827` (Dark) | **1.54:1** / 11.49:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-secondary)` on<br>`var(--color-bg-surface)` | **7.58:1** | **14.33:1** | **PASS** (>= 4.5:1) |
| **부차/보조 텍스트 (Muted on Surface)**<br>(입력 라벨, 카드 설명 :1092, :1116, :1140) | `#8b949e` on `#ffffff` (Light 가상)<br>`#8b949e` on `#111827` (Dark) | **3.08:1** / 5.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-surface)` | **5.75:1** | **6.99:1** | **PASS** (>= 4.5:1) |
| **보조 텍스트 (Muted on Subtle)**<br>(W3 Seam 배지 미검증 텍스트 :1075) | `#8b949e` on `#f1f5f9` (Light 가상)<br>`#8b949e` on `#1f2937` (Dark) | **2.81:1** / 4.77:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-text-muted)` on<br>`var(--color-bg-subtle)` | **5.25:1** | **5.78:1** | **PASS** (>= 4.5:1) |
| **활성 탭 텍스트 (Brand on Subtle)**<br>(계보 조회 탭 `tab-trace` :1190) | `#58a6ff` on `#f1f5f9` (Light 가상)<br>`#58a6ff` on `#1f2937` (Dark) | **2.31:1** / 5.81:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-brand-primary)` on<br>`var(--color-bg-subtle)` | **4.72:1** | **5.77:1** | **PASS** (>= 4.5:1) |
| **권한 없음 배너 텍스트 (Offline on Subtle)**<br>(승인 권한 없음 경고 :1165) | `#f85149` on `#f1f5f9` (Light 가상)<br>`#f85149` on `#1f2937` (Dark) | **3.06:1** / **4.38:1** | **FAIL**<br>(양 테마 < 4.5:1) | `var(--color-status-offline)` on<br>`var(--color-bg-subtle)` | **5.91:1** | **5.31:1** | **PASS** (>= 4.5:1) |
| **미노출 고지 배너 텍스트 (Degraded on Subtle)**<br>(계보 미노출 안내 :2156) | `#fed7aa` on `#f1f5f9` (Light 가상)<br>`#fed7aa` on `#1f2937` (Dark) | **1.24:1** / 10.84:1 | **FAIL**<br>(Light < 4.5:1) | `var(--color-status-degraded)` on<br>`var(--color-bg-subtle)` | **4.58:1** | **6.83:1** | **PASS** (>= 4.5:1) |
| **대화형 테두리 (Border on Surface)**<br>(컨트롤 패널 컨테이너 테두리 :1019) | `#30363d` on `#ffffff` (Light 가상)<br>`#30363d` on `#111827` (Dark) | 12.20:1 / **1.45:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-surface)` | **3.48:1** | **3.73:1** | **PASS** (>= 3.0:1) |
| **대화형 테두리 (Border on Subtle)**<br>(입력 필드, Seam 배지, 탭 하단선 :1065, :1106, :1180) | `#30363d` on `#f1f5f9` (Light 가상)<br>`#30363d` on `#1f2937` (Dark) | 11.14:1 / **1.20:1** | **FAIL**<br>(Dark < 3.0:1) | `var(--color-border-subtle)` on<br>`var(--color-bg-subtle)` | **3.18:1** | **3.08:1** | **PASS** (>= 3.0:1) |

---

## 3. 세부 파일별 조치 내역

### 3.1 `apps/web/src/features/mlops/ModelLineageView.tsx`
- **리터럴 감축**: 457건 -> **0건** (전수 제거, 100% 해소).
- **상세 변경 사항**:
  - 컨트롤 패널 상위 컨테이너: `var(--color-bg-surface)` 배경, `var(--color-border-subtle)` 테두리 결속.
  - W3 Seam Badge (`badge-w3-verify-seam`): 미검증 시 `var(--color-bg-subtle)` 배경, `var(--color-text-muted)` 텍스트, `var(--color-border-subtle)` 테두리 결속; 검증 완료 시 `var(--color-brand-primary-bg)` 배경, `var(--color-brand-primary-fg)` 텍스트, `var(--color-brand-primary)` 테두리 결속.
  - Project ID 및 Model ID 입력 필드 (`input-project-id`): `var(--color-bg-subtle)` 배경, `var(--color-text-primary)` 텍스트, `var(--color-border-subtle)` 테두리 결속.
  - 거버넌스 승인 권한 없음 배너 (`banner-no-approve-permission`): `var(--color-bg-subtle)` 배경, `var(--color-status-offline)` 텍스트 및 테두리 결속 (Light 5.91:1, Dark 5.31:1).
  - 네비게이션 탭 바 (`tab-trace`, `tab-register`): 활성 탭 `var(--color-bg-subtle)` 배경, `var(--color-brand-primary)` 텍스트 및 테두리 결속; 비활성 탭 `transparent` 배경, `var(--color-text-muted)` 텍스트 결속.
  - 계보 미노출 안내 배너 (`lineage-unexposed-notice`): `var(--color-bg-subtle)` 배경, `var(--color-status-degraded)` 텍스트 및 테두리 결속 (Light 4.58:1, Dark 6.83:1).
  - SVG 및 D3/Canvas 그래프 요소, 테이블, 모달, 상태 뱃지, 코드 블록 등 전 영역의 하드코딩 헥사/RGB 리터럴을 시맨틱 토큰으로 완전 승격.

### 3.2 `apps/web/tests/model-lineage.test.ts`
- `parseRgba` 테스트 헬퍼 함수가 하드코딩된 `rgba(...)` 문자열뿐만 아니라 CSS 변수 토큰(`var(--...)`) 형태의 스타일 값도 안전하게 해석할 수 있도록 지원 보강 (33/33 passed 100%).

### 3.3 `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **Test 9d 신설**: `ModelLineageView` 컴포넌트를 실제 렌더링하고, DOM 노드 스타일에서 추출한 CSS 변수를 기반으로 Light/Dark 테마 실제 렌더 배경 위 동적 명도 대비율(텍스트 >= 4.5:1, UI 경계 >= 3.0:1)을 검증.
- **Revert-Fail Probes 32~37 추가**: 과거 구형 결함 리터럴 조합(`#f0f6fc` on light surface, `#c9d1d9` on light surface, `#8b949e` on light surface, `#58a6ff` on light surface, `#fed7aa` on light subtle, `#30363d` on dark surface)이 WCAG AA 기준을 엄격히 미달함을 단언.
- **Fail-Closed 래칫 갱신**:
  - `ModelLineageView.tsx` multiset baseline: `{}` (0건)
  - `var(--color-border-subtle)` exact 292 / 23 files
  - 레거시 리터럴 상한치 강화 (`#64748b` <= 5/4, `#e2e8f0` <= 1/1, `#30363d` <= 116/14)

---

## 4. 테스트 및 변이 사살 (Mutation Verification) 증거

### 4.1 8종 변이 시험 결과 (100% 사살)

| 변이 ID | 변이 유형 | 변이 조작 대상 | 기대 동작 및 사살 결과 | 사살 여부 |
|---|---|---|---|---|
| **M1** | Foreground Swap | `banner-no-approve-permission` 텍스트를 `var(--color-bg-subtle)`로 치환 | 컨테이너 배경과 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |
| **M2** | Background Swap | `tab-trace` 활성 탭 배경을 `var(--color-brand-primary)`로 치환 | 텍스트/테두리와 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |
| **M3** | Foreground Swap | `tab-trace` 활성 탭 텍스트를 `var(--color-bg-subtle)`로 치환 | 탭 배경과 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |
| **M4** | Border Swap | `badge-w3-verify-seam` 테두리를 `transparent`로 치환 | DOM 테두리 토큰 바인딩 단언 실패로 Test 9d Assertion 실패 | **KILLED** |
| **M5** | Background Swap | `lineage-unexposed-notice` 배경을 `var(--color-status-degraded)`로 치환 | 텍스트/테두리와 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |
| **M6** | Token Reversion | 메인 헤더 타이틀 텍스트를 구형 리터럴 `#f0f6fc`로 회귀 | F2 멀티셋 래칫 위반 및 Probe 32 실패 | **KILLED** |
| **M7** | Foreground Swap | `badge-w3-verify-seam` 텍스트를 `var(--color-bg-subtle)`로 치환 | 컨테이너 배경과 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |
| **M8** | Foreground Swap | `input-project-id` 텍스트를 `var(--color-bg-subtle)`로 치환 | 입력창 배경과 1:1 대비 결함으로 Test 9d Assertion 실패 | **KILLED** |

---

## 5. 게이트 통과 증거

1. **Vitest Contrast & Token Ratchet**:
   - `npm test -- tests/acc09-contrast-tokens.test.tsx` -> **15 passed (15)**
   - `var(--color-border-subtle)` exact **292 / 23 files** PASS.
   - `ModelLineageView.tsx` multiset baseline: `{}` (0건) PASS.
2. **Defect Regression Suite**:
   - `npm test -- tests/s11-defect-fixes.test.tsx` -> **16 passed (16)**
3. **Model Lineage Suite**:
   - `npm test -- tests/model-lineage.test.ts` -> **33 passed (33)**
4. **TypeScript Build & Bundle**:
   - `npx tsc -b` -> exit code **0** (에러 0건)
   - `npm run build` -> exit code **0** (프로덕션 번들 정상 생성)
5. **Python Back-end Invariants & Routes**:
   - `pytest tests/test_route_coverage.py` -> exit code **0** (41 passed 100%)
6. **Integrity & Contract Tools**:
   - `python tools/check_frontend_integrity.py` -> exit code **0** (93 files scanned, 0 violations)
   - `python tools/check_contract_bindings.py` -> exit code **0** (55 fixtures, 20 bound types)
   - `python tools/check_docs.py` -> exit code **0** (PASS)
   - `python tools/check_doc_path_citations.py --ratchet --base-ref c41fe2da` -> exit code **0** (PASS)
   - `git diff --check` -> exit code **0** (Clean)
