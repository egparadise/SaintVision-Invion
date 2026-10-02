---
doc_id: "HIST-20261003-CARD245-GEMINI"
title: "Card 245 거버넌스 승인 센터 (ApprovalCenter) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-03T01:25:00+09:00"
updated: "2026-10-03T01:25:00+09:00"
source_of_truth: "Git"
---

# Card 245 거버넌스 승인 센터 (ApprovalCenter) 색상 리터럴 전수 토큰화, 상태 색 정합성 및 접근성 승격

## 1. 작업 개요
- **목표**: 거버넌스 승인 센터 메인 화면(`apps/web/src/features/approvals/ApprovalCenter.tsx`)의 색상 리터럴 전수(17건→0건) 토큰화, 보안 결정 핵심 화면에 대한 상태 식별성 및 접근성 승격:
  1. 승인 상태 설정 객체 최상단 정의 및 export: `APPROVAL_STATUS_CONFIG` (`approved`, `dispatched`, `expired`, `pending`, `rejected` 5종 wire 계약 enum과 엄밀 일치).
  2. `getApprovalStatusConfig` fail-closed own-key 방어: `Object.hasOwn` 기반 검사로 prototype key(`toString`, `constructor`, `__proto__`, `valueOf`, `hasOwnProperty`, `isPrototypeOf`), 대소문자 변형(`PENDING`), 계약 밖 값(`admitted`)의 fail-open 승격을 원천 차단하고 `var(--color-status-unknown)` 및 `UNKNOWN (<raw>)` 형식으로 강등 매핑 (WCAG 1.4.1 준수).
  3. 2인 승인 규칙 진행 상태 배지 시맨틱 분리: `1/2 승인 (2차 대기)` (`var(--color-brand-hover)`) vs `2인 필수` (`var(--color-text-secondary)`).
  4. 위험 상태는 위험 색 유지: `rejected`, `expired`, `stale-warning`, `error-state`는 `var(--color-status-offline)`.
  5. 키보드 포커스 링 보존: 새로고침 버튼 및 에러 재시도 버튼에 `outline: none/0`, `outlineWidth: 0` 등 포커스 링 억제 스타일 배제 및 DOM computed outline 검증.
  6. Multiset Baseline 래칫 강제: `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/approvals/ApprovalCenter.tsx` 허용 인벤토리를 `{}` (0건)으로 전면 래칫 고정. `var(--color-border-subtle)` 사용 횟수: 458건 / 31개 파일 엄밀 래칫.
  7. 40종 전수 변이 실측 사살: `tools/test_c245_mutations.py` W1~W40 40/40 100% 사살 실측 (timeout=120초, 각 변이 후 git diff 0 확인).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스의 실제 렌더링 합성값(라이트 캔버스 `#f8fafc` 위 카드 표면 `#ffffff`, 서브틀 배경 `#f1f5f9` 및 다크 캔버스 `#090d16` 위 `#0f172a`, `#1e293b`)을 기준으로 하며, 하드코딩 리터럴의 라이트 테마 전환 시 심각한 명도 결손(Probes 101~105 실측)과 알파 테두리 명도비 결손(< 3.0:1)이 존재했습니다. After 값은 `python tools/reproduce_c245_contrast.py` 실행 결과와 100% 일치합니다.

