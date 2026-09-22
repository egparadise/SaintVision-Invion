---
doc_id: "CLAUDE-REVIEW-CODEX-CARD16-FAIL-FAST-A28915BC-001"
title: "Codex 카드 16 착지 a28915bc(fail-fast + F-R1·F-R2 시험 보강) 독립 검토 — 판정: 승인(코드·시험·게이트·계약 표면 0, 되살림 3건 KILLED) + 단계 3 판정 '미통과 → flag off·S05 review 유지' 타당 — 단, hold P95 비교는 비대칭 계측(legacy는 대기 포함)이라 '감소 통과'는 미확정 — v1.3 의견: (b) legacy 유지·5노드 후 재판단, (a) limit-row 입도는 원인 미해소"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T02:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a28915bc"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "S05", "placement", "fail-fast", "lock-timeout", "F-S05-03", "mutation-test", "claude"]
---

# Codex 카드 16 `a28915bc` 독립 검토 (2026-09-23, 02:55 KST)

대상: `inv/placement.py`(−8/+7: `_reserve_short_commit`의 `RES-0007` 내부 retry 제거, docstring) · `tests/integration/test_placement_short_commit.py`(+123: F-R1 tight-fit, F-R2 BoundDatabase 55P03→savepoint→재호출, fail-fast 공개 표면) · `tests/integration/test_placement_benchmark.py`(+22: schema 1.4 `timeoutCount`·`timeoutRetryCount=0`·`acquisitionAttemptCount`·`contentionPolicy`) · [[2026-09-23_02-50-00_KST_S05_fail-fast_F-R1_F-R2_Codex]] · [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.3 · Evidence `s05-fail-fast-stage3-a60313a7.json`. 측정 트리 `D:\Project\sv-measure-claude`를 **`a28915bc`에 고정**(porcelain 0), 실 PG(disposable DB) 단일 파일 1회 + 되살림 3회, 시작 전 `codex-worker-status.md` 통보.

## 1. 판정: **승인** — 코드·시험·게이트·계약 표면은 통과. 단계 3 "미통과 → flag off·S05-DB `review` 유지" 판정 **타당**. 관찰 F-C1(비차단이지만 다음 결정의 근거에 영향)은 §4.

| # | 확인 | 결과 |
|---|---|---|
| (a) F-R1 | `_locked_fit`(placement.py:375)에서 `active_total` 제거 → `test_locked_fit_rejects_tight_fit_after_competing_active_total` **1 failed: `DID NOT RAISE _StalePlacement`**, 파일 전체 1 failed/12 passed | **KILLED** ✔ |
| (a) F-R2 | attempt savepoint(placement.py:585 `with conn.transaction():`)를 `nullcontext`로 → `test_bound_candidate_savepoint_recovers_after_fail_fast_limit_row_timeout` **1 failed: `InFailedSqlTransaction`**(두 번째 호출), 파일 전체 1 failed/12 passed | **KILLED** ✔ |
| (b) fail-fast 되살림(추가) | 제거된 `except DomainError: RES-0007 retryable → continue` 분기를 되살림 → `test_limit_row_contention_fails_fast_with_existing_public_contract` **1 failed: `assert 3 == 1`**(limit-row wait metric 3건) | **KILLED** ✔ — 시험이 내부 retry 0을 실제로 고정 |
| (a) F-R3 | Codex 보고 §F-R3: "flag-off는 바이트 무변경이 아니라 shared admission/prepared primitive로 리팩터된 뒤 실 PG에서 동작 동등성을 확인한 경로" | 정정 반영 ✔ |
| 기준 실행 | `test_placement_short_commit.py` **13 passed / 23s** · `test_model_retry.py::…short_commit_flag…` **1 passed** · 패치 복원 후 porcelain 0 | ✔ |

## 2. (b) fail-fast 변형 — 코드 정독

- `_reserve_short_commit` 루프는 `_StalePlacement`만 `continue`(최대 3회 재계획), 그 외 예외는 그대로 전파. limit row `FOR UPDATE`의 `55P03`은 `record_placement_metric(mode="placement-limit-row-wait", attempt, waitMs, outcome="timeout", sqlState)` 뒤 raise → `Database.transaction`의 기존 매핑(db.py:171~181)에서 **`RES-0007`/503/`retryable=true`**, `__cause__`=`LockNotAvailable`. 시험이 code/status/retryable·cause·sqlstate·metric 1건(attempt 1)·idempotency/Lease 잔존 0을 단언(§1 되살림으로 무게 확인).
- 계측: acquired/timeout 양쪽에 `waitMs` 기록(placement.py:603~640), 벤치 v1.4가 `p50/p95/max`·`acquisitionAttemptCount`·`timeoutCount`·`timeoutRetryCount=0`·`contentionPolicy`를 분리. `timeoutRetryCount`를 **상수 0**으로 둔 것은 v1.3 호환용이며 fail-fast에서 정의상 0 — 다만 이 필드는 더 이상 측정값이 아니므로 향후 제거 권장(관찰).
- BoundDatabase(caller-owned transaction)에서는 raw `LockNotAvailable`이 호출자에게 전파되고(시험이 이를 단언) 외부 `Database.transaction`이 매핑한다 — 공개 HTTP 표면은 변하지 않음. 계약 표면: `git diff 1a13e8ed a28915bc -- contracts/ packages/ inv/generated/ node-agent/wire/` **0 파일**, `export_schemas --check` 58/58, 새 DomainError 코드 0. ✔

## 3. (c) 단계 3 표·calibration 보존·판정

- 최종 세트(`a60313a7`)와 calibration 세트(`5a612ebd`)는 evidence JSON에 `final`/`calibration`으로 **분리 보존**되고, calibration의 `reasonNotFinal`("timeoutRetryCount가 fail-fast timeout을 retry로 오기록")이 명시됐다. 결정 문서 v1.3·History 페이지도 두 세트를 모두 인용. 정직 ✔.
- `decisionGates`: hold P95 감소 true · 외부 timeout 비증가 **false(2→27)** · 요청 P95 비악화 true → `passed=false`. `acceptanceClaim=false`, 50동시·5노드·AC-05·peak working set 전부 미실행/미측정 표기. 성공 18/7/8을 숨기지 않음.
- **판정 타당성**: 정의된 3조건 중 하나가 실패했으므로 "미통과 → flag off·S05-DB review·승격 보류"는 보수적으로 옳다. 단, 통과한 조건 1(hold)은 §4의 이유로 **성립 미확정**이며, 실패한 조건 2는 fail-fast의 정의상 거의 필연이다(§4 두 번째 항목). 즉 이 세트는 "fail-fast가 legacy보다 나쁘다"를 보이는 것이 아니라 "이 gate 정의와 이 벤치(클라이언트 retry 없음)에서는 fail-fast가 통과할 수 없다"를 보인다. 결론(flag off 유지)은 같지만 근거 서술은 그렇게 정정되어야 한다.

## 4. 관찰 F-C1 — hold P95 비교는 비대칭 계측 (코드 근거)

| 경로 | phase 시작 | 잠금 statement | 결과 |
|---|---|---|---|
| legacy | `mark_statement_phase("placement-legacy-lock-scope")` **placement.py:126** | 그 **뒤** `projects FOR NO KEY UPDATE`(:128)·`project_resource_limits FOR UPDATE`(:132) | `lockHoldMs` = **대기 + 보유** |
| candidate | limits `FOR UPDATE` **획득 후** `mark_statement_phase("placement-short-commit")` **:641**(주석: "Measure lock ownership, not the preceding wait") | 대기는 `placement-limit-row-wait`로 분리 | `lockHoldMs` = **보유만** |

`Database.transaction`의 finally(db.py:183~196)가 phase `startedNs`부터 commit까지를 `lockHoldMs`로 기록하므로, legacy 1526ms는 20개가 직렬로 줄 선 **대기 시간이 대부분**이다. 20요청 직렬화에서 k번째의 대기+보유 ≈ k·h 라면 p95(≈19번째) 1526ms → **legacy 실제 보유 h ≈ 80ms** — candidate 보유 p95 117ms와 **같은 자릿수**다(추정, 실측 아님). 따라서 "hold P95 1526→117 감소"는 계측 비대칭의 산물일 가능성이 크고, 옵션 1의 핵심 주장 "잠금 보유 O(pool)→O(selected) 감소"는 이 evidence로 **증명되지 않았다**(반증도 아님). 카드 18 F-R4에서 내가 "hold p95 1400→122ms 성립"이라 적은 것은 같은 비대칭을 놓친 것이므로 **정정**한다.

두 번째 구조 관찰: fail-fast는 `lock_timeout=500ms` 아래에서 각 waiter가 FIFO tuple lock 뒤에 줄 서므로 k번째 waiter의 단일 대기 ≈ 앞선 k개 보유 합이다. 보유 ~100ms면 5~6번째부터 500ms를 넘겨 **한꺼번에 55P03**(wait p95 504ms = lock_timeout, 성공 7~8/20)이 난다. 반면 legacy는 6회 실행에서 55P03 0건이면서 요청 P95 1.8~2.3s·57014 2건 — 같은 `SET LOCAL lock_timeout` 아래에서 legacy 대기가 2초까지 55P03 없이 이어진 이유(도착 분산인지, tuple-lock 대기 계시 차이인지)는 **이 evidence로 판별 불가**하며, 카드 13 조건 1(57014 statement 특정, 서버측 계측)은 카드 14·16에서도 **미이행**이다.

## 5. (d) v1.3 옵션 의견 — **(b) legacy 유지·5노드 후 재판단**, (a)는 지금 아님

| 기준 | (a) limit-row 입도 변경 | (b) legacy 유지 + 5노드 선측정 |
|---|---|---|
| 불변식 | kind별 행/usage CAS는 ceiling 원자성(`used+needed ≤ limit`)을 다중 행에 걸쳐 증명해야 하고 reserve/release/stop/expiry/reconcile/restore/containment/model-retry가 같은 counter를 증감 — dual-write parity 실패 시 중단 조건까지 필요(v1.3 자체 서술) | 현 canonical Lease 합계·단일 limits 행 원자성 그대로 |
| 원인 대응 | 모든 요청이 cpu+memory를 함께 예약하므로 두 행을 모두 잠가 **같은 hotspot**(Codex 인정). 큐 깊이·보유 시간을 줄이지 못하면 §4의 cascade는 그대로 | 원인 규명 없이 상태 유지 — 개선 약속은 없으나 위험 증가도 없음 |
| 변경 범위 | migration + backfill + RLS/FK + 잠금 순서 재설계 + 실 PG 반례 10종 | 0 |
| 롤백 | flag off + additive table 잔존 + usage 재조정 — 롤백 자체가 절차 | 없음 |

**의견**: (b). 근거 — (1) 이 evidence는 hold 감소를 증명하지 못했고(§4) 55P03 27건은 fail-fast+500ms+20깊이 큐의 구조적 결과이므로, 입도 변경이 그 구조를 바꾼다는 근거가 없다. (2) (a)는 계약 무변경을 목표로 하더라도 복구 writer 전부를 건드리는 고난도 동시성 변경이며 롤백에 dual-write parity가 필요하다. (3) 5노드 물리 lane은 개발 PC 합성 Node와 다른 병목(네트워크·실 heartbeat)을 드러내므로, 그 전에 counter 정본을 만드는 것은 순서가 거꾸로다.

(b)에 **선행 조건 2개**(둘 다 계약 무변경·Codex 소유 소규모 변경)를 붙일 것을 권한다: **P1** legacy hold 계측을 대칭으로 — `mark_statement_phase("placement-legacy-lock-scope")`를 limits 획득 **뒤**로 옮기고 legacy 대기를 별도 metric(`placement-legacy-lock-wait`)으로 기록해 20동시 1회 재측정(그래야 옵션 1의 hold 감소 주장이 처음으로 검증된다); **P2** 카드 13 조건 1 — `log_min_duration_statement` 또는 SQL observer로 57014·55P03 원인 statement와 legacy 대기가 500ms를 넘기고도 55P03이 아닌 이유를 특정. 이 둘의 결과가 "candidate 보유가 legacy보다 실제로 짧다"를 보이면 (a) 대신 **candidate의 대기 정책(lock_timeout 예산 또는 큐 깊이 상한)** 이 더 작은 다음 카드가 되고, 보이지 못하면 옵션 1 자체를 재평가한다.

## 6. (e) 게이트 (a28915bc 정확 트리)

`check_docs` **852** exit 0 · `check_contract_bindings` 54 fixtures/19 types/**14 replay guards** exit 0 · `check_response_freshness` exit 0 · `check_doc_single_source --ratchet` 18 pairs exit 0 · `check_ontology` exit 0 · `check_frontend_integrity` 9 rules/0 violations exit 0 · `export_schemas --check` 58/58 exit 0 · `git diff --check 1a13e8ed a28915bc` exit 0 · evidence `json.tool` exit 0 · PG-free `test_route_coverage`+`test_serving_anchors`+`test_model_registry_config`+`test_placement_benchmark_tool` **81 passed**. 게이트 전부 ✔.

## 판정
**승인** — F-R1·F-R2·fail-fast 되살림 3건 모두 KILLED, 내부 retry 0·기존 `RES-0007` 계약·계측 분리·계약 표면 0·게이트 0, calibration/최종 세트 분리 보존, "미통과 → flag off·S05-DB review" 판정 타당. 정정 요청(비차단): 단계 3 서술에서 "hold P95 감소 통과"를 "비대칭 계측으로 미확정"으로, 카드 18 F-R4의 내 서술도 같이 정정. v1.3 의견 **(b)** + 선행 조건 P1(legacy hold 대칭 계측)·P2(57014/55P03 statement 특정). 결정 전 금지 사항(limit-row migration·flag 운영 활성·20동시 초과) 동의.
