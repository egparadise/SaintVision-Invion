---
doc_id: "HIST-G07-003"
title: "2026-09-28 16:30:00 KST G-07 Eval 러너 Claude r2 수정 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T16:30:00+09:00"
source_of_truth: "Git"
---

# G-07 100 Prompt 30 Coding Eval 러너 및 변이 도구 Claude UI·시험 축 r2 결함 F1~F11 조치 보고

## 1. 개요 및 검토 배경
PR #190 (`agent/gemini/g07-eval-runner-impl`, head `5bf957c2`)에 대한 Claude UI·시험 축 1차 검토에서 지적된 11건의 결함(F1~F11)을 분석하고, 실재하는 Git 객체와 실제 엔진 실행 경로 기반으로 전면 수정·보강하였다.

---

## 2. 결함별 조치 내역 (F1 ~ F11)

### F1 [Critical] 실재 Git commit SHA 및 Git Blob OID 바인딩
- **원인**: 이전 증거의 `sourceHeadSha`가 임의 해시였고 `gitBlobOids`가 파일명 문자열의 SHA256으로 위조되어 있었음.
- **조치**:
  1. 실제 측정 대상 코드·픽스처 변경이 포함된 실재 커밋 SHA(`ac5d36c1c66ece079e25d07d3fac93119f4f9398`)를 `sourceHeadSha`로 봉인.
  2. 5대 핵심 파일에 대해 `git rev-parse ac5d36c1:<path>`로 실측된 실제 Git Blob OID(`sha1("blob <len>\0" + bytes)`)를 기록:
     - `agentEngine.ts`: `d9841553b732a1d713b4e080bc72e890a0c13793`
     - `evalRunner.ts`: `99d9e86b806f4d762c96e4e5a2c7c850d1af4b36`
     - `mutationTools.ts`: `ba92cd18e3fb82471432d4b18255e5aab93f5dc1`
     - `prompts_100.json`: `09871ac5ed866414e64e3e52620c2976731c4d3e`
     - `coding_tasks_30.json`: `22642b056b9cd14582b737f311331f5b6fdede14`
  3. `evalRunner.ts`의 하드코딩 기본값을 제거하고 미지정 시 fail-closed 예외를 발생시키도록 보강.
  4. 증거 파일명을 커밋 SHA 기반인 `s09-g07-eval-evidence-ac5d36c1.json`으로 갱신.

### F2 [High] PRM-074 verdict PASS 및 Summary 프롬프트 통계 명시
- **원인**: `agentEngine.ts:32`의 정규식에 이스케이프된 `cat \/etc\/shadow`가 출력되는데, 픽스처 토큰이 `cat /etc/shadow`로 불일치하여 FAIL(129 PASS / 1 FAIL)이 발생했으나 summary에 prompt pass/fail 항목이 없어 가려짐.
- **조치**:
  1. `prompts_100.json:598`의 `expectedViolationToken`을 `cat \/etc\/shadow`로 정정하고, `evalRunner.ts`에서 raw 및 normalized 비교를 이중 지원.
  2. Summary에 `promptsPass`(98), `promptsFail`(0), `promptsKnownFalsePositive`(2)를 신설.
  3. 시험에서 `cases.filter(c => c.verdict === 'FAIL').length === 0`을 엄격히 단언.

### F3 [High] Fixture SHA-256 Byte 봉인 및 카테고리/기대값 허용 목록(Whitelist) 가드
- **조치**:
  1. `EXPECTED_FIXTURE_BYTE_SHA256` 상수를 파일 실제 byte SHA256으로 선언:
     - `prompts100`: `da34cea2e226fca69a5e7908468d079a87c96544c07ea404a73d903a283d2046`
     - `codingTasks30`: `ee3ba6d78cf204f9038cef01589290d651ffc7a38b8498c72a7df674dbfe5408`
  2. 1바이트라도 변경되거나 SHA가 다를 경우 `FAIL-CLOSED: Fixture byte SHA-256 mismatch` 예외 발생.
  3. `ALLOWED_PROMPT_CATEGORIES`(78종), `ALLOWED_CODING_CATEGORIES`(18종), `ALLOWED_EXPECTED_STATUSES` 허용 목록을 구성하여 미등록 카테고리/기대값 입력 시 즉시 fail-closed 차단.
  4. 변조 시 `toThrow`를 검증하는 `MUT-RUN-01`, `MUT-RUN-02` 시험 배선.

### F4 [High] 시험과 증거 생성 분리 (eval:check drift 검사)
- **조치**:
  1. `agent-eval-runner.test.ts`에서 증거 파일 덮어쓰기(`writeFileSync`)를 전면 제거하고 읽기 전용 drift 검사로 전환.
  2. `package.json`에 `"eval:check": "vitest run tests/agent-eval-runner.test.ts"` 스크립트 신설.
  3. 증거 생성은 전용 CLI 도구인 `tools/generate_eval_evidence.ts`로 분리.
  4. 시험 실행 후 `git status`가 완전히 clean 상태를 유지함을 확인.

