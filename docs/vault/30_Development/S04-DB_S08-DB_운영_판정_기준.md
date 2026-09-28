---
doc_id: "CLAUDE-DONE-CRITERIA-S04DB-S08DB-001"
title: "S04-DB·S08-DB 운영 판정 기준 — 재전송은 코드가 이미 안전하게 만들었고 보존은 코드가 선언만 했다: 코드가 보장할 수 없는 것만 관측·계측·사전 등록 임계치로 고정한다 (카드 108, docs-only)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T23:34:27+09:00"
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
| **재전송된 event는 inbox UNIQUE `(consumer, event_id)`가 거부**하고, 먼저 읽고 나중에 넣지 않는다(두 배달이 둘 다 통과하는 경로 차단) | `db/models/evidence.py:144` `uq_inbox_events_consumer_event_id`, `services/evidence.py:196 mark_processed` docstring | `tests/test_execution.py:524 test_a_redelivered_event_is_rejected_by_the_inbox` |
| **발행 실패는 예산(10회)까지 `pending`으로 재시도하고 그 뒤 `failed`로 주차**한다; claim은 `FOR UPDATE SKIP LOCKED` | `services/evidence.py:166 mark_publish_failed`(`max_attempts=10`), `:140 claim_pending_events` | `tests/test_execution.py:590 test_publish_failures_retry_before_parking` |
| **만료된 승인은 거부**되고, 만료 시각이 과거인 승인은 기록조차 되지 않으며, 취소된 run·복원된 epoch은 승인을 무효화한다 | `services/runs.py:359 record_approval`(`expires_at <= now` 거부), `:404 assert_approval_valid`, `db/models/execution.py:347` CHECK `expiry_after_decision` | `tests/test_execution.py:494 test_an_expired_approval_is_refused`, `tests/integration/test_approvals.py` `test_expired_nonce_does_not_consume_vote`·`test_cancelled_run_or_restored_epoch_invalidates_approval` |
| **취소는 멱등**이고 끝난 run의 취소는 거부된다; 재시도 예산이 강제된다 | `services/runs.py:126 cancel_run` | `tests/test_execution.py:345 test_cancel_is_idempotent`, `:427 test_retry_budget_is_enforced` |
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
| partitioned 3 table(`resource_snapshots`·`audit_events`·`evidence_envelopes`)의 월 partition 삭제 `drop_expired_partitions(retention_months=…)` | **없다.** 정의(`db/partitions.py:135`) 외에 `src`·`tools`·`tests`·workflow 어디에도 호출자가 없고 `retention_months` 값도 어디에도 없다 | `git grep -n drop_expired_partitions` → 정의 1건, `git grep -n retention_months` → `partitions.py`뿐 |
| artifact **90일** 수명(Evidence가 참조하면 pin으로 연장) | **없다.** docstring(`db/models/artifacts.py:11`·`:88`)과 index뿐, GC 코드 없음 | `git grep -n -i lifetime\|expire -- services/artifacts.py` → 0건 |
| orphan context snapshot 수거 `collect_orphan_snapshots` | **없다.** 정의(`services/context.py:290`)와 시험(`tests/test_context_eval.py:308`)뿐, 제품 호출자 없음 | `git grep -n collect_orphan_snapshots` |
| backup record **35일** `retention_until` | **없다.** 기본값(`services/pilot.py:92`)과 조회 필터(`:529`·`:539`)뿐, 만료 backup을 지우거나 보고하는 것 없음 | 같은 파일 |
| PITR WAL/base backup **7일** | 계획 도구는 있으나 **Tier-A가 유예(결정 B)**라 archive 자체가 없다 | `docs/vault/40_Governance/S08-DB_PITR_opt-in_dry-run과_AC-12_복구드릴_초안.md` §1, `docs/vault/30_Development/Evidence/s08-pitr-opt-in/2026-09-23_dev-pg-dry-run.json`(`decision: tier-a-deferred`, `retentionApplied: false`) |
| outbox `failed` 행(예산 소진)의 재개·처분 | **없다.** `claim_pending_events`의 호출자가 제품에 없어(`git grep -l claim_pending_events -- src tools` → `services/evidence.py`뿐) **publisher worker 자체가 코드에 없다**; 주차된 행을 다시 `pending`으로 돌리는 도구도 없다 | S04-DB §2 O1·O6의 전제 |

즉 **"보존 정책"은 지금 코드에 네 개의 숫자(90일·35일·7일·`retention_months` 미정)로 흩어져 있고 하나도 실행되지 않는다.** 이것은 결함이 아니라 결정 부재다 — 삭제 주체·주기·대상은 제품 결정(`G-20`·`G-21`·`G-22`)이고, 코드는 그 결정 없이 지우지 않는 쪽을 택했다. 그래서 S08-DB 보존의 done 기준은 **관측 앞에 결정 항목(§3-0)이 온다.**

