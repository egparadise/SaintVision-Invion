---
doc_id: "RES-TOOL-001"
title: "RES-TOOL-001 L2 하한 강제와 회귀 검증"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T23:38:28+09:00"
source_of_truth: "Git"
---

# RES-TOOL-001 L2 하한 강제와 회귀 검증

[[ERR-TOOL-001 정책 보조 함수의 L2 하한 누락]] 대응: risk=L2이면 requiredApprovals!=2를 AUTH-0014로 거부한다. 순수 함수 회귀 test_legacy_policy_boundary_also_requires_two_people_for_L2와 실제 ToolGateway one-person-L2 거부 시험을 추가했다. 로컬 pytest exit 0, 89 passed/83 PostgreSQL skipped. 실제 DB 및 전체 회귀 결과는 검증 보고에 기록한다.
