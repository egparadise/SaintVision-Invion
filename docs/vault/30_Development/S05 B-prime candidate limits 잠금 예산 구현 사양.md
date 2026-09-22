---
doc_id: "CODEX-S05-BPRIME-LOCK-BUDGET-SPEC-001"
title: "S05 B-prime candidate limits 잠금 예산 구현 사양"
version: "1.2.2"
status: "implemented-calibration-failed-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T15:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "candidate", "lock-timeout", "statement-timeout", "specification"]
---

# S05 B-prime candidate limits 잠금 예산 구현 사양

> [!warning] observer-on 상한 기록, 승격 실패
> v1.1 사양을 구현해 실 PostgreSQL focused 17 passed와 legacy/candidate 20동시 각 3회를 실행했다. candidate B=1500은 세 판정 조건을 모두 충족하지 못해 승격하지 않는다. 현재 정본은 `placementShortCommit=false`, 기본 candidate budget 500ms, S05-DB `review`다. 20동시 초과, 5노드·50동시는 실행하지 않았다.

## 1. 목표와 비목표

B′의 목표는 `placementShortCommit=true`인 candidate 경로의 `inv.project_resource_limits ... FOR UPDATE` 한 statement에만 더 긴 lock 대기 예산을 줄 수 있게 만드는 것이다. 기본값은 현재와 같은 **500ms**이고, 실험값은 약 **1500ms**다. limits 행의 FIFO·잠금 모드·transaction 원자성은 바꾸지 않는다.

다음은 비목표다.

- legacy, direct lease, recovery/reconcile writer 또는 일반 `Database.transaction`의 500ms 기본값 변경
- `statement_timeout=2s` 확대, 새 HTTP route/field/header/error code 추가
- 내부 retry 복원, `FOR NO KEY UPDATE` 전환, semaphore·queue-depth 상한 구현
- throughput 해결 또는 AC-05 충족 주장
- 운영 flag 활성화, 20동시 초과, 50동시·5노드 실행

## 2. 내부 설정과 유효성

구현 카드의 provisional Python 이름은 `placement_candidate_limit_lock_timeout_ms`다.

| 항목 | 사양 |
|---|---|
| 소유 위치 | `Database`의 private constructor setting. `BoundDatabase`가 같은 값을 복사해 caller-owned outer transaction에서도 잃지 않는다. |
| 기본값 | `500` — 현재 동작과 동일 |
| 실험값 | `1500` — Card21의 tuple FIFO에서 holder 시간 `h`를 교정하는 첫 측정점이며 승격 후보나 최종 운영값이 아니다. 선택 대조 arm은 `1900`까지다. |
| 유효 범위 | `1 <= value <= 1900`, `bool`은 거부. 상한은 같은 statement의 `statement_timeout=2000ms`보다 반드시 작다. |
| 활성 조건 | `placement_short_commit is True`인 candidate limits lock에서만 읽는다. flag off/legacy에서는 값을 주어도 500ms 공통 경로가 유지돼야 한다. |
| 외부 노출 | 첫 구현·측정 카드는 공개 API와 production `INV_API_CONFIG` 허용 key를 늘리지 않는다. benchmark/test harness만 명시적으로 주입한다. 운영자 설정 노출은 성능 판정 뒤 별도 결정한다. |

따라서 “기본 500 유지”는 새 설정을 생략한 기존 constructor, production app factory, legacy, direct lease 모두에 대해 byte-for-byte 설정 동등성을 뜻한다. candidate B′ 측정만 benchmark의 명시적 opt-in 인자로 `1500`을 주입한다. 알 수 없는 production config key는 현재처럼 fail closed한다.

## 3. SQL 적용 경계

현재 transaction 시작 순서는 tenant GUC 뒤 `SET LOCAL lock_timeout='500ms'`, `SET LOCAL statement_timeout='2s'`다. B′는 이 공통 순서를 유지하고 candidate의 limits lock 직전에만 `set_config('lock_timeout', '<budget>ms', true)`로 session-local이 아닌 **transaction-local** 값을 바꾼다.

