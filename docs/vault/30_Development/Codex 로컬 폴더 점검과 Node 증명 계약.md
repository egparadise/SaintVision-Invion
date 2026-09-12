---
doc_id: "CONTRACT-STORAGE-SAMPLE-001"
title: "Codex 로컬 폴더 점검과 Node 증명 계약"
version: "1.5.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:24:08+09:00"
source_of_truth: "Git"
---

# Codex 로컬 폴더 점검과 Node 증명 계약

ADR-086 / owner Codex / reviewer Claude pending. 구현8c6805f, Linux harness a7d0f5e. [[2026-09-12_STORAGE-CHECK_Codex_검증보고]]. Claude71cf2c0 collector를 검토해 같은 tools/storage_check.py 경로에서 보완했다. 별도 collector/hash 정본을 만들지 않았다.

## 가능한 동작

운영자가 별도로 지정한 --root와 tenant/contribution/declared node가 모두 일치할 때 해당 로컬 폴더의 catalogued file을 점검한다. --root를 DB path나 request parent에서 추론하지 않는다. ReadRoot(ADR-085)로 실제 bytes를 두 번 읽고 catalog checksum과 byte_size를 비교한다. sample은 정수1~1000, 쿼리도 LIMIT을 사용하며 total/검사한 수/검사하지 않은 수를 구분한다.

```text
python tools/storage_check.py --dsn-env INV_STORAGE_CHECK_DSN --tenant <tenant UUID> --node <선언 Node ID> --contribution <기여 ID> --root <운영자가 허용한 로컬 절대경로> --sample 32 --json
```

DSN은 보호된 실행 환경 변수로 공급하며 argv에 넣지 않는다. CLI는 잘못된 인수·접속 오류에 원본 DSN/예외를 출력하지 않는다. PostgreSQL READ ONLY + REPEATABLE READ 트랜잭션으로 catalog를 읽는다. --apply/--record는 제공하지 않는다. 명령행 옵션 문자열만으로 실제 node 소유권을 입증하지 않는다.

응답 scope는 local-storage-sample-v1, nodeBindingVerified=false, recorded=false, operationalAcceptanceAssessed=false다. sampleHealthy는 검사 대상으로 선택된 sample의 결과이며 전체 폴더/원격 Node/운영 인수 정상이라는 뜻이 아니다. sampled는 hash 기준이 있는 파일의 검증 시도 수(읽기 실패 포함), mismatches는 실패 수다. unverifiable은 기준 hash가 없는 파일이다. unsampled는 선택하지 않은 catalog 항목 수다. 빈 sample/기준 없는 항목/파일 오류/hash 또는 size 불일치는 sampleHealthy=false다. freeBytes를 경로 기반 disk_usage로 추정해 운영 건강 판정에 쓰지 않는다.

exit0은 선택 sample 일치, exit1은 sample 불일치·검증 불가, exit2는 잘못된 scope/설정·접속/루트 오류다. exit0도 Node 신원 확인·DB 운영 기록·인수 완료가 아니다. text와 JSON은 같은 판정식을 쓴다.

## 기존 StorageCheck

record_storage_check의 healthy는 reachable AND sampled_count>0 AND mismatch_count=0 AND unverifiable 없음으로 제한한다. counts는 실제 nonnegative int만 허용한다. 주의 대상 집계는 과거 healthy boolean을 그대로 신뢰하지 않고 zero sample/검증 불가 detail/미래 시각/같은 최신 시각의 실패를 재평가한다. raw DB 제약·과거 row를 이번에 변경하지 않는다. 직접 SQL로 과거와 같은 boolean을 만들 수 있으므로 raw healthy만 소비하면 안 된다. 서비스와 집계의 제한은 Node attestation의 대체물이 아니다.

## 다음 쓰기 경계

다음 Codex 구현은 기존 Node mTLS/identity/epoch 체계에 collection challenge와 서명된 결과를 연결하는 것이다. tenant·node·contribution·승인 root 설정 버전·대상 catalog digest·challenge/만료·epoch·실제 결과 hash를 함께 묶고, 서비스가 현재 권한/최신 epoch/중복 결과를 확인한 뒤 기존 StorageCheck/Evidence에 원자적으로 기록해야 한다. root 승인·node 인증·관측의 freshness가 없으면 기록하지 않는다. 새 DB 원장을 별도로 복제하기 전에 기존 kernel Evidence와 idempotency 계약을 확인한다.

Claude는 이 보완본을 독립 검토하고 운영 절차를 조율한다. Gemini는 sample 일치와 Node 증명/운영 상태 unknown을 구분해야 한다. 실제 .225 설치/7개 시험과5대 인수는 이 로컬 점검으로 충족되지 않는다.



## 인증 선행 보강2830887

