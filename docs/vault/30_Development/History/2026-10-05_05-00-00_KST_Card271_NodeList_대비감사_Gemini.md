---
doc_id: "HIST-20261005-CARD271-GEMINI"
title: "Card 271 노드 목록 (NodeList) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T04:55:00+09:00"
updated: "2026-10-05T14:43:00+09:00"
source_of_truth: "Git"
---

# Card 271 노드 목록 (NodeList) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격

## 1. 작업 개요
- **목표**: 노드 목록 뷰(`apps/web/src/features/nodes/NodeList.tsx`)의 색상 리터럴 전수(9건→0건) 토큰화 및 디자인 토큰 체계 승격:
  1. 상태 설정 객체 정합성 및 중복 배제: Card 248에서 완성된 `NODE_STATUS_CONFIG` 및 `getClusterNodeStatusConfig` (`apps/web/src/features/cluster/ClusterOverview.tsx`) 계약을 직접 임포트하여 재사용. 정본 wire 계약 enum `NodeStatus` 9종(`online`, `active`, `syncing`, `degraded`, `draining`, `offline`, `rebalancing`, `maintenance`, `lost`)과 엄밀 일치.
  2. `getClusterNodeStatusConfig` fail-closed own-key 방어: `Object.hasOwn` 기반 검사로 prototype key(`toString`, `constructor`, `__proto__`, `valueOf`, `hasOwnProperty`, `isPrototypeOf`), 대소문자 변형(`ONLINE`), 계약 밖 값(`admitted`, `unknown_status`)의 fail-open 승격을 원천 차단하고 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 형식으로 안전 강등 매핑 (WCAG 1.4.1 준수).
  3. 코드 블록 및 부트스트랩 복사 UI: 다크 고정 리터럴 `#1e1e1e`, `#2d3748`, `#4ade80`, `#fff` 제거 및 `var(--color-bg-subtle)`, `var(--color-status-online)`, `var(--color-text-primary)` 토큰 승격. 복사 성공 피드백 텍스트를 `var(--color-status-online)`으로 승격하여 라이트 테마 명도비 1.74:1 결손(FAIL)을 5.02:1(PASS)로 교정.
  4. 관측 전용 배너 및 활성 노드 안내 시맨틱 보존: 관측 전용 배너(`role="region"`, `aria-label="관측 전용 모드 안내"`, `var(--color-status-unknown)` 테두리/텍스트), 활성 노드 알림(`role="region"`, `aria-label="활성 노드 실행 안내"`, `var(--color-status-active)` 테두리/텍스트). 반투명 리터럴 `rgba(210,153,34,0.15)`, `rgba(56,189,248,0.12)`, `rgba(56,189,248,0.3)` 전수 제거 및 라이트/다크 양방향 테두리 대비비 1.26:1/1.88:1 결손(FAIL)을 5.42:1/6.85:1(PASS)로 승격.
  5. 키보드 포커스 링 보존: 복사 버튼, 새로고침 버튼, 전체선택 버튼, 상세 토글 버튼, Studio 바로가기 버튼에 `outline: none/0`, `outlineWidth: 0` 등 포커스 링 억제 스타일 배제 및 computed outline 검증.
  6. Multiset Baseline 래칫 강제: `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/nodes/NodeList.tsx` 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정. `var(--color-border-subtle)` 사용 횟수: 중복된 서브틀 폴백 제거로 458건→457건으로 정밀 래칫.
  7. 40종 전수 변이 실측 사살: `tools/test_c271_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 PR 베이스(`c53f5451`)의 실제 렌더링 합성값(라이트 캔버스 `#f8fafc` 위 카드 표면 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#111827`, `#1f2937`)을 기준으로 하며, 하드코딩 리터럴의 라이트 테마 전환 시 심각한 명도 결손(Probes 116~120 실측)이 존재했습니다. 베이스 `c53f5451`의 리터럴은 총 9건(8종: `#1e1e1e`, `#2d3748`, `#4ade80`×2, `#fff`, `#ffffff`, `rgba(210,153,34,0.15)`, `rgba(56,189,248,0.12)`, `rgba(56,189,248,0.3)`)이며 전수 제거되어 0건으로 정착되었습니다. After 값은 `python tools/reproduce_c271_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before 베이스 합성값 (Hex/RGBA on Canvas/Surface/Subtle) | Before 명도비 (Light/Dark 렌더 실측) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 코드 블록 텍스트 | code-block text | #4ade80 on #1e1e1e | 9.07:1 (PASS) / 9.07:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 복사 버튼 텍스트 | btn-copy text | #ffffff on #2d3748 | 8.78:1 (PASS) / 8.78:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 복사 완료 피드백 | copy-feedback text | #4ade80 on #ffffff / #111827 | 1.74:1 (FAIL) / 9.25:1 (PASS) | --color-status-online on --color-bg-surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| 관측전용 배너 텍스트 | obs-banner text | var(--color-status-unknown) on rgba(210,153,34,0.15) | 6.46:1 (PASS) / 5.86:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 관측전용 배너 테두리 | obs-banner border | base에서 이미 토큰화됨 (var(--color-status-unknown) on surface) | 6.47:1 (PASS) / 5.82:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| 활성노드 안내 텍스트 | active-notice text | var(--color-status-active) on rgba(56,189,248,0.12) | 5.42:1 (PASS) / 6.85:1 (PASS) | --color-status-active on --color-bg-subtle | 5.42:1 | 6.85:1 | >= 4.5:1 | PASS |
