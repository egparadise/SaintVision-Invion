---
doc_id: "HISTORY-20260930-CARD160-S04-CANCEL-PRODUCT-BRIDGE-CODEX"
title: "CARD-160 S04-DB core cancel 제품 경로 결속 설계"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-30T17:21:52+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd"
task_ids: ["S04-DB"]
tags: ["card-160", "s04-db", "cancel", "product-route", "atomic-bridge"]
---

# CARD-160 S04-DB core cancel 제품 경로 결속 설계

## 선택 근거

- CARD-159/PR #256 최종 head
  `c9c1d836ff8fcd606b5bca3862c6cd764eadf4fd`에서 core 취소 상태와
  `run.cancel.requested` audit의 원자적 producer, 동시 취소 직렬화, hosted
  Backend/Core green을 확보했다.
- 그러나 production HTTP는 kernel `Control.cancel`을 호출하고 core
  `cancel_run` 호출자는 0이므로 clean C1은 여전히 `RECORDED_ONLY`다. 추가 PC,
  물리 Node, 원격 WS 없이 닫을 수 있는 가장 직접적인 S04-DB 공백이다.
- S05/S07의 5노드 성능·복구와 S08의 실제 PITR/보존 관측은 외부 자원이 필요하므로
  이 카드보다 뒤다.

## 조사 결과

- 공개 route·입력·응답은 이미 kernel에 확정돼 새 계약이 필요하지 않다.
- production `BusinessDispatch`도 run 실행 경로를 kernel에 남기도록 의도적으로
  제한한다.
- kernel role은 public run의 identity를 읽고 잠글 수 있지만 상태 UPDATE와 audit
  INSERT 권한은 없다. 별도 transaction으로 core service를 호출하면 kernel 취소와
  public audit 사이 crash gap이 생긴다.

## 결정

공개 계약은 변경하지 않는다. business-mapped run에만 같은 kernel PostgreSQL
transaction 안에서 좁은 SECURITY DEFINER primitive를 호출해 public run 상태와
exact audit를 함께 갱신한다. actor는 request가 아니라 인증 subject의 현재 business
user mapping에서 파생하며, 구조 불일치는 기존 `SYS-0001/503`으로 fail-closed한다.

normal·shard·replay 잠금 순서, privilege 최소화, downgrade, 부정 시험과 hosted 실
PG 판정은 [[S04-DB_core_cancel_제품경로_결속_설계]]에 고정했다. migration 번호가
필요하므로 보안 설계 승인과 번호 배정 뒤 구현한다. 이 단계에서는 코드·migration·
registry 상태를 바꾸지 않았고 S04-DB는 `review`를 유지한다.

## Claude 조건부 승인 반영(v1.1)

- bridge는 이 HTTP 요청이 kernel 상태를 실제 전이한 경우에만 호출한다. containment·
  dispatch·shard 등으로 kernel이 먼저 cancelled인 경우에는 뒤늦은 사용자 actor와
  `cancelled_by_user` audit를 만들지 않고 drift 관측으로 남긴다.
- 함수 인자를 subject/project/run/event/trace로 닫고 user·actor·action·outcome·
  target·reason은 함수 내부에서 결속·상수화했다. 같은 transaction의 kernel cancelled
  상태와 project/workspace 결속, static SQL, trace 형식도 승인 조건이다.
- owner 무-member 가드, table/column 최소 권한, owner 전용 RLS WITH CHECK,
  `PUBLIC`·`inv_app` EXECUTE 회수, definer policy와 RLS evidence/baseline 갱신을
  `0056_*` 구현 범위에 넣었다.
- 같은 key/다른 key 동시성, `RES-0007` lock timeout, 교차 tenant·권한·형식·
  kernel 선취소·audit partition 부재의 rollback 시험을 분리했다. kill-switch
  containment를 운영 탈출구로 명시하고 S04-DB `review`·`RECORDED_ONLY`는 유지한다.

## 구현과 교정

- `26f522eb`에서 제품 helper, normal·shard 결속, migration 0056, owner/RLS/definer
  gate와 PG-free·실 PG 시험을 구현했다. 공개 route·JSON Schema·ProblemDetails의
  새 code는 없으며 계약 표면 변경은 0이다.
