---
doc_id: "CLAUDE-S10-BE-MLFLOW-INTEGRATION-DESIGN-001"
title: "S10-BE MLflow 연동 설계 v1.2 — 결정 B(미러): 정본은 lineage digest, MLflow는 push-only 미러; intent+outbox 한 tx·append-only attempt·idempotent find; TrackingSink 계약; tenant 범위 operator service credential(0035 run 결속 lookup 미사용); TRACK-0001~0005 canonical code·verdict 매핑; canonical payload/URI 정규화; 부재·부분 실패 관측 (카드 bd, docs-only)"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:37:30+09:00"
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

## 2. lineage·정본 digest와의 관계 (v1.2: subject/schema 확정)

- **정본 불변**: `model_versions.content_sha256`(append-only, `uq_model_versions_tenant_id_content_sha256`), `verify_model_version`, `pin_retention`(연장만), `release_model_version`(verify+pin+trace), `record_deployment`(`deployed_digest=version.content_sha256`, approval digest 일치). **변경 없음.** lineage edge kind 5·`REQUIRED_KINDS`·`trace_model` 불변(MLflow run은 계보 주체가 아니라 미러).
- **subject 스키마(신규 table 2, 구현 카드 migration)**:

`mlflow_mirror_intents` — 정본 변경과 **같은 transaction**에서 INSERT되는 불변 의도(F-R3). 앱 role INSERT/SELECT만, RLS FORCE.

| 컬럼 | 규칙 |
|---|---|
| `intent_id` (`mmi_` + ULID) | PK(tenant_id, intent_id) |
| `tenant_id`, `project_id` | NOT NULL; FK projects |
| `subject_kind` | `CHECK IN ('experiment','training_run','eval_run','model_version','deployment')` |
| `run_id`, `eval_run_id`, `model_version_id`, `deployment_id` | **정확히 하나만 NOT NULL**(`experiment`는 전부 NULL): `CHECK (num_nonnulls(run_id, eval_run_id, model_version_id, deployment_id) = CASE WHEN subject_kind='experiment' THEN 0 ELSE 1 END)` + kind↔컬럼 일치 CHECK(`training_run`↔`run_id`, `eval_run`↔`eval_run_id`, …); FK는 각 정본 table |
| `payload` jsonb, `payload_sha256` | §2.1 canonical bytes의 sha256; `CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')` |
| `outbox_event_id` | FK `outbox_events`(core, 기존 `services/evidence.py:113` "caller의 transaction 안에서 append") — 의도와 outbox row가 한 tx |
| `created_at`, `recovery_epoch` | 기록; `UNIQUE(tenant_id, subject_kind, COALESCE(run_id,eval_run_id,model_version_id,deployment_id,project_id), payload_sha256)` → 같은 payload 재의도는 no-op(idempotent enqueue) |

`mlflow_mirror_attempts` — worker가 push **뒤** 남기는 append-only outcome(INSERT/SELECT만).

| 컬럼 | 규칙 |
|---|---|
| `attempt_id` (`mma_` + ULID), `intent_id` FK | `UNIQUE(tenant_id, intent_id, attempt_no)`, `attempt_no ≥ 1` — 재시도는 **새 행** |
| `status` | `CHECK IN ('mirrored','unavailable','refused','mismatch','invalid')` |
| `error_code` | `CHECK (error_code IS NULL OR error_code ~ '^TRACK-[0-9]{4}$')`; `status='mirrored'`이면 NULL, 아니면 NOT NULL(CHECK) |
| `tracking_uri_sha256` | §2.2 정규화 URI의 sha256(URI 원문 미저장) |
| `mlflow_experiment_id`, `mlflow_run_id`, `mlflow_model_version` | 미러 참조(nullable; `mirrored`면 kind에 맞는 참조 NOT NULL CHECK) |
| `response_payload_sha256` | attest에서 서버가 돌려준 tag/param 집합의 canonical sha256 |
| `started_at`, `finished_at`, `worker_id` | 기록 |

- **순서 고정(F-R3)**: (1) 정본 변경 + `mlflow_mirror_intents` INSERT + `outbox_events` INSERT를 **한 tx**에서 commit(기존 ADR-008 패턴, `services/evidence.py:113`). (2) worker가 outbox를 소비(`mark_published`/`attempts`/`max_attempts` 재사용, `:157-175`) → 설정·credential 해석 → push → attest → `mlflow_mirror_attempts` INSERT(append-only) → outbox published. (3) 어느 단계에서 죽어도: intent가 있고 attempt가 없으면 **pending**(crash-before-send), 재시작 시 outbox가 다시 배달.
- **idempotency·중복 배달**: 미러 생성 전에 MLflow에서 tag `inv.intent_id = <intent_id>`로 검색(experiment 범위). 있으면 새로 만들지 않고 attest만 하고 `mirrored`를 기록(send-success-before-local-record 복구). 없으면 생성 후 tag 기록. 같은 outbox event가 두 번 배달돼도 결과는 attempt 행 1개 추가·MLflow run 0개 추가.
- **불일치 표면화**: attest의 `response_payload_sha256 ≠ payload_sha256` → `mismatch`/`TRACK-0003`. 조용히 덮어쓰지 않음.

