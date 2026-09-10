---
doc_id: "ERR-NODE-CONTAINMENT-TENANT-001"
title: "NODE-CONTAINMENT tenant 격리 시험 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:23:28+09:00"
source_of_truth: "Git"
---

# 미등록 tenant와 등록된 다른 tenant의 구분

2026-09-10 15:23 KST, 구현 `18e2d236d3e3ffd1e8e76363601a241a69bdfa05`의 [Core Build 34443537621](https://github.com/egparadise/SaintVision-Invion/actions/runs/34443537621) artifact를 확인했다. 전용 21개는 통과했으나 전체 983개 중 `test_rls_and_queue_state_guards_reject_content_change_reexecution_and_false_stop` 1개가 실패했다. pytest exit 1, errors/skipped 0. 아직 완료되지 않은 후속 SHA의 결과로 대신하지 않는다.

기존 시험은 등록하지 않은 임의 UUID로 runtime transaction을 열고 조회 결과 0개를 기대했다. 새 tenant containment barrier는 제어 행이 없는 tenant를 AUTH-0060/503으로 거부하므로 조회에 도달하지 않았다. 데이터 노출이 관측된 오류가 아니며 fail-closed 장벽을 완화할 이유가 없다. [[NODE-CONTAINMENT tenant 격리 시험 해결]]에서 실제 다른 tenant의 RLS 검증을 유지한다.
