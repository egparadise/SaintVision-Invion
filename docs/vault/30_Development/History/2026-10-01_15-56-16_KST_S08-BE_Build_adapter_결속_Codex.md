---
doc_id: "HISTORY-S08-BE-BUILD-ADAPTER-20261001"
title: "S08-BE Build adapter 결속"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T16:18:16+09:00"
source_of_truth: "Git"
---

# S08-BE Build adapter 결속

## 선택 근거와 시작 기준

- Card 174, owner Codex, reviewer Claude, branch
  `agent/codex/s08-be-build-adapter`, base
  `7eb5e77e006ff952acb0eb114fb36440c6957087`이다.
- base는 PR #272의 승인 head다. exact-head Core run `36824220238`과 Backend run
  `36824220278`은 모두 success이며, #272 최종 확인 코멘트는
  `issuecomment-5926263570`이다.
- 승인된 PR #265의 `S08-BE ROOF·BuildKit·단일 GPU 구현 설계` v1.1.0의 구현 순서와
  #272 Claude r2 조건에 따라, **admitted binding 없이는 transport dispatch가 불가능한
  내부 adapter 경계**를 다음 코드 카드로 선택했다.
- 공개 route, 실제 rootless BuildKit daemon/socket, registry credential·push, GPU provider,
  migration은 이 카드 범위가 아니다.

## 구현한 경계

- transport가 raw `BuildPlan`을 직접 받지 않고, 첫 번째 짧은 DB transaction에서 ROOF
  승인과 live Run/Node/Resource/lease를 확인한 뒤 만들어진 내부 `_AdmittedBuild`만 받는다.
- capability digest는 ROOF binding뿐 아니라 run, 잠근 leased resource Node,
  lease ID, resource ID와 full fencing token을 함께 묶는다. final transaction의 Node가
  달라지면 dispatch 결과를 받아들이지 않고 cancel+quarantine한다.
- 첫 transaction은 `decisionId + runId + leaseId` identity를 `inv.idempotency`의
  `build.dispatch` claim으로 원자 소비한다. 동일 payload 재생도 `IDEM-0001`이며, claim
  commit 뒤 process crash는 자동 재실행하지 않고 운영자 reconciliation을 요구한다.
- Run은 `scheduled`·`running`·`verifying`만 허용한다. cancelled·failed·succeeded·recovering
  등 비실행 상태는 live lease가 남아 있어도 dispatch 전에 `RES-0005`로 거부한다.
- 외부 builder 관측·dispatch·cancel은 business transaction 밖에서만 수행한다.
- 완료 뒤 새 transaction에서 live lease/fencing, Node online·freshness·clock skew,
  project 권한·kill switch·정책·provider binding을 반복 검증한다.
- dispatch가 호출된 뒤 오류 또는 final drift가 생기면 cancel+quarantine을 요구하며,
  이 정리와 `inv.build.dispatch_quarantined` outbox audit 중 하나라도 확인되지 않으면
  `VERIFY-0022`로 실패한다. claim도 `inv.build.dispatch_claimed`로 redacted 기록한다.

## 비주장 경계

- 이 adapter가 반환하는 `EvidenceEnvelope`는 아직 DB에 저장하지 않는다. kernel lease를
  해제하려면 인증된 물리 cleanup receipt와 원자 저장 경계가 먼저 필요하므로, 이를
  합성하지 않는다.
- 실제 daemon 격리·socket 부재·seccomp/LSM/cgroup read-back·network/secret/cache·실제
  물리 cancel과 lease release는 계속 `NOT_OBSERVED`다.
- 현재 provider observation은 builder process가 어느 Node에 있는지, builder service 자체가
  draining/healthy인지 측정하지 않는다. 이 카드는 **leased resource Node**만 검증하며,
  measured provider↔Node binding 전에는 concrete transport와 공개 route 연결을 금지한다.
- private adapter의 pre-admission 거부는 persisted `EvidenceEnvelope`를 만들지 않는다.
  인증 주체와 거부 사유를 정본화하는 공개 route 카드가 denial Evidence를 구현하기 전에는
  이 adapter를 제품 route에 연결하지 않는다. claimed dispatch와 quarantine audit만 이번
  카드의 durable 기록이다.
- S08-BE registry 상태·점수와 물리 인수 판정은 변경하지 않는다.

## 검증 기록

| KST | 명령 | 결과 |
|---|---|---|
| 2026-10-01 15:55 | `python -m pytest tests/core/test_build_adapter.py -q` | exit 0, 12 passed |
| 2026-10-01 15:57 | `python -m pytest tests/core/test_build_adapter.py tests/core/test_build_governance.py tests/core/test_buildkit_contracts.py -q` | exit 0, 115 passed |
| 2026-10-01 15:58 | `python -m black --check services/control-plane/src/inv/build_adapter.py tests/core/test_build_adapter.py` | exit 0 |
| 2026-10-01 15:58 | `python tools/check_docs.py` | exit 0 |
| 2026-10-01 15:58 | `python tools/check_contract_bindings.py` | exit 0 |
| 2026-10-01 15:58 | `python tools/check_doc_path_citations.py --ratchet --base-ref agent/codex/s08-be-roof-binding` | exit 0, 새 결함 0 |
| 2026-10-01 15:58 | `git diff --check` | exit 0 |
| 2026-10-01 16:04 | Node identity를 포함한 dispatch binding 보강 뒤 focused 3파일 재실행 | exit 0, 116 passed |
| 2026-10-01 16:09 | 실제 helper SQL 순서와 live authority 부정 행렬 보강 뒤 focused 3파일 재실행 | exit 0, 124 passed |
| 2026-10-01 16:18 | Claude 검토 H1·M1~M3·L1~L3 조치 뒤 `test_build_adapter.py` | exit 0, 37 passed |
| 2026-10-01 16:18 | 조치 뒤 focused 3파일 재실행 | exit 0, 140 passed |

실제 `lock_run`·`lock_resources` helper를 통과하는 시험은 Run → Node → Resource → lease
`FOR UPDATE` 순서를 고정한다. tenant/project/released/expiry/recovery epoch/fence와 plan expiry,
Node status/epoch/heartbeat 미래·stale/clock skew를 각각 바꾸는 부정 시험은 모두 dispatch 전
거부를 고정한다. expiry와 plan expiry를 함께 만료시키는 시험, Node epoch 단독 drift,
NULL skew, terminal Run, 동일·상이 digest claim 재생, `KeyboardInterrupt`·`CancelledError`,
quarantine audit 실패도 각각 fail-closed 결과를 고정한다.

PR #274의 Claude 변경 요청을 위 경계로 조치했다. 새 exact-head hosted CI 전에는 실제
daemon 실행이나 제품 인수를 주장하지 않는다.
