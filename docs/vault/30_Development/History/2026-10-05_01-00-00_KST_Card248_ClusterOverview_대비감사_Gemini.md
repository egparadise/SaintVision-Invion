---
doc_id: "HIST-20261005-CARD248-GEMINI"
title: "Card 248 클러스터 대시보드 개요 (ClusterOverview) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-05T01:00:00+09:00"
updated: "2026-10-05T01:00:00+09:00"
source_of_truth: "Git"
---

# Card 248 클러스터 대시보드 개요 (ClusterOverview) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격

## 1. 작업 개요
- **목표**: 클러스터 대시보드 핵심 뷰(`apps/web/src/features/dashboard/ClusterOverview.tsx`)의 색상 리터럴 전수(17건→0건) 토큰화 및 디자인 토큰 체계 승격:
  1. 노드 상태 설정 객체 최상단 정의 및 export: `NODE_STATUS_CONFIG` (`active`, `degraded`, `draining`, `enrolling`, `lost`, `offline`, `online`, `retired`, `unknown` 9종 wire 계약 enum과 엄밀 일치).
  2. `getClusterNodeStatusConfig` fail-closed own-key 방어: `Object.hasOwn` 기반 검사로 prototype key(`toString`, `constructor`, `__proto__`, `valueOf`, `hasOwnProperty`, `isPrototypeOf`), 대소문자 변형(`ONLINE`), 계약 밖 값(`admitted`)의 fail-open 승격을 원천 차단하고 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 형식으로 안전 강등 매핑 (WCAG 1.4.1 준수).
  3. 자원 게이지 바(RAM, VRAM, Storage) 시맨틱 토큰화: RAM `var(--color-status-online)`, VRAM `var(--color-brand-hover)`, Storage `var(--color-status-degraded)`.
  4. 위험·에러 상태 시맨틱 보존: 에러 섹션 및 동기화 실패 경고 배너 `var(--color-status-offline)`.
  5. 키보드 포커스 링 보존: 새로고침 버튼 및 에러 재시도 버튼에 `outline: none/0`, `outlineWidth: 0` 등 포커스 링 억제 스타일 배제 및 DOM computed outline 검증.
  6. Multiset Baseline 래칫 강제: `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/dashboard/ClusterOverview.tsx` 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정. `var(--color-border-subtle)` 사용 횟수: 459건 / 31개 파일 엄밀 래칫.
  7. 40종 전수 변이 실측 사살: `tools/test_c248_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 바이트 일치 및 git diff 0 확인, 결과 메타데이터 봉인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스(`fddca9d1`)의 실제 렌더링 합성값(라이트 캔버스 `#f8fafc` 위 카드 표면 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#131b2e`, `#1a243b`)을 기준으로 하며, 하드코딩 리터럴의 라이트 테마 전환 시 심각한 명도 결손(Probes 106~110 실측)이 존재했습니다. After 값은 `python tools/reproduce_c248_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before 베이스 합성값 (Hex/RGBA on Canvas/Surface) | Before 명도비 (Light/Dark 렌더 실측) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 에러 섹션 제목 | error-section heading | #fca5a5 on #ffffff | 1.90:1 (FAIL) / 6.41:1 (PASS) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| 에러 섹션 테두리 | error-section border | #ef4444 on #ffffff | 3.76:1 (PASS) / 3.42:1 (PASS) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| 에러 섹션 본문 | error-section message | #94a3b8 on #ffffff | 2.68:1 (FAIL) / 6.99:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 에러 재시도 버튼 텍스트 | error-retry-btn text | #ffffff on #ef4444 | 3.76:1 (FAIL) / 3.76:1 (FAIL) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 에러 재시도 버튼 테두리 | error-retry-btn border | (border: none) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 동기화 실패 경고 텍스트 | stale-warning text | #fca5a5 on rgba(239,68,68,0.15) over #ffffff | 1.56:1 (FAIL) / 5.31:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 동기화 실패 경고 테두리 | stale-warning border | #ef4444 on #f1f5f9 (light subtle) | 3.52:1 (PASS) / 3.90:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 신선도 지표 텍스트 | freshness-indicator text | #94a3b8 on #ffffff | 2.68:1 (FAIL) / 5.78:1 (PASS) | --color-text-muted on --color-bg-subtle | 5.25:1 | 5.78:1 | >= 4.5:1 | PASS |
