---
doc_id: "GOV-S08-DB-PITR-OPTIN-001"
title: "S08-DB PITR opt-in dry-run과 AC-12 복구 드릴 초안"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T01:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["s08-db", "pitr", "ac-12", "recovery", "tier-a", "dry-run"]
---

# S08-DB PITR opt-in dry-run과 AC-12 복구 드릴 초안

## 1. 현재 결정과 이 문서의 효력

[[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]]의 결정 **B**를 유지한다. 즉 이 PC의 PostgreSQL에는 지금 `docker-compose.pitr.yml`을 적용하지 않고 `archive_mode=off` 상태를 유지한다. 이 문서와 `tools/pitr_opt_in_dry_run.py`는 적용 전 준비물이며 PostgreSQL 재시작, 설정 변경, compose `up`, WAL/base backup 삭제를 수행하지 않는다.

`possible`은 설정 전제만 관측했다는 뜻이다. 연속 WAL 전달, 아카이브 내구성, 목표시각 복구, RPO/RTO, 안전한 서비스 재개를 증명하지 않으므로 dry-run 보고서는 항상 `pitrVerified=false`, `ac12Satisfied=false`다. Tier-A는 같은 호스트의 외부 Docker volume이므로 off-device 장애 도메인도 충족하지 않는다.

## 2. 통합 dry-run

기존 `pitr_readiness`의 읽기 전용 실 DB 설정 관측과 `pitr_archive_retention`의 파일시스템 계획을 한 JSON에 묶는다. `--archive`와 `--backups`에는 실제 적용 전에는 읽기 전용 사본 또는 합성 fixture를 준다.

```powershell
$env:INV_PITR_DSN = '<operator-supplied read-only target DSN>'
python tools/pitr_opt_in_dry_run.py `
  --dsn-env INV_PITR_DSN `
  --archive '<read-only WAL archive or rehearsal copy>' `
  --backups '<read-only base-backup inventory or rehearsal copy>' `
  --days 7 `
  --output '.work/evidence/pitr-opt-in-dry-run.json'
```

종료 코드는 `0=관측 완료(absent 또는 possible)`, `2=입력/설정 판독 불충분`, `3=--require-possible 요청인데 possible 아님`이다. `--require-possible`도 복구 인수는 아니다. 출력은 DSN과 `archive_command` 원문을 싣지 않고 보관 후보의 파일명만 기록하며, 후보가 있어도 삭제하지 않는다.

## 3. Tier-A 활성 창에서만 수행할 외부 wal_archive 3단계

다음은 코디네이터가 재시작 창과 운영자를 지정한 뒤에만 실행한다. 현재 카드에서는 실행하지 않는다.

### 3.1 볼륨 소유권·권한

```powershell
$walVolume = 'saintvision-wal-archive'
docker volume create --label com.saintvision.invion.owner=pitr $walVolume
docker run --rm --user 0 -v "${walVolume}:/wal_archive" postgres:16-alpine sh -ceu 'chown 70:70 /wal_archive; chmod 0700 /wal_archive; test "$(stat -c %u /wal_archive)" = 70; test "$(stat -c %a /wal_archive)" = 700'
```

exit `0`과 `uid=70`, mode `0700`을 증거에 남긴다. 이미지 digest와 `docker volume inspect`의 이름·mountpoint·label을 기록하되 자격 증명은 기록하지 않는다. 기존 볼륨을 재사용할 때는 소유권이 불명확하면 중단한다.

### 3.2 compose 해석

배포 환경의 필수 secret 환경변수를 이미 주입한 shell에서만 다음을 실행한다. 값은 로그에 출력하지 않는다.

```powershell
$env:INV_WAL_ARCHIVE_VOLUME = $walVolume
docker compose -f docker-compose.prod.yml -f docker-compose.pitr.yml config --quiet
if ($LASTEXITCODE -ne 0) { throw "PITR compose config failed" }
```

필수 배포 변수는 `SAINTVISION_DEV_CERT_DIR`, `INV_WEB_AUTH_CONFIG`, `INV_BUSINESS_DSN`, `INV_RUNTIME_DSN`, `INV_RECOVERY_EPOCH`, `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `INV_CONFIG_VOLUME`, `INV_WAL_ARCHIVE_VOLUME`이다. `config --quiet` exit `0` 전에는 `up`을 실행하지 않는다.

### 3.3 적용 후 readiness

