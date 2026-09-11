---
doc_id: "HIST-FIRST-RUN-START-20260911"
title: "FIRST-RUN Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T10:50:59+09:00"
source_of_truth: "Git"
---

# FIRST-RUN 착수

Task FIRST-RUN / S03-BE·S04-DB·S06-BE 후속, owner Codex / reviewer Claude 대기. base `87ce97a1297a77c529ef1ded4bf21d06ff3f2c9e`, branch `agent/codex/dev-environment`. GUIDE-001, GOV-AGENT-001, GOV-GIT-001, PLAN-BACKEND-001, task registry v1.0.0와 ADR-INDEX-001 v1.20.0을 확인했다. agent-delivery/core-reliability v1.0.0을 적용한다.

목표: 기존 실행/실패/checkpoint를 시험 데이터로 만들어야만 Workspace 프로그램을 실행할 수 있는 공백을 해소한다. 실제 draft Run(attempt 0)에 승인할 제한 입력 bytes를 고정하고, 현재 권한과 별도 승인을 검증하여 한 번만 실행한다. 승인/예약/queue/Node 출력/결과 checkpoint를 연결하며 기존 복구 경로와 구분한다.

scope: 첫 실행 계약·forward migration·kernel API·Go 입력/출력 식별자·동시성/취소/복구 통합 시험 및 인계 문서. 기존 운영 DB/사용자 권한/PKI는 변경하지 않는다. 운영 IdP·일반 프로젝트 CRUD·Frontend는 각각 Claude/Gemini 영역이며 현재 mTLS 관측 전용 다른 PC의 실제 실행 성공을 주장하지 않는다.

합격 증거: 최초 attempt 1의 실제 Python/CPU 학습/결과 파일, 승인 전 거부·원자 queue·중복 요청·권한 상실·실패/취소 자원 회수·출력 publication 재개. 확정 코드 SHA에서 Linux/PostgreSQL/Go/Docker로 검증하고 CI·Obsidian 결과 및 독립 검토 대기를 보고한다.
