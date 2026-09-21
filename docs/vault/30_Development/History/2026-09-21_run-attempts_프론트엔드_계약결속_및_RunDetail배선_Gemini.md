---
doc_id: "RUN-ATTEMPTS-CONTRACT-FRONTEND-GEMINI-001"
title: "RunAttemptList 커널 공유 Fixture 프론트엔드 계약 결속, RunDetail 실배선 및 Ajv 검증 완결 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21T18:40:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["run-attempts", "run-attempt-list", "kernel-contract", "ajv-2020", "shared-fixture", "run-detail", "claude-handoff"]
---

# RunAttemptList 커널 공유 Fixture 프론트엔드 계약 결속, RunDetail 실배선 및 Ajv 검증 완결 보고

## 1. 개요 및 배경

Claude가 커널 공유 픽스처(`contracts/fixtures/run-attempt-list.json`), 백엔드 계약 테스트(`tests/core/test_run_attempt_contract.py`), 그리고 수기 타입 전수 훑기 보고서(`d416fe5`, `d0d41c3`)를 통해 인계한 `RunAttemptList` 과업을 Gemini가 프론트엔드 전 영역에서 100% 수용하여 결속을 완결하였다.

- **Claude 실측 드리프트 4종 전수 정정**:
  - `apps/web/src/contracts/types.ts`:
    1. `(a) const 무력화 해소`: `RunAttemptList.source: 'execution-kernel' | string`을 `source: 'execution-kernel'` const로 잠금.
    2. `(b) required->optional 왜곡 해소`: envelope `nextCursor?:`를 `nextCursor: number | null`로 정정하고, item의 `commandId`, `stopReceiptId`, `exitCode`, `reason`, `evidenceId`를 옵셔널 `?:`에서 필수 필드 `: ... | null`로 정정.
    3. `(c) 필드 누락`: 계약 명세 전수 대조 결과 누락 없음 확인.
    4. `(d) nullability 좁힘 역방향 왜곡 해소 (가장 위험)`: item의 `startedAt: string` 및 `nodeId: string`을 계약 정본과 일치하도록 `string | null`로 확장하여, 미배정(nodeId: null) 및 시작 대기(startedAt: null) attempt 응답 시 프론트엔드가 크래시되는 결함을 원천 방지함.
    - 추가로 `RunResultView` 및 `RunArtifactList`의 잔여 수기 드리프트(`source` const, required nullable 필드 등)도 함께 완전 정합함.
- **프론트엔드 어댑터 및 컴포넌트 실배선**:
  - `apps/web/src/shared/api/runAttemptObservation.ts` 신설: `/v1/projects/{project}/runs/{run_id}/attempts` 엔드포인트 호출 및 `source`, `runId`, `attempts` 배열, `count`, `nextCursor`, 각 attempt의 8대 필수 필드 무결성을 검증하는 Zero-Mock 런타임 가드 내장.
  - `apps/web/src/features/runs/RunDetail.tsx` 실배선: Tab 6 `6. 시도 이력 (Attempts)`를 신설하여, 활성화 시 실제 커널 시도 목록을 조회하고 출처 배지(`run-attempts-source-badge`), 노드 ID(`run-attempt-node-1`), 시작 시각(`run-attempt-started-1`), 종료 코드(`run-attempt-exit-1`), 사유, 명령 ID, 영수증 ID를 렌더링하며, 미배정/시작 대기 상태의 null 안전 처리, 빈 상태 알림(`run-attempts-empty`), 서버 장애 경고(`role="alert"`)를 완비함.
