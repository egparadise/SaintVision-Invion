# 2026-10-01 23:55:00 KST — Card 193 r1: NodeDetail 실제 렌더 배경 DOM 결속 및 수치 사실성 정정 (Gemini)

- **문서 ID**: `HIST-GEMINI-CARD193-NODEDETAIL-CONTRAST-R1`
- **작업 branch**: `agent/gemini/c193-nodedetail-residual`
- **Base commit**: `9673df46556fcb686cbaae7f1792069cc7f52da5` (PR #290 HEAD)
- **KST 시각**: 2026-10-01 23:55:00 KST
- **작업자**: Gemini (Frontend / UI / 접근성)
- **독립 검토자 요청**: Claude UI (UI/접근성 축), Codex (계약/디자인 토큰/불변식 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. 개요 및 r1 검토 피드백 조치 요약

PR #290 (`9673df46`)에 대한 Claude UI (`issuecomment-5933168572`) 및 Codex (23:10 독립 검토)의 수정 요청을 전수 반영하였습니다.

1. **T1 / F1 [Major] 실제 렌더링된 상위 컨테이너 배경 DOM 결속**:
   - `NodeDetail.tsx`에 `data-testid="node-detail-lease-panel"`, `data-testid="node-detail-observed-usage-box"`, `data-testid="node-detail-observed-headroom-box"`를 명시적으로 부여.
   - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Test 6에서 고정 토큰(`lightTokens['--color-bg-subtle']` / `lightTokens['--color-bg-surface']`)을 제거하고, DOM에서 상위 컨테이너의 `style.backgroundColor`를 직접 추출하여 토큰을 단언한 뒤 해당 토큰으로 대비율을 동적 계산하도록 개정.
   - 상위 컨테이너 배경 교체 변이 Z1, Z2를 포함한 5종 변이 전원 사살 실측 (5/5 = 100% killed).
2. **T2 / F2 [Medium/Minor] History 수치 및 배경 사실성 정정**:
   - `NodeDetail_잔여대비_Gemini.md` §2 표에서 Reserved와 Spare의 실제 렌더 배경을 `canvas`가 아닌 **subtle**(`var(--color-bg-subtle)`, `:229`)로 정정.
   - 수학적으로 검증된 정밀 대비율 수치(online on surface: 5.02:1 / 7.79:1, online on subtle: 4.58:1 / 6.44:1, brand on subtle: 4.72:1 / 5.77:1, muted on subtle: 5.25:1 / 5.78:1, border-subtle on subtle: 3.18:1 / 3.08:1)로 전면 일치.
   - 측정 배지 이전 배경을 `rgba(46,160,67,0.15)` on subtle tint(`#d4e8de` / `#213b39`)로 정정 (이전 텍스트 1.98:1 / 4.73:1, 이전 테두리 2.63:1 / 3.56:1).
   - 다크 모드 수치가 이전/이후 동일하게 표기되었던 오류 정정 (타임라인 6.98:1 -> 7.79:1, Reserved 5.81:1 -> 5.77:1).
   - §3-2의 "실측 대비율을 단언" 서술을 ">= 4.5:1 및 >= 3.0:1을 fail-closed로 단언"으로 정직하게 정정.
   - Test Probe 19, 21, 22, 23의 주석 수치(2.32:1, 2.31:1, 2.41:1, 1.98:1) 및 Probe 23 합성 베이스(`--color-bg-subtle`) 정정.

---

## 2. 변이 사살 실측 (Mutations Z1 ~ Z5, 100% Killed)

Claude UI 및 Codex가 제시한 5종 단독 변이를 `NodeDetail.tsx`에 순차 적용하여 사살 여부를 실측하였습니다 (`scratch/test_c193_r1_mutations.py`).

| 변이 | 변이 내용 | 결과 | 사살한 단언 |
|---|---|---|---|
| **H0** | 원본 (Clean HEAD) | **13 passed** | 정상 기준선 |
| **Z1** | 관측 여유량 박스 bg -> `var(--color-status-online)` (글자와 1:1) | **KILLED** (exit 1) | `expect(obsHeadroomBox.style.backgroundColor).toBe('var(--color-bg-subtle)')` 및 `Observed headroom light contrast >= 4.5:1` |
| **Z2** | resource 카드 bg -> `var(--color-status-online)` (Spare 글자와 1:1) | **KILLED** (exit 1) | `expect(resCardCpu.style.backgroundColor).toBe('var(--color-bg-subtle)')` 및 `Spare value light contrast >= 4.5:1` |
| **Z3** | Spare 주석 decoy -> `'#3fb950' /* var(--color-status-online) */` | **KILLED** (exit 1) | `Spare value must bind to var(--color-status-online)` & multiset inventory ratchet |
| **Z4** | 타임라인 online 토큰 되돌림 -> `'#3fb950'` | **KILLED** (exit 1) | `Timeline online status must bind to var(--color-status-online)` & multiset inventory ratchet |
| **Z5** | 측정 배지 bg -> `var(--color-status-online)` | **KILLED** (exit 1) | `Measured badge background must bind to var(--color-bg-subtle)` |

---

## 3. 종합 검증 증거 (Full Verification Gates)

| 검증 도구 | 실행 명령 | 결과 | 비고 |
|---|---|---|---|
| Vitest 접근성 스위트 | `npx vitest run tests/acc09-contrast-tokens.test.tsx --maxWorkers=1` | **13 passed (13)** (exit 0) | 상위 컨테이너 DOM 결속 및 동적 계산 검증 |
| 변이 테스트 하네스 | `python scratch/test_c193_r1_mutations.py` | **5 / 5 killed (100%)** | Z1~Z5 전원 즉시 사살 |
| TypeScript 컴파일 | `cd apps/web && npx tsc -b` | **0 errors (exit 0)** | Strict 타입 점검 통과 |
| Vite 프로덕션 빌드 | `cd apps/web && npm run build` | **built in 6.54s (exit 0)** | 프로덕션 번들 정상 생성 |
| 계약 타입 일치성 | `cd apps/web && npm run contracts:check` | **PASS (40 types, exit 0)** | 40개 API 응답 스키마 일치 |
| 라우트 커버리지 | `pytest tests/test_route_coverage.py` | **41 passed (exit 0)** | 파이썬 라우트 및 불변식 통과 |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | **93 files scanned, 0 violations (exit 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 점검 | `python tools/check_contract_bindings.py` | **55 fixtures, 20 bound types (exit 0)** | 게이트 통과 |
| 문서 일관성 점검 | `python tools/check_docs.py` | **PASS (1072 docs, exit 0)** | 문서 일관성 검사 통과 |
| 문서 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref 3e19b682` | **290 baseline, 0 new broken (exit 0)** | 인용 래칫 유지 |
| Git 공백/충돌 검사 | `git diff --check` | **Clean (exit 0)** | CR 0 바이트, 충돌 마커 0 |

---

## 4. 인계 및 다음 단계

- **상태**: PR #290에 전진 커밋(force-push 절대 금지)으로 반영 후 재검토 요청.
- **다음 담당자**: Claude UI (UI/접근성 재검토), Codex (계약/불변식 재검토).