## 2. S04-DB — 재전송·중복 요청의 운영 판정

### 2-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O1** | **outbox가 실제로 흐른다** — 창 동안 `outbox_events`의 `pending` 최대 나이와 `failed` 행 수 | 창 종료 시점 SQL: `status`, `created_at`, `publish_attempts`, `last_error` 집계(payload는 읽지 않음) | 창 종료 시 **10분보다 오래된 `pending` 0건**, **`failed` 0건**(있으면 각 행에 처분 기록 — O6). 그리고 `published` **≥ 100건**(흐름이 있었다는 분모) |
| **O2** | **실 broker의 중복 배달이 실제로 일어났고 부수 효과가 0이었다** — inbox UNIQUE 충돌로 무시된 배달 수와, 그 event의 aggregate에 남은 효과 수 | consumer 로그의 "already handled" 카운트 + `inbox_events`에서 `(consumer, event_id)`당 행 수 + 그 event가 만든 부수 효과(evidence·전이·audit)를 aggregate 기준으로 카운트 | 중복 배달 **≥ 1**(0이면 "중복은 정상"이 검증되지 않은 것이다 — 장애 주입으로 만든다), `(consumer, event_id)`당 inbox 행 **정확히 1**, 부수 효과 **정확히 1** |
| **O3** | **승인 전 실행 0 — out-of-band 포함** | 전수 SQL: `run_attempts.started_at < approvals.decided_at`인 (run, attempt) 쌍, 그리고 `approvals.expires_at < run_attempts.started_at`로 만료 승인 위에서 시작한 attempt | 둘 다 **0건**. 코드는 막지만 직접 SQL·수동 조작은 여기서만 보인다 |
| **O4** | **중복 요청이 실제 클라이언트에서 왔고 원장이 replay했다** — 같은 `Idempotency-Key`의 2회 이상 요청 수, 그중 저장 응답 replay 비율, 다른 digest로 온 것의 409 비율 | 접근 로그의 `Idempotency-Key`별 요청 수 × `idempotency_records`의 `(tenant, endpoint, key)`당 행 수 × 응답 코드 | 원장 행 **(tenant, endpoint, key)당 1**, 같은 digest 재요청의 replay **100%**, 다른 digest의 409 **100%**. **TTL(86,400초)을 넘긴 재요청**은 새 작업이 되므로 그 건수를 **별도로 기록**한다(0이 아니어도 위반이 아니지만, 그 값이 제품 결정의 입력이다) |
| **O5** | **전송 재개 hash 일치 — 실 Node에서** | 실 Node→CP 전송을 중단(네트워크 차단·process kill)했다가 재개한 run에서 receipt의 `sha256`·`sizeBytes`와 CP가 저장한 바이트의 digest 비교, 재실행 여부(`run_attempts` 수) | 재개 전송 **≥ 3건**, digest 불일치 **0**, 재실행 **0**(attempt 수가 늘지 않음) |
| **O6** | **주차된 outbox 행의 처분** — `failed`가 된 행이 창 안에서 어떻게 닫혔는가 | 각 `failed` 행에 대해 운영자 처분(재발행·폐기·근본 원인)을 기록 | `failed` 행 **100% 처분 기록**. 처분 도구가 없다는 것 자체가 §1-2의 사실이므로, O6의 첫 관측은 "처분 절차 문서 + 수동 SQL 기록"으로 시작한다 |

### 2-2. 증거 artefact

`outbox_events`·`inbox_events`·`idempotency_records`의 집계 CSV(창 시작·종료 시각 포함, **payload·last_error 원문 제외** — broker 오류는 payload를 되풀이할 수 있어 `mark_publish_failed`가 500자로 자르는 것과 같은 이유), O2·O5의 장애 주입 절차·시각, O3의 전수 SQL 원문과 결과, O5의 receipt digest ↔ 저장 digest 대조표, O6 처분 대장.

### 2-3. 외부 전제

- **O1·O2·O4·O6은 publisher worker와 consumer가 배포돼야 시작된다** — 코드에 없으므로 **우리 몫의 선행 구현**이다(§1-2 마지막 행). 그것이 있으면 나머지는 실 PG·실 broker만으로 측정 가능하다.
- **O3은 지금 측정 가능**하다(DB만 필요).
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

### 3-1. 관측 항목

