---
doc_id: "HIST-OPERATING-CONTRACT-START-20260912"
title: "2026-09-12 OPERATING-CONTRACT Codex 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-12T00:30:42+09:00"
source_of_truth: "Git"
---

# 2026-09-12 OPERATING-CONTRACT Codex 착수

CX-02 / S01-BE·S01-ST·S08-ST / owner Codex / reviewer Claude pending. base f5c43a1040c213e56efb546a2849ccc4317850cd, branch agent/codex/workspace-bridge, PR19.

공통 진행판1.0.18, Codex 작업판1.0.4, GUIDE/GOV-AGENT/GOV-GIT1.1.0, PLAN-STORAGE1.0.0, ADR INDEX1.30.0, agent-delivery1.1.0/core-reliability1.0.0을 따른다.

범위: 기존 identity/workspace/object/adapter 코드와 최초 계획을 대조하여 credential 참조/회수·운영 Storage·IdP/DNS/TLS·5대 장비 입력을 구분한다. 비밀 없는 참조 schema와 구현 인계/미확인 입력 페이지를 만든다. 실제 키 조회·계정 발급·운영 설정 변경·외부 API 호출은 이 계약 작업에 필요하지 않다.

합격: 기존 구현과 새 요구를 구분하고 owner/입력/차단 범위를 명시, schema 유효/거부 사례와 문서/ontology 검사, commit/push/CI/Obsidian 기록. 전체 운영 인수를 선언하지 않는다.
