---
doc_id: "HIST-GEMINI-20260918-07"
title: "2026-09-18 15:40 KST 브라우저 스모크 검증 경계 조치 (VB-MJS-02) 및 미검증 UI 불변식 명시 Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T15:40:00+09:00"
updated: "2026-09-18T15:40:00+09:00"
timezone: "Asia/Seoul"
base_sha: "120a8a0"
source_of_truth: "Git"
---

# 브라우저 스모크 검증 경계 조치 (VB-MJS-02) 및 미검증 UI 불변식 명시 Gemini 검증보고 (2026-09-18 15:40 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 감사/검토자**: Codex, Claude
- **기준 Commit**: `120a8a0`
- **감사 지적 수용 및 조치 (`VB-MJS-02`, P2)**:
  - Codex의 검증 도구 감사에서 `tools/run_browser_smoke.mjs` 러너의 클라이언트 UI 단언 3건이 상수 `true`로 하드코딩되어 있던 문제 완전 해결:
    1. **하드코딩 상수 `true` 문제**:
       - `tools/run_browser_smoke.mjs` 912~921행(개편 전)에 `windowManagerValid = true`, `keyboardA11ySupported = true`, `layoutPersistenceValid = true`로 박혀 있어, 창 관리·키보드 A11y 내비게이션·레이아웃 영속성이 실제로 동작하든 깨져 있든 무조건 `[PASS]`로 집계됨.
       - 이는 "실패할 수 없는 단언"의 대표적 형태로, 실제 관측되지 않은 클라이언트 UI 동작을 통과로 위장할 위험이 존재함.
    2. **Zero-Mock 원칙에 따른 해결 방향**:
       - Codex 권장 최소 수정안을 엄격히 채택: HTTP API 계약 스모크 스위트(Node.js fetch 기반)는 브라우저 DOM 렌더링, z-index 적층, Alt+Tab 키보드 이벤트, `localStorage` 저장을 직접 관측할 수 없으므로, 이 3개 UI 항목을 `[UNVERIFIED]`로 명시하고 `[PASS]` 집계에서 완전히 제외함.
       - 정적 HTML 번들에 해당 문자열이 있는지 검사하는 등의 속임수(shallow string matching)를 배제하고, 별도 대화형 브라우저 레인(DOM/Browser lane)으로 명확히 이관함.
    3. **영구 회귀 시험 가드**:
       - 소스 코드에 상수 true 단언이 재도입되지 않도록 정적 검증.
       - 러너 실행 결과 3개 항목이 `ℹ [UNVERIFIED]`로 출력되고 `✔ [PASS]`에 포함되지 않음을 검증.
       - 요약 배너가 레거시 `202/202`가 아닌 `199/199 observed checks passed` 및 `3 unverified UI invariants deferred to browser lane`으로 나타남을 검증.

---

## 2. 주요 조치 내역

### 1) `tools/run_browser_smoke.mjs` 가드 개편 및 정직한 스코프 명시
- **`recordUnverified(title, reason)` 헬퍼 및 `unverified` 카운터 도입**:
  - 미검증 항목을 별도 카운트하고 콘솔에 사유와 함께 투명하게 로깅 (`ℹ [UNVERIFIED] <title> (<reason>)`).
- **3개 UI 불변식의 `recordUnverified` 전환**:
  - `Window Manager enforces traffic lights, z-index elevation, and minimize/maximize`:
    - 사유: `Requires interactive DOM browser lane; unverified in HTTP API contract smoke`
  - `Web Desktop Shell implements Alt+Tab cycling and Escape modal dismissal protocol`:
    - 사유: `Requires interactive keyboard input browser lane; unverified in HTTP API contract smoke`
  - `Desktop window manager enforces local storage layout serialization protocol`:
    - 사유: `Requires browser localStorage persistence lane; unverified in HTTP API contract smoke`
