---
doc_id: "HIST-CODEX-S3-OBJECT-STORE-SPI-001"
title: "S3 호환 ObjectStore 구현 1단계 — SPI·단일 SigV4·provider conformance"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-28T18:10:00+09:00"
source_of_truth: "Git"
---

# S3 호환 ObjectStore 구현 1단계

## 범위

- Card 45, owner Codex / reviewer Claude.
- Branch `agent/codex/s3-object-store-implementation-v1`은 승인된 #140 설계 v1.2(`9c02a89b`)를 구현하며, 단일 signer의 출처인 #135 head `974f68d0` 위에 stack한다. #135와 #140 병합 전에는 integration에 병합하지 않는다.
- 이번 첫 분할은 locator 기반 `ObjectStore` SPI, 기존 `LocalObjects` compatibility wrapper, 제품 `S3Objects`, 제품 단일 SigV4 client, #135 preflight의 제품 client 재사용, PG-free/hosted conformance까지다.
- migration, strict 운영 설정, 두 checkpoint 생산자, Artifact provider-body download는 다음 stack PR 범위이며 이 단계만으로 제품 S3 경로가 완결됐다고 쓰지 않는다.

## 구현 경계

`ObjectStore`는 `put/get/delete/exists/hash`만 공개하고 tenant/project 권한은 storage row를 읽는 service/RLS 계층에 남긴다. Local은 기존 flat locator와 directory flock을 유지하고 scope를 받았다가 버리는 가짜 격리를 만들지 않는다. S3 locator는 설정 prefix 아래 `v1/tenants/<uuid>/projects/<project>/<namespace>/<uuid>` 구조만 허용하며 `..`, prefix 이탈, 미지 namespace, 비정규 UUID를 거부한다.

S3 `put`은 payload hash와 metadata digest를 같은 SigV4 요청에 묶고 후속 GET의 실제 body·metadata·길이를 다시 검증한다. timeout/5xx/409는 ambiguous 결과로 재조회해 동일 bytes만 멱등 성공으로 인정하고, 403 같은 명확한 접근 거부는 기존 object가 같더라도 성공으로 낮추지 않는다. `delete`는 후속 HEAD 404까지 확인하며 provider 원문 오류·endpoint·locator·secret을 DomainError에 싣지 않는다.

`inv.s3_client.S3Client`가 canonical request/signature/HTTP 전송의 단일 구현이다. `tools/verify_storage_roundtrip.py`는 signer 복사본을 제거하고 이 제품 class를 import한다. 고정 digest MinIO job에는 제품 `S3Objects`와 실제 Linux `LocalObjectStore`의 동일 conformance JUnit을 추가했다.

## 시험과 미측정

| 명령 | 결과 |
|---|---|
| `pytest -q tests/core/test_s3_object_store.py tests/core/test_storage_roundtrip_verifier.py` | 35 passed, exit 0 |
| `py_compile` 제품/도구 5파일 | exit 0 |
| `yaml.safe_load(.github/workflows/core.yml)` | exit 0 |
| hosted `tools/test_s3_object_store_hosted.py` | PR `run-core` label에서 실행 예정 |

PG-free 시험은 scoped locator, prefix 이탈, timeout 멱등, 403 fail-closed, body/metadata/size drift, delete 잔존, Local wrapper, signer 단일성, 공개 Input/Request/Spec/Command의 `objectId`/`locator` 입력 0건을 단언한다. 로컬 MinIO·Docker·PostgreSQL은 실행하지 않았다.

## 다음 행동

Claude가 이 분할 PR을 검토하고 hosted MinIO JUnit 2건이 실행돼야 한다. 그 뒤 같은 stack에서 provider/locator backfill migration, strict `objectStore` 설정, producer replay guard, provider-body Artifact download를 구현하며 hosted migration upgrade/definer audit를 증거로 남긴다.

## Claude 독립 검토 반영 (v1.1)

- hosted `s01-storage-roundtrip` job은 `requirements-test.txt`의 pinned pytest를 설치한다. 제품 conformance가 실패해도 기존 #135 storage evidence step은 `if: always()`로 별도 실행되어 두 증거가 조용히 함께 사라지지 않는다.
- S3 PUT은 서명된 `If-None-Match: *` 조건부 요청이다. 412는 실제 object를 다시 읽어 같은 byte만 멱등 성공으로 인정하고, 다른 byte는 `STORE-0005`/409로 거부한다. Local compatibility wrapper도 기존 byte와 다른 PUT을 같은 409 의미로 거부한다.
- AWS S3 SigV4 공식 GET Object 예제(2013-05-24, signature `f0e8…db41`)를 known-answer vector로 고정했다. signer key-derivation/canonicalization 변이는 hosted 환경 없이도 잡힌다.
- 공개 입력 검사는 request root의 중첩 property와 `$ref`, standalone request schema, FastAPI HTTP route의 path/query parameter까지 확장했다.
- PG-free focused 결과: `38 passed`, YAML parse와 `git diff --check` exit 0. Hosted S3/Local conformance 및 기존 storage evidence의 실제 JUnit은 수정 head의 Core run에서 확인한다.
