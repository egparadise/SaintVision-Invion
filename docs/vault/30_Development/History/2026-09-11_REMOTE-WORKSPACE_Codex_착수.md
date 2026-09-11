---
doc_id: "HIST-REMOTE-WORKSPACE-START-20260911"
title: "REMOTE-WORKSPACE Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T11:09:00+09:00"
source_of_truth: "Git"
---

# 원격 Node 실행 프로필 배포 착수

사용자가 새 Node 실행 프로필 배포 및 실제 원격 PC 실행·취소·복구 검증을 명시적으로 지시했다. owner Codex / reviewer Claude 대기, task REMOTE-WORKSPACE(S03-BE/S06-BE/S07-BE/S12-BE), base `9c3a3760f27205ec82e2800c4b681180a0381851`, 브랜치 `agent/codex/dev-environment`. 기존 작업 checkout을 이어 사용한다.

입력은 GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND-001 및 agent-delivery/core-reliability v1.0.0, ADR-INDEX-001 v1.21.0/ADR-063, CONTRACT-WORKSPACE-START-001 v1.0.0, task registry의 배정·선행 조건이다. Prompt는 이번 사용자 지시, Context는 위 고정 문서·base SHA, Harness는 추적 코드와 실제 명령·결과로 기록한다. 시험 identity와 실제 운영 계정, 장비 검증과 전체 업무 인수를 구분한다.

목표는 기존 Node 인증서·개인키·identity·epoch·volume·journal을 보존하면서 새 initialized/startId를 지원하는 고정 이미지를 배포하고 실제 파일 실행·물리 취소·기존 receipt 복구를 입증하는 것이다. 합격 증거는 이미지/설치본 SHA, fresh mTLS Node 관측, 실제 command/receipt/출력 hash, 종료와 중복 실행 없음, 배포 실패 rollback이다. 공개 설치본에 개인키를 넣지 않는다.

11:07 KST 실측에서 192.168.45.225 Node는 online/fresh, lan-observe-v1, 운영 제출 비활성이다. 해당 PC의 SSH 22·WinRM 5985/5986 접속이 모두 불가하여 직접 원격 설치 경로는 없다. 서버에서 검증한 설치본을 준비한 후 worker에서 한 번 실행해야 한다. 이 설치 대기 조건을 실제 배포 완료로 기록하지 않는다. 테스트만을 위해 운영 로그인·승인자를 생성하거나 사용자 작업의 실행 gate를 열지 않는다.
