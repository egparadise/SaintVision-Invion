---
doc_id: "HIST-20261001-C186-ACC09-001"
title: "Card 186 (ACC-09 남은 영역) NodeList 상태 배지 라이트 테마 대비 보정 및 디자인 토큰화"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-01T19:50:00+09:00"
updated: "2026-10-01T19:58:00+09:00"
source_of_truth: "Git"
base_sha: "2d2e0021"
task_ids: ["ACC-09", "S11-FE"]
tags: ["a11y", "contrast", "wcag", "nodelist", "status-badge", "design-tokens", "gemini"]
---

# Card 186 (ACC-09 남은 영역) NodeList 상태 배지 라이트 테마 대비 보정 및 디자인 토큰화

## 1. 배경 및 문제 정의 (PR #277 백로그 해소)

PR #277(승인 커밋 `2d2e0021`)에서 카드 180 디자인 토큰 기반 대비 전수 개선 및 140곳 저대비 요소 일괄 해소가 완료되었으나, History 7.1절 및 Claude UI r1 피드백에서 `apps/web/src/features/nodes/NodeList.tsx`의 내부 상태 배지에 하드코딩 리터럴 색상 3종(`#38bdf8`, `#f85149`, `#d29922`)이 잔존하여 라이트 표면(`--color-bg-surface: #ffffff`) 위에서 WCAG 2.2 AA 본문 텍스트 기준($\ge 4.5:1$)에 미달함이 백로그로 식별되었다.

본 카드(카드 186)는 해당 3개 상태색을 하드코딩 리터럴에서 정식 디자인 토큰으로 승격하고, 라이트/다크 양쪽 테마에서 본문 텍스트 기준($\ge 4.5:1$)을 전수 달성하며, 색상 외 텍스트·아이콘 수단을 동반하여 상태 간 의미적 구별성을 확보하는 것을 목표로 한다.

### Before vs After 실측 대비율 대조표

| 상태 구분 | 기존 구현 (하드코딩 리터럴) | 신규 디자인 토큰 | 라이트 표면 (`#ffffff`) 실측 대비율 | 다크 표면 (`#111827`) 실측 대비율 | WCAG 2.2 AA ($\ge 4.5:1$) 판정 | 상태 구별 수단 (색상 외 동반) |
|---|---|---|---|---|---|---|
| **active** (활성 · 헬스 미결정) | `#38bdf8` (2.14:1) | `--color-status-active`<br>(Light: `#0369a1` / Dark: `#38bdf8`) | **5.93:1** (▲ 3.79) | **8.28:1** (유지) | **합격 (PASS)** | • 텍스트: `ACTIVE (활성 · 헬스 미결정)`<br>• 안내 배너: `ℹ️ 계약 상태: active...`<br>• 6px 상태 인디케이터 도트 |
| **lost** (통신 단절 / 유실) | `#f85149` (3.35:1) | `--color-status-lost`<br>(Light: `#b91c1c` / Dark: `#f87171`) | **6.47:1** (▲ 3.12) | **6.41:1** (▲ 1.12 on subtle) | **합격 (PASS)** | • 텍스트: `LOST (단절)`<br>• 알림 문구: `🔴 노드와의 통신이 두절되어...`<br>• 시맨틱: `role="alert"`<br>• 6px 상태 도트 |
| **unknown** (미확인 / 미해석) | `#d29922` (2.52:1) | `--color-status-unknown`<br>(Light: `#92400e` / Dark: `#d29922`) | **7.09:1** (▲ 4.57) | **7.03:1** (유지) | **합격 (PASS)** | • 텍스트: `UNKNOWN (미확인)`<br>• 알림 문구: `⚠️ 서버에서 관측된 노드 상태...`<br>• 관측 배너: `⚠️ 관측 전용...`<br>• 시맨틱: `role="status"`<br>• 6px 상태 도트 |

---

## 2. 구현 내역 (Implementation Details)

### 1) 디자인 토큰 정의 (`apps/web/src/index.css`)
- `:root` (Light Theme):
  - `--color-status-active: #0369a1;` (sky-700, surface 대비 5.93:1, subtle 대비 5.42:1, canvas 대비 5.67:1)
  - `--color-status-lost: #b91c1c;` (red-700, surface 대비 6.47:1, subtle 대비 5.91:1, canvas 대비 6.18:1)
  - `--color-status-unknown: #92400e;` (amber-800, surface 대비 7.09:1, subtle 대비 6.47:1, canvas 대비 6.77:1)
