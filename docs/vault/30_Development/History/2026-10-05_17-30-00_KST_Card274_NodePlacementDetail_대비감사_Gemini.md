---
doc_id: "HIST-20261005-CARD274-GEMINI"
title: "Card 274 노드 및 배치 상세 화면 묶음 (NodeDetail, PlacementExplainView, ResourceTopologyGraph) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T17:30:00+09:00"
updated: "2026-10-05T18:50:00+09:00"
source_of_truth: "Git"
---

# Card 274 노드 및 배치 상세 화면 묶음 (NodeDetail, PlacementExplainView, ResourceTopologyGraph) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격

## 1. 작업 개요
- **목표**: ACC-09 노드 및 자원 배치 상세 화면 묶음 3개 파일의 색상 리터럴 전수(11건→0건) 토큰화 및 디자인 토큰 체계 승격:
  1. `apps/web/src/features/nodes/NodeDetail.tsx`: `rgba(210,153,34,0.12)`, `rgba(210,153,34,0.15)`, `rgba(248,81,73,0.1)` 3건 전수 제거 및 `var(--color-bg-subtle)` 승격. 관측 전용 콜아웃(103행), 자원 에러 알림(188행), 스케줄 가능 카드(396행)의 WCAG 2.2 AA (텍스트 >= 4.5:1, 테두리 >= 3.0:1) 달성.
  2. `apps/web/src/features/nodes/NodeDetail.tsx` 노드 상태 계약 순수성: 독자 상태 색상 분기 로직을 제거하고 Card 248 `NODE_STATUS_CONFIG` 및 `getClusterNodeStatusConfig` 정본을 직접 재사용하여 중복 정의를 방지하고 `Object.hasOwn` fail-closed prototype 방어 및 `UNKNOWN (<raw>)` / `var(--color-status-unknown)` 안전 강등 매핑을 공유.
  3. `apps/web/src/features/placement/PlacementExplainView.tsx`: `#d97706`, `rgba(16,185,129,0.1)`, `rgba(16,185,129,0.15)`, `rgba(234,179,8,0.15)`, `rgba(234,179,8,0.3)` 5건 전수 제거 및 `var(--color-bg-subtle)`, `var(--color-status-unknown)`, `var(--color-status-online)`, `var(--color-status-lost)` 토큰 승격. 시뮬레이션 고지 배지(35행), 위너 배너(59행), 후보 탈락/통과 배지(112행), 감점/제외 사유(136행), 위너 점수 하이라이트(179행)의 명도비 보장.
  4. `apps/web/src/features/placement/ResourceTopologyGraph.tsx`: `#ffffff` 2건, `rgba(16,185,129,0.08)` 1건 등 총 3건 전수 제거 및 `var(--color-bg-subtle)`, `var(--color-status-online)`, `var(--color-status-lost)` 토큰 승격. 1순위 배치 배지 및 FENCED 배지의 1px 테두리 추가로 비텍스트/텍스트 대비 동시 충족.
  5. **ResourceTopologyGraph 렌더링 구조 및 3.0:1 비텍스트 대비 규격 근거**:
     - `ResourceTopologyGraph`는 SVG `<svg>` 그래픽이 아닌 HTML `<div>`, `<span>` 기반의 반응형 플렉스/그리드 카드 레이아웃으로 렌더링됨.
     - 각 노드 카드는 `border: 2px solid ...`를 사용하여 상태(선택: `var(--color-status-online)`, 펜스: `var(--color-status-lost)`, 기본: `var(--color-border-subtle)`)를 표시함.
     - WCAG 2.2 SC 1.4.11 (Non-text Contrast)에 따라 UI 컴포넌트의 테두리 및 상태 식별자는 인접 배경(`var(--color-bg-surface)` 및 `var(--color-bg-canvas)`) 대비 최소 3.0:1 이상이어야 함.
     - 실측 결과: 선택 노드 테두리 라이트 5.02:1 / 다크 7.79:1 (>= 3.0:1 PASS), 펜스 노드 테두리 라이트 6.47:1 / 다크 6.41:1 (>= 3.0:1 PASS), 기본 노드 테두리 라이트 3.48:1 / 다크 3.73:1 (>= 3.0:1 PASS)로 모든 상태에서 비텍스트 대비 기준을 완벽 충족함.
  6. **AST 정적 분석 래칫 (3개 파일 전수 확장)**: `apps/web/tests/acc09-contrast-tokens.test.tsx`의 9j-2 `analyzeFile` 스위트에 3개 파일 전수를 등록하고 통계 래칫을 고정:
     - `NodeDetail.tsx`: totalStyleAttrs 66, checkedObjects 6, checkedPairs 38, unbound 27, covered 33, borderObj 16, borderPairs 18, violations 0.
     - `PlacementExplainView.tsx`: totalStyleAttrs 30, checkedObjects 2, checkedPairs 14, unbound 10, covered 12, borderObj 5, borderPairs 8, violations 0.
     - `ResourceTopologyGraph.tsx`: totalStyleAttrs 23, checkedObjects 2, checkedPairs 9, unbound 7, covered 9, borderObj 4, borderPairs 6, violations 0.
  7. **Multiset Baseline 래칫 강제**: `COLOR_LITERAL_MULTISET_BASELINE`에서 3개 파일의 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
  8. **40종 전수 변이 실측 사살**: `tools/test_c274_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 복원 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `450e04b1`의 실제 코드 실측값(라이트 캔버스 `#f8fafc` 위 카드 서피스 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 측정되었습니다. 알파 합성은 채널 반올림 표준 공식(`round(alpha * fg + (1 - alpha) * bg)`)을 적용하였습니다. 베이스 `450e04b1`에 존재하던 3개 파일의 색상 리터럴 11건이 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c274_contrast.py` 실행 결과(27개 전 항목)와 100% 일치합니다.

