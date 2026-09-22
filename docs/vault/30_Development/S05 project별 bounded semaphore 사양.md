---
doc_id: "CODEX-S05-PROJECT-BOUNDED-SEMAPHORE-SPEC-001"
title: "S05 project별 bounded semaphore fail-fast 사양"
version: "1.1.2"
status: "proposed-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T15:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "semaphore", "fail-fast", "contention", "specification"]
---

# S05 project별 bounded semaphore fail-fast 사양

> [!warning] 사양만 작성, 구현·측정 미승인
> 이 문서는 Card24 B′의 h 교정 결과를 받아 옵션 B를 설계한 문서다. 제품 코드, migration, 공개 계약, 시험 하네스는 변경하지 않았고 부하 시험도 실행하지 않았다. `placementShortCommit=false`, candidate lock budget 기본 500ms, S05-DB `review`를 유지한다. 구현과 실 PostgreSQL 20동시 측정은 Claude 검토와 코디네이터의 별도 승인 뒤에만 시작한다.

## 1. 목표와 비목표

옵션 B는 같은 tenant+project의 신규 placement 예약 시도가 candidate의 `project_resource_limits ... FOR UPDATE`에 한꺼번에 진입하지 않도록 **한 CP 프로세스 안에서만** 동시 진입 수를 제한한다. 상한을 이미 사용 중이면 기다리는 내부 큐를 만들지 않고 즉시 기존 `RES-0007`, HTTP 503, `retryable=true`로 반환한다.

목표는 DB FIFO 깊이를 작게 유지하고 fail-fast 지점을 명시적으로 계측하는 것이다. 다음은 비목표다.

- 전역 FIFO, 공정성 또는 다중 process·다중 CP 인스턴스에 걸친 동시성 상한
- `statement_timeout=2s`, 기본 `lock_timeout=500ms`, lock mode 또는 B′ budget의 변경
- 성공률·throughput·AC-05 충족 보장
- 새 HTTP route, response field/header, 오류 코드 또는 client backoff 계약
- migration, durable queue, distributed lock, Redis/PostgreSQL advisory lock 도입
- 운영 flag 활성화, 20동시 초과, 50동시 또는 물리 5노드 실행

## 2. 상한 N 도출 조건과 보수적 fallback

Card21/Card24에서 사용한 근사식은 `k`번째 waiter의 최장 단일 FIFO 구간을 `(k−2)·h`, 상한 B에서 timeout 없이 진입 가능한 동시 요청 수를 대략 `floor(B/h+2)`로 본다. 그러나 Card24의 candidate hold P95 중앙 `767.708ms`는 `pg_stat_activity`와 `pg_blocking_pids` queue observer를 함께 켠 값이다. Claude 카드 28은 legacy sampler interval이 약 21ms인 데 비해 candidate depth-19 wave에서는 약 67~89ms로 느려졌고, `pg_blocking_pids`가 lock 파티션 LWLock을 사용해 holder의 후속 lock 획득을 지연할 수 있음을 지적했다. sampler가 없던 카드 16/18의 candidate hold는 117~171ms였다.

따라서 `767.708ms`는 **관측자 비용이 포함된 상한**이지 제품 고유 `h`의 교정값이 아니다. `floor(500/767.708+2)=2`는 보수적 하한 탐색값일 뿐 N=2의 성능 근거나 N=3/4의 기각 근거로 확정하지 않는다.

| 입력 h | `floor(500/h+2)` | 현재 의미 |
|---:|---:|---|
| 117ms | 6 | 과거 sampler-off 단일 wave의 낮은 경계이며 현재 카드의 동시 대조가 아니다. |
| 171ms | 4 | 과거 sampler-off 상한 예시. N≤4 가능성을 열지만 zero-timeout 보장은 아니다. |
| 767.708ms | 2 | Card24 observer-on 상한. 정책 기본값 산출에 직접 쓰지 않는다. |

N의 실험 기본값은 다음 절차 뒤에만 확정한다.