1. candidate savepoint와 idempotency/Run/admission 검사를 현재 순서로 수행한다.
2. `current_setting('lock_timeout')`으로 진입 시 caller의 실제 값을 캡처한다. 복원값을 상수 500으로 가정하지 않는다.
3. `placement-limit-row-wait` phase를 표시하고 limits lock 직전에 transaction-local candidate 예산을 적용한다.
4. `SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE`를 수행한다.
5. 획득 성공 직후, Node/Resource 등 다음 writer lock 전에 `lock_timeout`을 2단계에서 캡처한 값으로 복원한다.
6. limits lock이 timeout이면 기존 savepoint/outer transaction unwind로 끝낸다. 실패한 savepoint에서 복원 SQL을 억지로 실행하지 않으며 rollback이 진입 값을 복구한다. 새 request/transaction은 처음부터 공통 설정을 다시 적용한다.

복원 뒤의 resource lock, canonical reserve, stale winner savepoint 재계획은 모두 caller 진입값을 따른다. 일반 `Database.transaction`에서는 500ms지만, `BoundDatabase`의 caller-owned outer transaction은 다른 값을 이미 가질 수 있다. B′가 transaction의 나머지 lock wait까지 1500ms로 넓히는 구현은 사양 위반이다. nested `BoundDatabase`에서도 attempt 사이 설정 누출이 없어야 한다.

## 4. 2초 statement timeout과 오류 표면

PostgreSQL `statement_timeout`은 transaction 총시간이 아니라 각 statement의 시작부터 끝까지 적용된다. 같은 limits `SELECT ... FOR UPDATE`에서는 다음 관계를 고정한다.

- candidate limits FIFO는 선행 FK 잠금으로 holder가 바뀌는 legacy 경로와 달리 최대 한 lock-wait segment로 누적된다. 따라서 같은 statement의 총시간은 대략 `B + h` 이하이며, 여기서 `B`는 candidate lock budget, `h`는 holder의 한 번 보유 시간이다.
- `B=1500ms`이고 `h<500ms`라면 `55P03`이 2초보다 먼저 발생해야 한다. `B=1900ms` 대조 arm은 `h>100ms`일 때 `57014`가 섞일 수 있으므로 두 SQLSTATE를 분리해 해석한다.
- holder 교체마다 lock timeout clock이 재시작되어 누적 대기가 statement timeout에 닿는 `57014` 현상은 idempotency FK의 RI KEY SHARE가 FIFO를 우회하는 **legacy 기전**이다. candidate FIFO 설명에 이 재시작을 적용하지 않는다.
- limits 획득 뒤 후속 statement는 새 2초 statement budget을 갖고 lock budget은 캡처한 caller 값으로 복원된다(일반 transaction은 500ms).
- `55P03`과 `57014`는 모두 현재 `Database.transaction` 매핑을 통해 `RES-0007`, HTTP 503, `retryable=true`다. SQLSTATE는 진단 evidence에만 남고 공개 ProblemDetails에 새 필드를 추가하지 않는다.

1500ms는 2초까지의 남은 “transaction 여유 500ms”라는 뜻이 아니다. 같은 limits statement 안에서 lock timeout이 statement timeout보다 먼저 작동하도록 둔 명목 차이다. 이 관계를 오기한 측정은 무효다.

### 4.1 FIFO 산술과 실험 위치

대기열의 `k`번째 waiter가 겪는 최장 구간은 대략 `(k−2)·h`, 20동시에서 예상 실패 수는 `20−⌊B/h+2⌋`로 본다. 이는 판정식이 아니라 queue-depth 표본과 함께 읽는 calibration 근사다.

| holder `h` | `B=500` 예상 실패 | `B=1500` 예상 실패 | `B=1900` 예상 실패 |
|---:|---:|---:|---:|
| 70ms | 11 | 0 | 0 |
| 100ms | 13 | 3 | 0 |
| 150ms | 15 | 8 | 6 |
| 289ms | 17 | 13 | 12 |

기존 `B=500` 관측 12~13/20은 `h≈90~110ms`와 맞는다. 따라서 B′는 성공을 기대하는 승격 후보가 아니라 실제 `h`와 FIFO 깊이를 교정하는 실험이다. 1500ms가 실패를 줄이지 못해도 구현 결함으로 단정하지 않으며, 결과와 무관하게 다음 설계 카드는 B(project별 bounded semaphore)다.

