---
doc_id: "HIST-CLAUDE-G04-W2-MODEL-VERSION-REGISTER-001"
title: "G-04 W2 model version 등록 route 구현 v1.1 — canApprove·부모 결속 404·정본 ProblemDetails·IDEM-6 advisory 직렬화, URI 서버 파생·잠금 뒤 시각 취득(Codex F2·F3), UNIQUE 충돌 409, PG-free 80 + 실 PG 13 시험"
version: "1.1.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T16:28:56+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-04", "model-registry", "idempotency", "problem-details", "implementation", "claude"]
---

# G-04 W2 model version 등록 route 구현 (카드 64)

승인된 설계 `#183` v1.2.1(head `0642b112`) §8의 **PR 4**다. base는 조정자가 고정한 `#175`(`agent/claude/s10-lineage-query-impl`, `#167` 포함) head `6ea12700` 위에 `#159` head `5e206aa4`를 merge한 것(`#184`와 같은 방식, 해소만)이다. 로컬 실 PG·Docker·전체 suite는 돌리지 않았다.

`register_model_version`은 S10-ST부터 `services/lineage.py`에 있었고 **HTTP 요청이 한 번도 도달한 적이 없었다**. 이 PR이 그 요청 경로이고, 서비스 시그니처는 **변경 0**이다.

## 1. 순서를 고정했다

`api/v1/model_versions.py`의 실제 순서이고 PG-free 시험이 그 목록을 문자 그대로 단언한다.

```
permission → body-read → lock → permission → ledger-read → model-get → service → audit → ledger-write
```

- **permission이 body보다 먼저**(`#184` F2와 같은 순서): 등급 없는 호출자는 자기 body가 어떻게 판정되는지 배우지 못한다. 시험은 `MAX_REQUEST_BYTES`를 넘는 body로 403(413이 아니라)을 단언한다.
- **`Idempotency-Key`는 body보다 먼저 판정**: 헤더 하나로 끝나는 거부에 body를 읽을 이유가 없다.
- **lock이 원장·row보다 먼저**(IDEM-6): 잠금 순서는 이 lane 전체에서 하나 — 직렬화점 → resource row.
- **lock 뒤 permission 재확인**: 두 span 사이에 회수된 membership은 쓰지도, **저장된 응답을 읽지도** 못한다(`#152` F-R5).
- **span은 2개**: 권한은 짧은 tx, body는 tx 없이, 쓰기는 하나의 원자적 tx. 설계의 "1 tx"는 쓰기를 뜻하고 그것이 두 번째 span이다. 쪼갠 이유는 **body가 도착하는 속도를 호출자가 정하기 때문**이다 — 그 구간에 tx를 열어두면 호출자가 tx를 붙잡을 수 있다. 시험이 body를 읽는 순간의 tx depth가 `0`임을 단언한다.

## 2. IDEM-6 직렬화점을 공유 helper로 만들었다

`deps.serialise_idempotent_write()`. `replay_or_reserve()`는 **예약하지 않는다**(조회만) — 동시 최초 2건이 둘 다 "없음"을 읽고 둘 다 서비스를 실행한 뒤 하나가 원장 unique index에서 진다. 예약할 row가 아직 없으므로 원장만으로는 못 막는다. 그래서 **row가 아니라 키에 대한 tx-scoped advisory lock**을 잡는다.

- 키 재료 = `namespace \x1f tenant \x1f project \x1f endpoint \x1f idempotency-key` → sha256 첫 8바이트를 **signed bigint**로. 파생이므로 저장물도 migration도 없고 commit/rollback이 해제한다.
- 구분자를 둔 이유: 없으면 `("a","bc")`와 `("ab","c")`가 같은 잠금이 된다. `Idempotency-Key`는 `[A-Za-z0-9._:-]{1,128}`로 좁혀 구분자가 키 안에 들어올 수 없게 했다(원장 열이 `String(128)`이기도 하다).
- 실 PG 시험이 **barrier로 두 tx를 같은 순간 잠금 앞에 세운다** — row 1, 원장 1, unique error 0, 두 응답 동일. 우연히 직렬화된 순서가 아니라 실제 경합이다.

