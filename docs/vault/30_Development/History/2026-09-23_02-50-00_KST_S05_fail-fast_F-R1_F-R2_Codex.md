---
doc_id: "HIST-CODEX-2026-09-23-S05-FAIL-FAST-FR1-FR2"
title: "S05 fail-fast 구현과 F-R1·F-R2 시험 보강 — F-S05-03 단계 3 재판정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T02:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c51a30251b9c7cc56adcba76d425966ae425f1ed"
implementation_source_sha: "a60313a72a618c338a0d67da13e2993b1e536e8e"
task_ids: ["S05-DB"]
tags: ["placement", "fail-fast", "postgresql", "F-S05-03", "mutation-test"]
---

# S05 fail-fast 구현과 F-R1·F-R2 시험 보강

## 결론

Claude 카드 18의 조건부 승인과 코디네이터의 fail-fast 우선 결정을 반영했다. candidate는 limit-row database contention을 내부에서 재시도하지 않고 첫 `55P03`을 기존 `RES-0007` / 503 / `retryable=true`로 반환한다. stale speculative decision의 side-effect 없는 최대 3회 재계획은 별개이며 유지한다. 공개 응답·오류·route 계약 변경은 0이고 `placementShortCommit` 기본값은 `false`다.

최종 20동시 3회에서 hold P95와 요청 전체 P95 중앙값은 감소했지만 외부 timeout은 legacy 2건에서 candidate 27건으로 증가했다. 단계 3의 세 조건 중 외부 timeout 비증가를 충족하지 못했으므로 **fail-fast도 미통과**다. flag off, S05-DB `review`, 50동시·물리 5노드 미승격을 유지한다. 다음 결정은 [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.3의 limit-row 입도 변경 대 legacy 유지·5노드 후 재판단이다.

## F-R1·F-R2·F-R3 보강

| 항목 | 원본 시험과 실측 | 되살림 판별 |
|---|---|---|
| F-R1 tight-fit | competing Lease가 `offered - need + 1`을 선점한 뒤 `_locked_fit`이 현재 `active_total`을 다시 읽어 `_StalePlacement`를 낸다 | `_locked_fit`에서 `active_total`을 제거하면 `DID NOT RAISE`, 대상 단일 시험 exit 1 — **KILLED** |
| F-R2 BoundDatabase savepoint | 같은 caller-owned outer transaction에서 다른 연결이 limit row를 잠가 첫 호출이 raw `55P03` fail-fast, holder 해제 후 호출자가 같은 key/body로 재호출하면 성공한다 | attempt savepoint를 제거하면 두 번째 호출이 `InFailedSqlTransaction`, 대상 단일 시험 exit 1 — **KILLED** |
| fail-fast 공개 표면 | standalone Database에서 limit row를 잠그면 metric 한 건(`attempt=1`, timeout, `55P03`) 뒤 `RES-0007`/503/retryable, idempotency·Lease 잔존 0 | 실 PG focused suite 13 passed/exit 0 |
| F-R3 문서 | 카드 14 당시 10+1 시험은 통과했지만 fit 재계산·savepoint 두 되살림은 미확인이었다 | 이번 두 판별 시험으로 닫았다. flag-off는 바이트 무변경이 아니라 shared admission/prepared primitive로 리팩터된 뒤 실 PG에서 동작 동등성을 확인한 경로다 |

F-R2의 “attempt 2”는 커널 내부 retry가 아니다. fail-fast가 외부로 오류를 반환한 뒤 caller가 같은 outer transaction에서 명시적으로 같은 key/body를 재호출하는 경계다. savepoint가 없으면 첫 SQL 오류가 caller transaction 전체를 abort하므로 이 경계가 성립하지 않는다.

## 단계 3 — 최종 schema 1.4

환경은 개발 PC, 합성 measured-node 1개, 실 disposable PostgreSQL이며 물리 5노드가 아니다. 순서는 L1→C1→C2→L2→L3→C3이고 각 프로세스가 자기 DB를 생성·삭제했다. 종료 뒤 `inv_test_` DB 잔존은 0이다.

| 모드 | 성공/20·exit 3회 | 요청 P95(all) 3회 / 중앙 | hold P95 3회 / 중앙 | 외부 timeout 합계 | limit wait P95 중앙 | 내부 retry |
|---|---|---|---|---:|---:|---:|
| legacy | 20/0 / 18/1 / 20/0 | 1027.020 / 2292.130 / 1817.763 / **1817.763ms** | 789.944 / 2021.962 / 1526.365 / **1526.365ms** | `57014` 2 | 해당 없음 | 0 |
| candidate fail-fast | 18/1 / 7/1 / 8/1 | 827.757 / 938.185 / 922.915 / **922.915ms** | 44.114 / 145.956 / 116.848 / **116.848ms** | `55P03` 27 | **504.190ms** | **0** |

- hold P95 감소: 통과.
- 외부 `55P03+57014` 합계 legacy 대비 비증가: **실패(2→27)**.
- 요청 P95 비악화: 통과. 단 candidate 성공 수가 18/7/8이므로 성공률을 숨기지 않는다.
- 종합: **미통과**. limit-row 입도 변경 보류를 해제할 근거는 생겼지만 구현 승인은 아직 없다.

첫 `5a612ebd` 세트는 schema v1.3의 `timeoutRetryCount`가 fail-fast timeout 자체를 retry로 잘못 이름 붙인 calibration이다. legacy 20/20×3, candidate 성공 10/14/6, 외부 `55P03` 30, hold P95 중앙 1360.102→141.310ms였으며 버리지 않았다. schema v1.4는 `timeoutCount`와 `timeoutRetryCount=0`, `acquisitionAttemptCount`, `contentionPolicy`를 분리했고 최종 세트를 새 SHA로 다시 실행했다. 구조화 요약: [[s05-fail-fast-stage3-a60313a7.json]].

## 검증과 경계

- `tests/integration/test_placement_short_commit.py`: **13 passed / exit 0**.
- `tests/integration/test_model_retry.py::test_retry_short_commit_flag_preserves_atomic_response_and_replay`: **1 passed / exit 0**.
- F-R1 mutation: **1 failed / exit 1**, 원복 완료.
- F-R2 mutation: **1 failed / exit 1**, 원복 완료.
- 전체 pytest/vitest/build, 20동시 초과, 50동시, 물리 5노드는 실행하지 않았다.
- process parent만 잡힌 첫 감시값은 실제 pytest child peak가 아니므로 peak working set은 **미측정**이다.

## 문서·정적 게이트

| 검증 | 결과 |
|---|---|
| evidence `python -m json.tool` | exit 0 |
| `python tools/check_docs.py` | exit 0 — latest-tip 재적층 뒤 852 versioned documents, 48 task mappings |
| `python tools/check_contract_bindings.py` | exit 0 — 54 fixtures, 19 response types, 14 replay guards |
| `..\.venv\Scripts\python.exe tools/check_ontology.py` | exit 0 — RDF/SHACL/48 task mappings/Obsidian mirrors |
| `python tools/check_doc_single_source.py --ratchet` | exit 0 — 18 pairs, stale 0 |
| `python tools/check_response_freshness.py` | exit 0 — advisory 10/10 |
| `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | exit 0 — 9 rules, 0 violations |
| `git diff --check` | exit 0 |

최종 착지 SHA는 R1 완료 뒤 이 기록의 Git history로 고정한다. reviewer Claude 카드 19 대기.
