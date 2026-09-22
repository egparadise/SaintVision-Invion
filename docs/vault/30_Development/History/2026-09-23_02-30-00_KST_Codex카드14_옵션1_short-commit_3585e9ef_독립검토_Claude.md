---
doc_id: "CLAUDE-REVIEW-CODEX-CARD14-SHORT-COMMIT-3585E9EF-001"
title: "Codex 카드 14 착지 3585e9ef(F-S05-01 옵션 1 speculative read + short commit, flag 기본 off) 독립 검토 — 판정: 조건부 승인(코드 변경 없음, 시험 보강 2건 요청: 되살림 2건이 모두 살아남음) — F-S05-03 후속 의견: fail-fast 우선, limit-row 입도는 대기 p95 계측 후"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T02:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3585e9ef"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "S05", "placement", "short-commit", "feature-flag", "F-S05-03", "claude"]
---

# Codex 카드 14 `3585e9ef` 독립 검토 (2026-09-23, 02:30 KST)

대상: `inv/placement.py`(+479: `_speculate`·`_selected_guard`·`_locked_fit`·`_reserve_short_commit`, flag 분기) · `inv/db.py`(+202: `placement_short_commit` strict bool, `_ObservedConnection` SQL observer, `record_placement_metric`, `BoundDatabase` 전파) · `inv/leases.py`(+62: `_admit_locked`·`_reserve_prepared_locked` 공통 primitive) · `app.py`(+2 설정 배선) · `tests/integration/test_placement_short_commit.py`(10) · `test_model_retry.py`(+1) · 하네스 v1.3 · [[2026-09-23_01-40-00_KST_S05_short-commit_구현과_F-S05-03_Codex]] · Evidence `s05-short-commit-stage3-a0f7dba2.json`. 측정 트리 `D:\Project\sv-measure-claude`를 **`3585e9ef`에 고정**(porcelain 0), 실 PG(disposable DB), 시작 전 `codex-worker-status.md` 통보.

## 1. 판정: **조건부 승인** — 코드는 sound, flag 기본 off 유지; **시험 보강 2건(F-R1·F-R2) 수정 요청**(구현 변경 아님). F-S05-03 의견 §6.

| # | 발견 | 성격 |
|---|---|---|
| **F-R1** | 되살림 A: `_locked_fit`(placement.py:375)의 `offered - active_total` 재계산에서 `active_total`을 제거(=잠금 아래 fit 재계산 무력화)해도 **10/10 passed**. 이유: `_reserve_prepared_locked`(leases.py:247·268~272)의 ceiling·`active_total+amount>offered` 검사가 **여전히 남아** 이중 예약을 막는다(defense in depth, 제품 안전). 그러나 설계의 핵심 주장 "final commit에서 fit을 재계산해 stale winner를 재계획"은 **어느 시험에서도 결정 요인이 아니다** — `test_active_total_change_recomputes_fit…`의 경쟁자는 1단위라 fit이 깨지지 않고, `…share_project_ceiling`은 ceiling 검사(prepared 층)가 잡는다 | **시험 갭(비차단)** — 요청: 경쟁자가 `offered - need + 1`을 선점하는 tight-fit 케이스로 `_locked_fit`이 need 미달을 감지해 재계획(또는 `RES-0001`)하는지 고정; 단위 시험에서 `_locked_fit` 직접 호출로 되살림 KILLED 확인 |
| **F-R2** | 되살림 B: `_reserve_short_commit`의 attempt별 `with conn.transaction():`(savepoint, placement.py:581)을 `nullcontext`로 바꿔도 **10/10 passed**, `test_bound_candidate_rolls_back_stale_attempt_to_savepoint` 포함. 이유: 그 시험의 stale 경로는 Python `_StalePlacement`(SQL 오류 없음)라 트랜잭션이 abort되지 않아 savepoint 유무가 결과에 안 나타난다. savepoint가 실제로 필요한 경우 = **caller-owned 트랜잭션(`BoundDatabase`, model-retry) 안에서 attempt 1이 SQL 오류(55P03 limit-row)로 abort된 뒤 attempt 2** — 이 경로는 시험이 없다 | **시험 갭(비차단)** — 요청: BoundDatabase에서 다른 연결이 limit row를 `pg_sleep`로 잡아 attempt 1을 `55P03`로 만들고 해제 뒤 attempt 2가 성공하는 케이스(savepoint 없으면 `InFailedSqlTransaction`으로 실패해야 함) |
| F-R3 | "flag off 경로 무변경"은 **바이트 동일이 아니다**: legacy `reserve`도 `lock_run`/`_reserve_locked` 직접 호출 대신 `_admit_locked`·`_reserve_prepared_locked`로 리팩터됐고 `_reserve_locked`의 project/limits/resources lock 순서 코드가 primitive로 이동했다. 동작 동등성은 아래 flag-off 실 PG로 확인(§2). 보고서 문구를 "동일 primitive로 리팩터, 동작 동등"으로 정정 권장 | 문서 |
| F-R4 | 단계 3 표의 55P03 14/10/11(35건)은 **내부 3회 retry × 20 클라이언트의 limit-row 경합 증폭** — 요청 P95 개선 4.2%(1771→1697ms)에 그친 이유. hold p95 1400→122ms는 잠금 보유 감소를 증명하지만 병목이 limit row 획득 대기로 **이동**했음을 Codex 스스로 F-S05-03으로 정직히 기록 | 관찰 |

## 2. (a) flag off 동등성 — 실 PG