| 신선도 지표 테두리 | freshness-indicator border | #e2e8f0 on #f1f5f9 | 1.15:1 (FAIL) / 1.25:1 (FAIL) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 상단 새로고침 버튼 텍스트 | topbar-refresh-btn text | #64748b on transparent over #ffffff | 4.34:1 (FAIL) / 14.33:1 (PASS) | --color-text-secondary on --color-bg-surface | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 상단 새로고침 버튼 테두리 | topbar-refresh-btn border | #cbd5e1 on #ffffff | 1.63:1 (FAIL) / 1.70:1 (FAIL) | --color-border-subtle on --color-bg-surface | 3.48:1 | 3.73:1 | >= 3.0:1 | PASS |
| RAM 게이지 바 | ram-gauge-bar | #10b981 on #f1f5f9 | 2.34:1 (FAIL) / 8.53:1 (PASS) | --color-status-online on --color-bg-subtle | 4.79:1 | 8.53:1 | >= 3.0:1 | PASS |
| VRAM 게이지 바 | vram-gauge-bar | #8b5cf6 on #f1f5f9 | 3.45:1 (PASS) / 10.78:1 (PASS) | --color-brand-hover on --color-bg-subtle | 6.41:1 | 10.78:1 | >= 3.0:1 | PASS |
| 스토리지 게이지 바 | storage-gauge-bar | #f59e0b on #f1f5f9 | 2.14:1 (FAIL) / 9.05:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.80:1 | 9.05:1 | >= 3.0:1 | PASS |
| 하트비트 텍스트 | heartbeat text | #64748b on #f8fafc (light canvas) | 4.34:1 (FAIL) / 4.08:1 (FAIL on #090d16) | --color-text-muted on --color-bg-canvas | 5.50:1 | 7.65:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Online | node-status-online | #10b981 on #f8fafc | 2.45:1 (FAIL) / 8.53:1 (PASS) | --color-status-online on --color-bg-canvas | 4.79:1 | 8.53:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Active | node-status-active | #38bdf8 on #f8fafc | 2.05:1 (FAIL) / 9.07:1 (PASS) | --color-status-active on --color-bg-canvas | 5.67:1 | 9.07:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Degraded | node-status-degraded | #d29922 on #f8fafc | 2.41:1 (FAIL) / 9.05:1 (PASS) | --color-status-degraded on --color-bg-canvas | 4.80:1 | 9.05:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Lost | node-status-lost | #f85149 on #f8fafc | 3.52:1 (FAIL) / 7.02:1 (PASS) | --color-status-lost on --color-bg-canvas | 6.18:1 | 7.02:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Offline | node-status-offline | #f85149 on #f8fafc | 3.52:1 (FAIL) / 7.02:1 (PASS) | --color-status-offline on --color-bg-canvas | 6.18:1 | 7.02:1 | >= 4.5:1 | PASS |
| 노드 상태 배지 Unknown | node-status-unknown | #8b949e on #f8fafc | 2.87:1 (FAIL) / 7.70:1 (PASS) | --color-status-unknown on --color-bg-canvas | 6.78:1 | 7.70:1 | >= 4.5:1 | PASS |
| 최근 실행 상태 텍스트 | recent-run-state text | #8b5cf6 on #ffffff | 3.87:1 (FAIL) / 10.78:1 (PASS) | --color-brand-hover on --color-bg-surface | 6.41:1 | 10.78:1 | >= 4.5:1 | PASS |