승인된 재시작·적용 후 정상 CLI의 exit `0`과 JSON `verdict=possible`을 요구한다.

```powershell
python tools/pitr_readiness.py --dsn-env INV_PITR_DSN --json
if ($LASTEXITCODE -ne 0) { throw "PITR readiness is not possible" }
```

`--require-pitr`는 설정만으로 인수를 막기 위해 의도적으로 계속 exit `1`이다. 기존 결정 문서의 “`--require-pitr` = possible” 표현을 실행 명령으로 사용하지 않는다. 이 단계가 끝나도 AC-12는 미달성이다.

## 4. AC-12 복구 드릴 초안 — Tier-A 활성 후

### 4.1 전제와 중단 조건

1. 코디네이터가 PostgreSQL 중단 창, drill owner, observer, 격리 restore host/port를 지정한다.
2. 3단계 volume/config/readiness 증거가 모두 있고, 최근 base backup과 그 START WAL 이후의 연속 WAL 목록·hash·매체 용량이 있다.
3. restore 대상은 운영 DB와 격리하고 기존 data directory, container, volume을 재사용하거나 덮어쓰지 않는다.
4. base backup 또는 WAL 연속성·hash·소유권이 불명확하면 드릴을 시작하지 않는다. Tier-A 같은 호스트 손실을 off-device 복구로 기록하지 않는다.

### 4.2 주입·복구·판정 순서

1. 원본에 고유 marker A를 commit하고 commit timestamp·LSN·timeline을 기록한다.
2. 목표시각 `T`를 기록한 뒤 marker B를 commit하고 WAL switch·archive 전달 완료를 관측한다.
3. fault 선언 시각부터 RTO clock을 시작하고 원본 writer를 fencing한다. 원본과 동시에 restore DB를 writer로 열지 않는다.
4. 새 격리 data directory에 검증된 base backup을 복원하고 `restore_command`, `recovery_target_time=T`, `recovery_target_action=promote`를 설정해 WAL을 replay한다.
5. recovery 종료·promotion·timeline을 확인한다. marker A 존재, marker B 부재, 목표시각 이전의 최신 기대 commit이 존재함을 각각 독립 query로 검증한다.
6. public/inv schema migration head, role membership·grant, RLS, SECURITY DEFINER allowlist, tenant 미설정 0행, 감사 불변 조건, 저장 object manifest/hash를 확인한다.
7. recovery epoch를 조정하고 예전 epoch의 lease/permit·Node write를 거부한다. API health 후 안전한 읽기와 최소 쓰기 1건을 성공시킨 시각에 RTO clock을 끝낸다.
8. 격리 자원 cleanup은 owner label과 명시 목록으로만 수행하고 제거 후 재-inspect한다. 본문 실패를 cleanup 오류로 덮지 않는다.

### 4.3 정량 판정과 증거

- **RPO** = fault cutoff와 복구된 최신 실제 durable commit의 차이. base backup 시각, archive timeout, 파일 mtime, 도구 실행 시각으로 대체하지 않는다. 목표는 `≤ 15분`이다.
- **RTO** = fault 선언부터 fencing·restore·검증·recovery epoch 조정·API 최소 안전 쓰기 재개까지. 목표는 `≤ 1시간`이다.
- marker A/B, LSN/timeline, WAL 연속 목록·hash, 명령별 시작/종료/exit, RPO/RTO 계산 입력, 권한/RLS/fencing 검사, cleanup receipt를 JSON과 JUnit으로 남긴다.
- artifact 이름은 `ac12-pitr-drill-<UTC timestamp>.json`, `ac12-pitr-drill-<UTC timestamp>.junit.xml`, `ac12-pitr-drill-<UTC timestamp>.log`로 고정한다. 로그에는 DSN/password/key/archive command 원문을 넣지 않는다.
- 모든 필수 assertion과 cleanup verification이 통과하고 reviewer Claude의 독립 검토가 끝나기 전에는 S08-DB/AC-12를 done으로 바꾸지 않는다.

## 5. 현재 카드의 판정

이 카드가 닫는 것은 dry-run 도구와 실행 전 절차의 빈칸뿐이다. 실제 `wal_archive` 생성·권한 변경, compose 적용, PostgreSQL 재시작, archive 전달, 물리 restore, RPO/RTO, 5노드·off-device 인수는 **미실행·미측정**이며 결정 B에 따라 Tier-A 활성 카드로 이관한다.
