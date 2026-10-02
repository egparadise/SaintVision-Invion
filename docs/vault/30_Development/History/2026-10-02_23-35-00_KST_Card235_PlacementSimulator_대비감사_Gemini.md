# 2026-10-02 23:35:00 KST — Card 235 [r2]: 배치 시뮬레이터 (PlacementSimulator) 색상 리터럴 전수 토큰화(28줄 33건→0), 상태 색 정합성 및 접근성 승격 (PR #340)

## 1. 개요 및 변경 목적
- **작업 ID**: Card 235 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory) [r2]
- **대상 화면**: `apps/web/src/features/placement/PlacementSimulator.tsx`
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: `agent/gemini/c235-placement-contrast`
- **기반 커밋 (Base)**: `81e9851b` (PR #328 head merge 후 실제 base)
- **PR 대상 (Target)**: `agent/gemini/c230-desktop-shell-contrast`
- **PR 번호**: PR #340
- **KST 시각**: 2026-10-02 23:35:00 KST (r2 갱신: 2026-10-03 02:10:00 KST)

### 1.1 주요 작업 내역
1. **색상 리터럴 전수 해소 (28줄 33 occurrences -> 0건, 100% 토큰화)**:
   - `apps/web/src/features/placement/PlacementSimulator.tsx`: 베이스(`81e9851b`)에 존재하던 총 28줄 33건의 하드코딩 색상 리터럴(Hex 24건, RGBA 9건; `#334155:3, #93c5fd:1, #94a3b8:2, #ef4444:4, #f87171:1, #fbbf24:4, #fca5a5:4, #fff:3, #ffffff:2` + rgba 2/2/4/1) 전수를 `apps/web/src/index.css` 정본 디자인 토큰(`var(--color-...)`)으로 100% 치환.
   - 로컬 시뮬레이션 배지(`local-simulation-badge`), 풀 목록 로딩/에러/재시도 버튼(`pools-error-banner`, `pools-retry-btn`), 풀 선택 버튼(`pool-btn-*`), 풀 자원 초과 경고 텍스트(`pool-capacity-error`), 자원 디스커버리 미검증 풀 배지(`unverified-badge`), GPU 요구 토글 버튼(`gpu-btn-*`), 서버 설명 안내 배너, 샤드 배치 미리보기 로딩/에러/재시도 버튼(`preview-error-banner`, `preview-retry-btn`), 디스커버리 후보 목록 로딩/에러/재시도 버튼(`candidates-error-banner`, `candidates-retry-btn`), 후보 목록 빈 상태 운영자 안내 링크, 디스커버리 후보 상태 배지 전수 토큰화.
2. **Wire 계약 Enum 일치 및 디스커버리 후보 상태 객체 정립**:
   - `DiscoveryCandidate['state']` wire 계약과 `DISCOVERY_CANDIDATE_STATE_CONFIG`의 key set을 100% 일치: `candidate` 단일 유효 상태로 한정.
   - `expect(Object.keys(DISCOVERY_CANDIDATE_STATE_CONFIG).sort()).toEqual(['candidate'])` 계약 일치 불변식 고정.
   - `getDiscoveryCandidateStateConfig`: `Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state)` 기반 own-key 검사를 적용하여 계약 외 임의 상태(`admitted`, `rejected`, `active`, `pending`), 대소문자 변형(`CANDIDATE`, `Candidate`), prototype key(`toString`, `constructor`, `__proto__`) 및 null/''/undefined 입력 시 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 대문자 접두어 형식(빈값은 `UNKNOWN`)으로 fail-closed 격리 단언 (WCAG 1.4.1 준수).
3. **AST 가드 (Test 9j-2) PlacementSimulator 등록 및 엄밀 래칫**:
   - `apps/web/tests/acc09-contrast-tokens.test.tsx`의 Test 9j-2 정적 AST 검사기에 `PlacementSimulator.tsx` 정합 등록.
   - AST 커버리지 래칫:
     - `totalStyleAttrs`: 78
     - `checkedObjects`: 16
     - `checkedPairs`: 41
     - `unboundColorObjects`: 23
     - `coveredColorObjects`: 39
     - `checkedBorderObjects`: 21
     - `checkedBorderPairs`: 23
     - `violations`: [] (0건, 클린 패스)
4. **키보드 접근성 및 포커스 링 보존**:
   - 풀 선택 버튼, GPU 토글 버튼, 재시도 버튼 등 모든 인터랙티브 요소에서 인라인 `outline: none`, `outline: 0`, `outlineWidth: 0` 억제를 일체 배제하고 `apps/web/src/index.css` 전역 `:focus-visible` 키보드 포커스 링 스타일 온전 보존.
   - retry button, GPU button 및 pool button의 computed `outline !== 'none'`, `outlineWidth !== '0px'` 검증 및 AST 가드 연동.
5. **Fail-Closed Multiset Baseline 래칫 강제**:
   - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/placement/PlacementSimulator.tsx`의 허용 리터럴 인벤토리를 `{}` (0건)으로 전면 래칫 고정.
   - `var(--color-border-subtle)` 사용 횟수: 451건/31개 파일 -> **456건/31개 파일**로 엄밀 래칫 갱신.
6. **위험 배너 3곳 DOM 전경/배경/테두리/아이콘/텍스트 전수 단언 (Test 9o r2 보강)**:
   - `preview-error-banner`: `var(--color-status-offline)`, subtle 배경, `⚠️` 경고 아이콘, `서버 배치 미리보기 실패` 제목 단언.
   - `pool-capacity-error`: `var(--color-status-offline)`, subtle 배경/테두리, `⚠️` 경고 아이콘, `실시간 용량 초과 경고` 텍스트 단언 (Claude 변이 C07 사살).
   - `pools-error-banner` 및 `candidates-error-banner`: `var(--color-status-offline)`, subtle 배경/테두리, `⚠️` 경고 아이콘, 헤딩/내용, 재시도 버튼 토큰 및 computed outline 단언 (Claude 변이 C08, C09 사살).
7. **40종 전수 변이 실측 사살 (tools/test_c235_mutations.py Z1~Z40 100% 사살)**:
   - fg==bg 충돌, border==bg 충돌, text token as bg, 불투명도 저하, 주석 decoy, 토큰 되돌림, 상태 색 붕괴, 라벨/아이콘 변형, outline: none/0 억제, prototype key 탈취, 계약 외 값 주입, 명명 색상 주입, UNKNOWN 접두어 제거, raw bypass, case-insensitive lookup 등 40종 변이를 컴파일 가능한 단일 유효 코드로 작성하여 전원 사살 실측.
   - Z32 (`state === 'toString'` prototype key) 및 Z31~Z40 순차 실행 100% 사살 실측 (Codex F-R1 해소).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스(`81e9851b`)의 실제 조상 JSX 체인과 정본 디자인 토큰(`index.css`: Light surface `#ffffff`, subtle `#f1f5f9`, canvas `#f8fafc` / Dark surface `#111827`, subtle `#1f2937`, canvas `#090d16`) 기준 렌더링 합성값입니다. 베이스의 하드코딩 리터럴은 다크 테마에서 일부 우연히 대비를 통과했으나, **라이트 테마 전환 시 35개 지표 중 13개 이상이 심각한 결손(Probes 96~100 실측)**을 보였습니다. After 값은 `python tools/reproduce_c235_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before 베이스 합성값 (Hex/RGBA on Canvas/Surface) | Before 명도비 (Light) | Before 명도비 (Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 로컬 시뮬 배지 텍스트 | local-sim-badge text | #fbbf24 on rgba(234,179,8,0.15) over canvas | 1.45:1 (FAIL) | 9.05:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 로컬 시뮬 배지 테두리 | local-sim-badge border | rgba(234,179,8,0.3) on canvas | 1.20:1 (FAIL) | 1.88:1 (FAIL) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 3.0:1 | PASS |
| 풀 에러 배너 제목 | pools-error title | #fca5a5 on rgba(239,68,68,0.1) over canvas | 1.60:1 (FAIL) | 9.51:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 풀 에러 배너 테두리 | pools-error border | #ef4444 on canvas | 3.60:1 (PASS) | 5.16:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 풀 재시도 버튼 텍스트 | pools-retry-btn text | #ffffff on #334155 | 10.35:1 (PASS) | 10.35:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 풀 재시도 버튼 테두리 | pools-retry-btn border | (border: none in base) | N/A (경계 미식별) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 선택된 풀 버튼 텍스트 | pool-btn-selected text | #ffffff on brand-primary-bg | 5.17:1 (PASS) | 6.70:1 (PASS) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 4.5:1 | PASS |
| 선택된 풀 버튼 테두리 | pool-btn-selected border | var(--color-border-strong) on brand-primary-bg | 2.02:1 (FAIL) | 1.13:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 비선택 풀 버튼 텍스트 | pool-btn-unselected text | var(--color-text-secondary) on subtle | 6.92:1 (PASS) | 5.72:1 (PASS) | --color-text-secondary on --color-bg-subtle | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 비선택 풀 버튼 테두리 | pool-btn-unselected border | var(--color-border-strong) on subtle | 2.34:1 (FAIL) | 1.94:1 (FAIL) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 풀 용량 초과 텍스트 | pool-capacity-error text | #fca5a5 on rgba(239,68,68,0.1) over surface | 1.66:1 (FAIL) | 8.61:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 풀 용량 초과 테두리 | pool-capacity-error border | #ef4444 on rgba(239,68,68,0.1) over surface | 3.29:1 (PASS) | 4.34:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 디스커버리 미검증 풀 배지 | pools-idle-unverified text | #fbbf24 on subtle | 1.52:1 (FAIL) | 8.79:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 폴백 미검증 풀 배지 | pools-fallback-unverified text | #fbbf24 on subtle | 1.52:1 (FAIL) | 8.79:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 활성 GPU 버튼 텍스트 | gpu-btn-active text | #ffffff on brand-primary-bg | 5.17:1 (PASS) | 6.70:1 (PASS) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 4.5:1 | PASS |
| 활성 GPU 버튼 테두리 | gpu-btn-active border | var(--color-border-strong) on brand-primary-bg | 2.02:1 (FAIL) | 1.13:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 비활성 GPU 버튼 텍스트 | gpu-btn-inactive text | var(--color-text-secondary) on subtle | 6.92:1 (PASS) | 5.72:1 (PASS) | --color-text-secondary on --color-bg-subtle | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 비활성 GPU 버튼 테두리 | gpu-btn-inactive border | var(--color-border-strong) on subtle | 2.34:1 (FAIL) | 1.94:1 (FAIL) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 서버 설명 안내 텍스트 | server-explanation text | var(--color-text-primary) on rgba(35,134,54,0.1) | 15.71:1 (PASS) | 15.45:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 서버 설명 안내 테두리 | server-explanation border | var(--color-success) on rgba(35,134,54,0.1) | 4.08:1 (PASS) | 6.37:1 (PASS) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| 미리보기 로딩 텍스트 | preview-loading text | #94a3b8 on surface | 2.56:1 (FAIL) | 6.92:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 미리보기 에러 배너 텍스트 | preview-error text | #fca5a5 on rgba(239,68,68,0.1) over canvas | 1.60:1 (FAIL) | 9.51:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 미리보기 에러 보조문구 | preview-error subtext | #f87171 on rgba(239,68,68,0.1) over canvas | 2.33:1 (FAIL) | 6.52:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 미리보기 에러 테두리 | preview-error border | #ef4444 on canvas | 3.60:1 (PASS) | 5.16:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 미리보기 재시도 버튼 텍스트 | preview-retry-btn text | #ffffff on #334155 | 10.35:1 (PASS) | 10.35:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 미리보기 재시도 버튼 테두리 | preview-retry-btn border | (border: none in base) | N/A (경계 미식별) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 후보 목록 로딩 텍스트 | candidates-loading text | #94a3b8 on surface | 2.56:1 (FAIL) | 6.92:1 (PASS) | --color-text-muted on --color-bg-surface | 5.75:1 | 6.99:1 | >= 4.5:1 | PASS |
| 후보 목록 에러 배너 텍스트 | candidates-error text | #fca5a5 on rgba(239,68,68,0.1) over canvas | 1.60:1 (FAIL) | 9.51:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 후보 목록 에러 테두리 | candidates-error border | #ef4444 on canvas | 3.60:1 (PASS) | 5.16:1 (PASS) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 후보 재시도 버튼 텍스트 | candidates-retry-btn text | #ffffff on #334155 | 10.35:1 (PASS) | 10.35:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 후보 재시도 버튼 테두리 | candidates-retry-btn border | (border: none in base) | N/A (경계 미식별) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 후보 목록 빈 상태 안내문구 | candidates-empty note | #93c5fd on surface | 1.80:1 (FAIL) | 9.84:1 (PASS) | --color-brand-hover on --color-bg-surface | 6.70:1 | 9.84:1 | >= 4.5:1 | PASS |
| 후보 상태 배지 텍스트 | candidate-status text | #fbbf24 on rgba(234,179,8,0.15) over surface | 1.52:1 (FAIL) | 8.04:1 (PASS) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 후보 상태 배지 테두리 | candidate-status border | rgba(234,179,8,0.3) on surface | 1.22:1 (FAIL) | 1.90:1 (FAIL) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 3.0:1 | PASS |
| 미지 후보 상태 배지 텍스트 | candidate-unknown text | (베이스 미구현, 미토큰화) | N/A (FAIL) | N/A (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |

> [!NOTE]
> **라이트 테마 Revert-Fail Probes (Probes 96~100)**:
> 옛 베이스 하드코딩 리터럴을 라이트 테마 조상 표면 위에 적용할 경우의 심각한 명도 결손 실측치(시험 `apps/web/tests/acc09-contrast-tokens.test.tsx:7181-7206`과 100% 일치):
> - Probe 96 (`#fbbf24` on light canvas `#f8fafc`): **1.60:1** (< 4.5:1 FAIL)
> - Probe 97 (`#fca5a5` on light canvas `#f8fafc`): **1.81:1** (< 4.5:1 FAIL)
> - Probe 98 (`#f87171` on light canvas `#f8fafc`): **2.64:1** (< 4.5:1 FAIL)
> - Probe 99 (unverified badge border `rgba(234, 179, 8, 0.3)` on light canvas `#f8fafc`): **1.20:1** (< 3.0:1 FAIL)
> - Probe 100 (operator note `#93c5fd` on light surface `#ffffff`): **1.80:1** (< 4.5:1 FAIL)

### 2.2 tools/reproduce_c235_contrast.py 실행 결과
```text
====================================================================================================
 Card 235 PlacementSimulator Contrast Verification Report (tools/reproduce_c235_contrast.py)
====================================================================================================
ID    | Element / Role               | MinCR | Light CR   | Dark CR    | Status
----------------------------------------------------------------------------------------------------
IT01  | local-sim-badge text         | 4.5   | 4.58       | 6.83       | PASS  
IT02  | local-sim-badge border       | 3.0   | 4.58       | 6.83       | PASS  
IT03  | pools-error title            | 4.5   | 5.91       | 5.31       | PASS  
IT04  | pools-error border           | 3.0   | 5.91       | 5.31       | PASS  
IT05  | pools-retry-btn text         | 4.5   | 16.30      | 14.05      | PASS  
IT06  | pools-retry-btn border       | 3.0   | 3.18       | 3.08       | PASS  
IT07  | pool-btn-selected text       | 4.5   | 5.49       | 8.11       | PASS  
IT08  | pool-btn-selected border     | 3.0   | 5.49       | 8.11       | PASS  
IT09  | pool-btn-unselected text     | 4.5   | 6.92       | 11.86      | PASS  
IT10  | pool-btn-unselected border   | 3.0   | 3.18       | 3.08       | PASS  
IT11  | pool-capacity-error text     | 4.5   | 5.91       | 5.31       | PASS  
IT12  | pool-capacity-error border   | 3.0   | 5.91       | 5.31       | PASS  
IT13  | pools-idle-unverified text   | 4.5   | 4.58       | 6.83       | PASS  
IT14  | pools-fallback-unverified text | 4.5   | 4.58       | 6.83       | PASS  
IT15  | gpu-btn-active text          | 4.5   | 5.49       | 8.11       | PASS  
IT16  | gpu-btn-active border        | 3.0   | 5.49       | 8.11       | PASS  
IT17  | gpu-btn-inactive text        | 4.5   | 6.92       | 11.86      | PASS  
IT18  | gpu-btn-inactive border      | 3.0   | 3.18       | 3.08       | PASS  
IT19  | server-explanation text      | 4.5   | 16.30      | 14.05      | PASS  
IT20  | server-explanation border    | 3.0   | 4.58       | 6.44       | PASS  
IT21  | preview-loading text         | 4.5   | 5.75       | 6.99       | PASS  
IT22  | preview-error text           | 4.5   | 5.91       | 5.31       | PASS  
IT23  | preview-error subtext        | 4.5   | 5.91       | 5.31       | PASS  
IT24  | preview-error border         | 3.0   | 5.91       | 5.31       | PASS  
IT25  | preview-retry-btn text       | 4.5   | 16.30      | 14.05      | PASS  
IT26  | preview-retry-btn border     | 3.0   | 3.18       | 3.08       | PASS  
IT27  | candidates-loading text      | 4.5   | 5.75       | 6.99       | PASS  
IT28  | candidates-error text        | 4.5   | 5.91       | 5.31       | PASS  
IT29  | candidates-error border      | 3.0   | 5.91       | 5.31       | PASS  
IT30  | candidates-retry-btn text    | 4.5   | 16.30      | 14.05      | PASS  
IT31  | candidates-retry-btn border  | 3.0   | 3.18       | 3.08       | PASS  
IT32  | candidates-empty note        | 4.5   | 6.70       | 9.84       | PASS  
IT33  | candidate-status text        | 4.5   | 4.58       | 6.83       | PASS  
IT34  | candidate-status border      | 3.0   | 4.58       | 6.83       | PASS  
IT35  | candidate-unknown text       | 4.5   | 6.47       | 5.82       | PASS  
----------------------------------------------------------------------------------------------------
Total Audit Items: 35 | Passed: 35 | Failed: 0
====================================================================================================
```

---

## 3. 검증 결과 요약

### 3.1 로컬 검증 실행 기록
1. `npx vitest run tests/acc09-contrast-tokens.test.tsx`:
   - 결과: **32 passed** (100% 통과, 0 failed, Test 9o 위험 배너/아이콘/포커스링 단언 및 Test 9j-2 AST 커버리지 래칫 통과)
2. `npx vitest run tests/placement-simulator.test.tsx tests/placement-explain.test.ts tests/pool-placement-response-contract.test.ts`:
   - 결과: **27 passed** (100% 통과)
3. `npx tsc -b`:
   - 결과: exit code 0 (타입 에러 0건)
4. `npm run build`:
   - 결과: exit code 0 (프로덕션 번들 빌드 성공)
5. `pytest tests/test_route_coverage.py`:
   - 결과: **41 passed** (화면-백엔드 라우트 및 불변식 100% 통과)
6. `python -X utf8 tools/check_frontend_integrity.py`:
   - 결과: 0 violations (프런트엔드 9대 무결성 통과)
7. `python -X utf8 tools/check_contract_bindings.py`:
   - 결과: PASS (계약 바인딩 게이트 통과)
8. `python tools/check_docs.py`:
   - 결과: PASS (문서 정본 게이트 통과)
9. `python tools/sync_obsidian.py --check`:
   - 결과: 0 conflicts, 0 differences (동기화 정합)
10. `git diff --check`:
    - 결과: 클린 (trailing whitespace / merge marker 0건)

---

## 4. 변이 사살 표 (tools/test_c235_mutations.py 40종 전수 사살)

아래 변이 설명 및 사살 경로는 `tools/test_c235_mutations.py` 정의 및 실제 실행 결과와 100% 일치합니다.

| 변이 ID | 변이 내용 (러너 정의 그대로) | 사살 검증 게이트 |
| :--- | :--- | :--- |
| Z1 | candidate config: fg==bg collision (color: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9o) |
| Z2 | candidate config: border==bg collision (border: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9o) |
| Z3 | pool button selected: fg==bg collision (color: brand-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z4 | pool button selected: border==bg collision (border: brand-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z5 | unverified badge: fg==bg collision (color: bg-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z6 | unverified badge: border==bg collision (border: bg-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z7 | gpu button selected: border==bg collision (border: brand-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z8 | error banner: border==bg collision (border: bg-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z9 | preview retry button: border==bg collision (border: bg-subtle) | KILLED (Test 9j-2 & Test 9o) |
| Z10 | candidate config: text token as bg (bg: var(--color-text-primary)) | KILLED (Test 9j-2 & Test 9o) |
| Z11 | pool button selected: text token as bg (backgroundColor: text-primary) | KILLED (Test 9j-2 & Test 9o) |
| Z12 | candidate badge: opacity degradation (opacity: 0.4) | KILLED (Test 9o) |
| Z13 | unverified badge: opacity degradation (opacity: 0.45) | KILLED (Test 9o) |
| Z14 | pool button: opacity degradation (opacity: 0.35) | KILLED (Test 9j-2) |
| Z15 | candidate config: comment decoy with legacy hex | KILLED (Test 9j-2 & Test 9o) |
| Z16 | unverified badge: comment decoy with legacy hex | KILLED (Test 9j-2 & Test 9o) |
| Z17 | candidate config: revert to legacy #fbbf24 | KILLED (Test 10 & Test 9j-2 & Test 9o) |
| Z18 | error banner: revert text to legacy #fca5a5 | KILLED (Test 10 & Test 9j-2 & Test 9o) |
| Z19 | error banner: revert border to legacy #ef4444 | KILLED (Test 10 & Test 9j-2 & Test 9o) |
| Z20 | operator note: revert text to legacy #93c5fd | KILLED (Test 9j-2) |
| Z21 | candidate config: degraded color collapsed to status-online | KILLED (Test 9o) |
| Z22 | preview error banner: offline color collapsed to status-online | KILLED (Test 9o) |
| Z23 | unverified badge: degraded color collapsed to status-online | KILLED (Test 9o) |
| Z24 | candidate config: label mutated to '대기' | KILLED (Test 9o) |
| Z25 | unverified badge: text mutated to '[시뮬레이션]' | KILLED (Test 9o) |
| Z26 | preview retry button: text mutated to '!' | KILLED (Test 9o) |
| Z27 | gpu button: outline: 'none' suppressing focus ring | KILLED (Test 9j-2 & Test 9o) |
| Z28 | retry button: outline: 0 suppressing focus ring | KILLED (Test 9j-2 & Test 9o) |
| Z29 | pool button: outlineWidth: '0px' suppressing focus ring | KILLED (Test 9j-2) |
| Z30 | gpu button: outline: '0px' suppressing focus ring | KILLED (Test 9j-2 & Test 9o) |
| Z31 | fail-closed: bypass Object.hasOwn with plain indexing | KILLED (Test 9o) |
| Z32 | prototype key: hijack toString into candidate config | KILLED (Test 9o) |
| Z33 | fail-closed: fallback returns candidate color instead of unknown | KILLED (Test 9o) |
| Z34 | contract bypass: map out-of-contract 'admitted' to candidate | KILLED (Test 9o) |
| Z35 | contract bypass: state !== 'candidate' bypass dropping candidate to unknown | KILLED (Test 9o) |
| Z36 | named color: candidate badge border injected with yellow | KILLED (Test 9j-2 & Test 9o) |
| Z37 | named color: error banner color injected with red | KILLED (Test 9j-2 & Test 9o) |
| Z38 | unknown label: remove 'UNKNOWN (' prefix | KILLED (Test 9o) |
| Z39 | unknown label: bypass UNKNOWN format and return raw uppercase | KILLED (Test 9o) |
| Z40 | case-insensitive lookup: toLowerCase() lookup bypass | KILLED (Test 9o) |

> [!NOTE]
> **Claude 독립 검토 변이 C07, C08, C09 사살 실측**:
> - C07 (`pool-capacity-error` fg를 `text-primary`로 상태 붕괴): Test 9o `expect(capError.style.color).toBe('var(--color-status-offline)')`에 의해 KILLED.
> - C08 (`pools-error-banner` fg+border를 중립 토큰으로 상태 붕괴): Test 9o `expect(poolsErrorBanner.style.color).toBe('var(--color-status-offline)')` 및 `borderColor`에 의해 KILLED.
> - C09 (`preview-error-banner` 제목의 `⚠️` 제거): Test 9o `expect(prevErrorBanner.textContent).toContain('⚠️')`에 의해 KILLED.

---

## 5. 다음 행동 및 인계
- **현재 상태**: Card 235 [r2] 수정 조치 완료, Claude UI r1 (F1~F7) 및 Codex r1 (F-R1, F-R2) 지적 전수 반영, 로컬 전체 게이트 100% 통과, 40종 변이 전원 사살 실측 완료, PR #340 업데이트 준비 완료.
- **다음 행동**: `agent/gemini/c235-placement-contrast` 브랜치 커밋 및 푸시 (no force push), PR #340 리뷰 요청 (r2) 코멘트 등록 (Zero bot tags `@...`), 이후 Card 245 (#342) branch에 고친 #340 head merge 및 #342 검토 요청.
- **다음 담당자**: Claude UI (기본 리뷰어) 및 Codex (보조 리뷰어).
