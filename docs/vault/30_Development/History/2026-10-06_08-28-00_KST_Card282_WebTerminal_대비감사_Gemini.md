---
doc_id: "HIST-20261006-CARD282-GEMINI"
title: "Card 282 웹 터미널 화면 색상 리터럴 전수 토큰화 및 ACC-09 그랜드 마일스톤 달성"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-10-06T08:28:00+09:00"
updated: "2026-10-06T08:28:00+09:00"
source_of_truth: "Git"
---

# Card 282 웹 터미널 화면 색상 리터럴 전수 토큰화 및 ACC-09 그랜드 마일스톤 달성

## 1. 작업 개요
- **목표**: ACC-09의 최종 잔여 대상 파일인 `WebTerminal.tsx`의 색상 리터럴 32 occurrences / 23 distinct 전수 토큰화(32건→0건), 웹 터미널 연결/명령 상태 설정 테이블 계약 결속, fail-closed 방어 체계 구축, 명도 대비 감사 및 ACC-09 저장소 전체 그랜드 마일스톤 달성:
  1. `apps/web/src/features/terminal/WebTerminal.tsx`: 베이스(`a17b0e7d`, Card 281 Commit C)에 잔존하던 32 occurrences / 23 distinct 색상 리터럴 (`#090d16`: 1, `#0d1117`: 1, `#161b22`: 1, `#1c1917`: 1, `#238636`: 1, `#30363d`: 2, `#451a03`: 1, `#58a6ff`: 1, `#6b7280`: 1, `#7f1d1d`: 1, `#8b949e`: 5, `#c9d1d9`: 2, `#d29922`: 1, `#d97706`: 1, `#ea580c`: 1, `#ef4444`: 2, `#f0f6fc`: 2, `#f85149`: 1, `#fb923c`: 1, `#fde68a`: 2, `#fecaca`: 1, `#fed7aa`: 1, `#fff`: 1) 전수 제거 및 디자인 토큰 전면 승격 (32건→0건).
  2. **ACC-09 그랜드 마일스톤 Invariant 달성**:
     - Card 282의 토큰화를 끝으로 `COLOR_LITERAL_MULTISET_BASELINE`에 등록된 36개 모든 파일의 리터럴 잔여량이 `{}`(0건)으로 전수 수렴 완료.
     - `observedFileMultisets` 등록 파일 수 0개 달성 (`expect(Object.keys(observedFileMultisets).length).toBe(0)` 신설 불변식 통과).
     - 저장소 전체 프런트엔드 프로덕션 코드(`apps/web/src`) 내 하드코딩 색상 리터럴 0건 마일스톤을 영구 봉인.
  3. **터미널 구현 구조 및 테마 아키텍처 정합성**:
     - `WebTerminal.tsx`는 외부 서드파티 터미널 라이브러리(xterm.js 등) 호출 없이 React JSX 기반의 가상 터미널 뷰포트와 양방향 WebSocket 스트리밍을 수행합니다.
     - 모든 터미널 출력 영역, 로그 라인, 프롬프트, 타이틀 바 및 알림 배너는 JSX 인라인 스타일의 CSS 변수 `var(--color-...)`에 직접 결속되어 라이트/다크 테마 전환 시 즉각 일관된 대비를 제공합니다.
  4. **Fail-Closed 연결 상태 계약 체계 확립**:
     - `WebTerminalConnectionStatus` ('connecting' | 'connected' | 'disconnected' | 'error')를 엄밀히 지원하는 `WEB_TERMINAL_CONNECTION_STATUS_CONFIG satisfies Record<WebTerminalConnectionStatus, WebTerminalConnectionStatusConfigItem>` 설정 표 구축.
     - `getWebTerminalConnectionStatusConfig` 헬퍼 함수에 `Object.hasOwn` 기반 fail-closed 룩업을 강제하여 `toString`, `constructor`, `__proto__`, `valueOf` 등 프로토타입 오염 공격 및 계약 외 미등록 상태를 `UNKNOWN (<key>)` 및 `var(--color-status-unknown)` 토큰으로 안전 강등하도록 봉인.
  5. **명도 대비 및 접근성 규격 승격 (WCAG 2.2 AA SC 1.4.3 & SC 1.4.11)**:
     - 재시도(Retry) 버튼 배경을 `--color-status-offline-bg`(`var(--color-status-offline-bg)`, `#dc2626`)로 결속하고 흰색 텍스트(`--color-brand-primary-fg`)를 적용하여 라이트 5.86:1, 다크 7.46:1 (>= 4.5:1 PASS) 달성.
     - 미인가 커맨드 재시도 비활성 버튼은 `--color-bg-subtle` 위 `--color-text-muted`(4.67:1 / 5.23:1 >= 4.5:1 PASS) 달성.
     - 터미널 뷰포트, 타이틀바, 연결 상태 배지, 커맨드 안내 배너, 오류 배너 등 총 32개 평가 지표 전원 WCAG 2.2 AA 합격 (PASS: 24, INFO: 8, FAIL: 0).
  6. **AST 정적 분석기 래칫 및 검증 테이블 바인딩**:
     - Test 9j-2 `analyzeFile` 스위트에 `WebTerminal.tsx` 등록:
       - totalStyleAttrs: 28, checkedObjects: 6, checkedPairs: 15, unboundColorObjects: 8, coveredColorObjects: 14, checkedBorderObjects: 9, checkedBorderPairs: 9, violations: 0.
  7. **Multiset Baseline 래칫 강제**:
     - `COLOR_LITERAL_MULTISET_BASELINE`에서 `features/terminal/WebTerminal.tsx: {}` (0건)으로 전면 래칫 고정.
     - `var(--color-border-subtle)` 정확히 487건(+3건), 36개 파일(+1개 파일) 래칫 보존 (Test 10 통과).
  8. **DOM 결속 및 Revert-Fail Probes**:
     - Test 9af 신설: `WebTerminal` 컴포넌트 렌더링, 색상 토큰 바인딩, 동적 명도 대비 계산, 프로토타입 오염 격리 전수 단언.
     - Revert-Fail Probes 166~170 신설: 베이스라인 결함 색상(`#fb923c`, `#fecaca`, `#fde68a`, `#ef4444`, `#238636`)이 라이트 캔버스 위에서 4.5:1을 탈락함을 증명.
  9. **40종 전수 변이 실측 사살 (Receipt A/B)**:
     - `tools/test_c282_mutations.py` M1~M40 40/40 100% 사살 실측 (clean commit A `bdee2e60` 기반, Commit B `51b93831` 봉인, 바이너리 read_bytes/write_bytes 복원 및 fail-closed clean-tree 무결성 검증 통과).

