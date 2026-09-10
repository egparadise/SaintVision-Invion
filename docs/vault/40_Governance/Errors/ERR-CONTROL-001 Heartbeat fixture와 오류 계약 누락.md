---
doc_id: "ERR-CONTROL-001"
title: "ERR-CONTROL-001 Heartbeat fixture와 오류 계약 누락"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:31:57+09:00"
source_of_truth: "Git"
---

# ERR-CONTROL-001 Heartbeat fixture와 오류 계약 누락

초기 구현 63ec7d465c1501d0e2274d0eeda75afd12bde482의 Core CI #34381950400에서 Python 273 passed / 1 failed. 실패는 test_real_mtls_probe_restores_offline_node_and_rejects_replay에서 heartbeat-only fixture에 없는 command를 container(a)가 참조한 AttributeError였다. 실제 제품 명령 실행 결함으로 보고하지 않는다. 해당 run의 Go race와 문서 검사는 통과했다.

추가 자체 검토에서 공개 API ProblemDetails의 category/traceId/causeRef/evidenceId와 W3C traceparent 상관관계 응답이 빠진 것을 확인했다. 이는 개발 중 계약 누락이며 운영 사고가 아니다. [[RES-CONTROL-001 비실행 검증과 추적 오류 응답]]을 따른다.

CI evidence helper를 완료 전 두 차례 호출해 assert가 exit 1이었으며 당시 GitHub 상태는 in_progress였다. 제품 테스트 실패로 합산하지 않는다. 완료 후 artifact를 내려받아 검증했다.

로컬 sync 회귀 명령을 존재하지 않는 tests/test_sync_obsidian.py로 한 번 지정해 수집 exit 4였다. 실제 CI 경로 tools/test_sync.py를 확인해 실행했다. 제품 테스트 결과에 합산하지 않는다.
