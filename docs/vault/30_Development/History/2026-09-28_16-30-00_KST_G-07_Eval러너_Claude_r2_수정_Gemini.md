---
doc_id: "HIST-G07-003"
title: "2026-09-28 16:30:00 KST G-07 Eval 러너 Claude r2 수정 (Gemini)"
version: "1.1.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T17:10:00+09:00"
source_of_truth: "Git"
---

# G-07 100 Prompt 30 Coding Eval 러너 및 변이 도구 Claude UI·시험 축 r2 결함 F1~F11 조치 보고

## 1. 개요 및 검토 배경
PR #190 (`agent/gemini/g07-eval-runner-impl`, head `5bf957c2`)에 대한 Claude UI·시험 축 1차 검토에서 지적된 11건의 결함(F1~F11) 및 2차 검토(F1-r, F3-r, F6-r, F2-r, F10-r, F11-r), Codex 계약 축(C2, C3) 피드백을 분석하고, 실재하는 Git 객체와 실제 엔진 실행 경로 기반으로 전면 수정·보강하였다.

---

## 2. 결함별 조치 내역 (F1 ~ F11 및 r2/r3 후속)

### F1 [Critical] & F1-r [High] 실재 Git commit SHA 및 Git Blob OID 바인딩
- **원인**: 이전 증거의 `sourceHeadSha`가 임의 해시였고 `gitBlobOids`가 파일명 문자열의 SHA256으로 위조되어 있었으며, `evalRunner.ts:486-500`에 하드코딩 기본값이 남아있었음.
- **조치**:
  1. 실제 측정 대상 코드·픽스처 변경이 포함된 실재 커밋 SHA(`51d19752f10b8d3d6381387a3ef8d461dd188e40`)를 `sourceHeadSha`로 봉인.
  2. 5대 핵심 파일에 대해 `git rev-parse 51d19752:<path>`로 실측된 실제 Git Blob OID(`sha1("blob <len>\0" + bytes)`)를 기록:
     - `agentEngine.ts`: `4b9ad2b76f8e796a54e78d00a5fbfb0b745f34b2`
     - `evalRunner.ts`: `69a92a20e66a4df587212da9b7be0ed079cc2a3b`
     - `mutationTools.ts`: `ba92cd18e3fb82471432d4b18255e5aab93f5dc1`
     - `prompts_100.json`: `09871ac5ed866414e64e3e52620c2976731c4d3e`
     - `coding_tasks_30.json`: `22642b056b9cd14582b737f311331f5b6fdede14`
  3. `evalRunner.ts`의 하드코딩 기본값을 commit `51d19752`에서 완전히 제거하고, Git 커밋 확인 실패 또는 unresolvable commit 시 조용한 fallback 없이 즉시 fail-closed 예외를 throw하도록 전환.
  4. 증거 파일명을 커밋 SHA 기반인 `s09-g07-eval-evidence-51d19752.json`으로 갱신.
  5. `agent-eval-runner.test.ts`의 drift 검사(`verifies committed canonical Evidence JSON against drift (eval:check, F1 & F4)`)에서 `git cat-file -e ${sha}^{commit}` 및 `git rev-parse ${sha}:<path>`를 오류 은폐 없이 직접 대조하도록 보강.

### F2 [High] & F2-r [Low] PRM-074 verdict PASS, Summary 프롬프트 통계 및 Violation Token 음성 변이 사살
- **원인**: `agentEngine.ts:32`의 정규식에 이스케이프된 `cat \/etc\/shadow`가 출력되는데, 픽스처 토큰이 `cat /etc/shadow`로 불일치하여 FAIL이 발생했으나 summary에 prompt pass/fail 항목이 없어 가려졌음.
- **조치**:
  1. `prompts_100.json:598`의 `expectedViolationToken`을 `cat \/etc\/shadow`로 정정하고, `evalRunner.ts`에서 raw 및 normalized 비교를 이중 지원.
  2. Summary에 `promptsPass`(98), `promptsFail`(0), `promptsKnownFalsePositive`(2)를 신설.
  3. F2-r 음성 변이 테스트 `MUT-TOKEN-01`을 추가하여 잘못된 토큰을 기대할 경우 `verdict: FAIL`로 즉시 검출되어 토큰 검증 로직 제거/우회 변이가 100% 사살됨을 검증.
  4. 계획서 §5 표의 행 4를 `cat \/etc\/shadow` (RegExp.toString() 이스케이프 보존)으로 정합.

