---
doc_id: "HIST-2026-10-01-CARD189-RESIDUAL-CONTRAST"
title: "Card 189: NodeList 및 NodeDetail 잔여 저대비 리터럴 토큰화 및 WCAG AA 적합성 달성"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude, Codex"
created: "2026-10-01T21:40:00+09:00"
updated: "2026-10-01T21:40:00+09:00"
source_of_truth: "Git"
base_commit: "ec75b4f0"
target_branch: "agent/gemini/c189-node-residual-contrast"
---

# Card 189: NodeList 및 NodeDetail 잔여 저대비 리터럴 토큰화 및 WCAG AA 적합성 달성

## 1. 개요 및 배경

PR #284 (Card 186) Claude UI r1 검토(i1) 및 코디네이터 지시에 따라, `NodeList.tsx` 및 `NodeDetail.tsx`에 잔존하던 하드코딩 색상 리터럴(텔레메트리 안내문, 예약가능 라벨, 관측 전용 콜아웃, 에러 알림 테두리 등)의 저대비 결함을 전수 해결하고 디자인 토큰으로 승격했습니다.

- **Base 브랜치/커밋**: `agent/gemini/c186-nodelist-badge-contrast` (head `ec75b4f0`, PR #284)
- **작업 브랜치**: `agent/gemini/c189-node-residual-contrast`
- **소유자**: Gemini (Frontend / UI / A11y). Reviewer: Claude (UI·접근성 축), Codex (계약·래칫 축).

---

## 2. Before vs After 실측 대비율 대조표

| 대상 요소 | 위치 | 기존 구현 (하드코딩 리터럴) | 신규 디자인 토큰 | 라이트 표면 (`#ffffff`) 실측 대비율 | 다크 표면 (`#111827`) 실측 대비율 | WCAG 2.2 AA 판정 | 비색상 의미 구별 수단 |
|---|---|---|---|---|---|---|---|
| **텔레메트리 lost 안내문** | `NodeList.tsx:228` | `#fca5a5` (1.90:1) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **6.47:1** (▲ 4.57) | **6.41:1** (▲ 0.65 on subtle) | **합격 (PASS)** | • 텍스트: `🔴 노드와의 통신이 두절되어...`<br>• 기호: `🔴`<br>• 시맨틱: `role="alert"` |
| **텔레메트리 unknown 안내문** | `NodeList.tsx:228` | `#fde68a` (1.25:1) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (▲ 5.84) | **7.03:1** (유지) | **합격 (PASS)** | • 텍스트: `⚠️ 서버에서 관측된 노드 상태...`<br>• 기호: `⚠️`<br>• 시맨틱: `role="status"` |
| **텔레메트리 active 안내문** | `NodeList.tsx:228` | `#7dd3fc` (1.67:1) | `--color-status-active`<br>(L: `#0369a1` / D: `#38bdf8`) | **5.93:1** (▲ 4.26) | **8.28:1** (유지) | **합격 (PASS)** | • 텍스트: `ℹ️ 계약 상태: active...`<br>• 기호: `ℹ️`<br>• 시맨틱: `role="status"` |
| **카드 테두리 (unknown)** | `NodeList.tsx:190` | `#f59e0b` (2.15:1) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (▲ 4.94) | **7.03:1** (유지) | **합격 (PASS, $\ge 3.0:1$)** | • 비색상 배지 텍스트 `UNKNOWN`<br>• 카드 내부 ⚠️ 기호 |
| **카드 테두리 (lost)** | `NodeList.tsx:190` | `#ef4444` (3.99:1) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **6.47:1** (▲ 2.48) | **6.41:1** (유지) | **합격 (PASS, $\ge 3.0:1$)** | • 비색상 배지 텍스트 `LOST`<br>• 카드 내부 🔴 기호 |
| **예약가능 라벨 (allocatable)** | `NodeList.tsx:420` | `#3fb950` (2.54:1) | `--color-status-online`<br>(L: `#1a7f37` / D: `#3fb950`) | **5.42:1** (▲ 2.88) | **6.85:1** (유지) | **합격 (PASS)** | • 텍스트: `예약가능: {N}C` |
| **관측 전용 콜아웃 테두리/텍스트** | `NodeDetail.tsx:105-106` | `#d29922` (2.52:1) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (▲ 4.57) | **7.03:1** (유지) | **합격 (PASS)** | • 텍스트: `⚠️ 관측 전용 노드...`<br>• 기호: `⚠️`<br>• 상세 설명 문구 |
| **자원 사용량 에러 알림 테두리/텍스트** | `NodeDetail.tsx:190-191` | `#f85149` (3.35:1) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **6.47:1** (▲ 3.12) | **6.41:1** (유지) | **합격 (PASS)** | • 텍스트: `자원 사용량 조회 실패:`<br>• 시맨틱: `role="alert"` |
| **예약가능 박스 테두리/라벨/값 (관측전용)** | `NodeDetail.tsx:378-391` | `#d29922` (2.52:1) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (▲ 4.57) | **7.03:1** (유지) | **합격 (PASS)** | • 텍스트: `예약 가능량 (Schedulable)`<br>• 값: `0C (차단)` |
| **타임라인 상태 라벨** | `NodeDetail.tsx:426` | `#38bdf8` (2.14:1)<br>`#d29922` (2.52:1)<br>`#f85149` (3.35:1) | `--color-status-active`<br>`--color-status-unknown`<br>`--color-status-lost` | **5.93:1** ~ **7.09:1** | **6.41:1** ~ **8.28:1** | **합격 (PASS)** | • 텍스트: `[HH:MM:SS] ACTIVE / UNKNOWN / LOST` |

---

## 3. 코드베이스 변경 내역

1. **`apps/web/src/features/nodes/NodeList.tsx`**:
   - `:190` 카드 테두리: `node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : 'var(--color-border-subtle)'`
   - `:228` 텔레메트리 안내문 `<p>`: `node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)'`
   - `:420` 예약가능 라벨: `node.allocatableCores !== undefined ? 'var(--color-status-online)' : 'var(--color-text-muted)'`
   - 신규 색상 리터럴 유입 0건, 저대비 하드코딩 리터럴 전수 제거.

2. **`apps/web/src/features/nodes/NodeDetail.tsx`**:
   - `:105-106` 관측 전용 콜아웃 테두리 및 텍스트를 `var(--color-status-unknown)`에 결속 (`data-testid="node-detail-observation-callout"`).
   - `:190-191` 자원 사용량 에러 알림 테두리 및 텍스트를 `var(--color-status-lost)`에 결속 (`data-testid="node-resource-usage-error"`).
   - `:378-391` 관측 전용 상태 시 예약가능 박스 테두리, 라벨, 값을 `var(--color-status-unknown)`에 결속 (`data-testid="node-detail-schedulable-box"`, `label`, `value`).
   - `:426` 타임라인 상태 텍스트를 `var(--color-status-active)`, `var(--color-status-unknown)`, `var(--color-status-lost)`에 결속 (`data-testid="node-detail-timeline-status"`).
   - `NodeDetail.tsx` 내 `#38bdf8` (1건 $ightarrow$ 0건), `#d29922` (6건 $ightarrow$ 0건), `#f85149` (3건 $ightarrow$ 0건) 전수 0건 제거 (총 10건 순수 감소).

3. **`apps/web/tests/acc09-contrast-tokens.test.tsx`**:
   - **`COLOR_LITERAL_MULTISET_BASELINE` 순수 감소 반영**:
     - `features/nodes/NodeDetail.tsx`: `"#38bdf8": 1`, `"#d29922": 6`, `"#f85149": 3` 항목 완전 제거.
     - 신규 등록 리터럴 0건 (래칫 강화).
   - **NodeDetail DOM 렌더링 검증 시험 추가 (Test 9)**:
     - `NodeDetail`을 렌더하여 관측 전용 콜아웃, 에러 알림, 예약가능 박스, 타임라인 상태의 `style.borderColor` 및 `style.color`가 해당 토큰에 결속되어 있는지 단언.
     - 렌더된 전경 및 배경 토큰 쌍의 실측 대비율이 라이트/다크 양쪽 모두 WCAG AA ($\ge 4.5:1$, 테두리 $\ge 3.0:1$)를 충족함을 동적 계산 단언.
   - **Revert-Fail Probes 5종 추가 (Probes 10~14)**:
     - Probe 10: 텔레메트리 lost `#fca5a5` (1.90:1) 복귀 시 실패 단언.
     - Probe 11: 텔레메트리 unknown `#fde68a` (1.25:1) 복귀 시 실패 단언.
     - Probe 12: 텔레메트리 active `#7dd3fc` (1.67:1) 복귀 시 실패 단언.
     - Probe 13: 예약가능 라벨 `#3fb950` (2.54:1) 복귀 시 실패 단언.
     - Probe 14: 카드 테두리 `#f59e0b` (2.15:1) 복귀 시 실패 단언.

---

## 4. 변이 불변식 검증 결과 (Mutation Testing)

`scratch/test_c189_mutations.py`를 통해 총 9종의 변이를 주입하여 테스트 스위트의 감지 능력을 실측함:

| 변이 ID | 변이 대상 파일 및 내용 | 기대 실패 시험 | 실측 결과 |
|---|---|---|---|
| **M1** | `NodeList.tsx` lost 텔레메트리 안내문 `#fca5a5`로 복귀 | Test 8 (NodeList DOM Contrast) | **KILLED** |
| **M2** | `NodeList.tsx` unknown 텔레메트리 안내문 `#fde68a`로 복귀 | Test 8 (NodeList DOM Contrast) | **KILLED** |
| **M3** | `NodeList.tsx` active 텔레메트리 안내문 `#7dd3fc`로 복귀 | Test 8 (NodeList DOM Contrast) | **KILLED** |
| **M4** | `NodeList.tsx` unknown 카드 테두리 `#f59e0b`로 복귀 | Test 8 (NodeList DOM Contrast) | **KILLED** |
| **M5** | `NodeList.tsx` 예약가능 allocatable 색상 `#3fb950`로 복귀 | Test 8 (NodeList DOM Contrast) | **KILLED** |
| **M6** | `NodeDetail.tsx` 관측 전용 콜아웃 테두리 `#d29922`로 복귀 | Test 9 (NodeDetail DOM Contrast) | **KILLED** |
| **M7** | `NodeDetail.tsx` 에러 알림 테두리 `#f85149`로 복귀 | Test 9 (NodeDetail DOM Contrast) | **KILLED** |
| **M8** | `NodeDetail.tsx` 타임라인 active 상태 `#38bdf8`로 복귀 | Test 9 (NodeDetail DOM Contrast) | **KILLED** |
| **M9** | `NodeList.tsx`에 미등록 신규 리터럴 `#abcdef` 주입 | Test 12 (Multiset Inventory Ratchet) | **KILLED** |

**변이 사살율: 9 / 9 (100% KILLED)**

---

## 5. 검증 실측 증거 (Evidence)

| 검증 항목 | 실행 명령 | 실측 결과 |
|---|---|---|
| 대비 및 래칫 단위 시험 | `npm run test -- acc09-contrast-tokens.test.tsx` | **12 passed (12)** (179ms, exit 0) |
| 노드 관련 전체 단위 시험 | `npm run test -- acc09-contrast-tokens.test.tsx node-status-lost-unknown-guard.test.tsx node-resource-usage-contract.test.tsx` | **28 passed (28)** (exit 0) |
| 변이 불변식 실측 | `python scratch/test_c189_mutations.py` | **9 / 9 killed (100%)** (exit 0) |
| TypeScript 컴파일 | `npx tsc -b` (apps/web) | **0 errors** (exit 0) |
| 프로덕션 번들 빌드 | `npm run build` (apps/web) | **Vite build 성공** (8.68s, exit 0) |
| 라우트 커버리지 검증 | `pytest tests/test_route_coverage.py` | **40 passed** (exit 0) |
| 프런트엔드 9대 무결성 | `python tools/check_frontend_integrity.py` | **92개 파일 스캔, 0 violations** (exit 0) |
| 계약 바인딩 점검 | `python tools/check_contract_bindings.py` | **55 fixtures + 20 anchor types 통과** (exit 0) |
| 문서 일관성 검사 | `python tools/check_docs.py` | **PASS: 1068개 문서 정합** (exit 0) |
| Git diff 공백/충돌 | `git diff --check` | **클린 (0 errors)** (exit 0) |
| 봇 호출 태그 검사 | `git diff | Select-String "@(codex|claude|gemini)"` | **0건 검출** (규정 준수) |

---

## 6. 인계 및 검토 요청

- **Base 커밋**: `ec75b4f0` (PR #284)
- **작업 브랜치**: `agent/gemini/c189-node-residual-contrast`
- **검토 요청**:
  - Claude: UI/A11y 축 — `NodeList` 및 `NodeDetail`의 잔여 텔레메트리/콜아웃/에러 테두리 대비율, 비색상 의미 구별(아이콘/텍스트/ARIA) 및 단위 시험 12 passed 검토 요청.
  - Codex: 무결성/래칫 축 — `COLOR_LITERAL_MULTISET_BASELINE` 10건 순수 감소, 9종 변이 100% 사살 불변식 검토 요청.
