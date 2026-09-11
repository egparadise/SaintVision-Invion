---
doc_id: "HIST-OFFER-SNAPSHOT-REPORT-20260911"
title: "2026-09-11 OFFER-SNAPSHOT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T23:56:33+09:00"
source_of_truth: "Git"
---

# 2026-09-11 OFFER-SNAPSHOT Codex 검증보고

CX-01 / owner Codex / reviewer Claude pending. base ade6721, 검증 **29c810f6487957a3f5f912e7ce292b5d2e454ac9**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-11_OFFER-SNAPSHOT_Codex_착수]].

## 결론과 작업

Claude cdf98ad F1의 “release는 lease만 잠근다”는 전제가 검토 대상 d14db0a와 현재 코드에 맞지 않는다. `LeaseStore._locked_lease`는 Run 잠금 후 `lock_resources`로 Node→Resource를 잠근 뒤 lease를 잠근다. 실제 HTTP offer를 첫 slice UPDATE에서 일시 중지하고 진짜 receipt-backed release를 병행하면 PostgreSQL에서 offer를 기다린다. offer 재개 후 둘 다 성공하고 public 기록량과 커널 적용 합계가 **1000/1000**이다. 따라서 이 경로의 1000/900 결함은 재현되지 않았다. F1 종결은 Claude의 이 근거 재검토를 기다린다.

새 결정론적 회귀를 `test_resource_offer_integrity.py`에 추가했다. 시험 전용 invoker trigger/advisory lock은 폐기 가능한 DB에만 만들며, `pg_blocking_pids`로 실제 offer→release 대기 관계를 확인한다. 잠금을 풀기 전 lease 미해제와 이후 실제 해제도 검사한다. 단순 sleep 성공으로 경합을 판정하지 않는다.

| 해제 경로 | 현재 잠금 근거 | 이번 확인 범위 |
|---|---|---|
| LeaseStore.release | _locked_lease → lock_resources | 실제 동시 실행 |
| Node stop receipt | node_execution에서 lock_resources 후 해제 | 코드 검토 |
| 실행 전 취소 | Control.cancel에서 lock_resources 후 reclaim_unclaimed | 코드 검토 + 기존 취소 회귀 3개 |
| containment 회수 | 미해제 자원 조회 → lock_resources → reclaim_unclaimed | 코드 검토 |
| shard admission 실패 회수 | 모든 관련 resource 잠금 후 savepoint/회수 | 코드 검토 |

기존 migration/definer 함수/policy/제품 구현은 변경하지 않았다. 원래 SQL 문장을 나누어 직접 UPDATE한 재현은 실제 release 경로의 잠금을 생략하므로 같은 실행의 재현으로 간주할 수 없다. 향후 해제 writer가 잠금 계약을 우회하지 않도록 회귀를 유지한다.

## 확인한 증거

- 초회 실경합 실험: exit 1, RES-0007 잠금 대기 시간초과. 제공량 불일치 실패가 아니며 [[2026-09-11_OFFER-SNAPSHOT_오류와해결]]에 정정했다.
- 잠금 제거 변이: private worktree에서 `_locked_lease`의 자원 잠금 한 줄만 제거하면 새 시험이 `Release bypassed the offer's resource locks`로 실패(exit 1). finally에서 원본 bytes 복구, 제품 수정 없음.
- 고정 clean 29c810f에서 `python .work/cx01_local.py tests/integration/test_resource_offer_integrity.py tests/integration/test_reservation_aborts.py tests/integration/test_definer_audit.py`: **36 passed / 0 skipped / exit 0**. 제공량11 + 취소3 + 함수감사22. 앞선 11개 준비 시험을 중복 합산하지 않는다.
- 실제 환경: Windows Python client + 독립 PostgreSQL 16 컨테이너. 시험용 DB/컨테이너 정리, 운영 컨테이너/DB/Node 변경 없음. Linux Node나 원격 2-PC 실행 시험으로 표시하지 않는다.
- `git push origin agent/codex/workspace-bridge`: 29c810f, exit 0. CI 조회 23:55:33: 같은 SHA 6개 workflow에 모두 job 시작 전 계정 결제/한도 annotation. 5개 failure, 1개 queued 상태였으며 CI 통과 아님.
- [36개 시험/변이 근거](../Evidence/offer-serialization-29c810f.json), [동일 SHA CI ID와 상태](../Evidence/offer-serialization-29c810f-ci.json).

## 다음 작업과 진척

- Codex: CX-01 F2의 실행 전 intent 기록, sequence/digest 검증, 응답 유실 후 감사 정합성을 설계·구현. Node의 기존 중복 실행 방어는 유지한다. 이후 CX-02 credential/Storage 계약.
- Claude: d14db0a `_locked_lease`와 29c810f 회귀를 검토해 F1 판정 정정/추가 반례를 기록. 작성자의 보고를 독립 승인으로 표시하지 않는다.
- 원격 profile/실제 7개 시험, CI 제한과 전체 운영 인수는 남는다. 이번 시험 추가만으로 최초 48개 작업 점수를 올리지 않는다. **산식 57.29% 완료 / 42.71% 잔여, 표시 약 55% / 45% 유지**.
- 문서 검사·동기화는 아래 전달 영수증으로 갱신한다.

## 전달 검사

- 2026-09-11T23:57:24+09:00: `python tools/check_docs.py` exit0 (24 original hashes, 271 versioned documents, 48 tasks, 12 outcomes), `python tools/check_ontology.py` exit0, `python -m black --check tests/integration/test_resource_offer_integrity.py` exit0, `git diff --check` exit0.
- `python tools/sync_obsidian.py --check --state .work/workspace-sync-state.json` exit0: 관리438개, 변경8개, 충돌0. 실제 apply 영수증은 다음 기록에서 확인한다.