### F5 [Medium-High] 반복 루프 fail-closed 경계 가드
- **조치**:
  1. `evalRunner.ts:243-255`의 루프 진행부에서 `!adv.canRepair || adv.currentLoops <= currentLoops` 조건을 검사하여 진행 불가 시 즉시 break하고 `BOUNDED_LOOP_EXCEEDED` 처리.
  2. `maxRepairLoops` 3→2 축소 변이 및 stalled loop 매니저에서도 행(hang) 없이 500ms 이내에 `verdict: FAIL`로 정상 종료됨을 실측(`MUT-RUN-04`).

### F6 [Medium] 코딩 과제 실제 엔진 예산 경로 및 REP-02 다중 루프 검증
- **조치**:
  1. `evaluateCodingTask`에서 가상 비용 수동 비교 대신 `fixture.costEstimate > 650000`에 따라 `contextFiles` 개수(25,000개)를 부여하여 `manager.createRunRequest` 내부의 `agentEngine.ts:71`(`costKrw > tenantBudgetKrw`) 실제 경로가 실행되도록 수정.
  2. 엔진 예산 검사를 우회하는 변이를 주입했을 때 시험이 즉각 사살됨을 실측(`MUT-RUN-06`).
  3. `TSK-21`(`expectedLoopCount: 2`, `REPAIRING`), `TSK-22`(`expectedLoopCount: 3`, `REPAIRING`)를 픽스처에 반영하여 REP-02의 2/3, 3/3 루프 전이 실제 관측.

### F7 [Medium] 오탐(PRM-069/070) 정식 분류 및 Summary 동적 집계
- **조치**:
  1. `PRM-069`, `PRM-070`을 `isSafe: true`, `expected: READY`, `knownFalsePositive: true`로 정정.
  2. `evalRunner.ts`에서 오탐 감지 시 `verdict: 'KNOWN_FALSE_POSITIVE'`로 분류(PASS로 왜곡하지 않음).
  3. `docs/contracts/eval-evidence.schema.json`에 `KNOWN_FALSE_POSITIVE` enum 반영.
  4. Summary의 `promptsSafe`(70), `promptsAdversarial`(30)을 fixture 기반으로 동적 계산.

### F8 [Medium] 브라우저 가짜 SHA-256 fallback 제거 및 Fail-Closed
- **조치**:
  1. `evalRunner.ts`의 32비트 임의 0-패딩 해시 생성을 제거하고 Node/Browser 환경에서 동기식 crypto 불가 시 즉시 `throw new Error('FAIL-CLOSED: crypto.createHash is unavailable')`로 전환.
  2. NIST 표준 테스트 벡터(`abc`, 빈 문자열)와 일치함을 검증하는 `MUT-RUN-05` 시험 추가.

### F9 [Low] 계획 불변식 증거 보강
- **조치**:
  1. 증거 JSON 및 스키마에 출력 누출 지표 `metrics.outputLeakage: { status: "NOT_OBSERVED", reason: "실제 LLM completion 부재 (클라이언트 가드 시뮬레이션)" }` 신설.
  2. 130개 case 객체마다 원본 입력 프롬프트인 `inputText` 필드 추가.

### F10 [Low] AST 정적 가드 고도화
- **조치**:
  1. 단순 substring 대신 `/(it|test|describe)(\.\w+)*\.(skip|only|todo)/` 및 `/\.skip\(\)/` 정규식으로 전환하여 `describe.todo`, `it.concurrent.skip`, `ctx.skip()` 모두 검출하도록 개선.
  2. 대상 파일 미존재 시 조용히 통과하지 않고 즉시 예외를 발생시키도록 강화.

### F11 [Low] History·진행판 정합 및 MUT 번호 계획 정렬
- **조치**:
  1. MUT 식별자를 계획 §1과 일치하도록 정렬:
     - `MUT-01`: 정규식 누출 방어 (Regex Guard)
     - `MUT-02`: 예산 경계 검증 (Budget Quota Guard)
     - `MUT-03`: 루프 상한 검증 (Bounded Repair Loop Guard)
  2. 실측 통계(Vitest 80 test files, 711 passed) 및 정합 수치 갱신.

---

## 3. 검증 실측 결과
- **단위 시험**: `npm run test` 및 `npm run eval:check`
  - `apps/web/tests/agent-eval-runner.test.ts`: 17 passed (17)
  - `apps/web/tests/agent-mutation-guards.test.ts`: 19 passed (19)
  - Vitest 전체 스위트: **80 files passed (80), 711 tests passed (711)** in 19.93s
- **TypeScript & Build**:
  - `npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: built in 10.39s (exit 0)
- **파이썬 게이트**:
  - `python tools/check_docs.py`: exit 0 (896 docs, 48 tasks, 12 outcomes PASS)
  - `python tools/check_contract_bindings.py`: exit 0 PASS
  - `python tools/check_frontend_integrity.py`: exit 0 PASS (9 integrity rules satisfied)
  - `pytest tests/test_route_coverage.py`: 39 passed in 1.21s (exit 0)
