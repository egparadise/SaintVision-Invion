---
doc_id: "PROPOSAL-CLAUDE-PITR-001"
title: "운영 compose PITR 변경안·격리 검증·영향 (AC-12 RPO 준비)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-19T03:30:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "pitr", "rpo", "ac-12", "operational-readiness", "proposal"]
---

# 운영 compose PITR 변경안·격리 검증·영향 (AC-12 RPO 준비)

`archive_mode=off`를 켜는 것은 운영 배포 결정(사용자 몫)이다. 그 전에 외부 권한 없이 준비할 수 있는 것을 만들어 둔다: **적용 준비된 변경안**(`docker-compose.pitr.yml`, opt-in override)과 **그 변경이 gate를 올바로 이동시키는지의 격리 검증**, 그리고 **영향 정리**(WAL 보관 용량·아카이브 저장소). 사용자는 결정만 하면 바로 적용할 수 있다.

정직 원칙(이번 세션 반복 패턴): **설정은 필요조건이지 RPO 달성의 증거가 아니다.** 도구도 그렇게 만들어져 있다 — `recovery_drill.rpo_bound_from`은 설정만으로는 bound를 항상 `None`으로 두고, `_meets_operational_rpo`는 `operationalRpoVerified is True`와 유한 bound를 요구한다. 따라서 이 변경안은 AC-12를 **충족시키지 않고**, 충족의 **전제조건**을 갖추며, 남은 증거(복구 drill)를 명시한다.

## 현재 상태 (실측)

- `docker-compose.prod.yml`의 postgres는 `postgres:16-alpine` 기본(command 없음): `archive_mode=off`, `archive_command` 없음, `archive_timeout=0`, `data_checksums=off`(initdb 기본). `docker-compose.workspace.yml`은 control-plane 볼륨만 추가하고 postgres 설정 없음.
- 즉 **운영 배포 정의에 시점 복구 설정이 전혀 없다.** `pitr_readiness` verdict = `absent`, `recovery_drill` archivingConfigured = False. **AC-12 RPO 목표 미달성**(CL-07 4b09dfc 기록과 일치).

## 변경안 — `docker-compose.pitr.yml` (opt-in override, Tier A 로컬 아카이브)

`docker compose -f docker-compose.prod.yml -f docker-compose.pitr.yml up -d`로만 활성. postgres에 다음을 준다: `archive_mode=on`, `archive_command`(로컬 `/wal_archive`에 비덮어쓰기 cp), `archive_timeout=300`, `wal_level=replica`, `wal_keep_size=1024`, `full_page_writes=on`, 그리고 신규 클러스터용 `POSTGRES_INITDB_ARGS=--data-checksums`. 외부 `wal_archive` 볼륨(운영자가 postgres 런타임 uid 소유로 사전 provision — repo의 server_config/workspace_data 패턴)을 마운트. `archive_mode`는 postmaster 설정이라 적용 시 **postgres 재시작**.

## 격리 검증 (도구를 순수 함수로 — docker/PG 불필요, 결정적)

`tools/pitr_readiness.assess`와 `tools/recovery_drill.rpo_bound_from`을, 현재/제안 설정이 만드는 settings dict로 직접 호출:

| 설정 | pitr verdict | archivingConfigured | operational RPO bound |
|---|---|---|---|
| 현재(off) | `absent` | False | None |
| 제안(on, 실 archive_command) | `possible` | True | None |
| 제안이되 no-op(`/bin/true`) | `absent` | False | None |

- **확인**: 변경안이 필요조건 gate를 `absent → possible`, `configured False → True`로 이동시킨다. no-op archive_command는 configured로 위장되지 않는다(guard 작동).
- **정직 기록**: 두 경우 모두 operational RPO **bound는 None** — 설정만으로는 확립되지 않는다. 이 검증은 "설정이 gate를 올바로 움직임"을 증명하지, "RPO가 달성됨"을 증명하지 않는다.
- 이 스크립트는 표준 라이브러리+도구만 쓰므로 이 환경에서 그대로 실행해 통과했다. probe 서버 실행/전체 복구 drill은 아래 참조.

## 수용 경로 — 3단계, 그리고 gate의 구조적 사실 (소스 재확인 후 정정)

지난 판(v1.0.0)에서 나는 "활성 후 복구 drill 증거가 나오면 `--require-operational-rpo`로 재확인"이라고 적었다. **이는 부정확했다.** `tools/recovery_drill.py`를 다시 읽어 잡았다(이번 세션 반복 패턴 그대로 — 통과 경로가 실은 닫혀 있었다):