- `[data-theme='dark']` (Dark Theme):
  - `--color-status-active: #38bdf8;` (sky-400, surface 대비 8.28:1, subtle 대비 6.85:1, canvas 대비 9.07:1)
  - `--color-status-lost: #f87171;` (red-400, surface 대비 6.41:1, subtle 대비 5.31:1, canvas 대비 7.02:1)
  - `--color-status-unknown: #d29922;` (amber-400/gold, surface 대비 7.03:1, subtle 대비 5.82:1, canvas 대비 7.70:1)

### 2) NodeList 화면 토큰 결속 (`apps/web/src/features/nodes/NodeList.tsx`)
- **텔레메트리 미수신(`telemetryUnavailable`) 배지**:
  - `color`: `node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)'`
  - `border`: `1px solid ${...}` 동일 토큰 결속.
  - `backgroundColor` (도트): 동일 토큰 결속.
- **표준 카드 배지 (`statusColor`)**:
  - `node.status === 'active' ? 'var(--color-status-active)' : node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : ...`
- **관측 전용(`observationOnly`) 배너 및 예약가능 용량**:
  - 배너 `border` & `color`: `'var(--color-status-unknown)'`
  - 예약가능 span color: `node.observationOnly ? 'var(--color-status-unknown)' : ...`
- **활성 상태 고지 배너**:
  - `color`: `'var(--color-status-active)'`
- **하드코딩 리터럴 제거 실측**:
  - `NodeList.tsx` 내 `#38bdf8`: 5건 $\rightarrow$ **0건**
  - `NodeList.tsx` 내 `#f85149`: 4건 $\rightarrow$ **0건**
  - `NodeList.tsx` 내 `#d29922`: 7건 $\rightarrow$ **0건**
  - 신규 리터럴 유입 0건 (순수 디자인 토큰 결속).

### 3) 상태 간 의미적 구별성 (WCAG 1.4.1 Use of Color 충족)
- 색상 외에 명확한 텍스트 및 시각 기호 동반:
  - `active`: 텍스트 `ACTIVE (활성 · 헬스 미결정)`, 안내 아이콘 `ℹ️`
  - `lost`: 텍스트 `LOST (단절)`, 경고 아이콘 `🔴`, 카드 속성 `role="alert"`
  - `unknown`: 텍스트 `UNKNOWN (미확인)`, 주의 아이콘 `⚠️`, 카드 속성 `role="status"`
  - 각 배지 내 6px 원형 상태 인디케이터 유지.

### 4) 시험 및 래칫 검증 (`apps/web/tests/acc09-contrast-tokens.test.tsx`)
- **멀티셋 인벤토리 래칫 갱신**:
  - `COLOR_LITERAL_MULTISET_BASELINE["features/nodes/NodeList.tsx"]`에서 `#38bdf8`, `#f85149`, `#d29922` 키 완전 제거.
  - 리터럴 총개수 16건 감소 (감소 래칫 고정, 신규 리터럴 유입 시 즉각 fail-closed 사살).
- **상태 토큰 자동 검증 스위트 연동**:
  - `statusTokenList`에 3개 토큰 등록 $\rightarrow$ 캔버스/서피스/서브틀 배경 전수 $\ge 4.5:1$ 자동 검증.
- **신규 DOM 렌더링 및 결속 검증 (Test 8)**:
  - `NodeList` 컴포넌트 실렌더링 후 `active`, `lost`, `unknown` 배지의 `style.borderColor`, `style.color`, dot `style.backgroundColor`가 각각 `var(--color-status-active)`, `var(--color-status-lost)`, `var(--color-status-unknown)`에 결속됨을 단언.
  - 비색상 의미 구별(텍스트, 이모지, ARIA role) 단언.
  - 라이트/다크 전수 대비율 $\ge 4.5:1$ 계산 단언.
- **Revert-Fail 프로브 추가 (Test 9)**:
  - Probe 7: `#38bdf8` on light surface $\rightarrow$ 2.14:1 (< 4.5:1 실패)
  - Probe 8: `#f85149` on light surface $\rightarrow$ 3.35:1 (< 4.5:1 실패)
  - Probe 9: `#d29922` on light surface $\rightarrow$ 2.52:1 (< 4.5:1 실패)

---