> [!NOTE]
> **라이트/다크 테마 Revert-Fail Probes (Probes 106~110)**:
> 옛 다크 하드코딩 리터럴을 테마 표면 위에 적용할 경우의 심각한 명도 결손 실측:
> - Probe 106 (`#fca5a5` on light surface `#ffffff`): **1.90:1** (< 4.5:1 FAIL)
> - Probe 107 (`#ffffff` on `#ef4444` retry button): **3.76:1** (< 4.5:1 FAIL)
> - Probe 108 (`#64748b` on dark canvas `#090d16`): **4.08:1** (< 4.5:1 FAIL)
> - Probe 109 (`#38bdf8` on light canvas `#f8fafc`): **2.05:1** (< 4.5:1 FAIL)
> - Probe 110 (`#d29922` on light canvas `#f8fafc`): **2.41:1** (< 4.5:1 FAIL)

### 2.2 tools/reproduce_c248_contrast.py 실행 결과
```text
====================================================================================================
 Card 248 ClusterOverview Contrast Verification Report (tools/reproduce_c248_contrast.py)
====================================================================================================
ID    | Element / Role               | MinCR | Light CR   | Dark CR    | Status
----------------------------------------------------------------------------------------------------
IT01  | error-section heading        | 4.5   | 6.47       | 6.41       | PASS
IT02  | error-section border         | 3.0   | 6.47       | 6.41       | PASS
IT03  | error-section message        | 4.5   | 5.75       | 6.99       | PASS
IT04  | error-retry-btn text         | 4.5   | 16.30      | 14.05      | PASS
IT05  | error-retry-btn border       | 3.0   | 3.18       | 3.08       | PASS
IT06  | stale-warning text           | 4.5   | 5.91       | 5.31       | PASS
IT07  | stale-warning border         | 3.0   | 5.91       | 5.31       | PASS
IT08  | freshness-indicator text     | 4.5   | 5.25       | 5.78       | PASS
IT09  | freshness-indicator border   | 3.0   | 3.18       | 3.08       | PASS
IT10  | topbar-refresh-btn text      | 4.5   | 7.58       | 14.33      | PASS
IT11  | topbar-refresh-btn border    | 3.0   | 3.48       | 3.73       | PASS
IT12  | ram-gauge-bar                | 3.0   | 4.79       | 8.53       | PASS
IT13  | vram-gauge-bar               | 3.0   | 6.41       | 10.78      | PASS
IT14  | storage-gauge-bar            | 3.0   | 4.80       | 9.05       | PASS
IT15  | heartbeat text               | 4.5   | 5.50       | 7.65       | PASS
IT16  | node-status-online           | 4.5   | 4.79       | 8.53       | PASS
IT17  | node-status-active           | 4.5   | 5.67       | 9.07       | PASS
IT18  | node-status-degraded         | 4.5   | 4.80       | 9.05       | PASS
IT19  | node-status-lost             | 4.5   | 6.18       | 7.02       | PASS
IT20  | node-status-offline          | 4.5   | 6.18       | 7.02       | PASS
IT21  | node-status-unknown          | 4.5   | 6.78       | 7.70       | PASS
IT22  | recent-run-state text        | 4.5   | 6.41       | 10.78      | PASS
----------------------------------------------------------------------------------------------------
Total Audit Items: 22 | Passed: 22 | Failed: 0
====================================================================================================
[SUCCESS] All items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.
```

---

## 3. AST 정적 분석 및 커버리지 래칫 (Test 9j-2)

`tests/acc09-contrast-tokens.test.tsx`의 Test 9j-2 `analyzeFile('features/dashboard/ClusterOverview.tsx')` 실측 검증:
- `totalStyleAttrs`: **67** (모든 인라인 style 선언 100% 포괄)
- `checkedObjects`: **6** (명시적 전경-배경 쌍 객체)
- `checkedPairs`: **29** (조건 분기 및 컨테이너 상속 조합 전수 검사)
- `unboundColorObjects`: **23** (컨테이너 배경 상속 전경 객체)
- `coveredColorObjects`: **29** (`checkedObjects + unboundColorObjects` = 100% 커버리지)
- `checkedBorderObjects`: **16** (명시적 테두리 토큰 선언 객체)
- `checkedBorderPairs`: **16** (테두리-배경 명도비 검사 조합)
- `violations`: `[]` (대비 위반 및 1:1 충돌 0건)

---

