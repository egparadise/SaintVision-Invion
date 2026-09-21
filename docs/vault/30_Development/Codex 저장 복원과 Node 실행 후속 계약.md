---
doc_id: "STORAGE-NODE-CONTRACT-001"
title: "Codex 저장 복원과 Node 실행 후속 계약"
version: "1.1.1"
status: "review"
author: "Codex"
updated: "2026-09-21T19:47:00+09:00"
source_of_truth: "Git"
---

# Codex 저장 복원과 Node 실행 후속 계약

Task storage-node-runtime / OUT-04·05·06·07 / owner Codex / reviewer Claude(pending). Base `6c4f8a937c399d7e79bf49d2538e0bce53f24af4`, branch `agent/codex/storage-node-runtime`. GUIDE-001·GOV-AGENT-001·GOV-GIT-001·PLAN-BACKEND/DB/STORAGE-001 및 task registry v1.0.0, ADR-INDEX v1.7.0, agent-delivery/core-reliability v1.0.0을 읽었다. 시작 메타데이터는 `.work/storage-delivery.json`에 작성했으며 문서 작성 시각을 최초 shell 실행 시각으로 소급하지 않는다.

사용자 순서: 기존 Storage/Checkpoint 잔여 경계 구현·검증 후 Claude의 Control Plane 후속 Node/실행 연결. Claude 고정 SHA `6db4a5f376be68fcd687b2e1be8de649633b36e4`는 풀·지역성 계산/metadata이며 실행 권한 또는 실제 hash 측정의 대체물이 아니다.

## ADR-034: 실제 byte publication과 체크포인트 pin

- 기존 Storage 계획의 S3 object/DB metadata 분리는 유지한다. 본 구현은 명시적으로 설정한 Linux 단일 service 계정의 private 0700 directory Provider다. binary는 DB에 넣지 않는다. 16 MiB part, 64 MiB object의 제한된 복원 kernel이며 S3 presigned/50 GiB 제품 구현으로 표시하지 않는다.
- 객체 ID는 UUID이며 project+tenant로 조회한다. 사용자 경로/아카이브 추출은 받지 않는다. root inode 고정, independent descriptor flock, openat/O_NOFOLLOW, regular file·owner·nlink=1·읽기 전용 모드·실제 size/hash를 확인한다. 모든 participating process는 같은 Provider/lock 규칙을 사용한다. root 상위 경로와 service 계정 및 host 관리자는 신뢰 경계다.
- upload identity/hash/size 고정, part 재전송은 같은 bytes만 허용한다. 재시작 후 part metadata에서 재개한다. 모든 part의 실제 byte를 읽어 전체 SHA-256을 검사하고 fsync→rename→directory fsync 후 ready metadata를 commit한다. metadata 전에 중단되면 동일 객체를 재검증하여 finalize한다.
- project budget을 잠그고 uploading/ready/deleting의 **논리 object size**를 예약한다. 실제 staging+final 파일은 최대 약 2배와 crash 임시 파일 공간을 사용하므로 quota를 물리 디스크 여유 보장으로 해석하지 않는다. 임시 orphan/원본 사용자 파일 자동 스캔·삭제는 하지 않는다. 운영 disk headroom/유예 GC/S3 multipart는 후속이다.
- Run→fences→object 순서와 현재 running attempt를 검증한다. 파일 재해시, immutable checkpoint, checkpoint object pin, outbox를 함께 commit한다. 같은 step의 다른 내용은 거절한다. 복원은 해당 project의 고정 attempt/step pin을 조회해 실제 byte 재검증 후 trusted Workspace adapter에 반환한다. 자동 실행/Lease 재발급이 아니다.
- GC는 checkpoint pin을 검사하고 deleting tombstone commit→unlink+fsync→deleted commit 순서를 따른다. 중단 시 삭제를 재개한다. pin은 현재 무기한 보존한다. 만료·회수 API를 도입하기 전에는 체크포인트 객체를 해제하지 않는다.
- RunStore.complete의 기존 path 기반 helper는 이 Provider로 아직 연결되지 않았다. Node stop receipt가 Lease를 반환하는 시점과 application Evidence publication의 순서를 별도 조율해야 하며, checkpoint 복원 검증을 Run 성공으로 승격하지 않는다.

