---
doc_id: "S03-ST-S3-OBJECT-STORE-ADAPTER-DESIGN-001"
title: "S03-ST S3 호환 Object Store Adapter 설계"
version: "1.1.0"
status: "proposed"
author: "Codex"
updated: "2026-09-28T15:10:00+09:00"
source_of_truth: "Git"
---

# S03-ST S3 호환 Object Store Adapter 설계

> 범위: 이 문서는 구현 전 검토용이다. 현재 `LocalObjects` 파일럿과 공개 계약은 바꾸지 않으며, reviewer 승인 전 제품 코드·migration·생성 계약을 구현하지 않는다. S3 호환은 프로토콜 호환을 뜻할 뿐 특정 운영 제품 채택이나 HA·복구 인수를 뜻하지 않는다.

## 결정

제품 내부에 vendor-neutral `ObjectStore` 경계를 둔다. 공통 SPI는 tenant/project scope를 받아
provider가 임의로 버리는 형태가 아니라, DB에 영속된 **provider-native opaque locator**와 검증
메타데이터를 받는다. 서비스 계층은 먼저 tenant/project RLS가 적용된 `storage_objects` row를
읽어 immutable `provider_id`, locator, digest, size를 얻고 그 뒤 registry에서 provider를 고른다.
요청자나 HTTP 입력은 raw locator/key를 만들 수 없다.

| 연산 | 계약 |
|---|---|
| `put(locator, body, expectedSha256)` | 실제 body SHA-256이 기대값과 같을 때만 불변 locator에 게시한다. 같은 bytes 재시도는 성공, 다른 bytes가 이미 있으면 충돌이다. |
| `get(locator, expectedSha256, expectedSize)` | metadata·ETag를 정본으로 삼지 않고 읽은 bytes의 길이와 SHA-256을 모두 검증해 반환한다. |
| `exists(locator)` | 정확한 locator의 존재만 답하며 접근 거부와 timeout을 `false`로 낮추지 않는다. |
| `hash(locator)` | object bytes를 읽어 계산한 `{sha256, sizeBytes}`를 반환한다. S3 ETag는 사용하지 않는다. |
| `delete(locator)` | 멱등 DELETE 후 재조회 404까지 확인한다. 잔존·timeout이면 완료가 아니다. |

현행 `LocalObjects.locked()`와 `ObjectHandle.read/put/remove`는 구현 전환 중 내부 compatibility
adapter로 유지할 수 있지만 공통 SPI에는 파일 inode/flock을 노출하지 않는다. Local locator는
기존 `obj-<hex>`/`part-<hex>-<index>` 평면 이름이고, S3 locator는 서버가 만든 scoped key다.
따라서 scope를 Local에 전달한 뒤 버리는 구현은 금지한다. 첫 S3 카드의 객체 상한은 현행
64 MiB를 유지한다. presign, multipart 50 GiB, lifecycle/DR, 운영 vendor 선택은 별도 카드다.

## 단일 서명 구현과 설정 정본

PR #135의 `tools/verify_storage_roundtrip.py`에 있는 SigV4 canonical-request·서명·HTTP 코드를 제품 모듈(예: `inv.s3_object_store`)로 옮긴다. `S3Objects`와 검증 도구가 그 모듈의 동일 client/오류 분류를 import하며, 도구 안에 두 번째 signer를 남기지 않는다. 전송 계층은 주입 가능하게 두어 PG-free 시험이 canonical request와 timeout을 결정적으로 검사한다.

설정은 #129 `configurationReadiness`가 관측하는 것과 동일한 보호된 `api.json`/immutable
`INV_CONFIG_VOLUME`에서 한 번만 파싱한다. 단일 정본은
`configurationReadiness.objectStore: {providerId, endpoint, bucket, region, credentialFile, prefix}`이며
`configurationReadiness.nodeMtlsCaBundle`은 sibling이다. endpoint를 adapter용 별도 설정에 복제하지
않는다. 자격증명은 `/run/saintvision/...`의 전용 regular file로 읽고 symlink·hardlink·과대
파일·느슨한 mode를 거부하며 값은 readiness, ProblemDetails, 로그에 출력하지 않는다.
`configurationReadiness.unresolvedSettings`에는 endpoint뿐 아니라 bucket·credential file의
누락도 각각 안정된 설정 이름으로 나타낸다.

