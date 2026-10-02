---
doc_id: "HISTORY-CARD223-S08-BE-PRODUCT-CALLER-20261002"
title: "Card 223 S08-BE product caller"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T13:44:26+09:00"
source_of_truth: "Git"
base_sha: "2dd25ff77a152575988b19a568ede348fd4dc1d8"
reviewer: "Claude"
---

# 선택 근거

`#317`의 재채점 근거는 `services/control-plane/src/inv/build_execution.py`의
`BuildExecutionService`를 제품에서 구성·호출하는 consumer가 0건이라고 측정했다. 승인된 Card 222
head `2dd25ff77a152575988b19a568ede348fd4dc1d8`에는 node-agent durable quarantine fence가 있으므로,
다음 외부 전제 없는 Codex 소유 공백은 공개 API가 아닌 trusted product worker seam이다. migration
0059는 코디네이터가 명시 예약했고 `0058_release_acceptance_resolver` 단일 부모로 고정했다.

# 표·RLS·trigger 설계

`inv.build_execution_intents`는 `(tenant_id, project_id, run_id)` 복합 PK다. 한 Run에 한 제품 build
intent만 허용하고, exact replay만 같은 행을 다시 읽는다.

| 영역 | 고정 규칙 |
|---|---|
| authority payload | strict `BuildRequest`·`BuildPlan`·`PolicyDecision` JSONB와 `policy_version`·`evidence_id`·사람 principal에서 얻은 `actor_id` |
| digest | PostgreSQL 16 `jsonb::text` UTF-8 bytes의 SHA-256을 INSERT trigger가 계산; caller digest는 authority가 아님 |
| lifecycle | `pending → claimed → completed`만 허용; claimed를 pending으로 되돌리는 retry 없음 |
| immutability | lifecycle 외 열 UPDATE 거부, DELETE 거부, 실패·crash의 claimed 행은 operator reconciliation 대상 |
| isolation | `ENABLE`+`FORCE ROW LEVEL SECURITY`, `inv.tenant_id` exact tenant policy, runtime role은 SELECT·INSERT와 lifecycle 열 UPDATE만 |
| concurrency | `SELECT … FOR UPDATE SKIP LOCKED` 후보를 같은 transaction에서 claimed로 전이; 두 worker가 같은 행을 받을 수 없음 |
| downgrade | 행이 하나라도 있으면 downgrade 거부; 기존 데이터 0인 배포에서만 빈 구조를 제거 |

# 제품 경로와 비주장 경계

`services/control-plane/src/inv/build_execution_worker.py`의 trusted enqueue는 세 공개 계약과
tenant/project/policy/subject 결속을 먼저 검사하고 committed Run이 `scheduled|running|verifying`일 때만
저장한다. worker는 product flag가 exact `1`인지 **claim 전에** 확인하고, DB에서 되읽은 strict 문서로
`BuildExecutionService.execute()`를 호출한다. 성공 뒤에만 completed로 전이한다.

공개 route와 browser 입력은 없다. worker가 실패한 claimed intent를 재queue하지 않는다. 실제 dispatch의
decision one-shot, live lease/fence, ROOF, node-agent health·cleanup, durable quarantine은 기존
`BuildExecutionAdapter`와 `BuildExecutionService`가 다시 검증한다. quarantine capability가 없거나 검증할
수 없으면 `RES-0006`이고, 기본 flag off는 유지된다. 이 변경은 S08-BE 완료·75점·물리 LAN builder
인수를 의미하지 않는다.

# 현재 검증

| 명령 | 결과 |
|---|---|
| `.venv\\Scripts\\python.exe -m pytest tests/core/test_build_execution_intents.py -q` | 13 passed |
| focused migration·AC-11·resolver 4파일 | 52 passed |
| `.venv\\Scripts\\python.exe -m pytest tests/test_migrations.py -q` | 27 passed |
| `.venv\\Scripts\\python.exe tools/migration_graph.py --head` | exit 0, `0059_build_execution_intents` |
| `python -m alembic upgrade head --sql` | exit 0, table·policy offline render 확인 |
| `git diff --check` | exit 0 |

로컬 `INV_TEST_ADMIN_DSN`은 설정되지 않았다. 따라서
`tests/integration/test_build_execution_intents_real_pg.py`의 two-connection one-shot claim, RLS,
payload 불변·DELETE 거부와 worker completion은 exact-head hosted Core가 실행하기 전까지
`NOT_OBSERVED`다. Claude 독립 검토와 hosted Core가 남아 있으므로 status는 review다.