### 2.1 canonical payload bytes (`payload_sha256`)

`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`를 **UTF-8 NFC**로 인코딩한 bytes의 sha256. 규칙: (a) 키 정렬·공백 없음; (b) 문자열은 NFC 정규화; (c) 숫자: 정수는 그대로, float는 `repr()`(최단 왕복) — **NaN/±Infinity는 거부**(`TRACK-0005 payload invalid`, INSERT 전에 실패 → 정본 tx도 실패시키지 않고 의도만 생성하지 않음? — 아니다: 의도 생성 실패는 **정본 tx 실패**로 둔다. 유효하지 않은 payload를 만든 것은 우리 결함이며 조용히 미러를 빼먹지 않기 위함); (d) metric은 `{"key","value","step"(int, 기본 0),"timestamp_ms"(int, 정본 시각)}` 배열을 key·step 순 정렬; (e) `None`은 필드 생략; (f) tag 값은 문자열만. 결정성 시험: 키 순서 뒤섞기·유니코드 NFD 입력·`1.0` vs `1`·metric 순서 뒤섞기가 같은 digest, NaN/Infinity 거부.

### 2.2 URI 정규화 (`tracking_uri_sha256`)

scheme·host 소문자(IDNA 인코딩), 기본 포트(443) 제거, 경로 percent-encoding 정규화 뒤 trailing slash 제거(`/` 단독은 빈 경로), query·fragment는 **거부**(`TRACK-0004`), userinfo 거부. 동치 시험: `HTTPS://Host.Example:443/mlflow/` ≡ `https://host.example/mlflow`; 비동치: 다른 path·다른 port·`http`.

## 3. TrackingSink 계약 (adapter contract 결속)

MLflow는 프롬프트를 실행하는 Provider가 아니므로 `ProviderAdapter`(`adapters/contract.py:177`) 8 메서드를 요구하지 않고, 같은 자료형을 재사용하는 `TrackingSink`(`adapters/tracking.py`, 신규)를 둔다.

| 멤버 | 자료형/의미 | 재사용 |
|---|---|---|
| `name`, `contract_version` | `"mlflow"`, `"1.0.0"` | `_declares_version` 규칙 |
| `probe() -> ProbeResult` | 도달·API 버전 | `contract.py:77` |
| `authenticate(secret_handle) -> AuthResult` | §4의 worker 전용 handle(파일 fd), 토큰 반환 없음 | `:90` |
| `find(intent_id) -> str | None` | tag `inv.intent_id` 검색(idempotency) | 신규 |
| `mirror(record: MirrorRecord) -> MirrorResult` | `MirrorResult(status, reference_id, response_payload_sha256, error_code)` | 신규(frozen) |
| `redact(content) -> (content, bool)` | run name·param 값 ADR-014 redaction | `ReferenceAdapter.redact_text` |
| `attest(reference_id) -> Attestation` | 서버 tag 집합 sha256 ↔ `payload_sha256`; 검증 불가면 `UNVERIFIABLE`(→ `mismatch`가 아니라 `unavailable`) | `:145` |

Provider adapter의 `Attestation.model_id`·`Usage`는 eval run 미러의 param/metric으로 동반. conformance: `run_tracking_conformance`(계약 버전·멤버·probe·redaction·attest가 항상 VERIFIED를 내지 않음·mismatch 표면화·`find` 멱등) + in-memory `ReferenceSink`(PG-free). 실제 `mlflow` Client는 `MlflowSink`에서만 import(extras `mlflow`).

## 4. credential·endpoint (v1.2: 별도 operator service-credential contract — F-R2)

**결정 (b)**: 0035 `PostgresCredentialRegistry.lookup(credential_id, version_id, context, purpose, destination)`은 **project·subject·비종료 run·recovery_epoch**에 결속된 **Run 실행용** 계약이다(`inv/credential_registry.py:16-38`). 미러는 정본 커밋 **뒤**, 대개 **종료된 run**에 대해 background worker가 수행하므로 run 결속 lookup은 정의상 거부된다. 0035에 `mlflow.mirror` purpose를 추가해도 grant가 run/subject를 요구하는 구조가 남는다. 따라서 **tenant 범위 operator service credential**을 별도 계약으로 둔다.

