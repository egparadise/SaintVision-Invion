---
doc_id: "CLAUDE-G04-W3-VERIFY-SEAM-DESIGN-001"
title: "G-04 W3 verify trusted-worker 측정 seam 설계 v1.1 — kernel outbound channel이 신원 정본(node-model-measure-v1), 단일 immutable DataLocation만 v1, measurement가 verified 상태에 DB로 결속(0054: inv.model_version_measurements + model_versions.verified_measurement_id), generic EvidenceEnvelope 미연결, W3 3-span 재결속, 시험 보강 (카드 83, Codex 계약 v1.1 반영, docs-only)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T19:00:18+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-ST"]
tags: ["G-04", "W3", "verify", "trusted-worker", "measurement", "node-channels", "design", "claude"]
---

# G-04 W3 verify trusted-worker 측정 seam 설계 v1.1 (2026-09-28, 카드 83)

> [!note] 범위
> G-04·G-05 설계 v1.2.1(#183)에서 **보류**된 W3 `POST /projects/{p}/models/{model_id}/versions/{version}/verify`. 보류 이유(Codex): `services/lineage.py:279` `verify_model_version`의 정본은 "trusted worker가 실제 weights를 해시했다"인데, 승인 사용자가 DB의 `content_sha256`을 그대로 제출해 `verified_at`을 세울 수 있으면 그 문장은 거짓이 된다. 이 문서는 **측정 정본(measurement) seam**을 정의한다. docs-only. **v1.1 = Codex 확정 계약(#209 코멘트) 반영**; 이 계약이 반영되기 전에는 PR A(측정 seam)·PR B(W3 route)를 시작하지 않는다.

## 0. 결론

1. **신원 정본은 kernel의 outbound channel이다**(§1). node가 business API로 들어오는 inbound client-cert(`identity/node_auth.py::NodePrincipal.lock_current`)는 measurement 정본으로 쓰지 않는다. kernel `StorageSampleStore._scope`(`inv/storage_commit.py:46`)가 `inv.nodes`·`inv.node_channels`를 잠가 만든 `ChannelProof(tenant_id, node_id, recovery_epoch, version, endpoint, certificate_sha256)`(`inv/node_channels.py:84`)와, 그 endpoint에 mTLS로 접속해 실제 TLS **server leaf**를 pin하고(`node_transport.py:95 storage_sample`, `include_peer_certificate=True`) 같은 leaf의 Ed25519 키로 서명된 payload를 검증하는 `storage_sampling.py:251 verify_sample`이 정본이다.
2. **새 protocol `node-model-measure-v1`**(§2): 기존 `node-storage-sample-v1`의 cryptographic pattern(domain-separated 서명·leaf pin·nonce·만료)만 재사용하고 domain/version·byte/time 한계는 별도.
3. **v1 측정 단위는 단일 immutable `DataLocation` 하나**(§3). `provider_id/locator` 결속은 삭제(근거 join 없음). 다중 shard/directory·단일 location으로 resolve되지 않는 URI는 `GRAPH-0002/409` + measurement 0 + **NOT_OBSERVED**.
4. **measurement는 verified 상태에 DB로 결속된다**(§4, migration **0054 확정**): kernel-owned append-only `inv.model_version_measurements` + `public.model_versions.verified_measurement_id`(nullable, composite FK) + `verified_at IS NULL iff verified_measurement_id IS NULL` CHECK. `verify_model_version`은 `measurement_id`를 **필수**로 받는다(서비스 시그니처 변경; digest 문자열만으로 verified를 세우는 경로 0개).
5. **generic `EvidenceEnvelope`/`inv.evidence`를 연결하지 않는다**(§5): run이 필수라 run-less subject를 담을 수 없고, 가짜 run·`produced_by_run_id` 대입은 금지. v1 정본 = measurement + request/consumption + bounded audit event.
6. **W3 route는 3 span**(§6): 짧은 canApprove tx → tx 없이 kernel 관측(`ModelMeasurementObservation`, caller bearer·no redirect·bounded·strict) → write tx(IDEM lock → canApprove → replay → Model parent + ModelVersion `FOR UPDATE/populate_existing` → 관측 identity 재결속 → contribution/location/replica exact version·상태 재확인 → freshness → `verify_model_version(measurement_id, content_sha256=observation.sha256)` → audit + ledger).

## 1. 신원 경계 — kernel outbound channel이 정본

| 항목 | 정본 | 인용 |
|---|---|---|
| node 신원 | `ChannelProof(tenant_id, node_id, recovery_epoch, version, endpoint, certificate_sha256)`; `assert_channel(conn, expected)`가 `inv.nodes.recovery_epoch`·`inv.node_channels`(version·endpoint·certificate_sha256·enabled)를 현재 값과 대조 | `inv/node_channels.py:84`, `:104`, `:169-186` |
| 잠금 | issue/accept tx가 `inv.nodes` `FOR UPDATE`·`storage_contributions` `FOR UPDATE`·location snapshot을 잡고, accept에서 `_current`가 run/root/channel/challenge digest/items를 issue 시점과 exact 비교 | `inv/storage_commit.py:46 _scope`, `:57`, `:63`, `:173 _current` |
| transport | `NodeTLSClient.storage_sample(channel, challenge)`: channel 불일치 `NODE-0032/403`, endpoint에 mTLS, 응답과 함께 **peer(server leaf) 인증서** 반환 | `inv/node_transport.py:95-118` |
| 서명 검증 | `verify_sample`: `payload`+`signature`만, `certificate_key`가 leaf DER 지문 == channel 지문·유효기간(`now`·`observedAt` 양쪽) 확인 뒤 `DOMAIN + payload` Ed25519 검증, `observedAt ∈ [issued_at, now]` | `inv/storage_sampling.py:162 certificate_key`, `:251 verify_sample`, `:284` |

**measurement가 남기는 binding 6 + nodeId**: `recoveryEpoch`, `channelVersion`, `certificateSha256`, `contributionVersion`, `locationVersion`, (challenge에 박힌) `relativePath`·`nodeId`. accept tx는 request row·contribution/location snapshot·`inv.nodes`·`inv.node_channels`를 **다시 잠가** issue 당시 값과 exact 일치시킨 뒤에만 서명/leaf/만료를 검증한다. 하나라도 다르면 accept 0행.

**caller가 node를 고르는 필드는 금지**: issue body는 `{}`(IDEM 키만 헤더). node는 `model_versions.uri` → `DataLocation` → `storage_contributions.node_id`로 서버가 정한다.

## 2. protocol `node-model-measure-v1`

- domain `saintvision/node-model-measure/v1\0`(storage-sample의 `DOMAIN`과 분리; 한 키로 서명해도 두 protocol의 payload가 서로 대체될 수 없다).
- challenge: `{protocol, channel(ChannelProof), tenantId, projectId, modelVersionId, uri, contributionId, contributionVersion, locationId, locationVersion, relativePath, expectedByteSize, nonce, issuedAt, expiresAt}`; `validate(now)`는 storage-sample의 `Challenge.validate`(`storage_sampling.py:87-107`) 규칙(정수·범위·만료 ≤ issued+창)을 따르되 창은 model-measure 전용.
- **한계(model-measure 전용, 계약에 명시)**: storage-sample의 `MAX_FILE_BYTES = 1 MiB`·`MAX_FILES = 32`·challenge ≤ 30 s·transport 6 s(`storage_sampling.py:35-37`, `:107`, `node_transport.py:114`)는 **재사용하지 않는다**. v1 제안값: `MODEL_MEASURE_MAX_BYTES = 8 GiB`(Settings; 초과는 issue 전에 `expectedByteSize`로 거부), challenge 창 `MODEL_MEASURE_CHALLENGE_SECONDS = 900`, transport deadline `MODEL_MEASURE_TRANSPORT_SECONDS = 600`; node 측 `hash_file`(`services/verification.py:74`)의 **두 번의 bounded read**가 deadline 안에 끝나 일치해야 하고, 아니면 pass가 아니라 실패/NOT_OBSERVED(`unverifiable` 응답은 measurement 행을 만들지 않는다).
- payload: `{protocol, challengeSha256, locationId, sha256, byteSize, observedAt, durationSeconds}`; 서명은 leaf 키; accept가 `challengeSha256`을 request row와 대조.

## 3. v1 측정 단위 — 단일 immutable DataLocation

issue 조건(모두 서버 판정; 하나라도 아니면 `GRAPH-0002/409`, measurement 0, 문서상 NOT_OBSERVED):
1. `model_versions.uri`가 `services/resolver.py:37 resolve_location`으로 tenant/project 안의 `kind='model'`인 **정확히 한** `DataLocation`으로 resolve된다(디렉터리·다중 location·미해결 → 409).
2. 그 location의 contribution이 `active`, location이 `ready`(`checksum_sha256`·`verified_at` 있음), 그 node에 ready replica가 있다.
3. 기록 정체성 = `(tenantId, projectId, modelVersionId, uri, contributionId, contributionVersion, locationId, locationVersion, relativePath, nodeId, recoveryEpoch, channelVersion, certificateSha256)`.

`data_locations` ↔ `inv.storage_objects` 사이에 정의된 FK/join이 없으므로 v1.0의 "provider_id/locator 복사"는 **삭제**. 다중 shard/directory의 aggregate digest는 이 PR에서 추측하지 않는다; 후속은 정렬된 `(shardIndex, byteLength, sha256)`의 **별도 versioned digest 계약**으로만 추가한다. `ModelExecutionManifestObservation`이 여러 shard/location을 뜻하면 v1은 fail closed.

## 4. measurement ↔ verified 상태의 DB 결속 (migration 0054, 확정)

- **`inv.model_version_measurements`**(kernel-owned, append-only, 성공한 signed observation만): `measurement_id`, `tenant_id`, `request_id`, `project_id`, `model_version_id`, `uri`, `contribution_id`, `contribution_version`, `location_id`, `location_version`, `relative_path`, `node_id`, `recovery_epoch`, `channel_version`, `certificate_sha256`, `sha256`, `byte_size`, `observed_at`, `recorded_at`, `challenge_sha256`, `response_sha256`, `duration_seconds`. `UNIQUE (tenant_id, measurement_id)`, `UNIQUE (tenant_id, request_id)`. RLS tenant. application role은 INSERT/UPDATE/DELETE **불가**(SELECT만); accept kernel path만 INSERT(0047 `record_auth_denial`처럼 SECURITY DEFINER 또는 kernel role).
- **`public.model_versions.verified_measurement_id`** nullable + composite FK `(tenant_id, verified_measurement_id) → inv.model_version_measurements (tenant_id, measurement_id)` + CHECK `(verified_at IS NULL) = (verified_measurement_id IS NULL)`. 허용된 전이는 두 열을 **같은 statement/transaction**에서 함께 설정한다.
- **`verify_model_version`**: `measurement_id`를 **필수**로 받고(또는 동등한 typed receipt), 그 행을 tenant·model_version_id로 결속해 `sha256`/`byte_size`를 대조한 뒤 `verified_at`·`verified_measurement_id`를 함께 세운다. `content_sha256` 문자열만 받는 호출 경로는 **0개**(전수 grep 시험 + DB 부정 시험: `verified_at`만 단독 UPDATE → CHECK 위반, FK 없는 id → FK 위반). 시그니처 0 유지보다 bypass 불가능성이 우선.
- 0054는 alembic 파일 하나가 kernel SQL(`inv/migrations/00xx_model_version_measurements.sql`)을 감싸는 #159(0048) 방식 + `public.model_versions` 열·FK·CHECK. 0052 방식의 catalogue 검사·fail-closed·resume 규칙 적용.

## 5. generic EvidenceEnvelope는 연결하지 않는다

`EvidenceEnvelope`(`db/models/evidence.py:34`, `run_id NOT NULL`)와 kernel `inv.evidence`는 real `run_id`가 필수다. model measurement는 run에 속하지 않으므로 v1.0의 `evidence_id → inv.evidence(action=model_version.measure)`는 현재 계약으로 만들 수 없고, 가짜 run이나 `produced_by_run_id` 대입은 금지한다. v1 정본 = measurement 행 + request/consumption 행 + bounded audit event(`record_event`, `model_version.measure`/`model_version.verify`, detail은 id만). run-less subject를 정식 지원하는 별도 envelope 계약이 생길 때만 연결한다.

## 6. W3 route — 3 span과 재결속

`POST /projects/{p}/models/{model_id}/versions/{version}/verify`, grade canApprove, body `{measurementId}`만(strict; digest·size·uri 필드 존재 시 422).

1. **짧은 tx**: live canApprove.
2. **tx 없이** kernel 관측 `GET {kernel}/…/measurements/{measurementId}` — caller bearer, no redirect, bounded read, strict `ModelMeasurementObservation`(`validate_contract`; unknown key 거부). 응답: `measurementId, tenantId/projectId/modelId/modelVersionId, uri, contributionId/contributionVersion, locationId/locationVersion/relativePath, nodeId/recoveryEpoch/channelVersion/certificateSha256, sha256, byteSize, observedAt, recordedAt`. kernel unreachable/invalid contract/redirect/oversize → `SYS-0001/503/retryable=true`(#167 `_observation` 패턴).
3. **write tx**(`api/lock_wait.bounded_lock_wait`, 카드 84): IDEM-6 lock → live canApprove → replay → Model parent + ModelVersion `FOR UPDATE/populate_existing`(`_locked_version`) → **관측 identity 재결속**(tenant/project/model/modelVersion/uri = path·row) → business-visible contribution/location/replica의 **exact version·active/ready 상태 재확인** → freshness(`now - observedAt ≤ Settings.model_measurement_max_age_seconds`, 기본 86400; `observedAt ≤ recordedAt ≤ now`, 미래 시각 거부) → `verify_model_version(session, tenant_id, model_version_id, measurement_id, content_sha256=observation.sha256, now)` → audit + ledger.

오류 표: missing/other tenant/other version = 동일 404; snapshot drift·digest/size/uri mismatch·stale = 값 비노출 `GRAPH-0002/409`; kernel 문제 = `SYS-0001/503`; 권한 회수 = 403 + denial 1행(#195); lock wait = `SYS-0001/503`.

**인증서 rotation/retire와 과거 measurement**: accept 당시 channel/leaf가 검증됐다는 사실은 과거 evidence다. 이후 정상 rotation/retire가 과거 측정을 자동 무효화하지 않는다(그러려면 verified version을 되돌리는 별도 revocation lifecycle이 필요). 대신 freshness 창 안에서 위 snapshot을 재확인한다. 보안 사고로 evidence를 폐기하는 explicit revocation은 후속 계약.

## 7. 시험 계획(되살림, Codex 보강 포함)

PR A(측정 seam, kernel):
1. inbound `NodePrincipal`로 바꾸면 실패(정본은 outbound channel); `channelVersion`/`recoveryEpoch`/`certificateSha256` 중 하나만 바뀌어도 accept 0행.
2. `contributionVersion`/`locationVersion`/ready replica/`relativePath` 중 하나가 바뀌면 accept 409(또는 W3 409)이고 verified 상태 불변.
3. 위조 envelope(다른 키 서명·지문 불일치·만료·`observedAt` 범위 밖) → 기록 0·409·audit `failed`; 다른 domain(storage-sample 서명)으로 만든 payload는 거부.
4. provider/locator를 임의 연결할 수 없음; multi-location/shard·미해결 URI는 fail closed(409, measurement 0).
5. 한계: `expectedByteSize > MODEL_MEASURE_MAX_BYTES` issue 거부; deadline 안에 두 번 read가 안 끝나면 실패.
6. replay: 같은 request 같은 응답 → 같은 measurement; 다른 응답 → 409. 실 PG: RLS·append-only(UPDATE/DELETE grant 없음)·UNIQUE.
7. 가짜 runId 없이 measurement 정본이 성립하고 generic `EvidenceEnvelope`/`inv.evidence` 행이 생기지 않음.

0054 + 서비스:
8. `verified_at`만 단독 UPDATE → CHECK 위반; measurement FK 없는 id → FK 위반; `verify_model_version`에 digest만 넘기는 호출 경로 0개(전수 grep + 시그니처 시험).

PR B(W3 route):
9. PG-free: body에 digest → 422; 3 span 순서; 관측 identity mismatch → 404; unknown key/redirect/oversize → 503; drift/mismatch/stale/미래 시각 → 409 값 비노출; 서비스에 넘긴 digest = 관측값; Settings 범위(양의 유한 초, startup fail-closed).
10. 실 PG: W3↔release·W3↔W4가 같은 ModelVersion lock(독립 세션 + `pg_stat_activity` barrier, W4 방식); commit 뒤 `(verified_at, verified_measurement_id)`가 둘 다 있거나 둘 다 NULL; 회수 재검사 403 + denial 1행.

## 8. 열린 질문(계약 밖, 후속)

- 다중 shard aggregate digest 계약(정렬된 `(shardIndex, byteLength, sha256)`의 versioned digest) — 별도 카드.
- explicit revocation lifecycle(보안 사고 시 과거 measurement 폐기와 verified 되돌림) — 별도 카드.

## 9. v1.0 → v1.1 변경 요지

| v1.0 | v1.1(Codex 확정) |
|---|---|
| `NodePrincipal.lock_current`(inbound)를 신원 정본으로 | kernel outbound `ChannelProof` + leaf pin + 서명이 정본; inbound는 금지 |
| storage-sample 기계를 그대로 | 별도 domain/version `node-model-measure-v1`, 전용 byte/time 한계 |
| provider_id/locator 복사 | 삭제(join 근거 없음); 단일 immutable DataLocation만 v1 |
| `evidence_id → inv.evidence` 연결 | 연결하지 않음(run 필수); measurement + request/consumption + audit가 정본 |
| `verified_at`만 세우고 measurement는 audit에 | `verified_measurement_id` FK + CHECK; `verify_model_version(measurement_id 필수)` |
| node retire/rotation 시 409 | 과거 measurement 자동 무효화 없음; freshness 창 안 snapshot 재확인 |
| 소유 kernel vs business 미정 | **kernel-owned measurement + public ModelVersion FK, 0054 확정** |

## 10. 검증 방법(실제 수행한 것만)

- `git grep -n -F`(base `1e8baf04`): `lineage.py:279`, `node_channels.py:84/:104/:169-186`, `storage_commit.py:46/:57/:63/:173/:186/:274`, `node_transport.py:95-118`, `storage_sampling.py:33-37/:87-107/:162/:251/:284`, `verification.py:56/:74`, `evidence.py:34`·`services/evidence.py:73`, `resolver.py:37`, `pathsafe.py:235`, `lineage.py:205`.
- Codex #209 코멘트(2026-09-28T09:59:20Z) 정독·반영. `_locked_version`·`bounded_lock_wait`는 #167/#196/#211 인용.
- 코드·workflow·migration 변경 없음. 실행한 시험 없음(docs-only).
