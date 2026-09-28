---
doc_id: "HIST-CODEX-S3-OBJECT-STORE-PRODUCT-BINDING-002"
title: "S3 호환 ObjectStore 제품 결속 v2"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-09-28T12:10:00+09:00"
source_of_truth: "Git"
---

# S3 호환 ObjectStore 제품 결속 v2

## 시작 조건과 범위

- Card 45 v2, owner Codex / reviewer Claude.
- branch `agent/codex/s3-object-store-implementation-v2`, stack base PR #149 head `5a794ae9`, 승인 설계 PR #140 v1.2 head `9c02a89b`.
- 구현 chain은 v1 SPI `6a4841aa`, provider/locator migration·replay `daf02843`, immutable PUT 보강 `73adeae6`, 제품 결속 `51ffdc26`이다. 승인된 v1 head `5a794ae9`는 force-push 없이 merge commit `82df64a0`으로 결속해 stack base 조상 관계를 복구했다.
- 로컬 실 PostgreSQL·Docker는 메모리 규칙에 따라 실행하지 않았다. 실제 migration/definer, S3+PostgreSQL, Artifact HTTP 다운로드는 `run-core` hosted lane에서만 실행하도록 배선했다.

## 구현

- `storage_objects.provider_id`·`locator`의 기존 local row backfill은 `local-bounded-v1`과 정확한 `obj-<uuidhex>`를 보존한다. checkpoint 공개 content에는 provider만 남고 locator는 노출하지 않는다. same-provider replay는 quiet, provider/digest drift는 `GRAPH-0004` 전체 실패다.
- `configurationReadiness.objectStore`는 `providerId`, `endpoint`, `bucket`, `region`, `credentialFile`, `prefix`의 exact object다. 미지/누락 inner key는 startup 거부, endpoint/bucket/private credential 미해결은 값 없이 이름만 관측한다. 자격 파일은 regular·single-link·bounded·0600이며 symlink/hardlink를 거부한다. S3가 예약 local provider ID를 주장하거나 root path-style 서명과 불일치하는 endpoint path를 쓰는 것도 거부한다.
- worker와 API가 같은 immutable `api.json` 정본을 읽는다. Workspace의 `snapshotObjectRoot`·`restoreRoot`가 둘 다 있으면 snapshot root의 exact Local provider와 준비된 S3 provider를 API read registry에 함께 등록하지만 dual-write는 하지 않는다. registry는 persisted provider ID를 exact match하고, write/collect/shard/workspace 경로는 주입 provider와 row provider가 다르면 상태 변경 전 `STORE-0001`/503/retryable로 거부한다. 제품 `WorkspaceRecovery.restore`와 checkout도 잠금 전 provider ticket을 만든 뒤 provider→DB 순서로 immutable row를 재검증한다.
- locator prefix는 provider 운영 정체성이다. 다른 configured prefix의 canonical locator는 잘못된 사용자 key 422로 낮추지 않고 `STORE-0001`/503/retryable로 닫는다. S3 credential의 `secret_key`는 dataclass repr에서 제외한다.
- 결과 다운로드는 receipt body fallback을 제거했다. 짧은 RLS transaction으로 immutable ticket을 만든 뒤 provider I/O를 수행하고, 같은 row·attempt·provider·locator·digest·size를 재검증한다. S3는 DB lock 밖에서 읽고 Local은 provider flock을 잡은 상태로 짧은 DB 재검증을 수행해 provider→DB lock order를 유지한다. provider/object 부재는 `STORE-0001`/503/retryable이고 과거 receipt 200으로 낮추지 않는다.
- HTTP route·공개 request schema의 `objectId`/`locator` 입력 0건 스캔은 positional·keyword-only·`Query(alias=...)`까지 포함한다. configuration readiness enum·fixture·Python/TS/Go/wire 생성물은 `generate_contracts.py`로 동기화했다.
- hosted Core는 digest-pinned MinIO를 명시적으로 생성·정리한다. 실제 Node output을 S3에 게시하고 Artifact HTTP body/header의 file digest, DB/provider의 outer-object digest, provider-missing 503을 각각 검증한다. 별도 `s01-storage-roundtrip` job은 disposable PG에서 S3 locator 영속·other-tenant RLS·delete 잔존 0뿐 아니라 제품 `WorkspaceRecovery.restore`의 S3 bytes·receipt replay와 Snapshot/workspace-output 두 생산자의 quiet replay·provider drift `GRAPH-0004`·event/pin 단일성을 JUnit으로 남긴다.

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
| Claude r1/r2 provider/prefix·제품 restore 보강 PG-free | provider binding 6 passed + S3 adapter 23 passed + 기존 replay/artifact/workspace 37 passed; 설정 3파일 합계 26 passed/1 Windows symlink skip, exit 0 |

## Hosted 관측과 남은 경계

- head `3cf7b33c` run `36370524842`: migration upgrade·LAN/Docker 사전 단계와 Core pytest `3361 passed / 36 skipped / 2 deselected / 0 failed`, S01 job `108765769138`의 conformance 2/2 및 MinIO+disposable PG 3/3, Backend 3.12·3.14 `3055 passed / 47 skipped / 2 deselected / 0 failed`, Docs·Frontend·Desktop은 green이다. Core job은 제품 실패가 아니라 base에 PR #117의 `run only through tools/placement_lock_wait_diagnostic.py` exact skip 1건이 없어 skip gate에서만 red였다.
- `c556e99a`가 Backend와 같은 exact skip 사유를 Core map에 넣었다. Claude r2가 찾은 제품 호출 공백은 그 뒤 `WorkspaceRecovery.restore`·checkout registry 선택과 실제 제품 restore hosted 시험으로 보강했다. 이 새 head의 S01 JUnit·Core skip/build/Go/TS 완주는 아직 대기이며 green 전에는 완료로 세지 않는다.
- S3 ETag는 정본이 아니고, 운영 S3 vendor·TLS·IAM·retention/GC/restore/DR 인수는 이 카드로 주장하지 않는다.
- 다음 Codex: 수정 head의 hosted migration/definer·MinIO·제품 Workspace restore·Artifact HTTP·skip/build/Go/TS를 확인한다. 다음 Claude: fixed head의 제품 호출 경로와 replay/read-ticket/strict-config 되살림을 재판정한다.
