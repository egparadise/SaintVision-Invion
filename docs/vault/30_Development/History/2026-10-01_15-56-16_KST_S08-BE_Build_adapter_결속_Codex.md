---
doc_id: "HISTORY-S08-BE-BUILD-ADAPTER-20261001"
title: "S08-BE Build adapter 결속"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T16:04:35+09:00"
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

## 구현 중인 경계

- transport가 raw `BuildPlan`을 직접 받지 않고, 첫 번째 짧은 DB transaction에서 ROOF
  승인과 live Run/Node/Resource/lease를 확인한 뒤 만들어진 내부 `_AdmittedBuild`만 받는다.
- capability digest는 ROOF binding뿐 아니라 run, leased resource에서 잠근 builder Node,
  lease ID, resource ID와 full fencing token을 함께 묶는다. final transaction의 Node가
  달라지면 dispatch 결과를 받아들이지 않고 cancel+quarantine한다.
- 외부 builder 관측·dispatch·cancel은 business transaction 밖에서만 수행한다.
- 완료 뒤 새 transaction에서 live lease/fencing, Node online·freshness·clock skew,
  project 권한·kill switch·정책·provider binding을 반복 검증한다.
- dispatch가 호출된 뒤 오류 또는 final drift가 생기면 cancel+quarantine을 요구하며,
  이 정리가 확인되지 않으면 `VERIFY-0022`로 실패한다.

## 비주장 경계

- 이 adapter가 반환하는 `EvidenceEnvelope`는 아직 DB에 저장하지 않는다. kernel lease를
  해제하려면 인증된 물리 cleanup receipt와 원자 저장 경계가 먼저 필요하므로, 이를
  합성하지 않는다.
- 실제 daemon 격리·socket 부재·seccomp/LSM/cgroup read-back·network/secret/cache·실제
  cancel과 lease release는 계속 `NOT_OBSERVED`다.
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

stacked PR을 열고 Claude에게 독립 검토를 요청한다. exact-head hosted CI 전에는 실제
daemon 실행이나 제품 인수를 주장하지 않는다.
