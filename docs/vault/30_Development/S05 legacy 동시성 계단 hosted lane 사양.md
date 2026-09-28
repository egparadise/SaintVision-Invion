---
doc_id: "CODEX-S05-LEGACY-STAIRCASE-LANE-SPEC-001"
title: "S05 legacy 동시성 계단 hosted lane 사양"
version: "1.0.0"
status: "implementation-ready"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T16:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "legacy", "hosted-ci", "benchmark", "staircase"]
---

# S05 legacy 동시성 계단 hosted lane 사양

## 1. 목적과 opt-in 경계

[[S05 bounded admission 후속 결정 제안]] v1.2에 따라 legacy(flag off)가 hosted PostgreSQL 16에서 처음 degrade하는 concurrency를 찾는다. `.github/workflows/s05-legacy-staircase.yml`은 `run-s05-legacy-staircase` PR label 또는 수동 `workflow_dispatch`에서만 실행되며 기본 PR/push CI와 skip map에 영향을 주지 않는다.

- rung은 `20→35→50`, 각 3 wave, wave는 한 번에 하나씩 순차 실행한다.
- 한 rung의 세 wave를 모두 마친 뒤 degrade를 판정하며, 첫 degrade 뒤 높은 rung은 실행하지 않는다.
- candidate/short-commit/semaphore/B-prime arm은 실행하지 않는다. flag 기본값은 off다.
- 공개 계약·migration·registry status 변경은 없다. S05-DB는 `in_progress`, 승격과 AC-05 판정은 없다.

## 2. DB 격리와 실행 증거

각 wave는 `tools/placement_benchmark.py`를 별도 프로세스로 실행한다. pytest session fixture가 `inv_test_<uuid>` DB와 전용 runtime role을 만들고 migration head를 적용한 뒤 강제 삭제한다. 보고서에는 DB 이름 대신 SHA-256 fingerprint만 기록한다.

lane은 다음을 fail closed로 확인한다.

1. wave 전후 hosted service의 `inv_test_%` DB 수가 0이다.
2. 실행된 모든 wave의 DB fingerprint가 서로 다르다. 즉 rung별 새 DB보다 강한 wave별 새 DB다.
3. `codeSHA`는 synthetic merge SHA가 아니라 checkout한 PR head와 정확히 같다.
4. `projectSemaphore.enabled=false`, registry entry/permit 잔존 0, `uniqueFencingTokens=true`, `noOverbooking=true`, `acceptanceClaim=false`다.
5. wave별 JSON·JUnit·redacted log와 aggregate JSON·JUnit을 artifact로 14일 보존한다.

runner OS/arch/image, CPU·메모리, Python·PostgreSQL 버전, service default timeout/max connections를 기록한다. DSN·password·DB 이름·tenant/project/run 식별자는 aggregate에 넣지 않는다. hosted 수치는 환경 고유 calibration이므로 개발 PC 수치와 직접 합치거나 절대값 비교하지 않는다.

## 3. 사전 degrade 기준

각 rung의 세 wave가 완결된 뒤 다음 중 하나면 첫 degrade다.

1. `55P03+57014`가 한 wave라도 1건 이상 — 세 wave **최대값** 판정
2. request P95 all 세 wave 중앙값이 `2000.000ms` 초과 — 세 wave **중앙값** 판정

최대값과 중앙값 혼용은 의도적이다. 기준 1은 드문 timeout을 숨기지 않고, 기준 2는 대표 누적 지연을 본다. 기준 2는 개별 SQL `statement_timeout=2000ms`와 별개인 요청 전체 누적 경로 기준이다. 여러 statement가 각각 2초 전에 끝나도 전체 요청 지연은 2초를 넘을 수 있다. `2000.000ms` 동률은 degrade가 아니며 측정 뒤 기준을 바꾸지 않는다.

hold P95/max와 legacy lock-wait P95/max는 진단으로만 기록한다. workflow/service/pull/setup/cleanup/fingerprint 실패는 제품 degrade가 아니라 `INVALID_RUN`이며 수치를 판정에 쓰지 않는다.

## 4. 결과 결정과 롤백

- 20/35/50에서 degrade: 해당 rung까지 보존하고 같은 concurrency candidate(W=0, N 후보) 비교는 별도 설계·승인을 받는다.
- 50까지 degrade 없음: 측정한 hosted 범위에서 semaphore가 풀 문제가 없으므로 semaphore 라인을 닫고 legacy를 확정한다.
- 어느 결과든 flag off, S05-DB `in_progress`, 승격 없음은 유지한다.

aggregate JUnit green은 측정 완결만 뜻하며 성능 합격을 뜻하지 않는다. 판정은 JSON의 `DEGRADE_AT_<N>` 또는 `NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE`으로 별도 기록한다.

롤백은 신규 workflow·runner·focused 시험과 integration report의 redacted DB fingerprint 필드를 제거하는 것으로 끝난다. 제품 경로·계약·migration에는 롤백 대상이 없다.
