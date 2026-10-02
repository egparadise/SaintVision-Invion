---
doc_id: "HISTORY-CARD223-S08-BE-PRODUCT-CALLER-20261002"
title: "Card 223 S08-BE product caller"
version: "1.0.3"
status: "review"
author: "Codex"
updated: "2026-10-02T14:45:13+09:00"
source_of_truth: "Git"
base_sha: "2dd25ff77a152575988b19a568ede348fd4dc1d8"
reviewer: "Claude"
---

## Claude r1 corrective boundary

Claude r1 correctly found that committing `pending -> claimed` before the service call could
strand every pre-dispatch retryable failure. The correction does not permit a general retry. It
returns `claimed -> pending` only when the adapter's durable `build.dispatch` one-shot claim is
absent. The adapter now stores the decision ID in that claim, and both the runtime queue and the
database trigger independently refuse to requeue a consumed dispatch. The original failure is
preserved even when the recovery write itself fails.

The claim query now verifies all three database-owned JSONB digests before transition. The INSERT
trigger also binds actor/subject, plan/decision action digest, and plan/decision expiry, so an
owner-restored corrupt row is quarantined and a SQL-checkable poison row is rejected before it can
block the queue. The strengthened real-PG cases cover a locked-first-row `SKIP LOCKED` selection,
payload mutation during a valid transition, completed-to-pending rollback, unconsumed versus
consumed requeue, digest tampering, poison binding, and a retryable pre-dispatch failure.

PG-free focused verification is **101 passed**. The local real-PG file contains **9 cases** but is
`NOT_OBSERVED` locally because no disposable PostgreSQL DSN is configured; exact-head hosted Core
must execute all nine before this revision is accepted. S08-BE completion or physical-builder
acceptance is still not claimed.

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
| lifecycle | `pending → claimed → completed`, retryable pre-dispatch의 bounded-backoff `claimed → pending`, invalid authority의 terminal `quarantined`만 허용 |
| retry metadata | claim마다 `attempt_count` 증가; retry는 `next_attempt_at` 1~60초 backoff와 `last_error_code`를 기록 |
| immutability | lifecycle 외 authority payload UPDATE와 DELETE 거부; committed dispatch의 claimed 행은 operator reconciliation 대상 |
| isolation | `ENABLE`+`FORCE ROW LEVEL SECURITY`, `inv.tenant_id` exact tenant policy, runtime role은 SELECT·INSERT와 lifecycle 열 UPDATE만 |
| concurrency | `SELECT … FOR UPDATE SKIP LOCKED` 후보를 같은 transaction에서 claimed로 전이; 두 worker가 같은 행을 받을 수 없음 |
| downgrade | 행이 하나라도 있으면 downgrade 거부; 기존 데이터 0인 배포에서만 빈 구조를 제거 |

# 제품 경로와 비주장 경계

`services/control-plane/src/inv/build_execution_worker.py`의 trusted enqueue는 세 공개 계약과
tenant/project/policy/subject 결속을 먼저 검사하고 committed Run이 `scheduled|running|verifying`일 때만
저장한다. worker는 product flag가 exact `1`인지 **claim 전에** 확인하고, DB에서 되읽은 strict 문서로
`BuildExecutionService.execute()`를 호출한다. 성공 뒤에만 completed로 전이한다.

공개 route와 browser 입력은 없다. worker는 durable one-shot claim이 없는 retryable pre-dispatch
거부만 bounded-backoff pending으로 되돌린다. 영구 거부와 손상 행은 quarantined로 격리하고 다음 행을
계속 처리하며, one-shot claim이 있으면 claimed 상태를 보존한다. 실제 dispatch의
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

## Hosted 1차 실행과 교정

PR `#323`의 첫 exact-head Backend run `36966250740`은 Python 3.12와 3.14에서 같은 두
시험이 실패했다. 첫째, migration head를 `0059`로 올리며 바뀐
`tools/definer-policy.json` Git blob을 AC-11 집계기의 `DEFINER_FILES` pin에 함께
회전하지 않았다. 둘째, replay 부정 시험이 저장된 문서와 다른 **유효한** strict 문서가
아니라 request만 바꾼 무효 문서를 넣어, 의도한 `IDEM-0001`보다 앞선 authority 검증의
`VERIFY-0002`를 받았다. 제품 dispatch 또는 DB 경합 실패가 아니라 pin·시험 fixture
결함이다.

교정은 definer policy blob을 실제 Git blob `e16ee086d5ba301d45fec4f8fac6a5333ae1a39a`로
고정하고, replay fixture가 변경 request의 `requestDigest`와 canonical action digest를
plan·decision 양쪽에 다시 결속하도록 했다. 교정 후 focused PG-free 검증은
`test_kernel_cancel_bridge.py` + `test_build_execution_intents.py` 34 passed,
AC-11 집계기까지 포함한 묶음은 120 passed다. 로컬에는 disposable PostgreSQL DSN이 없어
real-PG 5건은 계속 hosted Core의 exact-head JUnit을 판정 근거로 삼는다.

로컬 `INV_TEST_ADMIN_DSN`은 설정되지 않았다. 따라서
`tests/integration/test_build_execution_intents_real_pg.py`의 two-connection one-shot claim, RLS,
payload 불변·DELETE 거부와 worker completion은 exact-head hosted Core가 실행하기 전까지
`NOT_OBSERVED`다. Claude 독립 검토와 hosted Core가 남아 있으므로 status는 review다.
