---
doc_id: "HIST-CLAUDE-G04-W2-MODEL-VERSION-REGISTER-001"
title: "G-04 W2 model version 등록 route 구현 — canApprove·부모 결속 404·정본 ProblemDetails·IDEM-6 advisory 직렬화, UNIQUE 충돌 409(500 아님), PG-free 64 + 실 PG 13 시험"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T15:56:53+09:00"
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
