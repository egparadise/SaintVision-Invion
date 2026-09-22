---
doc_id: "HIST-CLAUDE-DECISION6A-MODEL-RETRY-INTEGRATION-001"
title: "결정 #6 6a 통합 검증 — POST …/runs/{parent}/model-retries (Codex 563c54ce) 실 PG + 실 HTTP: 7 passed, finding 1(타 tenant 503)"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T23:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["decision-6", "model-retry", "integration", "real-postgres", "http", "finding", "6c-placement"]
---

# 결정 #6 6a — model-retries 통합 검증 (Claude 레인)

배정: Codex 계약·라우트(`563c54ce`) → Gemini UI(미착지) → **Claude 통합 검증**. 대상 `POST /v1/projects/{project}/runs/{parent}/model-retries`(`inv/app.py`, `ModelRetryStore.prepare`). 시험 파일 **`tests/integration/test_model_retries_claude.py`**(단일 파일, Codex `test_model_retry.py`와 독립·상보). 실 PostgreSQL(일회용 Alembic-head DB, `.env INV_TEST_ADMIN_DSN` 127.0.0.1) + **실 HTTP**(`fastapi.testclient.TestClient(create_app(...))`, ASGI 경로 그대로). PowerShell `Start-Process` 분리 실행, 메모리 제약으로 단일 파일만.

## 1. 검증 표 (코디네이터 요구 항목 ↔ 시험 ↔ 결과)

| # | 요구 | 시험 | 관측 | 판정 |
|---|---|---|---|---|
| 1 | failed 종단 부모만 허용, 다른 상태 4xx | `test_non_failed_parent…[planned/awaiting_approval/scheduled/cancelled]` | 4건 모두 **409 `MODEL-0007`** ProblemDetails(계약 검증), lineage 0 | ✅ (running/succeeded는 guard가 직접 UPDATE를 막아 동일 분기로 갈음) |
| 1' | failed지만 lease 미해제 → 권한 이전 없음 | `test_failed_parent_with_unreleased_leases…` | **409 `LEASE-0003`**, lineage 0 | ✅ |
| 2 | Idempotency-Key 재사용 → 동일 child | 행복 경로 시험 내 replay | 201·**본문 동일**(deep equal) | ✅ |
| 2' | 같은 키 + 다른 본문 → 409 | 〃 | **409 `IDEM-0001`** ProblemDetails | ✅ |
| 2'' | 키 없음 | 〃 | **422 `VAL-0003`** | ✅ |
| 2''' | 다른 키로 같은 부모 재요청 | 〃 | **409 `MODEL-0003`**(부모당 child 1) | ✅ |
| 3 | can_request 없는 주체 403 | `test_subject_without_can_request…`(alice=approve만, outsider=grant 없음) | 둘 다 **403 `AUTH-0030`**, lineage 0 | ✅ |
| 3' | 타 tenant | `test_other_tenant_is_refused_403_and_never_creates_a_child` | child 0 + **403 `AUTH-0030`**(v1.1.0: Codex `4473c7f1`이 F1을 고쳐 pin을 403으로 뒤집음; 정본 tip에서 8 passed 재실측) | ✅ (F1 해소) |
| 4 | 응답 shape == 계약 fixture | 행복 경로 | `validate_contract("ModelRetryPrepareResult")` 통과 + **키 집합 동일**(최상위·run·placement·leases[0]) | ✅ |
| 5 | requiresFrozenInputAndApproval 정직, 자동 승인 없음 | 〃 | `true` 고정(계약 `Literal[True]`), child `state=planned`(awaiting_approval/scheduled 아님), `inv.tool_claims` 0 | ✅ |
| 6 | 옛 command/permit 미재사용, lineage 새 child | 〃 | lineage 정확히 1행 `(root=parent, parent, child, gen 2)`, child≠parent, **fencing token 교집합 ∅**(부모 leases vs child leases) | ✅ |
| 7 | placement 예약(6c) 연결 | 〃 | 응답 `placement.leases[].leaseId` 집합 == `inv.resource_leases`(child, released_at IS NULL) 집합 → **6c PlacementStore.reserve가 실제로 호출·영속** | ✅ |

**실행 결과**: **8 passed / 0 failed**(F1은 현 동작을 명시 pin — 아래), 28~32s. 시험 하네스 수정 2회: (a) 픽스처 체인 import 누락(Codex 파일과 같은 import 필요), (b) `running/succeeded`를 직접 UPDATE로 만들 수 없음(`inv.guard_run` 전이 규칙) → guard가 허용하는 상태로 교체. 둘 다 시험 문제, 제품 아님.

## 2. Finding

- **F1 — 타 tenant 요청이 503 `SYS-0001`(4xx 아님)** [소유 Codex, 분류·정직성] — **해소됨(2026-09-22 `4473c7f1`)**: `prepare`가 ledger INSERT 전에 호출자 tenant 범위의 `can_request` preflight를 두어 403 AUTH-0030. 되살림: preflight 제거 시 Codex 시험이 503으로 회귀(FAIL) 확인(검토 문서 `2026-09-22_Codex_카드2_실행Manifest관측_model-retry_F1_독립검토_Claude.md`, 별도 PR). 아래는 발견 당시 기록. `ModelRetryStore.prepare`가 **run 존재·grant 확인보다 먼저** `inv.idempotency`에 ledger 행을 INSERT한다(`_ledger` → `_grant` → `_scope` 순). 타 tenant principal의 트랜잭션에서 그 INSERT가 FK `inv.projects(tenant_id, project_id)`(또는 RLS)에 막혀 DB 예외가 되고, `inv.app`의 일반 예외 매핑이 **503 "Service temporarily unavailable", retryable=false**로 바꾼다. **child·lineage는 생성되지 않으므로 유출은 아니다**. 그러나 (i) 클라이언트가 "서버 장애"로 오해해 재시도하고, (ii) 운영 알람에 503으로 잡힌다. 권고: `_scope`의 `lock_run`(→ 404 `RES-0004`)/grant(→ 403)를 ledger INSERT 앞에 두거나, FK/RLS 예외를 404로 매핑. 시험은 현 동작을 **명시 pin**(xfail이면 backend skip-ratchet의 사유 카운트가 깨지므로) — 고쳐지면 pin을 4xx로 뒤집는다.
- **관찰(finding 아님)** — 6c 배치 예약이 실제로 연결되어 있음(표 7). Codex 문서의 "6c는 6a 연결 시 자동 해소"가 실 PG에서 성립.
- **관찰** — 응답의 `run.state`는 `planned`이며 approval 객체를 돌려주지 않는다(Workspace의 `WorkspacePrepareResult`와 달리). 후속 승인 경로(`/approvals`)를 클라이언트가 별도로 밟아야 함 — UI(Gemini) 카드가 이 흐름을 그려야 한다.

## 3. 범위 밖 / 하지 않은 것
- 8080 dev 서버 경유 실호출은 하지 않았다(dev DB에 failed 모델 Run·lease 픽스처가 없음; TestClient가 같은 ASGI 앱·같은 미들웨어를 탄다).
- Gemini UI 연결은 미착지라 브라우저 여정은 없음.
- 3세대 예산·동시성·복구 롤백은 Codex 시험이 이미 덮어 중복하지 않았다.

관련: [[2026-09-22_미연결_능력_부류_현황_및_노출분석_Gemini]] · [[사용자_결정대기_브리프_2026-09-22]] §6a · [[2026-09-22_Run_retry_path_and_low_risk_write_contracts_Codex]]