1. Card24와 같은 code SHA·PostgreSQL·20동시·candidate budget 1500ms에서 queue observer를 끈 대조 wave 1회를 실행한다.
2. 같은 report의 hold P95와 `55P03` 수를 observer-on 3회와 분리해 기록한다. `pg_blocking_pids` 호출 횟수·실제 interval·호출 elapsed를 기록할 수 있으면 관측자 비용도 함께 남긴다.
3. sampler-off `h`에 `floor(500/h+2)`를 적용해 N=3/4 arm의 산술 후보를 만든다. 이는 시험 arm 선택값이며 production 기본값이 아니다.
4. N=3/4 중 하나가 55P03 0을 보일 것이라는 주장은 candidate-B 20동시 3회가 끝나기 전에는 금지한다.

승인된 sampler-off candidate 1500×1은 실행 당시 local head `6c389a1d`에서 **20/20 성공, `55P03`/`57014` 0, hold p50/p95/max 55.469/155.873/234.974ms**였다. 이 head는 integration 이력에서 도달 불가하므로 측정 코드 정본을 도달 가능한 `c042b3fce80cd246ba5aeb77a6a28d2ca4cdb5ff`로 보정했다. 두 commit의 `placement.py`, `db.py`, benchmark/short-commit 시험, benchmark 도구 Git blob OID가 모두 일치한다. request P95(all)는 2014.409ms로 2초보다 14.409ms 길어 AC-05 판정에는 실패가 아니라 **미평가**로 남긴다. queue/sql diagnostic은 모두 off였고 disposable DB·신규 role 잔존은 0이다. [[s05-card25-sampler-off-6c389a1d.json]].

### 2.1 측정 코드 provenance

| 파일 | Git blob OID |
|---|---|
| `services/control-plane/src/inv/placement.py` | `8be573eed075812e04d271b3e1237351fde991e2` |
| `services/control-plane/src/inv/db.py` | `2e37b85eb96231e561bc08bf84a1673f9120f80e` |
| `tests/integration/test_placement_benchmark.py` | `46f0ab4878787975e1d60fdefb3927084008ed51` |
| `tests/integration/test_placement_short_commit.py` | `b29689ef4d004f403914959d9d63f14a539f9826` |
| `tools/placement_benchmark.py` | `9a8430ad684f7dfbda0c8aca7f3c289acc7bf4e5` |

`codeSHA`는 위 blob을 모두 포함하고 origin integration에서 도달 가능한 `c042b3fc…`다. `executionHeadAtRun=6c389a1d…`는 당시 local 실행 위치를 정직하게 보존하는 역사 필드일 뿐 재현 anchor로 사용하지 않는다. 새 wave는 실행하지 않았다.

P95를 쓰면 `floor(500/155.873+2)=5`지만 단일 wave의 낙관값일 수 있다. 관측 max를 보수적으로 쓰면 `floor(500/234.974+2)=4`다. N=4에서 가장 깊은 예상 구간은 `(4−2)×234.974=469.948ms`로 500ms 안이고, N=5는 `(5−2)×234.974=704.922ms`로 넘는다. 따라서 **첫 구현 실험값은 N=4**로 제안한다. N=3은 reviewer가 더 보수적 대조를 요구할 때의 lower arm이고, N=5는 현 근거로 제외한다.

observer-on P95 767.708ms와 sampler-off 155.873ms의 차이는 611.835ms, 비율은 약 4.925배다. 동일 하네스에서 diagnostic on/off에 따라 측정이 크게 달라져 **F-1 관측자 효과는 확인**됐다. 따라서 767.708ms는 관측자 포함 상한으로 유지한다. 다만 서로 다른 단일 wave의 나머지 실행 변동까지 모두 `pg_blocking_pids` 하나의 비용으로 인과 귀속하지 않는다. B′ 1500ms와 semaphore를 동시에 운영 기본값으로 묶지도 않는다.

Claude 카드 32 검토 조건으로 queue/sql diagnostic을 끈 candidate 1500×1 **재현 wave 1회**를 둔다. 재현 wave는 이번 20/20, timeout 0, hold p50/p95/max 범위를 대조하되 동일 수치 재현을 합격 조건으로 만들지 않는다. 방향이 뒤집히거나 `55P03`/`57014`가 생기면 N=4 산출을 보류하고 N을 다시 결정한다. 이 재현은 카드 32와 코디네이터 승인 전 실행하지 않는다.

