---
doc_id: "HIST-ACCOUNT-KERNEL-START-20260911"
title: "ACCOUNT-KERNEL Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T13:00:00+09:00"
source_of_truth: "Git"
---

# 계정·프로젝트와 실행 커널 통합 착수

사용자 후속 진행 지시에 따라 ACCOUNT-KERNEL(S01-BE/S02-BE/S02-DB/S03-BE/S12-BE)을 수행한다. owner Codex / Codex 수정 reviewer Claude 대기. base `97e68af8dfe7b886e72f26efe8f5bb20e717a713`, 브랜치 `agent/codex/account-kernel-integration`, 별도 worktree를 사용한다. Claude 작성 `ad71868`, `ece6fea`, `001fbee`, `5e0fed9`의 독립 검토와 실행 커널 통합, DB 이력 병합·권한 경계 검증이 범위다. Claude 저자 변경과 Codex 통합 수정을 구분한다.

입력은 GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001 및 agent-delivery/core-reliability v1.0.0, ADR-INDEX-001 v1.21.0/ADR-063, docs/task-registry.json의 배정 작업이다. Prompt는 사용자 후속 진행 지시, Context는 위 문서/base와 실제 소스, Harness는 실행 명령·고정 코드 SHA·공개 Evidence로 기록한다.

합격 증거는 별도 PostgreSQL의 신규/기존 양쪽 migration 이력 upgrade, 실제 JWT 검증과 현재 사용자/프로젝트 권한 거절, 승인·실행 API 정합성 및 회귀 시험이다. 운영 DB·사용자·자격 증명은 시험 대상이 아니다. 실제 IdP 배포·운영 권한 부여·물리 Node 실행을 시험 identity로 대체하지 않는다.

12:55 KST 실측 원격 192.168.45.225는 online/fresh, lan-observe-v1이다. [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]의 설치 결과가 아직 없어 실제 원격 실행은 대기 중이다. 서버 bootstrap/observer/UI와 기존 작업 checkout을 유지한다. Gemini 2e049ee 화면의 고정 Evidence/자원 fallback은 후속 owner 수정·실제 API 인수 항목이다.
