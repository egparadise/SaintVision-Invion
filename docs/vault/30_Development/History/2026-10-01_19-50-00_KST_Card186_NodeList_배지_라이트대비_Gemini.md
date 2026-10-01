---
doc_id: "HIST-20261001-C186-ACC09-001"
title: "Card 186 (ACC-09 남은 영역) NodeList 상태 배지 라이트 테마 대비 보정 및 디자인 토큰화"
version: "1.0.1"
status: "proposed"
author: "Gemini"
created: "2026-10-01T19:50:00+09:00"
updated: "2026-10-01T20:52:00+09:00"
source_of_truth: "Git"
base_sha: "37119fc1"
task_ids: ["ACC-09", "S11-FE"]
tags: ["a11y", "contrast", "wcag", "nodelist", "status-badge", "design-tokens", "gemini"]
---

# Card 186 (ACC-09 남은 영역) NodeList 상태 배지 라이트 테마 대비 보정 및 디자인 토큰화

## 1. 배경 및 문제 정의 (PR #277 백로그 해소)

PR #277(승인 커밋 `2d2e0021`, train 8 머지 `37119fc1`)에서 카드 180 디자인 토큰 기반 대비 전수 개선 및 140곳 저대비 요소 일괄 해소가 완료되었으나, History 7.1절 및 Claude UI r1 피드백에서 `apps/web/src/features/nodes/NodeList.tsx`의 내부 상태 배지에 하드코딩 리터럴 색상 3종(`#38bdf8`, `#f85149`, `#d29922`)이 잔존하여 라이트 표면(`--color-bg-surface: #ffffff`) 위에서 WCAG 2.2 AA 본문 텍스트 기준($\ge 4.5:1$)에 미달함이 백로그로 식별되었다.

본 카드(카드 186)는 해당 3개 상태색을 하드코딩 리터럴에서 정식 디자인 토큰으로 승격하고, 라이트/다크 양쪽 테마에서 본문 텍스트 기준($\ge 4.5:1$)을 전수 달성하며, 색상 외 텍스트·아이콘 수단을 동반하여 상태 간 의미적 구별성을 확보하는 것을 목표로 한다.

### Before vs After 실측 대비율 대조표

| 상태 구분 | 기존 구현 (하드코딩 리터럴) | 신규 디자인 토큰 | 라이트 표면 (`#ffffff`) 실측 대비율 | 다크 표면 (`#111827`) 실측 대비율 | WCAG 2.2 AA ($\ge 4.5:1$) 판정 | 상태 구별 수단 (색상 외 동반) |
|---|---|---|---|---|---|---|
| **active** (활성 · 헬스 미결정) | `#38bdf8` (2.14:1) | `--color-status-active`<br>(Light: `#0369a1` / Dark: `#38bdf8`) | **5.93:1** (▲ 3.79) | **8.28:1** (유지) | **합격 (PASS)** | • 텍스트: `ACTIVE (활성 · 헬스 미결정)`<br>• 안내 배너: `ℹ️ 계약 상태: active...`<br>• 6px 상태 인디케이터 도트 |
| **lost** (통신 단절 / 유실) | `#f85149` (3.35:1) | `--color-status-lost`<br>(Light: `#b91c1c` / Dark: `#f87171`) | **6.47:1** (▲ 3.12) | **6.41:1** (▲ 1.12 on surface / ▲ 0.93 on subtle) | **합격 (PASS)** | • 텍스트: `LOST (단절)`<br>• 알림 문구: `🔴 노드와의 통신이 두절되어...`<br>• 시맨틱: `role="alert"`<br>• 6px 상태 도트 |
| **unknown** (미확인 / 미해석) | `#d29922` (2.52:1) | `--color-status-unknown`<br>(Light: `#92400e` / Dark: `#d29922`) | **7.09:1** (▲ 4.57) | **7.03:1** (유지) | **합격 (PASS)** | • 텍스트: `UNKNOWN (미확인)`<br>• 알림 문구: `⚠️ 서버에서 관측된 노드 상태...`<br>• 관측 배너: `⚠️ 관측 전용...`<br>• 시맨틱: `role="status"`<br>• 6px 상태 도트 |