| # | 관측값 | 계측 방법 | 사전 등록 임계치 |
|---|---|---|---|
| **O7** | **운영 DB에서 RLS가 실제 행에 대해 닫혀 있다** | `tools/collect_rls_evidence.py`를 운영 catalogue·실 행에 대해 실행: role 속성, table별 권한·RLS flag·policy, scope 미설정/타 tenant/자기 tenant에서 보이는 행 수 | `inv_app`·`inv_kernel`의 **VIOLATIONS 0**, `has_tenant_id` table 전부에서 scope 미설정 **0행**, `bypassrls`·`superuser` **false** |
| **O8** | **감사 행이 out-of-band로 바뀌지 않았다** | 창 시작·종료의 `audit_events` `(audit_id, 전 컬럼)` digest 비교 + 행 수 단조 증가 + app role 권한 snapshot(`information_schema.role_table_grants`: INSERT만) | 변경 **0건**, 삭제 **0건**, 권한 snapshot 두 시점 모두 **INSERT only** |
| **O9** | **거부가 빠짐없이 기록된다 — 승인 우회 0의 DB 면** | 접근 로그의 401/403 응답 수 ↔ `audit_events`의 `outcome='deny'` 행 수(trace_id로 1:1 대조). 그리고 승인이 필요한 run 중 `approvals` 행 없이 시작한 것 | 미대조 **0**, 승인 없는 시작 **0** |
| **O10** | **보존 삭제가 계획대로만 일어났다** (D1·D5 뒤) | 삭제 job 실행 전 `drop_expired_partitions`의 계획(cutoff·대상 partition 목록)을 기록하고 실행 후 catalogue와 대조; 남은 가장 오래된 partition의 월 | 계획 = 실제 **정확히 일치**, cutoff 이후 partition 삭제 **0**, 삭제 후에도 `assert_partitions_available` 통과, Evidence·audit 행 중 창 안에서 참조된 것의 손실 **0** |
| **O11** | **backup 복원이 실제 backup으로 성공한다** | `tools/recovery_drill.py --json`을 **운영 backup**에 대해 격리 cluster에서 실행: 9 evidence table digest 일치, 소유권·grant·RLS, restricted role probe, RPO(backup 나이)·RTO | exit **0**, digest 불일치 **0**, RPO ≤ **D3/D4가 정한 값**, RTO ≤ **선언값**. 선언값이 없으면 이 관측은 pass가 아니라 **측정값 기록**으로 끝난다 — `tests/integration/test_recovery_drill.py` `test_cli_and_database_record_refuse_unverified_operational_target`이 지키는 규칙과 같다 |
| **O12** | **PITR이 실제로 복구한다** (D4·Tier-A 활성 뒤) | `tools/pitr_readiness.py` `possible` → 외부 `wal_archive` 3단계 → 목표 시각 복구 드릴(초안 §4) | `pitrVerified` **true**, `ac12Satisfied` **true**, off-device 장애 도메인 **충족** |
| **O13** | **보존 삭제가 pin을 존중한다** (D2·GC 뒤) | GC 1주기 뒤 `retention_pinned_until > now`인 artifact·data_location의 존재·digest | 손실 **0**, digest 불일치 **0** |

### 3-2. 증거 artefact

`collect_rls_evidence.py` JSON(운영 DSN은 넣지 않는다), 두 시점의 `audit_events` digest·권한 snapshot, 401/403 ↔ deny 대조표(trace_id만), 삭제 job의 계획·실행 로그와 catalogue 전후, `recovery_drill.py --json` 원문, PITR 드릴 JSON. **DSN·token·원문 hostname·backup 파일 자체는 넣지 않는다.**

### 3-3. 외부 전제

- **O7·O8·O9는 지금 측정 가능**하다(운영 DB와 접근 로그만 필요).
- **O10은 D1·D5 결정 + 삭제 job 구현**(우리 몫)이 먼저다.
- **O11은 `G-21`**(실 backup)에, **O12는 `G-22`**(Tier-A 활성·off-device)에, **O13은 `G-20`**(storage 제품 값·GC)에 걸린다. Codex owner 판정(2026-09-22)이 S08-DB done 차단으로 든 "off-device/PITR·보존 기간·독립 역할 복원"이 O11·O12·O10이고, "GPU workload 성공·승인 우회 0의 종단 인수"는 S08-BE/ST 면이라 여기서는 O9의 DB 면만 다룬다.

## 4. 지금 할 수 있는 것과 기다려야 하는 것

13개 관측 중 **지금 측정 가능한 것 4개, 우리 코드가 먼저 필요한 것 5개, 외부 전제 4개**다.

| 지금 가능 (4) | 우리 코드 선행 (5) | 외부 전제 대기 (4) |
|---|---|---|
| O3 승인 전 실행 0 (전수 SQL) | O1·O2·O4·O6 — **publisher/consumer worker + 주차 행 처분 도구** | O5 실 Node 전송 재개 (`G-24`·`G-19`) |
| O7 RLS 실 행 | O10 — **D1·D5 결정 + partition 삭제 job** | O11 실 backup 복원 (`G-21`) |
| O8 감사 불변 | | O12 PITR 복구 (`G-22`) |
| O9 거부 기록 1:1 | | O13 pin ↔ GC (`G-20`) |

