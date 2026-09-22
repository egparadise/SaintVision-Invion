# Kernel/control-plane 쓰기 계약 감사

## 범위와 판정 기준

- 기준 SHA: `712d9560`에서 시작한 Codex 작업 트리; 이 기록의 구현 후 커밋은 인계 시 갱신한다.
- `services/control-plane/src/inv/app.py`의 `POST`·`PUT`·`PATCH`·`DELETE` 라우트 28개를 전수 목록화했다.
- 프런트는 runs 생성·취소, approval, workspace start/resume·files, terminal ticket, node control을 control-plane에 직접 요청한다. 따라서 이 면은 내부 전용으로 간주할 수 없고, 새 ID·handle·전이 집합·경로를 반환하는 쓰기 응답은 v1 쓰기면과 같은 고위험 기준을 적용한다.
- 확인은 소스 읽기와 기존 계약/앵커 시험 실행으로 했다. 브라우저, 실 HTTP, PostgreSQL 전체 쓰기면 회귀는 이 감사에서 주장하지 않는다.

## 전수 분류

| 분류 | 범위 | 결과 |
|---|---|---|
| canonical contract + serving anchor | run create/cancel, containment, approval, terminal ticket, workspace prepare/enqueue/start, git, editor, business binding | 기존 앵커를 확인했고, replay 분기에서 빠진 검증을 보강했다. |
| 고위험 누락 수정 | `Control.cancel` | shard parent 반환, 일반 취소 결과, idempotency replay 모두 `ControlRunView`를 검증하도록 했다. parent 변형에서 앵커를 제거하면 시험이 실패한다. |
| replay 누락 수정 | containment, workspace API/start, business binding prepare | 저장된 prior 응답도 각각 `ContainmentResult`, `WorkspacePrepareResult`, `WorkspaceEnqueueResult`, `WorkspaceStartPrepareResult`, `WorkspaceStartEnqueueResult`, `BusinessBindingView`로 재검증한다. |
| 신규 계약 공백 수정 | business edit lock | `BusinessEditLockView`를 정본 JSON Schema에서 생성하고 lock 발급·replay에 앵커를 추가했다. lockId가 다음 prepare 요청의 대상이므로 고위험이다. |
| 별도 판단 필요 | business lock release의 `{lockId,releasedAt}`와 일부 운영 응답 | 현재 canonical response schema가 없다. 무명 raw dict를 억지로 기존 계약에 맞추지 않고 별도 계약 카드로 남긴다. |

`tools/check_contract_bindings.py`는 현재 48개 fixture가 시험에서 참조되고 14개 kernel 응답 타입에 serving-anchor 시험이 있음을 보고한다. 이 검사는 앵커 호출의 존재를 보장하지만 모든 write route의 의미적 도달성과 실제 DB 실행을 보장하지 않는다.

## 제품 경로·fixture·수동 타입 감사

- 제품 경로에 닿지 않는 구현(복구/재시도 등)은 기존 결정 대기 범위와 겹치며 이번 쓰기 계약 감사에서 연결하지 않았다.
- kernel fixture는 스키마 적합성은 검사하지만 producer가 실제로 만들 수 있는 상태인지 자동 검증하지 않는다. 이 부류는 별도 결정 대기로 유지한다.
- control-plane 소비를 위한 프런트 수동 타입은 별도 목록화가 필요하다. 이번 변경은 화면을 수정하지 않고 canonical adapter/type 경계에 한정했다.

## 검증

```text
python -m pytest -q tests/core/test_run_approval_observation_contract.py --tb=short
16 passed, exit 0
python tools/check_contract_bindings.py
PASS ... 48 fixtures ... 14 bound kernel responses ...
git diff --check
exit 0
```

되돌림 대조: `Control.cancel` parent 응답의 `validate_contract("ControlRunView", ...)` 호출을 제거하면 `test_parent_cancel_anchor_rejects_an_invalid_state`가 `DID NOT RAISE`로 실패한다. 즉 시험은 잘못된 응답을 초록으로 통과시키지 않는다.

남은 범위는 독립 검토와 통합 tip 재실행 전까지 완료로 세지 않는다.
