---
doc_id: "HISTORY-20261001-CARD171-AC11-ACCESSIBILITY-CODEX"
title: "CARD-171 AC-11 accessibility-e2e hosted 측정 선택"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T12:52:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7851412db792b4ef6c53cb92944be530d77eb2de"
task_ids: ["S11-BE", "S11-FE"]
tags: ["card-171", "ac-11", "accessibility", "e2e", "hosted"]
---

# CARD-171 AC-11 accessibility-e2e hosted 측정 선택

## 선택 근거

- 기준은 train 5 `7851412db792b4ef6c53cb92944be530d77eb2de`다.
- AC-11 8축 중 migration reversible/restore와 security는 이미 hosted 측정 수단이 있다.
- actual PITR, 물리 5노드 부하·복구, composite long-soak는 외부 전제가 남는다.
- accessibility-e2e에는 실제 browser journey와 desktop invariant producer가 있지만
  AC-11 전용 fail-closed collector·Evidence가 없다. 따라서 코드로 닫을 첫 공백으로
  선택했다.

## 사전 등록

[[S11_AC11_accessibility_e2e_hosted_target_v0]]에 정본 journey 5개, invariant 9개,
DOM contrast 3개, keyboard 2개와 동일 SHA 수동 인수 completeness를 결과를 보기 전에
고정했다. 수동 인수가 없는 hosted-only run은 `manualAcceptanceMissingCount=1`로 남아
`MEASURED_FAIL`이며, 자동 PASS나 AC-11 완료로 승격하지 않는다.

## 다음

이 target이 들어간 commit/blob을 collector에 결속하고, PG-free 부정 시험과 opt-in
hosted workflow를 구현한다. 실제 hosted 결과와 run ID는 실행 뒤 별도 절에 추가한다.

## 구현 결과

- 사전 target commit은 `a3ed04f189d5b2b7672348069b160a95be620267`, target blob은
  `7ec8eb1409531011737eaea79c4516bb130cf990`으로 고정했다.
- `tools/collect_ac11_accessibility_e2e.py`는 정본 journey 5개, invariant 9개, contrast
  3개, keyboard/focus 2개를 raw report에서 재계산한다. source/tree/clean checkout과
  입력 SHA-256을 결속하고 producer summary를 신뢰하지 않는다.
- 수동 인수 producer는 아직 없으므로 `manualAcceptanceMissingCount=1`과
  `acceptanceClaim=false`를 강제한다. 자동 결함이나 미수행을 0/PASS로 바꾸지 않는다.
- `.github/workflows/ac11-accessibility-e2e.yml`은 dispatch 또는
  `run-ac11-accessibility` label에서만 exact PR head를 checkout하고, job-level
  `cancel-in-progress:false`, credential 0, artifact 30일로 실행한다. 기본 CI와 skip map은
  바꾸지 않았다.
- PG-free 단일 파일 `tests/test_collect_ac11_accessibility_e2e.py`는 11 passed다. journey
  누락·skip/실패, invariant PARTIAL 재분류, contrast flag 위조, SHA drift, 수동 인수
  fabrication과 workflow opt-in 경계를 되살림 방지 시험으로 고정했다.

## 판정 경계

이 구현은 축을 측정 가능한 `MEASURED_FAIL`/`MEASURED_PASS` 상태로 만드는 raw hosted
producer다. 최초 hosted run ID와 artifact digest는 PR에서 실행한 뒤 기록한다. 이 카드
자체로 AC-11 done, S11-BE 점수 상승, 사용자 장비 접근성 인수를 주장하지 않는다.
