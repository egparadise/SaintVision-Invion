---
doc_id: "HIST-DB-ROLE-REVOKE-START-20260912"
title: "2026-09-12 DB-ROLE-REVOKE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:47:45+09:00"
source_of_truth: "Git"
---

# 승인된 운영 공용 로그인 폐기

CX-01 Codex owner/Claude reviewer pending. basea716699da74c0ee79b7239570695d6f42e958ab8, agent/codex/workspace-bridge. 진행판1.0.49/Codex1.0.29, agent-delivery1.1.0/core-reliability1.0.0.

사용자가 직전 운영 inv_app NOLOGIN/password 제거 적용 질문에 “이어서 해”라고 답해 해당 조치를 승인한 것으로 확인했다. 검증된 deploy/remediate-shared-app-role.sql만 실행한다. 현재 직접 세션0, 알려진 pytest/migration 시험 프로세스 없음, 관측 서비스는 inv_lan_runtime/inv_kernel 구성원임을 확인했다. 사전·사후 역할/권한 비교, 기존 credential 거부, runtime/Node 관측 검증을 기록한다. schema migration/kill switch/Node 실행 프로필은 변경하지 않는다. 노출 비밀번호 자동 복원은 하지 않는다.
