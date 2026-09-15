---
doc_id: "HIST-RECOVERY-INTEGRATION-START-20260911"
title: "2026-09-11 RECOVERY-INTEGRATION Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T18:35:40+09:00"
source_of_truth: "Git"
---

# RECOVERY-INTEGRATION 착수

- task: RECOVERY-INTEGRATION, 카드 CX-01/CX-07; 부모 S01-DB/S04-DB/S08-DB/S11-DB/S11-ST. owner Codex, reviewer Claude(아직 승인 없음).
- branch agent/codex/workspace-bridge; base `d14db0a9f6a943a2fa83f0bfdbec50f101556ea8`.
- 읽은 진행판 INDEX-PROGRESS-001 v1.0.14, WORKBOARD-CODEX-001 v1.0.0, GUIDE/GOV-AGENT/GOV-GIT v1.1.0, ADR-INDEX v1.28.0. Skill agent-delivery v1.1.0/core-reliability v1.0.0, engineering:code-review 적용.
- 고정 검토 입력: Claude `dee31e5145954d9d5195e8508133c1d6d78b30c6`(복원 0581964 포함), Gemini `f50310e`, 공통 기록 `d51ddfd`.
- 완성 목표: Claude 복원 도구를 정본 DB 함수 감사와 통합하고 복원 오류/누락/측정 오류/권한·RLS 실패를 거부한다. 단일 정본 도구 유지, 감사용 SQL 패턴 판별을 복원 합격 근거로 쓰지 않는다.
- 합격 증거: 일회용 PostgreSQL 실제 dump→restore, 손상/누락/잘못된 권한과 fencing 경계 실패, RPO/RTO 판정 경계, 소스 및 시험 DB 정리, 동일 코드 SHA 검증. CI/peer/운영 인수는 따로 기록한다.
- 허용 범위: 자체 worktree 코드·시험·계약·Git 전달·Obsidian 반영. 운영 DB/계정/Node/kill switch 변경 없음. 실제 원격 설치 미확인과 CI 계정 제한은 외부 선행이다.
- 종료 시 48개 동일 가중 진행도 재평가 및 다음 담당/첫 행동 기록. 문서나 시험 건수만으로 작업을 100%로 올리지 않는다.
