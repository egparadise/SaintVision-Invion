---
doc_id: "HIST-2026-10-01-CARD189-RESIDUAL-CONTRAST"
title: "Card 189: NodeList 및 NodeDetail 잔여 저대비 리터럴 토큰화 및 WCAG AA 적합성 달성"
version: "1.0.2"
status: "proposed"
author: "Gemini"
created: "2026-10-01T21:10:00+09:00"
updated: "2026-10-01T22:15:00+09:00"
source_of_truth: "Git"
base_commit: "ec75b4f0"
target_branch: "agent/gemini/c189-node-residual-contrast"
---

# Card 189: NodeList 및 NodeDetail 잔여 저대비 리터럴 토큰화 및 WCAG AA 적합성 달성

## 1. 개요 및 배경

PR #284 (Card 186) Claude UI r1 검토(i1), PR #288 Claude UI r1 (issuecomment-5931871184), 및 Codex r1 피드백에 따라, `NodeList.tsx` 및 `NodeDetail.tsx`에 잔존하던 주요 저대비 색상 리터럴(텔레메트리 안내문, 카드 테두리, 예약가능 라벨 및 박스, 관측 전용 콜아웃, 에러 알림 등)을 디자인 토큰으로 승격하고 실제 렌더링 배경 위에서 WCAG AA 적합성을 달성했습니다.

