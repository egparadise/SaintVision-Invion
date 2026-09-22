---
doc_id: "CODEX-S05-BPRIME-LOCK-BUDGET-SPEC-001"
title: "S05 B-prime candidate limits 잠금 예산 구현 사양"
version: "1.0.0"
status: "proposed-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T09:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "candidate", "lock-timeout", "statement-timeout", "specification"]
---

# S05 B-prime candidate limits 잠금 예산 구현 사양

> [!warning] 실행 권한 없음
> 이 문서는 [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.4의 B′를 구현 가능한 카드로 분해한 **사전 사양**이다. Claude Card24 의견과 코디네이터의 별도 구현·실측 승인 전에는 코드 변경, candidate 실행, 20동시 부하, 5노드·50동시 승격을 하지 않는다. 현재 정본은 `placementShortCommit=false`, 공통 `lock_timeout=500ms`, S05-DB `review`다.

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
| 실험값 | `1500` — Card21의 tuple FIFO 약 500ms cascade를 완화하는 첫 측정점이며 최종 운영값이 아니다. |
| 유효 범위 | `1 <= value < 2000`, `bool`은 거부. 상한은 같은 statement의 `statement_timeout=2000ms`보다 반드시 작다. |
| 활성 조건 | `placement_short_commit is True`인 candidate limits lock에서만 읽는다. flag off/legacy에서는 값을 주어도 500ms 공통 경로가 유지돼야 한다. |
| 외부 노출 | 첫 구현·측정 카드는 공개 API와 production `INV_API_CONFIG` 허용 key를 늘리지 않는다. benchmark/test harness만 명시적으로 주입한다. 운영자 설정 노출은 성능 판정 뒤 별도 결정한다. |

따라서 “기본 500 유지”는 새 설정을 생략한 기존 constructor, production app factory, legacy, direct lease 모두에 대해 byte-for-byte 설정 동등성을 뜻한다. candidate B′ 측정만 benchmark의 명시적 opt-in 인자로 `1500`을 주입한다. 알 수 없는 production config key는 현재처럼 fail closed한다.

## 3. SQL 적용 경계

현재 transaction 시작 순서는 tenant GUC 뒤 `SET LOCAL lock_timeout='500ms'`, `SET LOCAL statement_timeout='2s'`다. B′는 이 공통 순서를 유지하고 candidate의 limits lock 직전에만 `set_config('lock_timeout', '<budget>ms', true)`로 session-local이 아닌 **transaction-local** 값을 바꾼다.

1. candidate savepoint와 idempotency/Run/admission 검사를 현재 순서로 수행한다.
2. `placement-limit-row-wait` phase를 표시한다.
3. candidate 예산이 500ms와 다를 때 limits lock 직전에 transaction-local `lock_timeout`을 적용한다.
4. `SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE`를 수행한다.
5. 획득 성공 직후, Node/Resource 등 다음 writer lock 전에 `lock_timeout`을 공통 500ms로 복원한다.
6. limits lock이 timeout이면 기존 savepoint/outer transaction unwind로 끝낸다. 실패한 transaction에서 복원 SQL을 억지로 실행하지 않으며, 새 request/transaction은 처음부터 공통 500ms를 다시 설정한다.

복원 뒤의 resource lock, canonical reserve, stale winner savepoint 재계획은 모두 다시 500ms다. B′가 transaction의 나머지 lock wait까지 1500ms로 넓히는 구현은 사양 위반이다. nested `BoundDatabase`에서도 attempt 사이 설정 누출이 없어야 한다.

## 4. 2초 statement timeout과 오류 표면

PostgreSQL `statement_timeout`은 transaction 총시간이 아니라 각 statement의 시작부터 끝까지 적용된다. 같은 limits `SELECT ... FOR UPDATE`에서는 다음 관계를 고정한다.

- 한 lock wait segment가 candidate 예산 1500ms를 넘으면 `55P03`이 2초보다 먼저 발생해야 한다.
- holder가 바뀌어 `lock_timeout` clock이 구간별로 다시 시작되더라도, 한 statement의 누적 실행 시간이 2초에 닿으면 `57014`가 먼저 발생할 수 있다.
- limits 획득 뒤 후속 statement는 새 2초 statement budget을 갖지만 lock budget은 복원된 500ms다.
- `55P03`과 `57014`는 모두 현재 `Database.transaction` 매핑을 통해 `RES-0007`, HTTP 503, `retryable=true`다. SQLSTATE는 진단 evidence에만 남고 공개 ProblemDetails에 새 필드를 추가하지 않는다.

1500ms는 2초까지의 남은 “transaction 여유 500ms”라는 뜻이 아니다. 같은 limits statement 안에서 lock timeout이 statement timeout보다 먼저 작동하도록 둔 명목 차이다. 이 관계를 오기한 측정은 무효다.

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
4. **statement boundary:** 비-lock 2초 초과 또는 구간별 lock clock reset 대조에서 `57014` → 같은 `RES-0007` 표면을 확인한다. `55P03`과 `57014`를 합쳐 쓰지 않고 evidence에는 구분한다.
5. **restore:** limits 획득 직후와 stale 재계획 attempt 2 시작에서 `SHOW lock_timeout`이 500ms다. 후속 resource lock에 1500ms가 누출되지 않는다.
6. **invariants:** exact replay, changed-body 409, fencing/epoch, no-overbooking, RLS, rollback, direct lease 혼합의 기존 focused 시험을 그대로 통과한다.

실 PG 시험은 disposable DB만 사용하고 단일 파일로 실행한다. 20동시 성능 wave는 위 기능 시험과 분리하며 Claude 의견·코디네이터 승인 뒤에만 수행한다.

## 7. 성능 판정 게이트

승인되면 같은 code SHA·같은 PostgreSQL·합성 Node 조건에서 legacy(flag off, 공통 500)와 candidate(flag on, limits 1500)를 **20동시 각 3회** 순차 실행한다. 필요하면 candidate 500을 calibration으로 추가하되 합격 분모를 바꾸지 않는다. 50동시와 물리 5노드는 실행하지 않는다.

다음 세 조건을 모두 만족해야 후속 검토로 보낸다.

1. candidate의 외부 `55P03 + 57014` 합계가 legacy 이하
2. candidate request P95 3회 중앙값이 legacy 대비 비악화
3. candidate 성공 request의 post-acquire hold P95 3회 중앙값이 legacy 대비 비악화

성공 수, limits wait P95 또는 hold 감소 하나만으로 통과시키지 않는다. 각 wave의 성공/실패, SQLSTATE별 수, effective budget, request/limits-wait/post-acquire-hold P50/P95/max, queue-depth 표본, invariants, process exit를 같은 JUnit/JSON schema에 남긴다. 어느 조건이든 실패하면 flag off·S05 `review`를 유지하고 B′를 승격하지 않는다.

## 8. 롤백과 중단 기준

- 즉시 롤백은 candidate 실험 인자를 제거해 500ms로 되돌리고 `placementShortCommit=false`를 유지하는 것이다.
- migration·schema·data backfill이 없으므로 DB rollback이나 Lease 삭제는 없다.
- 새 오류 코드/응답 field/header, production config key, internal retry, lock mode 변경이 필요해지면 B′ 범위를 중단하고 별도 계약 결정을 요청한다.
- deadlock, fencing 중복, no-overbooking/RLS/rollback 위반, 2초를 넘기는 설정, 후속 lock으로 budget 누출 중 하나라도 관측되면 성능 수치와 무관하게 실패다.

## 9. 인계

- owner: Codex — 승인 뒤 구현·focused 회귀·20×3 측정
- reviewer: Claude — Card24 기전/정책 검토 뒤 이 사양의 SQL 범위·timer 관계·반례 독립 검토
- decision: 코디네이터 — 구현/실측 시작과 B′ 승격 여부

현재 handoff는 **설계 검토 대기**다. 구현·측정은 아직 시작하지 않았다.
