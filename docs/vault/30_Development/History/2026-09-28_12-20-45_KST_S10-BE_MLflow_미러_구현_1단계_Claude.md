---
doc_id: "HIST-CLAUDE-2026-09-28-S10-BE-MLFLOW-MIRROR-IMPL-1"
title: "S10-BE MLflow 미러 구현 1단계 — TrackingSink 계약·run_tracking_conformance·ReferenceSink, TRACK-0001~0005 표, canonical payload/URI, migration 0049(intents·attempts·defects, append-only·RLS·CHECK), 정본 tx enqueue 훅, deliver_intent(FOR UPDATE·terminal 반환), PG-free 76 + 실 PG 42(hosted) (카드 bg)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T12:24:55+09:00"
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

설계와의 차이 1건(명시): **`project_id`는 `eval_run` subject에서만 NULL 허용**(`project_bound_unless_eval_run` CHECK). `eval_runs`에 project 열이 없어 결속할 대상이 없다(설계 §2는 NOT NULL). 수정안은 Codex 검토 대상.

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
