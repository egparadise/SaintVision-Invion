---
doc_id: "GEMINI-S10-FE-SCENARIO-MATRIX-20260928"
title: "S10-FE Multi-LLM 어댑터 적합성·실패 분류·계보 역추적·배포 Digest 시나리오 매트릭스 (Gemini)"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude, Codex"
updated: "2026-09-28T09:00:00+09:00"
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
> - `src/saintvision/services/lineage.py`
> - `src/saintvision/db/models/evaluation.py`
> - `src/saintvision/errors.py`
> - `tests/test_lineage.py`
> - `tests/test_deployment_guard.py`

---

## 1. 개요 및 수용 목표 (OUT-10 / AC-10)

본 문서는 SaintVision 제어 평면 및 MLOps 관측·배포 서브시스템의 **S10-FE (Multi-LLM 어댑터 적합성·실패 분류·모델 계보 역추적·배포 Digest 검증)** 트랙을 완결하기 위해 수립된 **docs-only 시나리오 매트릭스 정본(v1.0.0)**이다.

본 매트릭스는 코디네이터 지침, Codex 차단지도([[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]), Claude 실 PG 교차 증거([[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]), 그리고 프런트엔드(`apps/web/src/features/mlops/ModelLineageView.tsx`, `mlopsEngine.ts`, `tests/model-lineage.test.ts`)와 백엔드 코어(`src/saintvision/services/lineage.py`, `models/evaluation.py`, `errors.py`)의 실제 코드 및 단언을 1:1로 엄격하게 대조하여 작성되었다.

### 1.1 핵심 작성 및 거버넌스 원칙 (Zero Fake / Honest Boundary)
1. **화면 합성 상태와 백엔드 정본의 엄격한 분리**:
   - `ModelLineageView.tsx` 화면은 현재 백엔드 제어 평면에 외부 노출용 HTTP 계보 조회 API가 부재함을 인식하고, 컴포넌트 마운트 시 가짜 파이프라인 그래프나 합성 평가 점수를 일절 생성하지 않는다.
   - HTTP API 부재 시 정직하게 안내 배너(`lineage-unexposed-notice`, `role="status"`)와 빈 상태 화면(`lineage-empty-state`, `role="status"`)을 렌더링하며, 네트워크 요청은 0건(Zero Network Calls)을 유지한다.
2. **정적 리터럴(Static Literal)의 명시적 구분 (측정값 왜곡 방지)**:
   - UI 화면 및 클라이언트 엔진(`mlopsEngine.ts`)에 포함된 어댑터 지연시간/처리량 수치(`Codex 142 ms`, `Claude 156 ms`, `Local-vLLM 48 ms`, `68.5 tok/s`, `100% 적합`, `W3C-Trace / SSE-v2 / RFC 9457 일치`)는 실시간 물리 측정값이 아니며, 공통 인터페이스 명세 충족을 확인하기 위한 **정적 리터럴(측정 아님)**로 명시한다.
3. **인용 시험 파일 및 행(File:Line) 실측 단언 검증**:
   - 매트릭스에 인용된 모든 단언은 `apps/web/tests/model-lineage.test.ts`, `tests/test_lineage.py`, `tests/test_deployment_guard.py` 소스 코드의 실제 실행 단언과 일치한다.
4. **미실행 돌연변이 및 물리 장비 경계의 정직한 표기**:
   - 외부 프로바이더 실제 원격 호출/인증서 검증/attestation 돌연변이는 `PLANNED/NOT_RUN (CX-02 credential 경계 대기)`로 표기한다.
   - 물리 노드 5대 PC 분산 환경 실측 항목은 `UNMEASURED (5노드 랩 후)`로 표기하여 임의 합격을 방지한다.
5. **정본 계약 오류 코드만 사용**:
   - `src/saintvision/errors.py` 및 `contracts/`에 실재하는 정본 오류 코드(`AUTH-APPROVAL-DIGEST-MISMATCH`, `AUTH-APPROVAL-EXPIRED`, `VAL-SCHEMA`, `RES-ARTIFACT-NOT-FOUND`, `DEPLOYMENT_GATED`)만을 사용한다.

---

## 2. 4대 핵심 영역 매트릭스 구성 체계

| 영역 코드 | 핵심 테마 | 대상 컴포넌트 / 모듈 | 핵심 방어 기제 및 백엔드 계약 규격 |
|:---:|---|---|---|
| **ADP** | **Multi-LLM Provider 어댑터 적합성**<br>(Multi-LLM Adapter Conformance) | `mlopsEngine.ts`<br>`ModelLineageView.tsx`<br>`tests/model-lineage.test.ts` | • Codex = Claude = Local-vLLM 공통 계약 동일성 (`v1.0.0-ADR-004`)<br>• 공통 프로토콜 지원 (`SSE-v2`, `W3C-TraceContext`, `ProblemDetails`)<br>• 화면 표시 성능 수치는 **정적 리터럴(측정 아님)** 표기<br>• 실제 외부 호출은 `PLANNED/NOT_RUN (CX-02 credential 대기)` |
| **FLT** | **평가 실패 분류 및 계보 이상 탐지**<br>(Failure Categorization & Trace Anomalies) | `db/models/evaluation.py`<br>`services/lineage.py`<br>`tests/test_lineage.py` | • Golden Suite 평가 결과 분류: `passed` vs `failed` vs `errored` vs `skipped`<br>• 금지 행동 위반(`violated=True`) 시 `outcome='failed'` 강제 및 `passed_gate=False` 고정<br>• 계보 역추적 결손 분류: 필수 요소 누락(`missing`) vs DB 고아 참조(`dangling`)<br>• `fullyTraceable: not missing and not dangling` 불변식 |
| **LIN** | **End-to-End 계보 역추적 및 무합성 가드**<br>(Reverse Lineage Query & Zero Synthesis) | `ModelLineageView.tsx`<br>`mlopsEngine.ts`<br>`services/lineage.py` | • 6단계 파이프라인: Dataset Digest → Source Commit → Training Run → Evaluation → Approval → Deployment Digest<br>• 다이제스트/커밋 기반 역추적 쿼리 (`queryLineage`)<br>• HTTP API 부재 시 정직한 고지 (`lineage-unexposed-notice`, `lineage-empty-state`)<br>• 미노출 시 가짜 평가 점수(81.2%, 94.8% 등) DOM 렌더링 0건 보장 |
| **DIG** | **배포 Digest 고정 및 승인 결속 가드**<br>(Deployment Digest & Governance Guard) | `services/lineage.py`<br>`test_deployment_guard.py`<br>`test_lineage.py` | • 배포 다이제스트는 호출자 입력이 아닌 Model Version의 `content_sha256`에서 고정<br>• 승인 다이제스트 불일치 차단: `AUTH-APPROVAL-DIGEST-MISMATCH`<br>• 승인 시효 검증: `[decided_at, expires_at)` 반열린 구간 엄격 검증<br>• 단일 Active 배포 불변식: 신규 배포 시 기존 active는 `superseded`로 원자 갱신 (DB 부분 유니크 인덱스 방어) |

---

## 3. 세부 시나리오 매트릭스 (15대 시나리오)

### 3.1 Multi-LLM 어댑터 적합성 (Adapter Conformance, ADP-01 ~ ADP-03)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **ADP-01** | **Multi-LLM 어댑터 스키마 및 프로토콜 적합성 검증** | `mlopsEngine.ts`<br>`ModelLineageView.tsx` | MLOps 관리자 초기화 | `verifyProviderConformances()` 호출 및 표 렌더링 | • 계약 버전: `v1.0.0-ADR-004`<br>• 지원 프로토콜: `SSE-v2`, `W3C-TraceContext`, `ProblemDetails`<br>• DOM 배지: `span:has-text("100% CONFORMING")` | • Codex와 Claude, Local-vLLM 어댑터가 동일 계약 버전(`v1.0.0-ADR-004`) 준수 확인 (`tests/model-lineage.test.ts:22-25`).<br>• 전 제공자 `conformancePassed === true` 단언 (`test.ts:27-28`).<br>• 필수 스트리밍 및 오류 규격 프로토콜 완비 단언 (`test.ts:31-34`). |
| **ADP-02** | **어댑터 응답 지연시간 및 처리량 정적 리터럴 고지** | `mlopsEngine.ts`<br>`ModelLineageView.tsx` | 어댑터 적합성 테이블 렌더링 | 화면 마운트 | • 지연시간 셀: `td:has-text("142 ms")`, `td:has-text("156 ms")`, `td:has-text("48 ms")`<br>• 토큰 처리량: `td:has-text("68.5 tok/s")`, `td:has-text("64.2 tok/s")`<br>• 상단 배너: `div:has-text("Provider 계약 동일성 (AC-10)")` | • UI에 표기된 수치는 실시간 백엔드 벤치마크가 아닌 **정적 리터럴(측정 아님)**임을 문서 및 툴팁으로 정직하게 고지.<br>• 상단 카드가 `100% 적합 (Codex = Claude = Local-vLLM)` 및 `W3C-Trace / SSE-v2 / RFC 9457 일치`를 정확히 반영. |
| **ADP-03** | **외부 프로바이더 실제 호출 및 증명 경계 격리 [Wire]** | `services/lineage.py`<br>`contracts/types.ts` | 실제 외부 LLM Provider 호출 요청 | 원격 추론/평가 작업 dispatch 시도 | • 백엔드 자격증명 경계: `CX-02 credential 경계`<br>• 오류 규격: `AUTH-MISSING-CREDENTIAL` 또는 격리 가드 | • **PLANNED/NOT_RUN (CX-02 credential 경계 대기)**: 실제 원격 클라우드 API 호출 및 토큰 회수는 자격증명 주입 전까지 안전하게 보류.<br>• 합성 성공 응답을 가짜로 주입하지 않으며, 클라이언트 어댑터 계약 검증과 운영 인프라 통신을 엄격히 분리. |

---

### 3.2 평가 실패 및 계보 이상 분류 (Failure & Traceback Categorization, FLT-01 ~ FLT-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **FLT-01** | **Golden Suite 평가 결과 분류: errored vs failed 분리 [Wire]** | `db/models/evaluation.py`<br>`test_lineage.py` | Golden Suite 평가 케이스 실행 중 예외 또는 단언 실패 발생 | 평가 케이스 결과 기록 (`EvalResult`) | • Outcome 제약: `CheckConstraint("outcome IN ('passed','failed','errored','skipped')")`<br>• DB 테이블: `eval_results` | • 단언 불일치나 허용 범위를 벗어난 결과는 `outcome = 'failed'`로 분류.<br>• 타임아웃, 커널 크래시, 통신 단절 등 비정상 실행 예외는 `outcome = 'errored'`로 명확히 분리.<br>• `errored`를 단순 `failed`로 뭉개거나 재시도로 조기 녹색(green) 처리하지 않음. |
| **FLT-02** | **금지 행동 위반 시 게이트 통과 전면 차단 (passed_gate = False) [Wire]** | `db/models/evaluation.py` | 모델이 보안/안전 정책 금지 행동(비밀 누출 등)을 1건 이상 위반 (`violations > 0`) | 평가 Run 완료 및 게이트 판정 | • DB 제약 1: `CheckConstraint("NOT violated OR outcome = 'failed'")`<br>• DB 제약 2: `CheckConstraint("NOT passed_gate OR violations = 0")`<br>• DB 테이블: `eval_runs` | • 금지 행동 위반 발생 시 해당 케이스는 반드시 `outcome = 'failed'`로 강제됨.<br>• 종합 점수가 아무리 높아도(`accuracy > 95%`) `violations > 0`인 경우 DB 레벨에서 `passed_gate = true` 저장이 거부됨(무결성 제약).<br>• 누출 등 치명적 위반을 점수 평균화로 상쇄하는 행위 전면 방지. |
| **FLT-03** | **계보 역추적 결손 탐지: missing 필드 정직 명시 [Wire]** | `services/lineage.py`<br>`tests/test_lineage.py` | 모델에 4대 필수 계보 중 일부(예: approval 누락)만 연결된 상태 | `trace_model()` 호출 | • 백엔드 함수: `trace_model(session, model_version_id)`<br>• 필수 계보 정의: `REQUIRED_KINDS = ('dataset_version', 'code_commit', 'eval_run', 'approval')`<br>• 시험: `tests/test_lineage.py:316` | • 발견된 항목만 반환하여 겉보기에 완전해 보이는 착시 방지.<br>• 누락된 필수 계보 항목을 `missing` 배열에 정확히 식별(`missing: ["approval"]`).<br>• `fullyTraceable === false` 반환 및 미추적 모델의 릴리스 차단(`release_model_version`에서 `VAL-SCHEMA` 422 거절). |
| **FLT-04** | **참조 대상 소실 엣지 고아 탐지: dangling 필드 보고 [Wire]** | `services/lineage.py`<br>`tests/test_lineage.py` | `model_lineage` 엣지는 존재하나 대상 레코드(Subject row)가 삭제/유실됨 | `trace_model()` 호출 | • 백엔드 함수: `trace_model()`<br>• 필드: `dangling: [{"kind": kind, "subjectId": subject}]`<br>• 시험: `tests/test_lineage.py:340` | • 실체 없는 허위 연결을 정상 연결로 취급하지 않음.<br>• 소실된 대상을 `dangling` 목록으로 즉시 격리 보고.<br>• `fullyTraceable = not missing and not dangling` 불변식에 따라 추적 실패 처리. |

---

### 3.3 End-to-End 계보 역추적 및 무합성 가드 (Lineage Query & Zero Synthesis, LIN-01 ~ LIN-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **LIN-01** | **백엔드 HTTP 계보 API 부재 시 미노출 배너 및 빈 상태 정직 렌더링** | `ModelLineageView.tsx` | 외부 HTTP 엔드포인트 미구현 상태에서 컴포넌트 마운트 (`initialLineages = []`) | 화면 최초 마운트 | • 안내 배너: `div[data-testid="lineage-unexposed-notice"][role="status"]`<br>• 빈 상태 컨테이너: `div[data-testid="lineage-empty-state"][role="status"]`<br>• 네트워크 호출: 0 requests | • `role="status"` 속성을 갖춘 미노출 경고 배너 렌더링 확인 (`tests/model-lineage.test.ts:138-143`).<br>• "가짜 계보 및 평가 점수(Accuracy/F1)의 합성을 전면 차단" 문구 표출.<br>• 빈 상태 컨테이너(`lineage-empty-state`) 표출 및 임의 합성 데이터 주입 0건 검증 (`test.ts:145-148`). |
| **LIN-02** | **가짜 평가 점수(Zero Synthesis) DOM 완전 배제 검증** | `ModelLineageView.tsx` | 미노출 기본 화면 렌더링 완료 | 전체 렌더링 DOM 텍스트 검사 | • 타겟 DOM: `container.textContent`<br>• 배제 대상 합성 점수: `"81.2%"`, `"0.812"`, `"94.8%"` 등 | • DOM 트리 전체에 임의 합성 수치(`81.2%`, `0.812`, `94.8%`)가 단 하나도 포함되지 않음을 단언 (`tests/model-lineage.test.ts:149-153`).<br>• 의사결정 왜곡을 초래하는 모의 점수 노출 원천 차단. |
| **LIN-03** | **배포 다이제스트 및 Git 커밋 SHA 기반 6단계 역추적 질의 (AC-10)** | `ModelLineageView.tsx`<br>`mlopsEngine.ts` | 테스트 픽스처 데이터셋 인입 (`TEST_FIXTURE_LINEAGES`) | 검색창에 다이제스트 또는 커밋 SHA 입력 후 역추적 질의 제출 | • 입력창: `input[placeholder*="Search by commit SHA"]`<br>• 제출 버튼: `button:has-text("역추적 질의 (Query)")`<br>• 6단계 노드: Dataset, Commit, Run, Eval, Approval, Digest | • 배포 다이제스트(`sha256:4a8b2c1d...`) 질의 시 원천 데이터셋(`dset_sha256_...`), 커밋(`58cabd3...`), 훈련 Run(`run_01JABCDE0001`), 정확도(0.948), 승인 ID(`apr_01JXYZ987654`) 완벽 매핑 (`tests/model-lineage.test.ts:51-65`).<br>• 커밋 SHA(`39699e9b...`) 질의 시 대상 모델(`mod_pacs_cls_v1`) 및 배포 다이제스트 역방향 매핑 확인 (`test.ts:67-78`). |
| **LIN-04** | **미승인 모델 게이트 배포 입력창 및 버튼 비활성화 가드** | `ModelLineageView.tsx` | `staging` 상태의 적합 모델 표시 중 | 화면 렌더링 및 승인 번호 입력 상호작용 | • 승인 입력창: `input[data-testid="approval-input"]`<br>• 배포 버튼: `button[data-testid="lineage-deploy-btn"]`<br>• 조치 안내: `span[data-testid="approval-input-user-action-notice"]` | • 승인 입력창의 초기값이 정직하게 빈 문자열(`""`)임을 단언 (`tests/model-lineage.test.ts:174-177`).<br>• 승인 번호 미입력 시 배포 버튼이 `disabled === true` 및 `aria-disabled === true`로 비활성화됨을 단언 (`test.ts:180-182`).<br>• 위조 승인 번호 기본 주입을 금지하고 사용자 조치 필요 배너 표출 확인. |

---

### 3.4 배포 Digest 고정 및 승인 결속 가드 (Deployment Digest & Governance Guard, DIG-01 ~ DIG-04)

| 시나리오 ID | 시나리오 명칭 | 대상 컴포넌트 | 선행 상태 및 조건 | 트리거 액션 | 실제 DOM 셀렉터 및 계약 규격 | 검증 단언 및 기대값 |
|:---:|---|---|---|---|---|---|
| **DIG-01** | **배포 Digest 모델 버전 고정 불변식 (Caller 주입 불허) [Wire]** | `services/lineage.py`<br>`tests/test_lineage.py` | `released` 상태의 모델 버전 존재 (`content_sha256: H`) | `record_deployment()` 호출 | • 백엔드 함수: `record_deployment(model_version_id, approval_id, ...)`<br>• 배포 레코드: `Deployment.deployed_digest`<br>• 시험: `tests/test_lineage.py:526` | • 배포 다이제스트는 호출자가 제공한 인자가 아닌 DB의 `ModelVersion.content_sha256` 값을 직접 채택.<br>• 승인자가 검토하지 않은 임의 바이트나 태그로의 바꿔치기 원천 방어.<br>• `deployed_digest === version.content_sha256` 단언. |
| **DIG-02** | **승인 대상 해시 불일치 시 배포 차단 (AUTH-APPROVAL-DIGEST-MISMATCH) [Wire]** | `services/lineage.py`<br>`tests/test_lineage.py` | 모델 버전 A(`sha256_A`)와 모델 버전 B(`sha256_B`)에 대한 승인 레코드 존재 | 버전 B의 승인 ID로 버전 A 배포 시도 | • 백엔드 오류 규격: HTTP 403 `AUTH-APPROVAL-DIGEST-MISMATCH`<br>• 오류 클래스: `InvError`<br>• 시험: `tests/test_lineage.py:543` | • 승인의 `subject_sha256`과 배포 대상 모델의 `content_sha256` 불일치 감지.<br>• 배포 즉시 차단 및 `AUTH-APPROVAL-DIGEST-MISMATCH` 예외 발생 단언.<br>• 타 모델의 2인 승인 번호를 도용한 부정 배포 방어. |
| **DIG-03** | **승인 유효 기간 만료 시 배포 거절 (AUTH-APPROVAL-EXPIRED) [Wire]** | `services/lineage.py`<br>`tests/test_deployment_guard.py` | 승인 유효 구간 `[decided_at, expires_at)`을 벗어난 시각(`now >= expires_at`) | `record_deployment()` 호출 | • 오류 규격: `AUTH-APPROVAL-DIGEST-MISMATCH` 또는 `AUTH-APPROVAL-EXPIRED`<br>• 시험: `tests/test_deployment_guard.py:43` | • 승인 시효 만료 검증.<br>• 만료된 승인을 이용한 지연 배포 시도 거절.<br>• 타임존 인식 `now` 기준으로 유효 구간 엄격 대조. |
| **DIG-04** | **단일 Active 배포 불변식: 재배포 시 이전 배포 원자적 superseded 전이 [Wire]** | `services/lineage.py`<br>`tests/test_deployment_guard.py`<br>`tests/test_lineage.py` | 환경(예: `staging`)에 기존 `active` 상태의 배포 레코드 존재 | 신규 승인 건으로 동일 모델 버전 재배포 | • DB 업데이트: `UPDATE deployments SET status = 'superseded'`<br>• DB 제약: 환경별 `active` 상태 부분 유니크 인덱스<br>• 시험: `test_lineage.py:590`, `test_deployment_guard.py:62, 118` | • 신규 배포 등록과 이전 배포 `superseded` 전이가 단일 DB 트랜잭션에서 원자적으로 체결됨.<br>• 환경 내에 동시 활성 배포가 2개 이상 존재하는 상태를 DB 레벨에서 불허.<br>• 현재 라이브 상태인 모델의 유일성(Single Active Record) 보장. |

---

## 4. 검증 단언 근거 및 교차 대조 증거 (Evidence Traceability)

### 4.1 Frontend 유닛/컴포넌트 단언 (`apps/web/tests/model-lineage.test.ts`)
- **ADP-01 / ADP-02**:
  - `model-lineage.test.ts:22-25`: `expect(codex?.contractVersion).toBe('v1.0.0-ADR-004')`, `expect(codex?.contractVersion).toBe(claude?.contractVersion)`
  - `model-lineage.test.ts:27-28`: `expect(codex?.conformancePassed).toBe(true)`, `expect(claude?.conformancePassed).toBe(true)`
  - `model-lineage.test.ts:31-34`: `expect(codex?.supportedProtocols).toContain('SSE-v2')`, `toContain('W3C-TraceContext')`
- **LIN-01 / LIN-02**:
  - `model-lineage.test.ts:138-143`: `expect(notice?.getAttribute('role')).toBe('status')`, `expect(notice?.textContent).toContain('모델 계보 및 평가 점수 미노출')`
  - `model-lineage.test.ts:145-148`: `expect(emptyState?.textContent).toContain('등록된 모델 계보 및 평가 점수 데이터가 없습니다')`
  - `model-lineage.test.ts:150-152`: `expect(container.textContent).not.toContain('81.2%')`, `not.toContain('0.812')`, `not.toContain('94.8%')`
- **LIN-03 / LIN-04**:
  - `model-lineage.test.ts:56-65`: 다이제스트 역추적 (`queryLineage(digest)`)
  - `model-lineage.test.ts:71-78`: 커밋 SHA 역추적 (`queryLineage(commitSha)`)
  - `model-lineage.test.ts:87-92`: 승인 누락 배포 차단 (`Two-Person Rule approval ID is required`)
  - `model-lineage.test.ts:95-100`: 임계치 미달 배포 차단 (`below mandatory threshold (85.0%)`)
  - `model-lineage.test.ts:177, 182`: `expect(input?.value).toBe('')`, `expect(deployBtn?.disabled).toBe(true)`

### 4.2 Backend 및 DB 무결성 단언 (`tests/test_lineage.py`, `tests/test_deployment_guard.py`)
- **FLT-01 / FLT-02**:
  - `src/saintvision/db/models/evaluation.py:128-135`: `CheckConstraint("NOT passed_gate OR violations = 0")`
  - `src/saintvision/db/models/evaluation.py:176-184`: `CheckConstraint("NOT violated OR outcome = 'failed'")`
- **FLT-03 / FLT-04**:
  - `src/saintvision/services/lineage.py:419, 448`: `missing = [kind for kind in REQUIRED_KINDS if not found[kind]]`
  - `src/saintvision/services/lineage.py:423-435`: `dangling = [...]`
  - `tests/test_lineage.py:316`: `test_the_traceback_names_what_is_missing`
  - `tests/test_lineage.py:340`: `test_an_edge_whose_subject_vanished_is_reported_as_dangling`
- **DIG-01 ~ DIG-04**:
  - `src/saintvision/services/lineage.py:466-543`: `record_deployment()`
  - `tests/test_lineage.py:526`: `test_a_deployment_pins_the_digest_that_shipped`
  - `tests/test_lineage.py:543`: `test_an_approval_for_other_content_cannot_deploy` (`AUTH-APPROVAL-DIGEST-MISMATCH`)
  - `tests/test_lineage.py:590`: `test_redeploying_supersedes_the_previous_active_one`
  - `tests/test_lineage.py:620`: `test_the_database_refuses_two_active_deployments`
  - `tests/test_deployment_guard.py:43`: `test_approval_time_and_cached_revocation_are_checked`
  - `tests/test_deployment_guard.py:62, 118`: `test_concurrent_first_deployments_leave_one_active_record`, `test_database_rejects_duplicate_active_and_service_supersedes`

### 4.3 정직한 미실행(not_run) 및 실측 경계
- **외부 프로바이더 실제 호출 및 취소/수집**: `PLANNED/NOT_RUN (CX-02 credential 경계 대기)`
- **물리 5노드 랩 환경 분산 배포 및 관측**: `UNMEASURED (5노드 랩 후)`
- **CI 환경 검증**: 로컬 실측 단언을 원격 배포 완료로 과장하지 않으며, Hosted CI(GitHub Actions) 통과는 풀 리퀘스트 수립 후 확인한다.

---

## 5. 결론 및 인계 사항

S10-FE 시나리오 매트릭스 v1.0.0은 Multi-LLM 어댑터 적합성, 평가 실패 분류, 계보 역추적 쿼리, 배포 다이제스트 불변식 등 S10 핵심 수용 조건(AC-10 / OUT-10)을 정직한 검증 경계와 함께 체계화하였다.

- **작성자**: Gemini (Antigravity Frontend & Acceptance Lead)
- **검토 요청**:
  - Claude (UI 사용자 여정 및 접근성·무합성 검증 축)
  - Codex (제어 평면 lineage/deployment 트랜잭션 및 DB 제약 무결성 계약 축)
- **차기 조치**: Claude 및 Codex 독립 검토 수렴 후 이상 없을 시 병합 대기열 편입.