## 5. 계측

기존 `placement-limit-row-wait` identifier-free metric에 다음을 추가한다.

- `lockTimeoutBudgetMs`: 실제 적용된 500 또는 실험 1500
- `waitMs`, `outcome`, `sqlState`, `attempt`: 기존 필드 유지
- effective budget 적용/복원 여부는 시험 assertion으로 고정하되 DSN, tenant/project/resource ID, PID/XID, SQL parameter는 기록하지 않는다.

request P95와 post-acquire hold P95는 기존 대칭 경계를 유지한다. limits wait P95와 queue depth는 원인 설명용 보조 지표이며, 그것만 좋아졌다고 판정하지 않는다. 운영 `app.py`의 legacy metric sink 부재와 stale attempt 1 hold 누락 경계도 그대로다.

## 6. 시험 사양

### 6.1 PG-free

1. 기본 constructor와 `BoundDatabase`가 500을 보존한다.
2. `bool`, 0, 음수, 2000 이상, 정수가 아닌 값은 fail closed한다.
3. flag off에서는 1500 주입이 legacy SQL 설정·경로를 바꾸지 않는다.
4. production config의 새 key는 아직 허용하지 않는다.
5. metric에 실제 budget만 나오고 식별자·비밀은 0건이다.

### 6.2 실 PostgreSQL 단일 파일

1. **default parity:** candidate 기본 500에서 기존 limits-row 55P03 회귀와 `RES-0007` 표면이 유지된다.
2. **budget success:** 같은 holder 조건에서 500ms는 실패하고 1500ms는 limits row를 획득하는 경계를 고정한다.
3. **budget exhaustion:** 한 구간을 1500ms보다 길게 보유하면 `55P03` → `RES-0007`/503/retryable이며 Lease·event·idempotency 잔존 0이다.
4. **statement boundary:** candidate 1500/1900 arm에서 `55P03`과 `57014`의 `B+h` 경계를 확인한다. legacy의 holder-reset 누적과 candidate FIFO를 합쳐 쓰지 않고 evidence에는 SQLSTATE를 구분한다.
5. **restore:** limits 획득 직후와 stale 재계획 attempt 2 시작에서 `SHOW lock_timeout`이 진입 시 캡처값과 같다. 일반 transaction의 500ms뿐 아니라 다른 caller 값을 가진 `BoundDatabase`에서도 후속 resource lock에 candidate 예산이 누출되지 않는다.
6. **invariants:** exact replay, changed-body 409, fencing/epoch, no-overbooking, RLS, rollback, direct lease 혼합의 기존 focused 시험을 그대로 통과한다.

실 PG 시험은 disposable DB만 사용하고 단일 파일로 실행한다. 20동시 성능 wave는 위 기능 시험과 분리하며 Claude 의견·코디네이터 승인 뒤에만 수행한다.

## 7. 성능 판정 게이트

메모리 여유 1.5GB 이상과 시작 승인을 확인하면 같은 code SHA·같은 PostgreSQL·합성 Node 조건에서 legacy(flag off, 공통 500)와 candidate(flag on, limits 1500)를 **20동시 각 3회** 순차 실행한다. 선택 대조는 candidate 1900을 1회만 실행하며 `57014` 혼입 규칙을 적용한다. 50동시와 물리 5노드는 실행하지 않는다.

다음 세 조건을 모두 만족해야 후속 검토로 보낸다.

1. candidate의 외부 `55P03 + 57014` 합계가 legacy 이하
2. candidate **전체 요청(all requests) P95** 3회 중앙값이 legacy 대비 비악화. 성공 요청만의 P95는 별도 보조값으로 함께 보고한다.
3. candidate 성공 request의 post-acquire hold P95 3회 중앙값이 legacy 대비 비악화

