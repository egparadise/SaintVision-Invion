---
doc_id: "GOV-AGENT-001"
title: "Agent 역할과 인계 계약"
version: "1.1.2"
status: "baseline"
author: "Codex"
updated: "2026-09-21T18:14:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Agent 역할과 인계 계약


## 작업 배정 기준

| 난도·영역 | owner | reviewer | 배정 조건 |
|---|---|---|---|
| 분산 상태·보안·데이터 손상 위험·공통 계약 | Codex | Claude | 동시성, fencing, 권한, 복구, 다영역 불변 조건 |
| 업무 로직·일반 DB·통합·문서 | Claude | Codex | 확정 계약 아래 중간 난도 구현 |
| 디자인·Frontend·웹 배포 | Gemini | Claude, 보안 경계는 Codex | Antigravity에서 실행·브라우저 검증 |

Codex는 공통 계약 통합 책임자다. Claude는 중간 난도 구현과 독립 검토를 소유한다. Gemini는 디자인 결정과 Frontend·웹 배포를 소유한다. 개발 Agent 역할은 제품 내부 Supervisor/Executor/Verifier와 혼동하지 않는다.

## Frontend와 API 계약의 경계

Codex는 canonical API 응답 스키마·생성 타입·backend 경계 검증·공유 fixture와 계약 적합성 시험을 소유하고, Gemini는 `apps/web` 화면·상태·렌더링·접근성·브라우저 동작을 소유하며, Codex의 `apps/web` 수정은 계약 전용 adapter/type/conformance-test 변경으로 제한하고 화면 동작 변경은 Gemini 인계로 분리한다.

## 시작 시 읽을 Context

최우선 재개 페이지는 [[전체 개발 진행 현황]]과 [[Codex 작업 현황]]·[[Claude 작업 현황]]·[[Gemini 작업 현황]]·[[Orca 작업 현황]]이다. 시작/종료 기록과 공통 집계·동시 수정 처리 규칙은 [[Agent 지속 개발 운영 규칙]]을 따른다. 수신 확인 전에 타 Agent가 실행 중/검토 완료라고 표시하지 않는다.

1. 저장소 루트 `AGENTS.md`와 자신의 `CLAUDE.md` 또는 `GEMINI.md`.
2. [[최종 개발 계획 - 모든 개발의 지침]]과 [[설계 충돌 정정 및 ADR]].
3. 자기 영역 계획, 배정 작업, 선행 작업의 build·report·검토 결과.
4. 관련 계약·오류·Skill 버전과 수정 허용 경로.

도구가 진입 파일을 자동으로 읽는다고 가정하지 않는다. 시작 기록에 읽은 doc ID·버전·base SHA를 남긴다. 모델 세션이 바뀌어도 작업 기록과 Git 정본으로 재개한다.

## TaskCard 계약

필수 필드: `task_id, sprint, area, owner, reviewer, status, depends_on, outcome_ids, acceptance_ids, contract_refs, skill_refs, scope, evidence_required, next_handoff`.

상태는 `planned → ready → in_progress → review → done`, 작업 차단은 `blocked`다. 제품 Run 상태와 다르다. ready는 선행 조건·권한·시험 데이터가 준비됐다는 뜻이다. done은 검증·push·build·report·교차 검토가 모두 성공해야 한다.

## Handoff 계약

발신자, 수신자, task ID, base/implementation commit SHA, branch, 변경 경로, 계약 버전, 실제 명령·종료 코드, build URL/ID, 증거 링크, 남은 오류, 다음 행동을 보낸다. 공유는 Git의 작업 기록과 Obsidian 링크로 수행한다. 다른 Agent에게 실제 전달하지 않았다면 `전달 대기`로 표시한다.

한 파일에 동시 쓰기를 피한다. 각 Agent는 별도 브랜치·worktree를 사용하고, 같은 계약 변경은 owner를 통해 통합한다. 타 Agent 파일을 덮어쓰지 않는다. 검토 실패는 원 owner에게 돌려보내고 수정 커밋에서 같은 실패 사례를 재검증한다.

## Skill 패키지

저장소 `skills/`의 `agent-delivery`, `core-reliability`, `service-integration`, `frontend-delivery`를 사용한다. 각 Skill은 입력·산출물·범위·실패 대응·버전을 가진다. 모델·공급자 변경은 역할과 계약 변경을 자동 의미하지 않는다.

## 권한

기존 사용자 승인과 현재 실행 환경의 권한을 확인한다. 이미 승인된 작업을 반복 승인 요청으로 중단하지 않는다. 삭제·강제 push·자격 증명 변경·공개 배포를 일반 commit/push 승인으로 확대하지 않는다. 필수 시스템 승인 실패는 실제 실패 사유와 함께 기록한다.
