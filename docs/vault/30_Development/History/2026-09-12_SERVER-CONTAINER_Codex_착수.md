---
doc_id: "HIST-SERVER-CONTAINER-START-20260912"
title: "2026-09-12 SERVER-CONTAINER Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:11:17+09:00"
source_of_truth: "Git"
---

# 후보 컨테이너 실행 검증

CX-02 owner Codex/reviewer Claude pending. base6ff090bc7d486ad1866d5cad37c44ffb190034f7, agent/codex/workspace-bridge. 공통 진행판1.0.52/Codex1.0.31, agent-delivery1.1.0/core-reliability1.0.0.

deploy/Dockerfile.backend 실제 build, UID65532 설정 읽기 및 권한 거부, 별도 PostgreSQL 연결과 실제 HTTP 준비 상태를 확인한다. Workspace 설정의 signing key·mTLS·workingRoot·Node/resource/profile 선행 조건을 확인한다. 시험 자격증명은 합성이며 운영 파일·DB·Node 프로필을 변경하지 않는다. 합격과 실패 기록, 코드/이미지 SHA, CI/Obsidian 및 다음 담당을 남긴다.
