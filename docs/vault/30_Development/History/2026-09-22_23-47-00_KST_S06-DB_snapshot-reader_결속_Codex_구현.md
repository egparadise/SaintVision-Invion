---
doc_id: "HISTORY-2026-09-22-S06-DB-SNAPSHOT-READER-BINDING-CODEX-001"
title: "S06-DB snapshot reader 제품 결속"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T00:16:00+09:00"
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

착지 SHA의 hosted run은 Backend `35742655421`, Core `35742655096`, Documentation `35742655197`, Frontend `35742655364`, Desktop/Browser `35742655235`로 생성됐다. 최초 보고 시점에는 진행 중/대기여서 통과로 세지 않았고, 아래 후속에서 Core 완주 결과만 별도로 보강했다.

## hosted Linux·독립 검토 후속

Core [run 35742655096](https://github.com/egparadise/SaintVision-Invion/actions/runs/35742655096)는 exact head `a4bf2cee3c4e396b0884aba7890aa3855e8d5aa8`에서 **success**로 완주했다. `saintvision-core-evidence`의 `core-tests.xml`(SHA-256 `965a98c8776ac7dd70b6ae7956493d2a600cee1b1ef15d02414ae4230df98bbf`)을 직접 집계한 결과는 전체 3,134 tests / 35 declared platform skips / 0 failure·error다.

- `tests.integration.test_workspace_recovery`: **12/12 passed, 0 skipped/failed**.
- `tests.integration.test_workspace_resume`: **11/11 passed, 0 skipped/failed**.
- 합계 **23/23 Linux scoped-handle·bounded Workspace case가 실행**됐다. 개발 PC Windows의 23 skip은 `Linux scoped handles` 12건 + `Linux bounded Workspace execution` 11건이었으며, hosted Linux에서는 두 사유가 0 skip이다. 별도 `workspace-tests.xml`도 resume 11건을 다시 11/11 통과했다.

Claude 독립 검토 PR #76은 승인이고, replay 권한 재검사를 제거한 되살림이 회수 후 201을 만들어 KILLED됐다. 이 보강은 review 관찰 O1을 해소하지만 물리 원격 WS/PTY/Git·Control Plane/Node 재시작 복원 여정을 대신하지 않는다. 따라서 S06-DB는 `review`와 AC-06 차단을 유지한다.

## 다음 행동

Claude 독립 검토와 hosted Linux 보강은 완료됐다. 작성자는 S06-DB를 self-close하지 않으며, 물리 원격 WS/PTY/Git 및 CP/Node 재시작 복원 여정은 [[Codex 5노드 랩 opt-in lane 정의]]에 따라 별도 랩 담당이 측정한다.
