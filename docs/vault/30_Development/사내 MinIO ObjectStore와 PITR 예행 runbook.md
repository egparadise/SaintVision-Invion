---
doc_id: "OPS-INTRANET-STORAGE-PITR-001"
title: "사내 MinIO ObjectStore와 PITR 예행 runbook"
version: "1.0.0"
status: "review"
owner: "Codex"
reviewer: "Claude"
author: "Codex"
updated: "2026-09-30"
task: "CARD-151"
source_of_truth: "Git"
tags: ["intranet", "object-store", "minio", "pitr", "u6", "g-20", "g-22"]
---

# 사내 MinIO ObjectStore와 PITR 예행 runbook

## 1. 판정 경계

이 절차는 사내 ObjectStore 입력 U6/G-20과 물리 PITR 예행 G-22를 준비한다. HTTP MinIO 왕복은 사전 배선 확인일 뿐 운영 PASS가 아니다. U6 PASS는 사내 CA로 검증한 HTTPS endpoint에서 `tools/verify_storage_roundtrip.py --target-kind operational`이 여섯 check를 모두 통과하고, 같은 `codeSha`·`observedAt`의 별도 attestation을 `tools/s01_readiness_preflight.py`가 받아야 한다.

PITR도 설정 관측과 실제 복원을 분리한다. `tools/pitr_readiness.py`의 `possible`은 복구 증거가 아니며, `tools/pitr_archive_retention.py`는 파일시스템 보존 계획기다. 이 카드의 runner는 `pg_basebackup`·연속 `pg_receivewal`·MinIO upload/download byte digest·`recovery_target_time` 격리 복원을 모두 실행할 때만 RPO/RTO를 낸다. source의 지속 archive 설정이 꺼져 있으면 runner 완료 뒤에도 상시 PITR readiness를 주장하지 않는다.

## 2. 비밀과 권한

- root, 제품 service, PITR service credential은 Git 밖 `.work/intranet/`과 대상 노드의 mode 0700 config directory에만 둔다. 명령·PR·문서·Evidence에는 값이 없다.
- `tools/generate_intranet_storage_secrets.py --directory .work/intranet`은 PITR credential 두 파일을 exclusive create하며 기존 파일을 덮어쓰지 않는다.
- 제품 policy는 `saintvision/product/*`와 verifier 전용 `saintvision-u6/*`의 get/put/delete만 허용한다. bucket list와 PITR bucket 접근은 없다.
- PITR policy는 별도 bucket의 `pilot/*` object와 그 prefix의 list만 허용한다. 제품 bucket 접근은 없다.
- `deploy/intranet/storage/provision-minio.sh`는 기존 컨테이너를 이름만으로 제거하지 않는다. owner/task label이 모두 일치할 때만 자기 컨테이너를 교체하고, 기존 Node 및 다른 프로젝트 컨테이너를 열거·수정하지 않는다.

## 3. MinIO 배포

운영자가 보호 디렉터리에 다음 파일을 둔다.

```text
minio-root.env
minio-service-user.env
pitr-service-user.env
product-policy.json
pitr-policy.json
provision-minio.sh
```

TLS 전 사전 배선은 내부 HTTP로 기동할 수 있으나 `targetKind=ci-candidate`만 허용한다. 운영 전환 때 `minio-certs/public.crt`, `minio-certs/private.key`, `minio-certs/ca-chain.pem` 세 파일을 모두 제공한다. 일부만 있으면 기동을 거부한다. private key는 0600이어야 한다.

```sh
~/.config/saintvision-intranet/provision-minio.sh
```

서버 image와 PostgreSQL client image는 script의 digest로 고정한다. MinIO는 비루트 UID, read-only root filesystem, `no-new-privileges`, capability 0으로 실행하고 data directory만 지속 mount한다. Console port는 publish하지 않는다.

## 4. Control Plane 여섯 key

`tools/render_intranet_object_store_config.py`로 기존 보호 `api.json`에 다음 exact block을 넣는다. `objectStoreEndpoint` legacy key와 동시 사용하지 않는다.

