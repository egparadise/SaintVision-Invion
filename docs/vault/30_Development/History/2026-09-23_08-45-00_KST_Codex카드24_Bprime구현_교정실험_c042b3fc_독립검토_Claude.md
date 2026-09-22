---
doc_id: "CLAUDE-REVIEW-CODEX-CARD24-BPRIME-CALIBRATION-C042B3FC-001"
title: "Codex 카드 24 착지 c042b3fc(B′ candidate limits 잠금 예산 구현 + 사양 v1.2 + 20×3 교정 실험) 독립 검토 — 판정: 승인(구현·시험·문서) + 측정 해석 조건 1건 — 구현은 statement 하나의 transaction-local 예산·캡처값 복원·savepoint 자동 복원·BoundDatabase 무누수·계약 표면 0으로 정확, PG-free 15(+52) passed·실 PG 17 passed·되살림 2건 KILLED, 3조건 전부 실패 판정 정합, D2/D3 반영 — 단 candidate hold p95 141→768ms 급증은 depth-19 큐에서 pg_blocking_pids 샘플러가 3~4배 느려진 관측자 효과와 분리되지 않았으므로 h≈768은 '교정값'이 아니라 '관측자 포함 상한'으로 표기하고 B 상수 도출 전 sampler-off 대조 1회 필요; ERR-008 미갱신; B 사양 카드 착수 찬성"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T08:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c042b3fc"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "S05", "placement", "lock-timeout", "B-prime", "calibration", "observer-effect", "claude"]
---

# Codex 카드 24 `c042b3fc` 독립 검토 (2026-09-23, 08:45 KST)

대상: `inv/db.py`(+21: `DEFAULT/MAX_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS` 500/1900, 생성자 strict int 범위 검사, `BoundDatabase` 복사) · `inv/placement.py`(+29: candidate limits 직전 `current_setting` 캡처 → `set_config(…, true)` → 획득 후 캡처값 복원, metric `lockTimeoutBudgetMs`) · `tests/core/test_placement_lock_budget.py`(신규 15) · `tests/integration/test_placement_short_commit.py`(+158 → 17) · 벤치 schema 1.7·`--candidate-limit-lock-timeout-ms` · 사양 v1.2 · 결정 v1.5 · 검증지도 · Evidence `s05-bprime-card24-4c8a7363.json` · History. 부모 `a570c3c0`. 측정 트리 **`c042b3fc` 고정**(porcelain 0), 실 PG 단일 파일 1회 + 되살림 2건(시작 전 `codex-worker-status.md` 통보, 20동시 부하 없음).

## 1. 판정: **승인** (구현·시험·문서 정합) + **측정 해석 조건 1건**(§4 F-1) + 관찰 2

## 2. (1) 구현 정독

| 사양 항목 | 코드 | 결과 |
|---|---|---|
| candidate limits statement에만 적용 | placement.py `_reserve_short_commit` attempt 루프 → `self.db.transaction` → savepoint 안에서 `_admit_locked` 뒤 캡처(`SELECT current_setting('lock_timeout')`) → `set_config('lock_timeout','<B>ms', true)` → `placement-limit-row-wait` phase → limits `FOR UPDATE` → 획득 직후 **`set_config(…, prior, true)`** → 그 뒤 `lock_resources`·`_reserve_prepared_locked` | ✔ statement 하나 |
| D1 캡처값 복원 | 상수 500 대신 진입 시 캡처값(시험: BoundDatabase caller 700ms → 획득 후 `observed_after_limit == ['700ms']`) | ✔ |
| 실패·stale 경로 | 55P03/`_StalePlacement`는 savepoint rollback이 GUC를 되돌림(명시 복원 없음, 주석과 사양 §3-6 일치) | ✔ |
| BoundDatabase 무누수 | 값 복사(db.py `BoundDatabase.__init__`), 같은 savepoint 경계, 시험 `…restores_caller_value`가 attempt 2·후속 lock에서 캡처값 확인 | ✔ |
| 범위·타입 | `type(...) is not int or not 1 <= v <= 1900 → ValueError`(bool은 int 서브클래스지만 `type is int`로 거부; 시험 8 케이스) | ✔ |
| flag 분리 | 값은 `_reserve_short_commit`(flag on 경로)에서만 읽음; legacy 경로 무변경. 벤치 CLI는 `--mode short-commit`이 아니면 500 외 값을 거부 | ✔ |
| production 노출 0 | `app.py`/config에 `placement_candidate_limit_lock_timeout_ms`·`INV_PLACEMENT_CANDIDATE_LIMIT_LOCK_TIMEOUT_MS` 참조 0(grep), 벤치 하네스 env로만 주입 | ✔ |
| 계약 표면 | `contracts/`·`packages/`·`generated`·`wire` diff **0**, `export_schemas --check` 58/58, 오류 매핑 무변경(55P03·57014 → `RES-0007`/503/retryable) | ✔ |