## 3. path→row와 404

`model_versions`에는 `project_id`가 없다. 부모 `models` row가 project를 말하는 유일한 것이고, **부재·다른 tenant·다른 project 세 경우가 같은 404 body**다(시험이 `traceId`만 뺀 body 3개가 동일함을 단언). 구분 가능한 path 변수는 존재 oracle이다.

## 4. UNIQUE 충돌은 409이고 500이 아니다

설계가 UNIQUE를 "2차 방어"로 세었으므로 호출자는 충돌을 들어야 한다. `IntegrityError`를 잡아 constraint 이름(psycopg `diag`), 없으면 메시지, 없으면 sqlstate `23505`로 판정한다.

| constraint | detail |
|---|---|
| `uq_model_versions_model_id_version` | "This model already has a version with that name." |
| `uq_model_versions_tenant_id_content_sha256` | "That content digest is already registered." |

**UNIQUE가 아닌 `IntegrityError`는 감추지 않는다**(FK 위반 등은 우리 결함이고, 409로 바꾸면 호출자에게 "재시도하지 말라"고 잘못 말한다). 시험이 sqlstate `23503`에서 500이 나오는 것을 단언한다.

## 5. 발견 — digest UNIQUE는 tenant 범위라 project 경계를 넘는다

`uq_model_versions_tenant_id_content_sha256`은 **tenant** 범위다. 그래서 project A의 승인자가 digest를 등록하려다 409를 받으면, 그 digest가 **자기가 볼 수 없는 project B에 이미 있다는 사실**을 알게 된다. route가 피할 수 없다(답을 해야 한다). 할 수 있는 것은 **어디서 충돌했는지 말하지 않는 것**이고 그렇게 했다 — detail은 충돌 사실만 말하고, 실 PG 시험이 응답에 상대 project id·model id가 없음을 단언한다. 제약 자체는 의도된 것(S10-ST: "두 이름으로 같은 bytes는 잡을 만한 실수")이므로 **판단은 owner 결정**으로 남기고 사실만 기록했다.

## 6. 범위에서 뺀 것 둘 (이유 있는 누락)

`register_model_version`은 `produced_by_run_id`와 `lineage`도 받지만 요청 모델에 **두지 않았다**.

- `produced_by_run_id`는 FK가 없다. 결속 없이 받으면 **다른 project의 run에 이 버전을 붙이는 거짓 provenance**가 된다. 결속에는 `project_scope.run_in_project`(`#184`, PR 1/8)가 필요하고 base가 `#175`로 고정돼 이 branch에 없다.
- `lineage` edge를 쓰는 `record_lineage`는 **subject row의 존재를 확인하지 않는다**(`#167`에서 실측). 노출하면 아무것도 가리키지 않는 edge를 쓸 수 있고 `trace_model`은 subject가 없는 kind를 그대로 보고한다.

둘 다 **거부를 시험으로 고정**했다(`producedByRunId`·`lineage`를 보내면 422). 되살리려면 의도적인 변경이어야 한다. `#184` 병합 뒤 후속 카드 후보다.

## 7. 관찰 — 정본 403은 denial audit을 남기지 않는다

`_require_approval`이 `InvError`를 `CanonicalProblem`으로 번역하므로 `app.py`의 `InvError` 핸들러(AUTH/SEC일 때 `record_denial_out_of_band`)에 **도달하지 않는다**. `install_canonical_problem_handler`는 감사를 쓰지 않는다. 즉 `#167`·`#175`·`#184`·이 PR의 `AUTH-0030` 403은 AC-02가 요구하는 denial 기록이 없다. **이 PR에서 고치지 않았다**(공유 핸들러 변경은 이 카드 범위가 아니고 네 route에 동시에 영향한다). 별 카드 후보로 적어 둔다.

