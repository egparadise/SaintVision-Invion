---
doc_id: "ERR-DESIGN-008"
title: "프로젝트 배치 잠금과 transaction timeout 경합"
version: "1.3.2"
status: "accepted-mitigation-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T05:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["placement", "concurrency", "lock-timeout", "statement-timeout", "postgresql", "S05-DB", "F-S05-01", "F-S05-02", "F-S05-03"]
---

# ERR-DESIGN-008 프로젝트 배치 잠금과 transaction timeout 경합

> [!warning] 상태
> 코디네이터 결정 (b): legacy 유지 · `placementShortCommit` 기본 off · S05-DB `review` · 단계 3 미통과 · 50동시와 물리 5노드 미측정. 카드 18 P1/P2 대칭 계측 완료, Claude 카드 20 검토 대기.

## 카드 18 P1/P2 — 대칭 계측과 SQL statement 귀속

legacy의 phase mark를 project limits 획득 뒤로 옮기고, 그 전 project+limits 획득 구간을 `placement-legacy-lock-wait` client elapsed로 분리했다. candidate도 같은 방식으로 limits 획득 뒤부터 hold를 잰다. 개발 PC·합성 Node 1개·실 PostgreSQL·20동시·각 1회 결과는 다음과 같다.

| 모드 | 성공/실패 | 요청 전체 P95 | 획득 후 hold P95 | 획득 client elapsed P95 | timeout |
|---|---|---:|---:|---:|---|
| legacy | 20/0 | 1885.489ms | 289.365ms | 1453.658ms | 0 |
| candidate fail-fast | 8/12 | 1054.907ms | 170.766ms(성공 8개) | 528.705ms | `55P03` 12 |

SQL observer는 candidate 12개 실패를 모두 `SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE`에 귀속했다. 두 mode 모두 fencing 유일성과 no-overbooking은 true다. hold 감소 방향은 보이지만 candidate survivor 8개와 legacy 20개를 한 번 비교한 값이므로 성능 통과 증거가 아니다. 외부 timeout 비증가 조건은 0→12로 실패한다.

legacy의 acquire client elapsed가 500ms를 넘는데도 `55P03`이 없는 이유는 카드 18 wave 자체에 대해서는 **미확정**이다. 코드상 mode별 면제는 없고 양쪽 모두 같은 `SET LOCAL lock_timeout=500ms`, `statement_timeout=2s` 경로다. SQL observer elapsed는 server lock wait뿐 아니라 Python thread scheduling과 query return 지연을 포함하고 당시 backend wait-event timeline은 수집하지 않았다.

Claude 카드 20의 커널 무관 PG probe는 가능한 lock queue mechanism을 확인했다. holder chain depth 2에서는 `lock_timeout`이 서로 다른 대기 구간마다 다시 적용돼 waiter가 총 728ms 뒤 성공했고, depth 3에서는 앞선 holder 시간이 한 구간에 누적돼 각 holder가 500ms 미만이어도 `55P03`이었다.

Card19 실제 legacy 20동시 wave는 arrival spread 0.793ms, max project-lock waiter 19, blocking chain depth 1, timeout 0이었다. 따라서 이 wave는 19 waiter가 현재 holder를 직접 기다리는 fan-in이지 카드 20의 depth≥3 holder chain이 아니다. request/acquire/hold P95는 2142.809/1588.193/151.225ms였지만 `55P03`은 0건이었다. `log_lock_waits=off`이고 server log를 읽지 않았으므로 원인은 여전히 **미확정**이다. holder 교체마다 실제 wait segment와 `lock_timeout` clock이 다시 시작돼 각 segment는 500ms 미만이고 누적 client elapsed만 길어졌다는 가설로 좁히며, `log_lock_waits=on` 상관 재실행은 별도 카드로 제안한다. [[2026-09-23_01-05-00_KST_F-S05-02_57014_원인분리_Codex]], [[2026-09-23_05-55-00_KST_S05_legacy_큐깊이_실측_Codex]], [[s05-symmetric-metrics-card18]], [[s05-legacy-queue-card19]].

다음 후보는 limit-row migration이 아니라 candidate의 lock-timeout 예산 또는 project별 queue 깊이 상한이다. Card19은 요청 arrival/completion timeline, parameter-free statement class, backend `wait_event`, blocking graph와 `log_lock_waits` 설정을 같은 20동시 wave에서 수집했다. server log 상관과 candidate 정책은 Claude 검토와 별도 결정 전 구현·실행하지 않는다.

계측 제한도 오류 설계 경계에 포함한다. `BoundDatabase` stale retry는 caller-owned outer transaction의 final phase만 방출해 attempt 1 hold가 현재 집계되지 않고, 운영 `app.py`는 `placement_metric_sink`를 주입하지 않으며 logger fallback은 candidate flag on에서만 동작한다. 따라서 nested retry의 attempt coverage와 기본 legacy 운영 metric은 불완전하고, benchmark sink 수치를 운영 telemetry로 승격할 수 없다.

## F-S05-03 — 경합 재배치

옵션 1 구현은 speculative read와 선택 Node/Resource final commit을 분리하고, canonical admission/prepared primitive, current active fit 재계산, stale winner savepoint rollback·재계획, lock-hold 계측을 넣었다. 응답·replay·fencing·RLS·rollback 불변식은 실 PG 9 passed, model-retry의 caller-owned transaction 경로는 1 passed/exit 0으로 유지됐다.

