---
doc_id: "ARCH-MODEL-MANIFEST-001"
title: "ModelManifest 커널 계약과 저장 Catalog 경계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T12:10:45+09:00"
source_of_truth: "Git"
---

# ModelManifest 커널 계약과 저장 Catalog 경계

ARCH-WEB-FABRIC-001/ROADMAP-VIRTUAL-COMPUTER-001 1.0.0의 VF-CX-02 구현 계약. owner Codex, 독립 reviewer Claude 미수신. JSON Schema 정본은 contracts/v1alpha1/core.schema.json의 ModelId/ModelShard/ModelReplica/ModelRuntimeCompatibility/ModelManifest이며 Python/TS/Go/Node schema는 생성한다.

## 정본과 재사용

- committed bytes identity의 정본은 `inv.model_manifests`. modelId + project + immutable version으로 식별하고 model body/manifestHash/sourceRun/epoch를 불변 기록한다.
- 물리 위치와 기여 디스크 정본은 기존 public.data_locations/storage_contributions. 새 catalog 테이블을 만들지 않는다. `inv.model_shard_locations`는 해당 기존 행에 대한 불변 FK 참조다. 참조된 catalog 행을 GC가 임의 삭제할 수 없다.
- public.models/model_versions 같은 lineage·사용자 metadata는 이 commitment를 참조할 수 있으나 두 번째 bytes 검증 정본을 만들지 않는다. Catalog/API/import·pin/repair/GC의 서비스는 Claude VF-CL-01/03/04 영역.
- lease/fence/epoch·Run·idempotency·outbox는 기존 커널 것을 재사용한다. 새 lease 체계 또는 가짜 Run 완료를 만들지 않는다.

## 계약

- ModelId는 기존 mdl ULID prefix. URI는 `inv://models/mdl_.../1.0.0/weights.bin`. 기존 `inv://models/name@1.0.0/path` 해석은 유지한다. 새 namespace의 latest/current/head는 거부.
- shard는 0부터 순서대로, offset에 빈틈/중복 없이 전체 totalBytes를 덮는 byte-range다. 현재 tensor 이름 기반 분할은 구현하지 않았다. contentHash는 순서대로 연결한 shard bytes 전체 SHA256이다.
- replica는 shardIndex/locationId/locationVersion/nodeId/state. 누락·중복·범위를 벗어난 index를 거부한다. 하나의 shard는 Node당 한 replica를 가리킨다.
- 최대 1024 shards/4096 replicas, manifest JSON 1 MiB, 전체 크기 1 TiB. 실제 검증 읽기 예산은 trusted worker configuration으로 별도 제한하며 기본 1 GiB. 파일 전체를 메모리에 적재하지 않고 1 MiB씩 읽는다.
- encryption/keyRef는 opaque svcred 참조만 허용. 현재 verifier는 plaintext만 구현되어 암호화 provider가 없으면 명시적으로 거부한다. runtimeCompatibility와 licensePolicy는 선언 metadata이며 승인이나 실제 runtime 지원의 증거가 아니다.

## Commit 경계

1. 검증된 Principal의 현재 프로젝트 grant·storage owner 연결과 Run 실행 상태, 정확한 active Lease/fence/epoch를 확인한다.
2. 요청 key와 body/fences를 기존 idempotency에 결속한다. 준비 단계에는 manifest가 존재하지 않는다.
3. trusted configuration의 RootBinding/ReadRoot로 실제 파일 전체 SHA256 및 전체 모델 hash를 검증한다. 사용자 body에서 root/path나 검증 권한을 만들지 않는다. 이 작업 동안 DB transaction을 잡지 않는다.
4. 다시 transaction에서 같은 key, 현재 grant/Run version/attempt/Lease/epoch/catalog/contribution version/Node 상태를 확인한다. 변경되거나 취소되었으면 commit하지 않는다.
5. manifest, FK 참조, outbox와 durable 응답을 한 transaction에 기록한다. 중복 key는 하나의 결과를 돌려주고 다른 key로 같은 model version을 덮지 못한다.
6. 이미 기록된 성공의 재응답은 새로운 읽기/실행/Lease 연장이 아니다. 취소 후에도 동일한 durable 결과를 읽을 수 있지만 현재 프로젝트 권한은 재검증한다.

## 아직 실행 가능한 모델이라는 뜻은 아니다

commit은 검증 시점의 bytes identity를 기록한다. mutable contributed 파일의 영구 불변성, 원격 Node 소유 증명, 서명 transport, runtime 설치, encryption provider, 실행 모드별 지원 또는 운영 배포를 인증하지 않는다. 응답은 항상 requiresExecutionRevalidation=true. 실제 실행 직전에는 replica/권한/permit/fence와 bytes를 다시 검증해야 한다. 파일 유실 때문에 manifest 자체를 지우지 않는다.

현재 이 서비스는 내부 trusted worker API이며 HTTP route를 열지 않았다. 브라우저가 임의 verifier나 filesystem root를 선택할 수 없다. VF-CX-03의 locality/placement와 VF-CX-04의 runtime/서명 transport에서 이 경계를 이어야 한다. unsupported collective/GPU/offload를 지원 완료로 표시하지 않는다.

## 검토 인계

Claude: 기존 DataLocation/version·lineage API와의 참조 계약, immutable retention/FK, 현재 권한 경합/두 phase의 TOCTOU, migration 0039와 함수 감사 정책을 독립 검토. Gemini: committed 표시를 executable/online으로 바꾸지 말고 requiresExecutionRevalidation 및 replica 미관측 상태를 표현. 다음 범위는 [[Codex VF 작업 현황]].
