---
doc_id: "HIST-CODEX-S05-CARD47-CLEAN-BASE-001"
title: "S05 Card47 semaphore 없는 clean-base legacy lane"
version: "1.0.0"
status: "implementation-ready"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T17:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "legacy", "hosted-ci", "clean-base"]
---

# S05 Card47 semaphore 없는 clean-base legacy lane

## 결정과 범위

코디네이터는 Card46의 `NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE`을 비준하고 #115·#141 제품 semaphore 스택을 병합하지 않기로 했다. 이 PR은 integration `1e8baf045c5a554209aaef601ae4883b64da50a7` 위에서 다음만 다시 구성한다.

1. Card42 v1.1 결정 내용과 Card46 종료 결정
2. legacy-only 20→35→50 hosted opt-in workflow·runner·PG-free 시험
3. Card46 정본 aggregate evidence와 History
4. benchmark schema 1.7에 일회용 DB 이름 대신 fingerprint·비노출·lifecycle을 더하는 최소 증거 필드

Card46 aggregate JSON은 `docs/vault/30_Development/Evidence/s05-card46-legacy-staircase-36362386530.json`에 원문 보존하며 SHA-256은 `2244f6c244e06672bfeaf2c9ac24b054efa6b0c30648db6076efa9b6f2845eae`다.

## 비이식 확인

`services/control-plane/src/inv/db.py`, `placement.py`, public contract, migration, `tools/placement_benchmark.py`는 integration base와 동일하게 유지한다. `--project-semaphore`, DB root transaction lifecycle wrapper, placement permit 경로를 가져오지 않는다. S05-DB는 `in_progress`이고 물리 5노드 AC-05는 별도다.

## 검증·hosted 경계

로컬은 PG-free focused 시험과 workflow/docs/ontology 게이트만 실행한다. 새 hosted run은 PR head에서 동일한 legacy staircase 명령이 clean base에서도 완결되는지만 확인하며 `runPurpose=clean-integration-base-execution-compatibility`, `canonicalDecisionEvidenceRunId=36362386530`, `mayReplaceCanonicalDecision=false`를 남긴다. 수치가 달라도 기존 정본 결론을 소급 변경하지 않는다.

정본: [[S05 bounded admission 후속 결정 제안]], [[S05 legacy 동시성 계단 hosted lane 사양]], [[2026-09-28_16-50-00_KST_S05_legacy_동시성_계단_Codex]].
