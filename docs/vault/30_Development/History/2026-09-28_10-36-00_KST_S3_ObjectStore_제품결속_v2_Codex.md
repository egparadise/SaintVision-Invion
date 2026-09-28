---
doc_id: "HIST-CODEX-S3-OBJECT-STORE-PRODUCT-BINDING-002"
title: "S3 호환 ObjectStore 제품 결속 v2"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-28T10:36:00+09:00"
source_of_truth: "Git"
---

# S3 호환 ObjectStore 제품 결속 v2

## 시작 조건과 범위

- Card 45 v2, owner Codex / reviewer Claude.
- branch `agent/codex/s3-object-store-implementation-v2`, stack base PR #149 head `5a794ae9`, 승인 설계 PR #140 v1.2 head `9c02a89b`.
- 구현 chain은 v1 SPI `6a4841aa`, provider/locator migration·replay `daf02843`, immutable PUT 보강 `73adeae6`, 제품 결속 `51ffdc26`이다.
- 로컬 실 PostgreSQL·Docker는 메모리 규칙에 따라 실행하지 않았다. 실제 migration/definer, S3+PostgreSQL, Artifact HTTP 다운로드는 `run-core` hosted lane에서만 실행하도록 배선했다.

## 구현

- `storage_objects.provider_id`·`locator`의 기존 local row backfill은 `local-bounded-v1`과 정확한 `obj-<uuidhex>`를 보존한다. checkpoint 공개 content에는 provider만 남고 locator는 노출하지 않는다. same-provider replay는 quiet, provider/digest drift는 `GRAPH-0004` 전체 실패다.
- `configurationReadiness.objectStore`는 `providerId`, `endpoint`, `bucket`, `region`, `credentialFile`, `prefix`의 exact object다. 미지/누락 inner key는 startup 거부, endpoint/bucket/private credential 미해결은 값 없이 이름만 관측한다. 자격 파일은 regular·single-link·bounded·0600이며 symlink/hardlink를 거부한다. S3가 예약 local provider ID를 주장하거나 root path-style 서명과 불일치하는 endpoint path를 쓰는 것도 거부한다.
- worker와 API가 같은 immutable `api.json` 정본을 읽는다. legacy Local과 S3 동시 설정은 dual-write 대신 거부하고, registry는 persisted provider ID를 exact match하여 fallback하지 않는다.
- 결과 다운로드는 receipt body fallback을 제거했다. 짧은 RLS transaction으로 immutable ticket을 만든 뒤 provider I/O를 수행하고, 같은 row·attempt·provider·locator·digest·size를 재검증한다. S3는 DB lock 밖에서 읽고 Local은 provider flock을 잡은 상태로 짧은 DB 재검증을 수행해 provider→DB lock order를 유지한다. provider/object 부재는 `STORE-0001`/503/retryable이고 과거 receipt 200으로 낮추지 않는다.
- HTTP route·공개 request schema의 `objectId`/`locator` 입력 0건 스캔은 positional·keyword-only·`Query(alias=...)`까지 포함한다. configuration readiness enum·fixture·Python/TS/Go/wire 생성물은 `generate_contracts.py`로 동기화했다.
- hosted Core는 digest-pinned MinIO를 명시적으로 생성·정리한다. 실제 Node output을 S3에 게시하고 Artifact HTTP body/header의 file digest, DB/provider의 outer-object digest, provider-missing 503을 각각 검증한다. 별도 `s01-storage-roundtrip` job은 disposable PG에서 `SnapshotStore`의 S3 locator 영속·other-tenant RLS 비가시성·delete 잔존 0을 JUnit으로 남긴다.

## 로컬 검증

| 명령/범위 | 결과 |
|---|---|
| object-store/config/artifact/replay/server-config focused pytest 7파일 | 87 passed, 3 skipped, exit 0. skip은 Windows symlink 생성 불가 1과 명시 Docker image opt-in 2이며 통과로 합산하지 않음 |
| 예약 provider ID·endpoint path 추가 focused 4파일 | 58 passed, 1 symlink skip, exit 0 |
| `pytest -q tests/test_route_coverage.py` | 40 passed, exit 0 |
| `python tools/check_contract_bindings.py` | exit 0, fixture 55 / bound response type 20 / replay guard 14 |
| `python tools/check_frontend_integrity.py` | exit 0, 9 rules / 0 violations |
| `python tools/check_response_freshness.py` | advisory exit 0, 10/10 |
| `python tools/check_ontology.py` | exit 0 |
| `python tools/generate_contracts.py` | exit 0; commit 뒤 drift 0 재확인 대상 |
| Python compile, Core YAML parse, Black, `git diff --check` | exit 0 |

## 미측정과 다음 행동

- hosted migration upgrade/definer audit, MinIO S3+PG, 실제 Artifact HTTP case와 정확한 JUnit 수는 PR head CI 전에는 미측정이다. green 전에는 완료로 세지 않는다.
- PR #149의 기존 Core red는 제품 conformance가 아니라 base의 알려진 `run only through tools/placement_lock_wait_diagnostic.py` skip map 1건 누락이다. PR #117 반영 base에서 다시 실행해야 한다.
- S3 ETag는 정본이 아니고, 운영 S3 vendor·TLS·IAM·retention/GC/restore/DR 인수는 이 카드로 주장하지 않는다.
- 다음 Codex: PR 생성 후 `run-core` label로 hosted migration/definer·MinIO·Local RLS·Artifact HTTP JUnit을 확인하고 차단 red만 수정한다. 다음 Claude: fixed head 독립 검토와 replay/read-ticket/strict-config 되살림 판정.
