---
doc_id: "HIST-CREDENTIAL-PROVISION-START-20260912"
title: "2026-09-12 CREDENTIAL-PROVISION Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T01:17:48+09:00"
source_of_truth: "Git"
---

# CREDENTIAL-PROVISION 착수

CX-02 / S01-BE·S08-ST, owner Codex, reviewer Claude pending. base3fb949a58baa1b6580e214a2c895bd1837f6ab04, branch agent/codex/workspace-bridge. GUIDE1.1 / GOV-AGENT1.1 / GOV-GIT1.1 / ADR1.33 / 진행판1.0.21 / Codex1.0.7 / 운영credential계약1.2.1. 공통 agent-delivery1.1 및 core-reliability1.0 적용.

기존 Linux/DB backend 위에 보호된 운영자 CLI를 추가한다. 명시적 manifest와 보호 DSN 환경, service-owned 기존 secret 파일만 사용하며 실제 운영 secret/DB/Node는 변경하지 않는다. 등록과 Run 권한 부여를 분리하고 원자 회전/회수·멱등 재시도·현재 epoch/tenant/project/Run·감사 무결성을 시험한다. 폐기 권한 자동 재활성화와 파일 덮어쓰기를 금지한다. 합격 증거는 실제 Linux/일회용 PostgreSQL 정상·거부·rollback·동시성 시험, CI 상태, Obsidian 인계다.

Claude 최신 c632d3f/4b09dfc의 운영 RPO 보고를 확인했다. 이번 credential 변경과 섞지 않고 별도 독립 검토 대기로 남긴다. 다른 Agent worktree는 변경하지 않는다.