| 실행 | 결과 |
|---|---|
| `test_placement_short_commit.py::test_flag_defaults_off_and_candidate_keeps_response_and_idempotency_contract` | 기본 off 단언 + 응답 키 `{runId, placement, leases}`·lease 2·exact replay·changed body `IDEM-0001` (10 passed 안에 포함) |
| flag off 경합·abort: `tests/integration/test_postgres.py` + `test_reservation_aborts.py` | **19 passed / 0 failed**, 42s(리팩터된 legacy primitive를 실 PG 경합·fencing·epoch·rollback 경로로 관통) |
| flag off 3동시 벤치 1회(legacy 경로) | **1 passed**: `benchmarkComplete/deterministicExplainAndSnapshot/uniqueFencingTokens/noOverbooking = True`, 성공 P95 1418ms |
| `tests/integration/test_placement.py` | 1 passed / 12 skipped("Real Linux Docker runtime explicitly enabled only in isolated CI" — node-runtime 게이팅, hosted Core 자리) |

## 3. (b) flag on 반례 시험 — 실 PG

`tests/integration/test_placement_short_commit.py` **10 passed / 16.5s**: 기본 off·응답/replay 계약 · legacy project mutex 미대기 · guard 변경 시 winner 폐기·재계획 · active_total 변화 시 fit 재계산(winner 유지) · BoundDatabase savepoint · grant 회수 `AUTH-0030` fail-closed · epoch flip `LEASE-0004` fail-closed · event 실패 시 lease/ledger rollback · direct lease와 ceiling 공유(성공 정확히 1, `RES-0001|RES-0007`) · 타 tenant RLS `AUTH-0030`. `test_model_retry.py::test_retry_short_commit_flag_preserves_atomic_response_and_replay` **1 passed**. 되살림 결과는 §1 F-R1/F-R2 — **2건 모두 생존**(코드가 아니라 시험의 무게 문제).

코드 정독으로 확인한 것: flag 분기 `getattr(self.db, "placement_short_commit", False)`(placement.py:99, strict bool은 db.py:86~88) · final commit 잠금 = idempotency → Run → `_admit_locked`(require_execution→recovery→handoff→start) → limits `FOR UPDATE`(대기 시간 계측) → **선택 node의 resource만** `lock_resources`(`speculative["resourceIds"]` = 선택 node 자원, :530~538) → grant 재검사 → `_selected_guard` digest(membership·limits version/cpu/memory·resource offered/capacity·node status/heartbeat/skew/epoch·snapshot received_at/epoch/channel version·channel enabled/cert) → `_locked_fit` → `_reserve_prepared_locked`(ceiling+offered 재검사) → event → `_save` · `_StalePlacement`와 `RES-0007 retryable`만 최대 3회, 소진 시 기존 `RES-0007` · 새 DomainError 코드 **0**(AUTH-0030·AUTH-0060·RES-0001/0003/0004/0008 전부 기존) · SQL observer는 statement template·phase·SQLSTATE만(파라미터·식별자 없음).

## 4. (c) 계약 표면

`git diff 2bb36828 3585e9ef -- contracts/ packages/ inv/generated/ node-agent/wire/` → **0 파일**. `export_schemas --check` 58/58. ProblemDetails 코드 신설 없음. ✔

## 5. (d) 게이트 (3585e9ef 정확 트리)

`check_docs` **847** exit 0 · `check_contract_bindings` 54/19 exit 0 · `check_response_freshness` exit 0 · `check_doc_single_source --ratchet` exit 0 · `check_ontology` exit 0 · PG-free `test_route_coverage` + `test_serving_anchors` + `test_model_registry_config` + `test_placement_benchmark_tool` **81 passed**. ✔

## 6. F-S05-03 후속 의견 (limit-row 잠금 입도 vs fail-fast + 클라이언트 retry)

**fail-fast를 먼저.** 근거: (1) 단계 3의 timeout 35건은 20 클라이언트 × 최대 3회 내부 retry가 같은 limit row를 두드린 **증폭**이다 — 내부 retry를 빼면 경합 압력이 최대 3배 줄고, 실패는 기존 `RES-0007`/503/`retryable=true` 계약으로 **즉시** 클라이언트에 가므로 계약 변경 0; (2) ceiling 원자성(`used + needed ≤ limit`을 limit row 아래에서 계산)이 그대로 보존된다; (3) 작다 — `_reserve_short_commit`의 `attempt < 3` 분기 하나. 조건: 클라이언트 관점 P95는 retry 포함으로 재측정하고, limit-row **대기 p50/p95/max·획득 시도 수**(report v1.3 필드)를 함께 남겨 다음 단계 근거로 쓴다. **limit-row 입도(kind별 행 분할·usage counter CAS)는 그 다음** — migration + release/restore/reconcile 동기화 + ceiling 원자성 증명이 필요한 큰 변경이라, fail-fast 뒤에도 limit-row 대기 p95가 예산을 넘을 때만.

## 판정
**조건부 승인** — 구현은 코드·게이트·실 PG(flag off 19+1+10, flag on 10+1)에서 sound하고 계약 표면 변경 0, flag 기본 off 유지. 조건: F-R1(tight-fit 되살림 시험)·F-R2(BoundDatabase 55P03 savepoint 시험) 보강 착지 — 그 전까지 "반례 9+1을 잡는다"는 문구는 "9+1 시험 통과, 그중 fit 재계산·savepoint 2건은 되살림 미확인"으로. 후속은 fail-fast 우선(§6). S05-DB review 유지, flag 운영 활성 없음.