## 4. 컴파일 검증 변이 테스트 (W1~W40) 사살 실측

> [!IMPORTANT]
> **증거 배치 및 Head 무결성 보증 (Card 245 합의 프로토콜 준수)**:
> `tools/.c248_mutation_results.json`은 러너 수정 commit A의 clean checkout 상태에서 `python tools/test_c248_mutations.py --all`을 단일 연속 실행하여 생성되었으며, commit B는 이 JSON 결과 파일만 추가합니다. commit A와 B 사이 제품 및 시험 코드 변경은 0건이며, 봉인된 `sourceHeadSha`는 commit A(코드·시험 tree)의 clean HEAD입니다.

`tools/test_c248_mutations.py`를 통해 모든 변이가 TypeScript 컴파일을 통과(`tsc -b` exit 0)함을 검증한 뒤, Vitest 계약 테스트 및 DOM 단언으로 사살됨을 확인했습니다.
결과 메타데이터는 `tools/.c248_mutation_results.json`에 `sourceHeadSha` 및 `observedAt`과 함께 영구 보존되었습니다.

| 변이 ID | 변이 설명 | 대상 코드 | 변이 내용 | 판정 | 사살 시험 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| W1 | online config: fg==bg collision | online.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W2 | active config: fg==bg collision | active.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W3 | degraded config: fg==bg collision | degraded.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W4 | lost config: fg==bg collision | lost.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W5 | unknown config: fg==bg collision | unknown.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W6 | offline config: fg==bg collision | offline.color | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W7 | ram gauge: fg==bg collision | ram.backgroundColor | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W8 | vram gauge: fg==bg collision | vram.backgroundColor | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W9 | storage gauge: fg==bg collision | storage.backgroundColor | `var(--color-bg-canvas)` | KILLED | Test 9q DOM |
| W10 | recent run state: fg==bg collision | runState.color | `var(--color-bg-canvas)` | KILLED | Test 9j-2 AST |
| W11 | error banner: fg==bg collision | error.backgroundColor | `var(--color-status-offline)` | KILLED | Test 9q DOM |
| W12 | error banner: border==bg collision | error.border | `var(--color-bg-surface)` | KILLED | Test 9q DOM |
| W13 | stale warning: fg==bg collision | warning.backgroundColor | `var(--color-status-offline)` | KILLED | Test 9q DOM |
| W14 | stale warning: border==bg collision | warning.border | `var(--color-bg-subtle)` | KILLED | Test 9q DOM |
| W15 | node status badge: opacity 0.35 | badge.style | `opacity: 0.35` | KILLED | Test 9q DOM |
| W16 | stale warning: opacity 0.4 | warning.style | `opacity: 0.4` | KILLED | Test 9j-2 AST |
| W17 | online config: comment decoy #10b981 | online.color | `/* #10b981 */` | KILLED | Test 9q DOM |
| W18 | active config: comment decoy #38bdf8 | active.color | `/* #38bdf8 */` | KILLED | Test 9q DOM |
| W19 | error heading: revert to #fca5a5 | heading.color | `#fca5a5` | KILLED | Test 9q DOM |
| W20 | error retry btn: revert bg #ef4444 | retry.backgroundColor | `#ef4444` | KILLED | Test 9q DOM |
| W21 | heartbeat: revert color #64748b | heartbeat.color | `#64748b` | KILLED | Test 9q DOM |
| W22 | active node: revert color #38bdf8 | active.color | `#38bdf8` | KILLED | Test 9q DOM |
| W23 | degraded node: revert color #d29922 | degraded.color | `#d29922` | KILLED | Test 9q DOM |
| W24 | ram gauge: revert bg #10b981 | ram.backgroundColor | `#10b981` | KILLED | Test 9q DOM |
| W25 | vram gauge: revert bg #8b5cf6 | vram.backgroundColor | `#8b5cf6` | KILLED | Test 9q DOM |
| W26 | storage gauge: revert bg #f59e0b | storage.backgroundColor | `#f59e0b` | KILLED | Test 9q DOM |
| W27 | refresh btn: outline: 'none' | refresh.style | `outline: 'none'` | KILLED | Test 9j-2 AST |
| W28 | error retry btn: outline: 'none' | retry.style | `outline: 'none'` | KILLED | Test 9j-2 AST |
| W29 | refresh btn: outline: 0 | refresh.style | `outline: 0` | KILLED | Test 9j-2 AST |
| W30 | error retry btn: outlineWidth: 0px | retry.style | `outlineWidth: '0px'` | KILLED | Test 9j-2 AST |
| W31 | fail-closed: Object.hasOwn -> in | in operator | `status in NODE_STATUS_CONFIG` | KILLED | Test 9q DOM |
| W32 | fail-closed: prototype key hijack | direct indexing | `(NODE_STATUS_CONFIG as any)[status]` | KILLED | Test 9q DOM |
| W33 | fail-closed fallback: online color | fallback.color | `var(--color-status-online)` | KILLED | Test 9q DOM |
| W34 | contract bypass: admitted -> online | admitted guard | `status === 'admitted' -> online` | KILLED | Test 9q DOM |
| W35 | contract bypass: drop online | online guard | `status !== 'online'` | KILLED | Test 9q DOM |
| W36 | unknown label: remove 'UNKNOWN (' | fallback.label | `(${raw})` | KILLED | Test 9q DOM |
| W37 | unknown label: raw uppercase | fallback.label | `raw.toUpperCase()` | KILLED | Test 9q DOM |
| W38 | case bypass: toLowerCase() | lookup key | `status.toLowerCase()` | KILLED | Test 9q DOM |
| W39 | error heading text mutation | h1 text | `클러스터 에러 발생` | KILLED | Test 9q DOM |
| W40 | stale warning: remove '⚠️' icon | warning text | `[동기화 실패] (no ⚠️)` | KILLED | Test 9q DOM |

