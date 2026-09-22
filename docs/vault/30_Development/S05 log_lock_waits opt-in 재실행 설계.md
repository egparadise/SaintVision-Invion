---
doc_id: "CODEX-S05-LOCK-WAIT-DIAGNOSTIC-001"
title: "S05 log_lock_waits opt-in 재실행 설계"
version: "1.2.0"
status: "measured-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T08:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "76f4528d25c609680c26fc3d0623c48be0591696"
task_ids: ["S05-DB"]
tags: ["placement", "postgresql", "log-lock-waits", "deadlock-timeout", "pgrowlocks", "workflow-dispatch", "queue-depth", "evidence"]
---

# S05 log_lock_waits opt-in 재실행 설계

## 0. 목적·미실행 상태

Card19 legacy 20동시 wave는 20/20 성공, request/acquire/hold P95 2142.809/1588.193/151.225ms, project-lock waiter 최대 19, blocking graph depth 1, timeout 0이었다. `lock_timeout=500ms`인데 acquire client elapsed가 500ms를 넘고도 `55P03`이 없었던 원인은 제품 커널에서 아직 확정하지 않았다.

Claude 카드 21의 커널 무관 probe는 다음 가설을 만들었다. legacy는 `placement.py:132`의 project `FOR NO KEY UPDATE` 전에 `approvals.py:86`이 `inv.idempotency`에 INSERT하며, `0001_core.sql:71`의 FK가 같은 project 행에 KEY SHARE를 먼저 보유한다. 이 선행 약한 잠금 때문에 tuple-lock FIFO를 건너뛰고 waiter들이 현재 holder xid를 직접 기다리며, holder 교체마다 `lock_timeout` 구간이 다시 시작됐을 수 있다. candidate의 limits `FOR UPDATE`에는 같은 선행 잠금이 없어 tuple FIFO가 누적된다는 설명이다. 이는 **probe 기반 가설**이지 제품 측정 사실이 아니다.

이 문서는 가설을 제품 경로에서 확인하는 opt-in 진단과 후속 정책 옵션을 설계한다. Claude 카드 23은 D1~D3 보강을 조건으로 승인했고 coordinator는 2026-09-23 08:10 KST에 Card21의 legacy 20×1 및 FK-DROP 대조 legacy 20×1 실행을 승인했다. 확인 시험 결과는 F-S05-02의 원인 기록을 닫는 데 쓰며, 후속 정책 순서는 결과에 의존하지 않고 B 계열(B′→B)을 우선한다. Claude가 별도 검토 중 실수로 실행한 50동시 1회는 절차 이탈로만 기록하며, 그 수치·P95·성공률은 이 카드의 근거와 비교표에 사용하지 않는다.

### Card21 실행 결과

승인된 코드 SHA `40b24329`에서 두 단일 파일 실행은 각각 exit 0이었다. FK 원본 legacy는 20/20 성공, depth 1, transaction acquired segment 190, tuple 0, `pgrowlocks` Key Share+For No Key Update, `55P03` 0이었다. FK-DROP 대조 legacy는 2/20 성공, depth 19, tuple segment, 최대 499.957ms, `55P03` 18이었다. 결합 판정은 **`HYPOTHESIS_SUPPORTED`**다. 20동시 초과·candidate·50동시는 실행하지 않았고 disposable DB/role 잔존 0, raw PID/xid/log·비밀 보존 0이다. 상세 분포는 [[s05-lock-wait-card21-40b24329.json]]에 있다.

이 결과는 기전을 지지하지만 P95 성능 판정은 아니다. logging 진단 wave의 request P95 2575.213ms/982.737ms를 AC-05나 정책 통과 근거로 쓰지 않으며, flag off·S05 `review`를 유지한다.

## 1. 운영 영향 0 설정 경계