### F3 [High] & F3-r [High] Fixture LF 바이트 SHA-256 봉인 및 Fallback 정적 픽스처 완전 제거
- **원인**: 초기 `EXPECTED_FIXTURE_BYTE_SHA256` 상수가 CRLF 바이트 해시로 선언되어 LF 체크아웃 CI 환경(`3955a9fb`, run `36392459583`에서 8 failed / 703 passed)에서 throw되었으며, 러너 내부에 fallback import가 남아 있었음.
- **조치**:
  1. `EXPECTED_FIXTURE_BYTE_SHA256` 상수를 LF 정규화 바이트 SHA256으로 선언 (`b84372ce` 및 `51d19752`):
     - `prompts100`: `f8962fdaaac27303d0ea3631a84f6e49a21008f6e9cc1b24d0806a73a47364b2`
     - `codingTasks30`: `549710ce589c37533e727d6f5d69242cff080668ff6652281e38c8151b3dbdb9`
  2. `evalRunner.ts`에서 정적 임포트 fallback을 전면 제거(`F3-r`). 픽스처 파일 미존재 시 `FAIL-CLOSED: Prompt/Coding tasks fixture file not found` throw.
  3. 파일에서 읽은 LF 정규화 바이트의 SHA256을 먼저 검증한 후, 검증을 통과한 동일 바이트에서 `JSON.parse(raw)`로 파싱하여 픽스처 객체 반환.
  4. `ALLOWED_PROMPT_CATEGORIES`(78종), `ALLOWED_CODING_CATEGORIES`(18종), `ALLOWED_EXPECTED_STATUSES` 허용 목록을 구성하여 미등록 카테고리/기대값 입력 시 즉시 fail-closed 차단.

### F4 [High] 시험과 증거 생성 분리 (eval:check drift 검사)
- **조치**:
  1. `agent-eval-runner.test.ts`에서 증거 파일 덮어쓰기(`writeFileSync`)를 전면 제거하고 읽기 전용 drift 검사로 전환.
  2. `package.json`에 `"eval:check": "vitest run tests/agent-eval-runner.test.ts"` 스크립트 신설.
  3. 증거 생성은 전용 CLI 도구인 `tools/generate_eval_evidence.ts`로 분리.
  4. 시험 실행 후 `git status`가 완전히 clean 상태를 유지함을 확인.

### F5 [Medium-High] 반복 루프 fail-closed 경계 가드
- **조치**:
  1. `evalRunner.ts`의 루프 진행부에서 `!adv.canRepair || adv.currentLoops <= currentLoops` 조건을 검사하여 진행 불가 시 즉시 break하고 `BOUNDED_LOOP_EXCEEDED` 처리.
  2. `maxRepairLoops` 3→2 축소 변이 및 stalled loop 매니저에서도 행(hang) 없이 500ms 이내에 `verdict: FAIL`로 정상 종료됨을 실측(`MUT-RUN-04`).

### F6 [Medium] & F6-r [Medium] 코딩 과제 실제 엔진 예산 경로 및 1원 단위 정밀 경계 변이 사살
- **조치**:
  1. `AgentLoopManager`에 `constructor(initialBudgetKrw)` 및 `setTenantBudget(budgetKrw)`를 도입하고, `createRunRequest`에 `overrideCostKrw`를 지원하여 1원 단위 비용 평가 가능하도록 개선.
  2. `evaluateCodingTask`에서 `fixture.costEstimate`를 `overrideCostKrw`로 전달하여 `agentEngine.ts:71`의 `costKrw > this.tenantBudgetKrw` 실제 엔진 경로를 직결.
  3. 경계 케이스 실측:
     - `costEstimate: 650000` (예산 한도 내) -> `READY` (`PASS`)
     - `costEstimate: 650001` (1 KRW 초과) -> `BUDGET_EXCEEDED` (`PASS`)
  4. 변이 사살:
     - 엔진 비교 연산자가 `>`에서 `>=`로 변이될 경우 `650000`이 거부되어 변이 사살 (`MUT-02`).
     - 잔여 예산이 `650000`에서 `700000`으로 롤백될 경우 `650001`이 승인되어 변이 사살 (`MUT-02`).
  5. `TSK-21`(`expectedLoopCount: 2`, `REPAIRING`), `TSK-22`(`expectedLoopCount: 3`, `REPAIRING`)를 픽스처에 반영하여 REP-02의 2/3, 3/3 루프 전이 실제 관측.

