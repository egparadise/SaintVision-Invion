---
doc_id: "HISTORY-S11-AC11-MIGRATION-REHEARSAL-20260928-CODEX"
title: "S11 AC-11 migration restore 리허설 구현"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T13:06:51+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tasks: ["S11-BE", "S11-DB"]
acceptance: ["AC-11"]
tags: ["s11", "ac-11", "migration", "restore", "hosted", "fail-closed"]
---

# S11 AC-11 migration restore 리허설 구현

## 기준과 범위

- 승인 설계: PR #157 v1.1.1, head `a793f258dac9b2a4951df084089bf3a3a3ae1bcc`, 설계 blob `99776a491772c4a62e1be26644d35a365d80a030`.
- stack base: PR #170 r2 head `ea93e2e79e4776cad57b101d07b1bf9a8b4126b5`.
- 공개 API·계약·기존 migration은 바꾸지 않는다. 로컬 PostgreSQL·Docker는 실행하지 않고 실제 리허설은 opt-in hosted lane에서만 수행한다.

## 구현

`tools/run_ac11_migration_rehearsal.py`는 exact PR head와 clean checkout을 확인하고 migration graph·fixture manifest를 정적으로 검증한다. 현재 head `0046_model_manifest_readiness`가 비가역이고 reversible tail이 0이므로 `migration-reversible-segment`는 구조적으로 `NOT_APPLICABLE`이며 PASS로 세지 않는다. 짝 축은 disposable source/restore DB를 각각 새로 만든 뒤 `0045_discovery_machine_cred`까지 forward, 사전 sentinel과 custom-format snapshot 생성, source를 head로 forward, 별도 DB에 restore 후 head forward 순서로 실행한다.

최종 source와 restore DB의 catalog fingerprint는 table·column·constraint·index·function body/owner·table/routine grant·RLS policy·role membership을 비교한다. forward 전 sentinel은 restore 뒤 exact match해야 한다. forward 후 sentinel은 사전 snapshot에 없어야 하며 `DECLARED_LOSS_REQUIRES_RESTORE`로 명시한다. 종료 시 owned DB를 강제 정리하고 residue가 하나라도 남으면 실패한다. 오류 보고에는 예외 type만 남기며 DSN·비밀번호·SQL 출력을 evidence에 쓰지 않는다.

fixture manifest는 graph의 가역 revision 17개를 exact cover한다. 그중 `0001_s02_baseline`~`0007_locality_replicas`, `0009_idempotency_and_inbox_scope`, `0010_canonical_resource_units`, `0025_workspace_tool_choice` 10개는 SQL rollback PASS로 세지 않고 restore 필요 등급으로 고정한다. 현재 hosted 실행은 최신 published prior `0045→0046` 한 case만 실제 restore한다. 이 10개는 이번 artifact에서 개별 실행된 것이 아니라 향후 curated published-prior matrix의 restore 경로 분류이며, 실행되지 않은 case를 측정 완료로 주장하지 않는다.

workflow `AC-11 Migration Rehearsal`은 manual dispatch 또는 PR label `run-ac11-migration`에서만 실행된다. job-level concurrency는 `cancel-in-progress: false`, checkout은 merge ref가 아닌 PR head SHA, PostgreSQL은 `postgres:16` service다. JSON과 3-case JUnit(현재 reversible 1 skip, fixture/restore 2 pass)을 artifact로 30일 보존한다.

## PG-free 검증

| 명령 | 결과 |
|---|---|
| `PYTHONUTF8=1 python -m pytest tests/test_ac11_migration_rehearsal.py -q` | exit 0, **8 passed** |
| `python -m py_compile tools/run_ac11_migration_rehearsal.py` | exit 0 |
| workflow YAML parse | exit 0 |
| `git diff --check` | exit 0 |

부정 시험은 `downgrade(): pass`, refusal revision을 성공 downgrade로 오분류, `0009` fixture 누락, 기존 catalog 객체 삭제, DSN 부재 시 파일 미작성, opt-in/exact-head/non-cancelling workflow 결속을 포함한다.

## 현재 판정

위 결과는 runner의 PG-free 검증일 뿐 migration restore 측정값이 아니다. hosted lane 실행 전 `irreversible-restore-forward`는 `NOT_OBSERVED`이며 AC-11과 S11 상태를 변경하지 않는다. hosted run ID·head·JUnit·JSON digest·cleanup receipt는 실행 후 이 문서에 추가한다.
