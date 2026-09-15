---
doc_id: "HIST-PROJECT-OBSERVATION-START-20260914"
title: "2026-09-14 PROJECT-OBSERVATION Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-14T17:28:03+09:00"
source_of_truth: "Git"
---

# 실제 서버의 승인·샤드 조회 계약

CX-01/CX-02, owner Codex/reviewer Claude pending, branch agent/codex/workspace-bridge, base6ab96b5c69c0560a0c4135d602a1d44485df210c. 지침GUIDE1.1.0/ADR1.35.13/GOV-AGENT1.1.0/GOV-GIT1.1.0, 진행판1.0.58/Codex1.0.35, agent-delivery1.1.0/core-reliability1.0.0.

실제 configured factory에 project-scoped 승인목록/개별조회와 샤드 부모Run조회 연결. 취소는 기존 부모Run cancel의 원자·멱등·실정지receipt 기반 회수를 정본으로 유지하고 수동reclaim 성공 endpoint는 만들지 않는다. 합격: 실제 HTTP/격리PG/RLS에서 권한없음·다른project/tenant·페이지경계·재생시권한취소 거부·부모없는Run/불완전샤드가 성공으로 보이지 않음. 계약 인계와 관련 회귀검증/CI/동기화 기록. 운영 schema/Node 프로필 변경 없음.
