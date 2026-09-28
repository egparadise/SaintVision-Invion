---
doc_id: "HIST-CLAUDE-2026-09-28-S10-BE-MLFLOW-MIRROR-IMPL-2"
title: "S10-BE MLflow 미러 구현 2단계 — 실 MLflow REST sink(push-only, transport seam, TRACK 매핑, provider 문구 비노출), tenant 범위 service credential 계약(0051, 0035 경계), worker 경로(credential→sink→deliver_intent, 부재·거부는 NOT_OBSERVED·refused), PG-free fake transport 20 + 실 PG 24 + opt-in run-mlflow live lane (카드 bh, PR #172 위 stack)"
version: "1.2.2"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T14:04:26+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "41256e4f"
task_ids: ["S10-BE"]
tags: ["S10-BE", "AC-10", "mlflow", "tracking", "credential", "ci", "claude"]
---

# S10-BE MLflow 미러 구현 2단계 (2026-09-28, 카드 bh)

1단계(PR #172, 설계 PR #168 v1.3) 위에 stack. PR base는 #172 branch이며 **#172 병합 뒤** 병합한다. 설계 §3·§4·§6을 따른다.

## 1. 만든 것

| 영역 | 파일 | 내용 |
|---|---|---|
| (1) 실 sink | `src/saintvision/adapters/mlflow_sink.py` | `MlflowSink(TrackingSink)` over REST(`/api/2.0/mlflow`). **push-only**(experiments get-by-name/create → runs/create(tag `inv.intent_id`·`inv.payload_sha256`·`inv.subject_kind`·**`inv.payload`=canonical bytes**) → runs/log-batch(param은 str, metric은 number) → model_version이면 registered-models/create + model-versions/create(우리 stage는 tag만, stage API 미사용) → runs/update FINISHED). 읽기 경로는 attest용 `runs/get` tag 재digest뿐. `Transport` seam 1 메서드; 기본 `UrllibTransport`(timeout ≥1s, redirect 거부, body 1MiB 상한, 오류 body 폐기). **오류 매핑**: 무응답/timeout/5xx → `TRACK-0001` unavailable, 401/403 → `TRACK-0002` refused, 그 밖 4xx(우리 요청 결함) → `MlflowRequestInvalid(TRACK-0004)` 예외(attempt 없음, outbox 정책이 재시도/정지). provider 오류 문구는 transport 경계에서 폐기되어 result·예외·로그 어디에도 없음. `find`는 서버가 "없음"을 답한 경우에만 None, 물어볼 수 없으면 `MirrorFailure(result)`로 raise → worker가 그 코드로 attempt 기록(중복 run 방지). `authenticate(handle)`는 handle.use(cb) 1회, bearer를 private 속성에만 보관(반환·repr·로그 없음). 설정 경로는 https만; 루프백 http는 `allow_insecure_loopback=True`로 sink를 직접 만들 때만(hosted lane) |
| (2) service credential | `migrations/versions/0051_service_credentials.py`, `src/saintvision/db/models/service_credentials.py`, `src/saintvision/tracking/service_credentials.py` | `service_credential_versions`(tenant·credential uuid·version uuid PK, purpose CHECK `mlflow.mirror`, destination alias regex, **`destination_uri_sha256`**(§2.2 정규화 URI digest = 설정 URI와 일치할 때만 사용), file_name `^[0-9a-f]{32}[.]secret$`, device/inode, content_sha256 **version pin**, revoked_at) + `service_credential_grants`(worker_principal regex, enabled, expires_at, revoked_at, recovery_epoch; **project/run 결속 없음**). raw secret 0. app role INSERT/SELECT + column UPDATE(`revoked_at`; grants `enabled`,`revoked_at`)만, RLS FORCE. `ServiceCredentialRegistry.lookup(LookupRequest)`가 조건 전부를 한 query로 검사 → `CredentialBinding`/None(=TRACK-0002). **0035 경계**: `inv.credential_*`는 run 결속(project·subject·비종료 run·epoch) Run 계약이라 종료 run 뒤 background 미러에서는 정의상 거부되므로 호출하지 않음(spy 시험). 파일 읽기는 기존 `credentials/linux_file.py`(fd·device/inode·mode·nlink·size·sha 검사)를 `ServiceRegistryAdapter`(0035 lookup 시그니처)로 **재사용** — 판정 로직 복제 0 |
| (3) worker 경로 | `src/saintvision/services/tracking.py` | `resolve_sink`(registry lookup → 없으면 `RefusingSink` → 있으면 sink_factory(settings) + `LinuxFileCredentials(root, adapter).resolve(svcred ref, worker_context)` → `sink.authenticate(handle)`; 거부·읽기 실패도 RefusingSink), `deliver_outbox_event(event)`: readiness absent/invalid → **None, attempt 0, event pending 유지**(NOT_OBSERVED/INVALID_RUN by readiness); payload `intentId` ≠ `aggregate_id` → `DeliveryIdentityError`; `RefusingSink`는 같은 `deliver_intent` 경로로 **refused TRACK-0002 attempt 1행**(네트워크 0). release·deploy는 미러 결과와 무관하게 성공(시험) |
| (4) hosted lane | `.github/workflows/backend.yml` job `mlflow-live` | `run-mlflow` label opt-in(push/dispatch는 항상). `ghcr.io/mlflow/mlflow:v2.17.2`를 `docker run`(`mlflow server --host 0.0.0.0 --port 5000`, sqlite backend) → `/health` 대기 → `tests/integration/test_mlflow_live_conformance.py`(probe 버전, **`run_tracking_conformance` 12/12 live**, mirror→find→attest 왕복·재배달 멱등). **digest pin은 NOT_OBSERVED**(tag pin; workflow owner Codex가 검증 뒤 digest로 고정). workflow 변경은 job 1개 추가뿐 |

## 2. 시험

| 파일 | 종류 | 내용 |
|---|---|---|
| `tests/test_mlflow_sink.py` | PG-free, fake transport | https-only·루프백 예외, 기본 transport 상한/redirect 거부, **요청 형식**(경로 순서 6, tag 4 + canonical payload tag = `canonical_bytes`, param str/metric number, experiment 생성), model_version 등록(stage API 미호출·재등록 400 허용), find 선행 멱등(재배달 create 0), 오류 매핑(무응답·5xx 4·401/403 → 코드, provider 문구 부재; 4xx → `MlflowRequestInvalid` 0004; 단계별 detail), attest(VERIFIED digest 결속·변조/삭제 MISMATCH·부재 UNVERIFIABLE), authenticate(1회·header만·None/공백/비handle/예외 → 0002, 문구 비노출), probe 버전, **conformance 12/12 over fake** |
| `tests/test_service_credentials.py` | 실 PG(hosted) | 유효 grant → binding(secret 열 없음), **부정 9**(grant revoke·disable·만료·epoch·version revoke·타 principal·타 destination·alias↔URI 불일치·설정 URI 불일치), LookupRequest 형태, adapter 0035 시그니처(tenant·principal·purpose·destination 결속 6), version CHECK 5·grant CHECK 3, lifecycle column만 UPDATE·DELETE 거부 6, RLS, **worker 경로**: 무grant → refused attempt 1·sink 0·**0035 lookup 0(spy)**, grant 있으나 파일 미admit → refused, absent → None·event pending·sink 0, payload intent 불일치 → DeliveryIdentityError, release·deploy가 미러 거부와 무관하게 성공(attempt=intent 수, 전부 0002) |
| `tests/integration/test_mlflow_live_conformance.py` | hosted opt-in lane | 위 (4) |

로컬(3.10, 가벼운 명령): PG-free `test_mlflow_sink`+`test_tracking_canonical`+`test_tracking_sink`+`test_migrations`+`test_adapters`+`test_service_credentials`(PG-free 1) **180 passed / 24 skipped(DSN 없음)**; offline render에 0051 DDL 존재; `migration_graph` head 단일 `0051_service_credentials`. `tests/integration`은 3.11+ 전용(`inv.state` StrEnum)이라 로컬 미수집 → hosted.

## 3. migration 순서 (코디네이터 13:06 KST, v1.1 2026-09-28T13:06:57+09:00)

**0047(#128) → 0048(#159) → 0049(#172) → 0050(#174 `0050_dataset_digest_lookup`) → 0051(이 PR)**. 첫 push(head c7e6c1c9)는 `down_revision=0049`라 #174와 head가 갈라졌다. 조치: origin의 #174 head `4e575faf`를 이 branch에 merge(force-push 없음, 충돌은 Claude 작업판 1개: 양쪽 유지·version max+1)하고 `0051.down_revision = "0050_dataset_digest_lookup"`. 병합 순서 **#172 → #174 → #176**. 확인: `migration_graph` head 단일 `0051`, `test_migrations` 통과, hosted Backend.

## 4. 경계·다음

- 범위 밖(durable): 일반 `artifacts` row·학습 `output_ref` 미러(1단계 History §6과 동일), MLflow 컨테이너 digest pin, operator provisioning CLI(secret 파일 배치·version INSERT), outbox consumer 루프 배선(`claim_pending_events` → `deliver_outbox_event` → `mark_published`)은 서비스 함수까지만이고 데몬 배선은 없음, readiness의 `configurationReadiness.mlflow` 노출(#159 패턴 병합 뒤).
- owner Claude / reviewer Codex / 병합 금지(#172 뒤). branch `agent/claude/s10-be-mlflow-mirror-p2`, base #172 head `41256e4f`, force-push 없음, 시각 `date`.

## 5. Codex 1차 검토 + hosted 결과 반영 (v1.2, 2026-09-28T13:27:20+09:00)

hosted(head 6cfe4a76): Backend run **36376369209** 3.12 = **3249 passed / 50 skipped / 2 deselected / 27 failed**; mlflow-live run **36376769104**(Codex가 label `run-mlflow` 생성·dispatch) = **2 passed / 1 failed**(서버 기동·`run_tracking_conformance` 12/12 live 통과).

실패 27 분류: **head pin 상호작용 22+1**(`tools/definer-policy.json`과 #159 시험이 #174의 0050을 head로 고정 → 0051이 head가 되며 `migration_revision_mismatch`; `check_migration_upgrade`도 같은 원인) / **#172 결함 2**(canonical 재정규화·NULL CHECK — #172 bda7ef86에서 수정, 이 branch에 merge) / **#176 자체 1**(`test_a_valid_grant_but_unreadable_file…`: `ReferenceSink.authenticate`가 handle을 읽지 않아 mirrored — 시험이 handle을 소비하는 sink를 쓰도록 정정; 실 `MlflowSink`는 원래 읽음) / **#174 관찰 1**(`test_lineage_digest_index_real_pg::test_35` planner가 `uq_dataset_versions_tenant_id_version_id`를 선택 — #174(Claude tab) 소관, 이 PR 변경과 무관, Claude tab에 통지).

| # | 지적 | 반영 |
|---|---|---|
| 1 (차단) 원격 부분 쓰기 승격 | runs/create 뒤 log-batch·model-version·update 실패 시 RUNNING run이 남고 다음 delivery의 `find`가 그 id를 돌려주며 attest가 create 시 쓴 tag digest만 봐 `mirrored`로 승격 | **완료 marker를 마지막에**: `runs/set-tag inv.mirror_complete = payload_sha256` → `runs/update FINISHED`. `find`는 marker == `inv.payload_sha256`이고 status FINISHED인 **complete run만** 반환; 불완전 run은 `_find_any`로 찾아 `mirror`가 **같은 run을 resume**(runs/create 재호출 0; log-batch 재기록은 동일 값이라 멱등; model version은 `model-versions/search run_id=`로 **run당 최대 1**). `attest`는 marker/FINISHED 없으면 **UNVERIFIABLE**(→ unavailable, 재시도) — VERIFIED는 marker·payload tag digest 일치 시에만. 시험: post-create 6단계 각각 5xx 주입 → unavailable·find None·attest UNVERIFIABLE → 재배달이 같은 run 완성(create 0, params 기록, model version 1, marker, FINISHED, find/attest VERIFIED); set-tag 403 → refused |
| 2 (차단·보안) revoke/disable 되살림 | column UPDATE가 양방향이라 `revoked_at=NULL`·`enabled=true` 복원 가능 | 0051에 BEFORE UPDATE trigger `service_credential_lifecycle_forward`(plain plpgsql, SECURITY DEFINER 아님 → definer catalogue 불변): `OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at` → `revocation_is_final`; grants `false→true` → `disable_is_final`(ERRCODE check_violation). 시험: 5 역방향 UPDATE 거부(grant NULL 복원·시각 변경·재enable, version NULL 복원·시각 변경) + lookup 여전히 None, 순방향 1회·멱등 허용 |
| live 1 failed | `GET /version`이 **plain text**("2.17.2")라 JSON 파싱 실패 → `api_version=None` | `_call`이 JSON이 아닌 짧은 본문(≤64자)을 `value`로 유지 → probe가 버전을 보고. 시험: JSON·plain text·HTML(버전 아님) 3형 |
| head pin | policy·#159 시험이 0050 고정 | `tools/definer-policy.json` revision → `0051_service_credentials`(catalogue 13 불변), 시험은 0048·0049·0050 속성 + head=0051 |

동시에 #174 head `51f4f426`(#172 bda7ef86 포함)를 merge. 로컬 PG-free 192 passed / 30 skipped; offline render에 trigger DDL 존재; `migration_graph` head 단일 0051. **digest pin은 여전히 NOT_OBSERVED**(Codex 관찰과 동일).

### 5.1 Codex r2 — trigger 분리 (v1.2.1, 2026-09-28T13:40:09+09:00)

hosted(39f1a9da): mlflow-live run 36377857338 **3 passed**(version·conformance·roundtrip). Backend 3.14 job 108787266063 **7 failed / 3287 passed / 50 skipped / 2 deselected**: 공유 trigger가 versions row에서도 `OLD.enabled`를 평가(PL/pgSQL은 `TG_TABLE_NAME = … AND` 뒤 field 접근을 건너뛰지 않음) → `record "old" has no field "enabled"`. 반영: **함수 2개로 분리** — `service_credential_revocation_forward`(revoked_at만; 두 table에 `BEFORE UPDATE OF revoked_at`)와 `service_credential_grant_disable_forward`(enabled만; grants에 `BEFORE UPDATE OF enabled`). 시험: table별 순방향 5 parametrize(versions revoke, grants revoke, grants disable, 멱등, 동시) + 기존 역행 거부 5(두 table 각각) 유지.

### 5.2 hosted run 36379482254(head 5886921c) — exact skip-map (v1.2.2, 2026-09-28T14:04:26+09:00)

Backend 3.12·3.14 모두 **3298 passed / 50 skipped / 2 deselected / 0 failed**, mlflow-live 3 passed. job이 red인 이유는 시험이 아니라 post-test **exact skip-map 단언**: `tests/integration/test_mlflow_live_conformance.py`가 이 job에서 `Set INV_MLFLOW_LIVE_URI (the run-mlflow lane starts the server)` 사유로 3 skip → 고정 map(47)과 불일치. 반영: `backend.yml`·`core.yml`의 `expected_skips`에 그 사유 **3**을 추가(가시적 skip, 성공으로 세지 않음; Core도 tests/integration을 수집하므로 동일). 그 밖 변경 0.