입력 schema는 strict-subset이므로 신 키 추가 자체는 additive가 아니다. rollout은 (1) 먼저
새 binary를 배포하되 이 binary는 legacy `objectStoreEndpoint` 또는 새 `objectStore` 중 정확히
하나만 허용하고 둘을 동시에 주면 startup을 거부하고, (2) 그 binary가 동작하는 동안 config를
새 block으로 전환하고, (3) 관측 기간 뒤 legacy 키 지원을 제거하는 순서다. 구 binary에 새 block을
먼저 주면 startup을 거부한다. 공개 응답의 `unresolvedSettings` enum 확장만 JSON Schema·생성
타입·fixture·bindings를 함께 바꾸는 additive 계약 변경이다.

## 무결성·격리·실패 의미

S3 locator는 예를 들어 `<configured-prefix>/v1/tenants/<tenant-uuid>/projects/<encoded-project-id>/<namespace>/<object-uuid>`처럼 서버가 만든다. tenant UUID, 검증된 project ID, allowlist namespace, UUID object ID 이외의 raw path와 `..`, slash 재해석을 거부한다. preflight 도구는 `preflight/<nonce>` 전용 prefix와 권한을 사용하며 제품 prefix를 읽거나 지우지 않는다. IAM도 tenant/prefix 경계를 최소 권한으로 제한한다.

Local은 의도적으로 다른 격리 계층을 가진다. 기존 private root 안의 locator는 전역 평면이며
tenant/project를 자체 검증하지 않는다. Local 접근 권한은 반드시 tenant-scoped DB row 조회를
통해 locator를 획득한 서비스 계층이 강제한다. 공통 provider conformance는 bytes 무결성,
멱등 put, 충돌, delete/timeout 의미를 공유하되 provider 내부 tenant-prefix 격리는 S3 전용
conformance로 둔다. Local 격리는 별도 service/RLS 음성 시험에서 타 tenant/project가 locator를
얻지 못함을 검증한다. 이를 S3와 같은 provider-internal 격리라고 주장하지 않으며, Local re-key와
기존 파일 migration은 하지 않는다.

`put`은 payload hash를 SigV4에 결속하고 같은 digest를 object metadata에 쓰되, 성공 판정은 후속 `get/hash`의 실제 bytes 검증으로 한다. upload timeout은 결과가 모호하므로 같은 key를 재조회한다. 기대 digest와 정확히 같으면 멱등 성공, 404면 retryable unavailable, 다른 bytes면 immutable conflict로 처리하며 덮어쓰지 않는다. 부분 쓰기/중단 upload는 ready DB 상태로 승격하지 않는다. `delete` 뒤 object가 남거나 재조회가 timeout이면 DB를 `deleting`에 유지하고 `deleted`로 바꾸지 않는다. provider timeout·접근 거부·5xx는 존재하지 않음이나 성공으로 낮추지 않고 비밀 없는 안정된 STORE/VERIFY 오류로 변환한다.

Artifact 다운로드는 현행 receipt-only body 경로를 provider body 경로로 **교체**한다. 짧은
tenant/project-scoped DB transaction이 immutable provider/locator/digest/size read ticket을 만들고
닫힌 뒤 provider bytes를 읽는다. Local은 먼저 provider lock을 얻고 짧은 DB 재검증을 수행해
provider→DB 순서를 지킨다. S3는 provider-wide lock 없이 원격 read를 DB lock 밖에서 수행한 뒤
짧은 DB 재검증으로 row가 같은 ticket인지 확인한다. 어떤 경로도 DB lock을 잡은 채 provider
I/O를 하지 않으므로 GC의 provider→DB 순서와 교착 순환을 만들지 않는다.

receipt는 audit/commit 증거로 남지만 body fallback이나 dual-read가 아니다. ready row인데 provider
object가 없거나 prefix가 잘못된 경우 과거 receipt 200으로 낮추지 않고 안정된
`STORE-0001`/503/retryable ProblemDetails와 내부 integrity alert를 낸다. 최종 HTTP body의 실제
SHA-256은 DB `content_hash`, provider 검증 digest, live `ArtifactContentResponse.artifact.checksumSha256`,
소문자 64-hex `X-Content-SHA256` 네 값과 같아야 한다. 설계-only
`ArtifactDownloadMetadata`를 쓰는 시험에서는 대응 필드가 `contentSha256`이며 live route 계약과
혼동하지 않는다. S3 ETag와 metadata-only 검사는 허용하지 않는다.