`service_credential_versions` / `service_credential_grants`(core, 신규 migration):

| 항목 | 규칙 |
|---|---|
| `purpose` | `CHECK IN ('mlflow.mirror')`(시작 값; 확장은 migration) |
| `destination` | alias `^[a-z][a-z0-9-]{0,63}$`; §2.2 정규화 URI의 sha256을 `destination_uri_sha256`로 결속 — worker는 alias→URI 매핑이 **설정의 URI sha256과 일치할 때만** 사용(destination 결속) |
| 비밀 | 0035와 동일: 파일 `^[0-9a-f]{32}[.]secret$`, device/inode, `content_sha256`(**version pin**); DB에 raw secret 0; worker는 fd로 열어 메모리에서만 사용, 로그·evidence·attempt 행에 미기록 |
| grant | `tenant_id`, `purpose`, `destination`, `worker_principal`(service subject), `enabled`, `expires_at`, `revoked_at`, `recovery_epoch`; **run/project 결속 없음**(tenant 범위) |
| lookup | `ServiceCredentialRegistry.lookup(tenant_id, purpose, destination, worker_principal, recovery_epoch)` → 유효(enabled·미revoke·미만료·epoch 일치·content_sha256 일치)일 때만 handle; 아니면 `TRACK-0002`(refused) |
| worker 권한 | worker는 `service_credential_*` SELECT·`mlflow_mirror_attempts` INSERT·`outbox_events` UPDATE(published/attempts)만; 정본 table UPDATE 권한 없음(미러가 정본을 바꿀 수 없음을 DB 권한으로 보장) |
| 설정 | `INV_MLFLOW_TRACKING_URI`(https만·userinfo/query/fragment 거부), `INV_MLFLOW_DESTINATION`(alias), `INV_MLFLOW_EXPERIMENT_PREFIX`(`^[a-z0-9-]{1,32}$`), `INV_MLFLOW_TIMEOUT_SECONDS`(기본 5). `INV_MLFLOW_CREDENTIAL_REF`는 폐기(v1.0 문구 삭제) |
| readiness | `configurationReadiness.mlflow ∈ {configured, absent, invalid}`(#159 `objectStore` 패턴, 단일 strict source, fallback 없음). **URI가 configured인데 `mlflow` client가 없으면 `invalid`(detail `client-missing`)**, absent로 축소 금지(F-R4) |

부정 시험: raw secret이 DB/로그/attempt에 없음, 잘못된 version pin(content_sha256 불일치) 거부, revoke·만료·다른 recovery_epoch 거부, destination alias의 URI sha256 불일치 거부, worker principal 외 grant 거부, 종료 run 뒤 미러가 0035 lookup을 **호출하지 않음**.

## 5. 오류 코드·fail-closed (v1.2: 정본 형식 — F-R1)

`ProblemDetails.code` 정본 regex `^[A-Z]+-[0-9]{4}$`(`contracts/v1alpha1/core.schema.json:1737`)에 맞춰 숫자 code. category `TRACK`은 `errors.py::ErrorCategory`에 없으므로 **#167 `api/problem.py::CanonicalProblem`**(status·retryable을 code별로 명시, category `^[A-Z]+$`)이 family owner다.

| code | 의미 | status | retryable | mirror `status` | evidence verdict(#153 S12·S10 collector 집계) |
|---|---|---|---|---|---|
| `TRACK-0001` | tracking server 미도달·timeout·5xx | 503 | true | `unavailable` | **NOT_OBSERVED**(외부 미도달; 값 없음) |
| `TRACK-0002` | 401/403·service credential 해석 거부(revoke·만료·epoch·pin) | 403 | false | `refused` | **MEASURED_FAIL**(유효 설정으로 시도했고 거부됨) |
| `TRACK-0003` | attest에서 `response_payload_sha256 ≠ payload_sha256` | 409 | false | `mismatch` | **MEASURED_FAIL** + alarm 후보 |
| `TRACK-0004` | 설정 무효(scheme·userinfo·query·prefix·client-missing) | 422 | false | (호출 안 함; readiness `invalid`) | **INVALID_RUN**(우리 쪽 결함) |
| `TRACK-0005` | payload canonicalization 실패(NaN/Infinity·비문자열 tag) | 422 | false | (intent 미생성 → 정본 tx 실패) | **INVALID_RUN** |
| (code 없음) | 설정 `absent` | — | — | (sink 미생성, intent도 생성 안 함) | **NOT_OBSERVED** |
| (내부 결함) | 정본 변경이 있는데 intent 없음 / intent 있는데 outbox 없음 | — | — | — | **INVALID_RUN**(enqueue 결함; collector가 정본 행 수 ↔ intent 수 대조) |

DB CHECK: `mlflow_mirror_attempts.error_code ~ '^TRACK-[0-9]{4}$'`. schema validation 부정 시험: `TRACK-MLFLOW-UNAVAILABLE` 같은 옛 형식·소문자·3자리 숫자·category 불일치가 `ProblemDetails` schema와 `CanonicalProblem.__post_init__`에서 거부됨.

fail-closed의 뜻: **미러가 정본을 바꾸지 못하고(권한·순서), 미러 실패가 성공으로 읽히지 않으며(append-only attempt + verdict 분리), 의도 유실이 "설정 없음"으로 위장되지 않는다(intent는 정본과 같은 tx).** 제품 release·deploy는 어느 경우에도 그대로 성공한다.

## 6. 외부 부재·부분 실패 시 동작

| 상황 | 관측 |
|---|---|
| 설정 `absent` | sink 미생성·intent 미생성; readiness `absent`; collector `NOT_OBSERVED` |
| URI configured + client 미설치 | readiness `invalid`(`client-missing`), `TRACK-0004`; **absent와 다름** |
| 서버 미도달 | intent 있음·attempt `unavailable`(`TRACK-0001`), outbox 재시도(`max_attempts` 뒤 dead-letter는 attempt 행으로 남음) |
| 거부·불일치 | attempt `refused`/`mismatch`, 재시도 없음(credential 재사용 위험·불일치는 사람이 봐야 함) |
| crash-before-send | intent 있음·attempt 없음 = pending; 재시작 시 outbox 재배달 |
| send-success-before-local-record | 재배달 시 `find(intent_id)`가 기존 run을 찾아 attest만 하고 `mirrored` 기록 |

## 7. 시험 계획 (v1.2)

| 종류 | 내용 |
|---|---|
| PG-free | `run_tracking_conformance`(ReferenceSink·attest 항상-VERIFIED 금지·mismatch·`find` 멱등·redaction·secret 반향 금지); canonical payload 결정성(키 순서·NFD/NFC·`1.0` vs `1`·metric 순서·NaN/Infinity 거부); URI 정규화 동치/비동치 5+; strict config 부정(scheme·userinfo·query·prefix·client-missing → `invalid`); `CanonicalProblem` TRACK-000x code/status/retryable 표 고정 + 옛 형식·소문자·3자리 거부; verdict 매핑 표(0001→NOT_OBSERVED, 0002/0003→MEASURED_FAIL, 0004/0005/enqueue 결함→INVALID_RUN, absent→NOT_OBSERVED); 정본 경로(`record_deployment` 등)가 sink 유무·실패에 무관하게 같은 결과 |
| 실 PG(hosted Backend) | intent+outbox 한 tx(정본 rollback 시 둘 다 없음); `num_nonnulls` XOR CHECK·kind↔컬럼 CHECK·error_code CHECK·UNIQUE(intent, attempt_no) 위반 거부; attempt append-only(UPDATE/DELETE 거부); worker role이 정본 table UPDATE 불가; service credential lookup 부정 6종(§4); crash-before-send(intent만 존재 → pending 집계); duplicate delivery(같은 event 2회 → attempt 1행·`find` 호출 1회); retry 새 행; 종료 run 뒤 미러가 0035 lookup 미호출 |
| hosted lane(선택, #159 MinIO 패턴) | digest-pinned MLflow 컨테이너 + disposable PG로 push→find→attest 1회; runner 없으면 exact map에 `NOT_OBSERVED` 선언 |
| 운영 실측 | G1b — 실제 endpoint·service credential(BLOCKED_EXTERNAL) |

## 8. 경계·다음

- docs-only. 코드·계약·migration 변경 0. **구현은 Codex 설계 승인 뒤** 별도 카드(예상 범위: `adapters/tracking.py`·`MlflowSink`·`ReferenceSink`·migration 2(`mlflow_mirror_intents`·`mlflow_mirror_attempts`)+service credential 2·outbox 훅·worker·`api/problem.py` TRACK family·readiness 필드·시험).
- 관련: S10-BE Evidence 대응표(PR #166) G1a/G1b, S10-DB lineage 조회 API 설계(PR #158 — 미러 참조를 응답에 포함할지는 그 설계의 후속), VF-CL-03 canonical ProblemDetails(PR #167), CL-06.
- owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s10-be-mlflow-design`, base `1e8baf04`. 다음 첫 행동: Codex delta 재검토(F-R1~F-R4) → 승인 뒤 구현 카드.
