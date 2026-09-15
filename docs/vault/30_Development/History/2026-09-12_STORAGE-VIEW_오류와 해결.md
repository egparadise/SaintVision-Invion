---
doc_id: "ERR-STORAGE-VIEW-20260912"
title: "2026-09-12 STORAGE-VIEW 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T14:15:21+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-VIEW 오류와 해결

처음 Windows67개에서65통과/2실패(exit1). 사용자 계정 fixture의 disabled는 실제 status enum에 없으므로 suspended로 수정했다. 저장 서명 변조가 입력 verifier의422로 응답하던 것은 저장 기록 무결성 오류409로 정규화했다. 이어69개 통과 후 DB session timezone을UTC로 가정하던 비교를 UTC 의미 비교로 고치고 Asia/Seoul 실제 DB 시험을 추가했다. 제품9d7559e Windows25/Linux153 통과(exit0).

CI6개는 account payments/spending limit 때문에 시작 전 실패. 반복 재실행하지 않았으며 계정 조치 뒤 같은 SHA 실행이 필요하다. Obsidian4개 외부 수정은 원문/hash를 보존하고 수신 요약을 반영한 뒤 동일 bytes 인수 절차로 동기화한다. 다른 Agent 작성자 보고를 독립 승인으로 바꾸지 않는다.
