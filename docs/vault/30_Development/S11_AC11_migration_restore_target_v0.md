---
doc_id: "S11-AC11-MIGRATION-RESTORE-TARGET-001"
title: "S11 AC-11 migration restore-forward target v0"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T13:51:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S11-BE", "S11-DB"]
tags: ["ac11", "migration", "restore", "target"]
---

# S11 AC-11 migration restore-forward target v0

이 문서는 `irreversible-restore-forward` 축을 실행하기 전에 고정하는 판정 목표다. 이 목표는 단일 hosted PostgreSQL 16 서비스의 합성 migration·restore 리허설만 판정하며 운영 PITR, 별도 장애 영역, 물리 5노드 복구를 대신하지 않는다.

## 사전 등록 기준

| metric | operator | target | 뜻 |
|---|---:|---:|---|
| `restoreForwardPassCount` | `eq` | `1` | 불가역 head 직전 snapshot을 새 disposable DB에 복원하고 head로 전진한 경로가 1회 성공 |
| `catalogMismatchCount` | `eq` | `0` | source head와 restore-forward head의 정규화 catalog 불일치가 없음 |
| `negativeFixturePassCount` | `eq` | `3` | 기존 객체 삭제, 0009 중복 key, ellipsis no-op 부정 fixture가 모두 EXPECTED_FINDING |

`requiredEnvironment`는 `topology=hosted-single-postgres-service`, `synthetic=true`다. 세 metric 중 하나라도 누락되거나 분모가 0이거나 artifact·checkout provenance·cleanup이 불완전하면 `INVALID_RUN`이다. 관측값이 목표를 어기면 `MEASURED_FAIL`이다.

## 증거 경계

- producer report 안의 JUnit hash는 `junitSha256`이며 GitHub artifact digest가 아니다.
- artifact download 뒤 importer가 GitHub artifact digest·만료 시각을 축별 `ac11-axis-evidence` 봉투에 결속한다.
- 현재 migration graph의 reversible tail이 0일 때 `migration-reversible-segment`는 정본 graph 재계산과 짝인 restore-forward PASS가 함께 있을 때만 구조적 `NOT_APPLICABLE`이다.
- label 재실행은 새 head push만으로 자동 발생하지 않는다. 새 head 증거가 필요하면 label을 제거 후 다시 붙이거나 `workflow_dispatch`를 사용한다.
- 같은 PostgreSQL service 안에서 만든 role은 새 cluster role 복원을 증명하지 않는다. 별도 cluster·운영 archive 증거는 AC-11의 다른 축으로 남는다.