- **정직한 요약 배너 (Honest API Contract Smoke Summary)**:
  - `🎉 API Contract Smoke Summary: 199/199 observed checks passed (100%) | 3 unverified UI invariants deferred to browser lane`
  - `passed !== total || total === 0` 가드로 오류 시 `process.exit(1)` 보장.

### 2) 영구 회귀 시험 스위트 신설 (`tests/test_browser_smoke_boundary.py`)
- **`test_source_code_has_no_constant_true_assertions_for_ui_invariants`**:
  - `windowManagerValid = true`, `keyboardA11ySupported = true`, `layoutPersistenceValid = true` 패턴이 소스 코드에 없음을 단언.
  - `recordUnverified` 및 3개 불변식의 이관 사유 문자열이 소스에 존재함을 검증.
- **`test_smoke_runner_reports_three_unverified_and_199_observed_checks`**:
  - 실제 러너를 서브프로세스로 기동하여 exit code 0 확인.
  - 3개 항목이 `ℹ [UNVERIFIED]`로 출력되고, `✔ [PASS]`로 출력되지 않음을 단언.
  - 요약 배너에 `199/199 observed checks passed`와 `3 unverified UI invariants deferred to browser lane`이 포함됨을 단언.
  - 과거의 왜곡된 `202/202 checks passed` 및 `Full E2E Browser Journey Smoke Summary: 202/202` 문구가 출력되지 않음을 엄격히 검증.

---

## 3. 실측 검증 결과

| 검증 영역 | 실행 명령 | Exit Code | 실측 결과 |
|---|---|---|---|
| **스모크 경계 회귀 시험** | `.venv\Scripts\python -m pytest tests/test_browser_smoke_boundary.py -v` | **0** | **2 passed in 3.15s** (소스 상수 부재, 3 unverified / 199 observed 통과) |
| **배포 런처 회귀 시험** | `.venv\Scripts\python -m pytest tests/test_deploy_intranet_preflight.py -v` | **0** | **10 passed in 5.35s** (VB-LAUNCH-01 종료가드 및 스코프 10개 전수 통과) |
| **프론트엔드 Vitest 전체** | `npm --prefix apps/web test -- --run` | **0** | **31개 파일 300 passed / 0 failed in 3.32s** |
| **스모크 러너 실실행** | `node tools/run_browser_smoke.mjs` | **0** | **199/199 observed checks passed (100%)**, 3 unverified UI invariants deferred |
| **문서 정합성 검증** | `.venv\Scripts\python tools/check_docs.py` | **0** | **PASS**: 24 original hashes, 550+ docs, wiki links, 48 tasks, 12 outcomes |
| **온톨로지 정합성 검증** | `.venv\Scripts\python tools/check_ontology.py` | **0** | **PASS**: RDF parsing, TTL/JSON-LD, 48 task mappings, positive SHACL |

---

## 4. 정직한 스코프 및 인계 원칙

1. **소급 변경 금지 원칙 준수**:
   - Codex의 감사 원칙에 따라 이전의 역사적 기록(과거 고정 SHA 커밋의 202 체크 통과 보고서)을 소급하여 결함으로 재분류하거나 수치를 깎지 않음.
   - 본 수정 시점부터 러너가 199 관측 통과 + 3 미검증 UI 불변식을 투명하게 보고하도록 정립함.
2. **실제 브라우저 인터랙티브 검증 경계**:
   - 창 관리(신호등 버튼/z-index), 키보드 단축키(Alt+Tab/Escape), 레이아웃 영속성(`localStorage`)은 대화형 DOM/키보드/스토리지 브라우저 레인에서 실제 렌더링 및 인터랙션 증거가 확보될 때만 `[PASS]`로 채점함.
3. **독립 검토 인계**:
   - 본 `VB-MJS-02` 조치와 회귀 시험 `tests/test_browser_smoke_boundary.py`를 Codex 및 Claude에 인계하여 독립 검토를 요청함.
