---
doc_id: "HISTORY-CARD222-NODE-QUARANTINE-20261002"
title: "Card 222 node-agent durable quarantine channel"
version: "1.2.1"
status: "review"
author: "Codex"
updated: "2026-10-02T12:46:10+09:00"
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

# Claude r1 조치

Claude r1 `issuecomment-5944843555`의 M-1~M-4를 다음처럼 닫았다.

- Node quarantine의 secondary `NODE-0030`이 최초 오류를 덮지 않도록 원인 보존 경계를 넓혔다.
- lease/session/daemon/decision/binding/epoch를 request·receipt와 replay key에 결속했다. epoch 또는
  daemon만 바뀌어도 새 requestId가 생기고, lost acknowledgement만 exact replay한다.
- capability 설정만 믿지 않고 매 dispatch fresh nonce preflight를 수행한다. 런타임 도달 불가도
  adapter 호출 0건인 상태에서 redacted outbox로 durable 표시하되 Node 상태는 바꾸지 않는다.
- post-dispatch 격리는 Node journal과 `inv.nodes.status='quarantined'` 두 marker를 독립 기록한다.
  기존 placement/build admission의 online guard가 후속 배정을 거부한다.
- focused Python 결과는 **239 passed, 1 skipped**였고, 추가 collector/service 재검증은
  **89 passed, 1 skipped**였다. skip 1건은 Windows의 POSIX mode 비지원이다.

hosted Core·Backend exact-head 결과와 Claude r2 판정은 이 조치 commit 이후 기록한다. 제품 caller와
실제 builder Node 인수는 여전히 별도 카드이며 S08-BE 완료를 주장하지 않는다.

# Claude r2 조치

- pre-dispatch probe 실패를 증명된 post-dispatch 위반과 분리했다. 다른 Node pin, 6초 clock skew,
  429 같은 일시 오류는 `RES-0006`으로 그 dispatch만 거부하고
  `inv.build.quarantine_preflight_unavailable` 관측을 남기며 Node는 online을 유지한다.
- post-dispatch 격리 해제는 기존 containment `resume`을 사용한다. person-backed `can_resume` 운영자,
  독립 2인 approval, settled 상태, fresh authenticated Node channel/resource snapshot, recovery epoch가
  모두 맞아야 online으로 복귀한다. actor·reason·approval·response는 `inv.containment_requests`에 남는다.
- Node journal이나 CP fence가 `DomainError` 밖의 driver/check/FK 오류를 내도 최초 `VERIFY-0002`·
  `VERIFY-0022`·`LEASE-0002`를 유지하고 redacted structured log만 남긴다.
- ±5초 freshness 경계를 각각 6초 stale/future fixture로 고정해 검사 제거 변이를 사살했다.

focused collector/service는 **92 passed, 1 skipped**다. quarantine resume의 실 PostgreSQL 경로는
exact-head Backend에서 실행하며, Core의 Linux journal과 함께 green 확인 전 승인·완료를 주장하지 않는다.

# Claude r3 잔여 판단

격리는 build/GPU별 부분 상태가 아니라 Node 단위 scheduling fence로 유지한다. scope마다 Node를 online으로
만드는 것은 단일 `inv.nodes.status` 모델과 모순되고 다른 scope의 위험을 조용히 해제하므로 허용하지 않는다.
대신 어느 scope든 active lease·delivery·run이 남아 있으면 resume를 `LEASE-0003`으로 거부한다. quarantine
전용 실 PG 회귀는 active lease 상태의 해제 거부와 trusted Node stop receipt에 의한 release를 확인한 뒤,
fresh observation과 2인 승인으로만 복귀함을 고정한다. resume 자체를 cleanup 영수증으로 부르지는 않는다.
