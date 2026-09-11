---
doc_id: "HIST-PROVISIONING-INTEGRITY-START-20260911"
title: "PROVISIONING-INTEGRITY Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T14:17:10+09:00"
source_of_truth: "Git"
---

# 계정 준비와 통합 권한 경계 착수

사용자의 재개 요청에 따라 base c9dea3f93216aad3a0172b323b3da71ed3d62ca7, branch agent/codex/provisioning-integrity에서 진행한다. Claude c6ed473e300dce4a7551b7b6c171323d66dfb877은 저자를 보존해 b4eaa8d로 가져왔다. 충돌한 결과/준비 상태 API는 최신 canonical 구현을 유지했다. 읽은 기준은 GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001 v1.0.0, ADR-INDEX-001 v1.23.0, agent-delivery/core-reliability v1.0.0이다. 관련 registry task는 S01-BE/DB, S03-BE, S12-BE, 연관 Claude S02-BE/DB다.

완성 목표: 기존 OIDC 계정을 바꾸거나 비활성 권한을 재활성화하지 않고 명시적 요청/승인 grant와 계정 연결을 원자 준비한다. 합격 증거: 실제 PostgreSQL의 현재 계정/멤버십/epoch 검사, 충돌 거부, 동일 요청 동시 실행 1개 감사, 늦은 실패 rollback, 실제 JWT API에서 draft 생성, 두 migration history upgrade/replay다. 실행 프로필/Workspace 준비는 이 도구의 권한 부여와 별도다.

Prompt는 현재 사용자 재개 요청, Context는 위 문서/소스 SHA, Harness는 tools/check_kernel_docker.py의 격리 PostgreSQL/Go/Node와 공개 Evidence, Skill은 위 두 v1.0.0이다. ROOF/Graph 계약 변경은 권한 준비 경계의 ADR-068로 기록한다. 작성자 Codex, 독립 reviewer Claude 대기.

14:10 KST 실제 원격 192.168.45.225는 online/fresh, lan-observe-v1이었다. 기존 worker 설치 결과는 미수신이다. 운영 계정/DB/epoch/Node/kill switch 변경 없이 별도 worktree와 disposable DB에서 검증한다. 공유 root의 Gemini 미커밋 UI는 보존한다.
