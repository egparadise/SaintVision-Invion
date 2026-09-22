# Kernel/control-plane 쓰기 계약 감사

## 범위와 판정 기준

- 기준 SHA: `712d9560`; 구현·통합 반영 SHA: `a2dada9a` (integration/all-agents-unified).
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
| 신규 계약 공백 수정 | business lock release | 실제 반환 `{lockId,releasedAt}`를 그대로 `BusinessEditLockReleaseView`로 기록하고 정상·replay 응답에 앵커를 추가했다. 새 필드를 추측하지 않았다. |

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

되돌림 대조: `Control.cancel` parent 응답의 `validate_contract("ControlRunDetail", ...)` 호출을 제거하면 `test_parent_cancel_anchor_rejects_an_invalid_state`가 `DID NOT RAISE`로 실패한다. 즉 시험은 잘못된 응답을 초록으로 통과시키지 않는다.

## 실제 PostgreSQL 확인

일회용 Docker PostgreSQL 16 컨테이너(`ai.saintvision.codex-audit=20260922`)에서 Alembic 초기화 후 다음을 실행했다.

- `test_public_create_cancel_and_replay_are_durable`: **1 passed**, exit 0. 일반 취소와 동일 idempotency key 재생을 실제 DB에서 확인했다.
- `test_concurrent_control_replay_has_one_version_and_immutable_audit`: **1 passed**, exit 0. containment replay의 동시성·단일 버전·감사 행을 확인했다.
- workspace/business replay 시험: Windows 호스트의 Linux 실행 전제 때문에 각각 **skip**. PostgreSQL 부재가 아니라 Linux Workspace 실행 전제이며, 이 경로의 실제 DB 증거는 CI/Linux에서 남아 있다.

컨테이너는 라벨을 확인한 뒤 해당 컨테이너만 제거했고, 보호 컨테이너는 건드리지 않았다.

`check_docs.py`는 이번 변경과 무관한 기존 History 문서의 깨진 wiki 링크 2건(`doc-only-commit-verify-the-code`, `empty-output-is-not-evidence`)으로 exit 1이었다. 이를 이번 계약 변경의 통과로 보고하지 않는다.

남은 범위는 독립 검토와 통합 tip 재실행 전까지 완료로 세지 않는다.
