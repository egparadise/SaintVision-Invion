---
doc_id: "HISTORY-20261001-CARD171-AC11-ACCESSIBILITY-CODEX"
title: "CARD-171 AC-11 accessibility-e2e hosted 측정 선택"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T12:42:40+09:00"
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
