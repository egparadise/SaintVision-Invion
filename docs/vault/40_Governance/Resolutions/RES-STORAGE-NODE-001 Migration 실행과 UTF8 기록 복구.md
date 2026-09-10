---
doc_id: "RES-STORAGE-NODE-001"
title: "Migration 실행과 UTF8 기록 복구"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T03:15:23+09:00"
source_of_truth: "Git"
---

# Migration 실행과 UTF8 기록 복구

0008을 기존 0001과 같이 driver_connection.execute로 실행하도록 바꿨다. 수정 f4e33b958379e058196135d737539a3cee9d0a85의 Core #34386900927/Docs #34386900905가 success이며 Python 316개 실패/오류/skip 0을 확인했다. 이후 0009/0010도 같은 방식을 사용한다.

한글 파일은 UTF-8 apply_patch 또는 UTF-8 파일 스크립트로 작성하고 stage/commit/push 결과를 순차 확인했다. 외부 사본 13개+새 보고서의 raw hash/변경 내용을 검토해 과거 상태 회귀를 거절하고 저자 제안을 보존한 후 전용 sync state로 재개했다. 자세한 최종 검증은 [[2026-09-10_03-15-23_KST_STORAGE-NODE_Codex_검증보고]].