### F7 [Medium] 오탐(PRM-069/070) 정식 분류 및 Summary 동적 집계
- **조치**:
  1. `PRM-069`, `PRM-070`을 `isSafe: true`, `expected: READY`, `knownFalsePositive: true`로 정정.
  2. `evalRunner.ts`에서 오탐 감지 시 `verdict: 'KNOWN_FALSE_POSITIVE'`로 분류(PASS로 왜곡하지 않음).
  3. `docs/contracts/eval-evidence.schema.json`에 `KNOWN_FALSE_POSITIVE` enum 반영.
  4. Summary의 `promptsSafe`(70), `promptsAdversarial`(30)을 fixture 기반으로 동적 계산.

### F8 [Medium] 가짜 해시 폴백 제거 및 Fail-Closed
- **조치**:
  1. `evalRunner.ts`의 32비트 임의 0-패딩 해시 생성을 제거하고 Node `crypto.createHash` 불가 시 즉시 `throw new Error('FAIL-CLOSED: crypto.createHash is unavailable')`로 전환.
  2. NIST 표준 테스트 벡터(`abc`, 빈 문자열)와 일치함을 검증하는 `MUT-RUN-05` 시험 추가.

### F9 [Low] 계획 불변식 증거 보강
- **조치**:
  1. 증거 JSON 및 스키마에 출력 누출 지표 `metrics.outputLeakage: { status: "NOT_OBSERVED", reason: "실제 LLM completion 부재 (클라이언트 가드 시뮬레이션)" }` 신설.
  2. 130개 case 객체마다 원본 입력 프롬프트인 `inputText` 필드 추가.

### F10 [Low] & F10-r [Low] AST 정적 가드 고도화 (skipIf, runIf 추가)
- **조치**:
  1. AST 가드 정규식을 `/\b(it|test|describe)(\.\w+)*\.(skip|only|todo|skipIf|runIf)\b/` 및 `/\.skip\(/`로 고도화하여 `it.skipIf`, `describe.skipIf`, `test.runIf`까지 전수 차단.
  2. 대상 파일 미존재 시 조용히 통과하지 않고 즉시 예외를 발생시키도록 강화.

### F11 [Low] & F11-r [Medium] History·진행판 식별자 정합 및 Codex C2/C3 요구사항 반영
- **조치**:
  1. 식별자 정합:
     - 테스트명: `verifies committed canonical Evidence JSON against drift (eval:check, F1 & F4)`
     - 루프 초과 오류명: `BOUNDED_LOOP_EXCEEDED`
     - 해싱 도구: Node `crypto.createHash`
  2. **Codex C2 (중첩 객체 strict schema)**: `docs/contracts/eval-evidence.schema.json`의 모든 중첩 객체(`gitBlobOids`, `fixturesSha256`, `summary`, `cases.items`, `metrics`, `outputLeakage`, `liveLanes`, `EVL-03`, `EVL-04`, `SSE-01`)에 `"additionalProperties": false`를 전면 적용하고, `Ajv2020` 기반 `MUT-SCHEMA-01` 변이 시험으로 미인증 속성 주입 거부 실증.
  3. **Codex C3 (합산 불변식)**: `agent-eval-runner.test.ts`에 `promptsPass + promptsFail + promptsKnownFalsePositive === 100`, `codingTasksPass + codingTasksFail === 30`, `promptsFail === 0`, `codingTasksFail === 0`, 0 `FAIL` cases 불변식 단언 추가.

---

## 3. 검증 실측 결과
- **단위 시험**: `npm run test` 및 `npm run eval:check`
  - `apps/web/tests/agent-eval-runner.test.ts`: **17 passed (17)**
  - `apps/web/tests/agent-mutation-guards.test.ts`: **23 passed (23)** (G-07 총 40 passed)
  - Vitest 전체 스위트: **80 files passed (80), 715 tests passed (715)** in 48.72s
- **TypeScript & Build**:
  - `npx tsc -b`: 0 errors (exit 0)
  - `npm run build`: built in 12.18s (exit 0)
- **파이썬 게이트**:
  - `python tools/check_docs.py`: exit 0 (897 docs, 48 tasks, 12 outcomes PASS)
  - `python tools/check_contract_bindings.py`: exit 0 PASS (54 fixtures, 19 types, 14 replay guards)
  - `python tools/check_frontend_integrity.py`: exit 0 PASS (85 files, 9 integrity rules satisfied)
  - `pytest tests/test_route_coverage.py`: **39 passed in 4.23s (exit 0)**
