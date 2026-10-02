# 2026-10-02 15:43:00 KST — Card 226: 모델 스튜디오 화면 (ModelStudioView) 색상 리터럴 전수 토큰화(26종/78 occurrences→0), 상태 색 정합성 및 접근성 승격 (r3)

## 1. 개요 및 변경 목적
- **작업 ID**: Card 226 (ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory)
- **대상 화면**: `apps/web/src/features/desktop/ModelStudioView.tsx`
- **담당자**: Gemini (Antigravity)
- **작업 브랜치**: `agent/gemini/c226-model-studio-contrast`
- **기반 커밋 (Base)**: `72fe74ce` (PR #321 r3 최종 반영 head)
- **KST 시각**: 2026-10-02 15:43:00 KST

### 1.1 Claude UI r1 및 Codex r1 피드백 조치 내역 (r2)
1. **[차단 / High] H1. DEF-S11-09 버튼 토큰 규격 준수 (exact-head hosted frontend 회복)**:
   - `ModelStudioView.tsx:437-438`의 쿼리 버튼 스타일이 `var(--color-brand-primary)` 배경 + `var(--color-text-inverse)`를 사용하여 전역 progress bar 전용 규칙(DEF-S11-09, 2곳 초과 금지)을 위반했던 결함 해소.
   - 컴포넌트 표준 규격인 `var(--color-brand-primary-bg)` 및 `var(--color-brand-primary-fg)` 조합으로 교체.
   - 로컬 `s11-defect-fixes.test.tsx` (16 tests) 전수 통과 확인 및 exact-head frontend CI 회복.
2. **[High] H2. wire 계약 replica 상태 (`healthy | repairing | missing`) 의미 보존**:
   - `apps/web/src/contracts/virtualFabric.ts:194`의 정본 replica 상태는 `'healthy' | 'repairing' | 'missing'`이나, r1에서 `missing`과 `repairing`이 누락되어 UNKNOWN으로 강등되던 결함 해소.
   - `REPLICA_STATUS_CONFIG`에 `repairing`(`var(--color-status-degraded)`, 진행/오렌지) 및 `missing`(`var(--color-status-offline)`, 실패/레드)을 정식 등록하고 기존 `unhealthy`/`degraded` 별칭도 방어적으로 유지.
3. **[High] H3. 정적 AST 가드 `checkConfigTables`의 `as const`/`satisfies` unwrap 지원**:
   - `ModelStudioView.tsx`의 4대 설정 객체가 `as const`로 선언되어 `ts.isObjectLiteralExpression(node.initializer)`에서 누락되던 맹점 해소.
   - `node.initializer.expression`을 언래핑하여 11개 설정 항목(replica 5 + availability 2 + feasibility 2 + eligibility 2)을 정적 가드에 온전히 포함.
   - exact coverage 래칫 갱신: totalStyleAttrs 86, checkedObjects 24, checkedPairs 42, coveredColorObjects 42, checkedBorderObjects 29, checkedBorderPairs 29, violations 0.
4. **[High & Low] H4, L1, L2, L3. DOM 결속 단언 보강 및 변이 23종 전원 사살**:
   - Test 9l에 healthy, repairing, missing 배지 DOM 전경/배경/테두리/opacity: 1/텍스트 단언 추가.
   - LAN 경고 배너 렌더링 및 `⚠️` 기호/대비/opacity: 1 단언 추가.
   - 쿼리 및 복구 버튼의 computed outline-style/width 및 인라인 outline 단언으로 `outline: 0` 및 `outline: none` 변이 사살.
   - Probe 85: 실효성 없는 1:1 테스트 대신 base의 결함이었던 LAN 경고 텍스트 `#fde68a` on light subtle 대비 1.14:1 (< 4.5:1 WCAG AA 실패) 검증으로 교체.
   - 지역 `helperExtractVar`: `var()`가 아닐 경우 throw하도록 강화하여 비토큰의 조용한 유입 원천 차단.
5. **[Medium] M1. `getModelAvailabilityConfig` fail-closed own-key 방어 체계 확립**:
   - `unknown`이 아닌 임의 문자열(`toString`, `bogus` 등)이 모두 `observed`로 승격되던 fail-open 결함 해소.
   - `Object.hasOwn(MODEL_AVAILABILITY_CONFIG, availability)` own-key 검사 적용.
   - 미지 값(`toString`, `constructor`, `__proto__`, `bogus`, `undefined`, `null`) 입력 시 `var(--color-status-unknown)` 및 `알 수 없음 (<raw>) · 실행 재검증 필요`로 안전 매핑되는 부정 시험 단언.
6. **[Medium] M2. History 및 작업판 지표 정합화**:
   - History §2 표 26개 행의 Before hex 및 After 토큰을 `tools/reproduce_c226_contrast.py` 실측과 100% 일치하도록 전수 동기화.
   - 파이썬 재현 스크립트 실행 콘솔 출력을 History 문서에 직접 결속.
   - Index 보드 PR 번호 오타(#326 -> #324) 정정.
   - Gemini 보드 Card 220 r3 확인 기준 줄 복원 및 `{}` 오타 정정.

### 1.2 Codex r2 피드백 조치 내역 (r3)
1. **[High] F-R1. wire 계약 enum 일치 및 계약 외 상태 fail-closed UNKNOWN 격하**:
   - `REPLICA_STATUS_CONFIG`: wire 계약(`apps/web/src/contracts/virtualFabric.ts:194`)은 엄격히 `'healthy' | 'repairing' | 'missing'` 3종이므로 wire 계약 외 임의 별칭이었던 `unhealthy` 및 `degraded`를 config 표에서 제거하여 known으로 부당 승격되는 결함 원천 차단.
   - `MODEL_AVAILABILITY_CONFIG`: 관측 API 계약(`apps/web/src/shared/api/fabricObservation.ts:38`)은 wire에서 `currentAvailability !== 'unknown'` 규칙에 따라 UI 상단 계약이 `unknown`만 정의하므로 계약 외 클라이언트 합성 상태였던 `observed`를 config 표에서 제거.
   - 불변식 단언: `expect(Object.keys(REPLICA_STATUS_CONFIG).sort()).toEqual(['healthy', 'missing', 'repairing'])` 및 `expect(Object.keys(MODEL_AVAILABILITY_CONFIG).sort()).toEqual(['unknown'])` 시험 고정.
   - 부정 시험: `unhealthy`, `degraded`, `observed`, `invalid_corrupted_state`, `bogus`, `toString`, `constructor`, `__proto__` 등 계약 외/프로토타입 문자열이 입력될 때 fail-closed되어 `var(--color-status-unknown)` 및 `알 수 없음 (<status>)`로 렌더됨을 DOM 및 helper 단언으로 검증.
   - AST 커버리지 래칫: 설정 객체 축소 반영 (totalStyleAttrs 83, checkedObjects 21, checkedPairs 39, coveredColorObjects 39, checkedBorderObjects 26, checkedBorderPairs 26, violations 0).
2. **[Low] F-R2. M23 focus ring 변이의 단일 유효 JSX style 주입 개정**:
   - r2에서 M23이 `<button style={{ outline: 'none' }} style={{...}}>` 형태로 중복 JSX 속성을 생성하여 구문 오류로 죽던 문제 수정.
   - 기존 style 객체 내부에 `outline: 'none'`을 주입하는 단일 유효 변이로 재작성하여 Test 9j-2 (AST outline 가드) 및 Test 9l (DOM focus ring 가드)에 의해 100% 사살됨을 실측.

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 수치는 `python tools/reproduce_c226_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before (Hex/RGBA) | Before 명도비 (Light / Dark) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 프로젝트 제목 | query header project / canvas | `#94a3b8` on `#0f172a` | 6.96:1 / 6.96:1 | `--color-text-secondary` on `--color-bg-canvas` | 7.24:1 | 15.69:1 | >= 4.5:1 | PASS |
| 프로젝트 설명 | query header desc / canvas | `#64748b` on `#0f172a` | 3.75:1 / 3.75:1 (FAIL) | `--color-text-muted` on `--color-bg-canvas` | 5.50:1 | 7.65:1 | >= 4.5:1 | PASS |
| 쿼리 폼 라벨 | query form label / surface | `#cbd5e1` on `#1e293b` | 9.85:1 / 9.85:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 쿼리 입력 텍스트 | query form input text / subtle | `#f8fafc` on `#0f172a` | 17.06:1 / 17.06:1 | `--color-text-primary` on `--color-bg-subtle` | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 모델 조회 버튼 | query button text / brand-primary-bg | `#ffffff` on `#3b82f6` | 3.68:1 / 3.68:1 (FAIL) | `--color-brand-primary-fg` on `--color-brand-primary-bg` | 5.17:1 | 6.70:1 | >= 4.5:1 | PASS |
| 조회 로딩 문구 | query status loading / canvas | `#93c5fd` on `#0f172a` | 9.90:1 / 9.90:1 | `--color-brand-hover` on `--color-bg-canvas` | 6.41:1 | 10.78:1 | >= 4.5:1 | PASS |
| 조회 에러 문구 | query status error / canvas | `#f87171` on `#0f172a` | 6.45:1 / 6.45:1 | `--color-status-offline` on `--color-bg-canvas` | 6.18:1 | 7.02:1 | >= 4.5:1 | PASS |
| 매니페스트 생성시각 | manifest committed at / surface | `#94a3b8` on `#1e293b` | 5.71:1 / 5.71:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 매니페스트 해시 | manifest sha hash / surface | `#94a3b8` on `#1e293b` | 5.71:1 / 5.71:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 미지 가용성 배지 | manifest availability unknown / surface | `#f59e0b` on `#1e293b` | 6.81:1 / 6.81:1 | `--color-status-unknown` on `--color-bg-surface` | 7.09:1 | 7.03:1 | >= 4.5:1 | PASS |
| 실행 재검증 안내 | manifest verify notice / surface | `#f59e0b` on `#1e293b` | 6.81:1 / 6.81:1 | `--color-status-degraded` on `--color-bg-surface` | 5.02:1 | 8.26:1 | >= 4.5:1 | PASS |
| 미관측 샤드 안내 | unobserved shards notice / surface | `#94a3b8` on `#1e293b` | 5.71:1 / 5.71:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 샤드 복구 에러 | shard repair error / subtle | `#fca5a5` on `#3d2d3c` | 6.75:1 / 6.75:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 샤드 복구 경고 | shard repair warning / subtle | `#fde68a` on `#3e3b34` | 8.97:1 / 8.97:1 | `--color-status-degraded` on `--color-bg-subtle` | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 샤드 복구 성공 | shard repair success / subtle | `#6ee7b7` on `#1c3f46` | 7.45:1 / 7.45:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 샤드 테이블 헤더 | shards table header / surface | `#94a3b8` on `#1e293b` | 5.71:1 / 5.71:1 | `--color-text-secondary` on `--color-bg-surface` | 7.58:1 | 14.33:1 | >= 4.5:1 | PASS |
| 정상 복제본 배지 | replica badge healthy / subtle | `#6ee7b7` on `#1b4649` | 6.82:1 / 6.82:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 복구 중 복제본 배지 | replica badge repairing / subtle | `#fde68a` on `#494031` | 8.18:1 / 8.18:1 | `--color-status-degraded` on `--color-bg-subtle` | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 유실 복제본 배지 | replica badge missing / subtle | `#fca5a5` on `#482e3d` | 6.38:1 / 6.38:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 샤드 저하 알림 배지 | shard degradation badge / subtle | `#fde68a` on `#494031` | 8.18:1 / 8.18:1 | `--color-status-degraded` on `--color-bg-subtle` | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 샤드 복구 실행 버튼 | shard repair button / surface | `#ffffff` on `#d97706` | 3.19:1 / 3.19:1 (FAIL) | `--color-text-inverse` on `--color-status-degraded` | 5.02:1 | 8.31:1 | >= 4.5:1 | PASS |
| 배치 가능 계획 배지 | plan feasible badge / subtle | `#6ee7b7` on `#1b4649` | 6.82:1 / 6.82:1 | `--color-status-online` on `--color-bg-subtle` | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 배치 불가 계획 배지 | plan infeasible badge / subtle | `#fca5a5` on `#482e3d` | 6.38:1 / 6.38:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 텐서 병렬 LAN 경고 | tensor parallel lan alert / subtle | `#fde68a` on `#3e3b34` | 8.97:1 / 8.97:1 | `--color-status-degraded` on `--color-bg-subtle` | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 할당 불가 노드 배지 | node ineligible badge / subtle | `#fca5a5` on `#482e3d` | 6.38:1 / 6.38:1 | `--color-status-offline` on `--color-bg-subtle` | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 할당 가능 노드 텍스트 | node eligible text / surface | `#10b981` on `#1e293b` | 5.77:1 / 5.77:1 | `--color-status-online` on `--color-bg-surface` | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |

### 2.2 `python tools/reproduce_c226_contrast.py` 실제 실행 콘솔 출력
```text
query header project / canvas            | Before:  6.96:1 (L actual on #0f172a) /  6.96:1 (D actual on #0f172a) | After:  7.24:1 (Light) / 15.69:1 (Dark)
query header desc / canvas               | Before:  3.75:1 (L actual on #0f172a) /  3.75:1 (D actual on #0f172a) | After:  5.50:1 (Light) /  7.65:1 (Dark)
query form label / surface               | Before:  9.85:1 (L actual on #1e293b) /  9.85:1 (D actual on #1e293b) | After:  7.58:1 (Light) / 14.33:1 (Dark)
query form input text / subtle           | Before: 17.06:1 (L actual on #0f172a) / 17.06:1 (D actual on #0f172a) | After: 16.30:1 (Light) / 14.05:1 (Dark)
query button text / brand-primary-bg     | Before:  3.68:1 (L actual on #3b82f6) /  3.68:1 (D actual on #3b82f6) | After:  5.17:1 (Light) /  6.70:1 (Dark)
query status loading / canvas            | Before:  9.90:1 (L actual on #0f172a) /  9.90:1 (D actual on #0f172a) | After:  6.41:1 (Light) / 10.78:1 (Dark)
query status error / canvas              | Before:  6.45:1 (L actual on #0f172a) /  6.45:1 (D actual on #0f172a) | After:  6.18:1 (Light) /  7.02:1 (Dark)
manifest committed at / surface          | Before:  5.71:1 (L actual on #1e293b) /  5.71:1 (D actual on #1e293b) | After:  7.58:1 (Light) / 14.33:1 (Dark)
manifest sha hash / surface              | Before:  5.71:1 (L actual on #1e293b) /  5.71:1 (D actual on #1e293b) | After:  7.58:1 (Light) / 14.33:1 (Dark)
manifest availability unknown / surface  | Before:  6.81:1 (L actual on #1e293b) /  6.81:1 (D actual on #1e293b) | After:  7.09:1 (Light) /  7.03:1 (Dark)
manifest verify notice / surface         | Before:  6.81:1 (L actual on #1e293b) /  6.81:1 (D actual on #1e293b) | After:  5.02:1 (Light) /  8.26:1 (Dark)
unobserved shards notice / surface       | Before:  5.71:1 (L actual on #1e293b) /  5.71:1 (D actual on #1e293b) | After:  7.58:1 (Light) / 14.33:1 (Dark)
shard repair error / subtle              | Before:  6.75:1 (L actual on #3d2d3c) /  6.75:1 (D actual on #3d2d3c) | After:  5.91:1 (Light) /  5.31:1 (Dark)
shard repair warning / subtle            | Before:  8.97:1 (L actual on #3e3b34) /  8.97:1 (D actual on #3e3b34) | After:  4.58:1 (Light) /  6.83:1 (Dark)
shard repair success / subtle            | Before:  7.45:1 (L actual on #1c3f46) /  7.45:1 (D actual on #1c3f46) | After:  4.58:1 (Light) /  6.44:1 (Dark)
shards table header / surface            | Before:  5.71:1 (L actual on #1e293b) /  5.71:1 (D actual on #1e293b) | After:  7.58:1 (Light) / 14.33:1 (Dark)
replica badge healthy / subtle           | Before:  6.82:1 (L actual on #1b4649) /  6.82:1 (D actual on #1b4649) | After:  4.58:1 (Light) /  6.44:1 (Dark)
replica badge repairing / subtle         | Before:  8.18:1 (L actual on #494031) /  8.18:1 (D actual on #494031) | After:  4.58:1 (Light) /  6.83:1 (Dark)
replica badge missing / subtle           | Before:  6.38:1 (L actual on #482e3d) /  6.38:1 (D actual on #482e3d) | After:  5.91:1 (Light) /  5.31:1 (Dark)
shard degradation badge / subtle         | Before:  8.18:1 (L actual on #494031) /  8.18:1 (D actual on #494031) | After:  4.58:1 (Light) /  6.83:1 (Dark)
shard repair button / surface            | Before:  3.19:1 (L actual on #d97706) /  3.19:1 (D actual on #d97706) | After:  5.02:1 (Light) /  8.31:1 (Dark)
plan feasible badge / subtle             | Before:  6.82:1 (L actual on #1b4649) /  6.82:1 (D actual on #1b4649) | After:  4.58:1 (Light) /  6.44:1 (Dark)
plan infeasible badge / subtle           | Before:  6.38:1 (L actual on #482e3d) /  6.38:1 (D actual on #482e3d) | After:  5.91:1 (Light) /  5.31:1 (Dark)
tensor parallel lan alert / subtle       | Before:  8.97:1 (L actual on #3e3b34) /  8.97:1 (D actual on #3e3b34) | After:  4.58:1 (Light) /  6.83:1 (Dark)
node ineligible badge / subtle           | Before:  6.38:1 (L actual on #482e3d) /  6.38:1 (D actual on #482e3d) | After:  5.91:1 (Light) /  5.31:1 (Dark)
node eligible text / surface             | Before:  5.77:1 (L actual on #1e293b) /  5.77:1 (D actual on #1e293b) | After:  5.02:1 (Light) /  7.79:1 (Dark)
```

---

## 3. 정적 AST 검사 및 커버리지 래칫 (Test 9j-2)

- **Target File**: `features/desktop/ModelStudioView.tsx`
- **Total Style Attributes**: `83` (100% 정합)
- **Checked Objects (Explicit style objects)**: `21`
- **Checked Pairs (Evaluated color-background pairings)**: `39`
- **Unbound Color Objects**: `18`
- **Covered Color Objects**: `39`
- **Checked Border Objects**: `26`
- **Checked Border Pairs**: `26`
- **Violations**: `[]` (0건)
- **Hardcoded Color Literal Residual**: `0건`

---

## 4. 변이 테스트 (23종 M1~M23 전원 사살 실측)

`python tools/test_c226_mutations.py` 실행 결과:
```text
================================================================================
 Summary: 23/23 mutants killed (100.0%)
================================================================================
 [PASS] KILLED    | ModelStudioView: root section color -> bg-canvas (fg==bg 1:1 collision)
 [PASS] KILLED    | ModelStudioView: REPLICA_STATUS_CONFIG.healthy.bg -> status-online (fg==bg collision)
 [PASS] KILLED    | ModelStudioView: PLAN_FEASIBILITY_CONFIG.feasible.bg -> text-secondary (text token as bg)
 [PASS] KILLED    | ModelStudioView: model-manifest-article border -> bg-surface (border==bg collision)
 [PASS] KILLED    | ModelStudioView: query-model-btn outline ring suppressed with outline: none
 [PASS] KILLED    | ModelStudioView: shard-degradation-badge opacity degraded to 0.4
 [PASS] KILLED    | ModelStudioView: REPLICA_STATUS_CONFIG.healthy.color reverted to legacy literal #10b981
 [PASS] KILLED    | ModelStudioView: PLAN_FEASIBILITY_CONFIG.infeasible.color reverted to legacy literal #ef4444
 [PASS] KILLED    | ModelStudioView: REPLICA_STATUS_CONFIG injects out-of-contract enum unhealthy
 [PASS] KILLED    | ModelStudioView: plan infeasible color collapsed to status-online (feasible collision)
 [PASS] KILLED    | ModelStudioView: shard-degradation-badge text label removed
 [PASS] KILLED    | ModelStudioView: plan-feasible-badge text label removed
 [PASS] KILLED    | ModelStudioView: shard-repair-error border swapped to status-online
 [PASS] KILLED    | ModelStudioView: unobserved-shards-notice color swapped to bg-surface (invisible text)
 [PASS] KILLED    | ModelStudioView: getReplicaStatusConfig unknown fallback returns healthy config (fail-closed bypass)
 [PASS] KILLED    | ModelStudioView: query-model-btn inject named color lightgray
 [PASS] KILLED    | ModelStudioView: getReplicaStatusConfig uses status in REPLICA_STATUS_CONFIG bypassing prototype keys
 [PASS] KILLED    | ModelStudioView: query-model-btn outline ring suppressed with outline: 0
 [PASS] KILLED    | ModelStudioView: MODEL_AVAILABILITY_CONFIG injects out-of-contract enum observed
 [PASS] KILLED    | ModelStudioView: getModelAvailabilityConfig uses availability in MODEL_AVAILABILITY_CONFIG bypassing prototype keys
 [PASS] KILLED    | ModelStudioView: replica repairing color collapsed to status-online (healthy collision)
 [PASS] KILLED    | ModelStudioView: replica missing color collapsed to status-online (healthy collision)
 [PASS] KILLED    | ModelStudioView: shard repair button outline ring suppressed with outline: none
```

---

## 5. 검증 요약
| 검증 항목 | 실행 명령 | 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| Vitest ACC-09 스위트 | `npx vitest run tests/acc09-contrast-tokens.test.tsx` | **29 passed (100%)** | Test 9l DOM 단언, Test 9j-2 AST 래칫, Probe 81~85 전수 통과 |
| S11 결함 회귀 스위트 | `npx vitest run tests/s11-defect-fixes.test.tsx` | **16 passed (100%)** | DEF-S11-09 brand-primary-bg/fg 버튼 검증 통과 |
| 형제 접근성/도메인 스위트 | `npx vitest run tests/accessibility-status-and-guards.test.tsx ...` | **75 passed (100%)** | 5개 스위트 전원 통과 |
| 타입스크립트 정적 검사 | `npx tsc -b` | **0 errors (Exit Code 0)** | Strict types 100% 충족 |
| 프로덕션 번들 빌드 | `npm run build` | **Build Success (Exit Code 0)** | Vite 프로덕션 번들 생성 완료 |
| 라우트 커버리지 및 무결성 | `pytest tests/test_route_coverage.py` | **41 passed (100%)** | 불변식 및 라우트 계약 일치 |
| 프런트엔드 무결성 가드 | `python -X utf8 tools/check_frontend_integrity.py` | **0 violations (Exit Code 0)** | 9대 무결성 규칙 전수 준수 |
| 계약 바인딩 검사 | `python -X utf8 tools/check_contract_bindings.py` | **PASS (Exit Code 0)** | 55 fixtures, 20 types 커버리지 |
| 명도 대비 동적 재현 | `python tools/reproduce_c226_contrast.py` | **26/26 passed (Exit Code 0)** | Light/Dark 전수 WCAG AA 충족 |
| 뮤테이션 테스트 스위트 | `python tools/test_c226_mutations.py` | **23/23 killed (100.0%)** | M1~M23 전원 사살 실측 |
