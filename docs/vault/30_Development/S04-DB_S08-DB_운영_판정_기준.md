---
doc_id: "CLAUDE-DONE-CRITERIA-S04DB-S08DB-001"
title: "S04-DB·S08-DB 운영 판정 기준 — 재전송은 코드가 이미 안전하게 만들었고 보존은 코드가 선언만 했다: 코드가 보장할 수 없는 것만 관측·계측·사전 등록 임계치로 고정한다 (카드 108, docs-only)"
version: "1.1.1"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-29T00:09:51+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "96a03486"
task_ids: ["S04-DB", "S08-DB"]
tags: ["done-criteria", "s04-db", "s08-db", "operational-acceptance", "retransmission", "retention", "claude"]
---

# S04-DB·S08-DB 운영 판정 기준

48 task 진행률 재채점(PR **#220**, `docs/vault/30_Development/2026-09-28 48 task 진행률 재채점.md`) §5가 두 task를 "**S04-DB 재전송·S08-DB 보존 정책의 운영 판정 기준**"으로 남겼다(§3의 두 행은 각각 "중복 요청·재전송 운영 인수", "보존 정책 운영 인수"를 외부 의존으로 적었다). 이 문서가 그 빈자리를 채운다. 카드 108이고 **docs-only**다 — 코드·migration 변경 0, 측정 실행 0. 형식은 카드 106(PR **#222**, `docs/vault/30_Development/S09-DB_S10-DB_S10-ST_운영_판정_기준.md`)과 같다.

분석 tree는 **`96a03486`**(`origin/coord/train-ci-2305`, 병합 목록 합성 commit)이고, 인용한 경로·줄은 그 tree에서 `git show`·`git grep -n`으로 확인했다. PR base(`integration/all-agents-unified`, `1e8baf04`)가 아니라 합성 commit을 고른 이유는 재채점이 S08-DB의 결속으로 든 `tests/core/test_canonical_denial_audit.py`·`tests/core/test_audit_action.py`가 base에는 없고 합성 commit에만 있기 때문이다(base에서 `git show`가 실패함을 확인했다). 그 밖의 인용은 두 tree에서 같다.

재채점 문서는 **wiki link가 아니라 평문(PR 번호·파일 경로)으로** 인용한다 — 병합 대기 문서를 wiki link로 두면 그것이 없는 branch에서 `check_docs`가 깨진다.

### v1.1 — Codex 1차 검토(head `85b66da0`) 반영: 관측하지 않은 안전성을 PASS로 만들 수 있던 판정 경계 5곳

| | 지적 | v1.1의 수정 |
|---|---|---|
| 1 | O3/O9의 승인 SQL이 제품의 승인 의미(run당 여러 approval 행, **최신 `approved`** + `expires_at > now` + `subject_sha256 = workload.spec_sha256`)를 재현하지 않아 reject·expired·digest-mismatch 행으로 **거짓 PASS**, 나중 행 때문에 **거짓 위반**이 가능했다 | O3의 SQL 계약을 `src/saintvision/services/runs.py:404 assert_approval_valid`와 **동일한 판정**으로 다시 적고 부정 fixture 5종을 고정했다(§2-1, T2). O9의 "승인 없는 시작"도 같은 계약을 쓴다. **v1.1.1(Codex 2차)**: C1은 **core DB(`public.approvals`·`run_attempts`) 판정**이고 recovery epoch은 **kernel의 별 계약**(`inv.approval_requests.recovery_epoch`·`bound_run_version`, `services/control-plane/src/inv/approvals.py::ApprovalStore`)이라 C1에서 epoch 주장을 **제거**했다 — 이 문서는 core 경계만 판정한다(§2-1 C1 경계) |
| 2 | O8의 두 시점 snapshot은 중간 UPDATE 후 복원·DELETE 후 재삽입을 놓친다 | O8을 **"순변화 없음 + 두 시점 권한 snapshot"** 으로 이름을 바꾸고 **done 증거에서 뺐다.** 창 전체의 불변은 중간 변경을 보존하는 독립 증거(DB 감사 로그·logical change feed)가 있어야 하고 그것은 코드에 없다 → 코드/인프라 선행 O8′(§3-1, T5) |
| 3 | O9의 "접근 로그 401/403 ↔ audit trace_id 1:1"에 입력 정본이 없다 — `src/saintvision/api/app.py:92-128`은 응답 trace와 denial audit만 만들고, 구성 앱은 `inv/app.py:1139 access_log=False` | O9를 **합성 요청 probe**(응답 `traceId`를 직접 캡처해 audit 1행과 대조)로 좁히고 "지금 가능"에서 **코드 선행**으로 옮겼다(probe 도구가 없다). 접근 로그 생산자는 별 결정이다 |
| 4 | O11이 보존 기간(D3 35일·D4 7일)을 RPO로 혼동했다 | **RPO·RTO는 운영자가 별도로 선언**(D6)하고, 실제 손실 구간은 drill JSON의 `operationalRpoBoundSeconds`·복구 cutoff·마지막 보존 WAL/backup 생성 시각으로 계산한다. 선언 전에는 측정값 기록·`BLOCKED_EXTERNAL`뿐이다 |
| 5 | O6의 "수동 SQL 기록"은 lock·idempotency·audit 경계를 우회하므로 합격 seam이 될 수 없다 | O6은 **감사되는 idempotent bounded operator command**가 생기기 전까지 **코드 선행**이고, 수동 SQL은 break-glass 관찰로만 기록하며 **done을 닫지 못한다**고 명시했다 |
| 관찰 | O4가 raw `Idempotency-Key`를 증거에 남길 수 있다; O2의 "정확히 1회"는 event type별 부수 효과가 다르다 | O4는 salted HMAC fingerprint 또는 단기 correlation id만 허용; O2는 **event type별 effect identity 등록**(E1)을 선행 조건으로 두었다 |

그 결과 §4의 분류가 바뀌었다: **지금 가능 2(O3·O7)**, 순변화 관측만 가능 1(O8), 우리 코드 선행 6(O1·O2·O4·O6·O9·O10 + O8′), 외부 전제 4(O5·O11·O12·O13). 관측 수 13은 그대로다.

## 0. 이 문서를 지배하는 규칙 하나

**코드가 이미 강제하는 것을 done 기준으로 다시 세지 않는다.** 카드 106과 같은 규칙이다.

두 task는 성질이 다르고, 그 차이가 이 문서의 결론이다.

| task | 코드의 상태 | 그래서 관측할 것 |
|---|---|---|
| **S04-DB** 재전송 | **안전장치가 전부 코드에 있다.** outbox는 Evidence·성공 전이와 한 transaction, inbox UNIQUE가 재전송을 무해하게 만들고, 발행 재시도 예산·승인 만료·취소 멱등·idempotency 원장·kernel의 receipt-hash 결속까지 시험이 지킨다 | **운영 환경에서 그 장치가 실제로 작동했다는 흔적** — 실 broker의 중복 배달, 실 Node의 전송 중단·재개, 원장 TTL 밖의 재요청 |
| **S08-DB** 보존 | **RLS·감사 불변은 코드에 있고, 보존은 코드가 *선언*만 했다.** partition 삭제 함수·artifact 90일·backup 35일·PITR 7일이 전부 있지만 **그것을 실행하는 주체가 없다**(§1-2) | 보존은 관측 이전에 **결정과 실행 주체**가 필요하다. 이 문서는 그 결정 항목을 사전 등록하고, 결정된 뒤 무엇을 보면 done인지 적는다 |

각 항목은 **관측값 · 계측 방법 · 사전 등록 임계치 · 증거 artefact · 외부 전제**를 갖는다. 임계치는 **결과를 보기 전에** 여기 고정한다.

## 1. 코드가 이미 강제하는 것 (다시 세지 않을 목록)

### 1-1. S04-DB — 허용 상태 전이·outbox·idempotency

| 이미 강제되는 불변식 | 출처 | 지키는 시험 |
|---|---|---|
| **outbox row는 Evidence INSERT·성공 전이와 한 transaction**이고(ADR-008), `event_id`는 republish에 걸쳐 불변이라 재전송이 "허용"이 아니라 "안전"이다 | `src/saintvision/db/models/evidence.py:1` docstring, `src/saintvision/services/evidence.py:102 enqueue_event` | `tests/test_execution.py` 25건 중 outbox 계열, `tests/integration/test_approvals.py` `test_audit_failure_rolls_back_nonce_vote_dispatch_and_outbox` |
| **재전송된 event는 inbox UNIQUE `(consumer, event_id)`가 거부**하고, 먼저 읽고 나중에 넣지 않는다(두 배달이 둘 다 통과하는 경로 차단) | `src/saintvision/db/models/evidence.py:144` `uq_inbox_events_consumer_event_id`, `src/saintvision/services/evidence.py:196 mark_processed` docstring | `tests/test_execution.py:524 test_a_redelivered_event_is_rejected_by_the_inbox` |
| **발행 실패는 예산(10회)까지 `pending`으로 재시도하고 그 뒤 `failed`로 주차**한다; claim은 `FOR UPDATE SKIP LOCKED` | `src/saintvision/services/evidence.py:166 mark_publish_failed`(`max_attempts=10`), `:140 claim_pending_events` | `tests/test_execution.py:590 test_publish_failures_retry_before_parking` |
| **core**: **만료된 승인은 거부**되고, 만료 시각이 과거인 승인은 기록조차 되지 않는다; 유효 승인은 **최신 `approved` + `expires_at > now` + `subject_sha256 == workload.spec_sha256`** 세 조건뿐이다(core `Approval`에는 recovery epoch·bound run version 열이 없다). 취소는 `start_attempt`의 state 전이 경계다 | `src/saintvision/services/runs.py:359 record_approval`(`expires_at <= now` 거부), `:404 assert_approval_valid`, `:155 start_attempt`, `src/saintvision/db/models/execution.py:347` CHECK `expiry_after_decision` | `tests/test_execution.py:494 test_an_expired_approval_is_refused`, `:345 test_cancel_is_idempotent` |
| **kernel(별 시스템)**: 복원된 recovery epoch·bound run version이 맞지 않는 승인은 dispatch되지 않는다 — `inv.approval_requests.recovery_epoch`·`bound_run_version`을 `ApprovalStore._current`/`dispatch`가 대조한다. **이 문서의 C1은 이 계약을 판정하지 않는다**(§2-1 C1 경계) | `services/control-plane/src/inv/approvals.py::ApprovalStore` | `tests/integration/test_approvals.py` `test_expired_nonce_does_not_consume_vote`·`test_cancelled_run_or_restored_epoch_invalidates_approval` |
| **취소는 멱등**이고 끝난 run의 취소는 거부된다; 재시도 예산이 강제된다 | `src/saintvision/services/runs.py:126 cancel_run` | `tests/test_execution.py:345 test_cancel_is_idempotent`, `:427 test_retry_budget_is_enforced` |
| **idempotency 원장**: 키에서 유도한 advisory lock으로 직렬화(IDEM-6), 같은 키·다른 digest는 거부, 저장 응답 replay; TTL 86,400초 | `src/saintvision/api/deps.py:81 serialise_idempotent_write`·`replay_or_reserve`·`:123 store_idempotent_response`, `src/saintvision/config.py:64 idempotency_ttl_seconds` | `tests/test_execution.py` `test_the_same_idempotency_key_in_two_projects_is_two_operations`, route별 replay 시험 |
| **replay 분기 12개가 구조로 고정**된다 — 재채점이 S04-DB의 결속으로 든 것 | `tools/check_contract_bindings.py:63 REPLAY_GUARD_COUNTS`(12) | `check_contract_bindings.py` 게이트 |
| **kernel의 process output은 receipt에 결속**되고 크기·sha256이 맞지 않으면 거부되며, crash 뒤 재개는 publication 3종에 한정된다 | `services/control-plane/src/inv/output_ingestion.py:1` docstring·`output_bytes` | `tests/integration/test_output_ingestion.py` 5건(실제 stdout/stderr 바이트 SHA-256 일치, receipt 이후 재시작 재개, 재실행 0 — Codex owner 판정 2026-09-22 기록), `tests/integration/test_node_delivery.py` 14건(`test_network_timeout_cancels_work_but_does_not_release_without_receipt`, `test_mtls_receipt_outbox_failure_can_be_recovered_without_execution`) |

**이 목록이 곧 "왜 S04-DB가 75점인가"의 절반이다.** AC-04의 세 문장 — 승인 전 실행 0, 중복 요청 부수 효과 0, 전송 재개 hash 일치 — 는 전부 코드와 격리 시험이 이미 말한다. 남은 절반은 **그것이 운영 환경에서 실제로 일어났다는 흔적**이다(§2).

### 1-2. S08-DB — RLS·감사 immutable·보존

| 이미 강제되는 불변식 | 출처 | 지키는 시험 |
|---|---|---|
| **RLS는 scope 미설정에서 fail-closed**다 — `NULLIF(current_setting('inv.tenant_id', true), '')::uuid`가 NULL이면 어떤 행도 맞지 않는다 | `src/saintvision/db/rls.py:11`·`:28` | `tests/test_migrations.py` `test_every_tenant_scoped_table_is_policed`, `tests/test_database.py` |
| **`audit_events`는 app role이 INSERT만 갖고 SELECT·UPDATE·DELETE가 없으며** 읽기는 `inv_audit_reader`뿐이다 | `migrations/versions/0047_audit_events_isolation.py:108-110`(`REVOKE SELECT ON audit_events FROM inv_app`, reader/writer 분리), `src/saintvision/db/models/__init__.py:257 AUDIT_TABLES` | `tests/test_migrations.py` `test_audit_tables_are_policed_and_unreadable_by_the_application`·`test_append_only_tables_are_never_granted_update_or_delete` |
| **정본 401/403은 공유 핸들러 경계에서 정확히 1행**으로 기록되고, action은 식별자 없는 template이다 | `src/saintvision/api/problem.py` `install_canonical_problem_handler` | `tests/core/test_canonical_denial_audit.py` 14건, `tests/core/test_audit_action.py` 16건 |
| **SECURITY DEFINER 함수는 검토된 policy와 정의·grant·revision이 정확히 일치**해야 하고, 벗어나면 fail-closed | `tools/definer-policy.json`, `tools/check_definer_functions.py` | `tests/integration/test_definer_audit.py` 8건 |
| **partition은 3개월 앞서 만들어지고 최소치 아래면 기동을 거부**한다; 삭제 job은 생성 job과 별 transaction이어야 한다 | `src/saintvision/db/partitions.py:56 ensure_partitions`·`:117 assert_partitions_available`, `src/saintvision/config.py:53 partition_lead_months`·`:55 partition_minimum_months` | `tests/test_migrations.py` partition 순서 시험, `tests/test_database.py` |
| **backup은 checksum 없이 verified가 될 수 없고**, drill은 측정값·checksum·(DB drill이면) fencing 확인 없이 pass가 될 수 없다 | `src/saintvision/db/models/operations_pilot.py:72` CHECK `verified_requires_checksum`, `src/saintvision/services/pilot.py:83 record_backup`·`:119 verify_backup`·`:142 record_recovery_drill` | `tests/test_pilot.py` 31건(`test_a_passing_drill_needs_checksum_verification` 등), `tests/integration/test_recovery_drill.py` 13건 |
| **PITR archive retention planner는 최신 backup을 항상 보존**하고, backup이 없으면 아무것도 삭제 후보가 아니다; dry-run은 절대 변경하지 않는다 | `tools/pitr_archive_retention.py:1` docstring(7일, 결정 2026-09-22), `tools/pitr_opt_in_dry_run.py` | `tests/test_pitr_archive_retention.py` 21건, `tests/test_pitr_opt_in_dry_run.py` 6건 |
| **보존 pin은 늘리기만** 한다 | `src/saintvision/services/storage.py:218 pin_retention` | `tests/test_storage_catalog.py` |

**보존에서 코드가 하지 않는 것 — 이것이 S08-DB의 나머지 절반이다.** 전부 `96a03486`에서 `git grep -n`으로 확인했다.

| 선언된 보존 | 실행 주체 | 확인 |
|---|---|---|
| partitioned 3 table(`resource_snapshots`·`audit_events`·`evidence_envelopes`)의 월 partition 삭제 `drop_expired_partitions(retention_months=…)` | **없다.** 정의(`src/saintvision/db/partitions.py:135`) 외에 `src`·`tools`·`tests`·workflow 어디에도 호출자가 없고 `retention_months` 값도 어디에도 없다 | `git grep -n drop_expired_partitions` → 정의 1건, `git grep -n retention_months` → `partitions.py`뿐 |
| artifact **90일** 수명(Evidence가 참조하면 pin으로 연장) | **없다.** docstring(`src/saintvision/db/models/artifacts.py:11`·`:88`)과 index뿐, GC 코드 없음 | `git grep -n -i lifetime\|expire -- services/artifacts.py` → 0건 |
| orphan context snapshot 수거 `collect_orphan_snapshots` | **없다.** 정의(`src/saintvision/services/context.py:290`)와 시험(`tests/test_context_eval.py:308`)뿐, 제품 호출자 없음 | `git grep -n collect_orphan_snapshots` |
| backup record **35일** `retention_until` | **없다.** 기본값(`src/saintvision/services/pilot.py:92`)과 조회 필터(`:529`·`:539`)뿐, 만료 backup을 지우거나 보고하는 것 없음 | 같은 파일 |
| PITR WAL/base backup **7일** | 계획 도구는 있으나 **Tier-A가 유예(결정 B)**라 archive 자체가 없다 | `docs/vault/40_Governance/S08-DB_PITR_opt-in_dry-run과_AC-12_복구드릴_초안.md` §1, `docs/vault/30_Development/Evidence/s08-pitr-opt-in/2026-09-23_dev-pg-dry-run.json`(`decision: tier-a-deferred`, `retentionApplied: false`) |
| outbox `failed` 행(예산 소진)의 재개·처분 | **없다.** `claim_pending_events`의 호출자가 제품에 없어(`git grep -l claim_pending_events -- src tools` → `src/saintvision/services/evidence.py`뿐) **publisher worker 자체가 코드에 없다**; 주차된 행을 다시 `pending`으로 돌리는 도구도 없다 | S04-DB §2 O1·O6의 전제 |

즉 **"보존 정책"은 지금 코드에 네 개의 숫자(90일·35일·7일·`retention_months` 미정)로 흩어져 있고 하나도 실행되지 않는다.** 이것은 결함이 아니라 결정 부재다 — 삭제 주체·주기·대상은 제품 결정(`G-20`·`G-21`·`G-22`)이고, 코드는 그 결정 없이 지우지 않는 쪽을 택했다. 그래서 S08-DB 보존의 done 기준은 **관측 앞에 결정 항목(§3-0)이 온다.**

## 2. S04-DB — 재전송·중복 요청의 운영 판정

### 2-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O1** | **outbox가 실제로 흐른다** — 창 동안 `outbox_events`의 `pending` 최대 나이와 `failed` 행 수 | 창 종료 시점 SQL: `status`, `created_at`, `publish_attempts`, `last_error` 집계(payload는 읽지 않음) | 창 종료 시 **10분보다 오래된 `pending` 0건**, **`failed` 0건**(있으면 각 행에 처분 기록 — O6). 그리고 `published` **≥ 100건**(흐름이 있었다는 분모) |
| **O2** | **실 broker의 중복 배달이 실제로 일어났고 부수 효과가 0이었다** — inbox UNIQUE 충돌로 무시된 배달 수와, 그 event의 aggregate에 남은 효과 수 | consumer 로그의 "already handled" 카운트 + `inbox_events`에서 `(consumer, event_id)`당 행 수 + 그 event가 만든 부수 효과를 **event type별로 사전 등록한 effect identity(E1)** 기준으로 카운트 — 예: `inv.run.completed` → (evidence 1, run 전이 1, audit allow 1). E1이 없는 event type은 관측 대상에서 제외한다(그것이 "1회"의 정의가 없다는 뜻이다) | 중복 배달 **≥ 1**(0이면 "중복은 정상"이 검증되지 않은 것이다 — 장애 주입으로 만든다), `(consumer, event_id)`당 inbox 행 **정확히 1**, event type별 effect identity 각각 **정확히 1** |
| **O3** | **승인 전 실행 0 — out-of-band 포함.** 판정은 **제품의 승인 의미와 동일**해야 한다: `src/saintvision/services/runs.py:404 assert_approval_valid`는 run당 여러 `approvals` 행(`src/saintvision/db/models/execution.py:328`에는 `(tenant_id, approval_id)` unique뿐) 중 **`decision='approved'`이고 `decided_at`이 가장 늦은 행 하나**를 고르고, `expires_at > now`와 `subject_sha256 == workload.spec_sha256`를 함께 검사한다 — **그것이 core의 승인 의미 전부**다. **C1 경계**: C1은 core DB(`public.approvals`·`run_attempts`·`workloads`·`runs`)만 판정한다. kernel `inv.approval_requests`의 recovery epoch·bound run version 계약(§1-1 kernel 행)은 **별 collector C1-K의 몫이고 이 문서는 그것을 정의하지 않는다** — 전체 제품 경계의 승인 우회 0을 주장하려면 C1-K가 따로 필요하다는 것을 명시한다 | 전수 SQL(collector 계약 C1): 각 `run_attempts` 행에 대해 **그 attempt의 `started_at` 시점**을 `now`로 놓고 (a) 같은 run의 `approvals` 중 `decision='approved' AND decided_at <= started_at`인 행에서 `decided_at DESC` 1행을 고른다; (b) 그 행이 없으면 위반; (c) 있으면 `expires_at > started_at`이고 `subject_sha256 = workloads.spec_sha256`(run→workload join)이어야 하며, (d) 그 attempt 시작 이전에 그 run의 취소 audit 행(`audit_events`, `run.cancel` 계열 action)이 없어야 한다(§6 — `runs.state`는 현재값뿐이라 이력은 audit로 본다). epoch 조건은 **없다**. **모든 approval을 attempt와 join하거나 "approvals 행 없음"만 보는 SQL은 계약 위반이다** — reject·expired·digest-mismatch 행으로 거짓 PASS가, 나중 행으로 거짓 위반이 난다 | 위반 **0건**. 부정 fixture 5종(§5 T2)이 각각 위반으로 잡혀야 한다 |
| **O4** | **중복 요청이 실제 클라이언트에서 왔고 원장이 replay했다** — 같은 `Idempotency-Key`의 2회 이상 요청 수, 그중 저장 응답 replay 비율, 다른 digest로 온 것의 409 비율 | 요청 기록의 key별 요청 수 × `idempotency_records`의 `(tenant, endpoint, key)`당 행 수 × 응답 코드. **증거에 raw `Idempotency-Key`를 남기지 않는다** — salted HMAC fingerprint 또는 단기 correlation id만 허용(원장의 유도 키와 같은 원칙). 요청 기록 생산자는 O9와 같은 이유로 코드에 없다(§2-3) | 원장 행 **(tenant, endpoint, key)당 1**, 같은 digest 재요청의 replay **100%**, 다른 digest의 409 **100%**. **TTL(86,400초)을 넘긴 재요청**은 새 작업이 되므로 그 건수를 **별도로 기록**한다(0이 아니어도 위반이 아니지만, 그 값이 제품 결정의 입력이다) |
| **O5** | **전송 재개 hash 일치 — 실 Node에서** | 실 Node→CP 전송을 중단(네트워크 차단·process kill)했다가 재개한 run에서 receipt의 `sha256`·`sizeBytes`와 CP가 저장한 바이트의 digest 비교, 재실행 여부(`run_attempts` 수) | 재개 전송 **≥ 3건**, digest 불일치 **0**, 재실행 **0**(attempt 수가 늘지 않음) |
| **O6** | **주차된 outbox 행의 처분** — `failed`가 된 행이 창 안에서 어떻게 닫혔는가 | **감사되는 idempotent bounded operator command**(재발행은 같은 `event_id`로 `pending` 복귀 + audit 1행, 폐기는 근본 원인과 함께 audit 1행; lock-wait bound 안에서)로만 처분한다. 그 command는 코드에 없다(§1-2) | `failed` 행 **100%가 그 command의 audit 행으로 닫힘**. **수동 SQL 처분은 break-glass 관찰로만 기록하고 done을 닫지 못한다** — raw SQL은 lock·idempotency·audit 경계를 우회하므로 합격 seam이 아니다 |

### 2-2. 증거 artefact

`outbox_events`·`inbox_events`·`idempotency_records`의 집계 CSV(창 시작·종료 시각 포함, **payload·last_error 원문 제외** — broker 오류는 payload를 되풀이할 수 있어 `mark_publish_failed`가 500자로 자르는 것과 같은 이유), O2·O5의 장애 주입 절차·시각, O3의 전수 SQL 원문과 결과, O5의 receipt digest ↔ 저장 digest 대조표, O6 처분 대장.

### 2-3. 외부 전제

- **O1·O2·O4·O6은 publisher worker와 consumer가 배포돼야 시작된다** — 코드에 없으므로 **우리 몫의 선행 구현**이다(§1-2 마지막 행). O2는 event type별 effect identity 등록(E1), O4는 key fingerprint를 남기는 요청 기록 생산자(현재 `src/saintvision/api/app.py:92 _trace`는 응답 `traceparent`와 denial audit만 만들고 구성 앱은 `services/control-plane/src/inv/app.py:1139`에서 `access_log=False`), O6는 처분 command가 더 필요하다.
- **O3은 지금 측정 가능**하다(DB만 필요, C1 계약대로).
- **O5는 `G-24`**(실 5노드 Node→CP 전송)·**`G-19`**(물리 PC)에 걸린다. Codex owner 판정(2026-09-22)이 S04-DB의 done 차단으로 든 "물리 Node 전송 재개 인수"가 바로 이것이다.

## 3. S08-DB — RLS·감사 immutable·보존의 운영 판정

### 3-0. 관측 앞에 오는 결정 항목 (사전 등록)

보존은 값이 정해지지 않은 채로는 관측할 것이 없다. 다음을 **결정 문서에 적기 전에는 O10·O12·O13을 시작하지 않는다.**

| 결정 | 지금 코드가 말하는 값 | 결정 주체 |
|---|---|---|
| D1 partitioned 3 table의 `retention_months` | **미정**(어디에도 없음) | 운영 owner + `G-22`(PITR·RPO/RTO — 감사·evidence를 얼마나 되돌아봐야 하는가) |
| D2 artifact 수명과 GC 주기 | 90일(docstring) | storage owner, `G-20` |
| D3 backup 보존 | 35일(기본값) | `G-21`(off-site backup 선언) |
| D4 PITR archive 보존 | 7일(결정 2026-09-22, Tier-A 유예) | `G-22` |
| D5 삭제 job의 실행 주체·주기·실행 role(owner) | 없음 | 운영 owner. **app role은 DROP 권한이 없어야 한다**(현재 그렇다) |
| D6 **RPO·RTO 선언**(허용 데이터 손실·복구 시간) — **보존 기간(D3·D4)과 다른 값**이다 | 없음. `tools/recovery_drill.py:444 rpo_bound_from`은 설정만으로는 RPO 경계를 세우지 않고 `operationalRpoVerified=false`를 낸다 | 운영 owner, `G-22` |

### 3-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O7** | **운영 DB에서 RLS가 실제 행에 대해 닫혀 있다** | `tools/collect_rls_evidence.py`를 운영 catalogue·실 행에 대해 실행: role 속성, table별 권한·RLS flag·policy, scope 미설정/타 tenant/자기 tenant에서 보이는 행 수 | `inv_app`·`inv_kernel`의 **VIOLATIONS 0**, `has_tenant_id` table 전부에서 scope 미설정 **0행**, `bypassrls`·`superuser` **false** |
| **O8** | **감사 행의 순변화 없음 + 두 시점 권한 snapshot** — 이것은 **창 전체의 불변을 증명하지 못한다**(중간 UPDATE 후 복원, DELETE 후 같은 행 재삽입을 놓친다). 그래서 **done 증거로 세지 않고** 기록만 한다 | 창 시작·종료의 `audit_events` `(audit_id, 전 컬럼)` digest 비교 + 행 수 + app role 권한 snapshot(`information_schema.role_table_grants`) | 순변화 **0**, 권한 snapshot 두 시점 모두 **INSERT only** — 충족해도 O8′ 없이는 pass가 아니다 |
| **O8′** | **창 전체의 감사 불변** — 중간 변경을 보존하는 **독립 증거**: DB 감사 로그(예: `pgaudit`의 DDL/DML 기록) 또는 logical change feed에서 `audit_events`에 대한 UPDATE·DELETE·DROP 이벤트 수 | 그 feed는 코드·배포에 **없다**(`git grep -i pgaudit\|logical` → `BACKUP_KINDS`의 `logical` 문자열뿐) → **인프라 선행** | UPDATE·DELETE·DROP **0건**, feed 자체의 무결성(연속성·gap 0) 확인 |
| **O9** | **거부가 빠짐없이 기록된다 — 승인 우회 0의 DB 면.** 접근 로그는 입력 정본이 **없다**(`src/saintvision/api/app.py:92`는 응답 `traceparent`·denial audit만, 구성 앱 `inv/app.py:1139 access_log=False`) → 범위를 **합성 요청 probe**로 좁힌다 | 운영 probe가 무토큰·비회원·revoked 등 거부 case를 **자기 요청으로** 보내고 **응답 `traceId`를 직접 캡처**해 `audit_events`의 `outcome='deny'` 행과 trace_id로 1:1 대조. 승인 우회는 O3의 C1 계약(**최신 approved·기간·digest·취소 audit**, core DB 경계)으로 판정한다 — "approvals 행 없음"만 보지 않는다. kernel epoch 경계(C1-K)는 범위 밖이다 | probe 거부 case당 deny 행 **정확히 1**(trace_id 일치), 미대조 **0**; C1 위반 **0**. probe 도구는 코드에 없으므로 **코드 선행**. 접근 로그 생산자를 둘지는 별 결정이다 |
| **O10** | **보존 삭제가 계획대로만 일어났다** (D1·D5 뒤) | 삭제 job 실행 전 `drop_expired_partitions`의 계획(cutoff·대상 partition 목록)을 기록하고 실행 후 catalogue와 대조; 남은 가장 오래된 partition의 월 | 계획 = 실제 **정확히 일치**, cutoff 이후 partition 삭제 **0**, 삭제 후에도 `assert_partitions_available` 통과, Evidence·audit 행 중 창 안에서 참조된 것의 손실 **0** |
| **O11** | **backup 복원이 실제 backup으로 성공하고, 실제 손실 구간이 선언한 RPO 안이다** | `tools/recovery_drill.py --json`을 **운영 backup**에 대해 격리 cluster에서 실행: 9 evidence table digest 일치, 소유권·grant·RLS, restricted role probe. **손실 구간**은 보존 기간이 아니라 **복구된 cutoff(복원 시점에 되살아난 마지막 시각)와 원본의 마지막 commit 사이**로 계산한다 — 입력은 drill JSON의 `operationalRpoBoundSeconds`(`recovery_drill.py:597`)·backup `taken_at`·마지막 보존 WAL 시각. RTO는 복원 시작부터 전 검사 종료까지(`recovery_drill.py:7`) | exit **0**, digest 불일치 **0**, **손실 구간 ≤ D6의 RPO**, RTO ≤ **D6의 RTO**. **D6 선언 전에는 pass가 아니라 측정값 기록·`BLOCKED_EXTERNAL`**이다 — `tests/integration/test_recovery_drill.py:425 test_cli_and_database_record_refuse_unverified_operational_target`이 지키는 규칙과 같다. D3(35일)·D4(7일)는 **보존 기간이지 RPO가 아니다** |
| **O12** | **PITR이 실제로 복구한다** (D4·Tier-A 활성 뒤) | `tools/pitr_readiness.py` `possible` → 외부 `wal_archive` 3단계 → 목표 시각 복구 드릴(초안 §4) | `pitrVerified` **true**, `ac12Satisfied` **true**, off-device 장애 도메인 **충족** |
| **O13** | **보존 삭제가 pin을 존중한다** (D2·GC 뒤) | GC 1주기 뒤 `retention_pinned_until > now`인 artifact·data_location의 존재·digest | 손실 **0**, digest 불일치 **0** |

### 3-2. 증거 artefact

`collect_rls_evidence.py` JSON(운영 DSN은 넣지 않는다), 두 시점의 `audit_events` digest·권한 snapshot, 401/403 ↔ deny 대조표(trace_id만), 삭제 job의 계획·실행 로그와 catalogue 전후, `recovery_drill.py --json` 원문, PITR 드릴 JSON. **DSN·token·원문 hostname·backup 파일 자체는 넣지 않는다.**

### 3-3. 외부 전제

- **O7은 지금 측정 가능**하다(운영 DB만 필요). **O8은 지금 기록할 수 있으나 done 증거가 아니다**; O8′는 DB 감사 로그/change feed **인프라 선행**이다.
- **O9는 probe 도구(코드 선행)**가 먼저다. **O10은 D1·D5 결정 + 삭제 job 구현**(우리 몫)이 먼저다.
- **O11은 `G-21`**(실 backup)과 **D6**(RPO·RTO 선언)에, **O12는 `G-22`**(Tier-A 활성·off-device)에, **O13은 `G-20`**(storage 제품 값·GC)에 걸린다. Codex owner 판정(2026-09-22)이 S08-DB done 차단으로 든 "off-device/PITR·보존 기간·독립 역할 복원"이 O11·O12·O10이고, "GPU workload 성공·승인 우회 0의 종단 인수"는 S08-BE/ST 면이라 여기서는 O9의 DB 면만 다룬다.

## 4. 지금 할 수 있는 것과 기다려야 하는 것

13개 관측 중 **지금 측정 가능한 것 2개, 기록만 가능한 것 1개, 우리 코드·인프라가 먼저 필요한 것 6개(+O8′), 외부 전제 4개**다.

| 지금 가능 (2) | 기록만 (1) | 우리 코드·인프라 선행 (6 + O8′) | 외부 전제 대기 (4) |
|---|---|---|---|
| O3 승인 전 실행 0 (C1 계약 전수 SQL) | O8 순변화 + 권한 snapshot (done 증거 아님) | O1·O2·O4·O6 — **publisher/consumer worker, E1 effect identity, key fingerprint 요청 기록, 감사되는 처분 command** | O5 실 Node 전송 재개 (`G-24`·`G-19`) |
| O7 RLS 실 행 | | O9 — **거부 probe 도구**(응답 traceId ↔ deny 행) | O11 실 backup 복원 + D6 RPO/RTO (`G-21`) |
| | | O10 — **D1·D5 결정 + partition 삭제 job** | O12 PITR 복구 (`G-22`) |
| | | O8′ — **DB 감사 로그/change feed**(인프라) | O13 pin ↔ GC (`G-20`) |

즉 **두 task의 75 → 100 사이에서 우리 몫은 2개 관측의 실행·기록과 7개의 선행 구현·결정·인프라**이고, 4개는 `G-19`·`G-20`·`G-21`·`G-22`·`G-24` 중 하나가 풀려야 시작된다. 다 채워도 **100은 되지 않는다** — 필수 운영 인수가 범위 안에 있기 때문이고, 그 사실을 숨기지 않는다.

**재채점(PR #220) §5는 이 문서를 Codex 몫으로 적었다.** 카드 108로 Claude에게 배정됐으므로 여기서 쓰되, **결정 항목 D1~D5와 선행 구현 5개의 owner는 이 문서가 정하지 않는다** — task-registry의 S04-DB·S08-DB owner는 Codex(reviewer Claude)다.

## 5. 되돌리면 실패해야 하는 시험 (관측을 정직하게 유지하는 장치)

관측 자체가 거짓이 되는 경로를 막는다. 구현 카드가 이 목록을 계약으로 받는다.

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 |
|---|---|---|
| T1 | O2의 "중복 배달 ≥ 1"이 **실제 배달**에서 온다 | consumer를 두 번 부르는 시험 stub으로 대체하면 실패 — broker의 재배달 로그 또는 장애 주입 기록이 분모다 |
| T2 | O3/O9의 collector가 **C1 계약**(attempt 시점 기준 최신 `approved`·`expires_at > started_at`·`subject_sha256 = spec_sha256`·취소 audit; **core DB만, epoch 없음**)을 그대로 구현한다 | 부정 fixture 5종이 각각 **위반으로 잡혀야** 한다: (a) `rejected` 행만 있는 run의 attempt, (b) `approved`지만 `expires_at < started_at`, (c) `approved`지만 `subject_sha256 ≠ spec_sha256`, (d) 취소 audit 행이 attempt 시작보다 앞선 run의 attempt, (e) 정당한 `approved` 뒤에 **더 늦은 `rejected` 행**이 추가된 run의 attempt는 **위반이 아니어야** 한다(거짓 위반 방지). 모든 approval을 attempt와 단순 join하거나 "approvals 행 없음"만 보면 (a)~(c) 중 하나가 pass하거나 (e)가 위반이 되어 실패한다. 그리고 코드 경로만 시험하면 실패 — 직접 SQL로 `started_at`을 앞당긴 뒤 관측이 그것을 드러내야 한다. **epoch 변이 fixture는 T2에 없다** — 그것은 C1-K의 시험이고, C1에 epoch 검사를 넣는 변이는 "core `approvals`에 없는 열을 읽는다"로 실패해야 한다 |
| T3 | O4의 원장 카운트가 **접근 로그와 독립 경로**다 | 원장만 세면 실패 — 로그의 요청 수가 없으면 "replay 100%"의 분모가 없다 |
| T4 | O5의 digest가 **receipt와 저장 바이트 양쪽**에서 온다 | receipt의 sha256만 비교하면 실패. `output_bytes`가 하는 것과 같은 3자(receipt·저장·attempt 수) 비교여야 한다 |
| T5 | O8의 권한 snapshot이 **`information_schema`에서** 오고, O8이 **done 증거로 집계되지 않는다** | 하드코딩 "INSERT only"면 실패 — app role에 UPDATE를 주면 snapshot 비교가 깨져야 한다. 그리고 O8만으로 S08-DB 감사 항목이 pass로 집계되면 실패: **UPDATE 후 원복**·**DELETE 후 같은 행 재삽입**을 창 중간에 넣은 fixture에서 O8은 "순변화 0"이 되므로, pass는 O8′의 feed가 그 두 이벤트를 잡을 때만이어야 한다 |
| T6 | O9의 1:1 대조가 **probe가 캡처한 응답 traceId 기준**이다 | 건수만 비교하면 실패 — 같은 수의 다른 거부는 일치가 아니다. 접근 로그를 분모로 쓰면 실패 — 그 로그는 생산자가 없다(`access_log=False`) |
| T7 | O10의 삭제 job이 **계획을 먼저 기록**하고 실행한다 | 계획 없이 실행 후 catalogue만 보면 실패. 그리고 `ensure_partitions`와 **같은 transaction이면 실패**(`partitions.py:15` docstring이 정한 분리) |
| T8 | O11이 **운영 backup**에 대해 돌고, 손실 구간을 **보존 기간이 아니라 복구 cutoff에서** 계산한다 | 시험 fixture backup으로 대체하면 실패 — hosted `test_recovery_drill`이 1 passed·19 environment skip인 상태를 "복원 성공"으로 세는 것이 바로 이 경로다. `RPO ≤ 35일`처럼 D3/D4 값을 RPO로 쓰면 실패; D6 미선언에서 pass가 나오면 실패(`operationalRpoVerified=false`가 pass를 막아야 한다) |
| T9 | O6의 처분이 **감사되는 command**를 거친다 | `failed` 행을 raw `UPDATE`로 `pending`으로 되돌린 fixture는 audit 행이 없으므로 "처분됨"으로 집계되면 실패 — break-glass 관찰로만 남아야 한다 |
| T10 | O4의 증거에 **raw `Idempotency-Key`가 없다** | 증거 파일에서 요청 header 원문이 발견되면 실패; fingerprint는 salt 없이 재계산되지 않아야 한다 |
| T11 | O2의 "정확히 1회"가 **E1의 event type별 effect identity**로 센다 | 등록되지 않은 event type을 "효과 0 = 정상"으로 집계하면 실패 — 미등록은 관측 제외다 |

## 6. 경계 · 미해결

- **임계치의 분모(O1 published ≥ 100, O5 재개 ≥ 3)는 이 문서가 처음 고정한 값**이다. 운영 데이터량을 본 뒤 올릴 수는 있으나, **결과를 보고 내리는 것은 금지**한다.
- **O4의 TTL 밖 재요청 건수는 임계치가 없다.** 그 값은 idempotency TTL(86,400초)이 제품에 맞는지의 입력이고, 결정은 별 카드다.
- **접근 로그 생산자를 둘지는 이 문서가 정하지 않는다.** O4·O9는 그것 없이 probe·fingerprint로 성립하도록 좁혔다. 두면 무엇을 남기고 무엇을 남기지 않는지(header 원문 금지)가 먼저다.
- **O8′의 DB 감사 로그/change feed는 인프라 결정**이다(pgaudit·logical replication slot 등). 어느 쪽이든 그 feed의 무결성(gap 0)이 O8′의 전제다.
- **C1의 취소 조건은 `runs.state`의 이력이 필요하다.** `runs`는 현재 상태만 갖고 전이 이력은 `audit_events`·evidence에 있으므로, C1 구현은 attempt 시작 시각과 취소 audit 행의 시각을 비교한다. 이력이 없는 run은 판정 불가로 기록하고 pass로 세지 않는다.
- **C1은 core 경계만이다(Codex 2차).** kernel `inv.approval_requests`의 recovery epoch·bound run version·dispatch/execution 기록 대조(C1-K)와 stale epoch 부정 fixture는 **이 문서가 정의하지 않는다.** 전체 제품 경계의 "승인 우회 0"은 C1 + C1-K 둘 다 있어야 하고, C1-K는 kernel owner의 별 카드다.
- **D1~D5는 이 문서가 정하지 않는다.** 코드가 지금 가진 숫자를 적었을 뿐이고, 그 숫자를 결정으로 승격하는 것은 owner의 일이다.
- **publisher worker·삭제 job이 코드에 없다는 사실은 이 문서가 처음 한 곳에 모아 적은 것**이지만 새 발견은 아니다 — orphan 수거자 부재는 Claude 작업 현황 v1.2.x의 CL-04 메모가 이미 적었다. 다만 `drop_expired_partitions`의 호출자 부재는 그 메모에 없다.
- **이 문서는 판정을 내리지 않는다.** 두 task의 현재 점수는 재채점(PR #220) v1.2의 **75**이고, registry status는 `review`(Codex owner 판정 2026-09-22)다. 이 문서는 그 75를 올리는 데 **무엇이 필요한지**만 정한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite·어떤 도구의 운영 실행. 이 문서의 실측은 `git show`·`git grep -n`으로 읽은 코드뿐이고, **관측은 하나도 수행하지 않았다.**
