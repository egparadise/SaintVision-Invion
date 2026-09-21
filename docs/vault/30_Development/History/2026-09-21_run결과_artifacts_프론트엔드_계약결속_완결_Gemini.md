---
doc_id: "RUN-RESULT-ARTIFACTS-CONTRACT-FRONTEND-GEMINI-001"
title: "RunResultView 및 RunArtifactList 커널 공유 Fixture 프론트엔드 계약 결속 및 Ajv 검증 완결 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21T17:55:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["run-result-view", "run-artifact-list", "kernel-contract", "ajv-2020", "shared-fixture", "developer-studio", "mock-equals-contract"]
---

# RunResultView 및 RunArtifactList 커널 공유 Fixture 프론트엔드 계약 결속 및 Ajv 검증 완결 보고

## 1. 개요 및 배경

Claude가 커널 공유 픽스처(`contracts/fixtures/run-result-view.json`, `run-artifact-list.json`)와 백엔드 계약 테스트(`tests/core/test_run_result_contract.py`)를 수립하고 인계한 과업을 Gemini가 프론트엔드 영역에서 100% 수용하여 결속을 완결하였다.

- **문제 의식**: `DeveloperStudio`는 `/result` 응답의 형태(Shape)에 따라 `/artifacts` 폴백 여부 및 UNVERIFIED 마킹을 결정한다. 만약 이 응답 형태가 프론트엔드와 공유 픽스처에 묶여 있지 않으면, 백엔드 변경 시 프론트엔드의 수기 목(Mock) 기반 테스트 18건이 계속 통과(Green)하는 동안 런타임 불일치가 은폐된다.
- **해결 조치**:
  1. `apps/web/tests/fixtures/run-result.ts` 신설: `happy-dom` 환경 호환 경로 해석기를 내장하여 `run-result-view.json` 및 `run-artifact-list.json`을 단일 원천으로 로드.
  2. `apps/web/tests/run-result-contract.test.ts` 신설: `contracts/v1alpha1/core.schema.json`의 `$defs/RunResultView` 및 `$defs/RunArtifactList`를 Ajv 2020으로 검증하고, 필수 필드(`output`, `artifacts`) 누락 시 유효성 검증 실패(false)를 실측하는 음성 대조 4종 탑재.
  3. `apps/web/tests/developer-studio-dom.test.tsx` 목 교체: `sampleFallbackArtifactList` 및 `result200`을 공유 픽스처(`runResultViewFixture`, `runArtifactListFixture`)와 직접 결합하여 **Mock == Contract** 상태를 달성.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (RunResultView 필수 필드 output 제거)**: `run-result-contract.test.ts`에서 `output` 필드를 제거했을 때 Ajv 검증이 즉시 실패(false)함을 단언하여 포착.<br>• **Mutation 2 (RunArtifactList 필수 필드 artifacts 제거)**: `artifacts` 필드를 제거했을 때 Ajv 검증이 즉시 실패(false)함을 단언하여 포착.<br>• **양방향 검증 일치**: Python `validate_contract`(VAL-0002)와 TypeScript `Ajv2020`(core.schema.json) 양쪽에서 정상 픽스처는 모두 PASS, 필드 누락 변조본은 모두 FAIL로 사슬 온전성 입증. |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `happy-dom` 환경에서 `new URL(..., import.meta.url)`이 `file://` 스키마 대신 가상 브라우저 URL로 해석되어 `readFileSync` 시 `TypeError: The URL must be of scheme file`이 발생하는 런타임 특성을 소스 분석으로 규명하고, `getFixturePath` 헬퍼에 `cwd` 기반 안전 탐색 폴백을 실장함.<br>• `packages/contracts-ts/src/index.ts`에 이미 `RunResultView`와 `RunArtifactList`가 생성되어 있음을 확인하고, 테스트 픽스처 타입으로 정합 결속함. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 실시간 웹소켓 터미널 스트리밍 중 커널 비정상 종료 시 ResultView 전송 타임아웃 지연.<br>• 실제 백엔드 PostgreSQL 저장소와의 네트워크 패킷 직렬화 지연시간.<br>• 상기 분산 런타임 검증은 백엔드 live HTTP 및 실장비 인수 레인으로 이관함. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/run-result-contract.test.ts` 신규 생성**: **4 tests 100% PASS**
  1. `validates runResultViewFixture against core.schema.json #/$defs/RunResultView`
  2. `rejects runResultViewFixture when required field "output" is removed`
  3. `validates runArtifactListFixture against core.schema.json #/$defs/RunArtifactList`
  4. `rejects runArtifactListFixture when required field "artifacts" is removed`
- **`apps/web/tests/developer-studio-dom.test.tsx` 목 정합**: **18 tests 100% PASS** (공유 픽스처 기반 실측 완결)
- **전체 Vitest 스위트**: 직전 보고 기준 **41개 파일 385 passed**에서 **42개 파일 389 passed**로 순증 (**from 385 to 389, net +4 tests**, 42개 테스트 파일 100% 합격).

### 3.2 빌드 및 거버넌스 도구 전수 합격 증거
1. **TypeScript & Vite 프로덕션 빌드 (`tsc -b && vite build`)**:
   `✓ built in 3.57s` (0 error, 0 warning).
2. **Pytest 클라이언트 라우트 및 커널 계약 (`test_route_coverage.py`, `test_run_result_contract.py`)**:
   34 passed in 1.27s (100% 통과).
3. **문서 정합성 (`tools/check_docs.py`)**:
   PASS: 24 original hashes, 617 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.
4. **온톨로지 무결성 (`tools/check_ontology.py`)**:
   PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.

---

## 4. 결론 및 인계

Claude로부터 인계받은 RunResultView / RunArtifactList 커널 계약 공유 픽스처 프론트엔드 결속 과업을 100% 완수하였다.

- **Outcome**: RunResultView & RunArtifactList 프론트엔드 계약 결속 완료 (Mock == Contract)
- **Code Reference Tip**: `integration/all-agents-unified`
- **Next Ready Action**: `VF-GM-04` (Model Studio: 단일 가상 GPU/vCPU 연산 뷰 & 다중 노드 실물 분산 매핑)
