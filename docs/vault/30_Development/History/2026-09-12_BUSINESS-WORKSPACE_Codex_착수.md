---
doc_id: "HIST-BUSINESS-WORKSPACE-START-20260912"
title: "2026-09-12 BUSINESS-WORKSPACE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:18:42+09:00"
source_of_truth: "Git"
---

# 업무 서비스와 영속 Workspace

CX-02 Codex owner/Claude reviewer pending. base8e4c856ce555ee58ef7672b940dec77e62383814, agent/codex/workspace-bridge. 진행판1.0.53/Codex1.0.32, agent-delivery1.1.0/core-reliability1.0.0.

배포 INV_DATABASE_URL과 실제 factory INV_BUSINESS_DSN 불일치를 수정한다. 합격 증거: 실제 후보 컨테이너/비소유자 분리 role/동일 synthetic JWT로 업무 프로젝트·Workspace 생성과 권한 경계 확인, 개인 영속 volume의 파일을 재시작 후 보존. 작업 파일 보존과 실제 Step/Node 복구 인수는 구분한다. 기존 운영·Node·인증 자료를 변경하지 않는다.
