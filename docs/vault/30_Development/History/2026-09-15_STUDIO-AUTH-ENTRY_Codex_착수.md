---
doc_id: "HIST-STUDIO-AUTH-ENTRY-START-20260915"
title: "2026-09-15 STUDIO-AUTH-ENTRY Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T00:45:00+09:00"
source_of_truth: "Git"
---

# Studio 인증과 프로젝트 진입 연결

CX-01 후속. Owner Codex, reviewer Claude 대기, Gemini 화면 인수 대기. agent-delivery 1.1.0/core-reliability 1.0.0 적용. 코드 base e0b4b4f50d64bd7bf44da18a881809c2460db8e3, agent/codex/approval-browser. 문서 정본은 workspace-bridge, base 74d1702. 공통 진행판과 역할 작업판을 확인했다.

전체 App이 아닌 승인 component만 검증된 상태에서 이어 간다. Gemini 578db00을 읽어 외부 token URL 추가를 확인했으나 JSON token 교환, 임의 auth_code fallback, JWT payload 사용자와 커널 subject의 불일치가 남아 있다. 중복 로그인 정본을 만들지 않고 기존 Login에 표준 form 교환과 서버 검증 사용자 연결을 적용한다. 커널 단독 projects(items)와 business projects(projects) 계약을 명시 구별한다. 기존 pilot 화면을 보존하면서 /studio 진입을 연결한다.

합격 증거: 합성 인증 제공자의 실제 redirect/PKCE/token 교환, configured server의 JWT 검증, 격리 PostgreSQL 권한 목록, 실제 Edge의 로그인→프로젝트→승인→로그아웃. 운영 IdP/원격 Node 인수와 구분한다. 실패·결과·commit/push/CI·동기화는 후속 보고한다.
