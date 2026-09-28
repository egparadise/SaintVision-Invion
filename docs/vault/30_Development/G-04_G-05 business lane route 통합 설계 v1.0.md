---
doc_id: "CLAUDE-G04-G05-BUSINESS-ROUTES-DESIGN-001"
title: "G-04·G-05 남은 business lane route 통합 설계 v1.0 — S09 넷(Context bundle 조회·RunRecord 봉인·pin 조회·eval 실행) + model-registry 셋(register·verify·pin_retention): 기존 서비스·index·route 재사용 표, 읽기 membership/쓰기 canApprove 등급, 정본 ProblemDetails·strict·path→row·404·IDEM, tx/lock 순서와 Codex 계약 지점, persistence 판정(eval suite project 결속 = migration 필요·번호 요청), 계약·FE 영향, route별 PR 분할 (카드 58, docs-only)"
version: "1.2.2"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:29:11+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-BE", "S10-BE"]
tags: ["G-04", "G-05", "business-lane", "route", "design", "claude"]
---

# G-04·G-05 남은 business lane route 통합 설계 v1.0 (2026-09-28, 카드 58)

> [!note] 범위
> PR #179 §3-4의 G-04(S09 넷)·G-05(model-registry 셋) **통합 설계 한 건**(docs-only). 구현은 route별 PR로 쪼갠다(§8). #158·#152/#167·#174·#175가 세운 원칙을 그대로 쓰고 새 원칙을 만들지 않는다. 식별자·경로는 `git grep -n -F`/`git cat-file -e`로 확인한 것만 적는다(base `1e8baf04`; #158/#152/#167/#174/#175는 해당 branch head에서 확인).

## 1. 먼저 읽은 것과 재사용할 것 (새로 만들지 않는다)

| 대상 | 이미 있는 것 (git grep -n -F 결과) | 이 설계에서의 쓰임 |
|---|---|---|
| **#174** `0050_dataset_digest_lookup` | `INDEX = "ix_dataset_versions_tenant_id_content_sha256"`(migration 0050:43, `CONCURRENTLY`) | 역조회 인덱스는 **이미 있다**. 이 설계의 7 route 중 digest로 찾는 것은 없으므로 새 index 0 |
| **#175** lineage 역조회·순방향 | `src/saintvision/api/v1/lineage_query.py`: `TRACE_PATH = "/projects/{project_id}/models/{model_id}/versions/{version}/lineage"`(:68), by-digest(:70), helper `_membership`(:124)·`_version_in_project`(:144)·`TRANSLATION`(`RES_ARTIFACT_NOT_FOUND: (RES_NOT_FOUND, 404, False)`, :65)·`_query/_limit/_cursor`(:81-120) | **path→row 결속·membership·404·cursor helper를 그대로 import**한다. model-registry 셋의 path는 `TRACE_PATH`와 같은 접두(`/projects/{p}/models/{m}/versions/{v}/…`) |
| **#158** lineage read 설계 | §1-4 "project 범위가 테이블마다 다르다"(`models`·`datasets`만 `project_id`; `eval_runs`·`model_versions`·`approvals` 없음), §6 권한·404, §9 정본 ProblemDetails 공유 모듈 | 읽기 등급·404 정책·오류 모듈 결정을 **물려받는다** |
| **#152/#167** release 쓰기 한 지점 | `src/saintvision/api/v1/model_release.py`: `RELEASE_PATH`(:327), `_require_approval`(:233, `permission.get("canApprove")` :250 — **canApprove를 강제하는 첫 business route**), `_locked_version`(:256), `_rebind_identity`(:279), `_require_release_preconditions`(:296); `src/saintvision/api/problem.py`(`CanonicalProblem`·`translate`·`strict_json_object`·`read_bounded_body`·`validate_strict`) | 쓰기 등급·잠금 뒤 재결속·정본 오류·strict body 읽기를 **그대로 재사용** |
| 서비스 함수 7 (base) | `services/records.py:41 seal_run_record`, `:141 get_record`, `:152 list_pinned_artifacts`, `:167 verify_pin`; `services/context.py:165 build_bundle`, `:240 read_bundle`, `:276 verify_bundle`; `services/eval_execution.py:240 run_suite`, `services/evaluation.py:130 start_eval_run`; `services/lineage.py:184 register_model_version`, `:271 verify_model_version`, `:292 pin_retention` | route는 **호출만** 한다. 서비스 판정(봉인 전제·검증 digest·pin 단조성)을 route에 복제하지 않는다 |
| 멱등 원장 | `src/saintvision/api/deps.py:75 request_digest`(body hash), `:81 replay_or_reserve`, `:124 store_idempotent_response`; `db/models` `idempotency_records`(tenant_id·project_id·endpoint·idempotency_key·request_sha256·response_status·response_body) | 쓰기 4 route의 IDEM(§4) — **새 원장 없음** |
| adapter 선택 | `src/saintvision/adapters/agents.py:104 adapter_for(name)`(`BY_NAME`, `CliAdapter`), `api/v1/adapters.py:36/:65` | eval 실행 route가 adapter를 **이름으로** 고른다 |
| 계약 생성 | `tools/export_schemas.py:11 exported()` — `schemas.Strict` 파생 `*Request`/`*Response`가 `contracts/*.schema.json`으로; `tools/check_contract_bindings.py` | 새 응답/요청 타입은 이 규칙으로만(§6) |

