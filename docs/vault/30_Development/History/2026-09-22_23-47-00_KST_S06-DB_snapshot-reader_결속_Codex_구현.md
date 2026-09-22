---
doc_id: "HISTORY-2026-09-22-S06-DB-SNAPSHOT-READER-BINDING-CODEX-001"
title: "S06-DB snapshot reader 제품 결속"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T23:47:00+09:00"
source_of_truth: "Git"
---

# S06-DB snapshot reader 제품 결속

## 범위와 착지

- TaskCard: S06-DB `snapshot reader ↔ 커널 결속`, owner Codex, reviewer Claude.
- 기준선은 카드 5 후속 `5f123331`이며 R1 착지 부모는 최신 integration `f28e4c819c23af40f66252a2400652481243de4f`다.
- 구현 SHA `a4bf2cee3c4e396b0884aba7890aa3855e8d5aa8`을 origin `integration/all-agents-unified`에 non-force fast-forward 착지했다.
- 기존 resume·commitment API는 바꾸지 않았다. 원격 WS/PTY 상태, 실제 Git 프로세스, Control Plane/Node 재시작 뒤 복원 한 여정은 **미측정**이며 AC-06을 닫지 않는다.

## 계약 우선과 제품 경계

`WorkspaceRestoreInput/View`와 `WorkspaceCheckoutInput/View` strict JSON Schema를 먼저 추가하고 Python·TypeScript·Go와 node-agent embedded schema를 생성했다. 두 canonical fixture는 contract test에 연결했다. project/run-scoped restore route는 checkpoint object의 실제 bytes를 읽어 immutable generation을 만들고, checkout route만 별도 writable generation을 만든다. fresh와 replay 응답 모두 schema anchor를 지나며 `check_contract_bindings` replay guard inventory가 각 branch를 고정한다.

운영 workspace 설정에 `snapshotObjectRoot`와 `restoreRoot`를 함께 주입하면 `LocalObjects → SnapshotStore → WorkspaceRecovery`가 실제 조립된다. 한쪽만 있으면 설정을 거부하고 둘 다 없으면 readiness의 `workspaceRecovery=not_configured` 및 route 503으로 드러낸다. receipt는 immutable snapshot identity라 freshness timestamp 대상이 아니라는 판단을 [[Codex Workspace 공개 API와 실행 커널 통합 계약]]의 S06 절에 기록했다.

## 실 PostgreSQL 권한·reader 시험

`.env`의 `INV_TEST_ADMIN_DSN`으로 disposable DB와 난수 `inv_app` login role을 만들고 `tests/integration/test_workspace_recovery_http.py` 한 파일을 실행했다. 결과는 **1 passed, 0 failed, 0 skipped, exit 0**다.

- fresh restore와 replay restore가 실제 object reader의 digest/size 검증을 통과했고 writable checkout도 strict receipt를 반환했다.
- replay 전에 grant를 폐기하자 저장 응답을 재사용하지 않고 `AUTH-0030/403` ProblemDetails를 반환했다.
- 타 project와 타 tenant의 같은 run 요청은 기존 존재 노출 정책대로 404 ProblemDetails였다.
- 난수 `inv_app` login의 `inv.workspace_restores` 직접 SELECT는 `InsufficientPrivilege`, tenant GUC 없는 `inv_kernel` login은 `workspace_restores`와 `checkpoint_objects` 모두 0행이었다. role과 disposable DB는 fixture가 정리했다.

## 검증

| 검사 | 결과 |
|---|---|
| contract/anchor/route/API + 기존 recovery/resume 관련 | 56 passed, 23 Windows의 Linux scoped-handle skip, 0 failed |
| 별도 실 PG HTTP 단일 파일 | 1 passed, 0 skipped/failed |
| `generate_contracts.py` 재실행 | Python/TS/Go/node schema drift 0 |
| contracts-go `go test ./...` | exit 0 |
| `check_contract_bindings.py` | 54 fixtures / 19 types / 25 sites / 14 replay guards, exit 0 |
| `test_route_coverage.py` | 관련 suite 포함 exit 0 |
| `check_response_freshness.py` | advisory 10/10, exit 0 |
| docs/frontend/ontology/single-source ratchet | 모두 exit 0 |

착지 SHA의 hosted run은 Backend `35742655421`, Core `35742655096`, Documentation `35742655197`, Frontend `35742655364`, Desktop/Browser `35742655235`로 생성됐다. 보고 작성 시점에는 진행 중/대기이므로 통과로 세지 않는다.

## 다음 행동

Claude가 구현 SHA의 transaction lock/auth 순서, replay guard 실제 무게, Linux scoped-handle hosted 결과와 운영 설정 결속을 독립 검토한다. 작성자는 S06-DB를 self-close하지 않으며, 물리 원격 WS/PTY/Git 및 CP/Node 재시작 복원 여정은 별도 랩 담당이 측정한다.
