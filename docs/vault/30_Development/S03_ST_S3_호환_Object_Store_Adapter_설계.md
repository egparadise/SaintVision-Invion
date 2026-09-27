---
doc_id: "S03-ST-S3-OBJECT-STORE-ADAPTER-DESIGN-001"
title: "S03-ST S3 호환 Object Store Adapter 설계"
version: "1.0.0"
status: "proposed"
author: "Codex"
updated: "2026-09-28T13:15:00+09:00"
source_of_truth: "Git"
---

# S03-ST S3 호환 Object Store Adapter 설계

> 범위: 이 문서는 구현 전 검토용이다. 현재 `LocalObjects` 파일럿과 공개 계약은 바꾸지 않으며, reviewer 승인 전 제품 코드·migration·생성 계약을 구현하지 않는다. S3 호환은 프로토콜 호환을 뜻할 뿐 특정 운영 제품 채택이나 HA·복구 인수를 뜻하지 않는다.

## 결정

제품 내부에 vendor-neutral `ObjectStore` 경계를 두고 `LocalObjects`와 `S3Objects`가 같은 의미를 구현한다. 요청자가 raw key를 주지 않고, 서비스가 `ObjectScope(tenantId, projectId, namespace)`와 object ID로 key를 만든다.

| 연산 | 계약 |
|---|---|
| `put(scope, objectId, body, expectedSha256)` | 실제 body SHA-256이 기대값과 같을 때만 불변 key에 게시한다. 같은 bytes 재시도는 성공, 다른 bytes가 이미 있으면 충돌이다. |
| `get(scope, objectId, expectedSha256, expectedSize)` | metadata·ETag를 정본으로 삼지 않고 읽은 bytes의 길이와 SHA-256을 모두 검증해 반환한다. |
| `exists(scope, objectId)` | 정확한 scope/key의 존재만 답하며 접근 거부와 timeout을 `false`로 낮추지 않는다. |
| `hash(scope, objectId)` | object bytes를 읽어 계산한 `{sha256, sizeBytes}`를 반환한다. S3 ETag는 사용하지 않는다. |
| `delete(scope, objectId)` | 멱등 DELETE 후 재조회 404까지 확인한다. 잔존·timeout이면 완료가 아니다. |

현행 `LocalObjects.locked()`와 `ObjectHandle.read/put/remove`는 구현 전환 중 내부 compatibility adapter로 유지할 수 있지만 공통 SPI에는 파일 inode/flock을 노출하지 않는다. 첫 S3 카드의 객체 상한은 현행 64 MiB를 유지한다. presign, multipart 50 GiB, lifecycle/DR, 운영 vendor 선택은 별도 카드다.

## 단일 서명 구현과 설정 정본

PR #135의 `tools/verify_storage_roundtrip.py`에 있는 SigV4 canonical-request·서명·HTTP 코드를 제품 모듈(예: `inv.s3_object_store`)로 옮긴다. `S3Objects`와 검증 도구가 그 모듈의 동일 client/오류 분류를 import하며, 도구 안에 두 번째 signer를 남기지 않는다. 전송 계층은 주입 가능하게 두어 PG-free 시험이 canonical request와 timeout을 결정적으로 검사한다.

설정은 #129 `configurationReadiness`가 관측하는 것과 동일한 보호된 `api.json`/immutable `INV_CONFIG_VOLUME`에서 한 번만 파싱한다. 권고 구조는 `objectStore: {providerId, endpoint, bucket, region, credentialFile, prefix}`다. endpoint만 readiness와 adapter에 따로 넣지 않는다. 자격증명은 `/run/saintvision/...`의 전용 regular file로 읽고 symlink·hardlink·과대 파일·느슨한 mode를 거부하며 값은 readiness, ProblemDetails, 로그에 출력하지 않는다. `configurationReadiness.unresolvedSettings`에는 endpoint뿐 아니라 bucket·credential file의 누락도 각각 안정된 설정 이름으로 나타낸다. 이 enum 추가는 생성 타입·fixture·bindings를 함께 바꾸는 additive 공개 계약 변경이다.

## 무결성·격리·실패 의미