## 8. 검증

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_model_version_register_route.py -q` | **64 passed** |
| `pytest tests/core/test_write_response_contracts.py -q` | 54 passed |
| `pytest tests/test_route_coverage.py -q` | 40 passed |
| `pytest tests/core/test_model_release_route.py -q` | 59 passed (형제 route 무회귀) |
| `python tools/export_schemas.py --check` | PASS (64 contract schemas) |
| `python tools/check_contract_bindings.py` | PASS |
| `python tools/check_response_freshness.py` | exit 0 |
| `check_docs` · `check_doc_single_source --ratchet` | exit 0 |
| openapi | `POST /v1/projects/{project_id}/models/{model_id}/versions` → `201` 노출 확인 |

**revert-fail 5건을 실제로 죽였다**(제품 파일을 변이시키고 돌린 뒤 복원):

| 변이 | 죽은 시험 |
|---|---|
| lock 뒤 permission 재확인 제거 | 2 |
| `Idempotency-Key` optional로 | 1 |
| lock을 원장 조회 뒤로 이동 | 3 |
| `IntegrityError` catch 제거 | 5 |
| 부재 model에만 다른 detail | 2 |

실 PG 13건은 hosted Backend에서 실행된다(메모리 규칙상 로컬 실 PG 없음). hosted가 `_seed`에서 죽는 일을 막기 위해 **PG-free guard**를 넣었다 — 통합 fixture를 import해 기록용 connection에 돌려 컬럼명·필수 컬럼·id kind를 미리 잡는다(`#167`에서 hosted 한 시간을 그것으로 잃었다).

## 9. 다음 첫 행동

Codex 검토. 병합 순서는 `#167` → `#175` → 이 PR(`#159` merge 포함). 승인 뒤 같은 설계의 W4(pin, PR 6)가 이 PR 위에 stack한다.

## 10. v1.1 — Codex 사전 검토 delta (#191, head `266adfc6` 기준)

순서·IDEM barrier 시험은 승인 방향으로 확인받았고(hosted Backend `36389688954` 3.12·3.14 각각 3263 passed / 47 skipped / 2 deselected, exact skip gate green), 차단점 넷 중 셋을 이 delta에서 고쳤다.

### 10-1. F2 — caller `uri`를 **없앴다**(결속이 아니라 파생)

지적이 정확했다. schema가 `uri`를 1~2048 임의 문자열로 받고 route가 `_model_in_project()`의 `Model`을 버린 뒤 그대로 서비스에 넘겼으므로 `https://user:secret@host`, `javascript:...`, **다른 model/version의 `inv://`** 가 모두 201로 영구 저장됐다. 그리고 `tests/test_model_registry.py::test_a_version_carries_the_join_key_the_kernel_manifest_is_addressed_by`가 "URI version == row version"을 전제한다.

Codex가 허용한 두 안 중 **서버 파생**을 골랐다 — `inv://models/<model.name>@<version>`은 부모 model의 이름과 이 요청의 version으로 완전히 결정되므로 **caller가 줄 것이 없고 검증할 것도 없다**. 필터링이 아니라 부류 자체를 제거한다. builder는 제품의 `storage.pathsafe.build_uri`(ADR-010)라 resolver 문법과 갈라질 수 없고, 문법이 표현할 수 없는 이름·version(`@`·`/`)은 500이 아니라 **422**다(해결될 수 없는 등록이므로 요청 오류다).

요청에서 `uri`를 **제거**했으니 위 세 종류는 모두 `extra="forbid"`의 422이고, 부정 시험 7개가 그것을 고정한다.

### 10-2. F3 — 시각을 **잠금 뒤에** 한 번 읽는다

`Depends(get_now)`는 handler 진입 전에 평가되고, 그 뒤 route는 caller가 속도를 정하는 body를 읽고 advisory lock에서 기다린다. 오래 걸린 요청은 **기다리기 전의 시각**으로 `created_at`·audit·원장 `expires_at`을 적었다. `now` dependency를 없애고 **lock 획득 + 두 번째 live 권한 확인 뒤** `request.app.state.clock()`을 한 번 읽어 service·audit·ledger에 같이 쓴다.

