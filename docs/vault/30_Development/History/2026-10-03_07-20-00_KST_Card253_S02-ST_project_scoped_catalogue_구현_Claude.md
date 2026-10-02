---
doc_id: "HISTORY-CARD253-S02ST-PROJECT-SCOPED-CATALOGUE-20261003"
title: "카드 253 — 0062와 project 범위 카탈로그 route를 설계대로 구현했다. 권한은 세 번 읽고, 소유자는 잠긴 행에서 읽고, 없음은 한 가지 404다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T07:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ab2829d9"
task_ids: ["S02-ST", "S02-DB"]
tags: ["s02-st", "storage", "catalogue", "project-scope", "migration", "idempotency", "rls", "claude"]
---

# 카드 253 — S02-ST 제공 폴더·DataLocation project 범위 구현 (Phase 1)

## 0. 한 줄

`#345`(카드 250)에서 Codex r6 승인을 받은 설계를 **그대로** 구현했다 — migration `0062`가 `data_locations`에 nullable `project_id` 열과 복합 FK를 더하고(정책·GRANT·ENABLE·FORCE 불변), core 앱에 `/v1/projects/{project_id}/storage/locations` 네 route가 생겼다. **project는 경로에서만 오고**, 권한은 **세 번** 읽고, contribution 소유자는 **잠긴 행에서** 읽고, 없음·비소유는 **byte 단위로 같은 `RES-0004` 404**이며 그 거부도 감사된다. 시험 46(실 PG 26), 변이 **15/15 사살**, disposable DB에서 alembic 왕복 실측.

## 1. 무엇이 들어갔는가

