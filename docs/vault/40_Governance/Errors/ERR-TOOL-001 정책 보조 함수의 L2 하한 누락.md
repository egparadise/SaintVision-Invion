---
doc_id: "ERR-TOOL-001"
title: "ERR-TOOL-001 정책 보조 함수의 L2 하한 누락"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-09T23:38:28+09:00"
source_of_truth: "Git"
---

# ERR-TOOL-001 정책 보조 함수의 L2 하한 누락

ToolGateway 연결을 위한 코드 검토에서 기존 policy.enforce_decision이 L2라도 requiredApprovals=1과 approvedBy 1개를 허용할 수 있음을 발견했다. ApprovalStore.request는 기존 0002 구현부터 L2의 2인 조건을 별도로 강제했으므로 durable 승인 경로는 이 입력을 이미 거부한다. 보조 함수만 호출하는 향후 adapter가 약한 요구를 통과시키지 않도록 공통 하한을 보완했다. 해결 [[RES-TOOL-001 L2 하한 강제와 회귀 검증]].