## 3. 변이 검사 실측 결과 (6종 변이 100% 사살)

| 변이 ID | 변이 내용 | 검증 가드 및 단언 | 결과 |
|---|---|---|---|
| **M1** | `NodeList.tsx` active 상태를 구 하드코딩 `#38bdf8`로 되돌림 | Test 8 DOM 결속 단언 & Test 10 멀티셋 인벤토리 래칫 | **KILLED** |
| **M2** | `NodeList.tsx` lost 상태를 구 하드코딩 `#f85149`로 되돌림 | Test 8 DOM 결속 단언 & Test 10 멀티셋 인벤토리 래칫 | **KILLED** |
| **M3** | `NodeList.tsx` unknown 상태를 구 하드코딩 `#d29922`로 되돌림 | Test 8 DOM 결속 단언 & Test 10 멀티셋 인벤토리 래칫 | **KILLED** |
| **M4** | `index.css` 라이트 `--color-status-active`를 `#38bdf8`로 되돌림 | Test 3 Status text colors $\ge 4.5:1$ 단언 | **KILLED** |
| **M5** | `index.css` 라이트 `--color-status-lost`를 `#f85149`로 되돌림 | Test 3 Status text colors $\ge 4.5:1$ 단언 | **KILLED** |
| **M6** | `index.css` 라이트 `--color-status-unknown`를 `#d29922`로 되돌림 | Test 3 Status text colors $\ge 4.5:1$ 단언 | **KILLED** |

> **실측 판정**: 6종 변이 중 **6종 전원 사망 (Killed: 6, Survived: 0, 사살율 100%)**.

---

## 4. 검증 게이트 실측 결과

| 검증 항목 / 도구 | 명령 및 실행 환경 | 실측 결과 | 상세 내용 |
|---|---|---|---|
| **신규/확장 단위 테스트** | `npm run test -- acc09-contrast-tokens.test.tsx` | **PASS (10 passed, 131ms)** | 10개 시험 전원 통과, 변이 6종 100% 사살 |
| **NodeList 관련 회귀 테스트** | `npm run test -- node-status-lost-unknown-guard.test.tsx node-resource-usage-contract.test.tsx` | **PASS (전원 통과)** | 노드 상태 표출 및 자원 계약 무파괴 통과 |
| **TypeScript 컴파일** | `npx tsc -b` (apps/web) | **PASS (에러 0건)** | 타입 체커 통과 |
| **프로덕션 번들 빌드** | `npm run build` (apps/web) | **PASS (exit 0)** | Vite production bundle 정상 생성 |
| **화면-백엔드 라우트 커버리지** | `pytest tests/test_route_coverage.py` | **PASS (41 passed)** | 41개 라우트/화면 검증 전원 통과 |
| **프런트엔드 무결성 점검** | `python tools/check_frontend_integrity.py` | **PASS (0 violations)** | 93개 파일 9대 무결성 규칙 클린 통과 |
| **계약 바인딩 점검** | `python tools/check_contract_bindings.py` | **PASS (exit 0)** | 55개 픽스처 + 20개 커널 응답 타입 앵커 통과 |
| **문서 정합성 점검** | `python tools/check_docs.py` | **PASS (exit 0)** | 1066개 문서 일관성 통과 |
| **문서 인용 래칫 점검** | `python tools/check_doc_path_citations.py --ratchet --base-ref 2d2e0021` | **PASS (exit 0)** | 0 new broken citations |
| **Git 포맷 무결성** | `git diff --check 2d2e0021` | **PASS (클린)** | 공백 및 개행 오류 0건 |
| **금지 문자열 검사** | 봇 호출 태그 점검 | **0건 검출 확인** | 커밋, 문서, PR 코멘트 대상 |

---

## 5. 인계 및 검토 요청

- **Base 브랜치**: `agent/gemini/c180-s11fe-contrast-fixes` (head `2d2e0021`, PR #277)
- **작업 브랜치**: `agent/gemini/c186-nodelist-badge-contrast`
- **검토 요청**:
  - Claude: UI/접근성/스타일링 축 — 상태 배지 라이트 테마 시각적 대비, 비색상 의미 구별(아이콘/텍스트/ARIA) 및 단위 시험 10 passed 검토 요청.
  - Codex: 무결성/래칫 축 — `COLOR_LITERAL_MULTISET_BASELINE` 순수 감소, 6종 변이 100% 사살 불변식 검토 요청.