성공 수, limits wait P95 또는 hold 감소 하나만으로 통과시키지 않는다. 각 wave의 성공/실패, SQLSTATE별 수, effective budget, request all/success-only P50/P95/max, limits-wait/post-acquire-hold P50/P95/max, queue-depth 표본, arrival spread, invariants, process exit를 같은 JUnit/JSON schema에 남긴다. P95 차이는 queue depth와 DB 도착 분산을 함께 제시하지 않으면 인과로 해석하지 않는다. 어느 조건이든 실패하면 flag off·S05 `review`를 유지하고 B′를 승격하지 않는다.

## 8. 롤백과 중단 기준

- 즉시 롤백은 candidate 실험 인자를 제거해 500ms로 되돌리고 `placementShortCommit=false`를 유지하는 것이다.
- migration·schema·data backfill이 없으므로 DB rollback이나 Lease 삭제는 없다.
- 새 오류 코드/응답 field/header, production config key, internal retry, lock mode 변경이 필요해지면 B′ 범위를 중단하고 별도 계약 결정을 요청한다.
- deadlock, fencing 중복, no-overbooking/RLS/rollback 위반, 2초를 넘기는 설정, 후속 lock으로 budget 누출 중 하나라도 관측되면 성능 수치와 무관하게 실패다.

## 9. 인계

- owner: Codex — 승인 뒤 구현·focused 회귀·20×3 측정
- reviewer: Claude — Card24 기전/정책 검토 뒤 이 사양의 SQL 범위·timer 관계·반례 독립 검토
- decision: 코디네이터 — 구현/실측 시작과 B′ 승격 여부

현재 handoff는 **구현·교정 실험 완료, Claude 카드 28 독립 검토 대기**다. 다음 구현 후보 B(project별 bounded semaphore)는 별도 사양·승인 카드로 분리한다.

## 10. v1.2 교정 결과

실행 당시 local head `4c8a7363`의 개발 PC·합성 Node·실 PostgreSQL 20동시 결과는 다음과 같다. 이 head는 integration 이력에서 도달 불가하므로 evidence `codeSHA`는 측정 파일 blob이 동일한 도달 가능 commit `c042b3fce80cd246ba5aeb77a6a28d2ca4cdb5ff`로 보정했다. 전체 원자료와 cleanup은 [[s05-bprime-card24-4c8a7363.json]], 절차·정직성 경계는 [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]]가 정본이다.

| mode | 성공/60 | 외부 timeout | request P95(all) 3회 중앙 | 성공 request P95 중앙 | hold P95 중앙 | acquire wait P95 중앙 |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 60 | 0 | 1785.486ms | 1785.486ms | 141.932ms | 1358.987ms |
| candidate B=1500 | 11 | `55P03` 49 | 2315.099ms | 2402.481ms | 767.708ms | 1530.788ms |

외부 timeout 비증가, all-request P95 비악화, 성공 request hold P95 비악화가 모두 실패했다. candidate queue depth는 매회 19였고 observer-on hold P95 중앙 767.708ms를 넣은 산술 예상 17 실패와 실제 16/16/17 실패가 evidence 내부에서 정합했다. 그러나 sampler interval이 legacy 약 21ms에서 candidate 약 67~89ms로 느려졌고 `pg_blocking_pids` 호출의 lock 파티션 비용이 holder를 지연했을 수 있어 767.708ms는 **관측자 포함 상한**이다. 제품 고유 h의 교정 완료나 N 산출 근거로 사용하지 않는다. 같은 방향 3회를 확인했고 `B+h>2s`의 `57014` 혼입 위험 때문에 승인에 따라 1900 arm은 실행하지 않았다. sampler-off candidate 1500×1 대조 뒤에만 B의 N 산술 후보를 확정한다.

측정 코드 provenance는 다음 Git blob OID로 고정한다: `placement.py=8be573eed075812e04d271b3e1237351fde991e2`, `db.py=2e37b85eb96231e561bc08bf84a1673f9120f80e`, `test_placement_benchmark.py=46f0ab4878787975e1d60fdefb3927084008ed51`, `test_placement_short_commit.py=b29689ef4d004f403914959d9d63f14a539f9826`, `placement_benchmark.py=9a8430ad684f7dfbda0c8aca7f3c289acc7bf4e5`. 이 다섯 blob은 local 실행 head `4c8a7363…`와 도달 가능한 `c042b3fc…`에서 모두 같다.