| UI 요소 | 식별자 / 위치 | Before 베이스 합성값 (Hex/RGBA on Canvas/Surface) | Before 명도비 (Dark/Light 렌더 실측) | After 토큰 쌍 (전경 / 배경 / 테두리) | After 명도비 (Light) | After 명도비 (Dark) | WCAG 기준 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 신선도 배지 텍스트 | freshness-badge text | #93c5fd on rgba(59,130,246,0.1) over #ffffff | 1.80:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 4.5:1 | PASS |
| 신선도 배지 테두리 | freshness-badge border | #93c5fd on #ffffff | 1.80:1 (FAIL) | --color-brand-hover on --color-brand-subtle | 5.49:1 | 8.11:1 | >= 3.0:1 | PASS |
| 새로고침 버튼 텍스트 | refresh-btn text | var(--color-text-primary) on #f1f5f9 | 16.30:1 (PASS) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 새로고침 버튼 테두리 | refresh-btn border | var(--color-border-subtle) on #f1f5f9 | 3.18:1 (PASS) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 동기화 실패 경고 텍스트 | stale-warning text | #fca5a5 on rgba(239,68,68,0.1) over #ffffff | 1.90:1 (FAIL) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 동기화 실패 경고 보조문구 | stale-warning subtext | #fed7aa on rgba(239,68,68,0.1) over #ffffff | 1.35:1 (FAIL) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 동기화 실패 경고 테두리 | stale-warning border | #ef4444 on #161b22 (dark) | 3.89:1 (FAIL text/UI) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 지표 대기건 텍스트 | metric-pending text | var(--color-brand-warning) on #ffffff | 2.15:1 (FAIL on light) | --color-status-degraded on --color-bg-surface | 5.02:1 | 8.26:1 | >= 4.5:1 | PASS |
| 지표 승인건 텍스트 | metric-approved text | var(--color-brand-success) on #ffffff | 2.54:1 (FAIL on light) | --color-status-online on --color-bg-surface | 5.02:1 | 7.79:1 | >= 4.5:1 | PASS |
| 지표 반려건 텍스트 | metric-rejected text | var(--color-brand-danger) on #ffffff | 4.31:1 (FAIL on light) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| 에러 상태 제목 | error-state-title | #fca5a5 on #ffffff | 1.90:1 (FAIL) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 4.5:1 | PASS |
| 에러 상태 테두리 | error-state-border | #ef4444 on #ffffff | 3.99:1 (PASS) | --color-status-offline on --color-bg-surface | 6.47:1 | 6.41:1 | >= 3.0:1 | PASS |
| 재시도 버튼 텍스트 | error-retry-btn text | #ffffff on #3b82f6 | 3.68:1 (FAIL) | --color-text-primary on --color-bg-subtle | 16.30:1 | 14.05:1 | >= 4.5:1 | PASS |
| 재시도 버튼 테두리 | error-retry-btn border | (border: none) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |
| 안건 선택 좌측 테두리 | card-selected-border | 3px solid var(--color-brand-primary) | 4.72:1 (PASS) | --color-brand-primary on --color-bg-surface | 4.72:1 | 5.77:1 | >= 3.0:1 | PASS |
| 상태 배지 대기 텍스트 | status-badge-pending text | #d97706 on rgba(234,179,8,0.15) | 3.42:1 (FAIL) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 4.5:1 | PASS |
| 상태 배지 대기 테두리 | status-badge-pending border | (border: none) | N/A (경계 미식별) | --color-status-degraded on --color-bg-subtle | 4.58:1 | 6.83:1 | >= 3.0:1 | PASS |
| 상태 배지 승인 텍스트 | status-badge-approved text | #059669 on rgba(16,185,129,0.15) | 3.82:1 (FAIL) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 4.5:1 | PASS |
| 상태 배지 승인 테두리 | status-badge-approved border | (border: none) | N/A (경계 미식별) | --color-status-online on --color-bg-subtle | 4.58:1 | 6.44:1 | >= 3.0:1 | PASS |
| 상태 배지 반려 텍스트 | status-badge-rejected text | #dc2626 on rgba(239,68,68,0.15) | 4.12:1 (FAIL) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 상태 배지 반려 테두리 | status-badge-rejected border | (border: none) | N/A (경계 미식별) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 상태 배지 만료 텍스트 | status-badge-expired text | (베이스 미분리, 반려 색상 종속) | 4.12:1 (FAIL) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 4.5:1 | PASS |
| 상태 배지 만료 테두리 | status-badge-expired border | (border: none) | N/A (경계 미식별) | --color-status-offline on --color-bg-subtle | 5.91:1 | 5.31:1 | >= 3.0:1 | PASS |
| 상태 배지 디스패치 텍스트 | status-badge-dispatched text | (베이스 미구현, 대문자 미매핑) | N/A (FAIL) | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 상태 배지 디스패치 테두리 | status-badge-dispatched border | (border: none) | N/A (경계 미식별) | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 3.0:1 | PASS |
| 상태 배지 미지 텍스트 | status-badge-unknown text | (베이스 미구현, 원문 대문자 노출) | N/A (FAIL) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 4.5:1 | PASS |
| 상태 배지 미지 테두리 | status-badge-unknown border | (border: none) | N/A (경계 미식별) | --color-status-unknown on --color-bg-subtle | 6.47:1 | 5.82:1 | >= 3.0:1 | PASS |
| 2인 승인 2차대기 텍스트 | two-person-progress text | (베이스 미분리) | N/A (FAIL) | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 4.5:1 | PASS |
| 2인 승인 2차대기 테두리 | two-person-progress border | (border: none) | N/A (경계 미식별) | --color-brand-hover on --color-bg-subtle | 6.12:1 | 8.14:1 | >= 3.0:1 | PASS |
| 2인 승인 필수 텍스트 | two-person-required text | (베이스 미분리) | N/A (FAIL) | --color-text-secondary on --color-bg-subtle | 6.92:1 | 11.86:1 | >= 4.5:1 | PASS |
| 2인 승인 필수 테두리 | two-person-required border | (border: none) | N/A (경계 미식별) | --color-border-subtle on --color-bg-subtle | 3.18:1 | 3.08:1 | >= 3.0:1 | PASS |