## DB·계약 영향과 전환

`inv.storage_objects`에 immutable `provider_id`와 provider-native locator를 추가하는 additive migration을
권고한다. 기존 row는 `provider_id=local-bounded-v1`과 기존 평면 object 이름으로 backfill하고 새
S3 row는 설정의 안정된 provider ID와 scoped locator를 기록한다. provider registry가 row의 ID로
reader를 선택하므로 설정 전환이 기존 로컬 객체를 S3 key로 조용히 재해석하지 않는다.
`storage_parts`와 checkpoint pin은 기존 object FK를 통해 같은 provider를 상속한다. byte 복사,
dual-read, 기존 object re-key는 이 카드 밖의 명시적 운영 절차다.

provider는 이미 checkpoint 공개 content와 identity hash에 참여한다. 이 불변식을 유지한다.
`snapshots.py`와 `workspace_resume.py` 두 생산 지점 모두 하드코딩 문자열 대신 해당 immutable storage
row의 `provider_id`를 사용해야 하며 한쪽만 바꾸면 안 된다. 기존 row backfill 값은 정확히
`local-bounded-v1`이므로 기존 checkpoint content/digest/replay는 변하지 않는다. 새 provider/object로
같은 논리 checkpoint identity를 다시 발행하면 provider가 identity의 일부이므로 digest가 달라지고
기존 `GRAPH-0004`가 의도대로 발생한다. 설정 전환만으로 기존 row provider를 바꾸지 않는다. 두
생산 경로 각각에 기존 local replay 불변, same-provider replay, 다른-provider identity 충돌 replay
guard를 둔다. provider는 이미 JSONB/event/응답에 공개되어 있으므로 별도 노출 결정을 유예하지 않는다.

Artifact 다운로드 공개 shape와 `X-Content-SHA256` 형식은 ADR-099 그대로라 breaking 변경이 없다.
다만 ready DB row와 provider object가 어긋나면 기존 receipt 200 대신 503이 되는 것은 의도한
fail-closed 동작 변화다. 필요한 공개 shape 변경은 configuration-readiness의 설정 이름 확장뿐이며
JSON Schema, 생성 TS/Go/Python 타입, fixture, serving anchor와 `generate_contracts.py` drift 0를
함께 요구한다.

## 구현 순서와 합격 증거

1. 계약 먼저: opaque-locator `ObjectStore` 공통 conformance와 Local service/RLS·S3 prefix 전용 격리 suite를 분리하고, 설정 schema/fixture/generated types, provider-id/locator migration과 두 checkpoint 생산자의 replay guard를 확정한다.
2. 제품 client로 SigV4를 한 번만 구현하고 #135 도구가 이를 import하게 한다. Local/S3 adapter, 두 checkpoint 생산자, result-view의 read-ticket 기반 provider download를 차례로 결속한다.
3. PG-free: S3 key/prefix 격리, Local flat-locator 보존, canonical SigV4 fixture, 공통 bytes conformance, body/metadata/digest 불일치, ambiguous PUT 재조회, delete 잔존, timeout·403 fail-closed, redaction을 시험한다. 타 tenant/project 거부는 Local service/RLS와 S3 prefix/IAM 경계를 각각 시험한다.
4. hosted MinIO lane: CI 소유 disposable instance에서 제품 adapter로 `put/get/exists/hash/delete`와 실제 Artifact HTTP download를 실행한다. JUnit에는 case와 passed 수, artifact에는 commit SHA·image digest·비밀 없는 endpoint 분류·정리 결과를 남긴다. #135 도구도 같은 제품 client를 사용해 왕복한다.
5. 실 PG route 시험은 storage row의 provider/locator 선택, bytes/DB digest/live artifact/header 4중 결속, receipt fallback 부재, ready-row/provider-missing 503, migration backfill과 두 checkpoint replay guard를 확인한다. hosted lane 성공과 별개로 운영 S3·복구 인수는 미측정으로 남긴다.

구현 중 silent fallback(local→S3 또는 S3→local), ETag-as-digest, 누락 설정의 기본값 합성, timeout의 성공 처리, reviewer 전 migration/제품 코드 착지는 금지한다.