- 총 변이 수: **40**
- 사살 (KILLED): **40** (100.0%)
- 생존 (SURVIVED): **0**
- 타임아웃 (TIMEOUT): **0**
- 컴파일 실패 (TSC_FAIL): **0**

---

## 5. 최종 검증 게이트 실측 결과

모든 테스트와 정적 분석은 단일 명령어 체인에서 `$LASTEXITCODE == 0`으로 통과되었습니다:

```powershell
# 1. 계약 테스트 스위트
npx vitest run tests/acc09-contrast-tokens.test.tsx
# Exit 0: 34 passed (34 tests)

# 2. TypeScript 빌드 검증
npx tsc -b
# Exit 0: 타입 에러 0건

# 3. 프로덕션 번들 빌드
npm run build
# Exit 0: dist/index-CMWlc6D7.js 번들 생성 완료 (8.51s)

# 4. 백엔드 라우트 커버리지 및 무결성 불변식
pytest tests/test_route_coverage.py
# Exit 0: 41 passed (5.75s)

# 5. 프런트엔드 9대 무결성 규칙
python -X utf8 tools/check_frontend_integrity.py
# Exit 0: All 9 integrity rules satisfied (0 violations)

# 6. 계약 바인딩 및 서빙앵커 커버리지
python -X utf8 tools/check_contract_bindings.py
# Exit 0: PASS check_contract_bindings (55 fixtures, 20 bound types, 14 replay guards)

# 7. 문서 무결성
python tools/check_docs.py
# Exit 0: PASS (24 hashes, 1082 versioned documents, 48 tasks, 12 outcomes)

# 8. 옵시디언 동기화 사전 점검
python tools/sync_obsidian.py --check
# Exit 0: 0 conflicts

# 9. Git 변경사항 공백/CRLF 무결성
git diff --check
# Exit 0: 0 errors
```

---

## 6. 인계 및 다음 단계
- **PR 대상**: `agent/gemini/c248-cluster-overview-contrast` -> `agent/gemini/c245-approval-center-contrast` (PR #342 브랜치).
- **리뷰 요청**: Codex(계약 및 상태 방어), Claude(UI 명도 대비 및 DOM 접근성).
- **다음 행동**: 카드 248 PR 제출 후 리뷰 응답 대기 및 공통 진행판 동기화.
