---
doc_id: "CLAUDE-VF-CL-02-MODEL-URI-SHARDS-DESIGN-001"
title: "VF-CL-02 설계안 — inv://models/<name>@<version> URI → ModelManifest.shards/replicas 확장 (계약 무변경, 비즈니스 resolver + 주입식 manifest reader, 정직 실패 모드)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T19:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3e267b05"
impl_sha: "(구현 커밋 — Claude 작업 현황 항목 참조)"
tags: ["vf-cl-02", "resolver", "model", "shards", "design", "claude"]
---

# VF-CL-02 설계안 — model-kind URI → shards 확장 (2026-09-22, 카드 8)

## 1. 현재 진입점·반환 타입 (실측)

`src/saintvision/services/resolver.py`(비즈니스 API, SQLAlchemy `public` 스키마, RLS tenant scope):
- `resolve_location(session, tenant_id, uri, reader_user_id=None) -> DataLocation` — `parse_uri` 선검증 → `(tenant_id, uri)` 유니크 행. public reader는 자기 active contribution만.
- `resolve(...) -> (ParsedUri, DataLocation)` · `ready_replica_nodes(...) -> list[node_id]`(state='ready'만) · `is_materialisable(...) -> bool`.
- docstring: "model-manifest binding(kind='model' URI → shard URIs)은 VF-CX-02 계약 대기" — **계약은 착지됨**: `$defs.ModelManifest{shards[ModelShard{index,offset,byteLength,sha256}], replicas[ModelReplica{shardIndex, locationId dtl_…, locationVersion, nodeId, state ∈ unverified|verified|unavailable}]}`.
- 저장 위치(실측): 매니페스트는 **커널** `inv.model_manifests(tenant,project,model_id,version,manifest jsonb,…)` + `inv.model_shard_locations(model_id,version,shard_index,location_id,location_version)`(Codex 소유). 비즈니스 role `inv_app`은 두 테이블 **SELECT 권한 없음**(has_table_privilege false). 비즈니스 측 join key는 `public.model_versions(model_id, version, uri)`(VF-CL-03 옵션 A, `1fe3a6ae` 시험이 고정) — URI `inv://models/<name>@<version>/…`의 name은 `public.models.name`(tenant 내 유니크), version은 `model_versions.version`.
- `ModelReplica.locationId`(`dtl_`)는 비즈니스 `public.data_locations.location_id`를 가리킨다(`kind='model'` 허용, CHECK 실측). 따라서 shard→location→node 확장의 **읽기 가능한 절반은 비즈니스 DB에 있고, shard 목록·replica 매핑 절반은 커널에 있다.**

## 2. 확장 설계 (계약 무변경)

새 함수 `resolve_model(session, *, tenant_id, uri, reader_user_id=None, manifest_reader=None) -> ModelResolution` (같은 모듈):

1. `parse_uri` → `kind != 'model'`이면 `ValueError`(조회 전 거부, 기존 규칙).
2. join key: `models.name == parsed.name` (tenant) → `model_versions(model_id, version == parsed.version)`; 없으면 `InvError(RES_ARTIFACT_NOT_FOUND)` — "카탈로그에 있으나 등록 안 된 모델"과 "미지 URI"를 섞지 않는다.
3. 위치: `data_locations.uri == uri`(있으면, reader scope 동일 적용) — 모델 파일 자체의 카탈로그 위치. 없을 수 있다(shard 단위로만 카탈로그된 모델).
4. **shards**: `manifest_reader(tenant_id, model_id, version) -> ModelManifest dict | None`를 **주입**받는다. 비즈니스 role이 커널 테이블을 못 읽으므로 기본값 `None` → `shards=None`, `manifest_source="unavailable"`, reason에 "kernel manifest not readable from business role; reader not injected"를 **명시**(빈 목록으로 위장 금지). reader가 있으면 각 shard index마다 replicas를 모아 `ShardResolution(index, offset, byteLength, sha256, replicas=[ReplicaResolution(location_id, location_version, node_id, manifest_state, location(DataLocation|None), version_matches, replica_ready, materialisable, reason)])`.
   - `materialisable = manifest_state=='verified' and location 존재 and location.version == locationVersion and data_replicas(state='ready', node_id) 존재`.
   - 정직 실패 모드: 매니페스트 replica가 가리키는 location이 tenant에 없음 → `reason="location-missing"`; `location.version != locationVersion` → `"location-version-drift"`(stale); manifest_state `unverified`/`unavailable` → 그대로; `data_replicas`에 ready 없음 → `"replica-not-ready"`; shard에 replica 0 → `"unrecorded"`. **shard 단위 `materialisable`은 replica 중 하나라도 true**, 모델 단위 `fully_materialisable`은 모든 shard가 true — 부분 가능은 부분으로 보고(허위 전체 성공 없음).