```json
{
  "providerId": "s3-compatible-intranet-v1",
  "endpoint": "https://<storage-host>:9000",
  "bucket": "saintvision-objects",
  "region": "us-east-1",
  "credentialFile": "/run/saintvision/object-store.json",
  "prefix": "saintvision/product"
}
```

API와 worker가 같은 검증 완료 config volume을 read-only mount하고 credential file은 0600 regular single-link file이어야 한다. live process 재시작과 drain은 별도 운영 단계이며, HTTP 사전 설정을 운영 설정으로 승격하지 않는다.

## 5. U6 Evidence

보호 환경에서 endpoint, bucket, region, credential을 주입하되 값을 출력하지 않는다.

```sh
python tools/verify_storage_roundtrip.py \
  --target-kind operational \
  --output dist/s01-storage-roundtrip.json \
  --junit dist/s01-storage-roundtrip.xml
```

attestation은 `executedBy`, `configurationProfile`, `runbookRevision`, `codeSha`, `observedAt` exact set이며 evidence와 마지막 두 값을 일치시킨다. canonical S01 실행은 [[외부 전제 인수 준비 패키지]] §2-0 명령을 그대로 사용한다.

## 6. 물리 PITR 예행

`deploy/intranet/storage/rehearse-pilot-pitr.sh`는 다음 순서다.

1. source에 mutation하기 전에 physical replication 연결과 WAL receiver 생존을 확인한다.
2. 카드 전용 disposable database를 만든다.
3. `pg_basebackup -Fp -X stream`과 synchronous `pg_receivewal`을 실행한다.
4. before marker, UTC target time, after marker를 순서대로 commit하고 WAL switch 완료를 확인한다.
5. `tools/pitr_archive_retention.py` 7일 dry-run을 실행한다.
6. base backup·WAL을 별도 PITR credential로 MinIO에 업로드하고 새 directory로 다시 내려받아 전 파일 digest를 비교한다.
7. 내려받은 bytes만 사용해 network-none 격리 PostgreSQL을 `recovery_target_time`까지 복원한다.
8. before 존재, after 부재, promotion을 확인한 뒤 RTO와 target 이전 마지막 복원 marker 기준 RPO를 기록한다.
9. source disposable database와 owner/run label이 일치하는 자기 컨테이너만 정리한다.

source가 Docker bridge 뒤에 있으면 physical replication HBA가 실제 client source를 허용해야 한다. 필요한 rule과 reload는 source 운영자가 별도 승인·적용한다. runner는 이 경계가 없으면 source database 생성 전에 중단한다. `archive_mode=off` source에 bounded receiver를 붙인 1회 예행은 상시 archive 구성이 아니다.

## 7. 현재 관측과 되돌리기

| 항목 | 현재 관측 | 판정 |
|---|---|---|
| MinIO 고정 image·지속 data·비루트 경계 | 실제 사내 storage node에서 ready | 준비됨 |
| 제품 service 왕복 | HTTP에서 put/get/body hash/metadata hash/delete/cleanup 6/6 | `ci-candidate` PASS, 운영 PASS 아님 |
| 권한 음성 | 제품 credential·PITR credential의 교차 prefix PUT 모두 403 | PASS |
| TLS | 사내 CA server certificate 입력 대기 | BLOCKED_EXTERNAL |
| pilot PostgreSQL 설정 | `archive_mode=off`, archive command disabled | 상시 PITR absent |
| 물리 replication | Docker gateway source에 replication HBA 없음 | source mutation 전 BLOCKED_EXTERNAL |
| 실제 target-time restore·RPO/RTO | 실행 전 차단 | NOT_OBSERVED |

되돌릴 때는 새 dispatch를 중지하고 product object 사용 여부를 확인한 뒤, owner label이 일치하는 MinIO 컨테이너만 중지한다. data directory, bucket, credential, PITR report는 자동 삭제하지 않는다. credential 회수는 scoped user를 disable한 뒤 별도 승인으로 수행한다. `docker system prune`, volume 삭제, 다른 컨테이너 조작은 이 runbook 범위 밖이다.
