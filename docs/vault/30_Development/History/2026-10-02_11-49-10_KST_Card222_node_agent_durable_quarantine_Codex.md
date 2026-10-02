---
doc_id: "HISTORY-CARD222-NODE-QUARANTINE-20261002"
title: "Card 222 node-agent durable quarantine channel"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T11:49:10+09:00"
source_of_truth: "Git"
base_sha: "63ef20c4df9455eaae05758ff18d00ad46e5ff0f"
reviewer: "Claude"
---

# 선택 근거

train 17 후보의 `#312`는 BuildExecutionService가 durable quarantine capability 없이는 dispatch를
시작하지 않도록 fail closed했다. `NodeAgentReceipts.quarantine_node()`가 기록 없이
`VERIFY-0022`만 발생시키는 공백은 외부 장비 없이 코드·hosted Linux로 닫을 수 있는 Codex 소유
후속이므로 Card 222를 선택했다.

# 변경

- strict request/receipt 계약과 Python·TypeScript·Go 생성물을 추가했다.
- node-agent에 인증된 `POST /v1/builds/quarantine`과 fsync+atomic rename journal을 추가했다.
- exact request replay만 허용하고 conflicting replay, tenant/Node/epoch 불일치를 거부한다.
- 기존 NodeTLSClient를 재사용한다. collector capability는 mTLS client와 pinned channel proof가 모두
  있을 때만 true다.
- response exact binding과 writer/durable authority를 control-plane에서 다시 검증한다.

# 현재 검증

- `go test ./runtime ./transport`: exit 0. Windows에서는 Linux journal test가 build tag로 제외되고
  transport package는 실제 mTLS route를 실행했다.
- focused Python contract/collector/service: **200 passed, 1 skipped**, exit 0. lost acknowledgement 뒤
  재호출이 같은 requestId/requestedAt을 재사용하는 단독 회귀를 포함한다.
- `tools/check_contract_bindings.py`: exit 0.
- Python 3.10에서 `tests/core/test_node_tls.py`는 제품 최소 버전보다 낮아 `StrEnum` import에서 수집
  중단했다. 로컬 Python 3.14에는 pytest가 없어 재실행하지 않았고, 이 파일과 Linux journal 시험은
  exact-head hosted Core로 판정한다.

# 판정과 잔여

코드 경계는 구현됐지만 hosted Core, 독립 Claude 검토, 실제 제품 caller 주입은 아직 남아 있다.
receipt는 reconciliation 의무의 durable 기록일 뿐 복구 완료 증거가 아니며, S08-BE 완료·점수 승격과
물리 builder 인수를 주장하지 않는다. 설계는 [[S08-BE_node-agent_durable_quarantine_channel]].
