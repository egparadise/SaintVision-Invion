# 2026-10-01 23:00:00 KST — Card 193: NodeDetail 잔여 리터럴 9건 전수 해소 및 대비 래칫 강화 (Gemini)

- **문서 ID**: `HIST-GEMINI-CARD193-NODEDETAIL-CONTRAST`
- **작업 branch**: `agent/gemini/c193-nodedetail-residual`
- **Base commit**: `3e19b68260c71248ee591eac1d3d839e84d84f4e` (PR #288 HEAD)
- **KST 시각**: 2026-10-01 23:00:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude (UI/접근성/테스트 축), Codex (디자인 토큰/무결성/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 작업 개요 및 인계 배경

- **배경**: PR #288 (Card 189, head `3e19b682`)의 History §7 백로그에 등록되었던 `NodeDetail.tsx`의 잔여 색상 리터럴 9건을 전수 해소.
- **핵심 목표**:
  1. WCAG 2.2 AA 기준 준수: 텍스트 요소는 라이트/다크 테마 모두 $\ge 4.5:1$, 비텍스트 UI(배지 경계선)는 $\ge 3.0:1$을 달성.
  2. 신규 토큰 유입 없이 기존 표준 디자인 토큰(`var(--color-status-online)`, `var(--color-brand-primary)`, `var(--color-bg-subtle)`, `var(--color-text-muted)`, `var(--color-border-subtle)`)으로 100% 매핑.
  3. `COLOR_LITERAL_MULTISET_BASELINE`에서 `NodeDetail.tsx`의 리터럴 9건(5개 키)을 완전히 삭제하여 순수 감소 래칫 달성.
  4. 실제 렌더링된 DOM 전경/배경 토큰 추출 및 동적 대비율 계산, 11종 변이(토큰 되돌림 9종, 배경 바꿔치기 1종, 신규 리터럴 주입 1종) 전원 사살 실측.

---

## 2. Before / After 대비율 개선 실측표

| 대상 요소 | 기존 리터럴 및 배경 | 기존 대비율 (Light / Dark) | 변경 후 디자인 토큰 및 배경 | 변경 후 대비율 (Light / Dark) | WCAG 기준 충족 |
|---|---|---|---|---|---|
| **최근 하트비트 타임라인 online 상태** (`:440`) | `#3fb950` on `#ffffff` / `#111827` (surface) | Light **2.54:1** (FAIL) / Dark 7.60:1 | `var(--color-status-online)` on surface (`#ffffff` / `#111827`) | Light **5.05:1** / Dark **7.60:1** | $\ge 4.5:1$ (본문 텍스트) |
| **측정됨 배지 텍스트** (`:249`) | `#3fb950` on `rgba(46,160,67,0.15)` / canvas | Light **2.16:1** (FAIL) / Dark 5.79:1 | `var(--color-status-online)` on `var(--color-bg-subtle)` | Light **4.50:1** / Dark **6.42:1** | $\ge 4.5:1$ (배지 텍스트) |
| **측정됨 배지 배경** (`:249`) | `rgba(46, 160, 67, 0.15)` | 임의 틴트 리터럴 | `var(--color-bg-subtle)` | - | 토큰화 (리터럴 제거) |
| **측정됨 배지 테두리** (`:250`) | `#2ea043` on canvas | Light **2.88:1** (FAIL) / Dark 4.88:1 | `var(--color-status-online)` on `var(--color-bg-subtle)` | Light **4.50:1** / Dark **6.42:1** | $\ge 3.0:1$ (UI 경계) |
| **미측정 배지 배경** (`:249`) | `rgba(110, 118, 129, 0.2)` | 임의 틴트 리터럴 | `var(--color-bg-subtle)` | - | 토큰화 (리터럴 제거) |
| **미측정 배지 테두리** (`:250`) | `var(--color-border-subtle)` | - | `var(--color-border-subtle)` on `var(--color-bg-subtle)` | Light **3.18:1** / Dark **3.08:1** | $\ge 3.0:1$ (UI 경계) |
| **예약 할당 (Reserved) 수치** (`:268`) | `#58a6ff` on `var(--color-bg-canvas)` | Light **2.39:1** (FAIL) / Dark 7.28:1 | `var(--color-brand-primary)` on `var(--color-bg-canvas)` | Light **5.02:1** / Dark **7.28:1** | $\ge 4.5:1$ (본문 텍스트) |
| **가용 잔여 (Spare) 수치** (`:274`) | `#3fb950` on `var(--color-bg-canvas)` | Light **2.45:1** (FAIL) / Dark 7.98:1 | `var(--color-status-online)` on `var(--color-bg-canvas)` | Light **4.80:1** / Dark **7.98:1** | $\ge 4.5:1$ (본문 텍스트) |
| **4-Tier 관측 사용량 수치** (`:367`) | `#58a6ff` on `var(--color-bg-subtle)` | Light **2.24:1** (FAIL) / Dark 5.85:1 | `var(--color-brand-primary)` on `var(--color-bg-subtle)` | Light **4.70:1** / Dark **5.85:1** | $\ge 4.5:1$ (본문 텍스트) |
| **4-Tier 관측 여유량 수치** (`:375`) | `#3fb950` on `var(--color-bg-subtle)` | Light **2.26:1** (FAIL) / Dark 6.42:1 | `var(--color-status-online)` on `var(--color-bg-subtle)` | Light **4.50:1** / Dark **6.42:1** | $\ge 4.5:1$ (본문 텍스트) |

---

## 3. 세부 변경 사항

### 1) `apps/web/src/features/nodes/NodeDetail.tsx`
- **배지 및 자원 리스트 (`:246-285`)**:
  - `resource-measured-badge`: 배경을 `var(--color-bg-subtle)`로 통일하고, `res.measured ? 'var(--color-status-online)' : 'var(--color-text-muted)'` (글자), `res.measured ? 'var(--color-status-online)' : 'var(--color-border-subtle)'` (테두리)로 결속.
  - `resource-reserved-val`: `res.reserved !== null ? 'var(--color-brand-primary)' : 'var(--color-text-muted)'`.
  - `resource-spare-val`: `res.spare !== null ? 'var(--color-status-online)' : 'var(--color-text-muted)'`.
- **4-Tier 관측 카드 (`:360-380`)**:
  - `node-detail-observed-usage-value`: `color: 'var(--color-brand-primary)'`.
  - `node-detail-observed-headroom-value`: `color: 'var(--color-status-online)'`.
- **최근 하트비트 스냅샷 타임라인 (`:435-445`)**:
  - `node-detail-timeline-status`: `node.status === 'online'` 분기 색상을 `#3fb950`에서 `var(--color-status-online)`로 교체.

### 2) `apps/web/tests/acc09-contrast-tokens.test.tsx`
- **`COLOR_LITERAL_MULTISET_BASELINE` 래칫 감소**:
  - `features/nodes/NodeDetail.tsx`의 인벤토리에서 `#2ea043`, `#3fb950`, `#58a6ff`, `rgba(110,118,129,0.2)`, `rgba(46,160,67,0.15)`를 완전히 제거하고 의도된 경고/에러 틴트 3건만 보존.
- **Test 9 확장**:
  - `onlineNode` 및 `sampleResourceUsage`를 렌더링하고, DOM에서 추출한 스타일 토큰을 기반으로 실측 대비율(5.05:1, 4.50:1, 4.70:1, 4.80:1 등)을 fail-closed로 단언.
- **Revert-Fail Probes (Probes 19~23 추가)**:
  - 과거 결함 리터럴 조합(`#3fb950` on subtle/surface/canvas, `#58a6ff` on subtle/canvas, `#3fb950` on green tint)의 4.5:1 미만 위반을 영구 고정.

---

## 4. 검증 결과 및 증거 (Evidence)

| 검증 항목 | 대상 / 명령 | 결과 |
| :--- | :--- | :--- |
| 대비 및 래칫 단위 시험 | `npm run test -- acc09-contrast-tokens.test.tsx` | **13 passed** (600ms, exit 0) |
| 노드 스위트 전체 시험 | `npm run test -- node` | **6 test files, 40 passed** (exit 0) |
| 11종 변이 사살 실측 | `python scratch/test_c193_mutations.py` | **11 / 11 killed (100%)** |
| TypeScript 컴파일 점검 | `cd apps/web && npx tsc -b` | **0 errors (exit 0)** |
| 프로덕션 번들 빌드 | `npm run build` (Vite production bundle) | **build 성공 (7.00s, exit 0)** |
| 정본 40개 계약 TS 점검 | `node apps/web/scripts/api-response-contracts.mjs --check` | **PASS (40 types match, exit 0)** |
| 라우트 커버리지 점검 | `pytest tests/test_route_coverage.py` | **41 passed (exit 0)** |
| 프런트엔드 무결성 점검 | `python tools/check_frontend_integrity.py` | **93 files scanned, 0 violations (exit 0)** |
| 계약 바인딩 점검 | `python tools/check_contract_bindings.py` | **55 fixtures, 20 bound types, exit 0** |
| 문서 일관성 검사 | `python tools/check_docs.py` | **PASS (1072 docs, exit 0)** |
| 문서 경로 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref 3e19b682` | **290 baseline, 0 new broken (exit 0)** |
| Git 공백/충돌 검사 | `git diff --check 3e19b682` | **Clean (exit 0)** |
| 봇 호출 태그 점검 | `git diff 3e19b682 \| Select-String -Pattern "@(codex\|claude\|gemini)"` | **0 occurrences (exit 0)** |

### 변이 사살 실측 요약 (11 / 11 Killed, 100%)
- M1 (revert timeline online color to #3fb950): **KILLED**
- M2 (revert measured badge background to rgba): **KILLED**
- M3 (revert measured badge text color to #3fb950): **KILLED**
- M4 (revert measured badge border to #2ea043): **KILLED**
- M5 (revert unmeasured badge background to rgba): **KILLED**
- M6 (revert resource reserved color to #58a6ff): **KILLED**
- M7 (revert resource spare color to #3fb950): **KILLED**
- M8 (revert observed usage color to #58a6ff): **KILLED**
- M9 (revert observed headroom color to #3fb950): **KILLED**
- M10 (background swapping: measured badge bg to var(--color-status-online)): **KILLED**
- M11 (unregistered literal injection: #abcdef): **KILLED**

---

## 5. 남은 영역 및 백로그

- `NodeDetail.tsx` 내 잔여 저대비 리터럴 결함 백로그: **0건 (완전 해소)**.
- 보존된 3건의 틴트는 의도된 상태 배경 알파 틴트(`rgba(210, 153, 34, 0.12)`, `rgba(210, 153, 34, 0.15)`, `rgba(248, 81, 73, 0.1)`)로서 Test 9에서 합성 대비율 적합성이 이미 엄격히 검증되어 관리 중입니다.

---

## 6. 다음 담당자 및 행동

- **다음 담당자**: Claude UI (UI/접근성/테스트 검토), Codex (디자인 토큰/무결성/불변식 검토)
- **이어서 할 행동**:
  1. Card 193 PR 생성 및 검토 요청 전달 (봇 호출 태그 0건 준수).
  2. 독립 검토 피드백 도착 시 최우선 조치.
