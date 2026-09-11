---
doc_id: "HIST-RPO-CAPABILITY-START-20260912"
title: "2026-09-12 RPO-CAPABILITY Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T01:33:31+09:00"
source_of_truth: "Git"
---

# RPO-CAPABILITY 착수

CX-01/09 / S11-DB·S12-DB, owner Codex / reviewer Claude pending. basef46b399ab92bf37e68d957cdbcc258fe05a3f956, branch agent/codex/workspace-bridge. GUIDE/GOV-AGENT/GOV-GIT1.1, ADR1.34, 진행판1.0.23, Codex1.0.8. agent-delivery1.1 및 core-reliability1.0 적용.

Claude4b09dfc/c632d3f와 후속8a8f3b4를 검토한다. 현재 정본의 definer/복원/DB 기록 수정을 보존하며 RPO capability만 선별 통합한다. archive_timeout을 전송·복원 RPO 상한으로 확정하는 오류와 raw archive_command 노출, CLI/DB 목표 판정 불일치를 수정한다. 운영 DB/Node는 변경하지 않고 원본 pure 함수 재현·격리 PostgreSQL no-op/failing archiver·실제 복원/기록 회귀로 확인한다. 8a8f3b4의 세 record fault는 현재 Codex 정본에서 이미 수정·시험되어 있으며 새 backup ledger 연결은 별도 검토다. Claude worktree를 변경하지 않는다.
