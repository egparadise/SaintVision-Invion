---
doc_id: "HIST-CLAUDE-2026-09-28-S10-BE-MLFLOW-MIRROR-IMPL-1"
title: "S10-BE MLflow 미러 구현 1단계 — TrackingSink 계약·run_tracking_conformance·ReferenceSink, TRACK-0001~0005 표, canonical payload/URI, migration 0049(intents·attempts·defects, append-only·RLS·CHECK), 정본 tx enqueue 훅, deliver_intent(FOR UPDATE·terminal 반환), PG-free 76 + 실 PG 42(hosted) (카드 bg)"
version: "1.3.1"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T12:59:25+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["S10-BE", "AC-10", "mlflow", "tracking", "mirror", "migration", "claude"]
---

# S10-BE MLflow 미러 구현 1단계 (2026-09-28, 카드 bg)

설계 문서(PR #168 `S10-BE MLflow 연동 설계 v1.0.md`) v1.3(, Codex 승인, 결정 B)을 그대로 구현한다. **실제 MLflow HTTP client와 operator service credential은 2단계**로 분리했고 이 PR에는 없다(`import mlflow` 0건).

## 1. 만든 것

| 영역 | 파일 | 내용 |
|---|---|---|
| canonical | `src/saintvision/tracking/canonical.py` | §2.1 그대로: bool 먼저, 정수값 float→int(`abs ≤ 2**53`), 그 밖 `repr`, NaN/Inf·Decimal·bytes·비문자열 key·list 안 None 거부, NFC 재귀 + NFC 뒤 충돌 key 거부, None 필드 생략, metric `(key, step)` 정렬·tag는 str→str, `json.dumps(sort_keys, separators, ensure_ascii=False, allow_nan=False)` UTF-8 → `payload_sha256`. 거부는 `CanonicalizationError(reason_class ∈ 5종)`. §2.2 URI 정규화(`https`만, host 소문자·IDNA, 443 제거, path 재인코딩·trailing slash 제거, userinfo/query/fragment 거부) → `tracking_uri_sha256` |
| codes | `src/saintvision/tracking/codes.py` | `TRACK-0001~0005` 표를 code별 status·retryable·mirror status·verdict로 고정(`^[A-Z]+-[0-9]{4}$`). `verdict_for_attempt`(mirrored=MIRRORED, 0001=NOT_OBSERVED, 0002/0003=MEASURED_FAIL) · `verdict_for_unattempted`(absent=NOT_OBSERVED, invalid=INVALID_RUN, intent만=pending NOT_OBSERVED, defect=INVALID_RUN, 둘 다 없음=INVALID_RUN). **#167 `api/problem.py`를 import하지 않음**(미병합) — 병합 뒤 route가 `entry(code)`로 `CanonicalProblem`을 만들면 되고 충돌 파일 0 |
| config | `src/saintvision/tracking/config.py` | `INV_MLFLOW_TRACKING_URI/DESTINATION/EXPERIMENT_PREFIX/TIMEOUT_SECONDS` strict 단일 source. readiness `absent`(전부 미설정)/`configured`/`invalid`(detail: partial·uri:*·destination·prefix·timeout·**client-missing**, TRACK-0004). URI가 있고 client가 없으면 invalid이지 absent가 아님(F-R4) |
| 계약 | `src/saintvision/adapters/tracking.py` | `TrackingSink` Protocol(name·contract_version·probe·authenticate·find·mirror·redact·attest; `ProbeResult`·`AuthResult`·`Attestation` 재사용), `MirrorRecord`(digest 결속)·`MirrorResult`(status↔code 일관), `run_tracking_conformance` 12 check(버전·멤버·probe·handle 미반향·find 사전 None·mirror 코드·find 멱등+같은 intent 재mirror가 2번째 run 안 만듦·redaction 2·attest가 mirror한 digest와 일치·미지 참조 VERIFIED 금지·tamper 시 MISMATCH) |
| 참조 sink | `src/saintvision/adapters/tracking_reference.py` | in-memory `ReferenceSink`(PG-free): `inv.intent_id`로 find, 저장 tag 집합 재digest로 attest(실패 가능), `fail_with(status, times)`·`tamper(ref)` 명시 결함 주입, 호출 횟수 기록 |
| DB | `migrations/versions/0049_mlflow_mirror.py`, `src/saintvision/db/models/tracking.py` | `mlflow_mirror_intents`(PK(tenant,intent), 정본 4 table composite FK, `num_nonnulls` XOR + kind↔컬럼 CHECK, `payload_sha256` hex CHECK, outbox `event_id` FK, 같은 subject+payload UNIQUE 표현식 index), `mlflow_mirror_attempts`(tenant 열·composite FK, `attempt_no ≥ 1` UNIQUE, `(outbox_event_id, delivery_no)` UNIQUE, status 5종, `error_code ~ '^TRACK-[0-9]{4}$'`, mirrored ⟺ code NULL, mirrored → reference NOT NULL), `mlflow_mirror_defects`(reason_class 5종, payload 미저장). 셋 다 **INSERT/SELECT만**·RLS FORCE·`_tenant_isolation` policy; `TENANT_SCOPED_TABLES`·`APPEND_ONLY_TABLES` 등록; ids prefix `mmi/mma/mmd` |
| 서비스 | `src/saintvision/services/tracking.py` | `enqueue_mirror`: readiness≠configured → skipped(행 0); canonicalize 실패 → **같은 tx에 defect 1행**(TRACK-0005, reason_class), intent 0; 같은 subject+digest 존재 → existing(no-op); 아니면 outbox `inv.mlflow.mirror.requested` + intent **같은 tx**. `deliver_intent`: intent `FOR UPDATE` → terminal attempt 있으면 그 행 반환(sink 호출 0) → `COALESCE(MAX(attempt_no),0)+1` → `find` → 없으면 `mirror` → `attest`(VERIFIED+digest 일치=mirrored / MISMATCH·불일치=mismatch 0003 / UNVERIFIABLE=unavailable 0001) → attempt 1행. payload 빌더 3종(참조·digest만, 바이트 0) |
| 훅 | `src/saintvision/services/lineage.py`, `src/saintvision/services/evaluation.py` | `register_model_version`·`record_deployment`·`finish_eval_run` 끝에서 `enqueue_mirror` 호출(정본 flush 뒤, 같은 tx). 정본 결과·예외 경로 변경 0 |

설계와의 차이(v1.2에서 정정): (a) **`project_id`는 `eval_run` subject에서만 NULL 허용**(`project_bound_unless_eval_run` CHECK; `eval_runs`에 project 열이 없음). (b) **§2의 `FOR UPDATE` 대신 `pg_advisory_xact_lock`**(intents는 append-only라 app role에 UPDATE 권한이 없고, 행 잠금은 UPDATE 권한을 요구 — §5 아래 설명). (c) 훅은 v1.2에서 §1 표 전부로 확장(아래 §5). 그 밖의 차이 없음.

## 2. 시험

| 파일 | 종류 | 내용 |
|---|---|---|
| `tests/test_tracking_canonical.py` | PG-free | §2.1 결정성·부정 전부(키 순서, 중첩 NFD/NFC, 충돌 key, `1.0`=`1`, `-0.0`=`0`, `1e3`=`1000`, `2**53+1` 보존, `True`≠`1`, `0.1` repr, NaN/Inf/Decimal/bytes/list-None/비문자열 key 거부, metric 순서·기형 7, tag 비문자열), §2.2 동치 1/비동치 3/거부 7, TRACK 표 고정·옛 형식/소문자/3자리/미정의 거부·verdict 매핑, readiness(absent·partial·configured·invalid 8종·client-missing) |
| `tests/test_tracking_sink.py` | PG-free | ReferenceSink 12/12 conformant + Protocol; 고장 sink 7종이 각각 해당 check만 실패(항상 VERIFIED, handle 반향, find 망각, 같은 intent 2번째 run, redaction 없음, 다른 버전, 예외); 결함 주입·tamper·handle 미반환·Record/Result 형태 |
| `tests/test_tracking_mirror.py` | **실 PG(hosted Backend)** | intent+outbox가 정본과 한 tx / rollback 시 셋 다 없음 / deployment·eval_run 훅 / absent·invalid 시 행 0·정본 동일 / canonicalize 실패 → 정본 커밋+defect 1·intent 0 / defect INSERT 차단(31자 id) → 정본 tx 전체 실패 / 멱등 enqueue / intent CHECK 8종·attempt CHECK 9종·UNIQUE 2 / 3 table UPDATE·DELETE permission denied / RLS 미설정·타 tenant 0 / **중복 배달 → attempt 1행·find 1·mirror 1** / unavailable 뒤 재배달 → attempt_no 2 / refused terminal / 원격 run만 있음 → attest만 mirrored / tamper → mismatch terminal / UNVERIFIABLE → unavailable / **경쟁 consumer 2 thread → 1행** / 배달이 정본 미변경 / 미지 intent LookupError |

로컬(가벼운 명령만): PG-free `test_tracking_canonical`+`test_tracking_sink`+`test_migrations`+`test_adapters` **124 passed**; `test_tracking_mirror` 42 skipped(DSN 없음, hosted에서 실행). `alembic upgrade head --sql` offline render OK(mlflow_mirror 57줄), `tools/migration_graph.py` head 단일 `0049_mlflow_mirror`.

## 3. migration 순서 (코디네이터 결정 2026-09-28 12:23 KST, v1.1 2026-09-28T12:24:55+09:00)

순서를 하나로 고정: **0047_audit_events_isolation(#128) → 0048_object_store_locator(#159) → 0049_mlflow_mirror(이 PR) → 0050(카드 be)**. 처음 push(head 44654021)는 `down_revision=0046`이었고 #128·#159가 먼저 병합되면 head가 둘로 갈라졌다. 조치: origin의 #159 head(`249b73e2`)를 이 branch에 **merge**(force-push 없음)하고 `down_revision`을 `0048_object_store_locator`로 변경. 충돌은 진행판·Claude 작업판 2개(양쪽 본문 모두 유지, version은 큰 쪽+1). PR base는 integration 그대로, **병합은 #159 뒤**. #159 head가 바뀌면 다시 merge한다. 확인: `tools/migration_graph.py` head 단일 `0049_mlflow_mirror`, `tests/test_migrations.py`.

## 4. 경계·다음

- 2단계(별도 카드): `MlflowSink`(실 HTTP, extras), `service_credential_*` migration 2 + `ServiceCredentialRegistry`, outbox consumer 배선(`claim_pending_events` → `deliver_intent`), readiness를 `configurationReadiness.mlflow`에 노출(#159 objectStore 패턴 병합 뒤), collector INVALID_RUN 대조(§5.1).
- owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s10-be-mlflow-mirror-impl`, base `1e8baf04`, force-push 없음. 시각은 `date`.

## 5. Codex 1차 검토 반영 (v1.2, 2026-09-28T12:46:08+09:00; head 322488fb → 수정 head)

hosted Backend run **36373656210**(head 322488fb) = 3.12 **3138 passed / 47 skipped / 2 deselected / 35 failed**, 3.14 동류. 실패 35 분류: **#159 merge 상호작용 22**(`tools/definer-policy.json`과 #159 시험이 head를 `0048`로 고정 → 0049가 head가 되며 `migration_revision_mismatch`; `check_migration_upgrade`도 마지막에 definer audit을 돌려 같은 원인) / **#172 자체 결함 13**(`FOR UPDATE` 권한, 시험 fixture 3종).

| # | 지적 | 반영 |
|---|---|---|
| 1 (차단) 정본→미러 매핑 누락 | 훅이 3곳뿐(등록·배포·eval 종료); Experiment·학습 run·suite 식별/분류 점수·release stage 전이 없음; History "차이 1건" 오기 | 훅 **§1 전부**: `enqueue_mirror`가 project의 **첫 intent에서 `experiment` intent를 같은 tx에 자동 생성**; `runs.complete_run` → `training_run`(workload spec sha·objective·contract_version·evidence_id·termination_reason); `release_model_version` → 별도 `model_version` intent(`inv.stage=released`, verified/pinned ms); `finish_eval_run` payload에 suite name/version/definition_sha256 + **분류별 pass_rate/mean_score metric**. artifact 참조는 model_version payload의 uri·content_sha256·byte_size(설계 §1 "참조만"). 시험: 경로 5(등록·release·배포·eval·training run)마다 intent+outbox 확인 + **rollback 5 parametrize**(intent·defect·정본·event 전부 0) |
| 2 (차단) status↔code 결속이 regex뿐 | `MirrorResult(REFUSED, "TRACK-0001")` 허용, DB도, `verdict_for_attempt`가 교차검증 없이 NOT_OBSERVED; `code_for_status(INVALID)→0005` | 정본 하나 `codes.STATUS_CODE_PAIRS`(mirrored/None·unavailable/0001·refused/0002·mismatch/0003). `check_pair`를 `MirrorResult.__post_init__`·`deliver_intent`·`verdict_for_attempt`가 호출; DB CHECK `status_code_pair`는 migration에 literal로 박고 시험이 `codes.sql_pair_check()`와 동일함을 고정. **`invalid` status 삭제**(0004/0005는 sink 전 결정, attempt 없음). 되살림: PG-free 4 status × 6 code 전 조합(맞는 4쌍만 통과), `MirrorResult` wrong-pair 6, DB wrong-pair 6 + 옛 형식 3 + `invalid` 1 |
| 3 (차단) delivery identity 미결속 | `deliver_intent`가 인자 event id를 그대로 기록, attempts에 outbox FK 없음 | 서비스: lock 뒤 `outbox_event_id != intent.outbox_event_id`면 **`DeliveryIdentityError`(sink 호출 0·행 0)**, 기록은 `intent.outbox_event_id`. DB: `outbox_events (tenant_id, event_id)` UNIQUE index 신설 → intents `(tenant_id, outbox_event_id)` FK, intents `UNIQUE(tenant_id, intent_id, outbox_event_id)` → attempts **composite FK `(tenant_id, intent_id, outbox_event_id)`** + `(tenant_id, outbox_event_id)` FK. 시험: 다른 event 주입 2형(실재 event·부재 event) → 예외·sink 0·attempt 0; 타 tenant → LookupError; DB 직접 INSERT 다른 event → FK 위반 |
| hosted 실패 (a) #159 상호작용 22 | policy·#159 시험 0048 고정 | `tools/definer-policy.json` `revision` → `0049_mlflow_mirror`(**functions 13 catalogue 불변**), #159 시험 2개를 "0048 속성 + head=0049" 로 재고정 |
| hosted 실패 (b) `FOR UPDATE` permission denied 9 | intents가 append-only(SELECT/INSERT)라 행 잠금 불가 | **`pg_advisory_xact_lock`**(tenant:intent sha256 8byte 키)로 직렬화. 권한 추가 0, append-only 유지. 경쟁 consumer 시험은 그대로(잠금 대기 → terminal 반환 → 1행) |
| hosted 실패 (c) fixture 3 | `verify_model_version` `content_sha256` 누락; 옛 긴 code가 varchar(16) DataError; `status='done'`이 pair CHECK에 먼저 걸림 | `_release` helper에 `content_sha256=WEIGHTS_SHA`; 옛 형식은 14자; 각 행이 기대 제약 **집합** 중 하나를 맞히도록 독립 fixture 15 |

로컬(3.10, 가벼운 명령): PG-free `test_tracking_canonical`+`test_tracking_sink`+`test_migrations`+`test_adapters` **160 passed**; offline render에 새 DDL 3(outbox unique·pair CHECK·composite FK) 존재; `migration_graph` head 단일 0049. `tests/core/test_object_store_locator_migration.py`는 3.11+ 전용(`StrEnum`)이라 로컬 미실행 → hosted. `test_tracking_mirror` **62 case**(hosted).

## 6. Codex 2차 반영 — 첫 Experiment intent 경쟁 (v1.3, 2026-09-28T12:55:53+09:00)

지적: 같은 project의 두 canonical mutation이 동시에 첫 intent를 만들면 둘 다 experiment 부재를 관측해 같은 digest를 INSERT하고, `uq_mlflow_mirror_intents_subject_payload`가 한쪽을 IntegrityError로 막으며 **그 canonical mutation 전체가 rollback**된다(결정 B 위반). 반영:

- `enqueue_mirror`가 readiness 확인 직후 **`pg_advisory_xact_lock("enqueue", tenant, project)`**(eval_run은 subject 키)를 잡는다. 같은 project의 두 번째 enqueue는 첫 tx의 **commit까지 대기**한 뒤 존재 검사를 하므로 experiment를 보고 만들지 않는다. 같은 잠금이 subject intent의 존재 검사도 덮어 동일 intent 경쟁은 `existing`이다. IntegrityError 경로는 남지 않는다(outbox 먼저·`ON CONFLICT` 방식의 고아 event 문제 없음: intent와 event가 같은 tx에서 함께 만들어지고 함께 commit).
- 부정 시험 `test_two_concurrent_first_intents_of_one_project_commit_both_with_exactly_one_experiment`: config absent로 model version 2개 준비 → thread A가 enqueue 뒤 tx를 열어둔 채 대기, thread B enqueue가 잠금에 막힘(0.5s 뒤 결과·오류 없음 확인) → A commit → B 진행. 기대: 오류 0, **experiment intent 1**, subject intent 2(각자 event 보존), mirror event 3 = intent의 event 집합(고아 0), ModelVersion 2 모두 commit.

**Durable 후속 공백(1단계 범위 밖, Codex 관찰)**: 일반 `artifacts` row와 학습 run의 `output_ref`(evidence 산출물)는 미러하지 않는다. 지금 미러되는 artifact 참조는 model_version payload의 `uri`·`content_sha256`·`byte_size`뿐이다. 후속 카드 후보: "artifact 참조 미러(`artifacts` checksum·`inv://` URI를 run tag로)". 2단계(카드 bh)에도 포함되지 않는다.

### 6.1 Codex r3 (v1.3.1, 2026-09-28T12:59:25+09:00) — 경쟁 시험 정정

지적: 시험이 ModelVersion 2개를 config absent인 선행 tx에서 미리 commit하고 thread에서는 `enqueue_mirror`만 호출해 "canonical mutation과 mirror의 같은-tx 결속" 변이가 생존하며, `sleep(0.5)`는 B가 잠금에 도달했다는 신호가 아니다. 정정: 두 thread가 각각 **실제 `register_model_version`(훅 포함)을 자기 tx 안에서** 호출(version 1.0.0/`a`*64, 1.0.1/`b`*64). A는 등록 뒤 tx를 열어둔 채 대기. `_serialize_enqueue`를 감싼 wrapper가 thread B의 잠금 진입 직전에 event를 set → main이 그 신호를 기다린 뒤(0.3s 뒤 B 미완료·오류 없음 확인) A를 release. 기대 그대로: canonical row 2, subject intent 2, experiment 1, event 3 = intent 집합, 오류 0. 잠금 제거 변이(B가 experiment 중복 INSERT → 롤백)와 "canonical 먼저 commit 뒤 mirror 별도 tx" 변이가 각각 죽는다.