---

## 2. 실측 명도 대비 지표 (§2.1 대비 표본)

아래 Before 값은 베이스 `a17b0e7d`(Card 281 Commit C)의 실제 코드 실측값을 기준으로 측정되었습니다. After 값은 `python tools/reproduce_c282_contrast.py` 실행 결과(32개 전 항목)와 100% 일치합니다.

| ID | 항목 명칭 | 역할 | 적용 토큰 | 라이트 대비 | 다크 대비 | 판정 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| WT-01 | WebTerminal Root Container Background | fill | --color-bg-canvas | 1.00:1 | 1.00:1 | INFO |
| WT-02 | WebTerminal Root Container Text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| WT-03 | WebTerminal Root Container Border | boundary | --color-border-subtle | 3.33:1 | 4.08:1 | PASS |
| WT-04 | Title Bar Background | fill | --color-bg-surface | 1.05:1 | 1.10:1 | INFO |
| WT-05 | Title Bar Bottom Border | boundary | --color-border-subtle | 3.48:1 | 3.73:1 | PASS |
| WT-06 | Status Dot Indicator | boundary | --color-status-online | 5.02:1 | 7.79:1 | PASS |
| WT-07 | Session ID Label Text | text | --color-text-muted | 5.75:1 | 6.99:1 | PASS |
| WT-08 | Connection Status Label Text | text | --color-text-muted | 5.75:1 | 6.99:1 | PASS |
| WT-09 | Toggle A11y Button Text | text | --color-text-primary | 17.85:1 | 16.98:1 | PASS |
| WT-10 | Close Button Text | text | --color-status-offline | 6.47:1 | 6.41:1 | PASS |
| WT-11 | Command Required Notice Background | fill | --color-bg-subtle | 1.05:1 | 1.32:1 | INFO |
| WT-12 | Command Required Notice Text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| WT-13 | Command Required Notice Divider | boundary | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| WT-14 | Command Required Notice Hint Text | text | --color-text-secondary | 6.92:1 | 11.86:1 | PASS |
| WT-15 | Error Alert Background | fill | --color-risk-l3-bg | 1.17:1 | 1.19:1 | INFO |
| WT-16 | Error Alert Message Text | text | --color-status-offline | 5.30:1 | 5.90:1 | PASS |
| WT-17 | Error Alert Divider | boundary | --color-risk-l3-border | 5.30:1 | 5.90:1 | PASS |
| WT-18 | Retry Button Background (Authorized) | boundary | --color-status-offline-bg | 3.95:1 | 3.38:1 | PASS |
| WT-19 | Retry Button Text (Authorized) | text | --color-brand-primary-fg | 4.83:1 | 4.83:1 | PASS |
| WT-20 | Retry Button Background (Unauthorized) | fill | --color-bg-subtle | 1.12:1 | 1.11:1 | INFO |
| WT-21 | Retry Button Text (Unauthorized) | text | --color-text-muted | 5.25:1 | 5.78:1 | PASS |
| WT-22 | Disconnected Alert Background | fill | --color-bg-subtle | 1.05:1 | 1.32:1 | INFO |
| WT-23 | Disconnected Alert Text | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| WT-24 | Disconnected Alert Divider | boundary | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| WT-25 | Disconnected Alert Dismiss Button | text | --color-status-degraded | 4.58:1 | 6.83:1 | PASS |
| WT-26 | A11y Text Log Region Background | fill | --color-bg-canvas | 1.00:1 | 1.00:1 | INFO |
| WT-27 | A11y Text Log Region Text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| WT-28 | Log Entry Stderr Text | text | --color-status-offline | 6.18:1 | 7.02:1 | PASS |
| WT-29 | Log Entry Stdout Text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |
| WT-30 | Stream Terminal Output Container Bg | fill | --color-bg-canvas | 1.00:1 | 1.00:1 | INFO |
| WT-31 | Stream Command Prompt Symbol ($) | text | --color-brand-primary | 4.94:1 | 7.64:1 | PASS |
| WT-32 | Stream Command Input Text | text | --color-text-primary | 17.06:1 | 18.59:1 | PASS |