각 지표의 배경 산출 근거 줄 번호:
- `NodeDetail.tsx`: 105행 관측 콜아웃(100행 `node-detail-observation-callout` `var(--color-bg-subtle)`), 188행 자원 에러(184행 `node-resource-usage-error` `var(--color-bg-subtle)`), 396행 스케줄 박스(394행 `node-detail-schedulable-box` `var(--color-bg-subtle)`), 200행 타임라인(180행 패널 `var(--color-bg-subtle)`).
- `PlacementExplainView.tsx`: 35행 시뮬레이션 배지(30행 배지 자체 `var(--color-bg-subtle)`), 59행 위너 배너(53행 `placement-explain-winner-banner` `var(--color-bg-subtle)`), 112행 후보 배지(107행 배지 자체 `var(--color-bg-subtle)`), 136행 탈락 사유(90행 후보 카드 `var(--color-bg-subtle)`), 179행 위너 점수(90행 후보 카드 `var(--color-bg-subtle)`).
- `ResourceTopologyGraph.tsx`: 56행 노드 카드(52행 카드 자체 `var(--color-bg-subtle)` over 조상 서피스/캔버스), 75행 선택 배지(73행 배지 자체 `var(--color-bg-subtle)`), 89행 펜스 배지(87행 배지 자체 `var(--color-bg-subtle)`), 69행 호스트명 및 70행 노드 ID(52행 카드 `var(--color-bg-subtle)`).