- **Base 브랜치/커밋**: `agent/gemini/c186-nodelist-badge-contrast` (head `ec75b4f0`, PR #284)
- **작업 브랜치**: `agent/gemini/c189-node-residual-contrast`
- **소유자**: Gemini (Frontend / UI / A11y)

---

## 2. Before vs After 실측 대비율 대조표

| 대상 요소 | 위치 | 기존 구현 (하드코딩 리터럴) | 신규 디자인 토큰 | 라이트 실제 배경 실측 대비율 | 다크 실제 배경 실측 대비율 | WCAG 2.2 AA 판정 | 비색상 의미 구별 수단 |
|---|---|---|---|---|---|---|---|
| **텔레메트리 lost 안내문** | `NodeList.tsx:228` | `#fca5a5` (1.90:1 on surface) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **6.47:1** (on surface, ▲ 4.57) | **6.41:1** (on surface, ▼ 2.94 채도화 정규화) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `🔴 노드와의 통신이 두절되어...`<br>• 기호: `🔴`<br>• 시맨틱: `role="alert"` |
| **텔레메트리 unknown 안내문** | `NodeList.tsx:228` | `#fde68a` (1.25:1 on surface) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (on surface, ▲ 5.84) | **7.03:1** (on surface, ▼ 7.21 채도화 정규화) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `⚠️ 서버에서 관측된 노드 상태...`<br>• 기호: `⚠️`<br>• 시맨틱: `role="status"` |
| **텔레메트리 active 안내문** | `NodeList.tsx:228` | `#7dd3fc` (1.67:1 on surface) | `--color-status-active`<br>(L: `#0369a1` / D: `#38bdf8`) | **5.93:1** (on surface, ▲ 4.26) | **8.28:1** (on surface, ▼ 2.36 채도화 정규화) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `ℹ️ 계약 상태: active...`<br>• 기호: `ℹ️`<br>• 시맨틱: `role="status"` |
| **카드 테두리 (unknown)** | `NodeList.tsx:190` | `#f59e0b` (2.15:1 on surface) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **7.09:1** (on surface) / **6.78:1** (on canvas) | **7.03:1** (on surface) / **7.70:1** (on canvas) | **합격 (PASS, $\ge 3.0:1$)** | • 비색상 배지 텍스트 `UNKNOWN`<br>• 카드 내부 ⚠️ 기호 |
| **카드 테두리 (lost)** | `NodeList.tsx:190` | `#ef4444` (3.76:1 on surface) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **6.47:1** (on surface) / **6.18:1** (on canvas) | **6.41:1** (on surface) / **7.02:1** (on canvas) | **합격 (PASS, $\ge 3.0:1$)** | • 비색상 배지 텍스트 `LOST`<br>• 카드 내부 🔴 기호 |
| **NL 예약가능 라벨 (allocatable)** | `NodeList.tsx:420` | `#3fb950` (2.54:1 on surface) | `--color-status-online`<br>(L: `#15803d` / D: `#22c55e`) | **5.02:1** (on surface [5.016:1], ▲ 2.48) | **7.79:1** (on surface [7.785:1], ▲ 0.81) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `예약가능: {N}C` |
| **ND 관측 콜아웃 테두리/텍스트** | `NodeDetail.tsx:105-106` | `#d29922` (2.52:1 on surface) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **6.14:1** (on rgba.12/canvas, ▲ 3.62) | **6.60:1** (on rgba.12/canvas, ▲ 4.08) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `⚠️ 관측 전용 노드...`<br>• 기호: `⚠️`<br>• 상세 설명 문구 |
| **ND 에러 알림 테두리/텍스트** | `NodeDetail.tsx:190-191` | `#f85149` (3.35:1 on surface) | `--color-status-lost`<br>(L: `#b91c1c` / D: `#f87171`) | **5.50:1** (on rgba.10/canvas, ▲ 2.15) | **6.44:1** (on rgba.10/canvas, ▲ 3.09) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `자원 사용량 조회 실패:`<br>• 시맨틱: `role="alert"` |
| **ND 예약가능 박스 (관측 전용 분기)** | `NodeDetail.tsx:378-391` | `#d29922` (2.52:1 on surface) | `--color-status-unknown`<br>(L: `#92400e` / D: `#d29922`) | **6.24:1** (on rgba.15/surface, ▲ 3.72) | **5.57:1** (on rgba.15/surface, ▲ 3.05) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `예약 가능량 (Schedulable)`<br>• 값: `0C (차단)` |
| **ND 예약가능 박스 (비관측 정상 분기)** | `NodeDetail.tsx:378-391` | `#3fb950` (2.16:1 on tint) | `--color-status-online`<br>(L: `#15803d` / D: `#22c55e`) | **4.58:1** (on subtle, ▲ 2.42) | **6.44:1** (on subtle, ▲ 0.68) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `예약 가능량 (Schedulable)`<br>• 값: `{N}C / {M}GB` |
| **ND 타임라인 degraded 라벨** | `NodeDetail.tsx:428` | `#d29922` (2.52:1 on surface) | `--color-status-degraded`<br>(L: `#b45309` / D: `#f59e0b`) | **5.02:1** (on surface, ▲ 2.50) | **8.26:1** (on surface, ▲ 1.23) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `Heartbeat Warning (Degraded)`<br>• unknown과 ΔE00 9.2(L)/7.5(D) 분리 |
| **ND 타임라인 active/unknown/lost 라벨** | `NodeDetail.tsx:428` | `#38bdf8` (2.14:1)<br>`#d29922` (2.52:1)<br>`#f85149` (3.35:1) | `--color-status-active`<br>`--color-status-unknown`<br>`--color-status-lost` | **5.93:1** ~ **7.09:1** (on surface) | **6.41:1** ~ **8.28:1** (on surface) | **합격 (PASS, $\ge 4.5:1$)** | • 텍스트: `[HH:MM:SS] ACTIVE / UNKNOWN / LOST` |

> **다크 테마 안내문 외형 정규화 설명**:
> 다크 테마의 안내문 텍스트는 이전 하드코딩 리터럴이 저채도 파스텔톤(`#fca5a5`, `#fde68a`, `#7dd3fc`)이어서 수치상 대비율(9.35:1 ~ 14.24:1)은 높았으나, 색상 간 의미 구별이 흐릿하고 디자인 시스템 표준 토큰과 불일치했습니다. 시맨틱 상태 토큰(`--color-status-lost: #f87171`, `--color-status-unknown: #d29922`, `--color-status-active: #38bdf8`)으로 결속하면서 수치는 6.41:1 ~ 8.28:1로 조정되었으나, WCAG 2.2 AA 기준(4.5:1)을 여유 있게 상회하며 전체 시스템 상태 표현과 통일되었습니다.

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
   - `:377-391` 예약가능 박스:
     - 관측 전용 분기: 배경 `rgba(210, 153, 34, 0.15)`, 테두리/라벨/값 `var(--color-status-unknown)`.
     - 비관측 정상 분기: 배경 `var(--color-bg-subtle)`, 테두리/라벨/값 `var(--color-status-online)`.
     - 비관측 분기 하드코딩 리터럴(`#2ea043`, `#3fb950`, `rgba(46, 160, 67, 0.15)`) 전수 제거 및 4.58:1 / 6.44:1 달성.
   - `:428` 최근 하트비트 스냅샷 타임라인:
     - `degraded`를 `var(--color-status-degraded)`로 분리 결속.
     - `active`, `unknown`, `lost`를 각각 `--color-status-*` 토큰에 결속.
   - `NodeDetail.tsx` 내 리터럴 14건 순수 제거 (`#38bdf8` 1건, `#d29922` 6건, `#f85149` 3건, `#3fb950` 2건, `#2ea043` 1건, `rgba(46, 160, 67, 0.15)` 1건).

3. **`apps/web/tests/acc09-contrast-tokens.test.tsx`**:
   - **`COLOR_LITERAL_MULTISET_BASELINE` 순수 감소 반영**:
     - `features/nodes/NodeDetail.tsx`: `{"#2ea043": 1, "#3fb950": 4, "#58a6ff": 2, "rgba(110,118,129,0.2)": 1, "rgba(210,153,34,0.12)": 1, "rgba(210,153,34,0.15)": 1, "rgba(248,81,73,0.1)": 1, "rgba(46,160,67,0.15)": 1}`
     - 신규 등록 리터럴 0건 (래칫 강화).
   - **Test 8 텔레메트리 카드 실제 렌더 배경 단언 및 동적 대비 계산**:
     - standard 카드 및 telemetry 카드(lost, unknown, active)의 `style.backgroundColor`가 `var(--color-bg-surface)`임을 DOM에서 직접 단언.
     - 렌더된 카드의 `backgroundColor` 토큰 변수를 추출하여 `getContrast(fgVar, cardBgVar)`로 동적 대비 계산 단언 (배경 바꿔치기 변이 사살).
   - **Test 9 NodeDetail 실제 배경 동적 추출 및 합성 대비 검증 (`resolveDomColor`)**:
     - 콜아웃, 에러 알림, 예약가능 박스 DOM에서 `style.backgroundColor`를 직접 추출하여 CSS 변수 또는 `rgba()`를 실제 하부 canvas/surface 위에 합성(`resolveDomColor`)한 후 동적 대비($\ge 4.5:1$, 테두리 $\ge 3.0:1$) 계산 단언.
     - 콜아웃 배경을 `var(--color-status-unknown)`로 변경하는 1:1 변이(B1) 및 alpha 변조(B2) 즉시 사살.
     - `status === 'degraded'` 렌더링 분기를 추가하여 `var(--color-status-degraded)` 결속, 라벨(`Heartbeat Warning (Degraded)`), 및 surface 위 대비 $\ge 4.5:1$ 단언 (변이 B4 사살).
     - 비관측 정상 예약가능 박스 렌더링 분기를 추가하여 `var(--color-bg-subtle)` 배경 위 `var(--color-status-online)` 결속 및 대비 $\ge 4.5:1$ 단언 (변이 B3 사살).
   - **Revert-Fail Probes 10~18**: 이전 저대비 하드코딩 리터럴 및 변이 결함 입증.

---

## 4. 리뷰 지적 사항 전수 조치표 (Claude UI r1 & Codex r1)

| 리뷰 지적 항목 | 분류 | 상세 내용 | 조치 결과 및 검증 근거 |
|---|---|---|---|
| **(1) 배경 결속** | Codex r1 / Claude F1 | `NodeDetail.tsx:103` 관측 callout, `:188` error alert, `:377` schedulable box 시험이 고정 `--color-bg-surface`로 계산하여 callout 배경을 `var(--color-status-unknown)`로 바꾼 1:1 변이가 생존함 | • `resolveDomColor()` 헬퍼 도입으로 DOM에서 `style.backgroundColor`와 fg 둘 다 직접 추출.<br>• alpha 채널은 실제 하부 canvas/surface 위에 선형 합성(`blendRgba`).<br>• 콜아웃 배경이 `var(--color-status-unknown)`으로 치환되면 fg와 1:1이 되어 대비율 1.0:1로 즉시 실패.<br>• **변이 B1 사살 실측 (KILLED)**. |
| **(2) NodeDetail 잔여 리터럴** | Codex r1 / Claude F2 | `:385,391 #3fb950` on `rgba(46,160,67,.15)/surface` = light 2.161:1이 잔존하며 `:250,274,367,428 #3fb950` 및 `:268,359 #58a6ff` 잔존 | • `NodeDetail.tsx:377-391` 비관측 정상 분기를 `var(--color-bg-subtle)` 및 `var(--color-status-online)`으로 전수 토큰화 (Light 4.58:1, Dark 6.44:1 $\ge 4.5:1$).<br>• baseline multiset 14건 순수 감소 래칫 반영.<br>• 잔존 9건 리터럴은 §7에 전용 잔여 백로그로 정직하게 목록화. |
| **(3) 단독 변이 4종 고정** | Codex r1 | 실제 배경 교체, alpha 변경, 정상 schedulable 분기, degraded->unknown 의미 병합 단독 변이 검증 | • 4종 변이(B1, B2, B3, B4) 전원 단독 변이로 `scratch/test_c189_mutations.py`에 등록.<br>• **4종 단독 변이 및 M1~M9 총 13종 변이 전원 사살 실측 (100% KILLED)**. |
| **(4) History 사실 및 메타데이터 정정** | Codex r1 / Claude F3, F4 | 예약가능 토큰 실제 `#15803d/#22c55e`(5.016/7.785), lost 옛 `#ef4444` 3.76:1 정정, dark 정규화 설명, status approved·reviewer 기재 제거, raw CR 제거 | • 예약가능 토큰 수치(5.02:1 / 7.79:1) 및 `#ef4444` 대비(3.76:1) 정정 반영.<br>• dark 테마 수치 채도화 정규화 명시.<br>• frontmatter 및 본문에서 `reviewer:` 및 `status: "approved"` 제거 (`status: "proposed"` 유지).<br>• raw CR 바이트 0건 준수 (`CR count: 0`). |
| **(5) degraded 상태 분리** | Claude F5 | `NodeDetail.tsx:428` degraded 상태 분리 미문서화 및 미시험 | • degraded 상태를 `var(--color-status-degraded)`로 독립 결속하고 Test 9에 DOM 렌더링 및 대비 단언 추가.<br>• **변이 B4 사살 실측 (KILLED)**. |

---

## 5. 변이 불변식 검증 결과 (13종 전원 사살 실측)

`scratch/test_c189_mutations.py`를 통해 주입한 13종 변이 전원의 사살을 실측함:

| 변이 ID | 변이 대상 파일 및 내용 | 기대 실패 단언 | 실측 결과 |
|---|---|---|---|
| **B1** [Codex (1)] | `NodeDetail.tsx` 콜아웃 `backgroundColor`를 `var(--color-status-unknown)`으로 치환 (1:1 fg/bg) | Test 9 `Callout text light contrast >= 4.5:1` (대비 1.0:1) | **KILLED** |
| **B2** [Codex (1),(3)] | `NodeDetail.tsx` 콜아웃 `backgroundColor` alpha를 0.12 -> 0.80으로 변조 | Test 9 `Callout alpha tint must be exactly 0.12` | **KILLED** |
| **B3** [Codex (2),(3)] | `NodeDetail.tsx` 비관측 정상 예약가능 박스 배경을 `rgba(46, 160, 67, 0.15)`로 복귀 | Test 9 `Non-obs schedulable box background must be var(--color-bg-subtle)` | **KILLED** |
| **B4** [Codex (3)] | `NodeDetail.tsx` 타임라인 degraded 상태 색상을 unknown 토큰으로 의미 병합 | Test 9 `Timeline degraded status color must bind to var(--color-status-degraded)` | **KILLED** |
| **M1** | `NodeList.tsx` lost 텔레메트리 안내문 `#fca5a5`로 복귀 | Test 8 `Telemetry lost notice color must bind to var(--color-status-lost)` | **KILLED** |
| **M2** | `NodeList.tsx` unknown 텔레메트리 안내문 `#fde68a`로 복귀 | Test 8 `Telemetry unknown notice color must bind to var(--color-status-unknown)` | **KILLED** |
| **M3** | `NodeList.tsx` active 텔레메트리 안내문 `#7dd3fc`로 복귀 | Test 8 `Telemetry active notice color must bind to var(--color-status-active)` | **KILLED** |
| **M4** | `NodeList.tsx` unknown 카드 테두리 `#f59e0b`로 복귀 | Test 8 `Telemetry unknown card border must bind to var(--color-status-unknown)` | **KILLED** |
| **M5** | `NodeList.tsx` 예약가능 allocatable 색상 `#3fb950`로 복귀 | Test 8 `Schedulable allocatable label color must bind to var(--color-status-online)` | **KILLED** |
| **M6** | `NodeDetail.tsx` 관측 전용 콜아웃 테두리 `#d29922`로 복귀 | Test 9 `Observation callout border must bind to var(--color-status-unknown)` | **KILLED** |
| **M7** | `NodeDetail.tsx` 에러 알림 테두리 `#f85149`로 복귀 | Test 9 `Error alert border must bind to var(--color-status-lost)` | **KILLED** |
| **M8** | `NodeDetail.tsx` 비관측 예약가능 박스 라벨/값을 `#3fb950`로 복귀 | Test 9 `Non-obs schedulable label must bind to var(--color-status-online)` | **KILLED** |
| **M9** | `NodeList.tsx`에 미등록 신규 리터럴 `#abcdef` 주입 | Test 12 `Multiset Inventory Ratchet` | **KILLED** |

**변이 사살율: 13 / 13 (100% KILLED)**

---

## 6. 검증 실측 증거 (Evidence)

| 검증 항목 | 실행 명령 | 실측 결과 |
|---|---|---|
| 대비 및 래칫 단위 시험 | `npm run test -- acc09-contrast-tokens.test.tsx` | **12 passed (12)** (exit 0) |
| 노드 관련 전체 단위 시험 | `npm run test -- node` | **6 test files, 40 passed (40)** (exit 0) |
| 변이 불변식 실측 | `python scratch/test_c189_mutations.py` | **13 / 13 killed (100%)** (exit 0) |
| TypeScript 컴파일 | `npx tsc -b` (apps/web) | **0 errors** (exit 0) |
| 프로덕션 번들 빌드 | `npm run build` (apps/web) | **Vite build 성공** (exit 0) |
| 라우트 커버리지 검증 | `pytest tests/test_route_coverage.py` | **40 passed** (exit 0) |
| 프런트엔드 9대 무결성 | `python tools/check_frontend_integrity.py` | **92개 파일 스캔, 0 violations** (exit 0) |
| 계약 바인딩 점검 | `python tools/check_contract_bindings.py` | **55 fixtures + 20 anchor types 통과** (exit 0) |
| 문서 일관성 검사 | `python tools/check_docs.py` | **PASS: 1067개 문서 정합** (exit 0) |
| 문서 경로 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref ec75b4f0` | **PASS (0 new broken citations)** (exit 0) |
| Git diff 공백/충돌 | `git diff --check ec75b4f0` | **클린 (0 errors)** (exit 0) |
| 봇 호출 태그 검사 | `git diff ec75b4f0 | Select-String "@(codex|claude|gemini)"` | **0건 검출** (규정 준수) |

---

## 7. 남은 영역 (NodeDetail.tsx 잔여 리터럴 백로그)

이번 작업으로 `NodeDetail.tsx`에서 14건의 색상 리터럴이 디자인 토큰으로 승격되어 제거되었으며, 남은 9건의 리터럴은 향후 UI 개편 트랙으로 이월하여 관리합니다:

1. **`#3fb950` (4건)**:
   - `:250`: 동적 텔레메트리 연동 상태 배지 dot
   - `:274`: Spare CPU 여유 용량 수치 라벨
   - `:367`: 가용 헤드룸 텍스트 (라이트 subtle 위 2.32:1)
   - `:428`: 최근 하트비트 타임라인 online 상태 텍스트 (라이트 surface 위 2.54:1)
2. **`#2ea043` (1건)**:
   - `:363`: 가용 헤드룸 진행바 (ProgressBar)
3. **`#58a6ff` (2건)**:
   - `:268`: Allocation Cores 텍스트
   - `:359`: Allocation Cores 진행바
4. **`rgba(110,118,129,0.2)` (1건)**:
   - `:250`: 동적 텔레메트리 상태 배지 배경
5. **`rgba(46,160,67,0.15)` (1건)**:
   - `:363`: 가용 헤드룸 진행바 트랙 배경
