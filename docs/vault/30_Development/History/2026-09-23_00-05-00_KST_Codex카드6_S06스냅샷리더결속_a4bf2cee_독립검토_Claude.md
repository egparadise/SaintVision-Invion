---
doc_id: "CLAUDE-REVIEW-CODEX-CARD6-S06-SNAPSHOT-READER-A4BF2CEE-001"
title: "Codex 카드 6 착지 a4bf2cee(+보고 325a669b, S06-DB snapshot reader ↔ 커널 결속) 독립 검토 — 판정: 승인(관찰 3, 비차단) — 계약 앵커·replay guard·403/404·inv_app 차단 실 PG 실측, 되살림(grant 재검사 제거 → 회수 replay 201) KILLED"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T00:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "325a669b"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["independent-review", "codex", "S06", "workspace", "snapshot", "recovery", "replay-guard", "claude"]
---

# Codex 카드 6 `a4bf2cee`(구현) + `325a669b`(보고) 독립 검토 (2026-09-23, 00:05 KST)

대상: `inv/app.py`(+53: `POST …/restores/{restore_id}`·`…/checkouts/{checkout_id}`, `WorkspaceRecoveryService` 조립, readyz `workspaceRecovery`) · `inv/workspace_recovery.py`(+198: `restore_view`/`checkout_view` 앵커, replay guard, `_authorize`) · `workspace_config.py` · 계약 `core.schema.json`(+137, `WorkspaceRestoreInput/View`·`WorkspaceCheckoutInput/View`) + fixture 2 + TS/Go/생성 Python · 시험 3파일 · `tools/check_contract_bindings.py`(SERVING_MODULES + REPLAY_GUARD_COUNTS 등록) · [[2026-09-22_23-47-00_KST_S06-DB_snapshot-reader_결속_Codex_구현]]. 측정 트리 `D:\Project\sv-measure-claude`를 **`a4bf2cee`에 고정**(porcelain 0), 실 PG 단일 파일 1회(시작 전 `codex-worker-status.md`에 통보, 겹침 없음).

## 1. 판정: **승인** (관찰 3, 비차단)

| # | 관찰 | 성격 |
|---|---|---|
| O1 | hosted run(Backend 35742655421·Core 35742655096 등, 보고 SHA `325a669b`)은 보고 시점 진행 중이라 통과로 세지 않음 — 본 검토도 hosted 결과를 인용하지 않는다. Linux scoped-handle 케이스 23건은 Windows에서 skip(정직)이라 **hosted Core가 첫 관측 자리** | 정보 |
| O2 | 원격 WS/PTY 상태·실제 Git 프로세스·CP/Node 재시작 뒤 복원 여정은 보고서 19행에 **"미측정이며 AC-06을 닫지 않는다"** 로 명시(d 항목 충족). 계약 문서 77행도 PTY·remote Git을 범위 밖으로 둔다 | 정직 ✔ |
| O3 | replay guard는 `authorize(conn)` → ledger 조회 → prior 반환 순서라 회수된 grant로는 replay도 403(되살림으로 확인). 다만 replay 응답의 `replayed: true`는 계약 필드로 노출되는데 화면(Gemini) 소비 여부는 이 카드 밖 | 정보 |

## 2. (a) 계약 앵커·fixture·replay guard·미러 동기

- `validate_contract("WorkspaceRestoreView", …)`·`("WorkspaceCheckoutView", …)`가 `restore_view`/`checkout_view` 빌더에서 **응답 직전** 호출되고, replay 경로는 `if prior is not None: validate_contract(...)`로 저장값도 재검증(REPLAY_GUARD_COUNTS에 `workspace_recovery.py: {WorkspaceRestoreView:1, WorkspaceCheckoutView:1}` 등록 → 12→**14 replay guards**).
- `check_contract_bindings` **PASS 54 fixtures / 19 bound kernel response TYPES**(17→19) exit 0. `export_schemas --check` **58/58** exit 0. 스키마 미러 3곳(`contracts/v1alpha1`·`inv/generated`·`node-agent/internal/wire`) **바이트 동일**(cmp). `packages/contracts-go` `go build ./... && go vet ./...` exit 0, `services/node-agent` build exit 0(go1.27.0).

## 3. (b) 동작 실측 — 실 PG 단일 파일 1회

`tests/integration/test_workspace_recovery_http.py` **1 passed, 0 failed, 12s**(disposable DB, TestClient + `create_app(..., workspace=…)`, 실제 `SnapshotStore`·`WorkspaceRecovery`). 한 시험이 아래를 한 번에 단언한다(정독):
- restore **fresh 201** → 계약 검증 · 같은 body **replay 201 + `replayed: true`** · checkout **201** + `WorkspaceCheckoutView` 검증(strict, `expectedVersion`).
- 타 project(`other_project`) → **404**, 타 tenant principal → **404**, 둘 다 `ProblemDetails` 검증(존재 누출 없음: `lock_run` 정책으로 project/run 범위를 먼저 확인).
- grant `enabled=false` 뒤 같은 key replay → **403** ProblemDetails(회수 replay).
- `inv_app`로 GRANT된 login role이 `inv.workspace_restores`를 직접 SELECT → **InsufficientPrivilege**; runtime role이 tenant GUC 없이 count → **0행**(RLS).

## 4. (c) 게이트 (a4bf2cee 정확 트리)

`check_docs` **828** exit 0 · `check_contract_bindings` 54/19 exit 0 · `export_schemas --check` exit 0 · `check_response_freshness` exit 0(advisory) · `check_doc_single_source --ratchet` exit 0 · `check_ontology` exit 0 · PG-free `tests/test_route_coverage.py` + `core/test_workspace_recovery_contract.py` + `core/test_serving_anchors.py` **52 passed**(새 라우트 2개가 route_coverage에 등록됨).

## 5. 되살림

`WorkspaceRecoveryService._authorize`의 `control.grant(conn, principal, project, "can_request")`를 no-op으로 → 같은 파일 재실행 **1 failed**: `assert 201 == 403`(회수 replay가 201로 통과) — 권한 재검사가 replay 경로에서 실제 무게를 가진다(KILLED). `git checkout --`로 복원, porcelain 0.

## 6. 요청(비차단)
- hosted Core 완주 후 Linux scoped-handle 23건 결과를 보고서에 추가(O1).
- `replayed` 필드의 소비자(화면/CLI) 정합은 Gemini 레인에 통지(O3).

## 판정
**승인** — 계약 앵커·fixture·replay guard·미러 동기·권한/tenant 경계·inv_app 차단이 실 PG에서 실측되고 되살림이 성립하며, 미측정 항목이 정직하게 표기됐다. S06-DB는 review 유지(AC-06은 원격 WS/PTY/Git·재시작 여정 후).
