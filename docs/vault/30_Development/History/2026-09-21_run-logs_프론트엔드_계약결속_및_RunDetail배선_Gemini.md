---
doc_id: "RUN-LOGS-CONTRACT-FRONTEND-GEMINI-001"
title: "RunLogView 커널 공유 Fixture 프론트엔드 계약 결속, RunDetail 실배선 및 Ajv 검증 완결 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21T18:20:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["run-logs", "run-log-view", "kernel-contract", "ajv-2020", "shared-fixture", "run-detail", "claude-handoff"]
---

# RunLogView 커널 공유 Fixture 프론트엔드 계약 결속, RunDetail 실배선 및 Ajv 검증 완결 보고

## 1. 개요 및 배경

Claude가 커널 공유 픽스처(`contracts/fixtures/run-log-view.json`)와 백엔드 계약 테스트(`tests/core/test_run_log_contract.py`)를 수립하고 인계한 과업(`c192cdc`)을 Gemini가 프론트엔드 영역에서 100% 수용하여 결속을 완결하였다.

- **Claude 실측 드리프트 지적 수용**:
  - `apps/web/src/contracts/types.ts:563`의 수기 `RunLogView` 인터페이스에서 `source: 'execution-kernel' | string`을 `source: 'execution-kernel'` const로 정정.
  - `truncated?: boolean | null` 및 `absentReason?: string | null` 옵셔널 필드를 스키마 필수 필드인 `truncated: boolean | null`, `absentReason: string | null`로 정정 (`packages/contracts-ts/src/index.ts:725`와 100% 일치).
- **프론트엔드 어댑터 및 컴포넌트 배선**:
  - `apps/web/src/shared/api/runLogObservation.ts` 신설: `/v1/projects/{project}/runs/{run_id}/logs` 엔드포인트 호출 및 `source`, `runId`, `redacted`, `truncated`, `absentReason` 무결성을 검증하는 런타임 가드 내장.
  - `apps/web/src/features/runs/RunDetail.tsx` 실배선: 기존의 하드코딩된 더미 로그 텍스트를 제거하고, Tab 2 선택 시 실제 커널 로그를 조회하여 표준 출력(`run-log-stdout`), 표준 에러(`run-log-stderr`), 민감정보 마스킹 배지(`run-logs-redacted-badge`), 로그 잘림 배지(`run-logs-truncated-badge`), 미발행 사유 배너(`run-logs-absent`), 서버 오류 경고(`role="alert"`)를 렌더링하도록 개편.