> [!NOTE]
> **다크 테마 lost 토큰값 보정 배경 (Claude m2)**: 다크 테마에서 기존 `#f85149`는 다크 subtle(`--color-bg-subtle: #1f2937`) 위에서 4.38:1로 WCAG AA 4.5:1에 미달하였습니다. 이를 `#f87171`로 보정하여 subtle 위 5.31:1(▲0.93) 및 surface 위 6.41:1(▲1.12)로 향상되어 양쪽 배경 모두 4.5:1 이상을 충족하는 의도된 개선입니다.
> 
> **상태색 공유 및 비색상 의미 식별 (Claude m4)**: `--color-status-lost`와 `--color-status-offline`은 두 테마 모두 동일한 빨간색 토큰(Light: `#b91c1c`, Dark: `#f87171`, $\Delta E_{00} = 0.0$)을 사용합니다. 이는 통신 단절 및 오프라인이라는 동일 심각도 범주의 색채 일관성을 위한 것이며, 상태의 고유 식별은 텍스트 라벨(`LOST (단절)` vs `OFFLINE`), 아이콘(🔴 경고 vs 일반), ARIA 속성(`role="alert"`)을 동반하여 WCAG 1.4.1(Use of Color) 지침을 온전히 충족합니다.

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
- **CSS 주석 Decoy 및 중복 선언 방지 검증 (Codex F2)**:
  - `extractTokens`에서 `/\*[\s\S]*?\*/` 주석을 완전히 제거한 후 실제 선언만 파싱하고 블록별 중복 선언 검출 시 즉각 예외 발생.
  - `:root` 및 `[data-theme='dark']` 블록에서 상태 토큰 3종이 각각 정확히 1회씩 선언됨을 단언.
- **신규 DOM 렌더링 및 결속 검증 (Test 8, Codex F1/F3, Claude m3)**:
  - 표준 카드 및 텔레메트리 미수신 카드 6개 분기 전수 렌더링.
  - 렌더된 배지의 `style.backgroundColor`가 `var(--color-bg-subtle)`임을 단언하고, DOM 요소의 인라인 스타일에서 추출한 foreground/background 토큰 쌍으로 라이트/다크 대비율 $\ge 4.5:1$ 동적 계산 단언 (Codex F1 해소).
  - 관측 전용 배너(`style.color`, `style.borderColor`), 예약가능 용량 라벨(`style.color`) 토큰 결속 단언 (Claude MD/m3 해소).
  - unknown 상태의 `role="status"` 및 `⚠️` 비색상 기호 단언 (Codex F3 해소).
  - 배너 alpha 합성 배경에 대한 명도 대비율 $\ge 4.5:1$ 계산 단언 (Claude m3 해소).
- **Revert-Fail 프로브 추가 (Test 9)**:
  - Probe 7: `#38bdf8` on light surface $\rightarrow$ 2.14:1 (< 4.5:1 실패)
  - Probe 8: `#f85149` on light surface $\rightarrow$ 3.35:1 (< 4.5:1 실패)
  - Probe 9: `#d29922` on light surface $\rightarrow$ 2.52:1 (< 4.5:1 실패)

---

## 3. 변이 검사 실측 결과 (9종 변이 100% 사살)

| 변이 ID | 변이 내용 | 검증 가드 및 단언 | 결과 |
|---|---|---|---|
| **M1** | `NodeList.tsx` 표준 배지 `backgroundColor`를 `var(--color-status-active)`로 변조 (Codex F1) | Test 8 렌더 배경 단언 및 DOM 추출 토큰 쌍 동적 대비 단언 (1.0:1 < 4.5:1) | **KILLED** |
| **M2** | `index.css` 라이트 active 복귀 후 주석 decoy 추가 (Codex F2) | `extractTokens` 주석 스트립 및 F2 단일 선언 단언 | **KILLED** |
| **M3** | `index.css` 라이트 lost 복귀 후 주석 decoy 추가 (Codex F2) | `extractTokens` 주석 스트립 및 F2 단일 선언 단언 | **KILLED** |
| **M4** | `index.css` 라이트 unknown 복귀 후 주석 decoy 추가 (Codex F2) | `extractTokens` 주석 스트립 및 F2 단일 선언 단언 | **KILLED** |
| **M5** | `NodeList.tsx` 관측 전용 배너 color를 `var(--color-status-degraded)`로 변조 (Claude MD) | Test 8 `obsBanner.style.color` 단언 | **KILLED** |
| **M6** | `NodeList.tsx` 표준 lost 분기에 리터럴+주석 decoy 복귀 (Claude MC) | Test 8 DOM 결속 단언 & Test 10 멀티셋 인벤토리 래칫 | **KILLED** |
| **M7** | `NodeList.tsx` 텔레메트리 unknown 카드의 `role="status"` 제거 (Codex F3) | Test 8 `telemUnknownCard.role` 단언 | **KILLED** |
| **M8** | `NodeList.tsx` 표준 unknown 카드의 `role="status"` 제거 (Codex F3) | Test 8 `stdUnknownCard.role` 단언 | **KILLED** |
| **M9** | `NodeList.tsx` 예약가능 용량 color를 `var(--color-status-degraded)`로 변조 (Claude m3) | Test 8 `schedLabel.style.color` 단언 | **KILLED** |

