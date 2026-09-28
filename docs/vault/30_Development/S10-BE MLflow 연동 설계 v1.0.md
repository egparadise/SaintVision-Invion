---
doc_id: "CLAUDE-S10-BE-MLFLOW-INTEGRATION-DESIGN-001"
title: "S10-BE MLflow 연동 설계 v1.0 — MLflow는 정본이 아닌 미러(tracking·registry 미러링), 정본은 lineage의 content_sha256·approval digest; TrackingSink 계약·strict config·fail-closed·부재 시 NOT_OBSERVED; 도입 여부는 결정 요청(선택지 A 미도입 / B 미러 / C 정본) (카드 bd, G1a 해소안, docs-only)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:23:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["S10-BE", "AC-10", "mlflow", "tracking", "lineage", "adapter", "design", "claude"]
---

# S10-BE MLflow 연동 설계 v1.0 (2026-09-28, 카드 bd)

> [!warning] 설계만 — 구현은 승인 뒤 별도 PR
> S10-BE Evidence 대응표(PR #166) G1a: task-registry S10-BE scope에 "MLflow"가 있으나 코드가 0건(`git grep -i mlflow` → src·services·tools·tests·requirements 0). 아키텍처 문서는 MLflow를 "실험과 model registry **MVP**, 배포 권한은 별도 정책"([[시스템 아키텍처와 기술 스택]] :227), ML Worker 생태계(:214), Dev Workspace `inv mlflow RUN`(연결된 Experiment 열기)로 두었고, 운영 자격증명 계약은 "MLflow-owned artifacts" namespace를 분리했다([[Codex 운영 자격증명과 Storage 계약]] :43). 반면 S10에서 이미 착지한 것은 **우리 lineage·registry**(`register_model_version`·`record_lineage`·`release_model_version`·`record_deployment`, 0004 migration의 append-only·approval digest 결속)다. 따라서 첫 질문은 "MLflow를 어떻게 붙이나"가 아니라 "**MLflow가 무엇의 정본인가**"이고, 답은 **정본이 아니다**여야 한다.

## 0. 결정 — **B(미러)로 진행** (코디네이터 결정 2026-09-28 11:22 KST, 사용자 재검토 가능)

> [!note] 결정 근거(코디네이터)
> 1. task-registry S10-BE scope에 MLflow가 명시돼 있어 A(미도입)는 scope 정정이 필요하다.
> 2. C(정본)는 append-only `model_versions`·release 검증·approval digest·활성 배포 1 불변식을 우회한다.
> 3. B는 정본 lineage를 그대로 두고, 미러 실패를 NOT_OBSERVED로 하여 release·deploy를 막지 않는다.
> 4. 필요하면 되돌릴 수 있는 결정이다(미러 테이블·sink는 정본에 영향 없음).
>
> 다음: Codex 설계 검토 → 승인 뒤 별도 구현 카드. 아래 선택지 표는 결정 기록으로 유지한다.

| 선택지 | 내용 | 장점 | 비용/위험 | 판정 |
|---|---|---|---|---|
| **A. 미도입** | S10-BE scope에서 MLflow를 제거(registry 문구 정정). 실험/metric은 `eval_runs`·`eval_results`(0003)로, 모델 registry는 `model_versions`(0004)로 충족 | 코드 0·외부 의존 0; 정본 이중화 위험 없음; AC-10 근거(계보 역추적·배포 digest)는 이미 우리 DB에 있음 | 아키텍처 문서·registry scope와 불일치(문서 정정 필요); Python AI 워크플로(Jupyter·MLflow Client)에 익숙한 사용자 편의 상실; "ML Worker 생태계" 항목 공백 | 가능. 결정권자가 "MVP에서 MLflow 편의는 불필요"라고 판단하면 채택 |
| **B. 미러(권고)** | MLflow **tracking server**에 우리 정본의 사본을 push(실험/run/metric/param/artifact 참조/model version 메타). 읽기 경로는 없음(우리 서비스가 MLflow에서 상태를 가져오지 않음). 정본은 항상 lineage DB; MLflow 실패는 미러 상태 `NOT_OBSERVED`로 기록되고 release/deploy를 막지 않음 | 사용자에게 MLflow UI/Client 제공; 정본 이중화 없음(MLflow 쪽 변경은 무시·불일치는 표면화); 계약·시험을 우리 쪽에서 완결; 외부 부재 시 제품 동작 불변 | 새 계약·설정·미러 테이블·시험 구현(1 카드); MLflow 서버/credential은 운영 입력(U6 계열); hosted 시험은 pinned 컨테이너 lane 필요 | **권고** |
| **C. 정본** | MLflow Model Registry stage(Staging/Production)로 release/deploy를 구동 | MLflow 표준 워크플로 | **거부 권고**: `model_versions` append-only·`release_requires_verification_and_pin`·`approval.subject_sha256 == content_sha256`(lineage.py:512)·활성 배포 1(0004:277)을 MLflow가 우회하게 됨; ADR-018·AC-10 "배포 digest는 버전에서" 원칙과 충돌 | 채택 불가 |

결정은 B이므로 §1~§8이 구현 카드의 계약이다(A는 기각·기록용; 사용자 재검토로 뒤집히면 registry scope 정정 docs PR만 남는다).

## 1. 범위 (B): 무엇을 보내고 무엇을 받는가

| MLflow 개념 | 우리 정본 | 방향 | 보내는 것 | 받는 것 |
|---|---|---|---|---|
| Experiment | `projects`(tenant·project) | push | experiment name = `<prefix>/<tenant_short>/<project_id>`(prefix는 설정), tag `inv.tenant_id`·`inv.project_id` | experiment_id(미러 참조로 저장) |
| Run | `eval_runs`(0003; `evaluation.py:130 start_eval_run`·`:251 finish_eval_run`)와 학습 run(`runs`, `produced_by_run_id`) | push | run name = eval_run_id/run_id, params = suite name·version·suite hash·adapter name·contract_version·model_id(pinned), tags = `inv.run_id`·`inv.eval_run_id`·`inv.workload_spec_sha256` | mlflow run_id |
| Metric | `score_report`(`evaluation.py:288`)의 분류별 점수·passed_cases/total_cases·violations | push | metric per category + `gate_passed`(0/1)·`violations` | — |
| Artifact | `artifacts`(checksum_sha256)·`inv://` URI | push **참조만** | artifact **URI + sha256 + byte_size**를 tag/param으로. **바이트는 보내지 않는다**(MLflow-owned artifacts namespace는 사용자가 MLflow Client로 직접 쓰는 영역; 우리 Evidence pin과 분리, 자격증명 계약 :43) | — |
| Model registry | `model_versions`(0004; `lineage.py:184 register_model_version`, `:308 release`) | push | registered model = `<prefix>/<model_id>`, version에 tag `inv.model_version_id`·`inv.content_sha256`·`inv.stage`; **stage transition은 우리 stage를 tag로 반영할 뿐 MLflow stage API를 쓰지 않음** | mlflow model version number(미러 참조) |
| 배포 | `deployments`(0004; `record_deployment`) | push | tag `inv.deployment_id`·`inv.deployed_digest`·`inv.approval_id` | — |

받는 것은 **미러 참조 id뿐**이다. MLflow에서 우리 상태를 읽어 판정에 쓰는 경로는 없다(아래 §3).

## 2. lineage·정본 digest와의 관계

- **정본**: `model_versions.content_sha256`(append-only, `uq_model_versions_tenant_id_content_sha256`), `verify_model_version`, `pin_retention`(연장만), `release_model_version`(verify+pin+trace), `record_deployment`(`deployed_digest=version.content_sha256`, approval digest 일치). **변경 없음.**
- **미러 참조 테이블(신규, 구현 카드에서 migration)** `mlflow_mirrors`: `tenant_id`, `subject_kind ∈ {model_version, eval_run, deployment}`, `subject_id`, `tracking_uri_sha256`(URI 자체는 저장하지 않음), `mlflow_experiment_id`, `mlflow_run_id | mlflow_model_version`, `payload_sha256`(우리가 보낸 tag/param 집합의 canonical sha256), `synced_at`, `status ∈ {mirrored, refused, unavailable}`, `error_code`. **INSERT/SELECT만**(0003 `NEW_APPEND_ONLY`와 같은 정책), RLS FORCE. 재시도는 새 행.
- **lineage edge 추가 없음**: `record_lineage`의 kind 집합(`dataset_version`·`code_commit`·`container_image`·`eval_run`·`approval`)은 그대로. MLflow run은 계보 주체가 아니라 계보의 **미러**이므로 `REQUIRED_KINDS`·`trace_model`에 영향 없음.
- **불일치 표면화**: 미러 push 응답의 tag가 우리 digest와 다르면(서버가 tag를 바꿨거나 재사용된 run) `TRACK-MLFLOW-DIGEST-MISMATCH`로 기록(status `refused`) — 조용히 덮어쓰지 않음.

## 3. adapter contract와의 결속

MLflow는 프롬프트를 실행하는 Provider가 아니므로 `ProviderAdapter`(`adapters/contract.py:177`) 8 메서드를 그대로 요구하지 않는다. 대신 같은 자료형을 재사용하는 **`TrackingSink` 계약**(`adapters/tracking.py`, 신규)을 둔다:

| 멤버 | 자료형/의미 | 계약 재사용 |
|---|---|---|
| `name`, `contract_version` | `"mlflow"`, `"1.0.0"` | Provider와 동일 규칙(`_declares_version`) |
| `probe() -> ProbeResult` | tracking server 도달·API 버전 | `contract.py:77` 그대로 |
| `authenticate(credential_ref) -> AuthResult` | credential **참조**만 받음, 토큰 반환 없음 | `:90` 그대로(`principal_ref`는 opaque) |
| `mirror(record: MirrorRecord) -> MirrorResult` | 한 subject의 tag/param/metric 집합을 push; `MirrorResult(status, reference_id, payload_sha256, error_code)` | 신규(frozen dataclass) |
| `redact(content) -> (content, bool)` | run name·param 값에 ADR-014 redaction | `ReferenceAdapter.redact_text` 재사용 |
| `attest(reference_id) -> Attestation` | 서버가 저장한 tag 집합의 sha256 ↔ `payload_sha256` 비교; 검증 불가면 `UNVERIFIABLE` | `:145` 그대로 |

- Provider adapter의 `Attestation.model_id`·`Usage`는 eval run 미러의 param/metric으로 **함께** 보낸다(두 Provider adapter가 남긴 model pin이 MLflow에서도 보이게).
- conformance: `run_conformance`와 같은 형태의 `run_tracking_conformance`(계약 버전·멤버·probe·redaction·attest가 항상 VERIFIED를 내지 않음·mismatch 표면화) + **in-memory ReferenceSink**로 PG-free 시험. 실제 MLflow Client(`mlflow` 패키지)는 `MlflowSink`에서만 import(optional dependency, extras `mlflow`).

## 4. credential·endpoint 설정 (strict, 비밀 비노출)

| 설정 | 의미 | 규칙 |
|---|---|---|
| `INV_MLFLOW_TRACKING_URI` | tracking server URI(https만; `file:`·`sqlite:` 거부) | 없으면 sink `absent`; 잘못된 scheme은 `invalid`(fail-closed, 부팅 시 `configurationReadiness.mlflow=invalid`) |
| `INV_MLFLOW_CREDENTIAL_REF` | 기존 credential registry(0035)의 참조 id. 토큰/비밀번호를 env에 직접 두지 않음 | 값은 어디에도 기록되지 않음; 로그·evidence는 `credentialRefPresent: true/false`만 |
| `INV_MLFLOW_EXPERIMENT_PREFIX` | experiment 이름 접두(기본 `inv`) | `^[a-z0-9-]{1,32}$` |
| `INV_MLFLOW_TIMEOUT_SECONDS` | 호출 상한(기본 5) | 초과 = `unavailable`, 제품 흐름 계속 |

- `configurationReadiness.mlflow ∈ {configured, absent, invalid}`를 #159의 `objectStore`와 같은 방식으로 **하나의 strict source**에서 읽는다(API·worker 동일). provider fallback 없음.
- 비밀 비노출: URI의 userinfo는 거부(`https://user:pw@…` → `invalid`); MLflow Client 로그는 `WARNING` 이상만·본문 미기록; evidence/#153 S12 collector에는 `tracking_uri_sha256`만.

## 5. 오류 코드·fail-closed

| 코드(신규, `errors.py`) | 언제 | 제품 동작 |
|---|---|---|
| `TRACK-MLFLOW-UNAVAILABLE` | probe 실패·timeout·5xx | 미러 행 `unavailable`; release/deploy **계속**(정본은 우리 DB); readiness에 표시 |
| `TRACK-MLFLOW-REFUSED` | 401/403·credential 참조 해석 실패 | 미러 행 `refused`; 재시도 없음(자동 재시도는 credential 재사용 위험) |
| `TRACK-MLFLOW-DIGEST-MISMATCH` | attest에서 서버 tag ≠ 보낸 payload | 미러 행 `refused` + alarm 후보; 정본 불변 |
| `TRACK-MLFLOW-CONFIG-INVALID` | scheme/userinfo/prefix 규칙 위반 | 부팅 시 readiness `invalid`; 미러 호출 자체를 하지 않음 |

fail-closed의 뜻: **미러가 정본을 바꾸지 못하고, 미러 실패가 성공으로 읽히지 않는다.** 미러는 정본 트랜잭션 **커밋 뒤** outbox 방식으로 push한다(정본 커밋 실패 시 미러 없음; 미러 실패 시 정본 롤백 없음).

## 6. 외부 부재 시 동작

- `absent`(설정 없음): sink 미생성, 미러 테이블 기록 없음, `#153 S12 collector`·readiness는 `NOT_OBSERVED`(PASS 아님, 0 아님). 제품 기능 전부 동작.
- `unavailable`/`refused`: 위 §5. 대응표 G1b(운영 실측)는 이때 BLOCKED_EXTERNAL로 남는다.
- Windows/로컬: `mlflow` extras 미설치면 `MlflowSink` import 실패 → `absent`와 동일하게 처리하되 readiness detail에 `client-missing`.

## 7. 시험 계획

| 종류 | 내용 |
|---|---|
| PG-free(구현 카드) | `run_tracking_conformance`(ReferenceSink 적합·attest는 항상 VERIFIED 불가·mismatch 표면화·redaction·credential 반향 금지); strict config(scheme·userinfo·prefix 부정 5+); 미러 payload canonical sha256 결정성; `absent`/`unavailable`/`refused`가 PASS로 승격되지 않음; `record_deployment` 등 정본 경로가 sink 유무에 무관하게 같은 결과(sink stub) |
| 실 PG(hosted Backend) | `mlflow_mirrors` append-only·RLS·재시도 새 행; outbox 순서(정본 커밋 → 미러) |
| hosted lane(선택, #159 MinIO 패턴) | digest-pinned MLflow 컨테이너 + disposable PG로 push→attest 1회; runner 없으면 `NOT_OBSERVED`로 선언(exact map) |
| 운영 실측 | G1b — 실제 endpoint·credential(BLOCKED_EXTERNAL) |

## 8. 경계·다음

- 이 문서는 docs-only. 코드·계약·migration 변경 0. **구현은 결정(§0)과 Codex 승인 뒤** 별도 카드(예상 범위: `adapters/tracking.py`·`MlflowSink`·`ReferenceSink`·`mlflow_mirrors` migration·outbox 훅·readiness 필드·시험).
- 관련: S10-BE Evidence 대응표(PR #166) G1a/G1b, S10-DB lineage 조회 API 설계(PR #158, lineage read API — 미러 참조를 응답에 포함할지는 그 설계의 후속), CL-06(실제 학습·평가·승인 배포).
- owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s10-be-mlflow-design`, base `1e8baf04`. 다음 첫 행동: Codex 설계 검토(결정 B 반영본) → 승인 뒤 구현 카드.
