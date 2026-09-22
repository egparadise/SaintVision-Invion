---
doc_id: "CLAUDE-REVIEW-CODEX-CARD21-LOCK-WAIT-ABF9240F-001"
title: "Codex 카드 21 착지 abf9240f(S05 log_lock_waits 원본·FK-DROP 대조 실측, HYPOTHESIS_SUPPORTED) 독립 검토(카드 24 역할) — 판정: 조건부 승인 — 두 wave 수치가 evidence·History·ERR-DESIGN-008·결정 v1.4 네 곳에서 일치, D1~D3 반영, 20 초과 0·잔존 0·운영 설정 무변경, PG-free 7 passed 재현 — 조건 1 = candidate limits FIFO 문구를 '실험 확인'이 아닌 '카드 18 정합 추론'으로 정정; 정책 v1.4(B′→B, A 기전용)는 카드 23 조건과 일치, B′ 구현 카드 개설 찬성"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T09:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "abf9240f"
impl_sha: "(문서 전용 — 코드 변경 없음; 검토 대상 abf9240f, 측정 코드 40b24329)"
tags: ["independent-review", "codex", "S05", "F-S05-02", "log_lock_waits", "pgrowlocks", "lock-timeout", "policy-v1.4", "claude"]
---

# Codex 카드 21 `abf9240f` 독립 검토 (2026-09-23, 09:50 KST)

## 0. 판정 요약

| 항목 | 결과 |
|---|---|
| 대상 | `abf9240f` "test(s05): confirm project lock wait mechanism"(부모 `fc18b95f`, 11 files): 신규 `tools/placement_lock_wait_diagnostic.py`(236)·`tests/integration/test_placement_lock_wait_diagnostic.py`(407)·`tests/test_placement_lock_wait_diagnostic_tool.py`(40)·`tests/integration/conftest.py`(+40)·evidence `s05-lock-wait-card21-40b24329.json`·History·ERR-DESIGN-008·결정제안 v1.4·재실행 설계 v1.2·검증 상태 지도·Codex 작업판. 제품 코드·계약·migration 변경 **0** |
| 판정 | **조건부 승인** — 조건 1건(문구, §2). 관찰 4건 비차단 |
| 내가 실행한 것 | 문서·evidence 수치 4곳 대조, 하네스·conftest·tool 코드 정독, PG-free `tests/test_placement_benchmark_tool.py` + `tests/test_placement_lock_wait_diagnostic_tool.py` **7 passed**(단일 파일, 메모리 경보 범위). 실 PG 재실행 없음(지시) |

## 1. 두 wave 결과와 판정표 정합 (질문 1)

| 수치 | evidence JSON | History | ERR-DESIGN-008 | 결정 v1.4 | 지도 |
|---|---|---|---|---|---|
| 원본 성공/실패 | 20/0 | 20/0 | 20/0 | 20/20 성공 | 20/20 |
| 원본 queue | waiter 19 · depth 1 | 동일 | 동일 | depth 1 | depth 1 |
| 원본 segment | transaction 190 · tuple 0 · holder change 0~18 · maxSingle 191.343ms · maxPerWaiter 1975.618ms | transaction 190·tuple 0·holder 0~18 | 동일 | 190·tuple 0 | 190·tuple 0 |
| 원본 pgrowlocks | `Key Share`+`For No Key Update`, 103 snapshots, maxHolder 20 | 동일 | 동일 | 동일 | 동일 |
| 원본 timeout | `55P03` 0(키 부재) | 0 | 0 | 0 | 0 |
| 대조 성공/실패 | 2/18 (`RES-0007` 18 = `55P03` 18) | 2/18 | 2/18 | 2/20 성공 | 2/20 |
| 대조 queue | waiter 19 · depth 19 | 동일 | 동일 | 동일 | 동일 |
| 대조 segment | tuple 1 · maxSingle **499.957ms** | tuple 관측·499.957 | 동일 | 동일 | 동일 |
| 대조 pgrowlocks | `For No Key Update`만, 4 snapshots | 동일 | 동일 | — | — |
| 판정 | `HYPOTHESIS_SUPPORTED` | 동일 | 동일 | 동일 | 동일 |

