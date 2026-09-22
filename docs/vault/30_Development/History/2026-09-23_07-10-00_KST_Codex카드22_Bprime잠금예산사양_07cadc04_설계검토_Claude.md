---
doc_id: "CLAUDE-REVIEW-CODEX-CARD22-BPRIME-SPEC-07CADC04-001"
title: "Codex 카드 22 착지 07cadc04(B′ candidate limits 잠금 예산 구현 사양 v1.0, docs-only) 설계 검토 — 판정: 조건부 승인(구현·20×3 측정 카드 진행 가능, 단 '교정 실험'으로 명시) — 산술: FIFO 규칙 (k−2)·h에서 1500ms는 k=20 cascade를 h≲100ms일 때만 없애고 h≈150ms면 ~8/20이 1500ms에 55P03이므로 게이트 1(외부 timeout ≤ legacy 0~2)은 h에 달림 — SET LOCAL 범위·savepoint 복원·57014 관계 정확, 보강 3건"
version: "1.0.0"
status: "review"
author: "Claude (design reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T07:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "07cadc04"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["design-review", "codex", "S05", "placement", "lock-timeout", "statement-timeout", "B-prime", "claude"]
---

# Codex 카드 22 `07cadc04` 설계 검토 (2026-09-23, 07:10 KST)

대상: [[S05 B-prime candidate limits 잠금 예산 구현 사양]] v1.0.0 · [[2026-09-23_09-20-00_KST_S05_Bprime_구현사양_Codex]] · 결정 v1.4 B′→B · 전제 = [[2026-09-23_08-45-00_KST_S05_Card21_lock_wait_기전확인_Codex]] `HYPOTHESIS_SUPPORTED`(legacy FK 있음 20/20·tuple 0·holder change 0~18 vs FK-DROP 2/18·tuple segment 최대 499.957ms·55P03 18 — 카드 23의 D1~D3 반영). 부모 `b23b4c6a`, 변경 3파일 전부 `docs/`(비문서 diff **0**). 측정 트리 `07cadc04` 고정, 실 PG 미실행(설계 검토).

## 1. 판정: **조건부 승인** — 구현·focused 회귀·20×3 측정 카드로 진행해도 된다. 조건은 §2의 산술 결론을 사양에 **예상 결과**로 명시하고(B′는 "교정 실험", 승격 후보 아님), §6의 보강 3건을 반영하는 것.

## 2. (1) 예산 1500ms가 cascade를 줄이는가 — 산술

카드 21 규칙(내 probe + Codex Card21 FK-DROP 대조로 제품에서 지지): tuple-lock FIFO에서 **k번째 waiter의 최장 단일 대기 구간 ≈ (k−2)·h + holder 잔여**, h = holder 1개의 획득 후 보유(candidate post-acquire hold). 20동시 동시 도착이면 예산 B에서 구간이 B를 넘는 waiter는 k > B/h + 2, 실패 수 ≈ 20 − ⌊B/h + 2⌋.

| h(ms) | B=500 실패 | B=1500 실패 | B=1900 실패 |
|---|---|---|---|
| 70 | 11 | **0** | 0 |
| 100 | 13 | **3** | 0 |
| 150 | 15 | **8** | 6 |
| 289 | 17 | 13 | 12 |