ADR-087에서 inbound ASGI verification failure를 명시적으로 거부하고 NodePrincipal.lock_current를 실제 heartbeat 기록 transaction에 연결했다. 이 메서드는 public tenant/node/certificate/status를 row lock으로 재확인한다. kernel recovery epoch/Storage challenge/Evidence 원자 연결은 아직 아니며 기존 Go transport nonce·ChannelProof 경로를 재사용하는 후속 계약을 진행한다. [[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]].


## ADR-088 내부 서명 sample 프로토콜

[[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_검증보고]] 구현124fe97. 불변 Challenge는 ChannelProof 전체·Run/project/contribution·승인 root_version·ordered catalog ID/version/path/hash/size·catalogued·32byte nonce·발급/만료를 포함한다. manifest 자체의 SHA-256은 domain prefix와 canonical JSON으로 계산한다. canonical JSON은 Python sort_keys/ensure_ascii/공백 없는 separators/NaN 금지이며 시각은 정수 epoch seconds, 용량·항목 수는 제한된 정수다. endpoint 등 문자열도 digest에 포함한다.

서명 payload는 protocol=node-storage-sample-v1, challengeSha256, observedAt(epoch seconds), ordered observations(locationId/sha256/byteSize)뿐이다. envelope는 payload/base64와 signature/base64뿐이다. 서명 대상은 ASCII saintvision/node-storage-sample/v1 뒤 NUL byte와 payload bytes다. Ed25519 인증서의 pin/SAN/epoch/EKU/유효기간을 기존 certificate_identity로 확인하고 같은 키로 검증한다. 인증서 DER는 신뢰된 채널에서 얻어 증거와 보존해야 하며 request의 자기 선언 공개키를 신뢰하지 않는다.

v1은32파일·파일당1MiB·payload64KiB·30초의 제한된 sample이다. 실제 열린 파일 크기를 먼저 확인한다. 강제 OS I/O deadline은 아니며 완료 시 만료면 서명하지 않는다. 실패 파일은 null hash/size 쌍이며 mismatch, 기준 없는 파일은 unverifiable이다. 빈/중복 manifest, 관측 누락·개수/순서 불일치·추가 필드·크기/서명/서명 domain 변경을 거부한다. 건강 판정은 verifier가 재계산한다. CLI와 같은 sampler/hash_file을 사용하고 CLI 출력의 Node 신원 미검증/운영 기록0은 유지한다.

이것은 내부 Python 참조 구현이며 공개 JSON Schema/Go endpoint를 추가한 것이 아니다. trusted caller가 실제 Run 권한/현재 catalog를 고정해야 한다. 실제 Node adapter는 인증된 요청만 처리하고 승인된 로컬 root/key를 선택해야 한다. private key를 Control Plane으로 보내지 않는다. 소비되지 않은 challenge인지와 현재 authority 재검사는 후속 DB transaction 책임이다. 같은 증거의 순수 재검증은 가능하며 기록0/운영 인수false다. 새 원장 없이 기존 inv.evidence와 StorageCheck를 연결하는 후속 검증 전에는 운영 건강을 갱신하지 않는다.


## ADR-089 Go Node 연결

[[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_검증보고]],688678d. 내부 Python 참조만 있던 ADR-088 후속으로 공통 JSON Schema 6개와 Go endpoint를 추가했다. POST /v1/storage/sample request는 NodeStorageSampleInput(challenge=canonical Challenge bytes의 base64), response는 NodeStorageSignedSample(payload/signature)다. Go는 받은 정확한 challenge bytes를 digest에 넣고 Python verifier는 발급된 canonical challenge와 대조한다. request가 canonical이 아니면 verifier 일치 보장을 얻지 못한다.

opt-in --storage-policy의 NodeStorageRootConfig(channel,contribution_id,root_version,root)는 로컬 보호 파일이며 v1에서 한 폴더만 활성화한다. Node peer mTLS가 먼저 필요하고 Node scope와 구성 hash/현재 인증서를 수집 전후 확인한다. 설정 변경은 fail closed/재시작으로 처리하며 root-policy의 durable rollback floor는 아직 없다. worker workload에 Node 키를 전달하지 않는다. 승인 root/key를 request 경로에서 만들지 않는다.

Go 수집은 Linux descriptor 경계/동일 device/regular single-link/두 번 bounded hash를 사용한다. Windows native opener는 거부하며 Docker/WSL Linux에서 동작하는 Node와 구분한다. Node별 별도 sample slot1/5초 cooperative context, client6초, 기존32파일/1MiB/30초·64KiB 제한이다. blocking filesystem syscall 강제 중단/일관 snapshot은 아니다. Control Plane은 실제 TLS peer DER를 envelope와 함께 받아 별도 signature verifier에 공급한다.

실제 Go+mTLS/파일/DB 시험130 통과는 운영 기록 성공이 아니다. durable issuer·nonce 소비·현재 Run/project/channel/contribution/catalog 재확인 및 기존 Evidence/StorageCheck의 단일 transaction 연결을 구현할 때까지 운영 기록0을 유지한다. 같은 epoch/version 숫자만으로 current 권한을 주장하지 않는다.