어느 N이든 20개 barrier 요청 중 나머지를 즉시 거절할 수 있으므로 성능 게이트 통과를 기대하지 않는다. 옵션 B는 우선 DB 보호와 실패 위치 교정 실험이며 승격 후보가 아니다.

## 3. 내부 설정과 활성 경계

구현 카드의 provisional 내부 설정은 다음과 같다.

| 설정 | 제안 | 경계 |
|---|---|---|
| `placement_project_semaphore_enabled` | 기본 `false` | `placement_short_commit is True`인 candidate 신규 예약 경로에서만 유효하다. |
| `placement_project_semaphore_limit` | flag-on 첫 실험값 `4` | 정수만 허용하고 `bool`, 0, 음수, 과도한 값은 fail closed한다. 최초 구현의 허용 범위는 1~20으로 제한한다. production 기본값이 아니며 flag 기본 off다. |

production `INV_API_CONFIG`에는 두 설정을 노출하지 않는다. benchmark와 focused test가 명시적으로 주입하며, 운영 노출은 실측·독립 검토 뒤 별도 결정한다. flag off에서는 registry 객체 생성, permit 계측, 거절 분기가 없어야 하며 기존 candidate/legacy SQL과 오류 표면이 유지돼야 한다.

## 4. 키, 진입 위치와 permit 수명

### 4.1 격리 키

permit key는 인증·RLS로 확인된 canonical `(tenant_id, project_id)`다. raw URL 문자열, 사용자가 보낸 tenant 값, principal 또는 idempotency key만으로 만들지 않는다. 서로 다른 tenant나 project는 독립 상한을 갖는다. metric과 로그에는 원문 ID를 남기지 않는다.

### 4.2 진입 순서

1. 기존 인증, tenant GUC, membership/grant, canonical request hash와 idempotency 분류를 수행한다.
2. 이미 commit된 exact replay는 기존 응답을 반환하고 permit을 소비하지 않는다. 같은 key의 다른 body는 기존 409를 반환한다.
3. **새 예약 시도만** candidate의 첫 project/limits writer lock 전에 non-blocking permit을 획득한다.
4. permit이 없으면 DB writer lock을 기다리지 않고 기존 `RES-0007`/503/retryable을 반환한다. 새 idempotency insert가 있었다면 transaction rollback으로 잔존 0이어야 한다.
5. permit을 얻은 요청은 기존 candidate final validation과 canonical reserve를 그대로 수행한다.

동시에 진행 중인 같은 idempotency key를 process-local future로 임의 coalesce하지 않는다. 첫 구현은 기존 DB idempotency 의미를 보존하고, in-flight duplicate가 어떤 표면을 내는지는 기존 transaction 규칙과 focused 시험으로 고정한다.

### 4.3 release 경계와 재진입

permit은 placement 함수 반환이 아니라 **root DB transaction의 commit 또는 rollback 완료 뒤** 정확히 한 번 반환한다. `BoundDatabase`나 savepoint에서 함수가 먼저 반환돼도 outer transaction이 lock을 보유할 수 있으므로 조기 release는 사양 위반이다.

- root transaction context에 release callback을 등록하고 commit, DomainError, 일반 exception, `CancelledError`, `BaseException` rollback에서 모두 실행한다.
- 같은 root transaction이 같은 tenant+project의 canonical primitive에 재진입하면 permit을 중복 차감하지 않는 reentrant token을 사용한다.
- savepoint rollback은 root permit을 반환하지 않는다. root transaction 종료만 반환한다.
- process crash 때 local registry는 사라지지만 DB connection 종료·transaction rollback은 기존 복구 경계다. 이 동작을 durable permit 복구라고 부르지 않는다.
- count가 0이 되면 registry entry를 제거한다. 정상·오류·취소 뒤 permit 및 registry 잔존은 0이어야 한다.

root finalizer를 `BoundDatabase`에 안전하게 연결할 수 없으면 구현을 진행하지 않고 설계 finding으로 되돌린다.

## 5. 오류와 계측 표면