> [!NOTE]
> **라이트 테마 Revert-Fail Probes (Probes 101~105)**:
> 옛 다크 하드코딩 리터럴을 라이트 테마 표면 위에 적용할 경우의 심각한 명도 결손 실측:
> - Probe 101 (`#93c5fd` on light surface `#ffffff`): **1.80:1** (< 4.5:1 FAIL)
> - Probe 102 (`#fca5a5` on light surface `#ffffff`): **1.90:1** (< 4.5:1 FAIL)
> - Probe 103 (`#fed7aa` on light surface `#ffffff`): **1.35:1** (< 4.5:1 FAIL)
> - Probe 104 (`#3b82f6` on light surface `#ffffff`): **3.68:1** (< 4.5:1 FAIL)
> - Probe 105 (`#ef4444` on dark subtle `#161b22`): **3.89:1** (< 4.5:1 FAIL text)

### 2.2 tools/reproduce_c245_contrast.py 실행 결과
```text
====================================================================================================
 Card 245 ApprovalCenter Contrast Verification Report (tools/reproduce_c245_contrast.py)
====================================================================================================
ID    | Element / Role               | MinCR | Light CR   | Dark CR    | Status
----------------------------------------------------------------------------------------------------
IT01  | freshness-badge text         | 4.5   | 5.49       | 8.11       | PASS
IT02  | freshness-badge border       | 3.0   | 5.49       | 8.11       | PASS
IT03  | refresh-btn text             | 4.5   | 16.30      | 14.05      | PASS
IT04  | refresh-btn border           | 3.0   | 3.18       | 3.08       | PASS
IT05  | stale-warning text           | 4.5   | 5.91       | 5.31       | PASS
IT06  | stale-warning subtext        | 4.5   | 5.91       | 5.31       | PASS
IT07  | stale-warning border         | 3.0   | 5.91       | 5.31       | PASS
IT08  | metric-pending text          | 4.5   | 5.02       | 8.26       | PASS
IT09  | metric-approved text         | 4.5   | 5.02       | 7.79       | PASS
IT10  | metric-rejected text         | 4.5   | 6.47       | 6.41       | PASS
IT11  | error-state-title            | 4.5   | 6.47       | 6.41       | PASS
IT12  | error-state-border           | 3.0   | 6.47       | 6.41       | PASS
IT13  | error-retry-btn text         | 4.5   | 16.30      | 14.05      | PASS
IT14  | error-retry-btn border       | 3.0   | 3.18       | 3.08       | PASS
IT15  | card-selected-border         | 3.0   | 4.72       | 5.77       | PASS
IT16  | status-badge-pending text    | 4.5   | 4.58       | 6.83       | PASS
IT17  | status-badge-pending border  | 3.0   | 4.58       | 6.83       | PASS
IT18  | status-badge-approved text   | 4.5   | 4.58       | 6.44       | PASS
IT19  | status-badge-approved border | 3.0   | 4.58       | 6.44       | PASS
IT20  | status-badge-rejected text   | 4.5   | 5.91       | 5.31       | PASS
IT21  | status-badge-rejected border | 3.0   | 5.91       | 5.31       | PASS
IT22  | status-badge-expired text    | 4.5   | 5.91       | 5.31       | PASS
IT23  | status-badge-expired border  | 3.0   | 5.91       | 5.31       | PASS
IT24  | status-badge-dispatched text | 4.5   | 6.12       | 8.14       | PASS
IT25  | status-badge-dispatched border | 3.0   | 6.12       | 8.14       | PASS
IT26  | status-badge-unknown text    | 4.5   | 6.47       | 5.82       | PASS
IT27  | status-badge-unknown border  | 3.0   | 6.47       | 5.82       | PASS
IT28  | two-person-progress text     | 4.5   | 6.12       | 8.14       | PASS
IT29  | two-person-progress border   | 3.0   | 6.12       | 8.14       | PASS
IT30  | two-person-required text     | 4.5   | 6.92       | 11.86      | PASS
IT31  | two-person-required border   | 3.0   | 3.18       | 3.08       | PASS
----------------------------------------------------------------------------------------------------
Total Audit Items: 31 | Passed: 31 | Failed: 0
====================================================================================================
[SUCCESS] All 31 items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.
```