## ADR-090 — durable 발급과 기존 기록의 원자 연결

fd0c081/0037부터 StorageSampleStore.issue/accept/collect는 내부 trusted boundary다. 현재 linked project can_request와 contribution 등록 소유자를 함께 검사한다. Run version/attempt, epoch, channel proof, root path/version, 제한된 catalog 항목을 발급·기록 transaction에서 잠그고 재검사한다. network I/O는 두 transaction 사이에만 있다. requests/consumptions는 불변 protocol state이며 inv.evidence/public.storage_checks가 기존 기록 정본이다.

같은 request는 sample_limit/scope/nonce를 바꿀 수 없다. accept는 같은 bytes만 같은 IDs로 replay하며 다른 응답은 충돌이다. 현재 권한은 replay에도 필요하다. 모든 증거/점검/consumption/outbox는 원자 기록되며 만료를 마지막 쓰기 뒤에도 검사한다. sample_healthy는 표본 일치일 뿐 Run 완료·운영 인수/전체 디스크 정상 판정이 아니다. cataloguedAtIssue는 발급 때의 수이며 unsampled 파일 bytes를 증명하지 않는다. 실제 안전한 디스크 snapshot도 아니다.

최소 컬럼 SELECT·고정 sentinel UPDATE·tenant RLS와 불변 trigger를 적용한다. 새 SECURITY DEFINER 없음. 신규 공개 API/자동 만료 갱신/운영 설치/ResultView UI 표시/독립 인수는 미완료. [[2026-09-12_STORAGE-COMMIT_Codex_검증보고]]의 같은 SHA 검증을 따른다. 앞 절의 미구현 진술은 해당 과거 단계 기준이며 이 절이 후속 DB 구현 상태를 갱신한다.


## ADR-091 — 인증된 과거 관측 조회

GET /v1/projects/{project}/runs/{run_id}/storage-samples/{request_id}는 kernel AccessTokens 인증 후 현재 can_request·linked business 권한·원 요청자·등록 소유자를 잠그고 검사한다. 기존 request/consumption/Evidence/StorageCheck를 조회하여 당시 시각의 서명/인증서, challenge/response hash 및 metadata 연결을 재검증한다. UTC timestamp 의미를 사용하여 DB 시간대와 무관하게 확인한다. 조회는 DB 관측·Run 상태를 변경하거나 Node 수집을 시작하지 않는다.

StorageObservationView/RecordedStorageObservation이 공통 Schema다. pending/expired에는 observation=null, recorded에는 evidenceId/checkId/observedAt/integrityVerified/sampleHealthy 및 표본 집계가 있다. currentHealth는unknown, operationalAcceptanceAssessed는false다. 원 root/path·파일명·nonce·서명·인증서·subject는 HTTP 응답에 포함하지 않고 no-store를 적용한다.

terminal Run/회수된 Node channel·contribution도 현재 원 요청자와 등록 소유자 권한이 유지되면 역사 조회는 허용한다. 새 수집은0037의 active/current channel/root 조건을 계속 요구한다. 당시 인증서 유효성과 현재 운영 신뢰를 혼동하지 않는다. request 목록·수집 POST·운영 설치/화면 인수는 별도이며 이 GET 구현을 운영 배포 완료로 표시하지 않는다. [[2026-09-12_STORAGE-VIEW_Codex_검증보고]]의 같은 SHA 증거를 따른다.


## ADR-092 — 재시작 후에도 유지되는 설정 최소 버전

f9d69a8은 기존 identity/epoch-bound private journal에 contribution별 rootVersion/channelVersion 및 root/channel/exact policy hash를 보존한다. 두 버전은 각각 단조 증가하고 같은 버전의 경로·채널 변경 또는 두 버전 모두 같은데 exact bytes 변경은 거부한다. 새 contribution 선택이 기존 contribution floor를 제거하지 않는다. 현재 TLS 인증서/키와 root/config를 검증한 뒤 floor를 영속화한다. pin callback 없는 sampler는 생성하지 않는다. 동시 writer는 기존 journal process lock으로 배제하고 이 함수는 startup 전용이다.

local startup receipt는 tenant/node/epoch·contribution·두 버전·hash이며 raw root/key/certificate는 포함하지 않는다. operationalAcceptanceAssessed=false다. 서명된 서버 인수나 Node 운영 health/작업 성공 증거로 쓰지 않는다. 전체 journal의 관리자 삭제·과거 backup 복원을 탐지하는 장치가 아니며 기존 recovery epoch/fencing 계약을 유지한다. [[Codex Node 저장소 설정 설치와 교체 절차]]에 실패 후 forward 복구·실제 운영 bundle 미연결 범위를 기록한다.