- 관측 대조: B=500에서 실제 candidate 실패 12~13/20(카드 16·18) → 유효 h ≈ 90~110ms(표와 일치). candidate post-acquire hold **p95**는 117~171ms(카드 16/18), p50은 그 아래.
- 따라서 **1500ms는 cascade를 "없애는" 값이 아니라 생존 깊이를 ~5에서 ~17로 올리는 값**이다. 게이트 1(외부 `55P03+57014` 합계 ≤ legacy 0~2)은 유효 h ≲ 100ms일 때만 통과하고, h≈150ms면 ~8/20이 **1500ms에 한꺼번에** 55P03이다. 즉 B′ 실측의 1차 산출은 "제품 h와 (k−2)·h 규칙의 교정"이며 통과 여부는 사전에 h에 달려 있음을 사양이 말해야 한다(현재 §1 "완화하는 첫 측정점"만 있음).
- **statement_timeout 2s 관계(정밀화)**: candidate FIFO waiter의 limits statement 총 시간 = tuple 구간(≤B) + head가 된 뒤 xid 구간(≤h) ≤ **B + h**. h<500이면 B=1500에서 항상 55P03이 57014보다 먼저다 → 사양 §4 첫 bullet은 옳고, 둘째 bullet("holder 교체로 clock이 재시작돼 누적이 2초에 닿으면 57014")은 **legacy(FIFO 우회, 구간 재시작 반복)** 의 현상이지 candidate에는 적용되지 않는다(candidate는 재시작 구간이 최대 1개). 이 구분을 §4에 적어야 측정 해석이 흔들리지 않는다. B=1900이면 h>100에서 B+h>2000이라 57014가 섞이기 시작한다 — 1900 arm을 추가한다면 이 점을 함께.

## 3. (2) SET LOCAL 범위·복원·BoundDatabase 누수

- 현재 경로: `Database.transaction`(db.py:154)만 `SET LOCAL lock_timeout='500ms'`/`statement_timeout='2s'`(:173~174)를 건다. `BoundDatabase.transaction`(:123~126)은 caller conn을 그대로 yield → 설정은 outer transaction 것을 상속. 저장소에 다른 `lock_timeout` 설정 지점 없음(grep 0).
- candidate: `_reserve_short_commit`(placement.py:577) → attempt 루프(:601) → `with self.db.transaction(...)`(:613) → **savepoint `with conn.transaction():`(:619)** 안에서 limits `FOR UPDATE`(:645). 사양 §3의 `set_config('lock_timeout', …, true)`(transaction-local)를 limits 직전에 두면 그 변경은 **savepoint 안**에 있다. PostgreSQL GUC 변경은 트랜잭션적이므로 (a) 55P03으로 서브트랜잭션이 abort되면 `ROLLBACK TO SAVEPOINT`가 lock_timeout을 **자동으로 500ms로 되돌린다**(사양 §3-6 "실패 트랜잭션에서 복원 SQL을 억지로 실행하지 않음"은 옳고 필요하지도 않다), (b) 획득 성공 뒤 `_StalePlacement`로 savepoint를 되감아도 마찬가지, (c) 성공 경로만 명시 복원이 필요하며 사양이 "획득 직후·다음 writer lock 전"으로 고정(:679 phase mark 직전) ✔. BoundDatabase(outer 트랜잭션 공유)에서도 savepoint 경계가 같으므로 attempt 사이·outer 호출자로의 누수는 없다. `RELEASE SAVEPOINT`는 GUC를 되돌리지 않으므로 성공 경로 명시 복원은 생략 불가 — 사양과 일치.
- 보강(§6 D1): 복원값을 상수 `'500ms'`로 박지 말고 진입 시 `current_setting('lock_timeout')`을 읽어 그 값으로 복원(공통값이 바뀌어도 사양 §1 "공통 500 유지"가 코드 상수와 이중으로 묶이지 않게).

## 4. (3) 불변식·계약 표면·설정 분리

- 잠금 모드·순서·FIFO·savepoint·`_reserve_prepared_locked` ceiling/offered 재검사(:715) 무변경 → no-overbooking·fencing/epoch·멱등 replay·RLS는 기존 시험(카드 16/18 되살림 3건 KILLED)이 그대로 지킨다. 바뀌는 것은 **대기 시간 상한 하나**뿐.
- 계약 표면 0: 55P03/57014 모두 db.py:199~209 매핑으로 `RES-0007`/503/retryable, SQLSTATE는 evidence만 ✔. production `INV_API_CONFIG` key 미추가·unknown key fail-closed 유지 ✔. 설정은 `Database` private + `BoundDatabase` 복사, `placement_short_commit is True`일 때만 읽음, 범위 `1 ≤ v < 2000`·bool 거부 ✔(PG-free 시험 §6.1이 고정).
- 반례(서면) **CE-1 상한 검증 누락 경로**: 값 1999는 허용되지만 h≥1ms면 B+h ≥ 2000 → 57014가 55P03보다 먼저 → 게이트 1 분모는 같아도 "예산 초과"와 "statement 초과"의 evidence 구분이 무의미해진다. 상한을 `< 2000 − h_max`(예: ≤1500 기본, 실험 최대 1900)로 두거나 §4에 "B+h<2000일 때만 55P03 우선" 조건을 명시.

