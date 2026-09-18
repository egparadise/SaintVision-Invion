---
doc_id: "PROPOSAL-CLAUDE-PITR-001"
title: "운영 compose PITR 변경안·격리 검증·영향 (AC-12 RPO 준비)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-19T02:00:00+09:00"
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

## 완전 수용 경로 (enablement 후, 내 권한 밖)

1. **설정 활성**(위 override) — 사용자 운영 결정. 활성 후 `pitr_readiness --dsn-env ... --json`이 `possible`을 확인.
2. **아카이브 저장소** — Tier A 로컬 볼륨(같은 호스트, DR 아님) 또는 Tier B minio(아래, 권장).
3. **복구 drill(증거)** — `recovery_drill`로 base backup + 연속 WAL + **목표 시점 복구를 실제로 수행해 데이터 손실 간격을 측정**. 이때만 `operationalRpoVerified=True`와 수치 bound가 서고, `--require-operational-rpo 900`이 통과(bound ≤ 900). **주의**: `recovery_drill`의 backup 경로는 **Linux 전용**(`_backup_parent`가 non-Linux 거부)이며 실 배포/디스크가 필요하므로 이 Windows 개발 환경에서 실행 불가 — enablement 후 운영/CI에서 수행.
4. `--require-operational-rpo <목표초>` gate가 인수 증거가 된다(현재는 exit 1).

## 영향 정리 (사용자 판단 근거)

- **WAL 보관 용량**: `archive_timeout=300`은 idle에도 300초마다 16MB 세그먼트를 강제 전환·아카이브 → **최소 ~192MB/시간, ~4.6GB/일(idle floor)**, 부하 시 더 큼. `archive_timeout=600`으로 올리면 idle 오버헤드 절반(900s 목표엔 여전히 여유). `wal_keep_size=1024`(1GB)는 pg_wal에 버퍼를 남겨 짧은 아카이브 지연이 미아카이브 세그먼트를 즉시 재활용하지 않게 한다.
- **아카이브 대상 저장소 요구**: 아카이브는 연속 증가하므로 **보관/정리 정책 필수** — 유지하는 가장 오래된 base backup보다 오래된 WAL은 삭제(pgbackrest는 자동, 로컬 cp는 수동 cron 필요). 용량 = (base backup 주기 동안의 WAL 생성량) × (보관하는 backup 세대 수) + 여유. Tier A 로컬은 같은 호스트라 호스트 손실 시 data+archive 동시 손실(DR 아님) — RPO를 호스트 손실까지 보장하려면 Tier B 필요.
- **data_checksums**: initdb 시점만 설정 가능. **신규 클러스터**는 override의 `POSTGRES_INITDB_ARGS=--data-checksums`로 켜짐(빈 postgres_data일 때만). **기존 클러스터**는 offline `pg_checksums --enable`(정지→실행→재시작, 다운타임)이 필요. RPO 항목은 아니나, 복구 drill의 원본이 조용히 손상돼 양쪽에서 같게 읽히는 것(CL-07에서 지적)을 막아 drill 증거의 신뢰를 높인다.
- **재시작 다운타임**: `archive_mode` 변경은 postgres 재시작(짧은 downtime) 동반.
- **볼륨 소유권 전제**: Tier A는 `wal_archive`를 postgres 런타임 uid 소유로 사전 provision해야 archive_command가 쓸 수 있다(안 하면 pg_wal 적체→디스크 full).

## Tier B (권장, 내구성 있는 수용) — 이미 있는 minio로

compose에 minio(S3 호환)가 이미 있다(`saintvision-minio`, `MINIO_ROOT_*`). **pgbackrest** 또는 **wal-g**를 사이드카/커스텀 이미지로 붙여 base backup+WAL을 minio 버킷으로 보내면 off-host 내구성과 자동 보관 정리를 얻는다. 필요한 것: (a) 도구가 든 이미지 또는 사이드카, (b) minio S3 엔드포인트·자격증명(이미 있는 `MINIO_ROOT_*` 또는 전용 키), (c) repo/stanza 설정. 이 중 자격증명·엔드포인트 결정은 운영 결정이라 override에 넣지 않고 경로만 제시한다.

## 사용자 결정 항목 (이 준비가 대기하는 것)

1. 연속 아카이빙 활성 여부(예 시 override 적용).
2. 아카이브 대상: Tier A 로컬 볼륨 vs Tier B minio(권장).
3. `archive_timeout` 값(300 vs 600) 및 base backup 주기 → 실제 RPO/용량 결정.
4. 아카이브 보관/정리 정책과 용량 배정.
5. `data_checksums`: 신규 클러스터에 켤지(기존은 다운타임 감수 여부).
6. 활성 후 복구 drill 수행(운영/CI, Linux)으로 `--require-operational-rpo` 인수 증거 생성.

## 다음 담당

- 준비 완료(변경안 파일·격리 gate 검증·영향)는 Claude. **활성·아카이브 대상·주기·복구 drill 실행은 사용자/운영**. 활성 후 복구 drill 증거가 나오면 Claude가 `--require-operational-rpo`로 재확인. 이 항목은 [[2026-09-19_Claude영역_검증상태지도]] §3 운영 인수 트랙.