20동시 3회 옛 기준선에서 commit lock-hold P95는 legacy **1399.883ms**와 candidate **122.126ms**로 기록됐지만, legacy만 잠금 대기를 포함한 비대칭 수치이므로 감소 통과 주장을 철회한다. 요청 성공 P95 중앙값은 **1771.763ms → 1697.737ms**, 74.026ms(약 4.2%) 차이였다. 두 모드 모두 20/20 × 3, 외부 실패 0이지만 SQL 진단은 legacy `55P03+57014` 0/0/0 대비 candidate 14/10/11이었다. 전부 `SELECT * FROM inv.project_resource_limits ... FOR UPDATE`의 `55P03`이며 내부 최대 3회 retry가 외부 실패를 숨겼다.

따라서 옵션 1은 경합을 없애지 않고 project mutex에서 limit row로 **재배치**했다. 옛 hold 감소 조건은 비대칭이라 미확정이고 timeout 합계 감소 조건도 미충족이므로 flag는 기본 off, S05-DB는 `review`, 5노드·50동시 승격은 없다. report schema v1.5는 legacy/candidate acquisition elapsed와 post-acquire hold, parameter-free SQL statement를 분리한다. 결정 (b)에 따라 limit-row 입도/usage migration은 보류한다.

## 문제와 인과 정정

`PlacementStore.reserve`는 idempotency와 Run 뒤 project row·project limits·후보 Node/Resource를 잠그고 권한·admission·관측·capacity를 검증한 다음 Lease·event·idempotency 응답을 한 transaction으로 기록한다. 원자성과 ceiling에는 안전하지만 같은 project의 독립 요청을 긴 임계구역에 모은다. placement는 이 잠금들을 잡은 뒤 `LeaseStore._reserve_locked`로 들어가 project/limits/resources를 다시 잠그며, direct lease 경로와 네 `require_*` 검사 순서도 다르다.

v1.0의 “project 직렬 대기가 15초 freshness를 넘겨 `RES-0003`을 만든다”는 인과는 철회한다. `inv/db.py`는 모든 transaction에 `lock_timeout=500ms`, `statement_timeout=2s`를 적용하므로 현재 관측된 경합은 15초보다 먼저 timeout 표면에 도달한다.

PR #74 검토의 “`LockNotAvailable` 미매핑이므로 새 ProblemDetails 계약이 필요하다”는 전제도 실측으로 정정한다. 현 코드는 `LockNotAvailable`, `QueryCanceled`, `DeadlockDetected`를 이미 `RES-0007`, HTTP 503, `retryable=true`로 매핑한다. 누구의 오류를 비난하기 위한 기록이 아니라 새 시험이 두 가설을 동시에 갱신한 결과다.

## 실측 근거

- 단일 lock 주입: `tests/integration/test_placement.py::test_project_lock_timeout_is_retryable_res_0007_problem` **1 passed / exit 0**. held project row + `pg_sleep(1.2)`에서 `LockNotAvailable`, SQLSTATE `55P03`, `RES-0007` / 503 / retryable, Lease·idempotency 잔존 0.
- 3동시: 3/3 성공 × 2, 성공 worst P95 **861.651ms**, 오류 0.
- 10동시: 10/10 성공 × 2, 성공 worst P95 **1,738.762ms**, 오류 0.
- 20동시: 1라운드 **17 성공 / 3 실패**, 성공 P95 **2,417.912ms**. 실패 3건은 모두 `QueryCanceled`, SQLSTATE `57014` statement timeout, `RES-0007` / 503 / retryable. fencing 유일성·no-overbooking true, active 합계 기대값 일치.
- 50동시와 물리 5노드: **미실행·미측정**. 20동시 peak working set도 감시기 연결 전에 프로세스가 끝나 **미측정**이다.

따라서 현 코드의 측정된 실패 모드는 **잠금 뒤 statement timeout 2초 도달**이다. lock timeout 주입과 20동시 경합은 원인 SQLSTATE가 각각 `55P03`과 `57014`로 다르지만 공개 표면은 기존 `RES-0007`로 같다. 이는 AC-05 합격 증거가 아니며 S05-DB는 `review`를 유지한다.

## 설계 영향

- 옵션 1은 project row 제거가 아니라 final reserve transaction과 project/limit/node/resource **잠금 보유 시간**을 줄여야 한다. 요청 총 지연과 별도로 lock hold p50/p95/max를 계측한다.
- bounded retry는 새 코드가 아니라 기존 `RES-0007 && retryable=true`를 기준으로 하며 exact idempotency key/body, 새 transaction, 재권한·재admission·재freshness·재fit 검증, 시도/총시간 상한을 요구한다.
- speculative winner의 digest만 비교하지 않는다. final lock 아래 current `active_total`, project ceiling, offered fit을 다시 계산하고 바뀌면 후보 계산부터 재시도한다.
- 단일 Node pool에서는 공통 Node/Resource row가 병목이라 project row 완화 이득이 0일 수 있다. 다중 Node에서 선택 lock 집합이 갈리는 경우만 병렬화 이득을 기대한다.
- placement와 direct lease는 `leases.py:176`의 중복 project lock과 네 `require_*` 순서를 하나의 canonical commit primitive·lock order로 통일한다.
- freshness 창 확대나 요청 진입 시각 동결은 경합과 2초 timeout을 고치지 않고 stale 결정을 허용하므로 기각한다.

## 결정 문서와 소유 경계

상세 옵션·불변식·시험·롤백은 [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.1과 [[2026-09-23_00-18-00_KST_S05_timeout_실측과_결정초안_v1_1_Codex]]에 있다.

- owner: Codex — 커널 설계·구현·회귀시험
- reviewer: Claude — fencing/epoch·원자성·교착·RLS·5노드 검증 독립 검토
- decision: 코디네이터 — C 조건부 보류 뒤 v1.1 재검토 결과로 A/B/C 재결정