## 3. (2) 시험 · 되살림 · 실 PG

- PG-free(c042b3fc 고정): `test_placement_lock_budget.py` **15** + route_coverage·serving_anchors·benchmark_tool = **67 passed**, `py_compile` 3파일 exit 0.
- 실 PG 1회: `tests/integration/test_placement_short_commit.py` **17 passed / 18.9s**(disposable DB). `>=700ms → >500ms` 문턱 교정은 "예산이 기본 500ms를 넘는 대기를 허용한다"는 목적을 그대로 검증하므로 의미 유지 ✔(0.8초 holder에서 client wait 681ms는 목적 충족).
- **되살림 A**(성공 경로의 캡처값 복원 4줄 제거) → `…applies_only_to_limits_statement_and_restores_caller_value` **1 failed: `'1500ms' == '700ms'`** — 복원이 실제 무게를 가짐(KILLED).
- **되살림 B**(`set_config`에 예산 대신 항상 `'500ms'`) → `…can_wait_beyond_default_without_changing_contract` **1 failed: `335.442 > 500`** — 예산 미적용을 잡음(KILLED; holder 타이밍에 따라 55P03 또는 이 단언 중 하나로 반드시 실패). 원복, porcelain 0.

## 4. (3) 측정 표 · 판정 · 산술 정합 — 그리고 F-1 관측자 효과

- 원자료(evidence `waves`) ↔ History 표 ↔ 결정 v1.5 ↔ 검증지도: legacy 20/20 ×3, request P95(all) 1846.488/1672.100/1785.486 → 중앙 **1785.486**, hold P95 141.932/148.346/132.282 → **141.932**; candidate B=1500 4/4/3 성공, `55P03` 16/16/17(합 **49**), `57014` 0, request P95(all) 2234.034/2550.888/2315.099 → **2315.099**, hold P95 723.016/767.708/848.163 → **767.708**, acquire wait P95 ~1530 — 네 문서 일치 ✔. 3조건(외부 timeout 0→49, all P95 1785→2315, hold 142→768) **전부 실패** ✔, `verdict: BPRIME_NOT_PROMOTED`, flag off·기본 500·S05 `review` ✔. 1900 arm `NOT_RUN` + 사유(`B+h>2000` → 57014 혼입, 3회 동일 방향, 승인) ✔. 잔존 DB 0·role baseline 2=2·fencing 유일·no-overbooking ✔. 게이트 2가 all P95이고 success P95를 보조로 병기(D3) ✔.
- 산술: `20−⌊1500/767.7+2⌋ = 20−3 = 17` ↔ 관측 16/16/17 정합 ✔ — **단 이 정합은 h를 같은 wave에서 사후에 읽었으므로 순환적**이다. 사전 예측(카드 27, h_p95 117~171ms 기준)은 "3~8 실패"였고 실제는 16~17이었다. 즉 **B=500(12~13 실패, h≈100)에서 B=1500으로 예산을 3배 늘렸는데 실패가 늘었다** — FIFO 산술로는 h가 ~7배 커져야만 가능하다.
- **F-1(측정 해석 조건)**: hold 급증(p50 49~55 → 293~778ms, p95 142 → 723~848ms)의 원인 후보를 evidence가 분리하지 못했다. 같은 JSON에서 계산하면 queue sampler(`pg_stat_activity`+`pg_blocking_pids`) 간격이 legacy **≈21ms**(90표본/1.9s, depth 1)에서 candidate **≈67~89ms**(27~38표본/2.3~2.6s, depth **19**)로 3~4배 느려졌다. `pg_blocking_pids`는 lock 파티션 LWLock을 잡고 대기 그래프를 계산하므로 depth-19 chain에서 표본당 비용이 O(n²)로 커지고, 그 동안 holder의 후속 lock 획득(`lock_resources`·lease INSERT)이 같은 파티션 lock에서 지연될 수 있다. 카드 16/18의 candidate hold 117~171ms는 sampler 없이(sampler는 카드 19 도입) 측정된 값이라 "예산을 늘리면 holder transaction 자체가 길어진다"(History §h 교정)는 서술은 기전 없이 두 변수를 동시에 바꾼 결과다. 따라서 `h≈768ms`는 **'경합+관측자 포함 상한'** 으로 적고 "교정된 h"로 쓰지 않는다. 판정(3조건 전부 실패·B′ 미승격)은 이 조건과 무관하게 유지된다 — sampler를 꺼도 B′가 게이트 1을 통과할 근거는 없다(카드 27 표: h≥100이면 실패 ≥3).
- **F-1 해소 조건(다음 카드에서, 20동시 1회 이내)**: candidate B=1500 wave 1회를 `INV_PLACEMENT_QUEUE_DIAGNOSTIC=0`으로 재실행해 hold p95를 대조하거나, sampler 간격을 100ms로 늘려 표본당 비용을 보고(`pg_blocking_pids` 호출 시간 기록)한다. B(bounded semaphore)의 상한 N을 `N ≈ ⌊500/h⌋+2`로 도출하려면 이 대조가 선행해야 한다(h=100이면 N≈7, h=768이면 N≈2 — 정책이 달라진다).