- **계약 검증 및 픽스처 결속**:
  - `apps/web/tests/fixtures/run-attempt.ts` 신설: happy-dom 호환 공유 픽스처 로더 탑재.
  - `apps/web/tests/run-attempt-contract.test.ts` 신설 (9 tests): Ajv 2020 기반 `core.schema.json#/$defs/RunAttemptList` 유효성, envelope 필수 필드 및 attempt 8대 필수 필드 누락 거부, nullable 필드 수용성 검증.
  - `apps/web/tests/run-detail-attempts-dom.test.tsx` 신설 (8 tests): RunDetail 탭 전환, 픽스처 렌더링, nodeId/startedAt null 처리, 빈 상태, 네트워크 오류 배너, Zero-Mock 어댑터 계약 가드 검증.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (fetchRunAttempts source 계약 검사 무력화)**: `runAttemptObservation.ts`에서 `if (result.source !== 'execution-kernel')` 검사를 주석 처리함.<br>→ **포착 단언 오류**: `AssertionError: promise resolved "{ source: 'third-party-kernel', …(4) }" instead of rejecting` at `tests/run-detail-attempts-dom.test.tsx:196:64` (`await expect(fetchRunAttempts('prj_test_01', 'run_test_01')).rejects.toThrow(...)`). 사살 완료(KILLED).<br><br>• **Mutation 2 (RunDetail 에러 배너 role="alert" 무력화)**: `RunDetail.tsx`에서 `role="alert"`를 `role="status"`로 변경함.<br>→ **포착 단언 오류**: `AssertionError: expected null not to be null` at `tests/run-detail-attempts-dom.test.tsx:186:23` (`expect(alert).not.toBeNull()`). 사살 완료(KILLED).<br><br>• **Mutation 3 (Ajv 스키마 검증 additionalProperties 무단 주입)**: `run-attempt-contract.test.ts`의 `nullableValid` attempt 객체에 스키마 미정의 필드 `unauthorizedExtraProperty: true`를 주입함.<br>→ **포착 단언 오류**: `AssertionError: [{"instancePath":"/attempts/0","schemaPath":"#/additionalProperties","keyword":"additionalProperties","params":{"additionalProperty":"unauthorizedExtraProperty"},"message":"must NOT have additional properties"}]: expected false to be true // Object.is equality` at `tests/run-attempt-contract.test.ts:143:92`. 사살 완료(KILLED). |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `services/control-plane/src/inv/app.py:423-427`의 `@api.get("/v1/projects/{project}/runs/{run_id}/attempts")` 및 `@api.get("/v1/runs/{run_id}/attempts")` 라우트 확인.<br>• `services/control-plane/src/inv/result_view.py:266`의 `_checked("RunAttemptList", ...)` 호출을 통해 커널 백엔드가 동일한 스키마로 자체 검증하고 있음을 확인.<br>• `contracts/v1alpha1/core.schema.json` lines 3452~3589의 `RunAttemptObservation` 및 `RunAttemptList` 정본 정의를 대조하여 필수 필드 5개(envelope) 및 8개(attempt)의 nullability와 const 속성을 도출함. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 다중 클러스터 분산 환경에서 attempt 페이징(`after`, `limit`, `nextCursor`)이 2048건 이상의 초대형 배치 작업에서 동작할 때의 메모리 프로파일.<br>• 상기 분산 대용량 페이징은 실장비 통합 성능 시험 트랙에서 검증 예정. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/run-attempt-contract.test.ts` 신규 생성**: **9 tests 100% PASS**
  1. `validates runAttemptListFixture against core.schema.json #/$defs/RunAttemptList`
  2. `rejects runAttemptListFixture when required envelope field "source" is not "execution-kernel"`
  3. `rejects runAttemptListFixture when required envelope field "nextCursor" is missing`
  4. `rejects runAttemptListFixture when attempt required field "commandId" is missing`
  5. `rejects runAttemptListFixture when attempt required field "stopReceiptId" is missing`
  6. `rejects runAttemptListFixture when attempt required field "exitCode" is missing`
  7. `rejects runAttemptListFixture when attempt required field "reason" is missing`
  8. `rejects runAttemptListFixture when attempt required field "evidenceId" is missing`
  9. `accepts null values for startedAt and nodeId in attempt items (contract richness: nullable required fields)`
- **`apps/web/tests/run-detail-attempts-dom.test.tsx` 신규 생성**: **8 tests 100% PASS**
  1. `Scenario 1: Switches to attempts tab and renders kernel attempt row with nodeId and startedAt from shared fixture`
  2. `Scenario 2: Renders attempt with nullable startedAt: null and nodeId: null without crashing (contract richness)`
  3. `Scenario 3: Renders empty state notice when attempts array is empty`
  4. `Scenario 4: Error handling - server 500 rejection displays role="alert" with message`
  5. `Scenario 5: fetchRunAttempts adapter rejects non-canonical source mutation`
  6. `Scenario 6: fetchRunAttempts adapter rejects missing runId`
  7. `Scenario 7: fetchRunAttempts adapter rejects invalid non-null/non-string nodeId in attempt`
  8. `Scenario 8: fetchRunAttempts adapter serializes after and limit query params correctly`

- **테스트 카운트 변천 기준선**:
  - VF-GM-06 완료 시점: 49개 테스트 파일, **447건 통과**
  - RunAttemptList 결속 완료 시점: 51개 테스트 파일, **464건 통과 (from 447 to 464, 순증 +17건)**

### 3.2 빌드 및 통합 검증 지표
- **Web Production Build (`npm --prefix apps/web run build`)**:
  - `tsc -b && vite build` 통과 (exit code 0, 3.18초 완료, 93 modules transformed).
- **Backend Contract Pytest**:
  - `.venv/Scripts/pytest.exe tests/core/test_run_log_contract.py tests/core/test_run_attempt_contract.py` 통과 (exit code 0, 7 passed in 0.49s).
- **Document & Ontology Validation**:
  - `python tools/check_docs.py` 100% PASS.
  - `python tools/check_ontology.py` 100% PASS.
  - `python tools/sync_obsidian.py --apply` 100% 동기화 (1420 files).

---

## 4. 인계 및 다음 권고

- **Claude에게 인계**:
  - `RunAttemptList` 프론트엔드 수기 타입 정합, Zero-Mock 어댑터 신설, Ajv 2020 계약 테스트, RunDetail Tab 6 실배선 및 DOM 8종 검증이 100% 완결되었음을 회신함.
  - Claude가 권고한 생성 타입(`packages/contracts-ts`) re-export 체제로의 장기 전환 방향에 동의하며, 우선순위가 높은 미결속 항목인 `ProblemDetails`의 백엔드 self-validate 앵커 구축 시 Codex/Claude와 즉시 프론트 결속을 공조할 준비가 됨.
- **다음 작업**:
  - 보강 로드맵 VF-GM-01 ~ VF-GM-06 전수 완료 상태 점검 및 통합 브랜치 PR 준비.
