---
doc_id: "HIST-CODEX-S05-CARD21-LOCK-WAIT-001"
title: "S05 Card21 log_lock_waits 원본·FK-DROP 대조 실측 — HYPOTHESIS_SUPPORTED"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T08:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "postgresql", "log-lock-waits", "pgrowlocks", "lock-timeout", "fk-control"]
---

# S05 Card21 log_lock_waits 원본·FK-DROP 대조 실측

## 결과

Claude 카드 23의 D1~D3와 코디네이터의 08:10/08:33 KST 명시 승인을 반영해 `40b24329`에서 실 PostgreSQL 16 disposable DB 두 개를 순차 사용했다. 제품 코드·계약·migration 파일은 바꾸지 않았고, 대조군은 자기 disposable DB에서 `inv.idempotency → inv.projects` FK 하나만 DROP했다.

| wave | 실행 | 성공/실패 | queue | server log | `pgrowlocks` | timeout |
|---|---|---:|---|---|---|---|
| legacy, FK 있음 | 1 passed, exit 0, 18.45s | 20/0 | waiter 19, depth 1 | transaction acquired 190, tuple 0; waiter별 segment 1~19·holder change 0~18 | 103 snapshots, Key Share+For No Key Update, max holder 20 | 0 |
| legacy, FK-DROP | 1 passed, exit 0, 14.85s | 2/18 | waiter 19, depth 19 | tuple segment, 단일 최대 499.957ms | 4 snapshots, For No Key Update만 | `RES-0007`/`55P03` 18 |

결합 판정은 **`HYPOTHESIS_SUPPORTED`**다. idempotency INSERT의 FK RI KEY SHARE가 이후 project `FOR NO KEY UPDATE`의 tuple-lock FIFO를 우회해 각 waiter가 현재 holder xid를 직접 기다리고, holder 교체마다 `lock_timeout=500ms`가 다시 시작된다. 그래서 원본은 `55P03` 없이 진행할 수 있고 비FIFO 재경쟁의 대기 합이 `statement_timeout=2s`에 닿으면 과거 legacy wave처럼 `57014`가 된다. FK가 선행 잠금을 만들지 않는 candidate limits 행과 FK-DROP 대조군은 tuple FIFO가 깊어져 약 500ms `55P03` cascade를 만든다.

## 하네스와 정직성

- `tools/placement_lock_wait_diagnostic.py`는 로컬 DSN·PostgreSQL 16·승인 컨테이너 포트 일치를 확인하고, phase별 단일 pytest 파일만 실행한다.
- disposable DB에만 `ALTER DATABASE ... SET log_lock_waits=on`, `deadlock_timeout=10ms`를 적용한다. `ALTER SYSTEM`·reload·restart·운영 DSN은 사용하지 않는다.
- observer는 `backend_xid`를 private memory에서 alias로 바꾸고 `pgrowlocks` mode·holder 수를 수집한다. raw PID/xid/server log/DSN은 artifact에 남기지 않는다.
- 두 wave 모두 20동시를 넘지 않았고 candidate·50동시·5노드는 실행하지 않았다. tool의 전후 inventory 비교에서 신규 disposable DB/role 잔존은 0이었다.
- legacy/FK-DROP request P95 2575.213/982.737ms는 logging·observer가 켜진 1회 진단 부수값이며 AC-05·정책 성능 판정에 쓰지 않는다. peak memory는 별도 sampler를 붙이지 않아 미측정이다.
- 첫 combine은 PostgreSQL `pgrowlocks` 실제 mode 문자열 `Key Share`를 하네스가 `For Key Share`로만 기대해 `NOT_OBSERVED`로 분류한 parser 결함이었다. 원본 evidence를 바꾸지 않고 두 표기를 수용하도록 고쳤고 PG-free 분류 시험 3 passed 뒤 같은 두 report를 다시 결합해 `HYPOTHESIS_SUPPORTED`를 얻었다.

보존 evidence: [[s05-lock-wait-card21-40b24329.json]]. 로컬 raw report/JUnit은 `.work/card21`에만 있고 Git에는 넣지 않는다.

## 정책 경계

[[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.4는 B′(candidate limits `lock_timeout` 500→약 1500ms) 뒤 B(project별 bounded semaphore)를 우선한다. 각 옵션은 외부 timeout 합계 legacy 이하, 요청 P95 비악화, post-acquire hold P95 비악화를 동시에 요구한다. A(`FOR NO KEY UPDATE` 전환)는 비FIFO 기아·thundering herd·2초 `57014`를 다시 만들 수 있어 기전 확인용으로만 둔다.

구현은 Claude 카드 24 독립 검토와 코디네이터의 별도 카드 전에는 시작하지 않는다. `placementShortCommit` 기본 off, S05-DB `review`, 20동시 초과·50동시·5노드 미승격을 유지한다.
