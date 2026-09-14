---
doc_id: "HIST-APPROVAL-BROWSER-INTEGRATION-START-20260915"
title: "2026-09-15 APPROVAL-BROWSER-INTEGRATION Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:17:06+09:00"
source_of_truth: "Git"
---

# 승인 화면·커널 격리 브라우저 통합

CX-01 후속, owner Codex/reviewer Claude 대기·Gemini UI/접근성 인수 대기. agent-delivery1.1.0/core-reliability1.0.0. 작업 초기 읽기와 환경 준비 후 이 착수 기록을 보완한다. base f011db3, 별도 worktree/branch agent/codex/approval-browser. 서버024a817 포함 base에 frontend ab8b645의 apps/web을 반영하고 기존 LiveApp/liveData/시험은 보존한다. 공유 최신efd61a7에는 손대지 않는다. 문서 정본 workspace-bridge.

기존 이름상 browser smoke는 HTTP 호출 스크립트라 실제 페이지 조작 증거가 아니다. production ApprovalCenter/API helper를 test-only Vite entry에 mount하고 configured factory+isolated PG+headless Edge에서2인승인·중복거부·취소후거부를 확인한다. JWT는 합성이고 App 로그인/운영 IdP/원격Node 검증은 아니다. 시험Origin만명시허용. code→검증→commit/push→CI→report/sync 순서.