## 5. (4) 카드 27 D2/D3 반영 · 문서 정합

- D1 캡처값 복원 ✔(§2). **D2** 산술표(사양 §4.1, 70/100/150/289 × B 500/1500/1900)·"B′는 교정 실험, 다음 카드는 B" ✔. **D3** §4 정정("candidate FIFO는 최대 한 구간 누적 → 총 ≤ B+h, holder 재시작 누적 57014는 legacy 기전") ✔, 게이트 2 = all-request P95 명시 + success P95 보조 ✔, 상한 `≤1900`으로 조정 ✔(CE-1 반영).
- **O-a** `ERR-DESIGN-008`은 tip에서 v1.4(08:45, "B′→B 우선")에 머물러 카드 24 결과(교정 실패·B 확정)가 없다 — 결정 v1.5·검증지도와 어긋나므로 v1.5 동기화 필요(비차단).
- **O-b** History의 "첫 worktree 실행 17 skipped(.env 경로 오인)·첫 실 PG 16 passed/1 failed(임의 700ms 문턱) → 교정 후 17 passed" 서술은 정직하며, 교정이 시험 목적을 바꾸지 않았음을 §3에서 확인.

## 6. (5) 게이트 (c042b3fc 정확 트리)

`check_docs` **886** · `check_contract_bindings` 54/19/14 · `check_response_freshness` · `check_doc_single_source --ratchet` 18 · `check_ontology` · `check_frontend_integrity` 9/0 · `export_schemas --check` 58/58 · `git diff --check a570c3c0 c042b3fc` · evidence `json.tool` — 전부 exit 0.

## 7. B 사양 카드 착수 의견

**찬성.** 근거: (1) B′ 결과와 무관하게 FIFO 누적은 큐 깊이 × h의 문제이므로 lock 진입 동시성을 제한하는 B가 DB 원자성을 바꾸지 않는 유일한 남은 후보(카드 23·27 의견과 일치). (2) 사양이 고정해야 할 것은 History가 이미 열거한 tenant+project 격리·permit 누수 0·exact replay 재진입·cancel/exception 반환·상한 초과 시 기존 `RES-0007`·process-local 한계·다중 CP 비주장·기본 off·즉시 rollback — 여기에 **F-1 대조 결과로 N을 정한다**는 조항과, permit 대기 자체에 상한(예: lock 예산과 같은 500ms)을 두어 큐를 DB 밖으로 옮겼을 뿐인 상태가 되지 않게 하는 조항을 추가. (3) 구현·부하는 별도 승인.

## 판정
**승인** — 구현은 사양 v1.1/v1.2를 정확히 따르고(statement 하나·캡처값 복원·savepoint 자동 복원·BoundDatabase 무누수·production 노출 0·계약 0), 시험은 PG-free 15·실 PG 17 passed에 되살림 2건 KILLED로 무게가 있으며, 측정 원자료·중앙값·3조건 실패·1900 생략 사유·D2/D3가 문서 간 정합하고 flag off·S05 review가 유지된다. 조건(비차단이나 다음 카드 전 필수): F-1 — `h≈768ms`를 관측자 포함 상한으로 표기하고 sampler-off 대조 1회 뒤에만 B의 N 도출에 사용; O-a ERR-008 v1.5 동기화. B 사양 카드 착수 찬성.
