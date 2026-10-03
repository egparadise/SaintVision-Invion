---
doc_id: "HISTORY-CARD261-S10-LINEAGE-WRITE-20261003"
title: "카드 261 — S10 lineage 쓰기 경로를 설계대로 구현했다. 0064가 생산 run을 DB에서 묶고, 증명할 수 없는 kind는 계약에서 막고, deployment digest는 caller가 말하지 않는다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T12:50:59+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e5549f4b"
task_ids: ["S10-ST", "S10-DB"]
tags: ["s10-st", "model-registry", "lineage", "deployment", "migration", "idempotency", "claude"]
---

# 카드 261 — S10 model registry·lineage 쓰기 경로 구현 (migration 0064)

## 0. 한 줄

`#352`(카드 257)에서 Codex r3 승인(`4ce8ad28`)을 받은 설계를 **그대로** 구현했다 — migration `0064`가 `model_versions.produced_by_run_id`를 `runs(tenant_id, run_id)`에 복합 FK로 묶고(**기존 dangling 값은 측정해서 거부하며 고치지 않는다**), 등록 route가 `producedByRunId`와 **project를 증명할 수 있는 세 kind의** lineage edge를 받고, 새 route `POST /v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments`가 deployment를 적는다. **digest는 caller가 말하지 않는다** — `ModelVersion.content_sha256`에서 나오고 approval이 그것에 대조된다. 권한은 **세 번** 읽고, 세 번째는 **두 행을 잠근 뒤 insert 직전**이다. 시험 34(실 PG 13), 변이 **9/9 사살**, 일회용 DB에서 alembic 왕복·definer 15·census 160 실측.

## 1. 무엇이 들어갔는가