- hosted Core `36675282617`은 migration과 definer pin을 통과한 뒤 기존 business
  handoff 취소에서 503을 재현했다. `846899fa`에서 호출자에게 이미 잠긴 kernel run과
  불변 mapping의 중복 `FOR SHARE`를 제거했다. 다음 Core `36676509637`도 503을 재현해,
  실제 authority 행의 `FOR SHARE`에 필요한 row-lock privilege가 빠졌음을 분리했다.
  `58d08dbe`의 sentinel grant 시도는 Claude r2에서 더 좁은 해법이 확인돼 최종안에서
  철회했다. `7168bc27`은 같은 transaction의 `Control.grant`/`business_auth.permission`이
  이미 잡은 authority lock을 재사용하도록 중복 `FOR SHARE`를 없앴다. owner UPDATE
  권한은 넓히지 않았고 이 경계를 PG-free 되살림 시험으로 고정했다.
- hosted catalogue가 보고한 교정 함수 definition SHA-256
  `3ebb7553073497364f41fd4ede1b363b1db3b743d66b99beb475e8953a32a0c1`을
  `9961ac0c`에서 definer policy와 AC-11 blob pin에 고정했다.
- route 전단의 비회원은 정본 `AUTH-0030/403`이고, 함수 내부 subject→user→role
  재도출은 `inv_kernel` 직접 호출 부정 시험으로 분리했다. mapping 없음, 비활성
  subject/user, approver-only role, event ID 재사용, public terminal 불일치, EXECUTE
  회수 rollback과 shard parent 분기 변이를 추가했다. 실제 전이 분기 강제는 Python
  호출부 불변식이라는 잔여 경계도 설계에 명시했다.
- `9961ac0c` Backend run `36678328387`은 이전 migration 회복 시험이 version marker만
  0052/0053으로 되돌린 뒤, 이미 남은 0056 policy를 다시 만들면서
  `DuplicateObject`로 중단됐다. 그 결과 공유 DB가 0053에 남아 0054의
  `verified_measurement_id` 누락 실패가 연쇄된 것이며 bridge 제품 동작 실패와는
  구분된다. `fd565286`은 0056 policy/function 재적용을 수렴형으로 바꾸고 이를
  되살림 시험으로 고정했다.
- audit 월 partition을 일시 분리한 실 PG 시험도 추가했다. 취소는 `SYS-0001/503`,
  kernel/public/audit/idempotency는 모두 rollback되고 partition 복구 후 같은 key가
  audit 정확히 1건으로 성공해야 한다.

## 검증

- PG-free: `tests/core/test_kernel_cancel_bridge.py` **17 passed**,
  `tests/test_migrations.py` **26 passed**,
  `tests/test_ac11_migration_rehearsal.py` **21 passed**,
  `tests/test_aggregate_ac11_evidence.py` **85 passed**,
  `tests/test_collect_rls_evidence.py -m "not postgres"` **17 passed / 3 deselected**,
  `tests/test_collect_s02_acceptance_evidence.py` **30 passed / 1 opt-in skipped**.
- hosted 교정 run `36680958915`은 bridge 본체 시험 전 setup에서
  `workspace_http` fixture 미등록 17건을 드러냈다(그 밖 **5930 passed / 22 skipped /
  2 deselected**). fixture import를 명시한 `b9c86029`의 Core `36683585881`은 real-PG
  17건을 모두 실행해 **16 passed / 1 failed**였고, 실패는 DB 제약상 유효하지 않은
  public terminal fixture였다. fixture를 실제 `failed + termination_reason + ended_at`로
  고친 최종 제품 code head는 `44556845448dea14813a9828c7817c8533a999ec`다.
- 최종 code head의 Backend `36686184974`는 Python 3.12·3.14 각각 **5629 passed /
  50 skipped / 2 deselected**로 성공했다. Core `36686184969`도 **5949 passed /
  22 skipped / 2 deselected**로 성공했다. artifact `saintvision-core-evidence`
  (`11084263352`)의 `core-tests.xml`을 다시 읽어
  `tests.integration.test_kernel_cancel_bridge_real_pg` **17건 실행, 17 passed,
  failure/error/skip 0**을 확인했다. 여기에는 route 403, 함수 내부 권한 재도출,
  mapping·terminal·event ID 부정군, lock timeout, EXECUTE 회수, audit partition 부재,
  shard·동시 취소와 catalogue digest 검증이 포함된다.
- 계약·ontology·docs·path citation·migration graph·diff gate는 아래 문서 commit 전
  최종 working tree에서 다시 실행한다.

운영 배포 SHA·활성 시각·관측 창은 아직 없다. 따라서 이 구현은 C1의 제품 producer
선행 조건을 닫지만 clean C1은 `RECORDED_ONLY`, S04-DB는 `review`다.
