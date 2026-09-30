---
doc_id: "DESIGN-S04-DB-CORE-CANCEL-PRODUCT-BRIDGE-001"
title: "S04-DB core cancel 제품 경로 결속 설계"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-30T13:52:17+09:00"
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

- kernel Python helper: mapping 유무를 확인하고, 인증된 principal의
  `subject_id`를 `services/control-plane/src/inv/business_auth.py::permission`으로
  현재 business `userId`에 결속한 뒤 DB primitive를 호출한다.
- migration primitive: `PUBLIC` 실행권을 회수한 `SECURITY DEFINER` 함수 하나가
  `public.runs` 행을 잠그고 상태를 갱신하며 exact audit 한 행을 추가한다. 함수는
  `pg_catalog` 고정 search path, named arguments, 현재 `inv.tenant_id`와 입력 tenant
  일치, `inv.business_runs`/workload project 결속, actor/user membership 재검증을
  강제한다.

전용 NOLOGIN·NOINHERIT·NOBYPASSRLS owner role에는 필요한 SELECT, `public.runs`의
취소 관련 열 UPDATE, `public.audit_events` INSERT만 부여한다. `inv_kernel`에는 함수
EXECUTE만 주며 테이블 직접 쓰기 권한은 주지 않는다. 함수 인자로 받는 event ID는
kernel의 `services/control-plane/src/inv/ids.py::new_id('aud')`가 만들고 함수가
`^aud_[0-9A-HJKMNP-TV-Z]{26}$`를 재검증한다.

### D3. actor와 오류 경계

- HTTP 취소 actor는 항상 인증 principal에서 파생한 `user`와 현재 mapping의
  business `userId`다. caller가 `actor_type`·`actor_id`를 지정할 수 없다.
- trace는 middleware가 만든 W3C trace ID만 전달한다. detail에는
  `{"reason":"cancelled_by_user"}` 외 값을 넣지 않는다.
- actor 입력을 외부에서 받지 않으므로 CARD-159 service의 `ValueError`가 HTTP로
  새어 나올 경로가 없다. bridge 구조 불일치나 privilege 오류는 성공으로 숨기지
  않고 기존 `SYS-0001/503` 표면으로 전체 transaction을 실패시킨다.
- 접근권한 부족은 기존 `AUTH-0030/403`, version race는 `GRAPH-0003/409`, terminal
  kernel run은 `GRAPH-0002/409`를 유지한다. public 상태의 비정상 불일치는 상태를
  노출하는 새 오류가 아니라 fail-closed `SYS-0001/503`이다.

### D4. 상태·replay·shard 규칙

| 경우 | kernel 결과 | public/core 결과 |
|---|---|---|
| mapping 없음 | 기존 취소 그대로 | public write/audit 0 |
| 첫 non-terminal 취소 | `cancelled`, version 증가 | 잠근 public run도 `cancelled`, `cancelled_by_user`, 종료 시각·version 증가, audit 정확히 1 |
| 같은 ledger replay | 저장 응답 반환 | bridge 재호출 0, audit 증가 0 |
| 다른 key로 이미 cancelled | idempotent `cancelled` | public replay, audit 증가 0 |
| public이 `succeeded`/`failed`인데 kernel은 non-terminal | 전체 실패 | 상태·audit 0, `SYS-0001/503` |
| shard parent 취소 | 기존 원자적 member/parent 취소 | 같은 shard transaction에서 mapping된 run만 run-id 정렬 순서로 mirror; 보통 business parent 1개 |

잠금 순서는 기존 kernel 순서를 보존한다: kernel run(들, run ID 정렬) → resource
rows → business identity/membership → public run(들, 같은 run ID 정렬) → 상태/audit.
bridge 실패 뒤 idempotency 응답을 저장하지 않는다.

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

- migration 1개: 전용 role, RLS policy, SECURITY DEFINER 함수, EXECUTE grant,
  reversible downgrade. 번호는 coordinator가 배정한 다음 migration을 사용한다.
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
3. normal·shard 첫 취소에는 bridge가 있고 replay 분기에는 호출이 없다.
4. DB 함수 owner/search_path/grant/RLS policy와 downgrade revoke/drop을 정적으로
   고정한다.
5. `ValueError`나 raw database message가 ProblemDetails detail에 노출되지 않는다.

### hosted PostgreSQL 단일 파일

1. 실제 HTTP 첫 취소: inv/public run 모두 cancelled, public audit exact 1,
   actor는 subject mapping의 user, trace 일치.
2. 같은 key replay와 다른 key cancelled replay: 응답은 200, audit 합계 1.
3. 두 connection 동시 첫 취소: 두 응답의 최종 상태는 cancelled, audit 합계 1.
4. 권한 철회·mapping disable·타 project/run: 403/404 정책을 유지하고 두 상태와
   audit 모두 불변.
5. public terminal 불일치, audit INSERT 실패, bridge EXECUTE 회수: 503이며 kernel
   상태/outbox/resource/idempotency와 public 상태가 모두 rollback.
6. mapping 없는 kernel run: 기존 동작과 응답이 동일하고 public audit 0.
7. shard parent와 mapping된 member fixture: mapping된 각 run만 exact audit 1,
   전체 shard rollback 원자성 유지.
8. role은 함수를 실행할 수 있지만 public run/audit 직접 write는 거부된다.

## 6. 롤백

먼저 새 application 호출을 제거한 뒤 migration downgrade로 EXECUTE, 함수, policy,
전용 role을 제거한다. downgrade는 `inv_kernel`에 public table 직접 권한을 남기지
않아야 한다. 이미 생성된 audit는 append-only 기록이므로 삭제하지 않는다. 이
순서를 지키지 않고 schema부터 내리면 취소 route는 성공으로 우회하지 않고
`SYS-0001/503`으로 fail-closed해야 한다.

## 7. 승인 요청

Claude는 다음을 독립 검토한다.

- 기존 공개 cancel 계약을 바꾸지 않는지
- SECURITY DEFINER 인자·search_path·owner·RLS·downgrade가 privilege escalation을
  만들지 않는지
- normal/shard/replay의 잠금 순서와 원자성에 빈틈이 없는지
- `RECORDED_ONLY`를 구현 존재만으로 승격하지 않는지

승인 뒤 migration 번호를 배정받아 구현 카드로 이어간다.
