---
doc_id: "S11-AC11-MIGRATION-RESTORE-TARGET-001"
title: "S11 AC-11 migration restore-forward target v0"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T20:19:23+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S11-BE", "S11-DB"]
tags: ["ac11", "migration", "restore", "target"]
---

# S11 AC-11 migration restore-forward target v0

이 문서는 `irreversible-restore-forward`와 `migration-reversible-segment` 축을 실행하기 전에 고정하는 판정 목표다. 이 목표는 단일 hosted PostgreSQL 16 서비스의 합성 migration·restore 리허설만 판정하며 운영 PITR, 별도 장애 영역, 물리 5노드 복구를 대신하지 않는다.

## 사전 등록 기준

| metric | operator | target | 뜻 |
|---|---:|---:|---|
| `restoreForwardPassCount` | `eq` | `1` | 불가역 head 직전 snapshot을 새 disposable DB에 복원하고 head로 전진한 경로가 1회 성공 |
| `catalogMismatchCount` | `eq` | `0` | source head와 restore-forward head의 정규화 catalog 불일치가 없음 |
| `negativeFixturePassCount` | `eq` | `3` | 기존 객체 삭제, 0009 중복 key, ellipsis no-op 부정 fixture가 모두 EXPECTED_FINDING |

`requiredEnvironment`는 `topology=hosted-single-postgres-service`, `synthetic=true`다. 세 metric 중 하나라도 누락되거나 분모가 0이거나 artifact·checkout provenance·cleanup이 불완전하면 `INVALID_RUN`이다. 관측값이 목표를 어기면 `MEASURED_FAIL`이다.

### 가역 tail 왕복 기준

target `s11-migration-reversible-roundtrip-v1`은 최신 불가역 barrier 뒤의 가역 tail을 실제 downgrade한 뒤 기준 DB와 비교한다.

| metric | operator | target | 뜻 |
|---|---:|---:|---|
| `reversibleRoundtripPassCount` | `eq` | `1` | 최신 불가역 barrier→head→barrier 왕복 경로가 1회 성공 |
| `catalogMismatchCount` | `eq` | `0` | fresh barrier DB와 downgrade candidate의 정규화 catalog 불일치가 없음 |
| `sentinelMismatchCount` | `eq` | `0` | 왕복 전 sentinel이 exact 보존됨 |

환경 조건은 restore-forward target과 같다. 가역 tail이 0이면 graph 재계산과 짝 restore-forward PASS 아래에서만 구조적 `NOT_APPLICABLE`을 허용한다. 가역 tail이 1 이상이면 이 target의 세 관측을 모두 내야 하며 `NOT_APPLICABLE`은 `INVALID_RUN`이다.

## 증거 경계

- producer report 안의 JUnit hash는 `junitSha256`이며 GitHub artifact digest가 아니다.
- artifact download 뒤 importer가 GitHub artifact digest·만료 시각을 축별 `ac11-axis-evidence` 봉투에 결속한다.
- head `0053_eval_suite_project_scope`의 최신 불가역 barrier는 `0052_model_version_digest_scope`이며 reversible tail은 1이다. hosted runner는 fresh 0052 기준 DB와 `0052→0053→0052` candidate를 비교한다.
- 이후 migration PR은 같은 PR에서 fixture manifest와 reversible-tail 기대를 갱신해야 한다. graph와 manifest가 어긋나면 lane은 database 작업 전에 fail-closed 한다.
- label 재실행은 새 head push만으로 자동 발생하지 않는다. 새 head 증거가 필요하면 label을 제거 후 다시 붙이거나 `workflow_dispatch`를 사용한다.
- 같은 PostgreSQL service 안에서 만든 role은 새 cluster role 복원을 증명하지 않는다. 별도 cluster·운영 archive 증거는 AC-11의 다른 축으로 남는다.