즉 **두 task의 75 → 100 사이에서 우리 몫은 4개 관측의 실행·기록과 5개의 선행 구현·결정**이고, 4개는 `G-19`·`G-20`·`G-21`·`G-22`·`G-24` 중 하나가 풀려야 시작된다. 9개를 다 채워도 **100은 되지 않는다** — 필수 운영 인수가 범위 안에 있기 때문이고, 그 사실을 숨기지 않는다.

**재채점(PR #220) §5는 이 문서를 Codex 몫으로 적었다.** 카드 108로 Claude에게 배정됐으므로 여기서 쓰되, **결정 항목 D1~D5와 선행 구현 5개의 owner는 이 문서가 정하지 않는다** — task-registry의 S04-DB·S08-DB owner는 Codex(reviewer Claude)다.

## 5. 되돌리면 실패해야 하는 시험 (관측을 정직하게 유지하는 장치)

관측 자체가 거짓이 되는 경로를 막는다. 구현 카드가 이 목록을 계약으로 받는다.

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 |
|---|---|---|
| T1 | O2의 "중복 배달 ≥ 1"이 **실제 배달**에서 온다 | consumer를 두 번 부르는 시험 stub으로 대체하면 실패 — broker의 재배달 로그 또는 장애 주입 기록이 분모다 |
| T2 | O3의 전수 SQL이 **join으로** 승인·attempt 시각을 비교한다 | 코드 경로(`assert_approval_valid`)만 시험하면 실패 — 직접 SQL로 `started_at`을 앞당긴 뒤 관측이 그것을 드러내야 한다 |
| T3 | O4의 원장 카운트가 **접근 로그와 독립 경로**다 | 원장만 세면 실패 — 로그의 요청 수가 없으면 "replay 100%"의 분모가 없다 |
| T4 | O5의 digest가 **receipt와 저장 바이트 양쪽**에서 온다 | receipt의 sha256만 비교하면 실패. `output_bytes`가 하는 것과 같은 3자(receipt·저장·attempt 수) 비교여야 한다 |
| T5 | O8의 권한 snapshot이 **`information_schema`에서** 온다 | 하드코딩 "INSERT only"면 실패 — app role에 UPDATE를 주면 snapshot 비교가 깨져야 한다 |
| T6 | O9의 1:1 대조가 **trace_id 기준**이다 | 건수만 비교하면 실패 — 같은 수의 다른 거부는 일치가 아니다 |
| T7 | O10의 삭제 job이 **계획을 먼저 기록**하고 실행한다 | 계획 없이 실행 후 catalogue만 보면 실패. 그리고 `ensure_partitions`와 **같은 transaction이면 실패**(`partitions.py:15` docstring이 정한 분리) |
| T8 | O11이 **운영 backup**에 대해 돈다 | 시험 fixture backup으로 대체하면 실패 — hosted `test_recovery_drill`이 1 passed·19 environment skip인 상태를 "복원 성공"으로 세는 것이 바로 이 경로다 |

## 6. 경계 · 미해결

- **임계치의 분모(O1 published ≥ 100, O5 재개 ≥ 3)는 이 문서가 처음 고정한 값**이다. 운영 데이터량을 본 뒤 올릴 수는 있으나, **결과를 보고 내리는 것은 금지**한다.
- **O4의 TTL 밖 재요청 건수는 임계치가 없다.** 그 값은 idempotency TTL(86,400초)이 제품에 맞는지의 입력이고, 결정은 별 카드다.
- **D1~D5는 이 문서가 정하지 않는다.** 코드가 지금 가진 숫자를 적었을 뿐이고, 그 숫자를 결정으로 승격하는 것은 owner의 일이다.
- **publisher worker·삭제 job이 코드에 없다는 사실은 이 문서가 처음 한 곳에 모아 적은 것**이지만 새 발견은 아니다 — orphan 수거자 부재는 Claude 작업 현황 v1.2.x의 CL-04 메모가 이미 적었다. 다만 `drop_expired_partitions`의 호출자 부재는 그 메모에 없다.
- **이 문서는 판정을 내리지 않는다.** 두 task의 현재 점수는 재채점(PR #220) v1.2의 **75**이고, registry status는 `review`(Codex owner 판정 2026-09-22)다. 이 문서는 그 75를 올리는 데 **무엇이 필요한지**만 정한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite·어떤 도구의 운영 실행. 이 문서의 실측은 `git show`·`git grep -n`으로 읽은 코드뿐이고, **관측은 하나도 수행하지 않았다.**