시험은 sleep 없이 이것을 죽인다 — fake session의 `execute`(잠금)와 body reader가 clock을 전진시키고, 기록된 `now`가 **전진한 값**임을 단언한다. 시각 취득을 원래 위치로 되돌리는 변이에서 3건이 죽었다.

### 10-3. 비차단 — 모르는 `23505`를 duplicate라 부르지 않는다

`_unique_conflict()`의 sqlstate fallback을 없앴다. **알려진 constraint 이름만** 409이고 나머지는 전파된다(500). 뒤에 생긴 UNIQUE나 생성 ULID 충돌(`uq_model_versions_tenant_id_version_id`)을 "당신의 digest가 중복"으로 위장하면 우리 결함을 caller 잘못으로 보고하는 것이다. 그 ULID constraint도 표에서 **뺐다**. 변이 1건이 죽었다.

### 10-4. 비차단 — advisory lock 무한 대기를 운영 공백으로 명시

제품 engine에 `lock_timeout`·`statement_timeout`이 없어 키를 쥔 장기 tx가 있으면 요청이 무기한 기다린다. bounded timeout은 이 route 혼자 정할 것이 아니라 **쓰기 lane 전체의 timeout 계약**이므로, 모듈 docstring에 공백으로 적고 별 카드로 분리했다. 조용한 raw DB detail 노출은 없다.

### 10-5. F1 — Codex 결정을 받았고, migration은 이 branch에 둘 수 없다

Codex 결정: tenant-wide `uq_model_versions_tenant_id_content_sha256`은 sibling-project 존재 oracle이므로 **`(model_id, content_sha256)`로 좁히는 migration을 이 route의 선행**으로 둔다. wire 문구만 숨기는 해법은 불가.

**이 branch에 넣을 수 없다**: W2의 base(#175 + #159)가 품은 migration head는 `0048_object_store_locator`이고, 고정된 중앙 순서는 `0049`(#172)·`0050`(#174)·`0051`(#176)·`0052`(W5 예약)다. 여기에 새 revision을 두면 `down_revision`이 가리킬 것이 없거나 head가 둘이 된다. 그래서 **별 PR**(사슬 꼬리를 품은 branch 위)로 올려야 하고, revision 번호와 그 base branch를 조정자에게 요청했다(조정자 사전 배정 `0053`).

시험은 그 사이를 정직하게 비웠다 — 누출을 "옳다"로 고정했던 시험을 지우고, **오늘의 동작을 공백으로 기록하는 시험**(409이고 식별자는 노출하지 않음)만 남겼다. 목표 시험("한 tenant의 두 project가 같은 digest를 각각 등록할 수 있다")은 **여기 두지 않았다**: 지금은 예상 실패여야 하고 `xfail`은 JUnit `skipped` 항목이라 Backend lane의 exact-skip gate가 거부한다. 그 시험은 **migration PR 소유**다.

### 10-6. F4 — 정본 403 denial audit

내가 보고한 공백에 Codex가 계약을 걸었다(`issuecomment-5865205424`). route-local 기록 금지, #189의 action + 공유 canonical handler 사용, 403 한 건이 tenant/actor/project/action/trace를 가진 denial 정확히 1행, audit write 실패는 500 fail-closed. **카드 69의 공유 PR이 구현 중**이고 그것이 나오면 merge한다. 이 PR에서 직접 고치지 않는다.

### 10-7. 검증(delta)

| 명령 | 결과 |
|---|---|
| `pytest tests/core/test_model_version_register_route.py -q` | **80 passed** (v1.0의 64 + F2 10 + F3 3 + 모르는 23505 3) |
| `pytest tests/core/test_model_release_route.py tests/core/test_write_response_contracts.py -q` | 113 passed |
| `export_schemas --check` · `check_contract_bindings` · `check_response_freshness` | PASS |
| `git diff --check` | 깨끗 |
| 실 PG | 13건(목표 F1 시험 1건은 migration PR로 이동) |

**변이 3건이 죽었다**: URI를 다른 model로 파생(6건 이상), 시각 취득을 lock 앞으로 되돌림(3건), sqlstate fallback 복원(1건).