---

## 3. 검증 결과 요약

### 3.1 로컬 검증 실행 기록
1. `npx vitest run tests/acc09-contrast-tokens.test.tsx`:
   - 결과: **33 passed** (100% 통과, Test 9p 및 Test 9j-2 AST 커버리지 래칫 통과)
2. `npx vitest run tests/acc-interactive-navigation.test.tsx tests/freshness-and-staleness-wiring.test.tsx tests/truth-time-and-freshness-axis.test.tsx tests/approval-review-panel-dom.test.tsx tests/approval-timeline.test.ts`:
   - 결과: **35 passed** (형제 승인/접근성 스위트 100% 통과)
3. `npx vitest run`:
   - 결과: **99 test files passed, 1134 passed** (전체 프런트엔드 테스트 100% 통과)
4. `npx tsc -b`:
   - 결과: exit code 0 (타입 에러 0건)
5. `npm run build`:
   - 결과: exit code 0 (프로덕션 번들 빌드 성공)
6. `pytest tests/test_route_coverage.py`:
   - 결과: **41 passed** (화면-백엔드 라우트 및 EvidenceViewer 무결성 불변식 100% 통과)
7. `python -X utf8 tools/check_frontend_integrity.py`:
   - 결과: 0 violations (프런트엔드 9대 무결성 통과)
8. `python -X utf8 tools/check_contract_bindings.py`:
   - 결과: PASS (계약 바인딩 게이트 통과)
9. `python tools/check_docs.py`:
   - 결과: PASS (문서 정본 게이트 통과)
10. `python tools/check_doc_path_citations.py --ratchet --base-ref f580e495`:
    - 결과: PASS (broken citation 0건 신규, floor 유지)
11. `python tools/sync_obsidian.py --check`:
    - 결과: 0 conflicts, 0 differences (동기화 정합)
12. `git diff --check`:
    - 결과: 클린 (trailing whitespace / merge marker 0건)

---

## 4. 변이 사살 표 (tools/test_c245_mutations.py 40종 전수 사살)