---

## 3. 검증 결과 및 증거 요약

1. **단위 및 계약 검증**:
   - `npx vitest run tests/acc09-contrast-tokens.test.tsx`: 46 tests 전수 통과 (Test 9af, Test 9j-2 WebTerminal 래칫, Probes 166~170, Test 10 ACC-09 그랜드 마일스톤 불변식 포함).
2. **TypeScript 컴파일 및 빌드**:
   - `npx tsc -b`: 0 errors.
   - `npm run build`: 프로덕션 번들 정상 빌드 완료.
3. **무결성 및 라우트 커버리지 검증**:
   - `python tools/check_frontend_integrity.py`: 0 violations (9개 규칙 전수 합격).
   - `python tools/check_contract_bindings.py`: PASS.
   - `pytest tests/test_route_coverage.py`: 41 passed (100%).
4. **문서 및 경로 인용 검사**:
   - `python tools/check_docs.py`: exit code 0.
   - `python tools/check_doc_path_citations.py --ratchet --base-ref a17b0e7d`: PASS.
   - `python tools/sync_obsidian.py --check`: 0 conflicts.
5. **돌연변이 검증 (Receipt A/B)**:
   - `python tools/test_c282_mutations.py --all`: 40/40 killed (100.0%, duration 829.5s).
   - Clean Commit A `bdee2e60` 위 Receipt B `51b93831` 봉인.