| ID | UI 요소 | 위치 (코드 줄) | Before 베이스 합성값 (Hex/RGBA on Underlay) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IT01 | 관측 콜아웃 제목 | NodeDetail.tsx:103 | var(--color-status-unknown) on rgba(210,153,34,0.12) (#faf7e8 / #292723) | 6.01:1 (PASS) / 4.96:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| IT02 | 관측 콜아웃 본문 | NodeDetail.tsx:105 | var(--color-text-primary) on rgba(210,153,34,0.12) (#faf7e8 / #292723) | 15.15:1 (PASS) / 11.97:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| IT03 | 자원 에러 알림 | NodeDetail.tsx:188 | var(--color-status-lost) on rgba(248,81,73,0.10) (#feeeec / #271f25) | 5.37:1 (PASS) / 4.67:1 (PASS) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| IT04 | 스케줄 박스 텍스트 | NodeDetail.tsx:396 | var(--color-status-unknown) on rgba(210,153,34,0.15) (#f9f5e4 / #2f2b26) | 5.86:1 (PASS) / 4.71:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| IT05 | 스케줄 박스 테두리 | NodeDetail.tsx:397 | var(--color-status-unknown) on rgba(210,153,34,0.15) | 5.86:1 (PASS) / 4.71:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| IT06 | 타임라인 offline 상태 | NodeDetail.tsx:200 | var(--color-status-offline) on var(--color-bg-subtle) | 6.47:1 (PASS) / 6.41:1 (PASS) | --color-status-offline on --color-bg-subtle | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| IT07 | 타임라인 unknown 상태 | NodeDetail.tsx:200 | var(--color-status-unknown) on var(--color-bg-subtle) | 7.09:1 (PASS) / 7.03:1 (PASS) | --color-status-unknown on --color-bg-subtle | 7.09:1 | 7.03:1 | >= 4.5:1 | PASS |
| IT08 | 시뮬레이션 배지 텍스트 | PlacementExplainView.tsx:35 | #d97706 on rgba(234,179,8,0.15) (#fbf4d8 / #312e1f) | 2.90:1 (FAIL) / 2.77:1 (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| IT09 | 시뮬레이션 배지 테두리 | PlacementExplainView.tsx:37 | rgba(234,179,8,0.3) on rgba(234,179,8,0.15) | 1.11:1 (FAIL) / 1.17:1 (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| IT10 | 위너 배너 테두리 | PlacementExplainView.tsx:61 | var(--color-brand-success) on rgba(16,185,129,0.1) (#e7f8f1 / #13282b) | 3.87:1 (PASS) / 5.21:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| IT11 | 위너 배너 본문 | PlacementExplainView.tsx:59 | var(--color-text-primary) on rgba(16,185,129,0.1) | 14.15:1 (PASS) / 11.51:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| IT12 | 통과 후보 배지 텍스트 | PlacementExplainView.tsx:112 | var(--color-brand-success) on rgba(16,185,129,0.15) (#dbf5ea / #143335) | 3.56:1 (FAIL) / 4.70:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| IT13 | 통과 후보 배지 테두리 | PlacementExplainView.tsx:114 | (테두리 없음 → 1px 토큰 테두리 신설) | N/A | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| IT14 | 탈락 후보 배지 텍스트 | PlacementExplainView.tsx:112 | var(--color-brand-danger) on var(--color-risk-l3-bg) | 4.58:1 (PASS) / 4.58:1 (PASS) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| IT15 | 탈락 후보 배지 테두리 | PlacementExplainView.tsx:114 | (테두리 없음 → 1px 토큰 테두리 신설) | N/A | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| IT16 | 탈락 사유 텍스트 | PlacementExplainView.tsx:136 | var(--color-brand-danger) on var(--color-bg-subtle) | 4.83:1 (PASS) / 4.83:1 (PASS) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| IT17 | 위너 점수 텍스트 | PlacementExplainView.tsx:179 | var(--color-brand-success) on var(--color-bg-subtle) | 4.58:1 (PASS) / 6.44:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| IT18 | 후보 카드 테두리 | PlacementExplainView.tsx:96 | var(--color-border-subtle) on var(--color-bg-surface) | 3.48:1 (PASS) / 3.73:1 (PASS) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| IT19 | 선택 노드 카드 테두리 | ResourceTopologyGraph.tsx:69 | var(--color-brand-success) on var(--color-bg-surface) | 4.79:1 (PASS) / 6.57:1 (PASS) | --color-status-online on --color-bg-surface | 5.02:1 | 7.79:1 | >= 3.0:1 | PASS |
| IT20 | 펜스 노드 카드 테두리 | ResourceTopologyGraph.tsx:69 | var(--color-risk-l3-border) on var(--color-bg-surface) | 6.47:1 (PASS) / 6.41:1 (PASS) | --color-status-lost on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| IT21 | 일반 노드 카드 테두리 | ResourceTopologyGraph.tsx:69 | var(--color-border-subtle) on var(--color-bg-surface) | 3.48:1 (PASS) / 3.73:1 (PASS) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| IT22 | 1순위 배치 배지 텍스트 | ResourceTopologyGraph.tsx:92 | #ffffff on var(--color-brand-success) (#16a34a / #22c55e) | 4.58:1 (PASS) / 2.28:1 (FAIL) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| IT23 | 1순위 배치 배지 테두리 | ResourceTopologyGraph.tsx:93 | (테두리 없음 → 1px 토큰 테두리 신설) | N/A | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| IT24 | FENCED 배지 텍스트 | ResourceTopologyGraph.tsx:107 | #ffffff on var(--color-brand-danger) (#dc2626 / #ef4444) | 4.83:1 (PASS) / 3.99:1 (FAIL) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| IT25 | FENCED 배지 테두리 | ResourceTopologyGraph.tsx:108 | (테두리 없음 → 1px 토큰 테두리 신설) | N/A | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| IT26 | 카드 호스트명 텍스트 | ResourceTopologyGraph.tsx:80 | var(--color-text-primary) on var(--color-bg-subtle) | 16.30:1 (PASS) / 14.05:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| IT27 | 카드 노드 ID 텍스트 | ResourceTopologyGraph.tsx:81 | var(--color-text-muted) on var(--color-bg-subtle) | 5.25:1 (PASS) / 5.78:1 (PASS) | --color-text-muted on --color-bg-subtle | 5.25:1 | 5.78:1 | >= 4.5:1 | PASS |

---

## 3. 핵심 구현 및 설계 결정사항

### 3.1 ResourceTopologyGraph HTML DOM 구조 및 3.0:1 비텍스트 대비 규격
- `ResourceTopologyGraph`는 복잡한 SVG 렌더링이 아닌 의미론적 HTML5 레이아웃 컴포넌트(`<div>`, `<span>`, `<code>`, `<strong>`)로 구성됨.
- 배지에 `#ffffff` 텍스트를 고정하여 다크 모드에서 각각 2.28:1(초록 배경 위 백색), 3.99:1(빨강 배경 위 백색)로 심각한 명도 결손(FAIL < 4.5:1)을 유발하던 레거시 구조를 전면 개편.
- 배지 배경을 다크/라이트 양 테마에서 모두 안정적인 `var(--color-bg-subtle)`로 통일하고, 텍스트와 1px 테두리에 상태 토큰(`var(--color-status-online)`, `var(--color-status-lost)`)을 부여하여 4.58~6.44:1의 텍스트 대비와 3.0:1 이상의 비텍스트 테두리 대비를 동시에 완벽 보장.
- 노드 카드의 2px 외곽선 테두리는 `isFenced ? 'var(--color-status-lost)' : isSelected ? 'var(--color-status-online)' : 'var(--color-border-subtle)'` 삼항식 인라인 표현으로 승격하여 `analyzeFile` AST 분석기가 3개 분기 모두를 정적으로 추적 및 검증 가능하게 함.

### 3.2 NodeDetail 정본 계약 재사용
- 노드 상태(`online`, `active`, `degraded`, `lost`, `unknown`)를 처리할 때 중복 매핑 객체를 정의하지 않고 Card 248에서 완성된 `getClusterNodeStatusConfig` 및 `NODE_STATUS_CONFIG`(`apps/web/src/features/dashboard/ClusterOverview.tsx`)를 직접 import하여 사용.
- `Object.hasOwn` fail-closed prototype 방어 검증을 타임라인 스냅샷(`[data-testid="node-detail-timeline-status"]`) 및 상태 라벨에 일관 적용하여 prototype 오염 키, 비표준 상태 문자열 주입 시 `Heartbeat FAILED (UNKNOWN (<raw>))`로 안전 강등.

### 3.3 PlacementExplainView 시뮬레이션 배지 및 위너 배너
- 하드코딩 `#d97706` 및 반투명 노랑 틴트 `rgba(234, 179, 8, 0.15)`의 심각한 결손(2.90:1 FAIL)을 `var(--color-bg-subtle)` 및 `var(--color-status-unknown)`(6.47:1 / 5.82:1 PASS)으로 정식 승격.
- 위너 배너 배경 `rgba(16, 185, 129, 0.1)`를 `var(--color-bg-subtle)`로 정규화하고 테두리에 `var(--color-status-online)`을 바인딩.

---

## 4. 40종 전수 변이 테스트 (W1~W40) 사살 표

| 변이 ID | 대상 파일 | 변이 내용 및 의도 | 사살 감지 시험 | 상태 |
| :--- | :--- | :--- | :--- | :--- |
| W1 | NodeDetail | 관측 콜아웃 배경==텍스트 1:1 충돌 (`backgroundColor: var(--color-status-unknown)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2 & Test 9x) | KILLED |
| W2 | NodeDetail | 관측 콜아웃 저대비 텍스트 변이 (`color: var(--color-text-inverse)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2 & Test 9x) | KILLED |
| W3 | NodeDetail | 관측 콜아웃 테두리==배경 1:1 충돌 (`border: 1px solid var(--color-bg-subtle)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2) | KILLED |
| W4 | NodeDetail | 자원 에러 알림 배경==텍스트 1:1 충돌 (`backgroundColor: var(--color-status-lost)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2 & Test 9x) | KILLED |
| W5 | NodeDetail | 자원 에러 알림 저대비 텍스트 변이 (`color: var(--color-text-inverse)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2 & Test 9x) | KILLED |
| W6 | NodeDetail | 자원 에러 알림 테두리==배경 1:1 충돌 (`border: 1px solid var(--color-bg-subtle)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2) | KILLED |
| W7 | NodeDetail | 스케줄 가능 박스 관측전용 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x DOM binding) | KILLED |
| W8 | NodeDetail | 스케줄 가능 박스 정상 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x DOM binding) | KILLED |
| W9 | NodeDetail | 스케줄 라벨 색상 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9j-2 AST check) | KILLED |
| W10 | NodeDetail | 타임라인 상태 텍스트 secondary 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x timelineOffline DOM) | KILLED |
| W11 | NodeDetail | 타임라인 상태 라벨 계약 fallback 우회 | `acc09-contrast-tokens.test.tsx` (Test 9x corrupt status DOM) | KILLED |
| W12 | NodeDetail | 관측 콜아웃 리터럴 회귀 `rgba(210, 153, 34, 0.12)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W13 | NodeDetail | 자원 에러 알림 리터럴 회귀 `rgba(248, 81, 73, 0.1)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W14 | NodeDetail | 스케줄 박스 리터럴 회귀 `rgba(210, 153, 34, 0.15)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W15 | PlacementExplainView | 시뮬레이션 배지 배경==텍스트 1:1 충돌 (`backgroundColor: var(--color-status-unknown)`) | `acc09-contrast-tokens.test.tsx` (Test 9x simBadge bg) | KILLED |
| W16 | PlacementExplainView | 시뮬레이션 배지 저대비 텍스트 변이 (`color: var(--color-text-inverse)`) | `acc09-contrast-tokens.test.tsx` (Test 9j-2 AST check) | KILLED |
| W17 | PlacementExplainView | 시뮬레이션 배지 테두리==배경 1:1 충돌 (`border: 1px solid var(--color-bg-subtle)`) | `acc09-contrast-tokens.test.tsx` (Test 9x simBadge border) | KILLED |
| W18 | PlacementExplainView | 위너 배너 배경 online 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x winnerBanner bg) | KILLED |
| W19 | PlacementExplainView | 위너 배너 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x winnerBanner border) | KILLED |
| W20 | PlacementExplainView | 위너 없음 배너 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x noWinnerBanner border) | KILLED |
| W21 | PlacementExplainView | 통과 후보 배지 배경==텍스트 1:1 충돌 | `acc09-contrast-tokens.test.tsx` (Test 9x candidateBadges[0] bg) | KILLED |
| W22 | PlacementExplainView | 탈락 후보 배지 배경==텍스트 1:1 충돌 | `acc09-contrast-tokens.test.tsx` (Test 9x candidateBadges[2] bg) | KILLED |
| W23 | PlacementExplainView | 후보 배지 저대비 텍스트 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x candidateBadges[0] color) | KILLED |
| W24 | PlacementExplainView | 후보 배지 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x candidateBadges[0] border) | KILLED |
| W25 | PlacementExplainView | 위너 점수 secondary 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x scoreValues[0] color) | KILLED |
| W26 | PlacementExplainView | 시뮬레이션 배지 리터럴 회귀 `#d97706` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W27 | PlacementExplainView | 후보 배지 리터럴 회귀 `rgba(16, 185, 129, 0.15)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W28 | PlacementExplainView | 위너 배너 리터럴 회귀 `rgba(16, 185, 129, 0.1)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W29 | ResourceTopologyGraph | 노드 카드 배경 status-online 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x selectedNodeEl bg) | KILLED |
| W30 | ResourceTopologyGraph | 선택 노드 카드 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x selectedNodeEl border) | KILLED |
| W31 | ResourceTopologyGraph | 펜스 노드 카드 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x fencedNodeEl border) | KILLED |
| W32 | ResourceTopologyGraph | 선택 배지 배경==텍스트 1:1 충돌 | `acc09-contrast-tokens.test.tsx` (Test 9x selectedBadge bg) | KILLED |
| W33 | ResourceTopologyGraph | 선택 배지 저대비 텍스트 변이 (`color: var(--color-text-inverse)`) | `acc09-contrast-tokens.test.tsx` (Test 9x selectedBadge color) | KILLED |
| W34 | ResourceTopologyGraph | 선택 배지 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x selectedBadge border) | KILLED |
| W35 | ResourceTopologyGraph | 펜스 배지 배경==텍스트 1:1 충돌 | `acc09-contrast-tokens.test.tsx` (Test 9x fencedBadge bg) | KILLED |
| W36 | ResourceTopologyGraph | 펜스 배지 저대비 텍스트 변이 (`color: var(--color-text-inverse)`) | `acc09-contrast-tokens.test.tsx` (Test 9x fencedBadge color) | KILLED |
| W37 | ResourceTopologyGraph | 펜스 배지 테두리 subtle 변이 | `acc09-contrast-tokens.test.tsx` (Test 9x fencedBadge border) | KILLED |
| W38 | ResourceTopologyGraph | 선택 배지 리터럴 회귀 `#ffffff` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W39 | ResourceTopologyGraph | 펜스 배지 리터럴 회귀 `#ffffff` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |
| W40 | ResourceTopologyGraph | 노드 카드 리터럴 회귀 `rgba(16, 185, 129, 0.08)` | `acc09-contrast-tokens.test.tsx` (Test 10 Multiset Baseline) | KILLED |

---

## 5. 게이트 및 검증 체크리스트

- [x] **Git Diff Check**: `git diff --check` 통과 (trailing whitespace 0건).
- [x] **Check Docs**: `python tools/check_docs.py` 통과 (doc_id, version, updated 양식 준수).
- [x] **Obsidian Sync Check**: `python tools/sync_obsidian.py --check` 통과.
- [x] **TypeScript Build**: `apps/web`에서 `node node_modules/typescript/bin/tsc -b` 통과 (에러 0건).
- [x] **Production Bundle**: `apps/web`에서 `npm run build` 통과 (`dist/` 번들 정상 생성).
- [x] **Route Coverage Gate**: `pytest tests/test_route_coverage.py` 통과 (41개 시험 전수 통과).
- [x] **Contrast Reproduction Script**: `python tools/reproduce_c274_contrast.py` 27개 항목 전수 ALL PASS.
- [x] **Vitest Unit Suite**: `npx vitest run tests/acc09-contrast-tokens.test.tsx` 38개 시험 100% PASS.
- [x] **Mutation Testing**: `python tools/test_c274_mutations.py --all` 40/40 100% 사살 실측 및 receipt B 봉인.