상한 초과는 새 오류 코드를 만들지 않는다.

- 공개 표면: `RES-0007`, HTTP 503, `retryable=true`
- 공개 응답에 semaphore, N, queue depth, process ID, SQLSTATE 또는 재시도 시간을 추가하지 않는다.
- 내부 reason은 `project-semaphore-limit`처럼 식별자 없는 값으로 구분한다.
- 내부 metric: `limit`, `inUseBefore`, `outcome=acquired|rejected|released`, `holdMs`, `releaseCause=commit|rollback|cancel|exception`, `reentrant`, `registryEntries`.
- **permit 대기 상한은 논리적으로 0ms**다. `try_acquire`는 permit 반환을 기다리는 queue/future를 만들지 않고 현재 count가 N이면 즉시 거절한다. registry의 원자적 count 갱신 wall-clock은 `admissionElapsedMs`로 별도 관측하되 permit wait로 부르지 않는다. I/O, sleep, DB call 또는 event-loop 재대기를 포함하면 구현 결함이다.

성능 판정에서 semaphore 거절을 SQL timeout과 분리해 보고하되 숨기지 않는다. 외부 실패 게이트는 `semaphore reject + 55P03 + 57014` 전체를 센다. 즉 SQL timeout을 빠른 503으로 이름만 바꾸어 성공으로 판정할 수 없다.

## 6. 다중 process·다중 CP 한계

process-local registry가 P개이면 같은 project가 동시에 획득할 수 있는 permit은 최악의 경우 `P×N`이다. worker process 재시작, rolling deployment, 다른 CP host는 서로의 count나 순서를 보지 못한다. 따라서 이 옵션은 다음을 보장하지 않는다.

- 전역 N, 전역 FIFO, fairness, starvation 방지
- 다른 process로 재시도된 요청의 admission 일관성
- multi-CP failover 동안의 queue 보존 또는 permit handoff

현재 단일 CP 실험에서 유효해도 운영 확장 근거가 아니다. 다중 인스턴스가 필요하면 durable coordinator/advisory-lock/외부 queue 중 하나를 별도 ADR로 결정하고, fencing·복구·가용성 영향을 다시 검토한다. 이 카드에서 분산 semaphore로 확장하지 않는다.

## 7. 보존해야 할 불변식

| 불변식 | 요구사항 |
|---|---|
| fencing / epoch | semaphore는 final epoch·heartbeat·channel·skew 재검사를 건너뛰지 않는다. token 발급 순서와 stale epoch 거부는 기존 DB transaction이 소유한다. |
| idempotency | commit된 exact replay는 permit 없이 같은 응답을 반환하고 changed-body는 409다. 새 시도의 semaphore reject는 idempotency·Lease·event 잔존 0이다. |
| 원자성 / no-overbooking | permit은 ceiling·offered·active 계산을 대신하지 않는다. Lease, event, ledger는 기존 한 transaction에서 모두 commit 또는 rollback한다. |
| RLS | canonical tenant+project를 DB 권한 확인 뒤 얻고 다른 tenant의 permit 상태로 접근·차단하지 않는다. |
| 결정성 | candidate 선택, Explain digest, active_total/fit 재검사는 기존 로직을 유지한다. semaphore 도착 순서를 placement 결정 입력으로 쓰지 않는다. |
| rollback | flag off는 즉시 신규 permit 경로를 우회하며 정상 commit된 Lease를 삭제하거나 local count를 durable state로 복원하지 않는다. |

## 8. 시험 계획

### 8.1 PG-free 단위 시험

1. flag off 경로가 registry와 metric을 만들지 않고 기존 함수를 그대로 호출한다.
2. 선택한 N=4에서 네 신규 시도는 획득하고 다섯 번째는 permit queue 생성 없이 즉시 기존 RES-0007 표면이다. N=1/3 경계도 parameterized 단위 시험으로 고정한다.
3. tenant A/project X, tenant B/project X, tenant A/project Y는 독립이다.
4. 정상 commit, DomainError, 일반 exception, cancellation, BaseException에서 permit이 정확히 한 번 반환된다.
5. 같은 root transaction 재진입은 한 permit만 쓰고 savepoint rollback은 조기 release하지 않는다.
6. exact replay는 permit 0개, changed-body는 409이며 신규 reject는 idempotency 잔존 0이다.
7. metric·log에 tenant/project/principal/idempotency key, DSN, PID/XID, SQL parameter 또는 비밀이 없다.
8. 독립 registry 두 개가 각각 N을 허용해 전역 상한이 `2N`이 될 수 있음을 부정 대조군으로 고정한다.

