---
doc_id: "GEMINI-S10-FE-SCENARIO-MATRIX-20260928"
title: "S10-FE Multi-LLM 어댑터 적합성·실패 분류·계보 역추적·배포 Digest 시나리오 매트릭스 (Gemini)"
version: "1.0.2"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T10:00:00+09:00"
source_of_truth: "Git"
tags: ["s10-fe", "acceptance-matrix", "mlops", "lineage", "adapter-conformance", "deployment-digest", "gemini"]
---

# S10-FE Multi-LLM 어댑터 적합성·실패 분류·계보 역추적·배포 Digest 시나리오 매트릭스 (Gemini)

> **관련 계약 및 선행 문서**:
> - [[전체 개발 진행 현황]]
> - [[Gemini 작업 현황]]
> - [[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]
> - [[2026-09-10_01-45-00_KST_S10-FE_Gemini_AI도구_모델계보_배포_개발과정]]
> - [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]
> - [[설계 충돌 정정 및 ADR]] (ADR-004, ADR-010, ADR-011, ADR-012, ADR-075, ADR-077)
> - `apps/web/src/features/mlops/ModelLineageView.tsx`
> - `apps/web/src/features/mlops/mlopsEngine.ts`
> - `apps/web/tests/model-lineage.test.ts`
> - `apps/web/tests/fixtures/model-lineage.ts`
> - `src/saintvision/adapters/contract.py`
> - `src/saintvision/adapters/conformance.py`
> - `src/saintvision/services/lineage.py`
> - `src/saintvision/services/eval_execution.py`
> - `src/saintvision/db/models/evaluation.py`
> - `src/saintvision/errors.py`
> - `services/control-plane/src/inv/app.py`
> - `services/control-plane/src/inv/model_view.py`
> - `migrations/versions/0004_s10_lineage.py`
> - `tests/test_lineage.py`
> - `tests/test_deployment_guard.py`
> - `tests/test_eval_execution.py`

---

## 1. 개요 및 수용 목표 (OUT-10 / AC-10)

본 문서는 SaintVision 제어 평면 및 MLOps 관측·배포 서브시스템의 **S10-FE (Multi-LLM 어댑터 적합성·실패 분류·모델 계보 역추적·배포 Digest 검증)** 트랙을 완결하기 위해 수립된 **docs-only 시나리오 매트릭스 정본(v1.0.2)**이다.

본 매트릭스는 코디네이터 지침, Claude 독립 UI 경로 검토(`issuecomment-5860935552`), Codex 계약 축 독립 검토(`issuecomment-5860950225`), Codex 차단지도([[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]), Claude 실 PG 교차 증거([[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]])의 지적 사항(N1~N4, 6, F-R1~F-R4)을 전수 반영하여 프런트엔드(`apps/web/src/features/mlops/ModelLineageView.tsx`, `mlopsEngine.ts`, `tests/model-lineage.test.ts`)와 백엔드 코어(`src/saintvision/services/lineage.py`, `eval_execution.py`, `models/evaluation.py`, `errors.py`)의 실제 코드 및 단언을 1:1로 엄격하게 대조하여 작성되었다.

### 1.1 핵심 작성 및 거버넌스 원칙 (Zero Fake / Honest Boundary)
1. **화면 표시 상태와 백엔드 제어 평면 정본의 엄격한 분리**:
   - `ModelLineageView.tsx` 화면은 현재 백엔드 제어 평면에 외부 노출용 HTTP 계보 조회/기록(trace/record) API가 부재함을 인식하고, 컴포넌트 마운트 시 가짜 파이프라인 그래프나 합성 평가 점수를 일절 생성하지 않는다 (`initialLineages = []`).
   - 제어 평면 정본 계보 추적 함수는 내부 Python 서비스 `trace_model(session, *, tenant_id, model_version_id)`([`src/saintvision/services/lineage.py:343-345`](file:///D:/Project/SaintVisionI-Invion/https-github.com-egparadise-SaintVision-Invion.git/.worktrees/gemini-fe-followups/src/saintvision/services/lineage.py#L343-L345))로 존재하며, 키워드 인자 `tenant_id`와 `model_version_id`를 필수로 요구하고 `datasets`, `commits`, `images`, `evaluations`, `approvals`, `missing`, `dangling`, `fullyTraceable`을 반환한다.
   - saintvision lineage HTTP API 부재 시 프런트엔드는 안내 배너(`lineage-unexposed-notice`, `role="status"`)와 빈 상태 화면(`lineage-empty-state`, `role="status"`)을 렌더링하며, 네트워크 요청은 0건(Zero Network Calls)을 유지한다.
   - 단, 백엔드 제어 평면에는 별도의 모델 커밋먼트 조회 엔드포인트(`/v1/projects/{project}/models/{model_id}/versions/{version}/commitment`, `services/control-plane/src/inv/app.py:449-452`, `model_view.py:37-69`)가 존재하여 `manifestHash`와 `sourceRunId`를 반환하나, 프런트엔드는 이를 호출하지 않는다(0건 호출). ADR-010 보강에 따라 S10 모델 레지스트리와 커널 실행 매니페스트는 별개 경계로 격리된다.
2. **어댑터 적합성 및 지연시간/처리량의 정적 리터럴(검증 아님) 명시**:
   - `mlopsEngine.ts:37-63`의 `verifyProviderConformances()`는 Codex, Claude, Local-vLLM 3개 제공자에 대해 `conformancePassed: true`, `contractVersion: 'v1.0.0-ADR-004'`, 프로토콜 목록, 지연시간/처리량(`142 ms`, `156 ms`, `48 ms`, `68.5 tok/s`, `64.2 tok/s`, `112.0 tok/s`)을 하드코딩하여 반환하는 **상수 배열(Fixture-only / Not-measured)**이다.
   - 따라서 UI에 노출되는 `100% CONFORMING` 배지(`ModelLineageView.tsx:442`), `100% 적합` 카드(:103-104), `100% 준수합니다` 안내문(:410)은 실제 제공자 프로브 결과가 아닌 **정적 리터럴(검증 아님)**이다.
   - 실제 제어 평면 정본 계약 버전은 `src/saintvision/adapters/contract.py`의 `CONTRACT_VERSION = "1.0.0"` 및 `ProviderAdapter` 8개 동작 명세이며, UI의 `v1.0.0-ADR-004`는 UI 상수에 불과하다 (정본 ADR-004는 ContextBundle/W3C traceparent/inv.* 규격임).
   - 실제 UI 소스코드(`ModelLineageView.tsx:445-446`)에 `title` 속성이 없으므로, 툴팁 고지 문구를 전면 삭제한다.
3. **클라이언트 배포 시뮬레이션과 백엔드 정본 불변식의 불일치 고지**:
   - 프런트엔드의 `deployModel()`(`mlopsEngine.ts:69-103`)은 사용자 입력 `approvalId`를 조합하여 `sha256(modelId:datasetDigest:sourceCommitSha:approvalId)`로 digest를 직접 합성한다.
   - 이는 배포 다이제스트를 호출자 입력이 아닌 DB `ModelVersion.content_sha256`에서 고정하는 백엔드 코어 불변식(`src/saintvision/services/lineage.py:534`)과 정반대로 동작하는 **client-only 배포 모의 시뮬레이션(백엔드 불변식과 불일치)**이다.
   - 승인 게이트 역시 단순히 문자열이 `apr_`로 시작하는지만 검사(`mlopsEngine.ts:78`)하며, 성공 알림은 `[모의 시뮬레이션]` 배너(`ModelLineageView.tsx:64`)를 표출함에도 노드 6 라벨은 `Production Live`(:386)로 표기되는 UI 결함이 존재함을 정직하게 기록한다 (차기 FE 결함 카드로 정비 예정).
4. **오류 코드의 정본 위치 및 클라이언트 전용 코드 구분**:
   - `DEPLOYMENT_GATED`는 `apps/web/src/features/mlops/mlopsEngine.ts`에만 존재하는 **UI-local 클라이언트 전용 시뮬레이션 마커**이며, 백엔드 정본 오류 코드(RFC 9457 / `ErrorCategory`)가 아니다.
   - 제어 평면 정본 오류 코드는 `src/saintvision/errors.py:126-149`에 정의된 정본 오류(`AUTH-APPROVAL-DIGEST-MISMATCH`, `AUTH-APPROVAL-EXPIRED`, `VAL-SCHEMA`, `RES-ARTIFACT-NOT-FOUND`, `AUTH-INVALID-CREDENTIAL` 등)이다 (`contracts/` 디렉터리가 아닌 `src/saintvision/errors.py`에 실재).
5. **승인 만료 시 백엔드 오류 코드 단일화**:
   - `record_deployment()`(`src/saintvision/services/lineage.py:501-512`)는 승인 유효 구간 검증 실패(`not approval.decided_at <= now < approval.expires_at`) 시 `AUTH_APPROVAL_DIGEST_MISMATCH` ("approval is not valid at the recorded deployment time")를 반환한다.
   - `AUTH-APPROVAL-EXPIRED` 상수는 `errors.py:149`에 정의되어 있으나 `lineage.py`는 이를 임포트하지 않으며 Run 승인 전용(`services/runs.py:434`)이므로, DIG-03의 기대 오류 코드는 `AUTH-APPROVAL-DIGEST-MISMATCH` 단일값으로 엄격히 고정한다.
6. **Active 배포 유일성 키 범위의 정확한 한정**:
   - DB 마이그레이션의 부분 유니크 인덱스(`migrations/versions/0004_s10_lineage.py:277-279`)는 `(tenant_id, model_version_id, environment) WHERE status = 'active'`이며, `record_deployment()`의 `superseded` 갱신(`lineage.py:520-526`) 또한 동일 `model_version_id`와 `environment`로 한정된다.
   - 따라서 보장되는 유일성은 환경 전체가 아닌 **tenant·model_version·environment당 active 1개**이다 (서로 다른 모델 버전은 동일 환경에서 동시에 active 상태 가능).
7. **인용 시험 파일 및 행(File:Line) 실측 단언 검증**:
   - `apps/web/tests/model-lineage.test.ts:22-35`는 Codex와 Claude만 단언하며(Local-vLLM 미단언), 프로토콜은 `SSE-v2`와 `W3C-TraceContext`만 단언(`ProblemDetails` 미단언)함을 정확히 서술한다.
   - `LIN-03`(test:51-78)은 클라이언트 인메모리 엔진 단언일 뿐이며 DOM 단언이 없고, 기본 제품 상태(`App.tsx:834`, 빈 계보)에서는 결과가 나올 수 없는 **Fixture 전용(AC-10 제품 완료 증거 아님)**임을 명시한다.
   - `LIN-04`는 버튼의 `.disabled === true`만 단언하며(`aria-disabled` 미단언, 조치 안내 span 미단언), fixture의 staging 모델은 정확도 81.2%로 게이트 미달 모델(`apps/web/tests/fixtures/model-lineage.ts:40`)임을 명시한다.
   - `FLT-01`의 `errored` vs `failed` 분리 근거로 `src/saintvision/services/eval_execution.py`, `tests/test_eval_execution.py:192-209` (`{"errored": 2}`), 및 `:333, :366`(`test_a_forbidden_case_declaring_nothing_forbidden_is_refused`, `assert outcome == "errored"`, `assert not run.passed_gate`)을 인용한다.
   - `FLT-03`의 `test_lineage.py:316`은 4종 필수 계보 전체 누락을 단언(`:332-334`)함을 정확히 적고, 릴리스 거절 시험(`test_lineage.py:431`, `:454`에서 `assert "not fully traceable" in caught.value.message` 단언)을 인용한다. 릴리스 차단은 `trace["missing"]`이 존재할 때만 발생하며(`lineage.py:328-336`), `dangling` 엣지는 릴리스 차단 조건이 아님을 정확히 기술한다.
8. **미실행 돌연변이 및 물리 장비 경계의 정직한 표기**:
   - 외부 LLM 어댑터 실제 프로브 및 자격증명 연동 돌연변이는 `WIRE-PLANNED (CX-02 credential 경계 대기)`로 표기한다.
   - 물리 노드 5대 PC 분산 환경 실측 항목은 `UNMEASURED (5노드 랩 후)`로 표기하여 임의 합격을 방지한다.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **ADP** | **Multi-LLM Provider 어댑터 적합성 [Fixture-Only]**<br>(Multi-LLM Adapter Conformance) | `mlopsEngine.ts`<br>`ModelLineageView.tsx`<br>`adapters/contract.py`<br>`adapters/conformance.py` | • UI 적합성 배열은 **상수 하드코딩(검증 아님 / Fixture-only)** 표기<br>• 정본 계약 버전(`1.0.0`, `adapters/contract.py`)과 UI 상수(`v1.0.0-ADR-004`) 분리<br>• 지연시간/처리량 수치는 **정적 리터럴(측정 아님)** 표기 (툴팁 없음)<br>• 실제 외부 호출 및 프로브는 `WIRE-PLANNED (CX-02 credential 대기)` |
| **FLT** | **평가 실패 분류 및 계보 이상 탐지 [Internal-Service]**<br>(Failure Categorization & Trace Anomalies) | `services/eval_execution.py`<br>`db/models/evaluation.py`<br>`services/lineage.py`<br>`tests/test_lineage.py` | • Golden Suite 평가 결과 분류: 실행 에러(`errored`) vs 단언 실패(`failed`) 분리 (`test_eval_execution.py:192-209, :366`)<br>• 금지 행동 위반(`violated=True`) 시 `outcome='failed'` 강제 및 `passed_gate=False` 고정 (`models/evaluation.py:134, 183`)<br>• 계보 역추적 결손 분류: 필수 요소 누락(`missing`, 4종) vs DB 고아 참조(`dangling`)<br>• 릴리스 차단은 `missing` 존재 시 발생 (`test_lineage.py:431, :454`, `dangling`은 릴리스 차단 조건 아님) |
| **LIN** | **End-to-End 계보 역추적 및 무합성 가드**<br>(Reverse Lineage Query & Zero Synthesis) | `ModelLineageView.tsx`<br>`mlopsEngine.ts`<br>`services/lineage.py`<br>`inv/app.py` | • 제어 평면 정본은 `trace_model(session, *, tenant_id, model_version_id)` (`services/lineage.py:343-345`)이며, HTTP 역추적 라우트는 미제공<br>• saintvision lineage API 미노출 시 정직한 고지 (`lineage-unexposed-notice`, `lineage-empty-state`)<br>• 미노출 시 가짜 평가 점수(81.2%, 94.8% 등) DOM 렌더링 0건 보장<br>• 다이제스트/커밋 쿼리는 **Fixture 전용 인메모리 필터(AC-10 제품 완료 증거 아님)**<br>• UI 배포 시 approvalId 기반 digest 합성은 **client-only 배포 시뮬레이션(백엔드 불변식과 불일치)**<br>• 별도 `/v1 .../commitment` 엔드포인트(`app.py:449`)는 FE 미사용 (0건 호출) |
| **DIG** | **배포 Digest 고정 및 승인 결속 가드 [Internal-Service]**<br>(Deployment Digest & Governance Guard) | `services/lineage.py`<br>`test_deployment_guard.py`<br>`test_lineage.py`<br>`0004_s10_lineage.py` | • 배포 다이제스트는 호출자 입력이 아닌 Model Version의 `content_sha256`에서 고정 (`lineage.py:454, 534`)<br>• 승인 다이제스트 불일치 및 승인 시효 만료 시 `AUTH-APPROVAL-DIGEST-MISMATCH` 차단 (`lineage.py:510-517`)<br>• 내부 Python 서비스 함수로 HTTP 경로 없음 (내부 서비스, 403은 ErrorCategory 매핑일 뿐)<br>• Active 유일성: **tenant·model_version·environment당 active 1개** (`0004_s10_lineage.py:277-279`) |

---

## 3. 세부 시나리오 매트릭스 (15대 시나리오)

### 3.1 Multi-LLM 어댑터 적합성 (Adapter Conformance, ADP-01 ~ ADP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **ADP-01** | **Multi-LLM 어댑터 스키마 및 프로토콜 UI 상수 단언 [Fixture-Only]** | `mlopsEngine.ts`<br>`ModelLineageView.tsx` | MLOps 관리자 초기화 | `verifyProviderConformances()` 호출 및 표 렌더링 | • UI 상수 버전: `v1.0.0-ADR-004` (정본은 `adapters/contract.py`의 `1.0.0`)<br>• 지원 프로토콜: `SSE-v2`, `W3C-TraceContext`<br>• DOM 배지: `span:has-text("100% CONFORMING")` | • **Fixture 전용 단언**: `tests/model-lineage.test.ts:22-35`는 Codex와 Claude 2개 제공자의 하드코딩된 UI 상수만을 단언함 (`test.ts:22-28`, Local-vLLM은 테스트에서 미단언).<br>• 프로토콜 단언은 `SSE-v2`와 `W3C-TraceContext` 2종만 검증 (`test.ts:31-34`, `ProblemDetails` 미단언).<br>• 실제 백엔드 8개 동작 및 프로브 suite(`adapters/conformance.py`)의 실행 검증이 아니며, UI 하드코딩 배열의 무결성만을 확인. |
| **ADP-02** | **어댑터 응답 지연시간·처리량·적합성 정적 리터럴(검증 아님) 고지** | `mlopsEngine.ts`<br>`ModelLineageView.tsx` | 어댑터 적합성 테이블 렌더링 | 화면 마운트 | • 지연시간 셀: `td:has-text("142 ms")`, `td:has-text("156 ms")`, `td:has-text("48 ms")`<br>• 처리량 셀: `td:has-text("68.5 tok/s")`, `td:has-text("64.2 tok/s")`, `td:has-text("112 tok/s")`<br>• 상단 배너: `div:has-text("Provider 계약 동일성 (AC-10)")`<br>• 배지/안내문: `100% CONFORMING`, `100% 적합`, `100% 준수합니다` | • UI에 표기된 지연시간/처리량 및 `100% CONFORMING` 배지, `100% 적합`, `100% 준수합니다` 문구는 실시간 벤치마크나 검증 결과가 아닌 **정적 리터럴(검증 아님 / 측정 아님)**임.<br>• 실제 코드(`ModelLineageView.tsx:445-446`)에 `title` 속성이 없으므로 툴팁 고지가 부재함을 정직하게 기록 (향후 FE 결함 카드로 고지 보강 예정). |
| **ADP-03** | **외부 프로바이더 실제 호출 및 증명 경계 격리 [Wire-Planned]** | `src/saintvision/adapters/contract.py`<br>`src/saintvision/adapters/conformance.py`<br>`src/saintvision/adapters/reference.py` | 실제 외부 LLM Provider 호출 요청 | 원격 추론/평가 작업 dispatch 시도 | • 백엔드 자격증명 경계: `CX-02 credential 경계`<br>• 계약 모듈: `src/saintvision/adapters/` | • **WIRE-PLANNED (CX-02 credential 경계 대기)**: 실제 원격 클라우드 API 호출 및 토큰 회수는 자격증명 주입 전까지 안전하게 보류.<br>• 합성 성공 응답을 가짜로 주입하지 않으며, 클라이언트 UI 전시용 상수와 제어 평면 어댑터 계약을 엄격히 분리. |

---

### 3.2 평가 실패 및 계보 이상 분류 (Failure & Traceback Categorization, FLT-01 ~ FLT-04) [Internal-Service]

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 코드/DB 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **FLT-01** | **Golden Suite 평가 결과 분류: errored vs failed 분리 [Internal]** | `services/eval_execution.py`<br>`db/models/evaluation.py`<br>`tests/test_eval_execution.py` | Golden Suite 평가 케이스 실행 중 예외 또는 단언 실패 발생 | 평가 케이스 실행 및 결과 기록 | • Outcome 제약: `CheckConstraint("outcome IN ('passed','failed','errored','skipped')")`<br>• 실행 서비스: `services/eval_execution.py`<br>• 시험: `tests/test_eval_execution.py:192-209, :333, :366` | • 어댑터 런타임 오류, 타임아웃, 예외 발생 시 `outcome = 'errored'`로 명확히 분리 기록 (`test_eval_execution.py:192-209`에서 `{"errored": 2}` 단언, `:333, :366`에서 빈 금지 케이스의 `outcome == "errored"` 및 `not run.passed_gate` 단언).<br>• 모델 출력의 기대치 불일치는 `outcome = 'failed'`로 분류.<br>• 실행 오류(`errored`)를 단순 실패(`failed`)로 뭉개거나 재시도로 조기 녹색(green) 처리하지 않음. |
| **FLT-02** | **금지 행동 위반 시 게이트 통과 전면 차단 (passed_gate = False) [Internal]** | `db/models/evaluation.py`<br>`services/eval_execution.py` | 모델이 보안/안전 정책 금지 행동(비밀 누출 등)을 1건 이상 위반 (`violations > 0`) | 평가 Run 완료 및 게이트 판정 | • DB 제약 1: `CheckConstraint("NOT violated OR outcome = 'failed'")`<br>• DB 제약 2: `CheckConstraint("NOT passed_gate OR violations = 0")`<br>• DB 테이블: `eval_runs` | • 금지 행동 위반 발생 시 해당 케이스는 반드시 `outcome = 'failed'`로 강제됨 (`evaluation.py:183`).<br>• 종합 점수가 아무리 높아도(`accuracy > 95%`) `violations > 0`인 경우 DB 레벨에서 `passed_gate = true` 저장이 거부됨 (`evaluation.py:134`).<br>• 누출 등 치명적 위반을 점수 평균화로 상쇄하는 행위 전면 방지. |
| **FLT-03** | **계보 역추적 결손 탐지: 4종 필수 계보 missing 보고 및 릴리스 차단 [Internal]** | `services/lineage.py`<br>`tests/test_lineage.py` | 모델에 4대 필수 계보(dataset_version, code_commit, eval_run, approval)가 결손된 상태 | `trace_model(session, *, tenant_id, model_version_id)` 및 `release_model_version()` 호출 | • 백엔드 함수: `trace_model()`, `release_model_version()`<br>• 필수 계보 정의: `REQUIRED_KINDS = ('dataset_version', 'code_commit', 'eval_run', 'approval')`<br>• 시험: `tests/test_lineage.py:316, :431` | • 맨 모델에 대해 필수 계보 4종이 전부 누락되었음을 정확히 지목 (`tests/test_lineage.py:332-334`, `set(trace["missing"]) == set(REQUIRED_KINDS)`).<br>• `fullyTraceable === false` 반환 및 미추적 모델의 릴리스 시도 시 `release_model_version()`에서 `VAL-SCHEMA` 422 거절 및 `"not fully traceable"` 메시지 단언 (`test_lineage.py:431, :454`).<br>• **릴리스 차단 조건의 정확한 한정**: 릴리스 거절은 `trace["missing"]`이 존재할 때만 발생하며(`lineage.py:328-336`), `dangling` 엣지는 릴리스 차단 조건이 아님을 확인.<br>• `trace_model` 호출 시 `tenant_id` 키워드 인수가 필수임을 준수 (`lineage.py:343-345`). |
| **FLT-04** | **참조 대상 소실 엣지 고아 탐지: dangling 필드 보고 [Internal]** | `services/lineage.py`<br>`tests/test_lineage.py` | `model_lineage` 엣지는 존재하나 대상 레코드(Subject row)가 DB 상에서 삭제/소실됨 | `trace_model(session, *, tenant_id, model_version_id)` 호출 | • 백엔드 함수: `trace_model()`<br>• 필드: `dangling: [{"kind": kind, "subjectId": subject}]`<br>• 시험: `tests/test_lineage.py:340` | • 실체 없는 허위 연결을 정상 연결로 취급하지 않음.<br>• 소실된 대상을 `dangling` 목록으로 즉시 격리 보고 (`test_lineage.py:340`).<br>• `fullyTraceable = not missing and not dangling` 불변식에 따라 추적 실패(`fullyTraceable: false`) 처리. |

---

### 3.3 End-to-End 계보 역추적 및 무합성 가드 (Lineage Query & Zero Synthesis, LIN-01 ~ LIN-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **LIN-01** | **saintvision 계보 API 미노출 시 안내 배너 및 빈 상태 정직 렌더링** | `ModelLineageView.tsx`<br>`services/control-plane/src/inv/app.py` | 외부 HTTP 계보 엔드포인트 미구현 상태에서 컴포넌트 마운트 (`initialLineages = []`) | 화면 최초 마운트 | • 안내 배너: `div[data-testid="lineage-unexposed-notice"][role="status"]`<br>• 빈 상태 컨테이너: `div[data-testid="lineage-empty-state"][role="status"]`<br>• 네트워크 호출: 0 requests | • `role="status"` 속성을 갖춘 미노출 경고 배너 렌더링 확인 (`tests/model-lineage.test.ts:138-143`).<br>• "가짜 계보 및 평가 점수(Accuracy/F1)의 합성을 전면 차단" 문구 표출.<br>• 빈 상태 컨테이너(`lineage-empty-state`) 표출 및 임의 합성 데이터 주입 0건 검증 (`test.ts:145-148`).<br>• 별도 commitment 엔드포인트(`/v1/projects/{project}/models/{model_id}/versions/{version}/commitment`, `app.py:449`)는 FE에서 호출하지 않음 (0 requests). |
| **LIN-02** | **가짜 평가 점수(Zero Synthesis) DOM 완전 배제 검증** | `ModelLineageView.tsx` | 미노출 기본 화면 렌더링 완료 | 전체 렌더링 DOM 텍스트 검사 | • 타겟 DOM: `container.textContent`<br>• 배제 대상 합성 점수: `"81.2%"`, `"0.812"`, `"94.8%"` 등 | • DOM 트리 전체에 임의 합성 평가 수치(`81.2%`, `0.812`, `94.8%`)가 단 하나도 포함되지 않음을 단언 (`tests/model-lineage.test.ts:149-153`).<br>• 의사결정 왜곡을 초래하는 모의 평가 점수 노출 원천 차단 (단, 기본 DOM의 어댑터 상수는 잔존). |
| **LIN-03** | **배포 다이제스트 및 Git 커밋 기반 인메모리 역추적 쿼리 [Fixture-Only]** | `mlopsEngine.ts`<br>`tests/fixtures/model-lineage.ts`<br>`services/lineage.py` | 테스트 픽스처 데이터셋 인입 (`TEST_FIXTURE_LINEAGES`) | `queryLineage(term)` 호출 | • 쿼리 함수: `mlops.queryLineage(term)`<br>• 검색 대상: `modelId`, `deploymentDigest`, `sourceCommitSha`, `modelName`<br>• 제외 대상: `datasetDigest` 미검색 | • **Fixture 전용 인메모리 필터 (AC-10 제품 완료 증거 아님)**: `tests/model-lineage.test.ts:51-78`은 클라이언트 엔진 단언일 뿐이며, DOM(input, button, 6단계 노드) 단언이 일절 없음.<br>• 제품 기본 상태(`App.tsx:834`, 빈 계보)에서는 결과가 나올 수 없으며, 픽스처 주입 시에만 문자열 부분 매칭으로 동작함.<br>• 제어 평면 정본은 `trace_model(session, *, tenant_id, model_version_id)`이며, HTTP 역추적 라우트는 부재 상태임. |
| **LIN-04** | **미승인 모델 게이트 배포 입력창 및 버튼 비활성화 [Client-Simulation]** | `ModelLineageView.tsx`<br>`mlopsEngine.ts` | `staging` 상태의 모델 표시 중 (fixture 모델은 정확도 81.2% 미달 모델) | 화면 렌더링 및 승인 번호 입력 상호작용 | • 승인 입력창: `input[data-testid="approval-input"]`<br>• 배포 버튼: `button[data-testid="lineage-deploy-btn"]`<br>• 조치 안내: `span[data-testid="approval-input-user-action-notice"]` | • 승인 입력창의 초기값이 빈 문자열(`""`)이며, 배포 버튼이 `.disabled === true`임을 단언 (`tests/model-lineage.test.ts:177, 182`).<br>• 주의: `aria-disabled` 단언은 테스트에 없으며, 조치 안내 span 미단언, 입력 후 활성화 상호작용(:185-192)에 expect 단언 없음.<br>• **Client-only 배포 시뮬레이션**: 성공 시 사용자 입력 `approvalId`로 digest를 합성(`mle:92-97`)하여 백엔드 `content_sha256` 고정 불변식과 정반대로 동작함을 정직하게 고지. |

---

### 3.4 배포 Digest 고정 및 승인 결속 가드 (Deployment Digest & Governance Guard, DIG-01 ~ DIG-04) [Internal-Service]

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 코드/DB 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **DIG-01** | **배포 Digest 모델 버전 고정 불변식 (Caller 주입 불허) [Internal]** | `services/lineage.py`<br>`tests/test_lineage.py` | `released` 상태의 모델 버전 존재 (`content_sha256: H`) | `record_deployment()` 호출 (`lineage.py:454`) | • 백엔드 함수: `record_deployment()` (`lineage.py:454`)<br>• 배포 레코드: `Deployment.deployed_digest = version.content_sha256`<br>• 시험: `tests/test_lineage.py:526` | • 배포 다이제스트는 호출자가 제공한 인자가 아닌 DB의 `ModelVersion.content_sha256` 값을 직접 채택 (`lineage.py:534`).<br>• 승인자가 검토하지 않은 임의 바이트나 태그로의 바꿔치기 원천 방어.<br>• `deployed_digest === version.content_sha256` 단언. |
| **DIG-02** | **승인 대상 해시 불일치 시 배포 차단 (AUTH-APPROVAL-DIGEST-MISMATCH) [Internal]** | `services/lineage.py`<br>`tests/test_lineage.py` | 모델 버전 A(`sha256_A`)와 모델 버전 B(`sha256_B`)에 대한 승인 레코드 존재 | 버전 B의 승인 ID로 버전 A 배포 시도 | • 오류 규격: `InvError(AUTH_APPROVAL_DIGEST_MISMATCH)` (`src/saintvision/errors.py:148`)<br>• 시험: `tests/test_lineage.py:543` | • 승인의 `subject_sha256`과 배포 대상 모델의 `content_sha256` 불일치 감지 (`lineage.py:513-517`).<br>• 배포 즉시 차단 및 `AUTH-APPROVAL-DIGEST-MISMATCH` 예외 발생 단언.<br>• 내부 Python 서비스 함수로 HTTP 경로 없음 (403은 ErrorCategory 매핑일 뿐 내부 서비스 함수). |
| **DIG-03** | **승인 시효 만료 시 배포 거절 (AUTH-APPROVAL-DIGEST-MISMATCH) [Internal]** | `services/lineage.py`<br>`tests/test_deployment_guard.py` | 승인 유효 구간 `[decided_at, expires_at)`을 벗어난 시각(`now >= expires_at`) | `record_deployment()` 호출 | • 오류 규격: `AUTH-APPROVAL-DIGEST-MISMATCH` (`lineage.py:510-511`)<br>• 시험: `tests/test_deployment_guard.py:43-59` | • 승인 시효 만료 검증 시 `AUTH_APPROVAL_DIGEST_MISMATCH` ("approval is not valid at the recorded deployment time") 반환.<br>• `AUTH-APPROVAL-EXPIRED` 상수는 lineage에서 미사용(run 전용).<br>• 타임존 인식 `now` 기준으로 유효 구간 엄격 대조. |
| **DIG-04** | **Active 배포 유일성: tenant·model_version·environment당 1개 한정 [Internal]** | `services/lineage.py`<br>`0004_s10_lineage.py`<br>`tests/test_lineage.py`<br>`tests/test_deployment_guard.py` | 환경(예: `staging`)에 기존 `active` 상태의 동일 모델 버전 배포 레코드 존재 | 동일 승인(또는 신규 승인) 건으로 동일 모델 버전 재배포 | • DB 제약: `(tenant_id, model_version_id, environment) WHERE status='active'` 부분 유니크 인덱스 (`0004_s10_lineage.py:277-279`)<br>• DB 업데이트: `lineage.py:520-526`<br>• 시험: `test_lineage.py:590, 620`, `test_deployment_guard.py:62, 118` | • 동일 모델 버전·동일 환경 재배포 시 기존 active 배포가 `superseded`로 원자적 전이됨 (`lineage.py:524-526`).<br>• `test_lineage.py:590`은 동일 승인 재사용 재배포를 검증.<br>• **유일성 범위의 엄격한 한정**: 환경 전체가 아닌 **tenant·model_version·environment당 active 1개** 보장 (서로 다른 모델 버전은 동일 환경에서 동시 active 가능).<br>• 두 active 배포 동시 생성 시 DB 제약으로 거절 단언 (`test_lineage.py:620`). |

---

## 4. 검증 단언 근거 및 교차 대조 증거 (Evidence Traceability)

### 4.1 Frontend 유닛/컴포넌트 단언 (`apps/web/tests/model-lineage.test.ts`)
- **ADP-01 / ADP-02 (Fixture-Only)**:
  - `model-lineage.test.ts:22-25`: `expect(codex?.contractVersion).toBe('v1.0.0-ADR-004')`, `expect(codex?.contractVersion).toBe(claude?.contractVersion)` (UI 상수 단언)
  - `model-lineage.test.ts:27-28`: `expect(codex?.conformancePassed).toBe(true)`, `expect(claude?.conformancePassed).toBe(true)` (하드코딩 상수 단언, Local-vLLM 미단언)
  - `model-lineage.test.ts:31-34`: `expect(codex?.supportedProtocols).toContain('SSE-v2')`, `toContain('W3C-TraceContext')` (`ProblemDetails` 미단언)
- **LIN-01 / LIN-02**:
  - `model-lineage.test.ts:138-143`: `expect(notice?.getAttribute('role')).toBe('status')`, `expect(notice?.textContent).toContain('모델 계보 및 평가 점수 미노출')`
  - `model-lineage.test.ts:145-148`: `expect(emptyState?.textContent).toContain('등록된 모델 계보 및 평가 점수 데이터가 없습니다')`
  - `model-lineage.test.ts:150-152`: `expect(container.textContent).not.toContain('81.2%')`, `not.toContain('0.812')`, `not.toContain('94.8%')` (기본 DOM 어댑터 상수는 잔존)
- **LIN-03 / LIN-04 (Fixture-Only / Client Simulation)**:
  - `model-lineage.test.ts:56-65`: 인메모리 다이제스트 역추적 (`queryLineage(digest)`, DOM 단언 없음)
  - `model-lineage.test.ts:71-78`: 인메모리 커밋 SHA 역추적 (`queryLineage(commitSha)`, DOM 단언 없음)
  - `model-lineage.test.ts:87-92`: 승인 누락 배포 차단 (`Two-Person Rule approval ID is required`, `DEPLOYMENT_GATED`는 client 전용 코드)
  - `model-lineage.test.ts:95-100`: 임계치 미달 배포 차단 (`below mandatory threshold (85.0%)`)
  - `model-lineage.test.ts:177, 182`: `expect(input?.value).toBe('')`, `expect(deployBtn?.disabled).toBe(true)` (`aria-disabled` 미단언)

### 4.2 Backend 및 DB 무결성 단언 (`tests/test_lineage.py`, `tests/test_deployment_guard.py`, `tests/test_eval_execution.py`)
- **FLT-01 / FLT-02**:
  - `tests/test_eval_execution.py:192-209`: 어댑터 실행 에러의 `errored` 분류 (`{"errored": 2}` 단언)
  - `tests/test_eval_execution.py:333, :366`: 빈 금지 케이스 거절 및 `outcome == "errored"`, `not run.passed_gate` 단언 (`test_a_forbidden_case_declaring_nothing_forbidden_is_refused`)
  - `src/saintvision/db/models/evaluation.py:128-135`: `CheckConstraint("NOT passed_gate OR violations = 0")`
  - `src/saintvision/db/models/evaluation.py:176-184`: `CheckConstraint("NOT violated OR outcome = 'failed'")`
- **FLT-03 / FLT-04**:
  - `src/saintvision/services/lineage.py:343-345`: `def trace_model(session: Session, *, tenant_id: uuid.UUID, model_version_id: str)` 키워드 인수 필수
  - `src/saintvision/services/lineage.py:419, 448`: `missing = [kind for kind in REQUIRED_KINDS if not found[kind]]`
  - `src/saintvision/services/lineage.py:423-435`: `dangling = [...]`
  - `tests/test_lineage.py:316, 332-334`: `test_the_traceback_names_what_is_missing` (4종 필수 계보 전수 누락 단언)
  - `tests/test_lineage.py:340`: `test_an_edge_whose_subject_vanished_is_reported_as_dangling`
  - `tests/test_lineage.py:431, :454`: `test_an_untraceable_model_cannot_be_released` (`assert "not fully traceable" in caught.value.message` 단언, `VAL-SCHEMA`는 `lineage.py:330-331`에서 발생, 릴리스 차단은 missing일 때만 발생)
- **DIG-01 ~ DIG-04**:
  - `src/saintvision/services/lineage.py:454`: `def record_deployment(...)`
  - `tests/test_lineage.py:526`: `test_a_deployment_pins_the_digest_that_shipped`
  - `tests/test_lineage.py:543`: `test_an_approval_for_other_content_cannot_deploy` (`AUTH-APPROVAL-DIGEST-MISMATCH`)
  - `tests/test_lineage.py:590`: `test_redeploying_supersedes_the_previous_active_one` (동일 승인 재사용 재배포 단언)
  - `tests/test_lineage.py:620`: `test_the_database_refuses_two_active_deployments`
  - `tests/test_deployment_guard.py:43-59`: `test_approval_time_and_cached_revocation_are_checked`
  - `tests/test_deployment_guard.py:62, 118`: `test_concurrent_first_deployments_leave_one_active_record`, `test_database_rejects_duplicate_active_and_service_supersedes`
  - `migrations/versions/0004_s10_lineage.py:277-279`: `(tenant_id, model_version_id, environment) WHERE status='active'` 부분 유니크 인덱스

### 4.3 정직한 미실행(not_run) 및 돌연변이(MUT) 표

| 돌연변이 ID | 대상 영역 | 계획된 검증 내용 | 현재 상태 및 미실행 사유 |
|:---:|---|---|---|
| **MUT-01** | 외부 LLM 어댑터 원격 프로브 | Codex / Claude 실제 원격 API ping 및 스키마 검증 | **WIRE-PLANNED (CX-02 credential 경계 대기)** |
| **MUT-02** | 어댑터 자격증명 주입/회수 | 유효하지 않은 API Key 주입 시 `AUTH-INVALID-CREDENTIAL` 거절 | **WIRE-PLANNED (CX-02 credential 경계 대기)** |
| **MUT-03** | 원격 Attestation 수집 | 제어 평면-외부 프로바이더 간 TLS 서명 검증 | **WIRE-PLANNED (CX-02 credential 경계 대기)** |
| **LAB-01** | 물리 5노드 랩 분산 배포 | Ubuntu 4노드 + Docker Desktop 1노드 대상 모델 실 배포 | **UNMEASURED (5노드 랩 후)** |

---

## 5. 결론 및 인계 사항

S10-FE 시나리오 매트릭스 v1.0.2는 Claude UI 검토 및 Codex 계약 축 검토 r2 지적 사항(commitment 완전 경로, test_eval_execution:366 errored 단언, 릴리스 거절 시험 message 단언 및 missing 한정, AUTH-INVALID-CREDENTIAL 코드, DIG-04 동일 승인 재배포 일치, 정본 trace_model 함수 명시)을 정직하고 완결성 있게 반영하였다.

- **작성자**: Gemini (Antigravity Frontend & Acceptance Lead)
- **검토자**: Claude (UI 사용자 여정/무합성 축), Codex (제어 평면 트랜잭션/계약 축)
- **후속 조치**: Claude 및 Codex r2 승인 확인 후 코디네이터 병합 대기.
