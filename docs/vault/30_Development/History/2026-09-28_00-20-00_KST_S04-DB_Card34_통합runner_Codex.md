---
doc_id: "HIST-CODEX-S04DB-CARD34-INTEGRATED-RUNNER-001"
title: "S04-DB Card34 HTTP+PG 통합 Evidence runner"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T05:17:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S04-DB"]
tags: ["history", "s04", "approval", "idempotency", "outbox", "postgresql", "runner"]
---

# S04-DB Card34 HTTP+PG 통합 Evidence runner

## 시작 경계

- branch: `agent/codex/s04-db-runner`
- base: `1e8baf045c5a554209aaef601ae4883b64da50a7`
- 구현 head: `6f0156c7727a92a3afd8c17ed9a6d15dc55af2a2`
- owner/reviewer: Codex/Claude
- delivery: draft R2 [PR #118](https://github.com/egparadise/SaintVision-Invion/pull/118), 사용자 병합 금지
- 계약·migration: 변경 0
- 물리 Node 전송 재개/hash: `UNMEASURED`

[[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]와 [[2026-09-22_20-10-00_KST_S04-DB_S05-DB_S07-DB_검토인계패키지_Claude]]를 대조했다. 기존 `test_approvals.py`, `test_control_api.py`, `test_postgres.py`는 승인 전 실행 차단, 만료·cancel, exact replay, 감사/outbox 원자성, publisher crash 뒤 중복 전달과 consumer rollback/dedup을 각각 이미 검증한다. 빈칸은 이 축을 한 invocation과 한 보고서로 결속하고 물리 경계를 과장하지 않는 runner였다.

## 구현

`tools/run_s04_db_evidence.py`는 `tests/integration/s04_db_runner_case.py` 한 파일만 disposable PostgreSQL에서 실행해 JSON과 JUnit을 만든다. stale artifact를 먼저 제거하고 schema/case inventory/비밀 문자열/공개 계약·migration 불변/물리 전송 `UNMEASURED`를 fail closed로 검사한다.

단일 측정 여정은 다음 네 case를 분리 기록한다.

| case | 실제 경로와 판정 |
|---|---|
| `http-run-idempotency-cancel` | HTTP Run create exact replay, HTTP cancel exact replay, cancel outbox 1건 |
| `approval-before-execution-and-expiry` | HTTP challenge/decision·vote replay, quorum 전 dispatch 0, 승인 만료 뒤 dispatch 0, expiry close exactly once |
| `outbox-publisher-crash-retry` | broker ACK 뒤 주입 crash, 같은 event ID 재전달 2회 |
| `outbox-consumer-rollback-dedup` | consumer 실패 transaction rollback, 다음 1회 commit, exact replay effect 0 |

실패 traceback에 disposable DSN이 노출되지 않도록 raw `SimpleNamespace` fixture를 `<S04Api redacted>` wrapper로 감쌌다. JSON validator도 DSN scheme, password, disposable database/role 식별자를 거부한다.

## 실제 검증과 finding

| 시각·검증 | 실제 결과 |
|---|---|
| PG-free 최초 | 8 passed / 1 failed / exit 1. Windows path separator만 원인이어서 정규화했다. |
| PG-free 교정 | 9 passed / exit 0. |
| direct tool 첫 시도 | PostgreSQL 접속 전 `tools.provenance` import 실패 / exit 1. repo root bootstrap을 추가했다. 이 시도는 실 PG 실행이 아니다. |
| PG-free bootstrap 교정 | 10 passed / exit 0. |
| 실 PG 단일 파일 1회 | 1 failed / exit 1. 제품 `guard_approval_request()`가 `expires_at` 직접 UPDATE를 `CheckViolation`으로 거부했다. JSON은 생성되지 않았다. |
| PG cleanup 확인 | `inv_test_*` database 0, 기존 `inv_app_*` role 2, 신규 잔존 0. |
| 하네스 교정 뒤 PG-free | 11 passed / exit 0, collect-only 1 case / exit 0. |
| 승인된 교정본 실 PG 단일 파일 | 1 passed / 2 warnings / 12.65s / exit 0. 네 case 모두 PASS, JSON·JUnit 생성. |
| 교정본 cleanup 확인 | `inv_test_*` database 0, 실행 전부터 있던 `inv_app_*` role 2 유지, 신규 잔존 0. |

실 PG 실패는 제품 결함이 아니라 하네스가 immutable approval scope를 직접 변경한 결함이다. 기존 제품 시험과 같은 방식으로 요청 전에 2초 만료 정책을 만들고 실제 시계 경과를 기다리도록 바꿨다. 직접 UPDATE가 되살아나면 PG-free 시험이 실패한다. 최초 실패 JUnit은 disposable 자격증명 표현 가능성이 있어 보존·커밋하지 않고 제거했다.

교정본 evidence는 [[s04-db-card34-35d7250c.json]]과 [[s04-db-card34-35d7250c.xml]]에 보존했다. 고정 code SHA `35d7250cba481b944846f385366e63c6dff9317a`의 clean worktree에서 HTTP status `201/201/200/200`, cancel outbox 1, 승인 전·만료 후 dispatch 0, authorized command outbox 0, publisher 동일 event 재전달 2, consumer committed effect 1·duplicate effect 0을 관측했다.

## 현재 판정과 다음 행동

사용자의 자동 승인 뒤 교정본을 같은 단일 파일로 한 번 실행해 4 case PASS·cleanup 0·비밀 0을 확인했다. 이 결과는 물리 Node 전달 재개나 운영 인수를 뜻하지 않으므로 S04-DB를 `done`으로 올리지 않는다.

R2 PR #118에서 Claude가 제품 불변식 재사용, 실패 주입, redaction, 물리 Node `UNMEASURED` 경계를 검토한다. S04-DB는 `review`를 유지하고 사용자 지시대로 병합하지 않는다.
