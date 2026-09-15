---
doc_id: "HIST-DB-TEST-ROLE-START-20260912"
title: "2026-09-12 DB-TEST-ROLE Codex 착수"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T20:02:58+09:00"
source_of_truth: "Git"
---

# 공용 그룹 역할의 시험 로그인 재발 방지

CX-01 보안 무결성, owner Codex/reviewer Claude pending. base0c771b5535ac93282676549e062f7cbd337fbc86, agent/codex/workspace-bridge, 진행판1.0.48/Codex1.0.28, agent-delivery1.1.0/core-reliability1.0.0.

테스트가 inv_app 공용 역할의 LOGIN/password를 변경하는 경로를 없애고, 시험마다 난수 credential의 별도 login 역할을 사용·정리한다. 배포 init SQL/compose의 고정 credential을 제거한다. 실제 PostgreSQL RLS/role flag 보존과 cleanup을 검증한다. 이미 있는 운영 inv_app credential 폐기/NOLOGIN은 서비스 의존 확인과 별도 critical 운영 조치로 남긴다. 기존 운영 설정·역할 변경 없음.