> **실측 판정**: 9종 변이 중 **9종 전원 사망 (Killed: 9, Survived: 0, 사살율 100%)**.

---

## 4. 검증 게이트 실측 결과

| 검증 항목 / 도구 | 명령 및 실행 환경 | 실측 결과 | 상세 내용 |
|---|---|---|---|
| **신규/확장 단위 테스트** | `npm run test -- acc09-contrast-tokens.test.tsx` | **PASS (11 passed, 170ms)** | 11개 시험 전원 통과, 변이 9종 100% 사살 |
| **NodeList 관련 회귀 테스트** | `npm run test -- node-status-lost-unknown-guard.test.tsx node-resource-usage-contract.test.tsx` | **PASS (전원 통과)** | 노드 상태 표출 및 자원 계약 무파괴 통과 |
| **TypeScript 컴파일** | `npx tsc -b` (apps/web) | **PASS (에러 0건)** | 타입 체커 통과 |
| **프로덕션 번들 빌드** | `npm run build` (apps/web) | **PASS (exit 0)** | Vite production bundle 정상 생성 |
| **화면-백엔드 라우트 커버리지** | `pytest tests/test_route_coverage.py` | **PASS (40 passed)** | 40개 라우트/화면 검증 전원 통과 |
| **프런트엔드 무결성 점검** | `python tools/check_frontend_integrity.py` | **PASS (0 violations)** | 92개 파일 9대 무결성 규칙 클린 통과 |
| **계약 바인딩 점검** | `python tools/check_contract_bindings.py` | **PASS (exit 0)** | 55개 픽스처 + 20개 커널 응답 타입 앵커 통과 |
| **문서 정합성 점검** | `python tools/check_docs.py` | **PASS (exit 0)** | 1066개 문서 일관성 통과 |
| **문서 인용 래칫 점검** | `python tools/check_doc_path_citations.py --ratchet --base-ref 37119fc1` | **PASS (exit 0)** | 0 new broken citations |
| **Git 포맷 무결성** | `git diff --check 37119fc1` | **PASS (클린)** | 공백 및 개행 오류 0건 |
| **금지 문자열 검사** | 봇 호출 태그 점검 | **0건 검출 확인** | 커밋, 문서, PR 코멘트 대상 |

---

## 5. 인계 및 검토 요청

- **Base 브랜치**: `agent/gemini/c180-s11fe-contrast-fixes` (head `37119fc1`, PR #277)
- **작업 브랜치**: `agent/gemini/c186-nodelist-badge-contrast`
- **검토 요청**:
  - Claude: UI/접근성/스타일링 축 — 상태 배지 라이트 테마 시각적 대비, 비색상 의미 구별(아이콘/텍스트/ARIA) 및 단위 시험 11 passed 검토 요청.
  - Codex: 무결성/래칫 축 — `COLOR_LITERAL_MULTISET_BASELINE` 순수 감소, 9종 변이 100% 사살 불변식 검토 요청.

---

## 6. 범위 밖 잔여 리터럴 후속 백로그 등록 (Claude i1 피드백)

본 카드(Card 186)는 NodeList 상태 배지 3개 리터럴(`#38bdf8`, `#f85149`, `#d29922`)의 디자인 토큰 승격 및 라이트 대비 개선을 전담하였으며, 아래 식별된 잔여 리터럴은 `COLOR_LITERAL_MULTISET_BASELINE`에 봉인된 상태로 차기 접근성/디자인 토큰 정비 카드로 안전하게 이월함:
- `NodeList.tsx:228` telemetryUnavailable 카드 안내문 `<p>` 색상:
  - `#fca5a5` (라이트 surface 대비 1.90:1)
  - `#fde68a` (라이트 surface 대비 1.25:1)
  - `#7dd3fc` (라이트 surface 대비 1.67:1)
- `NodeList.tsx:420` 예약가능 라벨: `#3fb950` (라이트 surface 대비 2.54:1)
- `NodeList.tsx:190` 카드 테두리: `#f59e0b`
- `NodeDetail.tsx` 내 동일 3개 리터럴 (`#fca5a5`: 1건, `#fde68a`: 6건, `#7dd3fc`: 3건)
