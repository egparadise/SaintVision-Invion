---
doc_id: "HIST-NODE-CONTAINMENT-INIT-001"
title: "2026-09-10_14-47-19_KST_NODE-CONTAINMENT_Codex_개발과정"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T14:47:19+09:00"
source_of_truth: "Git"
---

# NODE-CONTAINMENT 시작

task NODE-CONTAINMENT / S07-BE·DB 및 S08-BE·DB 부분 범위, OUT-07/08, AC-07/08. owner Codex, reviewer Claude pending. base `990f3f3a89cef6f6e8c7dd1236d8f2518041fc4f`, branch `agent/codex/node-containment`, 별도 worktree `.worktrees/codex-node-containment`. 기존 PR16의 Core/Backend/Documentation push·PR CI 6개 성공과 실제 962개 시험·268개 Obsidian 동기화를 확인했다. 독립 인수나 전체 Sprint done을 전제하지 않는다.

읽은 지침: GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/PLAN-DB-001/PLAN-STORAGE-001 v1.0.0, ADR-INDEX-001 v1.15.0, CODEX-REMAINING-001 v1.7.0, CODEX-BUSINESS-KERNEL-001 v1.0.0, task-registry S07-BE/S08-BE와 선행 조건. agent-delivery/core-reliability Skill v1.0.0을 적용한다.

목표는 현재 operator 권한으로 tenant kill switch와 Node drain을 durable하게 기록하고, 신규 실행 차단·기존 실행 취소/정리·안전한 명시적 재개를 실제 영수증에 연결하는 것이다. 주기 heartbeat 및 delivery worker를 재사용하고 bounded reconciliation을 추가한다. lock 순서, kill/예약/완료 경합, queued/uncertain/running, crash 뒤 계속 취소, 미발급 예약 회수, RLS·멱등성·권한 철회 및 실제 Go/mTLS/Docker 종료를 합격 증거로 요구한다. UI·운영 PKI·실제 5대 시험·무승인 재실행은 이 작업의 완료 주장에 포함하지 않는다.

`git status --short`, `git worktree list`, 지침/계약 코드 읽기, 기존 SHA CI 조회 exit 0. `git worktree add -b agent/codex/node-containment .worktrees/codex-node-containment 990f3f3a89cef6f6e8c7dd1236d8f2518041fc4f` exit 0. 구현/제품 CI는 아직 실행하지 않았다. 이후 실제 코드 SHA·명령/exit·CI ID·오류/해결·sync 결과를 후속 History와 PR에 남긴다.
