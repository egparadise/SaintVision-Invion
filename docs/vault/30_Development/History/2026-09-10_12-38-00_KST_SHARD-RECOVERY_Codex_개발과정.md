---
doc_id: "HIST-SHARD-RECOVERY-INIT-001"
title: "SHARD-RECOVERY 개발 과정"
version: "1.0.0"
author: "Codex"
status: "in_progress"
updated: "2026-09-10T12:38:00+09:00"
source_of_truth: "Git"
---

# SHARD-RECOVERY 개발 과정

- 작업: SHARD-RECOVERY, S03-BE·S05-DB·S07-BE·S07-DB 실행 계약 보강.
- 기준: GUIDE-001·GOV-AGENT-001·GOV-GIT-001·PLAN-BACKEND-001·PLAN-DB-001·PLAN-STORAGE-001 v1.0.0, ADR v1.13.0, agent-delivery·core-reliability v1.0.0.
- 준비: 2026-09-10 12:37 KST, base `a70aff43262b7457098d68c0d5b8a662aad4742a`, branch `agent/codex/shard-recovery`, 별도 worktree. `git fetch origin`, `git worktree add` exit 0.
- owner Codex, 독립 reviewer Claude 대기. 공용 worktree와 Gemini 변경은 보존한다.

목표는 독립 샤드의 새 승인 기반 재실행과 대체 Node 실행이다. 종료한 부모·자식 Run은 보존하고, 물리적 종료가 모두 확인된 계획에서 새 Run과 승인을 준비한다. 승인 소비·예약·claim·queue·복구 계보를 한 트랜잭션에 연결한다. 원 실행을 포함해 최대 3개 실행 세대만 허용한다. 승인 만료로 실행되지 않은 준비 요청은 이 실행 횟수에 포함하지 않는다.

합격 증거는 새 승인 누락·원 실행 종료 미확인·변경된 작업·권한 철회·오래된 epoch·경합·중간 실패에서 실행과 예약이 남지 않는 실제 PostgreSQL 시험, 두 개 Go Node/mTLS/Docker 실행과 출력 집계, 같은 SHA의 CI·문서 검사·Obsidian sync 기록이다. 이는 한 CI 호스트 안의 별도 Node 프로세스 시험이며 5대 PC 검증이 아니다. MPI/NCCL 통신과 UI 복구 버튼은 별도 범위다.

현재 상태는 구현 전이다. 이후 명령·exit code·SHA·CI·sync·다음 담당자를 검증 보고서에 기록한다.
