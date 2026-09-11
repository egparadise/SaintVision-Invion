---
doc_id: "HIST-KERNEL-LIVE-INIT-20260911"
title: "KERNEL-LIVE Codex 실제 실행 연결 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T09:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["development", "kernel", "workspace"]
---

# KERNEL-LIVE 실제 실행 연결

- Task KERNEL-LIVE / S03-BE·S06-BE·S12-BE 후속 / owner Codex / reviewer Claude 대기.
- Base SHA `32367cd7fe7847c654a2bec0513cfdc58cb72b6f`, 기존 독립 checkout과 `agent/codex/dev-environment` 브랜치 사용.
- 기준 GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001/task-registry 1.0.0, ADR-INDEX-001 1.20.0, agent-delivery/core-reliability 1.0.0. 사용자 후속 진행 승인 계승.

09:51 KST 실제 worker는 fresh mTLS online이지만 아직 `lan-observe-v1`이다. 해당 PC에 원격 관리 셸이 없어 설치 완료 전 원격 실행은 하지 않는다. 독립적으로 서버에 재현 가능한 Linux 제어 커널/DB/Node 통합 검증 환경을 준비한다. 임의 사용자/승인자를 실제 운영 DB에 등록하지 않는다.

범위: 고정 Python/Node supervisor 실행 이미지, 일회용 PostgreSQL·내부 Docker 네트워크·소스 사본을 쓰는 제한 통합 시험 도구, 실제 승인→lease→mTLS→Python 프로젝트 작업→출력/Evidence/Workspace checkpoint 연결. 기존 실행 전 취소·등록 실패 회수·복구 계약을 검증하고 발견한 결함을 수정한다. 시험 identity/PKI는 합성 fixture로 명시하며 운영 인증 연동 완료를 뜻하지 않는다.

합격 증거: 고정 코드/이미지 SHA, 개별 pytest 결과와 skip/failure 수, 실제 CPU 작업/파일 결과/Run 상태 및 물리 종료/예약 회수, 소스 변경·승인 변경·실패·취소·Node 재시작/Workspace 재개 경계. 실장비 두 PC·GPU·UI 전체 완료와 구별하여 Git/CI/Obsidian에 보고한다.