## 담당과 인계

| owner | 구현/후속 |
|---|---|
| Codex | 저장 무결성·pin/GC, Node mTLS 자동 관측·실측 snapshot·bounded transfer, 결정론적 배치·Lease 및 샤드 승인/실행 경계 |
| Claude | discovery 후보/풀 CRUD·업무 API, 확정 계약 adapter, 실행 기록, S02/S05/S07 차이 정리와 Codex 검토 회신; 본 계약 독립 검토 |
| Gemini | 후보 목록, totalOffered/largestSingleNode/spareNow 세 숫자, Explain와 실제 API 연결 |

Claude의 idle-first 계산은 ADR-005 가중치 Scheduler를 대신할 수 없다. float CPU core→integer cpuMillis, ram→memoryBytes, node active→online 등의 변환은 명시적이어야 한다. 한 capability snapshot만으로 다른 자원의 미측정 used를 0이라고 간주하거나 미래 snapshot을 여유로 인정하지 않는다. 계획 placement는 Lease/승인/Node 실행 증거가 없으면 실행된 것으로 표시하지 않는다. 신규 migration 번호는 각 branch 내 이력으로, Claude 0007과 Codex 0007/0008을 그대로 하나의 Alembic head로 합치지 않는다.

## 검증 상태

로컬 pytest 147 passed / 169 skipped / 실패 0. Linux private directory/PostgreSQL/Docker 검증은 동일 SHA CI에서 실행 후 History에 원본 Evidence로 기록한다. peer review, 실장비 5대·IdP/CA/DNS·Storage 제품 선택은 pending이다.

Storage 구현 `f4e33b958379e058196135d737539a3cee9d0a85`: Core #34386900927 / Docs #34386900905 success. 원본 [[storage-f4e33b9-tests.xml]], [[storage-f4e33b9-unit.jsonl]], [[storage-f4e33b9-provenance.json]]. Python 316/실패·오류·skip 0, Linux Go race 57 leaf cases. 초기 db7eae7의 migration 실패는 `%I`를 포함하는 SQL을 매개변수 보간 없이 실행하도록 수정한 후 재검증했다.

## ADR-035: 공지·실측 관측·전송·독립 샤드

