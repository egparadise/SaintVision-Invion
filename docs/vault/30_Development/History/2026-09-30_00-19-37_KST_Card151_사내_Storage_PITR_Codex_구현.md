---
doc_id: "HIST-20260930-CODEX-CARD151-001"
title: "Card 151 사내 Storage U6/G-20·PITR G-22 구현과 실측"
version: "1.0.0"
status: "review"
author: "Codex"
owner: "Codex"
reviewer: "Claude"
updated: "2026-09-30T00:19:37+09:00"
source_of_truth: "Git"
task: "CARD-151"
base_sha: "6fc0428b49f28379cb4da17830d92256b55c2eb2"
implementation_sha: "154719fcd35c5e02e92260b9a9e4cb9ed15b3e14"
pr: 248
---

# Card 151 사내 Storage U6/G-20·PITR G-22 구현과 실측

## 착수 계약

- base `6fc0428b49f28379cb4da17830d92256b55c2eb2`, branch `agent/codex/intranet-storage-pitr`, owner Codex, reviewer Claude.
- 비밀은 Git 밖 보호 directory에만 두고 값을 출력·문서·PR에 남기지 않았다. 로컬 Docker Desktop, 다른 프로젝트 container, 기존 Node container는 변경하지 않았다.
- 정본 경계는 [[외부 전제 인수 준비 패키지]] §2-0/§2-6/§2-8과 [[VF-CL-04 replica 복구와 PITR 운영 runbook]]을 따랐다.

## 구현

- `deploy/intranet/storage/provision-minio.sh`: MinIO exact digest, persistent data, non-root, read-only rootfs, `no-new-privileges`, capability 0, console port 미공개. 소유 label을 확인하고 교체 실패 시 이전 container를 원래 이름으로 복원한다.
- product/PITR bucket·service identity·policy를 분리했다. product는 `saintvision/product/*`·`saintvision-u6/*` object 연산만, PITR는 별도 bucket의 `pilot/*` object/list만 허용한다.
- `tools/render_intranet_object_store_config.py`: `providerId`, `endpoint`, `bucket`, `region`, `credentialFile`, `prefix` exact six-key block을 보호 `api.json`에 exclusive-write하고 legacy key·unknown key·자격증이 든 URL·비보호 경로를 거부한다.
- `deploy/intranet/storage/rehearse-pilot-pitr.sh`: source mutation 전 physical WAL receiver 생존을 확인하고, `pg_basebackup`·`pg_receivewal`·MinIO upload/download digest·retention dry-run·`recovery_target_time` 복원·before/after marker를 결속한다.
- 운영 절차와 판정 경계는 [[사내 MinIO ObjectStore와 PITR 예행 runbook]]에 고정했다.

## 실측

| 항목 | 결과 | 판정 |
|---|---|---|
| MinIO image/runtime | exact digest, user `1000:1000`, rootfs read-only, cap drop ALL, 지속 data, ready | PASS |
| U6 byte roundtrip | put/get/body SHA-256/metadata SHA-256/delete/cleanup 6/6 true | `ci-candidate` PASS |
| 권한 음성 | product credential의 외부 prefix PUT 403, PITR credential의 product bucket PUT 403 | PASS |
| TLS | Card 150 사내 CA server certificate 입력 미도착 | BLOCKED_EXTERNAL |
| source PITR readiness | `archive_mode=off`, archive command disabled, `pitrVerified=false` | absent |
| physical replication | SSH reverse tunnel 이후 source Docker gateway에 replication HBA rule이 없어 거부 | BLOCKED_EXTERNAL |
| target-time restore/RPO/RTO | source mutation 전 중단, restore 미시도, 수치 `null` | NOT_OBSERVED |
| cleanup | 카드 전용 DB 0, 소유 container 0, tunnel 종료 | PASS |

HTTP 실측을 운영 U6 PASS로 올리지 않았고, 복원을 실행하지 못한 상태에서 RPO/RTO를 만들지 않았다. blocked report는 `sourceMutated=false`, `restoreAttempted=false`, RPO/RTO `null`, reason `physical-replication-hba-rejected`다.

## 검증

- focused PG-free: `11 passed`, exit 0.
- remote 두 shell script `sh -n`: exit 0.
- `python tools/check_docs.py`: exit 0.
- `python tools/check_doc_path_citations.py --ratchet --base-ref origin/integration/all-agents-unified`: exit 0.
- `python tools/check_contract_bindings.py`: exit 0.
- `python tools/check_frontend_integrity.py`: exit 0.
- `python tools/check_ontology.py`: exit 0.
- `git diff --check`: exit 0.
- hosted PR #248: Docs success; Backend·desktop-browser는 본 기록 시점 진행 중, Core/ObjectStore opt-in lane은 label 미지정으로 skip.

## 다음 첫 행동

1. Card 150 CA가 제공한 MinIO server cert/key/CA-chain으로 service를 TLS 전환하고 operational roundtrip+attestation을 새로 만든다.
2. source 운영자가 physical replication HBA rule과 reload를 명시 승인·적용한 뒤 runner를 재실행해 MinIO에서 다시 받은 byte로 target-time restore, RPO, RTO를 관측한다.
3. Claude가 PR #248을 독립 검토한다. 두 외부 경계가 닫히기 전에는 self-close·merge하지 않는다.