## 2. route별 등급 (읽기 = live membership, 쓰기 = canApprove)

| # | route (제안) | 종류 | 등급·출처 | 서비스 |
|---|---|---|---|---|
| R1 | `GET /projects/{p}/runs/{run_id}/record` | 읽기 | **membership** — `require_project_access`(`services/projects.py:204`; membership 없으면 `AUTH_PROJECT_SCOPE`), #158 §6-3 "읽기에 필요한 등급은 membership" | `get_record` |
| R2 | `GET /projects/{p}/runs/{run_id}/record/artifacts[?role=]` + `GET …/record/artifacts/{artifact_id}/verify` | 읽기 | membership | `list_pinned_artifacts`, `verify_pin` |
| R3 | `GET /projects/{p}/runs/{run_id}/context-bundle` | 읽기 | membership | `read_bundle` + `verify_bundle`(응답에 `hashVerified`) |
| W1 | `POST /projects/{p}/runs/{run_id}/record` (봉인) | 쓰기 | **canApprove는 필요조건일 뿐**(Codex F1). integrity 값(`component_versions`·**봉인 artifact 집합 전체**·`bundle_id`·checksum)은 request가 아니라 **서버가 잠근 정본(Run/Evidence/Context/Artifact)에서 완전하게 파생**; request는 서버 파생 artifact 각각의 **role 매핑만** 줄 수 있고 누락·추가할 수 없다(§5-2) | `seal_run_record` |
| W2 | `POST /projects/{p}/models/{model_id}/versions` (등록) | 쓰기 | canApprove | `register_model_version` |
| W3 | `POST /projects/{p}/models/{model_id}/versions/{version}/verify` | 쓰기 | **보류**(Codex F1 최종 승인 불가): `lineage.py:279`의 정본은 "trusted worker hashed the actual weights"인데 canApprove 사용자가 DB에 있는 digest를 그대로 제출해 `verified_at`을 세울 수 있음. **trusted-worker identity + 실제 object read/hash Evidence 결속 seam**을 먼저 정한 뒤에만 구현 | `verify_model_version` |
| W4 | `POST /projects/{p}/models/{model_id}/versions/{version}/retention-pin` | 쓰기 | canApprove | `pin_retention` |
| W5 | `POST /projects/{p}/eval/suites/{suite_id}/runs` (실행) | 쓰기 | canApprove(외부 adapter 호출·비용 발생) — **§5에서 project 결속 불가 판정 → migration 번호 요청 뒤 진행** | `run_suite` |