key는 예를 들어 `<configured-prefix>/v1/tenants/<tenant-uuid>/projects/<encoded-project-id>/<namespace>/<object-uuid>`처럼 서버가 만든다. tenant UUID, 검증된 project ID, allowlist namespace, UUID object ID 이외의 raw path와 `..`, slash 재해석을 거부한다. preflight 도구는 `preflight/<nonce>` 전용 prefix와 권한을 사용하며 제품 prefix를 읽거나 지우지 않는다. IAM도 tenant/prefix 경계를 최소 권한으로 제한하고, DB의 tenant RLS가 object-store 격리를 대신한다고 간주하지 않는다.

`put`은 payload hash를 SigV4에 결속하고 같은 digest를 object metadata에 쓰되, 성공 판정은 후속 `get/hash`의 실제 bytes 검증으로 한다. upload timeout은 결과가 모호하므로 같은 key를 재조회한다. 기대 digest와 정확히 같으면 멱등 성공, 404면 retryable unavailable, 다른 bytes면 immutable conflict로 처리하며 덮어쓰지 않는다. 부분 쓰기/중단 upload는 ready DB 상태로 승격하지 않는다. `delete` 뒤 object가 남거나 재조회가 timeout이면 DB를 `deleting`에 유지하고 `deleted`로 바꾸지 않는다. provider timeout·접근 거부·5xx는 존재하지 않음이나 성공으로 낮추지 않고 비밀 없는 안정된 STORE/VERIFY 오류로 변환한다.

Artifact 다운로드는 `inv.storage_objects.content_hash/size_bytes`와 provider에서 검증한 실제 bytes가 일치해야만 응답한다. 최종 HTTP body를 다시 hash한 값이 `ArtifactDownloadMetadata.checksumSha256` 및 소문자 64-hex `X-Content-SHA256`과 모두 같아야 한다. receipt-derived bytes fallback, S3 ETag, metadata-only 검사는 허용하지 않는다.

## DB·계약 영향과 전환

`inv.storage_objects`에 immutable `provider_id`를 추가하는 additive migration을 권고한다. 기존 row는 `local-bounded-v1`로 backfill하고 새 S3 row는 설정의 안정된 provider ID를 기록한다. provider registry가 row의 ID로 reader를 선택하므로 설정 전환이 기존 로컬 객체를 S3 key로 조용히 재해석하지 않는다. `storage_parts`와 checkpoint pin은 기존 object FK를 통해 같은 provider를 상속한다. checkpoint 응답의 하드코딩된 `local-bounded-v1`도 row의 provider ID로 바꾼다. byte 복사·dual-read·기존 object migration은 이 카드 밖의 명시적 운영 절차다.

Artifact 다운로드 공개 shape와 `X-Content-SHA256` 형식은 ADR-099 그대로라 breaking 변경이 없다. 필요한 공개 변경은 configuration-readiness의 설정 이름 확장뿐이며 JSON Schema, 생성 TS/Go/Python 타입, fixture, serving anchor와 `generate_contracts.py` drift 0를 함께 요구한다. provider ID를 외부 응답에 새로 노출할지는 소비자가 생길 때 별도 계약으로 결정한다.

## 구현 순서와 합격 증거

1. 계약 먼저: `ObjectStore` conformance, 설정 schema/fixture/generated types, provider-id migration과 replay guard를 확정한다.
2. 제품 client로 SigV4를 한 번만 구현하고 #135 도구가 이를 import하게 한다. Local/S3 adapter와 result-view download를 차례로 결속한다.
3. PG-free: key/prefix 격리, canonical SigV4 fixture, Local/S3 공통 conformance, body/metadata/digest 불일치, ambiguous PUT 재조회, delete 잔존, timeout·403 fail-closed, redaction, 타 tenant/project 거부를 시험한다.
4. hosted MinIO lane: CI 소유 disposable instance에서 제품 adapter로 `put/get/exists/hash/delete`와 실제 Artifact HTTP download를 실행한다. JUnit에는 case와 passed 수, artifact에는 commit SHA·image digest·비밀 없는 endpoint 분류·정리 결과를 남긴다. #135 도구도 같은 제품 client를 사용해 왕복한다.
5. 실 PG route 시험은 storage row의 provider 선택, bytes/digest/header 3중 결속, receipt fallback 부재와 migration backfill을 확인한다. hosted lane 성공과 별개로 운영 S3·복구 인수는 미측정으로 남긴다.

구현 중 silent fallback(local→S3 또는 S3→local), ETag-as-digest, 누락 설정의 기본값 합성, timeout의 성공 처리, reviewer 전 migration/제품 코드 착지는 금지한다.