### 8.2 실 PostgreSQL focused 시험

1. flag off legacy/candidate 동등성과 기존 replay/fencing/RLS/no-overbooking을 재확인한다.
2. 선택한 N개의 root transaction이 permit을 보유한 동안 N+1 신규 요청은 limits lock 도달 전에 RES-0007을 반환한다. permit wait queue와 waiter task는 0이다.
3. commit·rollback·cancel 뒤 다음 요청이 permit을 획득하고 registry 잔존은 0이다.
4. `BoundDatabase` outer transaction이 끝나기 전에는 permit이 반환되지 않으며 attempt/savepoint 경계에서 누수·중복 release가 없다.
5. saturated project의 commit된 exact replay와 changed-body 409, 다른 project·tenant의 독립 진행을 확인한다.
6. epoch flip, membership/grant revoke, stale heartbeat, ceiling/offer 감소, resource fit 실패가 기존 오류와 rollback을 유지한다.

시험은 disposable DB와 단일 파일만 사용한다. 구현 승인 전에는 작성·실행하지 않는다.

### 8.3 20동시 성능 판정

sampler-off candidate 1500×1 결과로 첫 실험값 N=4를 정했다. 다음 구현 승인 뒤 같은 code SHA, PostgreSQL, 합성 Node, barrier 조건에서 legacy(flag off)와 candidate-B(flag on, N=4, lock budget 기본 500)를 각각 20동시×3회 순차 실행한다. N=3 lower arm, N=5 이상, 50동시, 물리 5노드는 별도 승인 없이는 실행하지 않는다.

세 판정 조건은 Card24와 동일하되 semaphore 거절을 누락하지 않는다.

1. candidate의 외부 실패 합계 `semaphore reject + 55P03 + 57014`가 legacy의 `55P03 + 57014` 이하
2. candidate 전체 요청(all requests) P95 3회 중앙값이 legacy 대비 비악화
3. candidate 성공 요청의 post-acquire hold P95 3회 중앙값이 legacy 대비 비악화

성공/실패, semaphore reject, SQLSTATE별 timeout, all/success-only P50/P95/max, acquire/hold, in-use max, permit hold, registry residue, arrival spread, queue depth와 불변식을 JSON/JUnit에 모두 남긴다. 빠른 거절로 all-request P95가 낮아져도 조건 1을 실패하면 승격하지 않는다. 세 조건 외에도 fencing/RLS/no-overbooking/replay/rollback 중 하나라도 깨지면 즉시 실패다.

## 9. 롤백과 인계

- 롤백은 `placement_project_semaphore_enabled=false`로 신규 admission을 즉시 우회하는 것이다.
- local registry는 drain 뒤 폐기한다. 강제 초기화로 진행 중 transaction의 permit을 조기 반환하지 않는다.
- migration·durable state가 없으므로 DB cleanup이나 정상 Lease 삭제는 없다.
- deadlock, permit leak, early release, cross-tenant coupling, replay/409 변화, 새 공개 오류 표면이 필요하면 구현을 중단하고 결정 요청으로 되돌린다.

owner는 Codex, reviewer는 Claude, 구현·실측 승인자는 코디네이터다. 현재 handoff는 **docs-only 사양 검토 대기**이며 S05-DB `review`, flag off, 기본 lock budget 500ms를 유지한다. 근거는 [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[s05-bprime-card24-4c8a7363.json]], [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]]다.

Card25 sampler-off wave 종료 뒤 `inv_test_*` database는 0건이었다. 실행 전부터 있던 `inv_app_*` role 2건은 종료 뒤에도 2건으로 같아 신규 role 잔존은 0이다. [[s05-card25-sampler-off-6c389a1d.json]].