5. 인가 술어 재사용: reader scope는 `resolve_location`과 동일(`reader_user_id`가 있으면 active contribution만). 프로젝트 grant는 비즈니스 API 계층(라우트)에서 이미 검사 — 이 서비스 함수는 tenant RLS + reader scope만(기존 함수와 동일 층위). 커널 manifest는 reader가 커널 인가로 읽는다.
6. 계약: JSON Schema·생성 타입 **무변경**. 반환은 파이썬 dataclass(내부 서비스 값)이며 HTTP 응답 계약은 이 카드 범위 밖(필요 시 별도 결정).

## 3. Codex 확인이 필요한 한 가지 (결속 방식)

manifest_reader의 **운영 구현**: (a) `inv_app`에 `inv.model_manifests`·`inv.model_shard_locations` **SELECT grant**(마이그레이션, Codex 소유) 또는 (b) 커널 HTTP(ModelCommitObservation/ModelView, 이미 서빙)를 비즈니스가 호출(현재 saintvision에 커널 HTTP 클라이언트 없음) 또는 (c) 커널 측 확장 라우트(응답 계약 신설 필요 → 계약 변경). 이 카드는 (a)/(b)/(c) 중 무엇이든 **주입 지점만** 만들고 시험은 계약 형태의 fake reader로 확장 논리를 검증한다. 결정 전엔 운영 경로에서 `manifest_source="unavailable"`이 정직한 답이다.

## 4. 시험 계획 (실 PG, `tests/test_model_uri_resolver.py`, 단일 파일)

| 케이스 | 기대 |
|---|---|
| model URI인데 등록된 version 없음 | `RES_ARTIFACT_NOT_FOUND` |
| dataset URI를 `resolve_model`에 | `ValueError`(조회 전) |
| 등록 version 있음 + reader 없음 | `shards is None`, `manifest_source="unavailable"`, reason 명시, location/ready_nodes는 정상 |
| reader가 shard 2개·replica: (0→verified, location 존재·버전 일치·ready 노드) (1→verified이나 location.version 드리프트) | shard0 materialisable, shard1 `location-version-drift`, `fully_materialisable=False` |
| replica state `unavailable` / 데이터 replica가 `stale` | 각각 reason 그대로, materialisable False |
| shard에 replica 없음 | `unrecorded` |
| 타 tenant의 location을 가리키는 replica | `location-missing`(RLS 누출 없음) |
| reader가 계약 밖 dict(필수 키 누락) | `ValueError`(형태 검증) — 허위 확장 금지 |

## 5. 구현 결과 (코디네이터 승인 조건 4개 충족)

- `src/saintvision/services/resolver.py`에 `resolve_model` + `ModelResolution/ShardResolution/ReplicaResolution` dataclass + `ManifestReader` 타입 + `_check_manifest_shape`(계약 형태 검증, 스키마 검증기 아님) 추가. 기존 함수·인가 경로 무변경, `_reader_scoped`가 `resolve_location`과 **같은 reader scope 술어**를 재사용(우회 SQL 없음). 계약 파일·생성 타입 무변경.
- `tests/test_model_uri_resolver.py` **7 passed**(실 PG, disposable DB, RLS tenant scope) + 기존 `tests/test_uri_resolver.py` **25 passed** 불변 = 32 passed. 실패 모드 전부 시험: dataset URI 조회 전 거부 · 미등록 version `RES_ARTIFACT_NOT_FOUND` · reader 없음 → `shards=None`·`manifest_source="unavailable"`·reason 명시(빈 목록 아님) · shard0 ok/shard1 `location-version-drift` · `manifest-unavailable`·`replica-not-ready` · shard replica 0 `unrecorded` + 타 tenant location `location-missing`(RLS 누출 없음) · 계약 밖 reader 결과 `ValueError`.
- 시험이 잡은 fixture 결함 2건(도구 결함 아님): `new_id("data_replica")`는 없는 kind(정본은 `replica`/`rep_`), `data_replicas`의 ready는 `checksum_sha256`+`verified_at` 필수(CHECK) — 스키마가 "검증 없는 ready 복제본"을 거부한다는 것이 실측으로 재확인됨.
- 운영 reader 결속(§3 (a)/(b)/(c))은 Codex 회신 대기 — 회신은 이 문서에 인용해 별도 카드로.