| 자리 | 내용 |
|---|---|
| `migrations/versions/0064_model_version_run_fk.py` | 복합 FK `fk_model_versions_tenant_id_produced_by_run_id` → `runs(tenant_id, run_id)` **하나만**. 열 추가·삭제 0, 정책·GRANT·ENABLE·FORCE 0. 부모는 `0063_build_policy_budgets`. revision id 25자 — `alembic_version.version_num`이 `varchar(32)`이므로(카드 255 r1에서 34자가 깨뜨린 그 한도) 시험이 길이를 단언한다 |
| `src/saintvision/db/models/lineage.py` | 같은 복합 FK를 `ModelVersion.__table_args__`에 — metadata가 DB와 어긋나면 `_insert` 기반 fixture가 먼저 깨진다 |
| `src/saintvision/services/lineage.py:259` | `SUBJECT_TABLES` — service가 아는 5 kind의 (표, id 열). 이 표가 있기 전에는 kind 집합이 여러 군데에 손으로 적혀 있었다 |
| 같은 파일 `:268`, `:291`, `:698` | `subject_exists` (tenant 범위 존재) · `subject_project` (kind별 project 증명 사슬) · `approval_project` (approval→run→workload.project) |
| 같은 파일 `:604`, `:619`, `:716` | `DeploymentAuthority` · `locked_deployment_authority` (두 행을 잠그고 판정, **아무것도 쓰지 않는다**) · `apply_deployment` (supersede+insert+mirror, **아무것도 판정하지 않는다**) |
| 같은 파일 `:772` | `record_deployment`는 두 절반을 잇는 wrapper로 남는다 — 기존 호출자(시험·S10 acceptance)를 깨지 않는다 |
| `src/saintvision/api/schemas.py` | `ProvableLineageKind`(3값) · `ProvableLineageEdge` · 등록 요청에 `producedByRunId`·`lineage`(최대 64) · `ModelDeploymentRequest`(**2 field**) · `ModelDeploymentResponse` |
| `contracts/model-deployment-request.schema.json` 외 2 | 위 Pydantic에서 **생성**(`tools/export_schemas.py`)했다. 손으로 쓰지 않았다 |
| `src/saintvision/api/v1/model_deployments.py` | 새 route 하나. 등록은 `src/saintvision/api/v1/projects.py` |
| `src/saintvision/api/v1/model_versions.py:251` | `_provable_edges` — 주장된 edge의 project가 경로의 project와 다르면 **없음과 같은 `RES-0004` 404** |
| `tools/definer-policy.json`, `docs/vault/30_Development/Evidence/s11-security-allowlist-reviewed-source-v1.json` | definer policy revision을 `0064_...`로 올리고 **검토된 source의 `policyRevision`도 같은 commit에서** 다시 묶었다(#343 교훈). `tools/aggregate_ac11_evidence.py`의 그 파일 blob pin도 `5dba3e93`→`bfac852e` |

AC-11 allowlist(`s11-security-allowlist-v0.json`)와 census(`tools/rls-table-census.json`)는 **건드리지 않았다** — `0064`는 표를 더하지 않고 축 정의를 바꾸지 않는다. 네 aggregator pin과 allowlist·census pin 전부를 실제 blob과 대조해 일치를 확인했다(§5).

## 2. 쓰기 route의 순서가 계약이다

`src/saintvision/api/v1/model_deployments.py`의 순서는 카드 250·253이 이 lane에서 이미 고정한 것과 **같다**.

1. `_require_idempotency_key` — **key는 필수**다. 없으면 `VAL-0003` 422이고 그 앞에 아무것도 일어나지 않는다.
2. `_authorised` [1차] — lock 이전의 첫 판정.
3. `serialise_idempotent_write` — **자원 행보다 먼저**. 이 lane의 잠금 순서는 key → version → approval 하나로 유지된다.
4. `_authorised` [2차] — **replay 판단 전에** 다시 읽는다. 이 lock을 기다리는 동안 등급이 사라졌다면 저장된 성공을 돌려주면 안 된다.
5. `replay_or_reserve` — ledger body에 **경로의 `modelId`·`version`을 넣는다**. 넣지 않으면 같은 key로 다른 version을 배포했을 때 첫 번째의 답이 replay된다(변이 M5).
6. `_version_in_project` → `locked_deployment_authority` — version과 approval을 잠그고 판정한다.
7. `_authorised` [3차] — **insert 직전**. 행 잠금도 대기이고 철회가 그 사이에 커밋될 수 있다. **설계 r2에서 Codex가 "현재 호출 경계로는 불가"라고 지적한 자리이고, service를 둘로 쪼갠 이유가 이것이다.**
8. `apply_deployment` → allow 감사 1행 → `store_idempotent_response` — 같은 transaction 경계.

등급은 `canRequest`가 아니라 **`canApprove`**다. 이 route가 적는 행은 "이 내용이 저 승인 아래 나갔다"는 **결정 등급의 진술**이고, 일을 요청할 수 있다는 것으로는 할 수 없는 말이다. `effective_permission`은 archived project·suspended user에서 **예외 없이 false 셋**을 주므로 세 판정 전부 **boolean을 읽는다**.

## 3. caller가 말할 수 없는 셋

| 말할 수 없는 것 | 어디서 오는가 | 왜 |
|---|---|---|
| `deployedDigest` | `ModelVersion.content_sha256` | 한 build를 승인한 것이 같은 version 이름으로 **다른 build를 내보낼** 권한은 아니다. approval의 `subject_sha256`이 그 digest에 대조된다 |
| `imageId` | 받지 않는다 | `container_images`에 project가 없다. 서버가 증명할 수 없는 것을 받지 않는다 |
| approval의 project | `approvals.run_id`→`runs.workload_id`→`workloads.project_id` | 같은 tenant의 **다른 project** approval이 이 project의 배포를 승인하게 된다. digest만으로는 그것이 누구의 build였는지 말하지 않는다(변이 M4) |

approval 실패 **여섯 가지**(없음·다른 tenant·다른 project·승인 아님·유효기간 밖·다른 내용)는 한 답 `GRAPH-0002` 409다. 원인별로 다른 코드를 주면 볼 수 없는 사람에게 approval id의 존재를 알려 주게 되고, 그것은 lineage subject가 이미 거부하는 그 신탁이다.

## 4. 설계에 없던 둘 — 적어 둔다

1. **감사 action이 template 그대로가 아니다.** ledger의 `endpoint`는 79자 template 그대로지만 `audit_events.action`은 64자가 한도다. 그래서 `long_template_action("POST", template, "record_model_deployment")` → `POST record_model_deployment#6ee159dbe4e8`을 쓴다(release route가 쓰는 같은 fallback). 식별자는 여전히 들어가지 않는다. 시험이 **79 > 64를 직접 재고** 그 fallback 값을 단언한다.
2. **`record_lineage`의 의미가 바뀌었다 — 설계가 정한 자리에서.** r2에서 나는 `record_lineage`가 `code_commit`·`container_image`를 항상 거부하게 하자고 적었는데, 그러면 **release가 불가능해진다**: `REQUIRED_KINDS`에 `code_commit`이 있고 `model_release.py:369-377`이 `trace["missing"]`에서 거부한다. 그래서 거부를 service에서 **공개 계약의 kind 집합으로** 옮겼다 — service는 다섯 kind를 계속 알고(내부 호출자가 쓴다), **caller가 주장할 수 있는 것은 project를 증명할 수 있는 셋**이다. service에 새로 생긴 거부는 "subject가 실재하는가" 하나다.

## 5. 실제 검증 증거

| 무엇 | 명령 | 결과 |
|---|---|---|
| 계약·순서·거부표 (PG 없이) | `pytest tests/core/test_model_deployment_contract.py` | **21 passed** |
| 실 PG (일회용 DB 55432) | `pytest tests/integration/test_model_deployment_real_pg.py` | **13 passed** |
| 영향 받은 14 파일 + 새 계약 시험 | §6 아래 목록 | **607 passed** |
| 변이 | 9개, 한 번에 하나 | **9/9 KILLED** (§6) |
| alembic 왕복 | 일회용 DB `c261_head`에 `upgrade head` → `downgrade -1` → `upgrade head` | head `0064_model_version_run_fk`, downgrade 뒤 FK 0행·**두 열 그대로**, 재상승 뒤 `FOREIGN KEY (tenant_id, produced_by_run_id) REFERENCES runs(tenant_id, run_id)` |
| definer | `INV_AUDIT_DSN=… python tools/check_definer_functions.py --json` | exit 0, `matches_reviewed_policy`, functions **15**, unsafe **0**, policy revision `0064_model_version_run_fk` |
| census | `python tools/collect_rls_evidence.py --disposable` | tables **160**, definer_functions **15** — 검토된 census와 **집합이 동일**(양쪽 차집합 0). `0064`는 표를 더하지 않는다 |
| allowlist 생성기 | `python tools/write_ac11_security_allowlist.py --check` | exit 0, blob `6c57afcf` 불변 |
| pin 6개 | aggregator 4 + allowlist + census를 `git hash-object`와 대조 | **전부 일치** |
| 문서·계약 gate | `export_schemas --check` / `check_docs` / `sync_obsidian --check` / `git diff --check` | PASS 102 계약 / PASS / 0 conflicts / 깨끗 |

### 측정에서 나온 두 가지를 숨기지 않는다

- **collector가 1건을 `UNMEASURED`로 남긴다**: `inv_cancel_bridge_owner public.audit_events` — `ctid` 거부 42501로 행 동일성을 확인할 수 없고, 읽을 수 있는 식별 열로 **0행을 비교**했으므로 "빈 비교는 무조건 일치하며 아무것도 재지 않는다". 이는 이 지역 DB의 권한 모양에서 나오는 것이고 `0064`와 무관하다(FK 하나는 `audit_events`의 RLS를 건드리지 않는다). 지역 관측 한계로 기록하며 **통과로 세지 않는다**.
- **변이 M9는 처음에 살아남았다.** `ProvableLineageKind` Literal을 다섯 값으로 넓혔는데 시험이 죽지 않았다 — 그 단언이 **생성된 contract 파일**만 읽고 있었기 때문이다(`export_schemas --check`가 따로 잡지만, 그것은 다른 gate다). 살아 있는 model을 함께 단언하도록 시험을 고치고 재실행해 KILLED를 확인했다.

## 6. 변이 9개

| # | 무엇을 뺐는가 | 판정 |
|---|---|---|
| M1 | lineage subject의 실재 요구 | KILLED |
| M2 | 주장된 edge의 project를 경로와 대조 | KILLED |
| M3 | `producedByRunId`를 project 안에서 해석 | KILLED |
| M4 | approval의 project 증명 | KILLED |
| M5 | ledger가 경로의 model·version을 묶는 것 | KILLED |
| M6 | **insert 직전 3차 권한 재검사** | KILLED (PG 없는 순서 시험과 **실 PG 경쟁 schedule 양쪽에서**) |
| M7 | `canApprove` → `canRequest` | KILLED |
| M8 | `0064`가 기존 행을 측정하는 것 | KILLED |
| M9 | caller가 service의 다섯 kind 전부를 주장 | KILLED (시험 보강 후, §5) |

영향 받은 파일 목록: `tests/core/`의 `test_model_deployment_contract` · `test_eval_suite_project_scope_migration` · `test_model_version_measurements_migration` · `test_object_store_locator_migration` · `test_release_acceptance_resolver` · `test_build_policy_resource_budget` · `test_model_version_register_route` · `test_kernel_cancel_bridge` · `test_lineage_query_routes` · `test_model_release_route`, `tests/`의 `test_ac11_migration_rehearsal` · `test_import_ac11_security_scan` · `test_run_ac11_security_threat_reports` · `test_model_registry` · `test_lineage`.

### 경쟁 schedule은 타이밍이 아니다

`tests/integration/test_model_deployment_real_pg.py`의 `test_a_grade_revoked_while_the_rows_are_locked_refuses_before_the_write`는 **잠금과 3차 검사 사이**에서 멈춘다 — 행 잠금이 잡힌 뒤에 철회가 도착할 수 있는 창은 그 하나다. 멈춘 그 순간에 **다른 backend가 `model_versions`·`approvals`에 행 잠금을 들고 있음을 `pg_locks`에서 확인하고**(sleep으로 가정하지 않는다), 멤버십을 지우고, 답은 하나다: `AUTH-0030` 403 · deployment 0행 · 거부 감사 1행. M6을 되살리면 같은 schedule에서 **201과 행 하나**가 나온다 — 그것이 이 시험이 무엇을 증명하는지다.

## 7. 남은 문제 / 차단

- **`G-23`(deployment digest 운영 인수)는 이 repository 밖이다.** 이 route는 **적는다. 배포하지 않는다** — kernel permit도 없고 byte도 움직이지 않는다. 실제로 돌고 있는지는 운영자의 관측이다.
- `code_commit`·`container_image`의 project를 증명하는 사슬은 schema에 **없다**. 그것을 만드는 것은 이 카드의 범위가 아니고, 그때까지 caller는 그 둘을 주장할 수 없다.
- 지역 collector의 `UNMEASURED` 1건(§5)은 hosted lane의 권한 모양에서 다시 재야 한다.
- hosted exact-head Backend/Core/security 결과는 **측정한 뒤에** PR에 적는다. 재지 않은 통과를 주장하지 않는다.

## 8. 다음

PR을 열고 exact-head CI 세 lane이 green인 것을 확인한 뒤 **'검토 기준 head' 코멘트 1회**. 검토는 Codex.