- `inv-discover`는 명시적 HTTPS endpoint·CA·tenant·stable installation ID와 `INV_DISCOVERY_BEARER_TOKEN`으로 `/v1/discovery/announcements`에 공지한다. 서버는 인증 principal의 tenant와 header를 대조하며 다르면 DB 쓰기 전에 거부한다. 30초 주기 또는 `--once`, 5초 timeout, proxy/redirect 금지. OS/CPU/RAM은 미검증 자기 보고이며 GPU 미측정은 labels에 명시한다. bootstrap token 소비나 Node 인증서 발급·등록 승인·Offer 편입을 자동 수행하지 않는다. 실제 운영 credential 발급/주입은 운영자 설정이 필요하다.
- 등록된 `inv-node`의 `/v1/snapshots`는 기존 pinned mTLS, Node/tenant/epoch 및 일회 nonce를 사용한다. Linux `/proc/stat` 150ms CPU delta와 `/proc/meminfo` MemAvailable을 읽고 CPU millis/메모리 bytes로 반환한다. guest double-count를 피한다. 읽기 실패/불완전한 counter는 여유 0의 실측으로 꾸미지 않고 요청을 거절한다. 이 snapshot은 Offer·GPU/VRAM·격리 capability 증명이 아니다.
- `inv-observer-worker`는 명시적 tenant/DSN/epoch/TLS로 최대 5개 등록 채널을 5 worker에서 조회한다. 시작/끝 offline sweep, 5초 I/O와 5초 반복 대기, nonce/순서/clock/현재 인증서 검증 및 snapshot 저장을 묶는다. 60초 stale threshold는 sweep 주기와 함께 측정해야 하며 실장비 이탈 ≤60초 SLO를 아직 증명하지 않는다. Node 실종은 Lease 물리 반환 근거가 아니다.
- 인증된 `/v1/projects/{project}/capacity`는 project_nodes 허용 목록의 CPU/memory만 totalOffered/largestSingleNode/spareNow로 제공한다. 15초 이내 관측과 current channel·epoch, 활성 Lease를 검사한다. host busy와 Lease를 별도로 차감하여 보수적인 여유를 계산한다. 단일 노드 최대치는 자원 차원별 값으로 동시에 해당 조합을 만족하는 Node를 보장하지 않는다. 예약 시에는 기존 Scheduler/Lease 잠금을 재실행한다.
- `inv-node --objects <private-root>`를 명시한 경우에만 `/v1/objects/read`를 제공한다. SHA256 파일명·Linux openat/O_NOFOLLOW·private root·단일 link·읽기 전용 파일·전체 hash/size, 256KiB 응답 chunk와 Node 전송 슬롯 2개를 적용한다. host/service 계정은 신뢰 경계다. configured content root 전체를 현재 CP mTLS principal에 공개하므로 business adapter가 project별 catalog/읽기 권한을 검사해야 한다.
- `NodeTransfer.fetch`는 catalog hash/size, nonce와 chunk scope, canonical base64 및 chunk SHA를 검사하고 part commit/finalize transaction에서 channel 권한을 다시 확인한다. 실제 수신 bytes의 전체 hash가 맞아야 ready다. 중단 시 저장 완료된 16MiB part부터 재개하며 진행 part는 재수신한다. 측정 경로는 **Node→CP**이므로 Node→Node 링크 대역폭 또는 5노드 locality 실측으로 재사용하지 않는다. 다운로드는 metadata만 받아 ready로 바꾸지 않는다.
- `ShardRuntime.enqueue`는 명시적으로 분할 가능한 독립 workload 최대 16개, 서로 다른 Run/command 및 각 샤드의 사전 승인·Lease·현재 policy/runtime를 요구한다. plan→모든 Run→approval→모든 Node/resource→grant 잠금 후 기존 ToolGateway를 같은 transaction에서 호출한다. 하나라도 실패하면 전체 claim/queue/plan/outbox가 rollback된다. 기존 실행을 새 plan에 편입하지 않는다.
- 전달은 기존 durable queue/worker→mTLS→Go→격리 컨테이너를 사용한다. 같은 Node의 여러 샤드는 현재 단일 실행 슬롯에 따라 순차 실행된다. plan 재요청은 관측만 한다. `allPhysicallyStopped`는 각 샤드의 실제 receipt를 의미하며 계산 결과 성공이 아니다. 전 Node 동시 시작/gang scheduling이나 실패 자동 재실행을 약속하지 않는다.
- 샤드 간 MPI/NCCL/소켓 통신 및 output reducer는 미구현이며 `communication != none`을 거절한다. 현재 network=none 보안 계약을 암묵적으로 완화하지 않는다. S03-BE 위의 통신 격리·per-shard credential·새 서명 profile, 결과 교환/집계와 parent Run 성공의 Evidence가 후속이다.

## Claude 최신 변경의 조율 요청

고정 SHA 6db4a5f의 `pools.node_spare`는 node 하나의 어떤 capability라도 snapshot이 있으면 `measured=True`로 두고 나머지 used를 0으로 계산하며, latest snapshot 조회에 미래 시각 상한이 없다. `locality.estimate_transfer`도 link의 미래 시각을 제외하지 않는다. `mark_replica_ready`는 전달받은 hash와 catalog 문자열을 비교하므로 실제 byte를 검사한 trusted transfer adapter만 호출해야 한다. malformed/변조된 source bytes·stale/future 관측을 주입해 원 owner 테스트로 검증할 것을 요청한다. 이는 코드 검토 결과이며 Claude가 수신/수정/승인했다고 표시하지 않는다.

이 branch는 Claude의 별도 SQLAlchemy 모델과 HTTP 앱을 병합하지 않았다. Claude는 본 API/단위/상태/인증 계약을 업무 adapter에 연결하고 기존 검토 P1 heartbeat 인증·경합·backup hash의 수정 SHA를 제시한다. Gemini는 세 용량 숫자와 후보/배치 Explain 화면에 실제 응답을 연결한다. 실제 장비·Windows/GPU·S3·PKI/IdP·업무 UI·collective 통신·독립 검토는 미완료다.
