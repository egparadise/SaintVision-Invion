---
doc_id: "HIST-20260930-CODEX-CARD151-001"
title: "Card 151 사내 Storage U6/G-20·PITR G-22 구현과 실측"
version: "1.2.1"
status: "review"
author: "Codex"
owner: "Codex"
reviewer: "Claude"
updated: "2026-09-30T01:06:00+09:00"
source_of_truth: "Git"
task: "CARD-151"
base_sha: "6fc0428b49f28379cb4da17830d92256b55c2eb2"
implementation_sha: "0a768892e506059a61092ff3b83a7ebba1db2d82"
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
- PITR 전송 자격과 source PostgreSQL 자격은 각각 보호 파일 하나만 read-only mount하고 컨테이너 내부에서 읽는다. host process argument와 Docker `Config.Env`에는 자격을 남기지 않으며 broader config tree를 mount하지 않는다.
- 운영 절차와 판정 경계는 [[사내 MinIO ObjectStore와 PITR 예행 runbook]]에 고정했다.

## 실측

| 항목 | 결과 | 판정 |
|---|---|---|
| MinIO image/runtime | exact digest, user `1000:1000`, rootfs read-only, cap drop ALL, 지속 data, ready | PASS |
| U6 byte roundtrip | 사내 CA HTTPS에서 put/get/body SHA-256/metadata SHA-256/delete/cleanup 6/6 true | operational PASS |
| 권한 음성 | product→PITR bucket, PITR→product bucket PUT 각각 403 | PASS |
| TLS | `objects.sv.lan`·`.210` SAN, serverAuth, CA=false, intermediate 서명·key 일치; HTTPS ready | PASS |
| source PITR readiness | `archive_mode=off`, archive command disabled, `pitrVerified=false` | absent |
| physical replication | SSH reverse tunnel 이후 source Docker gateway에 replication HBA rule이 없어 거부 | BLOCKED_EXTERNAL |
| target-time restore/RPO/RTO | source mutation 전 중단, restore 미시도, 수치 `null` | NOT_OBSERVED |
| cleanup | 카드 전용 DB 0, 소유 container 0, tunnel 종료 | PASS |

초기 HTTP 실측은 운영 U6 PASS로 올리지 않았다. Card 150 CA 발급기(PR #249)로 MinIO 전용 leaf를 발급한 뒤 strict six-key config endpoint를 HTTPS로 교체했고, reachable head `c075e669ada2205f234a297c940ae97be87434a0`에서 operational evidence와 별도 attestation의 SHA·시각을 exact 결속했다.

첫 TLS 후보에서 image가 환경변수만으로 cert directory를 읽지 않아 HTTP로 뜨는 문제와, 두 번째 후보에서 self-bootstrap이 loopback SAN/CA trust를 만족하지 못하는 문제를 각각 실제 rollback으로 확인했다. 명시적 `--certs-dir`, bind IP, `SSL_CERT_FILE`, 3초 bounded readiness를 추가했다. 진단 중 host `ps`에 root alias가 한 번 노출되어 해당 root 자격을 즉시 원자 회전했고, 후속 구현은 모든 bootstrap 자격을 stdin으로 전달해 host process argument와 container config에 남지 않게 했다. service/PITR 자격은 노출되지 않았다.

canonical preflight는 storage check만 PASS했고 전체는 PASS 1/FAIL 2/BLOCKED 6, `acceptanceAssessed=false`였다. operator/session token, CP hostname/HTTPS, inventory의 71개 사용자 결정 값이 없으므로 합성하지 않았다. 복원을 실행하지 못한 상태에서 RPO/RTO를 만들지 않았고, blocked report는 `sourceMutated=false`, `restoreAttempted=false`, RPO/RTO `null`, reason `physical-replication-hba-rejected`다.

## 검증

- focused PG-free: `11 passed`, exit 0. TLS bootstrap 보강 단일 파일은 추가 실행마다 `4 passed`였다.
- remote 두 shell script `sh -n`: exit 0.
- `python tools/check_docs.py`: exit 0.
- `python tools/check_doc_path_citations.py --ratchet --base-ref origin/integration/all-agents-unified`: exit 0.
- `python tools/check_contract_bindings.py`: exit 0.
- `python tools/check_frontend_integrity.py`: exit 0.
- `python tools/check_ontology.py`: exit 0.
- `git diff --check`: exit 0.
- hosted PR #248 evidence head `c075e669`: Docs run `36592638603` success, Core의 `s01-storage-roundtrip` job도 success. 보안 후속 head `f420530a`의 Docs run `36594438509`도 success이며 Backend·desktop-browser는 본 기록 시점 진행 중이다.
- PITR·source DB 자격 비노출 후속: `tests/test_intranet_storage_bundle.py` 4 passed, local·remote shell syntax와 `git diff --check` exit 0.
- canonical `tools/s01_readiness_preflight.py`: exit 1, 전체 FAIL(PASS 1/FAIL 2/BLOCKED 6), storage check만 `storage-operational-evidence-valid`; 미입력을 합성하지 않은 기대된 부분 판정이다.
- focused 첫 재실행은 `PYTHONPATH`에서 `tools` 누락으로 두 모듈 collection error였고 통과로 세지 않았다. 정정한 `tools;src;services/control-plane/src` 환경에서 `11 passed`를 다시 확보했다. citation gate도 PR #249 전용 경로를 현 branch 실재 경로로 오인한 새 인용 1건을 제거한 뒤 PASS했다.
- `python tools/sync_obsidian.py --check`: exit 3, 기존 unmanaged collision 15건(11 no-baseline, 4 both-diverged). 파일은 쓰지 않았고 `--apply`는 실행하지 않았다.

## 다음 첫 행동

1. source 운영자가 physical replication HBA rule과 reload를 명시 승인·적용한 뒤 runner를 재실행해 MinIO에서 다시 받은 byte로 target-time restore, RPO, RTO를 관측한다.
2. Card 152가 CP hostname/HTTPS와 operator/session token, 완성 inventory를 제공하면 canonical preflight를 재실행한다.
3. Claude가 PR #248을 독립 검토한다. PITR 외부 경계와 S01 나머지 입력이 닫히기 전에는 self-close·merge하지 않는다.
