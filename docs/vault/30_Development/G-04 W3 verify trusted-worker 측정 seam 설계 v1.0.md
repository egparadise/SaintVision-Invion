---
doc_id: "CLAUDE-G04-W3-VERIFY-SEAM-DESIGN-001"
title: "G-04 W3 verify trusted-worker 측정 seam 설계 v1.0 — 누가 bytes를 읽는가(node mTLS 신원·challenge-bound signed sample 재사용), 무엇을 기록하는가(measurement 정본), verify route는 measurement만 받는다(사용자 digest 불신), §5-3 잠금 순서, 실패 코드·존재 비노출, migration 0054 필요 판정, 시험 계획 (카드 83, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T18:37:52+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-ST"]
tags: ["G-04", "W3", "verify", "trusted-worker", "evidence", "node-auth", "design", "claude"]
---

# G-04 W3 verify trusted-worker 측정 seam 설계 v1.0 (2026-09-28, 카드 83)

> [!note] 범위
> G-04·G-05 설계 v1.2.1(#183)에서 **보류**된 W3 `POST /projects/{p}/models/{model_id}/versions/{version}/verify`. 보류 이유(Codex): `services/lineage.py:279` `verify_model_version`의 정본은 "trusted worker가 실제 weights를 해시했다"인데, 승인 사용자가 DB의 `content_sha256`을 그대로 제출해 `verified_at`을 세울 수 있으면 그 문장은 거짓이 된다. 이 문서는 **측정 Evidence seam**을 제안한다: 누가 읽고, 무엇을 남기고, verify route가 그 기록만 받도록 결속한다. docs-only. 검토자 Codex가 계약을 확정한다. 코드·workflow 변경 없음.

## 0. 결론 먼저

1. **bytes를 읽는 것은 사용자가 아니라 node다.** 읽는 주체는 그 model version의 데이터가 놓인 contribution을 가진 **enrolled node**(`nodes.certificate_fingerprint`, mTLS)이고, 읽기는 kernel이 이미 가진 **challenge-bound signed sample**(`services/control-plane/src/inv/storage_commit.py:186 accept`, `node_transport.py:95 storage_sample`, `storage_sampling.py:251 verify_sample`)과 같은 모양으로 한다: control plane이 nonce·대상·만료를 담은 challenge를 발급 → node가 자기 ReadRoot 아래서만 읽어(`services/verification.py:74 hash_file` → `:56 ByteObservation`) 서명한 envelope + pinned TLS leaf 인증서를 돌려줌 → control plane이 서명·인증서 지문·challenge 신선도를 검증한 뒤에만 기록.
2. **기록은 measurement 한 행이 정본이다**(§2). 사용자 입력이 아닌 검증된 envelope에서만 만들어지고, model version·object locator·sha256·byte_size·읽은 시각·node id·인증서 지문·challenge/응답 digest·evidence id를 가진다.
3. **verify route는 `measurementId`만 받는다**(§3). request에 digest 필드는 존재하지 않는다(strict schema). 잠근 ModelVersion 행과 measurement 행을 결속해 `sha256`·`byte_size`·object·신선도·node 상태를 서버가 판정하고, `verify_model_version(content_sha256=measurement.sha256)`(시그니처 변경 0)에 **measurement의 digest**를 넘긴다.
4. **migration은 필요하다** — measurement 정본 테이블(§6). 번호는 코디네이터 지시대로 **0054**를 요청한다(이 문서에서 확정하지 않음; Codex 계약 확정 뒤).
5. **지금 W3 route를 구현하지 않는다.** 이 seam(측정 수집·기록)이 먼저 있어야 W3가 "trusted worker" 문장을 참으로 만든다. §7의 순서로 두 PR(측정 seam → W3 route).

## 1. 누가 bytes를 읽는가 — 신원과 결속(기존 체계 재사용)

| 요소 | 재사용하는 정본 | 이 설계에서의 역할 |
|---|---|---|
| node 신원 | `src/saintvision/identity/node_auth.py:75 NodePrincipal`(`certificate_sha256`, mTLS 또는 allowlist된 trusted proxy만), `:99 lock_current`(변경 tx 안에서 `nodes` 행 `FOR UPDATE` + 지문 재확인, retired 거부) | 측정 응답을 기록하는 tx에서 node 행을 잠그고 지문이 현재 credential과 같을 때만 기록 |
| bytes 위치 | `model_versions.uri`(`inv://models/<name>@<version>[/<path>]`, `storage/pathsafe.py:235 build_uri`) → `services/resolver.py:37 resolve_location` → `data_locations`(`contribution_id`) → `storage_contributions.node_id`(`normalized_path`, `status='active'`) | **어느 node가 읽을지는 서버가 정한다**(caller가 node를 고르지 않음). object provider/locator(#159 `inv.storage_objects.provider_id/locator`, 불변 trigger)는 measurement에 그대로 복사해 "무엇을 읽었는가"를 고정 |
| 읽기 경계 | node 측 `storage/readroot.py`(설정된 root만, link·cross-device·변경 중 파일 거부) + `hash_file`(두 번 bounded read 일치, byte budget) | node는 challenge가 가리키는 항목만, 자기 root 아래서만 읽는다 |
| challenge/응답 | `inv/storage_sampling.py:75 Challenge`(channel = node 인증서 지문·project·run·contribution·root_version·items·now, `validate(now)` 만료), `:251 verify_sample`(payload+signature, `certificate_key`가 pinned leaf 지문 = channel 지문 검증, `observedAt` 시점에도 인증서 유효) | 새 challenge 종류 `model-measure`(§2-1)를 같은 기계로 발급·검증. **위조 envelope는 서명 검증에서 죽고 기록에 도달하지 않는다** |
| 기록 저장 | kernel `accept`는 `inv.evidence`(EvidenceEnvelope JSON, `action: verify-storage-sample`, `inputSha256=challenge digest`, `outputSha256=payload digest`) + `public.storage_checks` + `inv.storage_sample_consumptions(request_id, response_sha256, evidence_id)`(replay는 같은 response digest만) | 같은 3중 기록 패턴을 measurement에 적용(§2-2) |

**사용자(승인 등급)는 무엇을 하는가.** 측정을 **요청**할 수 있을 뿐(§2-1의 issue), 값을 제출하지 못한다. 이것이 `mark_verified`(`services/storage.py:183`, "Record a checksum computed by a trusted worker")가 route 없이 서비스로만 있는 이유와 같은 원칙이다.

## 2. 무엇을 기록하는가 — measurement 정본

### 2-1. 측정 요청(issue)과 수집(accept)

- **issue** `POST /v1/projects/{p}/models/{model_id}/versions/{version}/measurements` (grade canApprove, IDEM 키 필수, body `{}`만): 서버가 path→row 결속(Model parent → ModelVersion, #183 §2 규칙) 뒤 `uri`를 resolve해 대상 `data_locations`·contribution·node를 정하고 kernel에 `model-measure` challenge 발급을 위임한다. challenge에는 `modelVersionId`, 대상 location id/relative_path/`byte_size`, contribution `root_version`, channel(node 인증서 지문), `now`/만료(기존 `Challenge.validate` 규칙)가 들어간다. 응답은 `{measurementRequestId}`; **digest는 응답에 없다**.
- **accept**: kernel이 node로부터 signed envelope(`NodeStorageSignedSample` 계약과 같은 `payload`+`signature`, pinned leaf 인증서 동봉)를 받아 `verify_sample`과 같은 검증(서명·지문·만료·`observedAt`)을 통과한 경우에만 measurement 행을 만든다. 통과하지 못하면 **아무것도 기록하지 않고** 요청은 실패로 끝난다(§4). 같은 request의 재응답은 `response_sha256`이 같을 때만 replay(기존 `IDEM-0001` 규칙), 다르면 409.
- 동기/비동기: kernel `collect`(`storage_commit.py:307`)처럼 issue→node 호출→accept를 한 요청에서 끝내는 형태를 기본으로 하되, node 호출 시간(`timeout=6`)이 business route의 tx 밖에서 일어나야 한다(#167 release가 관측 fetch를 tx 밖 별 span에서 하는 것과 같은 이유). 즉 business route는 (1) 권한 preflight tx → (2) kernel 호출(tx 없음) → (3) 기록 tx.

### 2-2. measurement 행(정본, append-only)

| 열 | 값 | 근거 |
|---|---|---|
| `measurement_id` | InvId | PK |
| `tenant_id` | node·model version의 tenant(둘이 같아야 기록) | RLS |
| `model_version_id` | 잠근 ModelVersion | 결속 대상 |
| `uri` | `model_versions.uri` 그대로 | "무엇을" |
| `provider_id`, `locator` | #159 `inv.storage_objects`의 값(있을 때), 없으면 `data_locations.location_id`·`relative_path` | 객체 정체 |
| `sha256`, `byte_size` | envelope의 `ByteObservation` | 측정값 |
| `observed_at` | envelope `observedAt`(node 시각, 서명 대상) | 신선도 판정 |
| `recorded_at` | control plane clock(잠금 뒤 1회 읽기) | 기록 시각 |
| `node_id`, `certificate_sha256` | `NodePrincipal`(lock_current 통과) | "누가" |
| `request_id`, `challenge_sha256`, `response_sha256` | issue/accept의 nonce·digest | 재생·위조 방지 |
| `evidence_id` | `inv.evidence`에 남긴 EvidenceEnvelope id(`action: model_version.measure`, `inputSha256=challenge digest`, `outputSha256=payload digest`, `result`) | 감사 연결 |
| `duration_seconds` | `ByteObservation.duration_seconds` | 운영 관측(느린 스토리지) |

- **saintvision `EvidenceEnvelope`(`db/models/evidence.py:34`)를 measurement 정본으로 쓰지 않는 이유**: `run_id NOT NULL`(측정은 run이 아니라 version에 속함), `output_ref`는 `inv://`만 허용(`services/evidence.py:73`)이라 provider/locator를 담을 수 없고, 텔레메트리 JSON에서 digest를 꺼내 판정하면 "정본이 JSON 안의 문자열"이 된다. kernel `inv.evidence`도 같은 이유로 **연결(evidence_id)**만 한다.
- 불변: UPDATE/DELETE grant 없음(app role INSERT·SELECT만), #159 `guard_storage_object`처럼 trigger로 신원 열 변경 거부. `UNIQUE (tenant_id, request_id)`.

## 3. verify route(W3)가 measurement만 받는 결속

`POST /projects/{p}/models/{model_id}/versions/{version}/verify`, grade **canApprove**(#183 §2; 사용자가 값을 주지 않으므로 등급은 "이 version을 verified로 승격할 권한"만 뜻함).

- **request**: `ModelVersionVerifyRequest{measurementId: InvId}` strict. `contentSha256`·`byteSize`·`uri` 등 값 필드는 **존재하지 않으며** 있으면 422(extra forbid). 되돌림 시험: body에 digest를 넣으면 422.
- **순서(#183 §5-3 W4 계약과 동일 골격, READ COMMITTED)**: preflight canApprove(별 tx) → body → `SET LOCAL lock_timeout` → IDEM-6 직렬화점 → live canApprove → app clock 1회 → 원장(replay/409) → **Model parent path 결속 → ModelVersion 단일 행 `FOR UPDATE + populate_existing`(#167 `model_release.py::_locked_version`, W4 #196과 같은 helper)** → live canApprove 재확인 → **measurement 행 `FOR SHARE`**(tenant·`measurement_id`) → 서버 판정(아래) → `verify_model_version(session, tenant_id, model_version_id=row.model_version_id, content_sha256=measurement.sha256, now)` → audit(`model_version.verify`, detail에 measurementId·nodeId·observedAt; digest 값은 열에만) + ledger 같은 tx.
- **서버 판정(모두 통과해야 함)**:
  1. measurement.tenant_id == principal.tenant_id, measurement.model_version_id == row.model_version_id (아니면 404 "No such measurement." — 다른 version의 measurement도 같은 404: 존재 비노출).
  2. measurement.uri == row.uri (등록 뒤 uri가 바뀌었으면 409).
  3. measurement.sha256 == row.content_sha256 이고 (row.byte_size > 0이면) measurement.byte_size == row.byte_size — 아니면 `GRAPH-0002/409` "The measurement does not match the registered digest."(값 비노출). 서비스의 `VAL_SCHEMA` 검사는 2차 방어.
  4. `now - measurement.observed_at <= Settings.model_measurement_max_age`(기본 24h; 설정) — 아니면 409 "stale".
  5. measurement.node_id의 `nodes.status != 'retired'`이고 `certificate_fingerprint == measurement.certificate_sha256`(측정 뒤 인증서 교체·retire된 node의 측정은 승격 불가) — 아니면 409.
  6. 이미 `verified_at`이 있으면: 같은 measurement 또는 같은 sha256이면 **자연 멱등 200**(변경 0), 다른 sha256이면 409(정본 `content_sha256`은 불변이므로 실제로는 3에서 먼저 걸린다).
- **응답**: `ModelVersionResponse`류 strict(`verifiedAt`, `measurementId`, `stage`); digest는 이미 등록값이므로 노출 범위 변화 없음.
- **오류 표**: 키 없음/다른 body 422·409(IDEM), measurement 404, 불일치·stale·node 상태 409 `GRAPH-0002`, lock timeout/deadlock `SYS-0001/503/retryable=true`, 권한 403(공유 denial audit #195), 무토큰 401.

## 4. 실패 코드와 존재 비노출

| 상황 | 어디서 | 응답 |
|---|---|---|
| envelope 서명 불일치·인증서 지문 ≠ channel·challenge 만료·`observedAt` 시 인증서 무효 | accept(기록 전) | 기록 0, `AUTH-0030/403` 아닌 **`GRAPH-0002/409` "The measurement could not be verified."**(어느 검사가 실패했는지는 kernel 로그·evidence `result: failed`에만; 응답에 비노출) |
| node가 항목을 읽지 못함(root 밖·변경 중·크기 초과) | node → envelope `unverifiable` | measurement `sha256 NULL` 행은 **만들지 않음**(정본은 성공 측정만) — evidence에는 실패로 남김 |
| measurement가 다른 tenant/version/없음 | verify | `RES-0004/404` 동일 문구 |
| digest·size·uri 불일치 | verify | `GRAPH-0002/409`, 값 비노출 |
| stale·node retired·지문 변경 | verify | `GRAPH-0002/409` |
| 같은 request 재응답이 다른 digest | accept | 409(kernel `IDEM-0001` 규칙) |

## 5. 동시성

- verify는 W4·release와 **같은 `_locked_version` 한 행**을 잠근다(#183 §5-3 "parent read 후 ModelVersion 한 행"). release↔verify: release가 먼저면 verify는 기다린 뒤 released row에 `verified_at`을 세울 수 있는가 — release는 `verified_at IS NOT NULL`을 전제(`release_requires_verification_and_pin` CHECK)하므로 released row는 이미 verified다; verify는 자연 멱등(3-6). verify가 먼저면 release는 기다린 뒤 verified를 본다. pin↔verify는 값이 겹치지 않는다(W4 실측은 #196에서 NOT_OBSERVED로 남긴 항목을 이 PR의 실 PG 시험이 채운다).
- measurement 행은 append-only라 잠금 경합이 없고 `FOR SHARE`는 verify 중 삭제 방지(삭제 grant가 없으므로 사실상 문서용).
- issue 동시 2건(같은 version): kernel `storage_sample_requests`처럼 `request_id`(IDEM 키에서 파생) UNIQUE + 같은 nonce 재발급 금지 규칙 재사용.

## 6. migration 필요 여부 — 필요, 번호 0054 요청

- 새 테이블 `model_version_measurements`(§2-2) + RLS(tenant) + app role INSERT/SELECT + 불변 trigger + `UNIQUE(tenant_id, request_id)` + index `(tenant_id, model_version_id, observed_at DESC)`. `model_versions`에는 열을 추가하지 않는다(`verified_at`만 세움; 어떤 measurement로 세웠는지는 audit + measurement의 `model_version_id`로 역추적 가능. 열 추가 여부는 Codex 판단에 맡김: 추가 시 `verified_measurement_id` nullable FK, 같은 0054).
- 위치: kernel이 accept를 수행하면 kernel 스키마(`inv.*`, `services/control-plane/src/inv/migrations/00xx.sql`을 alembic 0054가 감싸는 #159 방식) / business가 기록하면 `public.model_version_measurements`(alembic 0054 직접). **권고: kernel 소유**(node transport·challenge 검증이 kernel에 있고 business app은 node channel을 열지 않는 현 경계 유지; #167 release가 kernel 관측을 HTTP로 읽는 패턴과 같음). 그러면 business W3 route는 `GET {kernel}/…/measurements/{id}` 관측(caller bearer, no-redirect, bounded read = `model_release.py::fetch_commitment` 패턴)으로 measurement를 읽고 §3 판정을 한다 — 단, 이 경우 §3의 `FOR SHARE`는 없고 관측의 `measurementId`·`sha256`·`observedAt`·`nodeId`·`certificateSha256`을 kernel 응답 계약(`ModelMeasurementObservation`, strict, `validate_contract`)으로 받는다. 어느 쪽이든 **번호는 0054 하나**.

## 7. 시험 계획(되살림)

PR A(측정 seam, kernel 또는 business):
1. **위조 evidence**: 서명이 다른 키로 된 envelope / 인증서 지문 ≠ channel / 만료된 challenge / `observedAt`에 인증서 무효 → 기록 0·409·evidence `failed`.
2. **다른 object**: challenge의 항목과 다른 location을 읽은 응답(payload의 item id 불일치) → 거부.
3. **replay**: 같은 request 같은 응답 → 같은 measurement id; 다른 응답 → 409.
4. **node 신원 없음**: mTLS/proxy 지문 없는 요청 → `AUTH-MISSING-CREDENTIAL`; retired node → `AUTH-INVALID-CREDENTIAL`(기존 `node_auth` 시험 재사용).
5. 실 PG: measurement 행 RLS(타 tenant 조회 0), 불변 trigger(UPDATE 거부), UNIQUE request.

PR B(W3 route):
6. PG-free: body에 `contentSha256`이 있으면 422(사용자 digest 불신의 되돌림); 순서 로그(§3); measurement 404 3경로 동일 문구; 불일치 sha/size/uri → 409 값 비노출; stale → 409; node retired/지문 변경 → 409; 멱등 200; 55P03/40P01 → 503; 서비스에 넘긴 `content_sha256`이 **measurement의 값**임을 단언(요청에 digest가 없으니 다른 출처가 없음).
7. 실 PG: 정상 측정 → verify 200·`verified_at` 세움·audit 1; **DB digest를 그대로 넣은 위조 measurement 행은 만들 수 없음**(app role INSERT는 accept 경로만; 시험은 owner로 넣은 행이 `certificate_sha256`/node 결속에서 거부됨을 확인); release↔verify·verify↔pin 경합(독립 세션·`pg_stat_activity` barrier, W4 방식); 회수 재검사 403 + denial 1행(#195).

## 8. 열린 질문(Codex 확정 필요)

1. **다중 파일 model의 `content_sha256` 정의**: `register_model_version`은 단일 digest를 받는다. `uri`가 디렉터리(여러 `data_locations`)면 "실제 weights의 해시"가 무엇인지(파일 목록의 정렬된 (path, sha256) 해시? 단일 object만 허용?)가 먼저 정해져야 한다. 이 설계는 **단일 object(location 1개) 우선**, 다중 파일은 정의 확정 전 NOT_OBSERVED.
2. measurement 기록 소유(kernel vs business, §6)와 그에 따른 0054의 스키마 위치.
3. 신선도 창(24h 기본)과 stale 뒤 재측정 요구 여부.

## 9. 검증 방법(실제 수행한 것만)

- `git grep -n -F`(base `1e8baf04`): `lineage.py:279`, `node_auth.py:75/:99`, `storage_commit.py:186 accept`·`:274 consumptions`, `node_transport.py:95`, `storage_sampling.py:75/:142/:162/:251`, `verification.py:56/:74`, `storage.py:183 mark_verified`, `evidence.py:40/:73`, `resolver.py:37`, `pathsafe.py:235`, `projects.py:204`, `lineage.py:205`(uq), 0048 wrapper·`inv/migrations/0026_object_store_locator.sql`(provider_id/locator/불변 trigger).
- `_locked_version`은 base에 없고 #167/#183 §5-3·#196의 것을 인용(병합 목록).
- 코드·workflow·migration 변경 없음. 실행한 시험 없음(docs-only).
