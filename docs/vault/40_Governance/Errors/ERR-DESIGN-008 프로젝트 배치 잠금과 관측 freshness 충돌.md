---
doc_id: "ERR-DESIGN-008"
title: "프로젝트 배치 잠금과 transaction timeout 경합"
version: "1.1.0"
status: "decision-deferred"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T00:18:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["placement", "concurrency", "lock-timeout", "statement-timeout", "postgresql", "S05-DB", "F-S05-01"]
---

# ERR-DESIGN-008 프로젝트 배치 잠금과 transaction timeout 경합

> [!warning] 상태
> 코디네이터 결정 C(조건부 보류) · 개발 PC 실 PG 20동시에서 현 실패 모드 측정 · 50동시와 물리 5노드 미측정 · Claude v1.1 재검토 전 구현 금지

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