등급 결정(v1.2, Codex F1 최종): **W2 register·W4 retention-pin = canApprove 최종 승인**; **W5 eval 실행 = canApprove 최종 승인**(요청자가 endpoint/credential을 주입하지 못하고 서버 `adapter_for()`의 구성된 allowlist만 고르는 조건에서; 외부 비용 권한 신설 근거 없음); **W1 seal = canApprove 필요조건 + 서버 파생 integrity**(§5-2); **W3 verify = 보류**(trusted measurement seam 결정 전 구현 금지). 읽기 3 = membership 승인.

**project 결속 방법(#158 §1-4의 제약 그대로)**: `run_records`·`context_bundles`는 `run_id` → `runs.workload_id` → `workloads.project_id`(`db/models/execution.py` `Workload.project_id`)로 부모 join; `model_versions`는 `models.project_id`로 부모 join(#175 `_version_in_project` 재사용). **`eval_suites`·`eval_runs`는 어떤 join으로도 project를 증명할 수 없다**(`db/models/evaluation.py:52-72`에 project 열 없음; #158 §1-4 표) → §5.

## 3. 정본 오류·strict·path→row·404 (한 규칙)

- **정본 ProblemDetails**: `api/problem.py::CanonicalProblem`(code `^[A-Z]+-[0-9]{4}$`, status·retryable 명시, `validate_contract("ProblemDetails")` 앵커). business `InvError`는 route별 `translate(error, table=…)`로 번역하고 표에 없는 code는 `SYS-0002`. 이 설계가 새로 만드는 code는 **0개**: `VAL-0003`(요청), `AUTH-0030`(membership/canApprove), `RES-0004`(404), `GRAPH-0002`(전제 위반: 미종료 run 봉인·미검증 artifact pin·digest 불일치·pin 단축), `SYS-0002`.
- **strict 요청**: `read_bounded_body`(8 KiB) → `strict_json_object` → `validate_strict(Strict 모델)`; FastAPI annotation body 금지(#158 §9-4). GET은 body 금지(`require_absent_body`).
- **path→row 결속**: path의 `{project_id}`와 row가 가리키는 project가 다르면 **같은 404**(`RES-0004`, "No such …")— #175 `_version_in_project`와 동일. run 계열은 `_run_in_project(session, tenant, project, run_id)`를 **한 곳**(새 helper, `lineage_query.py` 옆)에 두고 R1~R3·W1이 공유.
- **존재 비노출 404**: 부재·다른 project·다른 tenant·path 불일치 모두 같은 body(#158 §6-6).
- **strict 응답**: `Strict`(extra forbid) 파생 `*Response`만; 응답에 사람 식별자·자유 텍스트 없음(#175 `LineageDeployment` 주석과 같은 원칙). `content`(bundle 본문)는 R3에서 **길이·sha만**, 본문은 별 route로 미룸(§9).

## 4. 멱등 키(IDEM) — 쓰기 4(봉인·등록·검증·pin) + 실행 1

원장은 `idempotency_records`(§1)이고 helper는 `deps.replay_or_reserve`/`store_idempotent_response`다. 규칙:

| 규칙 | 내용 |
|---|---|
| IDEM-1 | `Idempotency-Key` 헤더는 W1~W5에서 **필수**(없으면 `VAL-0003` 422). 길이·문자는 원장 열(`String(128)`)에 맞춤 |
| IDEM-2 | 원장 키 = `(tenant_id, project_id, endpoint, idempotency_key)`; `endpoint`는 route 상수(예 `POST:/projects/{p}/runs/{run}/record`) |
| IDEM-3 | 같은 키 + 같은 `request_sha256` → **저장된 응답을 재생**(status 포함), 서비스 미호출. 같은 키 + 다른 body → `GRAPH_IDEMPOTENCY_CONFLICT` 번역 `GRAPH-0002` 409 |
| IDEM-4 | 원장 기록은 **서비스 tx와 같은 tx**에서 commit(둘 중 하나만 남지 않게). 실패(4xx/5xx)는 원장에 남기지 않는다(재시도 허용) |
| **IDEM-6 (Codex F4)** | 현재 helper는 예약하지 않는다: `deps.py:81 replay_or_reserve()`는 **조회만**(FOR UPDATE·placeholder INSERT·advisory lock 없음)이고 `store_idempotent_response()`는 서비스 뒤 INSERT → 동시 최초 같은 키 2건이 둘 다 서비스를 실행하고 하나가 unique error가 된다. W1~W5 공통 **직렬화점**: tx 진입 직후 `pg_advisory_xact_lock(hash(tenant, project, endpoint, idempotency_key))`(deterministic, tx-scoped)를 잡고 그 **뒤에** 원장을 조회한다 — 두 번째 요청은 첫 tx commit을 기다린 뒤 저장 응답을 **exact replay**(status+body). unique violation은 정상 흐름이 아니며(부정 시험: 동시 최초 2건 → 서비스 호출 1·원장 1·unique error 0), **lock 순서는 모든 route에서 이 직렬화점 → resource row(FOR UPDATE)** 순으로 고정한다 |
| IDEM-5 | 자연 멱등과 겹칠 때: W2 등록은 `uq_model_versions_tenant_id_content_sha256`가 있어 같은 digest 재등록이 서비스에서 거부됨 — 키가 다르면 거부(409), 키가 같으면 재생. W4 pin은 `until`이 더 짧으면 서비스가 no-op(“never shortens”) — 키 규칙은 그대로 |

## 5. 서비스 시그니처·tx·lock 순서 — Codex 계약 지점

| route | 시그니처(변경 여부) | tx/lock 순서 | 난도 | 결정 |
|---|---|---|---|---|
| R1~R3 | `get_record`, `list_pinned_artifacts(role=)`, `verify_pin`, `read_bundle`, `verify_bundle` **변경 0** | 읽기 1 tx: `tenant_scope` → `require_project_access` → `_run_in_project` → 서비스 | 낮음 | Claude 구현 |
| W2 register | `register_model_version(session, tenant_id, model_id, version, content_sha256, uri, now, byte_size, produced_by_run_id, lineage)` **변경 0** | 1 tx: access(canApprove) → `Model` row가 path project인지 → 서비스(UNIQUE가 2차 방어) → IDEM 저장 | 중 | Claude 구현 |
| W3 verify | `verify_model_version(…, content_sha256, now)` **변경 0** | (보류) 잠금은 W4와 같은 `_locked_version` 한 행; **digest는 request가 아니라 trusted worker의 측정 Evidence에서** 와야 함 | **높음(보안: 측정 신원)** | **보류** — seam 결정 후 |
| W4 pin | `pin_retention(…, until)` **변경 0**(단, 잠금 전 값을 읽는 경로 금지 — route가 잠근 row를 넘김) | **Codex F3 계약(§5-3)**: idempotency 직렬화 → live canApprove → Model parent path 결속 → **ModelVersion 한 행 FOR UPDATE + populate_existing** → canApprove 재확인 → `max(current, until)` → ledger. #167 release·W3도 같은 `_locked_version`만 사용(parent read 후 ModelVersion 한 행) | **높음(동시성)** | 계약 고정됨(v1.2) → 구현 가능 |
| W1 seal | `seal_run_record(…)` 호출은 유지하되 **인자는 서버 파생**(§5-2) | **Codex F2 계약(§5-2)**: READ COMMITTED + 명시 잠금, 6단계 순서 고정, 기존 record는 canonical seal intent 비교로 자연 멱등/409, IntegrityError 500 금지, lock timeout `SYS-0001/503 retryable` | **높음(동시성·보안: 영구 기록)** | 계약 고정됨(v1.2) → 구현 가능 |
| W5 eval run | `run_suite(session, tenant_id, suite_id, adapter, now, component_versions, require_model_pinning)` **변경 0**; adapter = `adapter_for(name)` | **project 결속 불가**(§2): `eval_suites`에 `project_id`가 없다 → route가 `/projects/{p}/…`로 path→row를 묶을 수 없다 | 구조 | **persistence 필요 → §5-1** |

### 5-2. W1 seal 계약 (Codex F2, v1.2 고정)

격리 수준 **READ COMMITTED + 명시 잠금**(SERIALIZABLE 불요). 한 tx에서 순서 고정:

1. `tenant_scope` + 저비용 live `canApprove` preflight.
2. `(tenant, project, endpoint, Idempotency-Key)` **직렬화점**(IDEM-6 advisory lock) 확보 → 원장 조회(있으면 exact replay 또는 `GRAPH-0002/409`).
3. `runs` 대상 행 **`FOR UPDATE` + `populate_existing`**, path→`workload.project` 재결속, terminal 상태·최종 필드 재확인.
4. live `canApprove` **재확인**(회수 TOCTOU).
5. bundle/workload와 artifact를 **서버 정본에서 읽고**, 변경 가능한 행(`artifacts`)은 **`artifact_id` 오름차순으로 잠근 뒤** active/verified/run 결속 재확인. **봉인 대상 artifact 집합은 서버가 run 정본에서 완전하게 파생한다**: 그 run의 `artifacts` 중 `status='active'`이고 `checksum_sha256`이 있는 행 **전부**(v1.2.1, Codex 조건). request는 그 집합의 각 artifact에 대한 **role 매핑만**(`roles: {artifact_id: role}`) 줄 수 있다 — 매핑이 없는 서버 파생 artifact는 `other`로 봉인되고, 서버 집합에 없는 artifact_id를 매핑하면 `GRAPH-0002/409`(누락도 추가도 불가). `component_versions`·checksum·`bundle_id`·`workload_spec_sha256`은 서버가 파생. 서비스 `seal_run_record(artifacts=…)`에는 route가 **서버 파생 집합 + role**로 만든 `ArtifactPin` 목록을 넘긴다(서비스 시그니처 변경 0). 일부 선택 봉인은 제품 의도가 아니며 지원하지 않는다.
6. 기존 RunRecord 확인 → 없으면 record + pin + idempotency 응답을 **같은 tx**에 기록. 있으면 **canonical seal intent = 서버 파생 artifact 집합에 role을 입힌 정렬된 (artifact_id, role, checksum) 집합 + 파생 값**과 저장된 record+pin 집합을 비교해 **동일할 때만 자연 멱등 성공**, 다르면 `GRAPH-0002/409`.

`uq_run_records_run_id`(`0003:174`)는 최후 방어이지 정상 직렬화 수단이 아니다. IntegrityError가 raw 500으로 새거나 pin 일부가 남으면 안 된다(한 tx). 오류 표: 동일 키·동일 body → exact replay; 동일 키·다른 body → `GRAPH-0002/409`; lock timeout/deadlock → 값 비노출 **`SYS-0001/503/retryable=true`**; 그 밖 전제 위반 → `GRAPH-0002/409`.

**되살림 시험(독립 PG session + barrier)**: (a) 동일 intent 동시 2건 → record 1·pin 집합 1·양쪽 성공 또는 exact replay; (b) 다른 intent 동시 2건 → 승자 1·패자 409·부분 pin 0; (c) terminal 전환과 봉인 경합 → 잠금 뒤 최신 상태만 봉인; (d) 권한 회수 대기 뒤 최종 재검사 403. mock Session만으로는 lost-update 되살림을 죽인 것으로 세지 않는다.

### 5-3. W4 pin / release / verify 잠금 계약 (Codex F3, v1.2 고정)

READ COMMITTED. 순서: **idempotency 직렬화점 → live canApprove → Model parent path 결속 → ModelVersion 단일 행 `FOR UPDATE` + `populate_existing` → live canApprove 재확인 → `max(current, until)` → ledger**. `pin_retention()`이 잠금 전 값을 읽는 경로는 금지: route가 **이미 잠긴 최신 row**를 넘기고 서비스는 그 row만 본다(route↔service 불변식). #167 release와 W3 verify도 같은 `_locked_version`만 사용 → 잠금 순서는 항상 **parent read 후 ModelVersion 한 행**.

| 경합 | 기대 |
|---|---|
| pin 먼저 | release는 기다린 뒤 새 pin을 본다 |
| release 먼저 | pin은 기다린 뒤 released row의 retention만 연장 |
| 짧거나 같은 `until` | 200 no-op, 절대 단축 없음 |
| 서로 다른 두 연장 | commit 순서와 무관하게 최종값 `max(old, a, b)` |
| idempotency conflict / lock timeout·deadlock | `GRAPH-0002/409` / `SYS-0001/503/retryable=true` |

시험(독립 PG session + barrier): 역순 commit 두 경우, verify↔pin, release↔pin, shorter no-op.

### 5-1. persistence·index 판정

- R1~R3·W1~W4: **migration 없음**. 조회는 PK/UNIQUE(`uq_model_versions_tenant_id_content_sha256`, run_records PK) 경로. 새 index 0.
- **W5: migration 필요.** 최소안 = `eval_suites.project_id`(nullable, composite FK `(tenant_id, project_id)` → `projects`; 기존 suite는 NULL이며 route는 NULL suite를 404로 취급) + `eval_runs`는 suite로 전이. 대안(tenant 범위 route + canApprove)은 #158 §1-4·Codex F-R1("범위 표시만으로는 권한이 생기지 않는다")과 충돌해 채택하지 않는다. **코디네이터 결정(2026-09-28 14:21 KST, PR #183 코멘트; 2026-09-28 PR #191 코멘트로 번호 교체): W5 migration 번호 `0053`, `down_revision = 0052_model_version_digest_scope`(#197, #191 F1 유일성).** 중앙 순서 0047(#128)→0048(#159)→0049(#172)→0050(#174)→0051(#176)→0052(#191 F1)→0053(W5). W5 선행 migration PR은 #197 head 위에 stack, W5 route PR(8)은 #191 승인 뒤 그 위에 stack; 최소안이 검토에서 바뀌면 번호는 유지하고 내용만 갱신. 다른 PR은 0053을 쓰지 않는다.

## 6. 계약 변경 범위와 FE 영향

- `src/saintvision/api/schemas.py`에 `Strict` 파생 추가: `RunRecordResponse`, `RunRecordArtifactPageResponse`, `ArtifactPinVerificationResponse`, `ContextBundleResponse`, `RunRecordSealRequest`/`…Response`, `ModelVersionRegisterRequest`/`ModelVersionResponse`, `ModelVersionVerifyRequest`, `RetentionPinRequest`, (W5) `EvalRunStartRequest`/`EvalRunResponse`. `python tools/export_schemas.py`가 `contracts/<kebab>.schema.json`을 만들고 `--check`가 drift를 막는다(`tools/export_schemas.py:11-33` 규칙). `check_contract_bindings`·`check_response_freshness` 통과가 각 PR의 게이트.
- openapi: FastAPI가 자동 생성; #175처럼 `register(router)` 함수로 `api/app.py`에 include(#175 pattern).
- **FE(Gemini owner)**: 생성된 `apps/web/src/contracts/*.ts`가 늘어난다(현재 `ModelLineageView.tsx`만 lineage route 사용). 화면은 **만들지 않는다**; Gemini에게 route·계약 목록만 인계한다.
- kernel(`inv`)과의 중복: `services/control-plane/src/inv/app.py`에 run_record·seal·bundle·eval route **없음**(git grep 0건) → business surface 전용.

## 7. 부정 시험 — 되돌리면 실패해야 하는 것 (route별 공통 + 개별)

공통(모든 route): (a) membership 없음 → 403 `AUTH-0030`, (b) 다른 project의 row를 path로 → 404 `RES-0004`(존재 비노출, body 동일), (c) 다른 tenant → 404, (d) body 있는 GET → 422 `VAL-0003`, (e) `additionalProperties` → 422, (f) 응답이 `Strict` 계약을 통과(`validate_contract`), (g) `InvError`가 표 밖 code → `SYS-0002`. 쓰기 공통: (h) `canRequest`만 있는 principal → 403, (i) IDEM 헤더 없음 → 422, (j) 같은 키·다른 body → 409, (k) 같은 키·같은 body → 재생(서비스 호출 0, DB 행 증가 0), (l) 권한 통과 뒤 회수 → 잠금 뒤 재확인에서 403이고 정본 불변(#152 F-R5).
동시성(§5-2·§5-3, 독립 PG session+barrier, mock 불인정): W1 (a)~(d); W4 역순 commit 2·verify↔pin·release↔pin·shorter no-op; IDEM-6 동시 최초 2건 → 서비스 1·원장 1·unique error 0.
개별: R2 `verify_pin` digest 불일치 → `verified:false`(200, 사실 보고; 실패 아님); R3 hash 불일치 → `hashVerified:false`; W1 미종료 run → 409 `GRAPH-0002`·기록 0, 미검증 artifact → 409, 다른 run의 bundle_id → 409, **동시 봉인 2 → 1행**(Codex 계약); W2 같은 digest 재등록(다른 키) → 409, `content_sha256` 대문자 → 422; W3 digest 불일치 → 409·`verified_at` NULL 유지; W4 더 짧은 until → 200 no-op(`retention_pinned_until` 불변), **동시 연장 2 → max 유지**(Codex 계약); W5(번호 뒤) adapter 이름 미지 → 422, `MODEL_PINNING` 없는 adapter + `requireModelPinning:true` → 409.

## 8. 구현 PR 분할 순서 (각 PR = route 1 + 시험 + 계약)

| 순서 | PR | 의존 | 비고 |
|---|---|---|---|
| 1 | R1 RunRecord 조회 + `_run_in_project` helper | #175 병합(helper import) | 가장 작음, helper의 첫 소비자 |
| 2 | R2 pin 조회·검증 | 1 | |
| 3 | R3 Context bundle 조회(메타+hashVerified) | 1 | 본문 노출은 별 카드(§9) |
| 4 | W2 model version 등록 | #167 병합(`_require_approval`) | IDEM 첫 소비자 |
| 5 | W3 verify | **보류** | trusted measurement seam(측정 신원·Evidence 결속) 결정 뒤 |
| 6 | W4 pin_retention | 4 | §5-3 계약 고정됨 |
| 7 | W1 seal | 1 | §5-2 계약 고정됨(서버 파생 integrity) |
| 8 | W5 eval 실행 | **migration 번호** + 4 | |

## 9. 범위 밖 · 미해결

- bundle 본문(`content`) 노출 route: 비밀 스캔(`context.py:71 _refuse_recognised_secrets`)이 저장 시점에만 있어 읽기 노출은 별 결정.
- 봉인 시 outbox/mirror 훅 여부(#172의 `enqueue_mirror`는 lineage·eval에만) — 봉인은 미러 대상 아님(설계 #168 §1 표에 없음).
- **Codex 설계 판정(v1.2 반영)**: F1 등급 최종(W2·W4·W5 canApprove 승인, W1 필요조건+서버 파생, **W3 보류**), F2 W1 계약(§5-2), F3 W4 계약(§5-3), F4 IDEM 예약(IDEM-6). 실 PG 계약 시험은 각 구현 PR에서 독립 PG session+barrier로.
- **코디네이터 결정(v1.1, 2026-09-28 #191 결정으로 갱신)**: W5 migration 번호 **0053**(§5-1; 0052는 #191 F1 유일성). canApprove 통일 잠정 승인은 v1.2 Codex 최종 판정으로 대체됨(위 항목).
- **최종 상태(v1.2.1)**: W2·W4·W5 = canApprove 확정, **W4 구현 차단 해제**; W1 = canApprove + 서버 파생 완전 artifact 집합(§5-2 5항)으로 계약 확정, 구현 가능; **W3 = 보류**(trusted-worker 실제-byte 측정 Evidence seam 전). R1(#184)·R2(#188) draft는 이 판정과 정합.
- owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/g04-g05-business-routes-design`, base `1e8baf04`, force-push·`git add -A` 없음. 시각은 `date`.
