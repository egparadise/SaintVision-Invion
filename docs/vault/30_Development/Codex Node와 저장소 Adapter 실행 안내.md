---
doc_id: "NODE-STORAGE-RUNBOOK-001"
title: "Codex Node와 저장소 Adapter 실행 안내"
version: "1.0.3"
status: "review"
author: "Codex"
updated: "2026-09-21T20:03:00+09:00"
source_of_truth: "Git"
---

# Codex Node와 저장소 Adapter 실행 안내

이 페이지의 명령은 운영자가 실제 구성값을 넣어 실행할 안내이며 실행 완료 기록이 아니다. 계약은 [[Codex 저장 복원과 Node 실행 후속 계약]], 기존 실행/인증은 [[Codex Node mTLS 전달과 인증서 권한 계약]]을 따른다. owner Codex, reviewer Claude pending.

## 공지와 등록 후 관측

CI artifact에 `inv-discover`, `inv-node`, Python wheel이 들어간다. 공지는 미등록 후보만 만들며 admission은 하지 않는다. `POST /v1/discovery/announcements`는 이제 인증 principal을 요구하고 `X-Inv-Tenant`가 그 principal의 tenant와 같아야 한다. Node Agent 실행 환경에 해당 tenant로 인증되는 `INV_DISCOVERY_BEARER_TOKEN`을 보안된 secret manager/service environment로 주입한다. 토큰을 CLI 인자, 저장소, 로그 또는 보고서에 넣지 않는다. 실제 endpoint, 해당 CA, 비밀이 아닌 tenant UUID와 안정적인 installation ID를 지정한다.

> **온보딩 차단 조건:** 위 문장은 자격증명 전달 위치만 설명하며 발급 절차를 제공하지 않는다. 저장소에는 미등록 Node용 discovery bearer 발급/배포 절차가 없고, 후보 admission의 one-time `bootstrapToken`은 최초 공지 뒤에 발급되므로 이를 대체하지 않는다. 유효한 tenant-mapped OIDC access token을 미리 주입하지 못한 새 Node는 후보로 나타나지 않는다. 권고된 operator-issued, installation-bound, 15분 bounded-refresh credential 절차도 제안 단계이며 구현되지 않았다. 발급자와 승인된 secret 전달 절차가 확정·구현되기 전까지 이 안내를 완결된 신규 Node bootstrap 절차로 사용하지 않는다. 임의 user token을 장기 기계 자격증명으로 취급하거나 익명 route를 임시 재개하지 않는다. 선택지와 합격 증거: [[2026-09-21_Discovery_기계자격증명_최소권한_계약제안_Codex]].

```bash
inv-discover --endpoint "$INV_DISCOVERY_ENDPOINT" --ca "$INV_DISCOVERY_CA_FILE" \
  --tenant "$INV_TENANT_ID" --instance "$INV_INSTALLATION_ID" --once
```

프로세스 환경에 `INV_DISCOVERY_BEARER_TOKEN`을 안전하게 설정해야 하며, 값 자체를 명령행에 쓰지 않는다. `--once`를 생략하면 30초 간격으로 공지한다. bootstrap token·인증서·Node role은 이 공지의 결과가 아니다. 기존 Node 실행 CLI의 명시적 tenant/node/epoch/profile/image/executable/state/public-key/mTLS 설정이 별도로 필요하다. 운영 등록 토큰과 CA 발급 경로도 별도 미완료다.

설치한 Python package의 `inv-observer-worker`는 `INV_OBSERVER_CONFIG` JSON 파일을 읽는다. 파일의 키는 `tenantId`, `tls`이고 tls는 `ca_file`, `certificate_file`, `key_file`이다. 현재 등록 Node CA와 CP client cert/key를 사용한다. `INV_RUNTIME_DSN`은 비owner·NOBYPASSRLS service role, `INV_RECOVERY_EPOCH`는 운영자가 검증한 현재 UUID다. 비밀은 Git/CLI 출력/보고서에 넣지 않는다.

```bash
inv-observer-worker --once
inv-delivery-worker --once
```