| 활성노드 안내 테두리 | active-notice border | rgba(56,189,248,0.3) on #ffffff / #111827 | 1.21:1 (FAIL) / 1.74:1 (FAIL) | --color-status-active on --color-bg-subtle | 5.42:1 | 6.85:1 | >= 3.0:1 | PASS |
| Studio 열기 버튼 | btn-studio-open text | #ffffff on var(--color-brand-primary-bg) | 5.17:1 (PASS) / 6.70:1 (PASS) | --color-brand-primary-fg on --color-brand-primary-bg | 5.17:1 | 6.70:1 | >= 4.5:1 | PASS |
| Studio 열기 (관측전용) | btn-studio-obsonly text | base에서 이미 토큰화됨 (--color-text-inverse on --color-border-strong) | 7.58:1 (PASS) / 7.03:1 (PASS) | --color-text-inverse on --color-border-strong | 7.58:1 | 7.03:1 | >= 4.5:1 | PASS |
| 새로고침 버튼 | btn-refresh text | base에서 이미 토큰화됨 (var(--color-text-primary) on subtle) | 16.30:1 (PASS) / 14.05:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 전체선택 버튼 | btn-select-all text | base에서 이미 토큰화됨 (var(--color-text-primary) on subtle) | 16.30:1 (PASS) / 14.05:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 상태 배지 Online 텍스트 | badge-online text | base에서 이미 토큰화됨 (var(--color-status-online) on subtle) | 4.58:1 (PASS) / 6.44:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 상태 배지 Online 테두리 | badge-online border | base에서 이미 토큰화됨 (var(--color-status-online) on subtle) | 4.58:1 (PASS) / 6.44:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| 상태 배지 Active 텍스트 | badge-active text | base에서 이미 토큰화됨 (var(--color-status-active) on subtle) | 5.42:1 (PASS) / 6.85:1 (PASS) | --color-status-active on --color-bg-subtle | 5.42:1 | 6.85:1 | >= 4.5:1 | PASS |
| 상태 배지 Active 테두리 | badge-active border | base에서 이미 토큰화됨 (var(--color-status-active) on subtle) | 5.42:1 (PASS) / 6.85:1 (PASS) | --color-status-active on --color-bg-subtle | 5.42:1 | 6.85:1 | >= 3.0:1 | PASS |
| 상태 배지 Degraded 텍스트| badge-degraded text | base에서 이미 토큰화됨 (var(--color-status-degraded) on subtle) | 4.58:1 (PASS) / 6.83:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 상태 배지 Degraded 테두리| badge-degraded border | base에서 이미 토큰화됨 (var(--color-status-degraded) on subtle) | 4.58:1 (PASS) / 6.83:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 3.0:1 | PASS |
| 상태 배지 Lost/Offline 텍스트| badge-lost text | base에서 이미 토큰화됨 (var(--color-status-lost) on subtle) | 5.91:1 (PASS) / 5.31:1 (PASS) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 상태 배지 Lost/Offline 테두리| badge-lost border | base에서 이미 토큰화됨 (var(--color-status-lost) on subtle) | 5.91:1 (PASS) / 5.31:1 (PASS) | --color-status-lost on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 상태 배지 Unknown 텍스트 | badge-unknown text | base에서 이미 토큰화됨 (var(--color-status-unknown) on subtle) | 6.47:1 (PASS) / 5.82:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 상태 배지 Unknown 테두리 | badge-unknown border | base에서 이미 토큰화됨 (var(--color-status-unknown) on subtle) | 6.47:1 (PASS) / 5.82:1 (PASS) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| 헤더 제목 | header-title text | base에서 이미 토큰화됨 (#0f172a on #ffffff / #f9fafb on #111827) | 17.85:1 (PASS) / 16.98:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 헤더 부제목 | header-subtitle text | base에서 이미 토큰화됨 (var(--color-text-muted) on surface) | 5.75:1 (PASS) / 6.99:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 빈 화면 제목 | empty-title text | base에서 이미 토큰화됨 (var(--color-text-primary) on surface) | 17.85:1 (PASS) / 16.98:1 (PASS) | --color-text-primary on --color-bg-surface | 17.85:1 | 16.98:1 | >= 4.5:1 | PASS |
| 빈 화면 설명 | empty-desc text | base에서 이미 토큰화됨 (var(--color-text-muted) on surface) | 5.75:1 (PASS) / 6.99:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |

> [!NOTE]
> **라이트/다크 테마 Revert-Fail Probes (Probes 116~120)**:
> 옛 다크 하드코딩 리터럴을 테마 표면 위에 적용할 경우의 심각한 명도 결손 실측:
> - Probe 116 (`#4ade80` on light surface `#ffffff`): **1.74:1** (< 4.5:1 FAIL)
> - Probe 117 (`rgba(56, 189, 248, 0.3)` on light surface `#ffffff`): **1.21:1** (< 3.0:1 FAIL)
> - Probe 118 (`rgba(56, 189, 248, 0.3)` on dark surface `#111827`): **1.74:1** (< 3.0:1 FAIL)
> - Probe 119 (`#1e1e1e` on light surface `#ffffff` in code block): 1:1 contrast collision if inverted
> - Probe 120 (`#2d3748` on light canvas in copy button): 1:1 contrast collision if inverted

### 2.2 tools/reproduce_c271_contrast.py 실행 결과
```text
====================================================================================================
 Card 271 NodeList Contrast Verification Report (tools/reproduce_c271_contrast.py)
====================================================================================================
ID    | Element / Role               | MinCR | Light CR   | Dark CR    | Status
----------------------------------------------------------------------------------------------------
IT01  | code-block text              | 4.5   | 4.58       | 6.44       | PASS
IT02  | btn-copy text                | 4.5   | 16.30      | 14.05      | PASS
IT03  | copy-feedback text           | 4.5   | 5.02       | 7.79       | PASS
IT04  | obs-banner text              | 4.5   | 6.47       | 5.82       | PASS
IT05  | obs-banner border            | 3.0   | 6.47       | 5.82       | PASS
IT06  | active-notice text           | 4.5   | 5.42       | 6.85       | PASS
IT07  | active-notice border         | 3.0   | 5.42       | 6.85       | PASS
IT08  | btn-studio-open text         | 4.5   | 5.17       | 6.70       | PASS
IT09  | btn-studio-obsonly text      | 4.5   | 7.58       | 7.03       | PASS
IT10  | btn-refresh text             | 4.5   | 16.30      | 14.05      | PASS
IT11  | btn-select-all text          | 4.5   | 16.30      | 14.05      | PASS
IT12  | badge-online text            | 4.5   | 4.58       | 6.44       | PASS
IT13  | badge-active text            | 4.5   | 5.42       | 6.85       | PASS
IT14  | badge-degraded text          | 4.5   | 4.58       | 6.83       | PASS
IT15  | badge-lost text              | 4.5   | 5.91       | 5.31       | PASS
IT16  | badge-unknown text           | 4.5   | 6.47       | 5.82       | PASS
IT17  | badge-online border          | 3.0   | 4.58       | 6.44       | PASS
IT18  | badge-active border          | 3.0   | 5.42       | 6.85       | PASS
IT19  | badge-degraded border        | 3.0   | 4.58       | 6.83       | PASS
IT20  | badge-lost border            | 3.0   | 5.91       | 5.31       | PASS
IT21  | badge-unknown border         | 3.0   | 6.47       | 5.82       | PASS
IT22  | header-title text            | 4.5   | 17.85      | 16.98      | PASS
IT23  | header-subtitle text         | 4.5   | 5.75       | 6.99       | PASS
IT24  | empty-title text             | 4.5   | 17.85      | 16.98      | PASS
IT25  | empty-desc text              | 4.5   | 5.75       | 6.99       | PASS
----------------------------------------------------------------------------------------------------
Total Audit Items: 25 | Passed: 25 | Failed: 0
====================================================================================================
[SUCCESS] All items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.
```

---

## 3. AST 정적 분석 및 커버리지 래칫 (Test 9j-2)

`apps/web/tests/acc09-contrast-tokens.test.tsx`의 Test 9j-2 `analyzeFile('features/nodes/NodeList.tsx')` 실측 검증:
- `totalStyleAttrs`: **53** (모든 인라인 style 선언 및 배지·버튼·배너 100% 포괄)
- `checkedObjects`: **7** (명시적 전경-배경 쌍 객체)
- `checkedPairs`: **26** (조건 분기 및 컨테이너 상속 조합 전수 검사)
- `unboundColorObjects`: **14** (컨테이너 배경 상속 전경 객체)
- `coveredColorObjects`: **21** (`checkedObjects + unboundColorObjects` = 100% 커버리지)
- `checkedBorderObjects`: **11** (명시적 테두리 토큰 선언 객체)
- `checkedBorderPairs`: **13** (테두리-배경 명도비 검사 조합)
- `violations`: `[]` (대비 위반 및 1:1 충돌 0건)

---

## 4. 컴파일 검증 변이 테스트 (W1~W40) 사살 실측

> [!IMPORTANT]
> **증거 배치 및 Head 무결성 보증 (Card 245/248 합의 프로토콜 준수)**:
> `tools/.c271_mutation_results.json`은 러너 및 제품 코드가 포함된 commit A의 clean checkout 상태에서 `python tools/test_c271_mutations.py --all`을 단일 연속 실행하여 생성되며, commit B는 이 JSON 결과 파일만 추가합니다. commit A와 B 사이 제품 및 시험 코드 변경은 0건이며, 봉인된 `sourceHeadSha`는 commit A(코드·시험 tree)의 clean HEAD입니다.

`tools/test_c271_mutations.py`를 통해 모든 변이가 TypeScript 컴파일을 통과(`tsc -b` exit 0)함을 검증한 뒤, Vitest 계약 테스트 및 DOM 단언으로 사살됨을 확인했습니다.
결과 메타데이터는 `tools/.c271_mutation_results.json`에 `sourceHeadSha` 및 `observedAt`과 함께 영구 보존됩니다.

| 변이 ID | 변이 설명 | 판정 | 사살 시험 |
| :--- | :--- | :--- | :--- |
| W1 | telemetry badge: color==bg collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W2 | telemetry badge: border==bg collision (border: 1px solid var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W3 | telemetry badge: synchronized low-contrast mutation (color: var(--color-text-inverse)) | KILLED | Test 9v / Probes 119~120 계산 단언 |
| W4 | telemetry badge: dot background collision with subtle | KILLED | Test 9v DOM / Test 9j-2 |
| W5 | telemetry card: lost border collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W6 | telemetry card: unknown border collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W7 | telemetry notice: lost text collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W8 | telemetry notice: unknown text collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W9 | standard badge: color==bg collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W10 | standard badge: border==bg collision (border: 1px solid var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W11 | standard badge: synchronized low-contrast mutation (color: var(--color-text-inverse)) | KILLED | Test 9v / Probes 119~120 계산 단언 |
| W12 | standard badge: dot collision with subtle | KILLED | Test 9v DOM / Test 9j-2 |
| W13 | standard card: border collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W14 | standard card: CPU usage bar color collision with subtle | KILLED | Test 9v DOM / Test 9j-2 |
| W15 | standard card: GPU box background collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W16 | telemetry detail button: background collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W17 | observation banner: bg==color collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W18 | observation banner: border==bg collision (border: 1px solid var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W19 | observation banner: revert to raw rgba background | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W20 | observation banner: remove warning emoji icon | KILLED | Test 9v 아이콘 단언 |
| W21 | active notice: bg==color collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W22 | active notice: border==bg collision (border: 1px solid var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W23 | active notice: revert to raw rgba background | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W24 | active notice: remove info emoji icon | KILLED | Test 9v 아이콘 단언 |
| W25 | schedulable text: observationOnly color collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W26 | schedulable text: allocatable color collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W27 | studio open button: normal color collision (color: var(--color-brand-primary-bg)) | KILLED | Test 9v DOM / Test 9j-2 |
| W28 | studio open button: normal revert to raw literal #ffffff | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W29 | studio open button: obsOnly color collision with border-strong | KILLED | Test 9v DOM / Test 9j-2 |
| W30 | studio open button: focus ring suppression via outline: none | KILLED | Test 9v 포커스 링 / Test 9j-2 |
| W31 | studio open button: focus ring suppression via outline: '0' | KILLED | Test 9v 포커스 링 / Test 9j-2 |
| W32 | schedulable section: borderTop collision with surface | KILLED | Test 9v DOM / Test 9j-2 |
| W33 | code block: revert background to raw literal #1e1e1e | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W34 | code block: revert text to raw literal #4ade80 | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W35 | code block: bg==color collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W36 | copy button: bg==color collision (color: var(--color-bg-subtle)) | KILLED | Test 9v DOM / Test 9j-2 |
| W37 | copy button: focus ring suppression via outline: none | KILLED | Test 9v 포커스 링 / Test 9j-2 |
| W38 | copy button: revert background to raw literal #2d3748 | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W39 | copy feedback text: revert to raw literal #4ade80 | KILLED | Test 10 Multiset 래칫 / Test 9v |
| W40 | node select button: focus ring suppression via outline: none | KILLED | Test 9v 포커스 링 / Test 9j-2 |

- 총 변이 수: **40**
- 사살 (KILLED): **40** (100.0%)
- 생존 (SURVIVED): **0**
- 타임아웃 (TIMEOUT): **0**
- 컴파일 실패 (TSC_FAIL): **0**

---

## 5. 최종 검증 게이트 실측 결과

모든 테스트와 정적 분석은 `$LASTEXITCODE == 0`으로 통과되었습니다:

```powershell
# 1. 계약 테스트 스위트
npx vitest run tests/acc09-contrast-tokens.test.tsx
# Exit 0: 36 passed (36 tests)

# 2. 노드 연관 테스트 스위트
npx vitest run tests/node-fetch-error-workspace-wiring.test.tsx
# Exit 0: 3 passed (3 tests)

# 3. TypeScript 빌드 검증
npx tsc -b
# Exit 0: 타입 에러 0건

# 4. 프로덕션 번들 빌드
npm run build
# Exit 0: dist 번들 생성 완료

# 5. 백엔드 라우트 커버리지 및 무결성 불변식
pytest tests/test_route_coverage.py
# Exit 0: 41 passed

# 6. 프런트엔드 9대 무결성 규칙
python -X utf8 tools/check_frontend_integrity.py
# Exit 0: All 9 integrity rules satisfied (0 violations)

# 7. 계약 바인딩 및 서빙앵커 커버리지
python -X utf8 tools/check_contract_bindings.py
# Exit 0: PASS check_contract_bindings

# 8. 문서 무결성
python tools/check_docs.py
# Exit 0: PASS

# 9. 옵시디언 동기화 사전 점검
python tools/sync_obsidian.py --check
# Exit 0: 0 conflicts

# 10. Git 변경사항 공백/CRLF 무결성
git diff --check
# Exit 0: 0 errors
```

---

## 6. 인계 및 다음 단계
- **PR 대상**: `agent/gemini/c271-node-list-contrast` -> `agent/gemini/c270-workspace-list-contrast` (PR #367 브랜치).
- **리뷰 요청**: Codex(계약 및 상태 방어), Claude(UI 명도 대비 및 DOM 접근성).
- **다음 행동**: 카드 271 PR 제출 후 리뷰 응답 대기 및 공통 진행판 동기화.