| 변이 ID | 변이 내용 | 사살 검증 게이트 |
| :--- | :--- | :--- |
| W1 | pending config: fg==bg collision (color: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9p) |
| W2 | pending config: border==bg collision (border: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9p) |
| W3 | approved config: fg==bg collision (color: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9p) |
| W4 | approved config: border==bg collision (border: var(--color-bg-subtle)) | KILLED (Test 9j-2 & Test 9p) |
| W5 | two-person badge: fg==bg collision (color: bg-subtle) | KILLED (Test 9j-2 & Test 9p) |
| W6 | two-person badge: border==bg collision (border: bg-subtle) | KILLED (Test 9j-2 & Test 9p) |
| W7 | dispatched config: text token as bg (bg: var(--color-text-primary)) | KILLED (Test 9p) |
| W8 | freshness indicator: text token as bg (backgroundColor: text-primary) | KILLED (Test 9p) |
| W9 | stale warning banner: fg==bg collision (backgroundColor: offline) | KILLED (Test 9p) |
| W10 | stale warning banner: border==bg collision (border: bg-subtle) | KILLED (Test 9p) |
| W11 | status badge: opacity degradation (opacity: 0.4) | KILLED (Test 9p) |
| W12 | two-person badge: opacity degradation (opacity: 0.35) | KILLED (Test 9p) |
| W13 | pending badge: opacity degradation (opacity: 0.45) | KILLED (Test 9p) |
| W14 | two-person badge: unstarted opacity degradation (opacity: 0.5) | KILLED (Test 9p) |
| W15 | dispatched config: comment decoy with legacy hex #93c5fd | KILLED (Test 9p & Test 9j-2) |
| W16 | rejected config: comment decoy with legacy hex #fca5a5 | KILLED (Test 9p & Test 9j-2) |
| W17 | freshness indicator: revert text to legacy #93c5fd | KILLED (Test 10 & Test 9p) |
| W18 | stale warning banner: revert border to legacy #fca5a5 | KILLED (Test 10 & Test 9p) |
| W19 | stale warning note: revert color to legacy #fed7aa | KILLED (Test 10 & Test 9j-2) |
| W20 | error retry button: revert bg to legacy #3b82f6 | KILLED (Test 10 & Test 9p) |
| W21 | pending config: degraded color collapsed to status-online | KILLED (Test 9p) |
| W22 | expired config: offline color collapsed to status-online | KILLED (Test 9p) |
| W23 | rejected config: offline color collapsed to status-online | KILLED (Test 9p) |
| W24 | pending config: label mutated to '대기중' | KILLED (Test 9p) |
| W25 | two-person badge: text mutated to '1차 완료' | KILLED (Test 9p) |
| W26 | error retry button: text mutated to '다시 시도' | KILLED (Test 9p) |
| W27 | refresh button: outline: 'none' suppressing focus ring | KILLED (Test 9j-2 & Test 9p) |
| W28 | error retry button: outline: 'none' suppressing focus ring | KILLED (Test 9j-2 & Test 9p) |
| W29 | refresh button: outline: 0 suppressing focus ring | KILLED (Test 9j-2 & Test 9p) |
| W30 | error retry button: outlineWidth: '0px' suppressing focus ring | KILLED (Test 9j-2 & Test 9p) |
| W31 | fail-closed: bypass Object.hasOwn with in operator | KILLED (Test 9p) |
| W32 | fail-closed: prototype key hijack with plain indexing lookup | KILLED (Test 9p) |
| W33 | fail-closed: fallback returns approved color instead of unknown | KILLED (Test 9p) |
| W34 | contract bypass: map out-of-contract 'admitted' to approved | KILLED (Test 9p) |
| W35 | contract bypass: drop approved out of contract to unknown | KILLED (Test 9p) |
| W36 | named color: status badge border injected with yellow | KILLED (Test 9j-2 & Test 9p) |
| W37 | named color: error banner color injected with red | KILLED (Test 9j-2 & Test 9p) |
| W38 | unknown label: remove 'UNKNOWN (' prefix | KILLED (Test 9p) |
| W39 | unknown label: bypass UNKNOWN format and return raw uppercase | KILLED (Test 9p) |
| W40 | case-insensitive lookup: toLowerCase() lookup bypass | KILLED (Test 9p) |

---

## 5. 다음 행동 및 인계
- **현재 상태**: Card 245 구현 완료, 로컬 전체 게이트 100% 통과, 40종 변이 전원 사살 실측 완료, PR 생성 준비 완료.
- **다음 행동**: `agent/gemini/c245-approval-center-contrast` 브랜치 커밋 및 푸시, PR 생성 (base: `agent/gemini/c235-placement-contrast`), 리뷰 요청 코멘트 등록 (Zero bot tags `@...`).
- **다음 담당자**: Claude UI (기본 리뷰어) 및 Codex (보조 리뷰어).