`classify()`(tool 111~151행)의 기준: baseline = (`Key Share` 또는 `For Key Share`) ∧ `For No Key Update` ∧ transaction segment>0 ∧ tuple segment=0 ∧ `55P03`=0; control = tuple segment>0 ∧ depth≥2 ∧ `55P03`>0 ∧ 450~650ms 구간 event 존재 → 두 evidence로 `SUPPORTED`가 도출되며 `CONTRADICTED`(depth≤1 ∧ tuple 0 ∧ 55P03 0)·`NOT_OBSERVED`가 분리돼 있다. parser 정정("Key Share"/"For Key Share" 양쪽 수용)은 evidence를 바꾸지 않고 재결합했다는 서술과 코드 일치. PG-free 분류 시험 3건이 세 판정을 고정.

**D1~D3 반영** ✔ — D1: conftest가 disposable DB에만 `ALTER DATABASE … SET log_lock_waits=on`, `deadlock_timeout='10ms'`; `loggedSegmentCount`는 "10ms threshold 이상만"으로 명명·해석(설계 v1.2 문구). D2: observer가 `pg_stat_activity.backend_xid`를 표본해 raw xid→`backend-N` alias를 메모리에서만 유지(시험 59~79·142~143행), evidence `rawPidOrXidRetained=false`. D3: FK-DROP은 새 disposable DB에서 `inv.idempotency→inv.projects` FK가 정확히 1개임을 assert 후 DROP(conftest), 제품/migration 파일 무변경.

## 2. 기전 승격 문구의 범위 (질문 2)

실험이 직접 지지하는 것: **legacy 원본에서 idempotency FK RI `KEY SHARE` 선행 → project `FOR NO KEY UPDATE`의 tuple-lock FIFO 우회(transaction-level 대기, holder 교체 0~18) → holder 교체마다 `lock_timeout` 재시작(단일 segment 최대 191ms, waiter 합 최대 1975ms, `55P03` 0)**, 그리고 **FK 하나만 제거하면 같은 경로가 tuple FIFO(depth 19)·≈500ms `55P03` cascade로 바뀐다**. 네 문서의 핵심 문장은 이 범위 안이다.

**조건 1(문구)**: History·ERR-DESIGN-008·결정 v1.4가 "**candidate limits 행은** 선행 FK 잠금이 없어 FIFO가 누적되고 한 구간이 약 500ms에 닿아 `55P03`이 된다"를 확인된 사실처럼 적는다. 이번 실험은 candidate를 실행하지 않았고(evidence `safety.candidateExecuted=false`) 대조군은 *FK를 제거한 legacy*다. candidate limits `FOR UPDATE` FIFO 설명은 카드 18(`55P03` 12, limits statement 귀속)과 **정합하는 추론**이지 이 카드가 확인한 기전이 아니다. 세 문서에서 해당 문장을 "카드 18 관측과 정합하는 추론(candidate 미실행)"으로 정정할 것. 같은 이유로 "`57014` 경계"는 이 실행에서 `57014` 0건·최대 대기 1975.6ms<2s이므로 "과거 legacy wave와 정합"으로만 두는 현재 표기가 맞다.

안전 경계 ✔: `INV_PLACEMENT_BENCHMARK_REQUESTS/CONCURRENCY=20`·`ROUNDS=1`·`SHORT_COMMIT=0` 고정(tool 83~86), 두 wave 20동시 초과 0; tool이 로컬 host·PG16·승인 컨테이너 포트 일치를 검사(20~48행); 실행 전후 `inv_test_%`/`inv_app_%` inventory 비교로 잔존 0 아니면 exit 4(102~107행); `ALTER SYSTEM` 미사용·`ALTER DATABASE`는 disposable 이름에만(conftest); `pgrowlocks` 확장은 disposable DB에 생성 후 PUBLIC EXECUTE REVOKE; evidence `safety` 블록(operationalDsnUsed/alterSystemUsed false, residue 0, secret 0) 일치.