- **계약 검증 및 픽스처 결속**:
  - `apps/web/tests/fixtures/run-log.ts` 신설: happy-dom 호환 공유 픽스처 로더 탑재.
  - `apps/web/tests/run-log-contract.test.ts` 신설 (6 tests): Ajv 2020 기반 `core.schema.json#/$defs/RunLogView` 유효성 및 필수 필드/const 누락 거부 검증.
  - `apps/web/tests/run-detail-logs-dom.test.tsx` 신설 (8 tests): RunDetail 탭 전환, 픽스처 렌더링, redacted/truncated/absentReason 분기, 네트워크 오류 배너, Zero-Mock 계약 거절 검증.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (RunDetail 에러 알림 무력화)**: `RunDetail.tsx`에서 `logError && (`를 `false && (`로 변경하여 에러 배너 생성을 억제함.<br>→ **포착 단언 오류**: `AssertionError: expected null not to be null` at `tests/run-detail-logs-dom.test.tsx:224:28` (`expect(errorAlert).not.toBeNull()`). 사살 완료(KILLED).<br><br>• **Mutation 2 (absentReason 분기 무시 및 허위 로그 노출)**: `RunDetail.tsx`에서 `logView.absentReason ? (`를 `false ? (`로 변경하여 미발행 사유 배너를 무시함.<br>→ **포착 단언 오류**: `AssertionError: expected null not to be null` at `tests/run-detail-logs-dom.test.tsx:169:26` (`expect(absentEl).not.toBeNull()`). 사살 완료(KILLED).<br><br>• **Mutation 3 (runLogObservation source 계약 검사 무력화)**: `runLogObservation.ts`에서 `if (result.source !== 'execution-kernel')` 가드를 주석 처리함.<br>→ **포착 단언 오류**: `AssertionError: promise resolved "{ …(7) }" instead of rejecting` at `tests/run-detail-logs-dom.test.tsx:242:54` (`await expect(fetchRunLogs('prj_test', 'run_test')).rejects.toThrow(...)`). 사살 완료(KILLED). |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `services/control-plane/src/inv/app.py:418`의 `@api.get("/v1/projects/{project}/runs/{run_id}/logs")` 라우트와 `result_view.py:232`의 `_checked("RunLogView", result)` 반환 계약을 소스 분석으로 대조 확인.<br>• `RunDetail.tsx`의 Tab 2가 기존에는 정적 mock 텍스트만 표시하고 API와 결속되지 않았음을 파악하고, `activeTab === 'logs'` 시점에 `fetchRunLogs`를 호출하여 실제 상태와 동기화되도록 수정. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 실시간 대용량 로그 스트리밍 시 WebSocket/SSE 재연결 백오프 및 P95 지연시간 실측.<br>• 분산 다중 노드 환경에서의 프로세스 표준 출력 flush 지연으로 인한 일시적 로그 부재 레이스 컨디션.<br>• 상기 분산 네트워크 지연 검증은 E2E 실장비 인수 트랙(VF-GM-06)으로 이관함. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/run-log-contract.test.ts` 신규 생성**: **6 tests 100% PASS**
  1. `validates runLogViewFixture against core.schema.json #/$defs/RunLogView`
  2. `rejects runLogViewFixture when required field "source" is invalid (not "execution-kernel")`
  3. `rejects runLogViewFixture when required field "stdout" is removed`
  4. `rejects runLogViewFixture when required field "truncated" is removed`
  5. `rejects runLogViewFixture when required field "absentReason" is removed`
  6. `rejects runLogViewFixture when required field "redacted" is removed`
- **`apps/web/tests/run-detail-logs-dom.test.tsx` 신규 생성**: **8 tests 100% PASS**
  1. `Scenario 1: Switches to logs tab and renders kernel stdout from shared fixture`
  2. `Scenario 2: Renders redacted badge when kernel marks sensitive content redacted`
  3. `Scenario 3: Renders truncated badge when output exceeded max buffer`
  4. `Scenario 4: Renders absentReason notice and suppresses empty log sections when logs absent`
  5. `Scenario 5: Renders stderr in red text when present`
  6. `Scenario 6: Displays role="alert" banner on network/server failure without fabricating fallback fake logs`
  7. `Scenario 7: fetchRunLogs strictly rejects non-"execution-kernel" sources (Zero-Mock)`
  8. `Scenario 8: fetchRunLogs strictly rejects invalid redacted boolean (Contract Type Guard)`
- **전체 Vitest 스위트**: 직전 보고 기준 **44개 파일 409 passed**에서 **46개 파일 423 passed**로 순증 (**from 409 to 423, net +14 tests**, 46개 테스트 파일 100% 합격).

### 3.2 빌드 및 거버넌스 도구 전수 합격 증거
1. **TypeScript & Vite 프로덕션 빌드 (`tsc -b && vite build`)**:
   `✓ 92 modules transformed. ✓ built in 4.05s` (0 error, 0 warning).
2. **Pytest 커널 계약 (`tests/core/test_run_log_contract.py`)**:
   `3 passed in 2.54s` (100% 합격).
3. **문서 정합성 (`tools/check_docs.py`)**:
   `PASS: 24 original hashes, 622 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.`
4. **온톨로지 무결성 (`tools/check_ontology.py`)**:
   `PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.`

---

## 4. 결론 및 인계

Claude로부터 인계받은 `RunLogView` 커널 계약 공유 픽스처 프론트엔드 결속 및 `RunDetail` 실배선 과업을 100% 완결하였다.

- **Outcome**: RunLogView 프론트엔드 계약 결속 및 RunDetail 배선 완료 (Mock == Contract)
- **다음 작업**: 보강 로드맵 카드의 최종 완결 카드인 `VF-GM-06` (외부 HTTPS, Browser Matrix, Rollback 및 브라우저 인수 보고서 작성) 진행.