PostgreSQL 16의 `log_lock_waits=on`은 `deadlock_timeout`보다 오래 기다린 lock을 기록한다. `deadlock_timeout` 하향은 lock 조사 시 로그를 더 빨리 남기지만 검사 비용을 늘린다. `ALTER DATABASE ... SET`은 이후 새 session의 해당 DB 기본값만 바꾸며, cluster 전체 영구 설정인 `ALTER SYSTEM`과 범위가 다르다. 근거: [Error Reporting and Logging](https://www.postgresql.org/docs/16/runtime-config-logging.html), [Lock Management](https://www.postgresql.org/docs/16/runtime-config-locks.html), [Setting Parameters](https://www.postgresql.org/docs/16/config-setting.html), [ALTER DATABASE](https://www.postgresql.org/docs/16/sql-alterdatabase.html).

실행마다 새 `inv_test_<uuid>` disposable DB와 전용 `inv_app_<uuid>` runtime role을 만든 뒤에만 다음 DB 기본값을 건다.

```sql
ALTER DATABASE <quoted_disposable_db> SET log_lock_waits = on;
ALTER DATABASE <quoted_disposable_db> SET deadlock_timeout = '10ms';
```

- 금지: `ALTER SYSTEM`, `postgresql.conf` 편집, `pg_reload_conf()`, server/container 재시작, 기존 role/DB 설정 변경, 운영 DSN 사용.
- runtime role은 계속 `NOSUPERUSER NOBYPASSRLS`이고 schema owner가 아니다. 설정 변경과 server log 수집은 격리된 hosted service의 관리자 연결만 수행한다.
- migration/grant 이후 benchmark runtime·observer connection을 새로 만든다. 재사용 session은 허용하지 않는다.
- 부하 시작 전 runtime session에서 `SHOW log_lock_waits=on`, `SHOW deadlock_timeout=10ms`, transaction 안에서 `SHOW lock_timeout=500ms`, `SHOW statement_timeout=2s`를 기록한다. 하나라도 다르면 `INVALID_SETUP/exit 3`이다. 10ms는 PostgreSQL 최소 1ms보다 높고 기존 50ms보다 짧아, 짧은 holder segment 누락 위험을 줄인다(D1).
- `CREATE EXTENSION pgrowlocks`는 disposable DB에서만 관리자 연결로 수행하고, runtime role에는 함수 실행 권한을 주지 않는다. snapshot collector만 최소 권한 관리자 연결을 사용한다.
- cleanup은 성공·실패와 무관하게 DB를 `DROP DATABASE ... WITH (FORCE)`하고 role을 DROP한다. DB drop 실패 시 관리자 연결에서 두 DB 기본값을 RESET하고 다시 drop하며, 최종 잔존이면 job failure다.
- 기본 실행 위치는 전용 `postgres:16` hosted service다. 공유 개발 PG는 다른 DB session의 server log 혼입 가능성이 있어 coordinator가 별도 격리를 승인한 경우에만 허용한다.

## 2. 확인 시험: legacy 20동시 1회

### 2.1 고정 입력과 상관키

- 승인된 SHA, `placementShortCommit=false`, 20 requests, concurrency 20, rounds 1만 허용한다. 20동시 초과·50동시·5노드 실행은 이 카드 범위 밖이다.
- barrier release를 0ms로 둔 schema 1.6 `requestTimeline`과 `pg_stat_activity`/`pg_blocking_pids` observer를 함께 사용한다.
- sampler 5ms는 **명목 주기**다. Card19 실제 98표본 간격은 약 16.7ms였으므로 artifact에는 명목값과 실제 p50/p95/max interval을 모두 기록한다(O-a).
- Card19 arrival spread 0.793ms는 client barrier 기준이다. 첫 Lock 표본은 515.384ms였으므로 DB lock 도착이 0.793ms였다고 쓰지 않고, barrier release부터 각 backend의 첫 pre-lock/project-lock 표본까지를 별도로 기록한다(O-b).
- 각 request는 `application_name=s05lw-<opaque-run>-r<00..19>`를 쓰고 private scratch에서만 PID→`backend-N`을 매핑한다. observer는 `pg_stat_activity.backend_xid`도 함께 표본해 raw xid→`backend-N` holder alias를 private scratch에서만 도출한다(D2). tenant/project/run ID, DSN, SQL parameter, raw transaction/lock ID는 공개 artifact에 남기지 않는다.
- `_chain_depth`는 표본 밖 PID(다른 role/DB)를 depth 0으로 끊는다. 전용 DB·전용 role만 허용하고, outsider blocker가 한 번이라도 관측되면 결과를 `INVALID_CROSS_SCOPE`로 판정한다(O-c).

### 2.2 server log와 `pgrowlocks` 동시 증거

hosted preflight에서 `log_destination`에 `stderr`가 포함되고 `logging_collector=off`이며 `log_line_prefix`에 PID 상관키가 있는지 읽기 전용으로 확인한다. 다르면 설정을 고치지 않고 `UNMEASURED/exit 3`으로 끝낸다.

제안 collector는 다음 두 증거를 같은 wave에서 수집한다.

1. service container의 raw stderr를 private scratch로만 받아 승인된 20 backend의 lock-wait/acquired 행만 정규화한다. 기대 signature는 waiter 하나에 대해 holder가 바뀔 때 서로 다른 xid를 기다린 log segment가 반복되고, `ExclusiveLock on tuple` 대기 행은 없는 것이다.
2. 10~20ms 간격의 짧은 구간에 `pgrowlocks('inv.projects')` snapshot을 수집한다. `pg_locks`만으로는 xmax에 저장되는 보유 row lock mode를 충분히 볼 수 없으므로 원인 판정에는 쓰지 않는다. 기대 signature는 대상 project 행에 다수 `Key Share`와 하나의 `No Key Update` 보유가 겹치는 것이다.

공개 `lock-wait-segments.json` 필드는 다음으로 제한한다.

| 필드 | 의미 |
|---|---|
| `backendId`, `requestIndex`, `segmentIndex` | 익명 backend와 요청, 동일 요청 안의 순서 |
| `statementClass` | `project-lock` 같은 parameter-free 분류 |
| `waitEvent`, `lockKind` | `transactionid`/`tuple` 같은 공개 분류 |
| `observerFirstOffsetMs`, `observerLastOffsetMs` | observer가 본 Lock 구간 |
| `serverStillWaitingOffsetMs`, `serverAcquiredOffsetMs`, `serverReportedWaitMs` | server log threshold 통과·획득과 해당 segment 대기 |
| `holderAliasChanged` | raw xid를 노출하지 않은 holder 교체 여부 |
| `rowLockModes` | `pgrowlocks`에서 정규화한 `Key Share`/`No Key Update` mode와 보유자 수 |

waiter별 `loggedSegmentCount`, `sumLoggedWaitMs`, `maxSegmentWaitMs`, `holderChanges`, `tupleWaitCount`, `55P03/57014`, request completion을 함께 계산한다. `loggedSegmentCount`는 **10ms threshold 이상만** 포함하며 실제 전체 segment 수로 해석하지 않는다(D1). raw Docker log·PID/xid map·원문 SQL은 artifact upload 전에 삭제한다.

### 2.3 FK-DROP 반증 대조군(D3)

legacy wave가 끝나고 그 disposable DB/role을 제거한 뒤, **새 disposable DB**를 같은 SHA·입력으로 만든다. 관리자 연결이 `inv.idempotency(tenant_id,project_id) → inv.projects` FK가 정확히 하나임을 확인하고 그 FK만 DROP한 다음 legacy 20×1을 한 번 실행한다. 제품 코드·계약·migration 파일은 바꾸지 않고, 대조 DB는 실행 직후 삭제한다.

- 가설 지지 signature: `Lock:tuple`/tuple server log가 나타나고 blocking depth가 2 이상으로 깊어지며 약 500ms(`lock_timeout`)의 `55P03` cascade가 발생한다.
- 가설 기각 signature: FK 제거 뒤에도 depth 1·tuple wait 0·`55P03=0`이 유지된다.
- 어느 signature도 완전하지 않거나 observer/log/pgrowlocks가 불완전하면 `NOT_OBSERVED`다. 누락 값을 0으로 대체하지 않는다.
- 두 wave는 각각 20동시를 넘지 않으며 별도의 시작·종료 알림과 disposable DB/role 잔존 0 확인을 남긴다.

## 3. 판정 기준

### 3.1 실행 유효성

다음 조건을 모두 충족해야 원인 판정에 사용한다.

1. 승인 SHA·수동 run/job·전용 Postgres service·legacy 20×1이 일치한다.
2. 네 `SHOW` 값과 `pgrowlocks` extension preflight가 일치한다.
3. request index/application name/backend alias가 20개 모두 1:1이고 arrival·DB-first-seen·completion이 존재한다.
4. server log와 observer pair completeness가 100%이며 parser orphan/duplicate가 0이다.
5. `pgrowlocks`가 대상 project 행 snapshot을 최소 1개 포착하고, 다른 DB/role blocker가 0이다.
6. DB/role/raw scratch 잔존 0, secret marker 0, 공개 artifact SHA-256이 존재한다.

하나라도 실패하면 `INVALID` 또는 `UNMEASURED`이며 0으로 채우거나 성공으로 간주하지 않는다.

### 3.2 가설 판정

| 판정 | 필수 증거 | 의미 |
|---|---|---|
| `HYPOTHESIS_SUPPORTED` | 제품 legacy에서 transactionid segment·tuple wait 0·`pgrowlocks` Key Share+No Key Update·`55P03=0`, FK-DROP 대조군에서 tuple wait·depth≥2·약 500ms `55P03` cascade를 함께 관측 | FK 선행 약한 잠금→tuple FIFO 우회 가설을 두 wave 인과 대조로 지지 |
| `LOCK_TIMEOUT_OBSERVED` | 한 segment가 약 500ms에서 `55P03`으로 종료되고 SHOW/statement class가 일치 | timeout은 적용됐으나 해당 request가 reset 경로로 완료되지 않음 |
| `NOT_OBSERVED` | 유효한 run이나 다중 holder segment 또는 Key Share/No Key Update 겹침이 없음 | 지지·기각 불가; 반복은 새 승인 필요 |
| `HYPOTHESIS_CONTRADICTED` | legacy 지지 signature는 있으나 FK-DROP 뒤에도 depth 1·tuple wait 0·`55P03=0` 유지 | FK가 큐 차이의 원인이라는 가설 기각; 제품 정책 변경 금지 |

request P95·success count·hold P95는 부수 결과다. logging overhead가 있고 1회 진단 wave이므로 AC-05, candidate 정책, 5노드 승격의 pass/fail 근거로 쓰지 않는다.

## 4. 후속 정책 옵션 — 확인 시험과 순서 비의존

### 옵션 A: limits lock을 `FOR NO KEY UPDATE`로 낮추는 선행 약한 잠금 변형

candidate가 limits 행에 먼저 약한 잠금을 확보한 뒤 commit lock을 취하는 변형을 검토하려면, 현재 최종 `FOR UPDATE`를 그대로 둘 수 없다. 여러 transaction이 KEY SHARE를 보유한 뒤 서로 `FOR UPDATE`로 승격하면 교착할 수 있으므로, key 열을 바꾸지 않는다는 정적·동적 증거 아래 최종 lock도 `FOR NO KEY UPDATE`로 전환해야 한다.

- 계약 표면: 공개 request/response/ProblemDetails 변화 0, 내부 opt-in flag 기본 off. 제품 기본 경로로 승격하지 않는다.
- 선행 조건: legacy 확인 시험이 `KEY_SHARE_RESET_SUPPORTED`; limits key 열 미갱신과 `_reserve_prepared_locked` 포함 모든 writer의 잠금 순서 검토; 교착·fencing/epoch·멱등·RLS·부분 실패 rollback 반례 시험.
- 비교 실행: 별도 승인 SHA에서 candidate control 20×1과 option-A 20×1을 각각 새 disposable DB로 실행한다. `FOR KEY SHARE + FOR UPDATE` 조합은 시험 대상에서 제외한다.
- 판정: tuple wait 0과 depth-1 transactionid fan-in 전환을 확인하더라도 성능 승격은 아니다. 비FIFO 기아, holder commit마다 모든 waiter가 깨는 thundering herd, 2초 `57014` 재집중, fail-fast 목표 상충을 필수 위험으로 기록한다.
- rollback: 내부 flag off, `FOR UPDATE` 기본 경로 유지, disposable DB/role 삭제. 공개 계약·migration은 남기지 않는다.

### 옵션 B′→B: FIFO 유지 + timeout 예산, 이어 queue 깊이 상한

우선 B′에서 candidate limits 행의 `lock_timeout` 예산을 500ms에서 약 1500ms로 늘려 statement timeout 2초 안에서 FIFO 공정성과 원자성을 유지한다. 그 뒤 B에서 DB lock 진입 전에 project별 bounded semaphore 동시 admission 수를 제한하고 넘는 요청은 기존 `RES-0007`/503/retryable 표면으로 fail-fast 한다.

- 계약 표면: 기존 오류 코드·status·retryable만 사용한다. 새 공개 오류 코드나 성공 응답 필드는 별도 계약 결정 없이는 금지한다.
- 선행 조건: 확인 시험으로 legacy/candidate 큐 signature를 고정하고, queue 상한의 원자성·분산 인스턴스 일관성·누수 복구·idempotency 순서를 설계한다.
- 판정: queue depth가 상한을 넘지 않고, 외부 timeout 합계가 legacy 대비 비증가하며, request P95 비악화와 fencing/epoch·RLS·멱등 불변식이 모두 유지돼야 다음 카드로 간다.
- rollback: admission flag off와 counter/lease cleanup. migration이 필요하면 expand/contract와 reconcile·dual-read rollback을 별도 결정한다.

정책 순서는 확인 시험 판정에 의존하지 않는다. 확인 시험은 F-S05-02 기전을 닫고, 제품 정책은 **B′→B 우선**으로 별도 결정한다. 옵션 A는 FIFO를 피하지만 기아·thundering herd와 fail-fast 목표가 충돌하므로 기전 확인용 변형일 뿐 제품 정책 후보로 승격하지 않는다. 이 카드에서는 어느 옵션도 구현하지 않는다.

## 5. CI opt-in 제안

후속 구현 카드에서 `.github/workflows/s05-lock-wait-diagnostic.yml`을 `workflow_dispatch` 전용으로 추가한다. `core.yml`의 integration/PR 자동 lane에는 넣지 않는다.

```yaml
name: S05 Lock Wait Diagnostic
on:
  workflow_dispatch:
    inputs:
      approved_sha:
        description: Coordinator-approved exact 40-hex commit
        required: true
permissions:
  contents: read
concurrency:
  group: s05-lock-wait-diagnostic
  cancel-in-progress: false
jobs:
  diagnostic:
    environment: s05-lock-wait-diagnostic
    runs-on: ubuntu-latest
    timeout-minutes: 10
    services:
      postgres:
        image: postgres:16@sha256:<pinned-before-first-run>
        env:
          POSTGRES_PASSWORD: inv_test_only
          POSTGRES_DB: postgres
```

- Environment required reviewer가 승인하고 checkout HEAD가 input SHA와 정확히 같아야 DB 생성으로 진행한다.
- 단일 diagnostic file만 실행하며 Core/pytest/build/browser와 병행하지 않는다.
- artifact는 `manifest.json`, schema 1.7 후보 `placement.json`, `lock-wait-segments.json`, `pgrowlocks-snapshots.json`, JUnit, `redaction.json`만 30일 보존한다. raw Docker log·PID/xid map·DSN은 업로드하지 않는다.
- `manifest.json`은 Postgres image digest/version, exact command/exit, 네 SHOW 값, 실제 sampler interval, UTC/KST window, cleanup 결과를 담는다.

실행 승인은 다음과 같이 legacy 확인 wave의 범위를 명시해야 한다.

```text
APPROVE S05-LOCK-WAIT-DIAGNOSTIC: sha=<40hex>, legacy=20x1, fk_dropped_control=20x1, deadlock_timeout=10ms, pgrowlocks=true, disposable-db=true
```

옵션 A/B 비교는 이 승인에 포함되지 않는다. 별도 결정·별도 exact-SHA 승인 전에는 flag off, S05-DB `review`, candidate/50/5-node 미승격을 유지한다.