## 5. (4) 판정 게이트·롤백·측정 계획

- 3조건 AND(외부 timeout 합계 ≤ legacy, request P95 중앙값 비악화, post-acquire hold P95 중앙값 비악화) + "성공 수·limits wait·hold 하나로 통과 금지" — 카드 16/18 원칙과 동일 ✔. 20×3 순차, 같은 SHA·PG·합성 Node, candidate 500 calibration 허용, 50·5노드 금지 ✔.
- 롤백: 실험 인자 제거·flag off, migration 0 ✔. 중단 기준(deadlock·fencing 중복·불변식 위반·2초 초과 설정·후속 lock 누출) ✔.
- 반례(서면) **CE-2 게이트 2의 착시**: 실패 요청이 504ms 대신 1500ms에서 끝나면 candidate request P95(all)는 **오히려 오른다**(실패가 늦어짐). 게이트 2가 "all" 기준이면 B′는 실패 수를 줄이고도 P95에서 지고, "성공만" 기준이면 survivor 편향(카드 18 지적). 사양이 어느 P95인지 명시해야 한다 — 권장: all 기준 + 실패 수 감소를 별도 행으로 병기.
- 반례(서면) **CE-3 도착 분산**: 20동시가 실제로는 DB에 515ms에 걸쳐 도착(카드 19 O-b)하면 유효 큐 깊이 <20이라 표 §2보다 실패가 적게 나온다 — 통과가 나와도 "20-deep 동시"가 아닌 "도착 분산된 20"임을 queue-depth 표본으로 같이 보고(사양 §7이 queue-depth 표본을 요구하므로 해석 규칙만 추가).

## 6. 보강 요청(v1.1, 비차단) · 의견

- **D1** 복원값은 `current_setting` 캡처값(§3). **D2** §2 표를 사양에 넣고 B′를 "h 교정 실험, 승격 후보는 B"로 명시, 선택적으로 같은 승인에 1900 arm(단 57014 혼입 해석 규칙 포함). **D3** §4에 "candidate는 재시작 구간 최대 1개 → 총 ≤ B+h; 둘째 bullet은 legacy 현상"으로 정정, 게이트 2의 P95 정의(all vs 성공) 명시.
- **의견: 구현 카드 승인(조건부).** 근거 — 변경이 statement 하나의 대기 상한뿐이라 위험·롤백 비용이 최소이고, 실측이 제품 h와 FIFO 규칙을 교정해 B(project별 bounded semaphore)의 상한 N을 정하는 입력이 된다. 다만 게이트 1 통과를 기대값으로 두면 안 되며, 결과와 무관하게 다음 카드는 B다. flag off·S05-DB `review`·candidate/50/5노드 미승격 유지에 동의.

## 7. (5) 게이트 (07cadc04 정확 트리)

`check_docs` **879** · `check_contract_bindings` 54/19/14 · `check_response_freshness` · `check_doc_single_source --ratchet` 18 · `check_ontology` · `check_frontend_integrity` 9/0 · `export_schemas --check` 58/58 · `git diff --check b23b4c6a 07cadc04` — 전부 exit 0. 비문서 diff 0.

## 판정
**조건부 승인** — SQL 적용 경계·savepoint 복원·57014 관계·불변식·계약 0·롤백은 정확하고 구현 가능하다. 조건: §2 산술(1500ms는 k=20에서 h≲100ms일 때만 게이트 1 통과, h≈150ms면 ~8/20 실패)을 예상 결과로 명시해 B′를 교정 실험으로 자리매김, D1~D3 반영, 게이트 2 P95 정의 명시. 구현·20×3 측정 카드는 그 뒤 진행.