## 3. 정책 v1.4 초안 vs 카드 23 조건 (질문 3)

| 카드 23(내 카드 20 검토) 조건 | v1.4 초안 | 일치 |
|---|---|---|
| B 계열 우선: B′(limits `lock_timeout` 500→~1500ms, 2초 안) → B(project별 bounded semaphore), A는 기전 확인용 | 동일 순서·동일 정의, A "제품 정책 후보 아님·disposable probe 외 구현 금지" | ✔ |
| 판정 기준 = 외부 `55P03+57014` 합계 legacy 이하 **AND** 요청 P95 비악화 **AND** post-acquire hold P95 비악화, 성공 수만으로 통과 금지 | B′·B 모두 동일 3조건 + queue depth·wait p95·timeout statement 기록 | ✔ |
| 불변식·변경 범위·롤백 | B′: limits `FOR UPDATE`/FIFO·idempotency/fencing/epoch/RLS·원자성·`RES-0007` 표면 유지, candidate 내부 statement에만 예산, flag off, 롤백=flag off; B: DB 원자성 대체 금지·tenant+project 격리·permit 반환·process-local·분산 상한 주장 금지, 롤백=flag off+permit 폐기 | ✔ |
| 정책이 판정에 비의존 | `policyDecisionIndependent=true`, "순서 비의존" 명시 | ✔ |

**검토자 의견(B′ 구현 카드)**: **개설 찬성**. 전제 4가지 — (a) 예산 상한은 `statement_timeout` 2s보다 엄격히 작게(≤1500ms) 고정하고 statement별 `SET LOCAL`로만; (b) 비교는 카드 18 P1 대칭 계측(post-acquire hold·acquire elapsed·SQL observer)으로 legacy/candidate 20×3, 순서 교차; (c) 통과는 위 3조건 동시 + `timeoutCount`/`timeoutRetryCount=0` 분리 유지; (d) flag 기본 off·S05 `review`·50동시/5노드 미승격 그대로. B는 B′ 결과와 무관하게 별도 카드.

## 4. 게이트·재현 (질문 4)

- `tests/test_placement_benchmark_tool.py`(4) + `tests/test_placement_lock_wait_diagnostic_tool.py`(3) = **7 passed**(내 실행, `.venv` 3.14.7). 실 PG 두 wave는 재실행하지 않았다(지시·메모리 경보).
- 문서 게이트: 이 검토 PR 브랜치에서 `check_docs` exit 0(PR 본문).

## 5. 관찰(비차단)

| ID | 내용 |
|---|---|
| O1 | 대조군 signature의 tuple segment는 **1건**(`tupleSegmentCount=1`, 22 logged events 중 acquired 2)이라 얇다. depth 19·`55P03` 18이 주 신호이고 450~650ms 조건은 그 1건(499.957)이 충족 — 재현 wave 1회를 더 얻으면 좋으나 판정 자체는 성립 |
| O2 | observer 실제 간격 p95가 원본 90.9ms·대조 980.5ms(명목 5ms)라 큐 깊이 표본이 성기다 — 설계가 server log로 보완한다고 명시했고 depth 19는 log와 정합 |
| O3 | request P95 2575/983ms는 logging 진단 부수값으로 AC-05·정책 판정에서 배제 — 네 문서 모두 명시 ✔ |
| O4 | conftest의 진단 분기는 `INV_S05_LOCK_WAIT_DIAGNOSTIC=1`일 때만 활성이라 기존 integration 시험 경로 무변경 ✔ |

## 6. 다음 인계

- Codex: 조건 1 문구 정정(세 문서) — docs-only. 이후 B′ 구현은 코디네이터 별도 카드.
- 코디네이터: 카드 21 **조건부 승인**(문구 1건). S05-DB `review`·flag off 유지.
