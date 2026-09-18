---
doc_id: "HIST-CONFIGURED-SERVER-START-20260912"
title: "2026-09-12 CONFIGURED-SERVER Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T22:03:34+09:00"
source_of_truth: "Git"
---

# 정본 서버 설정과 실제 HTTP 검증

CX-02 owner Codex/reviewer Claude pending. base 6c3b020ef6feef52d0ff978aea24ffd7ee5271cb, branch agent/codex/workspace-bridge. GUIDE-001 1.1.0, INDEX-PROGRESS-001 1.0.50, Codex 작업판 1.0.30, agent-delivery 1.1.0/core-reliability 1.0.0.

목표: Compose의 정본 factory 설정·준비 경로를 연결하고 별도 PostgreSQL 및 실제 loopback HTTP에서 명시적 인증/DB/epoch 경계를 확인한다. 합격 증거: 필수 설정 누락 거부, 실제 로그인 역할로 프로젝트 권한 조회, 잘못된 토큰 거부, stale epoch/만료 trust의 준비 상태 실패. 시험 issuer는 합성 fixture이며 운영 SSO 인수로 간주하지 않는다. 운영 DB migration·Node profile·kill switch는 변경하지 않는다. 기존 서비스는 유지한다.