- `_recovery_capability`가 `operationalRpoVerified: False`·`operationalRpoBoundSeconds: None`을 설정하고, 이후 **어디서도 True/수치로 바뀌지 않는다**(492행에서만 대입, recoveryCapability는 772행에서 한 번만 설정, 1094행은 `operationalRecoveryVerified: False` 하드코딩).
- `_meets_operational_rpo`는 `operationalRpoVerified is True`와 유한 bound를 요구하므로, **수치 목표에 대해 항상 False**를 반환한다. `--require-operational-rpo` help도 명시한다: "current configuration-only observations cannot satisfy this gate".
- **결론**: `--require-operational-rpo <N>`는 **활성·drill 성공 후에도 구조적으로 통과하지 못한다(fail-closed)**. 단일 drill의 간격을 운영 보장으로 승격하지 않겠다는 CL-07 통찰이 도구에 그대로 박혀 있다.

따라서 정확한 3단계는 이렇다:

1. **설정 활성**(위 override) — 사용자 운영 결정. 활성 후 `pitr_readiness --dsn-env <ENV> --json` verdict = `possible` 확인(필요조건 충족). *이것만으로 RPO 달성 아님.*
2. **기능 복구 drill (활성 후, 실제로 달성 가능)** — 아래 runbook. `recovery_drill`이 실제 backup을 복원하고 **무결성·fencing·app/kernel role 읽기**를 검증하며 `measuredRpoSeconds`(이 복원의 데이터 손실 간격)·`measuredRtoSeconds`를 기록한다. `_passed`가 True면 **PITR이 실제로 작동함과 측정된 간격**이 증거로 남는다. **이것이 활성 후 얻을 수 있는 실질 증거다.** (backup 경로는 **Linux 전용**·실 디스크 필요 → 이 Windows 개발 환경 실행 불가, 운영/CI 몫.)
3. **operational-RPO 인증 (현재 gap)** — `--require-operational-rpo`가 통과하려면 도구에 `operationalRpoVerified=True`와 수치 bound를 세우는 **인증 경로**(연속 아카이브 지연/실패 모니터링, 보관·연속성 검증, off-site 내구성)가 추가돼야 한다. 이는 **별도 작업 항목**이며 지금은 존재하지 않는다(§인증 gap).

### 인수 runbook — 기능 복구 drill (활성 후, Linux 운영/CI)

```
INV_RECOVERY_SOURCE_DSN=<운영 DB libpq DSN(읽기)>          # 복원 대상 원본
INV_RECOVERY_ADMIN_DSN=<CREATE DATABASE 가능한 DSN>         # 복원 DB 생성
python tools/recovery_drill.py \
  --from-backup <이전에 뜬 backup 파일>  \                  # 실제 복구 경로(dump-then-restore 아님)
  --backup-taken-at <backup 시점 ISO> \
  --app-role inv_app --kernel-role inv_kernel \
  --tenant <t> --user <who> --record-dsn <기록 DSN> \        # drill 행 기록(옵션)
  --json
```

- exit 0 + `measuredRpoSeconds`/`measuredRtoSeconds` + `integrityVerified`/`fencingVerified` = **기능 PITR 성공 증거**.
- `--require-operational-rpo <N>`을 붙이면 위 §3 이유로 현재는 통과하지 못한다(의도된 fail-closed). 붙이지 않고 기능 drill 증거를 남기는 것이 활성 직후의 현실적 인수 단계다.
- 목표 시점(point-in-time) 복원을 시험하려면 §override가 켠 **연속 아카이브 WAL**이 있어야 하며(그래서 활성이 선행), backup 시점 이후 목표 시각까지 replay한다.

### operational-RPO 인증 gap (별도 작업 항목)

`--require-operational-rpo`를 언젠가 통과 가능하게 하려면 `recovery_drill`에 다음을 세우는 인증 로직이 필요하다: (a) 연속 아카이브의 **지연·실패 모니터링**(마지막 성공 아카이브와 현재 WAL 위치 간격), (b) **보관·연속성 검증**(가장 오래된 유지 backup부터 현재까지 WAL 끊김 없음), (c) **off-site 내구성** 확인. 이것이 서면 `operationalRpoVerified=True`와 수치 bound가 정당하게 선다. 이는 관측·운영 영역(내 owner 후보)이나 설계 결정이 선행이므로 지금은 gap으로 남긴다 — 지어내지 않는다.

## 영향 정리 (사용자 판단 근거)

