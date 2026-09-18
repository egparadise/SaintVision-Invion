---
doc_id: "ERR-NODE-AUTH-COMMIT-20260912"
title: "2026-09-12 NODE-AUTH-COMMIT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T11:46:52+09:00"
source_of_truth: "Git"
---

# 2026-09-12 NODE-AUTH-COMMIT 오류와해결

- 원본345cc1a에서 ASGI 인증서 오류가 무시되고, 인증 뒤 회수/교체를 끼워 넣어도 heartbeat가 적용됐다. 실제 DB 원본3개 assertion failure로 확인하고2830887에서 실패 transport의 proxy fallback 금지와 기록 transaction의 current binding row lock으로 수정했다.
- 초기 새 API 시험3개는 AUTH 오류를401로 기대해 실패했다. 기존 errors.py의 AUTH는403이다. 서비스 응답을 바꾸지 않고 시험을403 및 AUTH-INVALID-CREDENTIAL/기록0으로 정정했다. 최종 Windows89/Linux89 통과.
- 같은 SHA Actions6개는 계정 결제/한도 문제로 실행 전 차단됐다. 로컬 성공을 CI 성공이라고 표시하지 않는다.
- Obsidian 외부 공통 진행판/Claude 작업판 편집으로 check exit1·쓰기0. 외부 원문2개를 hash와 함께 보존하고 새 보고는 작성자 수신 정보로 병합했다. 외부본에서 누락된 기존 Codex review/handoff 기록을 제거하지 않는다. [[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]].

