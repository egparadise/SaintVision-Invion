---
doc_id: "NODE-STORAGE-RUNBOOK-001"
title: "Codex Node와 저장소 Adapter 실행 안내"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-21T21:00:00+09:00"
source_of_truth: "Git"
---

# Codex Node와 저장소 Adapter 실행 안내

이 페이지의 명령은 운영자가 실제 구성값을 넣어 실행할 안내이며 실행 완료 기록이 아니다. 계약은 [[Codex 저장 복원과 Node 실행 후속 계약]], 기존 실행/인증은 [[Codex Node mTLS 전달과 인증서 권한 계약]]을 따른다. owner Codex, reviewer Claude pending.

## 공지와 등록 후 관측

CI artifact에 `inv-discover`, `inv-node`, Python wheel이 들어간다. 공지는 미등록 후보만 만들며 admission은 하지 않는다. `POST /v1/discovery/announcements`는 기존 OIDC principal 또는 제한된 `discovery:announce` 기계 자격증명을 요구한다. 기계 자격증명은 발급 시 tenant와 안정적인 installation ID에 결속되고, `X-Inv-Tenant`는 기록된 tenant와 일치해야 한다. 만료는 15분이며 30초보다 잦은 공지는 거부된다. 자격증명은 후보를 하나만 만들거나 갱신할 수 있고, 실제 기기 정체를 증명하지 않는다.

### 운영자 임시 발급 절차

ADR-097에 따라 임시 발급자는 운영자 CLI이며 발급 권한은 운영자에게 남는다. DB 관리자는 지정된 운영자 로그인에만 `inv_discovery_issuer` 멤버십을 부여한다. 역할은 `NOLOGIN`이고 CLI는 접속 계정이 이 역할의 멤버인지 확인한 뒤 해당 역할로 전환한다. 일반 개발자 계정·프로젝트 멤버·호스트 로컬 접근만으로는 발급할 수 없다. 이 역할은 현재 모든 tenant의 발급·폐기 권한을 가지므로 승인된 소수 운영자만 받아야 한다.

운영자는 승인된 비밀 저장소/환경 주입으로 전용 DSN을 `INV_DISCOVERY_ISSUER_DSN`에 제공한다. DSN이나 비밀 값을 셸 명령, 저장소, 기록 문서 또는 로그에 직접 입력하지 않는다. 먼저 해당 tenant와 설치 ID로 사전 검사를 실행한다.

```bash
python tools/discovery_credential.py issue --tenant <tenant-uuid> --installation <stable-installation-id>
```

사전 검사가 통과하면 비공개·비녹화 대화형 터미널에서 `--apply`를 붙여 발급한다.

```bash
python tools/discovery_credential.py issue --tenant <tenant-uuid> --installation <stable-installation-id> --apply
```

CLI는 DB commit 뒤 bearer를 stdout에 한 번만 보여주며, 발급 레코드에는 SHA-256 digest만 저장한다. 화면 공유·터미널 녹화·로그 수집을 끄고 즉시 승인된 보호 전달 경로로 옮긴다. 원문을 티켓, 채팅, 셸 인자, 캡처 또는 보고서에 복사하지 않는다. CLI 출력의 비밀은 다시 조회할 수 없으므로 잃어버리면 같은 설치 ID로 재발급한다. 재발급은 이전 미폐기 자격증명을 먼저 폐기한다.

Node 서비스의 보호된 환경 주입 경로에 `INV_DISCOVERY_BEARER_TOKEN`을 설정하고 실제 endpoint, CA, 비밀이 아닌 tenant UUID와 installation ID를 지정한다. 새 자격증명은 `inv-discover`가 읽는 기존 환경변수 계약을 사용한다.

```bash
inv-discover --endpoint "$INV_DISCOVERY_ENDPOINT" --ca "$INV_DISCOVERY_CA_FILE" \
  --tenant "$INV_TENANT_ID" --instance "$INV_INSTALLATION_ID" --once
```

프로세스 환경에 `INV_DISCOVERY_BEARER_TOKEN`을 안전하게 설정해야 하며, 값 자체를 명령행에 쓰지 않는다. `--once`를 생략하면 30초 간격으로 공지한다. bootstrap token·인증서·Node role은 이 공지의 결과가 아니다. 기존 Node 실행 CLI의 명시적 tenant/node/epoch/profile/image/executable/state/public-key/mTLS 설정이 별도로 필요하다. 운영 등록 토큰과 CA 발급 경로도 별도 미완료다.

운영자는 후보가 표시되면 installation ID와 관측 정보를 물리 기기와 별도로 대조한 뒤 기존 admission 절차를 수행한다. 승인/거절 시 연결된 discovery 자격증명은 자동 폐기된다. 사고 대응 또는 계획된 폐기에는 발급 때 기록한 비밀이 아닌 credential ID를 사용한다.

```bash
python tools/discovery_credential.py revoke --tenant <tenant-uuid> --credential-id <dcr-credential-id> --apply
```

만료 자격증명은 API에서 자동 거부되며 만료 이력은 감사 목적으로 남는다. 재발급은 같은 tenant/installation의 이전 grant를 회전 폐기한다. DB 기록에는 원문 bearer가 없다.

> **운영 경계:** 코드와 임시 CLI/API 경로는 disposable PostgreSQL에서 검증됐다. 실제 조직 승인 전달 채널, 실제 `inv-discover` 바이너리/물리 Node 발급부터 공지, admission 뒤 one-time enrollment 교환과 mTLS까지는 이 문서 갱신에서 실행하지 않았다. 운영자가 승인된 보호 전달 채널을 확보하지 못하면 신규 Node 온보딩은 여전히 차단이다. 사용자 승인으로 운영자 CLI를 임시 선택했고, 보호된 tenant-operator API는 장기 결정으로 열려 있다. 상세 근거: [[2026-09-21_Discovery_기계자격증명_최소권한_계약제안_Codex]].

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