- **WAL 보관 용량**: `archive_timeout=300`은 idle에도 300초마다 16MB 세그먼트를 강제 전환·아카이브 → **최소 ~192MB/시간, ~4.6GB/일(idle floor)**, 부하 시 더 큼. `archive_timeout=600`으로 올리면 idle 오버헤드 절반(900s 목표엔 여전히 여유). `wal_keep_size=1024`(1GB)는 pg_wal에 버퍼를 남겨 짧은 아카이브 지연이 미아카이브 세그먼트를 즉시 재활용하지 않게 한다.
- **아카이브 대상 저장소 요구**: 아카이브는 연속 증가하므로 **보관/정리 정책 필수** — 유지하는 가장 오래된 base backup보다 오래된 WAL은 삭제(pgbackrest는 자동, 로컬 cp는 수동 cron 필요). 용량 = (base backup 주기 동안의 WAL 생성량) × (보관하는 backup 세대 수) + 여유. Tier A 로컬은 같은 호스트라 호스트 손실 시 data+archive 동시 손실(DR 아님) — RPO를 호스트 손실까지 보장하려면 Tier B 필요.
- **data_checksums**: initdb 시점만 설정 가능. **신규 클러스터**는 override의 `POSTGRES_INITDB_ARGS=--data-checksums`로 켜짐(빈 postgres_data일 때만). **기존 클러스터**는 offline `pg_checksums --enable`(정지→실행→재시작, 다운타임)이 필요. RPO 항목은 아니나, 복구 drill의 원본이 조용히 손상돼 양쪽에서 같게 읽히는 것(CL-07에서 지적)을 막아 drill 증거의 신뢰를 높인다.
- **재시작 다운타임**: `archive_mode` 변경은 postgres 재시작(짧은 downtime) 동반.
- **볼륨 소유권 전제**: Tier A는 `wal_archive`를 postgres 런타임 uid 소유로 사전 provision해야 archive_command가 쓸 수 있다(안 하면 pg_wal 적체→디스크 full).

## Tier B (권장, 내구성 있는 수용) — 이미 있는 minio로 (구체 설계)

compose에 minio(S3 호환)가 이미 있다(`saintvision-minio`, `MINIO_ROOT_*`). WAL·base backup을 minio 버킷으로 보내면 **off-host 내구성 + 자동 보관 정리**를 얻어 호스트 손실까지 RPO를 보장한다. `archive_command`는 postgres 컨테이너 안에서 실행되므로 도구가 그 이미지에 있어야 한다 — **wal-g**(단일 바이너리, pgbackrest보다 단순)를 권장한다.

- **커스텀 이미지** (lane 후 materialize·빌드): `FROM postgres:16-alpine` + wal-g 바이너리 복사. (빌드·리허설은 docker 필요 → 지금은 설계만.)
- **compose override env** (minio를 S3로): `AWS_ENDPOINT=http://minio:9000`, `AWS_S3_FORCE_PATH_STYLE=true`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`(minio 자격증명 — `MINIO_ROOT_*` 재사용 또는 전용 키 권장), `WALG_S3_PREFIX=s3://<bucket>/pg`.
- **아카이브**: `-c archive_command='wal-g wal-push %p'`(Tier A의 로컬 cp를 대체). `archive_timeout`·`wal_level`은 Tier A와 동일.
- **base backup(주기)**: `wal-g backup-push "$PGDATA"`를 주기 실행(cron/systemd timer/주기 job). 주기가 RPO 하한과 아카이브 용량을 함께 결정.
- **보관 정리(자동)**: `wal-g delete retain FULL <N>` — 유지할 full backup 세대 수 N. 로컬 cp의 수동 cron 불필요.
- **복원(기능 drill/실복구)**: `wal-g backup-fetch "$PGDATA" LATEST` 후 `restore_command='wal-g wal-fetch %f %p'` + `recovery_target_time`으로 목표 시점 replay.
- **선행 결정(운영)**: (a) minio 버킷 생성, (b) 전용 S3 키 vs `MINIO_ROOT_*` 재사용, (c) base backup 주기·보관 세대 수. 자격증명·엔드포인트는 운영 결정이라 파일에 박지 않고 env로 주입.

리허설(커스텀 이미지 빌드 + minio로 push/fetch + `recovery_drill` 기능 drill)은 **PostgreSQL/도구 컨테이너가 필요**하므로 image lane 판별이 끝난 뒤 수행한다(사용자 신호 대기). 그때 Dockerfile·override를 실제 파일로 만들고 검증한다.

## 사용자 결정 항목 (이 준비가 대기하는 것)

1. 연속 아카이빙 활성 여부(예 시 override 적용).
2. 아카이브 대상: Tier A 로컬 볼륨 vs Tier B minio(권장).
3. `archive_timeout` 값(300 vs 600) 및 base backup 주기 → 실제 RPO/용량 결정.
4. 아카이브 보관/정리 정책과 용량 배정.
5. `data_checksums`: 신규 클러스터에 켤지(기존은 다운타임 감수 여부).
6. 활성 후 **기능 복구 drill**(운영/CI, Linux)으로 PITR 작동 + measuredRpo 증거 생성. (`--require-operational-rpo`는 현재 구조적 fail-closed — 그 통과는 §인증 gap의 별도 작업이 선행.)

## 다음 담당

- 준비 완료(변경안 파일·격리 gate 검증·영향)는 Claude. **활성·아카이브 대상·주기·복구 drill 실행은 사용자/운영**. 활성 후 복구 drill 증거가 나오면 Claude가 `--require-operational-rpo`로 재확인. 이 항목은 [[2026-09-19_Claude영역_검증상태지도]] §3 운영 인수 트랙.