| 자리 | 내용 |
|---|---|
| `migrations/versions/0062_data_location_project_scope.py` | `project_id CHAR(30)` nullable 열 · 복합 FK `fk_data_locations_tenant_id_project_id` → `projects(tenant_id, project_id)` · 색인 `(tenant_id, project_id, catalogued_at)`. **그 외 0줄** — 정책 교체·GRANT·ENABLE·FORCE 없음 |
| `src/saintvision/db/models/storage.py` | 같은 열·복합 FK·색인을 모델에 (metadata가 DB와 어긋나면 `_insert` 기반 fixture가 먼저 깨진다) |
| `src/saintvision/api/schemas.py` | `LocationKindName`(정본 4값) · `LOCATION_IDENTITY_RULES` · `ProjectDataLocationRequest`(요청에 `projectId` 없음, `extra="forbid"`, kind별 `oneOf`) · 응답 2개 |
| `contracts/project-data-location-request.schema.json` 외 2 | 위 Pydantic에서 **생성**(`tools/export_schemas.py`)했다. 손으로 쓰지 않았다 |
| `src/saintvision/services/storage.py` | `catalogue_location(..., project_id=None)` · `locked_contribution(...)` · `_owned_for_update(...)` · `list_project_locations(...)` |
| `src/saintvision/services/resolver.py`, `src/saintvision/services/replica_observation.py` | `project_id`가 주어지면 **조건을 더한다**(두 번째 답을 만들지 않는다) |
| `src/saintvision/db/session.py` | `PROJECT_GUC = "inv.project_id"` · `project_scope()` (검증 뒤 `SET LOCAL`, transaction 한정) |
| `src/saintvision/api/v1/storage_project.py` | 새 route 넷. 등록은 `src/saintvision/api/app.py` |
| `src/saintvision/api/v1/storage.py` | 기존 activation·revocation이 **행의 `registered_by_user_id`** 를 권위로 쓴다(설계 §3-4-2, T6) |
| `tools/definer-policy.json`, `docs/vault/30_Development/Evidence/s11-security-allowlist-reviewed-source-v1.json` | definer policy revision을 `0062_...`로 올리고 **검토된 source의 `policyRevision`도 같은 commit에서** 다시 묶었다(#343 교훈) |

## 2. 쓰기 route의 순서가 계약이다

`src/saintvision/api/v1/storage_project.py`의 쓰기는 이 순서이고, 각 단계에 이유가 있다.

1. `_require_idempotency_key` — **key는 필수**다. 없으면 `VAL-0003` 422이고 그 앞에 아무것도 일어나지 않는다.
2. `_authorised` [1차] — lock 이전의 첫 판정.
3. `serialise_idempotent_write` — **자원 행보다 먼저** 잡는다(그 docstring이 잠금 순서를 고정한다).
4. `_authorised` [2차] — **replay 판단 전에** 다시 읽는다. 이 lock을 기다리는 동안 멤버십이 사라졌다면 저장된 성공을 돌려주면 안 된다.
5. `replay_or_reserve` — 같은 key·같은 body면 저장된 응답, 다른 body면 `GRAPH-0002` 409.
6. `locked_contribution` — contribution 행을 `FOR UPDATE`로 잡고 **그 행에서** 소유자·tenant·`active`를 읽는다.
7. `_authorised` [3차] — insert 직전. 행 잠금도 대기이고 같은 철회가 그 사이에 커밋될 수 있다.
8. `project_scope` + `catalogue_location` — 경로의 project를 쓴다.
9. 성공 감사 1행 + `store_idempotent_response` — 같은 transaction 경계.

`effective_permission`은 archived project·suspended user에서 **예외 없이 false 셋**을 주므로 세 판정 전부 **boolean을 읽는다**. "예외가 없었다"를 승인으로 쓰지 않는다.

## 3. 설계에 없던 둘 — 적어 둔다

둘 다 측정에서 나왔고, 설계의 결론을 바꾸지 않는다.

1. **tenant 전역 URI 유일성이 이제 닿는다.** `data_locations`는 `0001`부터 `(tenant_id, uri)`가 유일한데 `0062`는 그것을 project 단위로 좁히지 않았다. `catalogue_location`에는 이 PR 전까지 **제품 호출자가 없었으므로**(시험만) 그 충돌이 제품 경로에서 처음 닿는다. 그대로 두면 `IntegrityError` → 500이므로 savepoint 안에서 잡아 **`GRAPH-0002` 409**로 답하고, 그 message는 **어느 project가 그 URI를 들고 있는지 말하지 않는다**(말하면 project 간 존재 신탁이 된다). URI를 project 단위로 유일하게 만드는 것은 Phase 2의 몫이다.
2. **성공 감사 1행.** 설계 §3-2-3이 "location insert·ledger·감사가 같은 경계에서 커밋되거나 함께 사라진다"고 적었으므로 `storage.location.catalogue` allow 행을 같은 transaction에 적는다. `detail`에는 **경로도 URI도 넣지 않았다** — 둘 다 호출자가 준 text에서 만들어지고, 식별자만으로 그 행을 찾을 수 있다.

## 4. 측정

### 4-1. 시험

| 무엇 | 결과 |
|---|---|
| `tests/core/test_storage_project_contract.py` (PG 없음: T1·T2·T11·T12·T17·T19 + `0062` 본문 불변식) | **20 passed** |
| `tests/integration/test_storage_project_scope_real_pg.py` (실 PG: T3·T4·T5·T6·T7·T8·T9·T12·T13·T14·T15·T16·T18-a/b/c·T20·T21·T22) | **26 passed** |
| 회귀: `tests/test_storage_api.py` · `tests/test_storage_catalog.py` · `tests/integration/test_storage_catalog_api.py` · `tests/core/test_write_response_contracts.py` · `tests/core/test_lock_wait.py` · `tests/test_vf_replica_migration.py` | **123 passed** |
| `tools/export_schemas.py --check` | exit 0 (100 schema) |

경쟁 두 schedule은 **시간 가정이 없다** — `pg_stat_activity`에서 그 database의 backend가 lock을 기다리는 것을 본 뒤에만 다음 단계로 간다. T18-b·T21은 행 잠금 **뒤**, insert **앞**의 한 지점에서 요청을 멈추는데, 그 지점은 판정이 아니라 지연만 한다.

### 4-2. 변이 15/15 사살 (exit 1만 사살로 센다)

| # | 변이 | 결과 |
|---|---|---|
| M1 | contribution 행 잠금(`FOR UPDATE`) 제거 | KILLED (T18-a) |
| M2 | 잠긴 행의 소유자 검사 제거 | KILLED (T12·T6) |
| M3 | `active` 검사 제거 | KILLED (T18-c) |
| M4 | project 결속을 쓰지 않음(`project_id=None`) | KILLED (T3·T14) |
| M5 | 목록 조회에서 project 조건 제거 | KILLED (T7) |
| M6 | resolver가 project를 무시 | KILLED (T3) |
| M7 | 3차 재검사 제거 | KILLED (T22) |
| M8 | 2차 재검사 제거 | KILLED (T21) |
| M9 | 등급을 읽지 않고 예외 유무만 신뢰 | KILLED (T4-viewer·T22) |
| M10 | 읽기를 모든 멤버에게 개방 | KILLED (T3-viewer) |
| M11 | key 필수를 해제 | KILLED (T20) |
| M12 | 없음 거부를 감사하지 않음 | KILLED (T12 둘) |
| M13 | URI 충돌이 다시 500 | KILLED |
| M14 | 요청 본문이 `projectId`를 받음 | KILLED (T1) |
| M15 | kind가 남의 식별자를 허용 | KILLED (T17) |

M10은 **처음에 살아남았다** — 교차 project 시험의 주체가 애초에 그 project의 멤버가 아니어서 `require_project_access`가 등급 검사 전에 거부했기 때문이다. 읽기 등급(`canRequest ∨ canApprove`)을 실제로 묻는 시험(같은 project의 `viewer`, 그리고 쓰기는 못 하지만 읽는 `approver`)을 더해 사살했다.

### 4-3. disposable DB에서 alembic 왕복

`CREATE DATABASE` → `alembic upgrade head` → 관측 → `downgrade -1` → 관측 → 다시 `upgrade head` → `DROP DATABASE`.

| 관측 | 값 |
|---|---|
| `alembic upgrade head` 뒤 head | `0062_data_location_project_scope` |
| 열 | `project_id` / `character` / `is_nullable = YES` |
| FK | `fk_data_locations_tenant_id_project_id`, `confupdtype=a`·`confdeltype=a`, deferrable 아님, validated |
| 색인 | `CREATE INDEX ix_data_locations_tenant_id_project_id ON public.data_locations USING btree (tenant_id, project_id, catalogued_at)` |
| `downgrade -1` | head `0060_build_execution_admissions`, `project_id` 열 없음 |
| 다시 `upgrade head` | `0062_data_location_project_scope` |

그리고 T8이 **SQL 수준 불변식**으로 같은 왕복을 본다 — downgrade 뒤 `pg_policies`·`relrowsecurity`·`relforcerowsecurity`·`information_schema.role_table_grants`가 **전부 그대로**이고(`(True, True)`), 열만 사라진다.

### 4-4. 검토된 사슬 — census는 돌지 않고 allowlist도 돌지 않는다

| 무엇 | 측정 |
|---|---|
| 표 모집단 | head `0062`의 disposable DB에서 collector가 센 **157**개가 `tools/rls-table-census.json`의 검토된 157개와 **정확히 같다**(unreviewed 0·missing 0). `0062`는 표를 더하지 않으므로 census는 stale이 되지 않는다 |
| definer 함수 | 같은 관측에서 **15개**, `tools/check_definer_functions.py --json` **exit 0 / `unsafe: 0`** — revision 비교가 rebound policy와 일치한다 |
| AC-11 allowlist | `tools/write_ac11_security_allowlist.py --check` **exit 0**, `docs/vault/30_Development/Evidence/s11-security-allowlist-v0.json`의 md5가 **변하지 않았다**(`395e30d78c0e594ea969cb4b02c6ef5d`) — 그 파일은 revision을 들고 있지 않다. AC-11 정의는 건드리지 않았다 |

## 5. 하지 않은 것 · 남은 것

- **Phase 2(정책 교체)는 이 PR에 없다.** `data_locations`는 `0001`의 tenant 정책을 그대로 쓴다. project GUC를 요구하는 정책으로 바꾸면 project 선택자가 없는 기존 owner 범위 route가 **조용히 0행**이 되므로 별 카드다.
- **`0062`의 `down_revision`은 지금 `0060_build_execution_admissions`** 다. `0061_build_preparations`(#343, 카드 247)는 이 base의 조상이 아니다. train 33이 조립되어 `#343`이 들어오면 **`0062`의 `down_revision`을 `0061`로 다시 가리켜야 한다**(migration 선형성). 그때 definer policy revision은 이미 `0062`이므로 추가 회전은 없다.
- **브라우저 화면은 Gemini 몫이다.** API·계약까지만 했다. S02-ST 100은 실제 사용자 여정과 외부 전제가 남아 있고 이 카드로 닫히지 않는다.
- URI를 project 단위로 유일하게 만드는 것(§3-2)은 Phase 2 후보다.

## 6. 다음 첫 행동

**Codex 검토**(고난도 동시성 — 잠금 순서·세 번의 재검사·경쟁 두 schedule). 그다음은 train 33 조립 시 `down_revision` 재지정, 그리고 Phase 2 정책 교체 카드의 범위 결정.

설계 전문은 `#345`가 담았다(이 base에 없으므로 wiki link를 걸지 않는다).
