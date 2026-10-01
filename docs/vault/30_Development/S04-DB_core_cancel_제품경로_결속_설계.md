---
doc_id: "DESIGN-S04-DB-CORE-CANCEL-PRODUCT-BRIDGE-001"
title: "S04-DB core cancel 제품 경로 결속 설계"
version: "1.2.2"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T10:40:20+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd"
task_ids: ["S04-DB"]
tags: ["s04-db", "cancel", "audit", "business-handoff", "atomicity", "security-definer"]
---

# S04-DB core cancel 제품 경로 결속 설계

## 0. 선택과 범위

CARD-159(PR #256)은 `src/saintvision/services/runs.py`의 취소 상태와 exact
`run.cancel.requested` audit를 한 transaction에 결속했지만, 운영 HTTP/worker가 그
service를 호출하지 않으므로 clean evidence를 `RECORDED_ONLY`로 유지했다. 다음
외부 전제 없는 Codex 고난도 공백으로 이 호출 경로를 선택한다. 출발점은
`origin/integration/all-agents-unified` `6fc0428b49f28379cb4da17830d92256b55c2eb2`와
그 위의 CARD-159 승인 head
`c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd`이다.

이 문서는 계약과 transaction 경계를 먼저 고정한다. migration 번호와 구현은 이
설계의 보안 검토 뒤 별도 commit/card에서 수행한다. S04-DB는 계속 `review`이며,
이 문서만으로 운영 evidence를 `MEASURED_PASS`로 올리지 않는다.

## 1. 현재 제품 경계

1. 공개 취소 route의 정본은
   `services/control-plane/src/inv/app.py`의
   `POST /v1/projects/{project}/runs/{run_id}/cancel`이다. 입력은
   `contracts/v1alpha1/core.schema.json`의 strict `RunCancelInput`, 응답은
   `ControlRunDetail`이고 `Idempotency-Key`를 사용한다.
2. kernel의 실제 취소 authority는
   `services/control-plane/src/inv/control.py::Control.cancel`과 shard parent의
   `services/control-plane/src/inv/shards.py::ShardRuntime.cancel`이다. kernel run,
   resource lease, outbox, idempotency ledger를 한 kernel transaction에서 바꾼다.
3. business/core 취소 불변식은
   `src/saintvision/services/runs.py::cancel_run`에 있다. CARD-159부터 첫 상태 전이와
   `public.audit_events.action='run.cancel.requested'`가 같은 transaction이고, replay는
   audit를 늘리지 않는다.
4. production의 `services/control-plane/src/inv/business_surface.py::BusinessDispatch`는
   실행 route를 kernel에 남긴다. 같은 URL을 business router에도 추가하면 어느
   authority가 resource와 shard를 취소하는지 갈라지므로 허용하지 않는다.
5. `services/control-plane/src/inv/migrations/0021_business_kernel.sql`은 `inv_kernel`에
   `public.runs` SELECT와 lock sentinel UPDATE만 준다. public run 상태 UPDATE와
   `public.audit_events` INSERT 권한은 없다. 따라서 단순 Python 호출 추가만으로는
   같은 transaction 결속을 구현할 수 없다.

## 2. 결정

### D1. 공개 계약 변경 없음

새 route, body 필드, 응답 필드, status code를 추가하지 않는다. 기존
`RunCancelInput={expectedVersion}`, `ControlRunDetail`, `Idempotency-Key`,
ProblemDetails 표면을 그대로 유지한다. actor, reason, trace를 요청 body에서 받지
않는다.

### D2. kernel transaction 안의 좁은 business bridge

`inv.business_runs`에 결속된 run만 kernel 취소 transaction 안에서 core 상태와
audit를 함께 바꾼다. 별도 HTTP 호출, 별도 `inv_app` transaction, out-of-band
best-effort audit는 금지한다. 하나라도 실패하면 kernel 상태, resource/outbox,
public 상태, audit, idempotency ledger가 모두 rollback돼야 한다.

구현 seam은 다음 두 층으로 둔다.

- kernel Python helper: mapping 유무를 확인하고, **이 요청이 kernel 상태를
  non-terminal에서 `cancelled`로 실제 전이한 경우에만** DB primitive를 호출한다.
  이미 kernel이 cancelled인 replay/다른 key 요청은 public 상태를 보정하거나 audit를
  새로 만들지 않고 drift 관측 대상으로 남긴다.
- migration primitive: `PUBLIC` 실행권을 회수한 `SECURITY DEFINER` 함수 하나가
  `public.runs` 행을 잠그고 상태를 갱신하며 exact audit 한 행을 추가한다. 함수는
  `pg_catalog` 고정 search path와 정적 SQL만 사용한다. 인자는
  `p_subject_id`, `p_project_id`, `p_run_id`, `p_event_id`, `p_trace_id` 다섯 개뿐이다.
  현재 `inv.tenant_id`, 같은 transaction의 `inv.runs.state='cancelled'`,
  `inv.runs.project_id`, `inv.business_runs`와 public workspace/workload project 결속을
  재검증한다.

전용 NOLOGIN·NOINHERIT·NOBYPASSRLS owner role에는 필요한 SELECT, `public.runs`의
취소 관련 열 UPDATE, `public.audit_events` INSERT만 부여한다. `inv_kernel`에는 함수
EXECUTE만 주며 테이블 직접 쓰기 권한은 주지 않는다. 함수 인자로 받는 event ID는
kernel의 `services/control-plane/src/inv/ids.py::new_id('aud')`가 만들고 함수가
`^aud_[0-9A-HJKMNP-TV-Z]{26}$`를 재검증한다. trace는 `^[0-9a-f]{32}$`만 허용한다.

함수 내부에서 `p_subject_id`를 enabled `inv.business_subjects` → active
`public.users` → active business project → `project_members.role_code`의
`owner|maintainer|operator` 순으로 다시 결속해 actor user를 파생한다. caller는
user ID를 주지 않는다. `actor_type='user'`, `action='run.cancel.requested'`,
`outcome='allow'`, `target_type='run'`, `detail={"reason":"cancelled_by_user"}`와
`termination_reason='cancelled_by_user'`는 함수 상수다. trace는 correlation일 뿐
인증 provenance가 아니다. DB는 OIDC subject 자체를 증명하지 못하므로 침해된 kernel이
다른 적격 subject를 고르는 위험은 kernel/RLS 신뢰 경계에 남는다.

owner 전용 RLS policy는 `public.runs`, `public.audit_events`, `public.users`,
`public.project_members`, `public.projects`, `public.workspaces`, `public.workloads`와
필요한 `inv` 결속 테이블에 명시한다. audit INSERT `WITH CHECK`는 tenant GUC와 위
action/outcome/target 상수를 모두 강제한다. `public.runs` 권한은
`state, termination_reason, ended_at, version` UPDATE와 필요한 SELECT 열로 제한한다.
owner role은 NOLOGIN·NOINHERIT·NOBYPASSRLS이며 migration은 기존 member가 있으면
fail-closed한다. `PUBLIC`과 `inv_app`의 EXECUTE는 명시적으로 회수한다.

### D3. actor와 오류 경계

- HTTP 취소 actor는 항상 인증 principal에서 파생한 `user`와 현재 mapping의
  business `userId`다. caller가 `actor_type`·`actor_id`를 지정할 수 없다.
- trace는 middleware가 만든 W3C trace ID만 전달한다. detail에는
  `{"reason":"cancelled_by_user"}` 외 값을 넣지 않는다.
- actor 입력을 외부에서 받지 않으므로 CARD-159 service의 `ValueError`가 HTTP로
  새어 나올 경로가 없다. bridge 구조 불일치나 privilege 오류는 성공으로 숨기지
  않고 기존 `SYS-0001/503` 표면으로 전체 transaction을 실패시킨다. DB lock 대기는
  `RES-0007/503/retryable=true`로 끝난다.
- 접근권한 부족은 기존 `AUTH-0030/403`, version race는 `GRAPH-0003/409`, terminal
  kernel run은 `GRAPH-0002/409`를 유지한다. public 상태의 비정상 불일치는 상태를
  노출하는 새 오류가 아니라 fail-closed `SYS-0001/503`이다.

### D4. 상태·replay·shard 규칙

| 경우 | kernel 결과 | public/core 결과 |
|---|---|---|
| mapping 없음 | 기존 취소 그대로 | public write/audit 0 |
| 첫 non-terminal 취소 | `cancelled`, version 증가 | 잠근 public run도 `cancelled`, `cancelled_by_user`, 종료 시각·version 증가, audit 정확히 1 |
| 같은 ledger replay | 저장 응답 반환 | bridge 재호출 0, audit 증가 0 |
| 다른 key, kernel·public 모두 이미 cancelled | idempotent `cancelled` | bridge 재호출 0, audit 증가 0 |
| containment/dispatch/shard 등이 kernel만 먼저 cancelled | idempotent `cancelled` | public write/audit 0, drift 관측 |
| kernel은 이미 cancelled, public은 succeeded/failed | idempotent `cancelled` | public write/audit 0, terminal 상태 보존·drift 관측 |
| public이 `succeeded`/`failed`인데 kernel은 non-terminal | 전체 실패 | 상태·audit 0, `SYS-0001/503` |
| shard parent 취소 | 기존 원자적 member/parent 취소 | 같은 shard transaction에서 mapping된 run만 run-id 정렬 순서로 mirror; 보통 business parent 1개 |

잠금 순서는 선행 idempotency ledger lock을 포함해 기존 kernel 순서를 보존한다.
normal은 ledger → kernel run → resource rows → business identity/membership → public
run → 상태/audit다. shard는 ledger → shard plan → member runs(run ID 정렬) → parent
run → business identity/membership → public runs(run ID 정렬) → 상태/audit이며 resource
lock은 없다. bridge 실패 뒤 idempotency 응답을 저장하지 않는다.

## 3. 기각한 선택지

| 선택지 | 기각 사유 |
|---|---|
| business app에 같은 cancel route 추가 | `BusinessDispatch`가 kernel authority를 우회해 resource lease·shard·outbox 취소가 갈라진다 |
| kernel 성공 뒤 localhost HTTP로 core 호출 | 두 transaction 사이 crash가 상태와 audit를 영구 분리한다 |
| `inv_kernel`에 public table UPDATE/INSERT 직접 grant | kernel 전체 SQL 표면에 business 상태·audit 위조 권한을 준다 |
| 비동기 outbox consumer만 사용 | 전달 전까지 C1이 사실이 아니며 exactly-once audit와 취소 응답 commit이 같은 경계가 아니다 |

비동기 consumer는 관측 복구용 보조 수단일 수 있으나 정본 취소 producer가 될 수
없다.

## 4. 구현 변경 범위

- alembic 단일 stream의 Python migration `0056_*` 1개(현재 head
  `0055_adapter_conformance_records`): 전용 role, RLS policy, SECURITY DEFINER 함수,
  EXECUTE grant, reversible downgrade.
- `tools/definer-policy.json`에 정확한 signature·definition hash·
  `executeRoles:["inv_kernel"]`·tenant-bound kind를 등록하고 revision을 `0056_*`로
  올린다. `tools/collect_rls_evidence.py`와
  `tools/rls-boundary-baseline.json`에는 새 owner를 포함한다.
- `services/control-plane/src/inv/` helper와 `Control.cancel`,
  `ShardRuntime.cancel` 호출 결속.
- 공개 JSON Schema와 생성 계약은 변경 0. 계약 fixture는 기존
  `RunCancelInput`/`ControlRunDetail`이 byte-equivalent임을 검사한다.
- CARD-159 collector는 제품 route의 배포 SHA와 관측 창이 들어오기 전까지
  `RECORDED_ONLY`를 유지한다. 구현 뒤에도 과거 row를 소급해 canonical producer
  산출로 세지 않는다.

## 5. 되돌리면 실패해야 하는 시험

### PG-free

1. route가 request actor/reason을 읽지 않고 principal subject만 helper에 전달한다.
2. public 계약 파일과 생성 타입 diff가 0이다.
3. normal·shard의 실제 kernel 전이 분기에만 bridge가 있고 replay와 kernel 선취소
   분기에는 호출이 없다.
4. DB 함수 owner/search_path/static SQL/grant/RLS policy와 downgrade revoke를 정적으로
   고정한다.
5. `ValueError`나 raw database message가 ProblemDetails detail에 노출되지 않는다.

### hosted PostgreSQL 단일 파일

1. 실제 HTTP 첫 취소: inv/public run 모두 cancelled, public audit exact 1,
   actor는 subject mapping의 user, trace 일치.
2. 같은 key 동시 요청은 둘 다 200이고 audit 합계 1. 다른 key 동시 요청은 200과
   `GRAPH-0003/409`이며 audit 합계 1.
3. GUC 미설정·교차 tenant·kernel non-terminal 직접 함수 호출·mapping 없음·
   project/workspace 불일치·disabled subject·inactive user·viewer/approver-only role·
   event ID/trace 오류는 모두 거부되고 상태와 audit가 0이다.
4. `inv_app`·PUBLIC 함수 실행과 owner `SET ROLE`은 거부된다. `inv_kernel`은 함수만
   실행할 수 있고 public run/audit 직접 write는 거부된다.
5. public terminal 불일치, audit INSERT 실패, bridge EXECUTE 회수: 503이며 kernel
   상태/outbox/resource/idempotency와 public 상태가 모두 rollback.
6. mapping 없는 kernel run: 기존 동작과 응답이 동일하고 public audit 0.
7. shard parent와 mapping된 member fixture: mapping된 각 run만 exact audit 1,
   전체 shard rollback 원자성을 유지. CARD-166은 한 parent 취소 요청 안에서 이미
   kernel-cancelled 된 mapped member는 public draft·audit 0으로 남기고, 실제 전이한
   다른 member와 parent만 `cancelled_by_user`·audit 각 1건으로 결속하는 real-PG
   fixture를 추가했다. 구현은 완료됐지만 hosted Core JUnit 전에는 **NOT_RUN**이며,
   실행 결과는 PR의 exact-head evidence에서만 판정한다.
8. 다른 transaction이 public run lock을 보유하면 `RES-0007/503/retryable=true`,
   kernel/outbox/resource/ledger/public/audit 모두 미저장이고 같은 key 재시도는 성공해
   audit가 정확히 1이다.
9. containment가 먼저 kernel을 취소한 run에 사용자 취소를 보내면 public write와
   audit는 0이다.
10. audit 월 파티션이 없으면 503과 전체 rollback이다.
11. `tools/check_definer_functions.py`는 `matches_reviewed_policy`, RLS collector는
   E1~E6 PASS여야 한다.

## 6. 운영 의존성과 탈출구

`public.audit_events`는 월 파티션에 DEFAULT가 없다. 다음 달 파티션 선행 생성이
끊기면 business-mapped 사용자 취소는 fail-closed 503이 된다. 이 실패는 숨기지 않고
경보 대상이다. 그때 연산 정지의 탈출구는 사용자 cancel을 우회하는 tenant kill-switch
`ContainmentReconciler`이며, 그 선행 kernel 취소를 뒤늦은 사용자 actor/audit로
재분류하지 않는다. collector 관측 창은 migration 적용 시각 뒤에서 시작해야 한다.

## 7. 롤백

먼저 새 application 호출을 제거한 뒤 migration downgrade로 EXECUTE, 함수, policy,
owner의 권한을 회수한다. cluster 공유 가능성이 있는 전용 role 자체는 drop하지 않는다.
downgrade는 `inv_kernel`에 public table 직접 권한을 남기지 않아야 한다. 이미 생성된
audit는 append-only 기록이므로 삭제하지 않는다. 이 순서를 지키지 않고 schema부터
내리면 취소 route는 성공으로 우회하지 않고 `SYS-0001/503`으로 fail-closed해야 한다.

## 8. 승인 조건과 구현 진행

Claude는 다음을 독립 검토한다.

- 기존 공개 cancel 계약을 바꾸지 않는지
- SECURITY DEFINER 인자·search_path·owner·RLS·downgrade가 privilege escalation을
  만들지 않는지
- normal/shard/replay의 잠금 순서와 원자성에 빈틈이 없는지
- `RECORDED_ONLY`를 구현 존재만으로 승격하지 않는지

Claude의 2026-09-30 조건부 승인(M1~M4, L1~L5, R5~R8)을 이 v1.1에 반영했다.
구현은 이 문서 commit 다음 별도 commit으로 이어가며, 공개 계약 변경 0과
`RECORDED_ONLY`·S04-DB `review` 유지를 승인 조건으로 둔다.

## 9. 구현 결과(v1.2)

- migration `0056_kernel_cancel_audit_bridge`와 제품 helper를 구현했다. normal과
  shard 취소는 이 요청이 kernel 상태를 실제로 전이한 분기에서만 bridge를 호출하며,
  middleware trace를 그대로 전달한다. mapping 없는 run과 kernel 선취소 replay에는
  public write와 audit가 없다.
- 전용 `inv_cancel_bridge_owner`는 NOLOGIN·NOINHERIT·NOBYPASSRLS이고 member가 있으면
  migration이 중단된다. 함수는 정적 SQL과 고정 search path를 사용하며 PUBLIC·
  `inv_app` 실행권을 회수하고 `inv_kernel`에만 실행권을 준다. 실제 catalogue 정의
  SHA-256은 `3ebb7553073497364f41fd4ede1b363b1db3b743d66b99beb475e8953a32a0c1`으로
  `tools/definer-policy.json`과 AC-11 blob pin에 고정했다.
- hosted에서 함수가 호출자에게 이미 잠긴 kernel·mapping·authority 행을 다시
  `FOR SHARE` 하는 중복 잠금을 발견했다. `Control.grant`/`business_auth.permission`이
  같은 transaction에서 이 행들을 먼저 잠그므로 함수의 중복 잠금을 모두 제거했다.
  owner의 UPDATE 권한은 넓히지 않았고 public run의 최종 `FOR UPDATE`만 유지했다.
- Alembic의 이전 revision 회복 시험은 catalogue를 보존한 채 version marker만
  되돌린다. 0056은 같은 policy를 먼저 제거·정의하고 함수를 `CREATE OR REPLACE`해
  재적용이 수렴한다. 이 규칙이 없던 head에서는 0053~0055 회복 뒤 0056의 policy
  중복으로 Backend가 중단됐고, 후속 공유 DB 시험이 누락된 0054 열을 관측했다.
- "실제 kernel 전이일 때만 bridge 호출" 규칙은 현재 Python normal/shard 호출부가
  강제한다. DB 함수 자체는 같은 transaction의 `inv.runs.state='cancelled'`를
  재검증하지만 누가 그 전이를 수행했는지는 증명하지 못한다. 따라서 새 호출부를
  추가할 때는 동일 분기 guard를 되살림 시험과 함께 요구한다.
- 구현·시험 존재만으로 운영 배포 SHA와 관측 창을 만들지는 않는다. 따라서 clean C1은
  `RECORDED_ONLY`, S04-DB는 `review`를 유지한다. 월 audit partition이 없을 때의 503
  fail-closed·전체 rollback·같은 key 재시도와 tenant kill-switch 탈출구도 그대로다.
- exact-code `44556845448dea14813a9828c7817c8533a999ec`의 hosted Core
  `36686184969`는 전체 **5949 passed / 22 skipped / 2 deselected**, 그 JUnit 안의
  bridge real-PG **17/17 passed**였다. Backend `36686184974`도 Python 3.12·3.14가
  각각 **5629 passed / 50 skipped / 2 deselected**였다. 이 수치는 운영 배포 관측이
  아니라 제품 tree와 실 PostgreSQL 경계의 구현 검증이다. 이 17건에는 shard
  parent/member real-PG fixture가 없으며, 시험 7은 위의 **NOT_RUN** 후속 상태다.

## 10. CARD-166 시험 7 후속(v1.2.2)

- shard parent route 한 요청이 parent와 member를 같은 transaction에서 취소하는 실제
  경로를 `tests/integration/test_kernel_cancel_bridge_real_pg.py`에 고정했다. 먼저
  member 하나를 kernel에서 취소한 뒤 요청하므로, bridge가 단순히 최종 state만 보고
  호출되는 변이는 그 member의 public state·audit 단언에서 실패한다. 같은 key replay도
  audit 건수를 늘릴 수 없다.
- 직접 함수 부정군은 `viewer`, archived public project, disabled
  `inv.business_projects`를 추가했다. 세 경우 모두 kernel state가 cancelled여도 현재
  business authority를 재도출하지 못하므로 `42501`, public draft, audit 0이어야 한다.
- H1 PG-free guard는 특정 `FOR SHARE` 문자열 하나가 아니라
  `FOR (KEY SHARE|SHARE|NO KEY UPDATE|UPDATE)` 전체를 정규식으로 잡는다. public run의
  의도된 최종 `FOR UPDATE OF r`은 허용하고, 그 전에 kernel·mapping·authority 행을
  다시 잠그는 변형만 거부한다.
- 로컬 PG-free 단일 파일은 21 passed다. real-PG 판정은 `run-core` exact-head JUnit
  전까지 `NOT_RUN`이며, 공개 계약·migration·제품 코드는 변경하지 않았다.