일회 실행이 통과한 뒤 service manager 연결 여부는 실제 환경에 맞춘다. 이 작업에서 운영 service 설치/자동 시작을 수행하지 않았다. observer는 `/v1/snapshots`, dispatcher는 기존 실행/관찰/취소 경로를 사용한다. liveness 성공은 GPU·Offer·작업 성공의 증거가 아니다.

## 파일 전송과 체크포인트 Adapter

Node 파일 공개는 기존 `inv-node --serve`에 `--objects <absolute private directory>`를 추가한 경우만 켜진다. 이 디렉터리는 Node service 계정 소유 0700, 파일명은 content SHA256, 단일 hardlink의 읽기 전용 regular file이어야 한다. 기존 사용자 폴더를 그대로 공개하지 않는다. 이 root의 내용은 해당 Node를 관리하는 현재 CP certificate에 허용되므로 catalog/project 권한이 확인된 파일만 넣는다.

CP Provider도 별도의 service-owned 0700 절대 디렉터리를 운영자가 지정한다. `LocalObjects(root)`와 `SnapshotStore(database, provider)`를 만들고 operator가 `inv.storage_budgets(tenant_id,project_id,quota_bytes)`를 먼저 구성한다. budget은 논리 객체 용량이며 staging/임시 파일의 물리 여유는 별도 확인한다. 기본값으로 사용자 디스크를 편입하지 않는다.

Claude business adapter의 호출 순서:

1. 현재 사용자 project 권한과 catalog의 immutable hash/size, Node 소속/허용 범위를 확인한다. `NodeTransfer(db, tls_client, snapshots).fetch(node, project_id, object_id, digest, size)`에 browser 경로나 임의 endpoint를 넘기지 않는다.
2. 새 전송은 UUID를 발급하고 재시도는 같은 ID/hash/size를 사용한다. trusted bytes를 직접 수신하는 adapter는 `begin → put_part(index, bytes) → finalize`를 사용한다. 상태는 `status`에서 읽는다.
3. running attempt의 현재 Lease proof가 있을 때 `checkpoint(tenant, run_id, step_id, object_id, proofs=...)`를 호출한다. 같은 attempt/step의 내용을 바꾸려면 기존 ID를 재사용하지 않는다.
4. 복원은 `restore(tenant, project, run, attempt, step)`의 검증된 bytes를 Workspace adapter가 다룬다. 현재 구현은 archive 추출·사용자 폴더 덮어쓰기·자동 프로세스 실행을 수행하지 않는다.
5. `collect`는 보존 정책이 허용한 미참조 객체에만 요청한다. checkpoint pin이 있으면 거절한다. crash 뒤 deleting을 다시 collect하면 안전하게 삭제를 마무리한다. pin 해제와 임시 orphan 자동 청소는 아직 제공하지 않는다.

## 용량과 샤드 업무 연결

인증 API `GET /v1/projects/{project}/capacity`는 `totalOffered`, `largestSingleNode`, `spareNow`에 `cpuMillis`, `memoryBytes`를 반환한다. `unmeasuredNodes`가 있으면 여유가 0으로 보수적으로 집계된다. GPU/디스크 수치는 미측정으로 별도 표시한다. 이 API는 project에 허용된 Node 집합의 read model이며 Claude의 별도 pool ID CRUD를 대체하지 않는다. pool 부분집합 Adapter와 예약 전 재검증을 연결해야 한다.

Claude의 placement를 실행하려면 각 shard에 별도 Run·승인·workload·Lease와 `ShardAdmission`을 구성한다. 승인 후 shard index/argv/resources를 수정하지 않는다. `ShardRuntime.enqueue(..., signing_key=..., splittable=True, communication="none")`는 모든 샤드를 검사한 뒤 원자 queue commit을 수행한다. signer는 service 내부의 기존 Ed25519 key 객체이며 private key를 plan/DB에 저장하지 않는다.

queue worker가 각 샤드를 실행하고 실제 stop receipt를 저장한다. `ShardRuntime.status`의 `allPhysicallyStopped`는 프로세스 종료 확인값이다. 계산 결과의 완전성, output reducer, parent Run succeeded/Evidence는 별도 구현해야 한다. MPI/NCCL·collective 소켓 통신이 필요한 계획은 현재 거절되며 transport profile·credential·분할/취소/복구 계약을 추가한 후에만 활성화할 수 있다.
