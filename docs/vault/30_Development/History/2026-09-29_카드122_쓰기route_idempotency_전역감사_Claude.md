---
doc_id: "HIST-CLAUDE-CARD122-WRITE-ROUTE-AUDIT-001"
title: "src/saintvision/api 전역 쓰기 route 감사 — release가 idempotency 없이 나간 것과 같은 부류가 다른 POST/PUT/DELETE에 있는가 (카드 122)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-29T01:40:55+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["G-04"]
tags: ["g-04", "idempotency", "audit", "lock-wait", "claude"]
---

# 쓰기 route 전역 감사 (카드 122)

#229(카드 113)에서 release route가 W2/W4와 달리 서버 idempotency 없이 나갔던 것을 계기로, `src/saintvision/api` 아래 **모든 POST/PUT/DELETE 28개**를 같은 잣대로 훑었다. 기준 tree는 #229 branch head `41fe5c3c`(= 착지 후보 `b91ab72f` + #221 + #229; 감사 대상 파일은 두 tree에서 같은 blob). 판정 항목은 카드가 정한 10개: ① `Idempotency-Key` 소비 ② canonical hash(`request_digest`) ③ replay ④ 같은 key·다른 payload 409 ⑤ ledger 같은 tx ⑥ `serialise_idempotent_write`(IDEM-6 advisory lock) ⑦ #211 `bounded_lock_wait` ⑧ live 권한 재확인(쓰기 tx 안) ⑨ 공용 canonical denial audit(`app.py` `_record_denial`, AUTH/SEC 범주만) ⑩ 존재 비노출 404 ⑪ strict 요청·응답.

읽은 방법: 각 파일을 실제로 열어 handler·service를 대조했고(세 묶음은 보조 agent가 먼저 읽고 Claude가 High·핵심 인용을 `git grep`/`sed`로 재확인), pytest는 단일 파일만 돌렸다. 아래 file:line은 `41fe5c3c` 기준.

## 1. 결론 요약

| 부류 | route | ①~⑥ | ⑦ | 판정 |
|---|---|---|---|---|
| **business lane**(add_api_route, 카드 84·113·#211) | eval_runs·model_versions·model_verify·model_retention·model_release·run_seal 6개 | **전부 O** | 5개 O, **eval_runs X** | eval_runs만 이 PR에서 수정 |
| **legacy lane**(`@router.*`, `get_session` 단일 tx) | nodes 3·pools 7·projects 3·settings 6·storage 3 = 22개 | **21개 X**(storage 등록 1개만 선택적 O) | **22개 전부 X** | Claude 소유 아님 → §4 인계 |

release와 "같은 부류"(쓰기 route인데 ①~⑥이 없는 것)는 legacy 22개 전부다. 다만 재시도 시 side effect 중복 **위험 High**는 그중 하나뿐(discovery admit)이고, 나머지는 자연 멱등(upsert/delete-if-exists/유일 제약)이거나 중복이 audit 1행·version 증가·timestamp 재기록에 그친다(Medium/Low). 특히 FE `apps/web/src/shared/api/client.ts`는 Gemini 2026-09-12 보고대로 mutation에 `Idempotency-Key`를 주입하는데, legacy 22개는 그 헤더를 **읽지 않는다**(nodes enroll은 선언만 하고 미사용 `nodes.py:56`) — 클라이언트가 안전한 재시도로 오인할 수 있는 지점이다.

## 2. business lane (6) — 항목별

| route | file:line | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | ⑧ | ⑨ | ⑩ | ⑪ | 재시도 중복 위험 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| POST …/eval/suites/{s}/runs | `eval_runs.py:210`(등록 `:364`) | O 필수 `:130` | O | O | O | O `:341` | O `:259` | **X → 이 PR에서 O**(두 span) | O `_require_approval` ×3 `:234,268,301` | O | O `RES_NOT_FOUND` 404 `:181` | O `strict_json_object`/`validate_strict` | Low — ledger replay; 수정 전엔 key·row 대기가 무한 |
| POST …/models/{m}/versions | `model_versions.py:286`(`:447`) | O `:192` | O | O | O | O `:424` | O `:340` | O `:312,335` | O `:315,350` | O | O `:219` | O | Low |
| POST …/versions/{v}/verify | `model_verify.py:315`(`:457`) | O | O | O | O | O `:440` | O `:360` | O `:330,357` | O ×3 | O | O `:198,245` | O | Low |
| POST …/versions/{v}/retention-pin | `model_retention.py:141`(`:282`) | O | O | O | O | O `:265` | O `:185` | O `:159,182` | O ×3 | O | O | O | Low |
| POST …/versions/{v}/release | `model_release.py`(#229) | O | O | O | O | O | O | O ×3 | O ×4 | O | O | O | Low(#229) |
| POST …/runs/{r}/record | `run_seal.py:260`(`:422`) | O `:137` | O | O | O | O `:405` | O `:296` | O `:276,293` | O ×3 | O | O `:160,163` | O | Low |

eval_runs ⑦: `tests/core/test_lock_wait.py`의 ratchet `test_every_transaction_span_of_every_write_route_is_bounded_and_no_copy_exists`가 module 목록에 eval_runs를 넣지 않아 #211이 이 route를 비켜갔다. 실 PG `test_lock_wait_real_pg.py`에도 W3 case가 없었다.

## 3. legacy lane (22) — 항목별

①~⑥은 storage 등록(⑦행) 외 **전부 X**(`Header`·`replay_or_reserve`·`serialise_idempotent_write` 미import: projects·settings·pools 0건). ⑦은 22개 전부 X(`get_session` `deps.py:61-74`는 `SET LOCAL lock_timeout` 없음). 아래는 ⑧~⑪과 위험만.

| route | file:line | ⑧ live 권한 | ⑨ denial audit | ⑩ 비노출 404 | ⑪ strict | side effect | 재시도 중복 위험 |
|---|---|---|---|---|---|---|---|
| POST /nodes enroll | `nodes.py:48` | X(bootstrap token 조건부 UPDATE가 곧 인증) | O(VAL은 범주상 미기록) | n/a | O | Node·capabilities·offers·audit `:106` | **Low-Med** — token 1회성이라 중복 행 0, 그러나 재시도는 실패하고 node id 복구 불가; `Idempotency-Key` 선언만 하고 미사용 `:56` |
| POST /nodes/{n}/heartbeats | `nodes.py:125` | 부분(인증 별도 tx, 쓰기 tx는 row lock) | O AUTH_NODE_MISMATCH | 부분 — 타 tenant → RES_NODE_NOT_FOUND **409** | O | 조건부 UPDATE, observations | Low — sequence guard로 replay는 `applied:false` |
| POST /nodes/liveness-sweeps | `nodes.py:209` | X | n/a | n/a | O | bulk lost + audit(변경 시만) `:239` | Low — 두 번째 sweep은 변경 0 |
| POST /discovery/announcements | `pools.py:47` | 부분(machine: grant FOR UPDATE; user: tenant 동일성만) | O | O | O | upsert + credential event | Low — upsert; event 1행 추가 |
| **POST /discovery/candidates/{id}/admission** | `pools.py:245` | X(`get_principal`만) | 부분(RES 409 미기록) | 부분 409 | O | **bootstrap token 발급** `services/discovery.py:261-`(`issue_bootstrap_token` 후 state는 candidate 유지 `:290-293`) + audit `:273` | **High** — 응답 유실 뒤 재시도가 **두 번째 유효 token**을 발급하고(첫 token은 TTL까지 살아 있음) audit 2행; row lock 없어 동시 admit 둘 다 성공 |
| DELETE /discovery/candidates/{id} | `pools.py:294` | X | 부분 409 | 부분 409 | O | state=declined, revoke(멱등 filter) | Low — `decided_at` 재기록만 |
| POST /pools | `pools.py:324` | O `require_project_access` `:335` | O AUTH-PROJECT-SCOPE | O | O | ResourcePool insert(audit 없음) | **Medium** — `uq_resource_pools_tenant_id_name`(`db/models/discovery.py:131`)이 두 번째 행을 막지만 미번역 IntegrityError → 500, pool id 복구 불가 |
| PUT /pools/{p}/members/{n} | `pools.py:354` | **X — project 검사 없음**(tenant 동일성만) | 부분 409 | 부분 | O | get-or-insert PK | Low(순차) / 동시 최초 2건은 IntegrityError 500 |
| DELETE /pools/{p}/members/{n} | `pools.py:377` | **X — pool 존재 확인도 없음** | n/a | X(`removed:false`로 통일) | O | delete-if-exists | Low |
| POST /pools/{p}/plans | `pools.py:445` | **X — project 검사 없음** | 부분 | 부분 | O | DistributedPlan + placements | **Medium** — `uq_distributed_plans_run_id`가 중복 막고 500; planId 복구 불가 |
| POST /projects | `projects.py:80` | O(User FOR SHARE + status) | O | n/a(중복 code → 422) | O | Project + audit `:108` | Low — 유일 제약 422, audit 중복 없음 |
| POST /projects/{p}/workspaces | `projects.py:162` | O `lock_project`+canRequest | O | O(403 통일) | O | Workspace + audit `:190` | Low — name 유일 422 |
| PUT /workspaces/{w}/tool | `projects.py:205` | O | O | 부분(RES_NODE_NOT_FOUND 409) | O | tool set, version+1, audit `:233` | Medium — 값 멱등, version·audit 중복 |
| PUT /projects/{p}/members/{u} | `settings.py:99` | O `require_administrator` | O | 부분 | O | upsert + audit | Medium — audit 중복 |
| DELETE /projects/{p}/members/{u} | `settings.py:133` | O | O | 부분(부재도 `removed:true`) | O | delete + audit | Medium — audit 중복·거짓 `removed:true` |
| PUT /users/{u}/status | `settings.py:169` | O(preflight, row FOR UPDATE 보유) | O | 부분 409 | O | status + audit | Medium — audit 중복 |
| PUT /projects/{p}/status | `settings.py:208` | O | O | O(403 통일) | O | status, version+1, audit | Medium |
| PUT /workspaces/{w}/status | `settings.py:236` | O | O | 부분 409 | O | status, version+1, `deleted_at` 재기록, audit | Medium |
| PUT /capabilities/{c}/offer | `settings.py:292` | O ×2(route+service) | O | 부분 409 | O | offer row, `apply_capability_offer`(inv.resources 쓰기), audit | Low-Med — 같은 수량은 short-circuit, kernel apply·audit은 매번 |
| POST /storage/contributions | `storage.py:65` | X(tenant 존재만) | O(VAL/RES 미기록) | 부분 409 | O | contribution + audit `:113` + **ledger** `:130` | **Medium** — ①~⑤ O이나 **key 선택적**(없으면 ledger 우회, 422 아님 `:77`), ⑥ 없음(동시 최초 2건은 `deps.py:91-97`이 적은 그 race), key 없는 재시도는 `uq_storage_contributions_node_id_normalized_path`(`db/models/storage.py:54`) IntegrityError 500(번역 handler 없음) |
| POST /storage/contributions/{id}/activation | `storage.py:145` | X | 부분 409 | 부분 409 | O | status=active(audit 없음) | Low |
| DELETE /storage/contributions/{id} | `storage.py:160` | X | 부분 409 | 부분 409 | O | status=revoked, `revoked_at` 재기록(audit 없음) | Low |

교차 발견(legacy 공통): (a) `RES_*` InvError는 RESOURCE 범주 기본 **409**(`errors.py:51`)라 "없음"이 404가 아니고 `DENIAL_CATEGORIES=("AUTH","SEC")`(`app.py:101`)에도 안 들어 기록되지 않는다 — business lane의 `CanonicalProblem(RES_NOT_FOUND, 404)` 규칙과 다르다. (b) IntegrityError 번역 handler가 `app.py`에 없어 유일 제약 충돌은 500이다. (c) pools 멤버·plan 3 route는 project 권한 검사가 없다(tenant 안 모든 principal이 모든 pool을 조작).

## 4. 조치와 인계

**이 PR(Claude, eval_runs ⑦)**: `eval_runs.py` 두 span에 `bounded_lock_wait(session, timeout_ms=settings.business_lock_timeout_ms)` 추가(다른 5 route와 같은 형태). 되돌리면 실패하는 시험: `tests/core/test_lock_wait.py` ratchet module 목록에 `eval_runs` 추가(span 수 == bound 수), `tests/core/test_eval_run_route.py::test_card122_both_spans_bound_their_lock_waits`(SET LOCAL 2회, preflight span의 유일 statement, 쓰기 span에서 advisory lock 직전), 실 PG `tests/integration/test_lock_wait_real_pg.py` W3 2건(key 보유 → SYS-0001/503 within budget·eval_runs 0·ledger 0; 호출자 user row 보유 → 503). PG-free stub은 `SET LOCAL`을 "lock"으로 세지 않게 정정(순서 시험 보존).

**Codex 인계(보안·동시성·identity 소유, 카드 122 목록)** — 위험 순:
1. **High** `POST /discovery/candidates/{id}/admission`: 재시도가 두 번째 bootstrap token을 발급. 제안: announcement row `with_for_update()` + 이미 admitted(`admitted_by_user_id`)면 기존 미소비 token 재제시 또는 409; 또는 business lane 계약(필수 key + ledger) 적용.
2. **Medium** `POST /pools`·`POST /pools/{p}/plans`·`POST /storage/contributions`(key 없음)·`PUT /pools/{p}/members`(동시): 유일 제약 IntegrityError → 500. 제안: `app.py`에 IntegrityError → 409 canonical 번역 handler, 또는 route별 사전 조회.
3. **Medium** 권한: pools 멤버 추가/제거·plan 생성에 project 권한 검사 부재.
4. **Medium** legacy 7개 PUT/DELETE의 audit 중복(값은 멱등). 제안: FE가 이미 보내는 `Idempotency-Key`를 legacy lane도 소비(필수 아닌 선택적 ledger라도)하거나, 최소한 nodes enroll의 미사용 헤더 선언 제거.
5. **Low/설계** legacy `RES_*` 409 vs canonical 404, `DENIAL_CATEGORIES` 밖 미기록, `bounded_lock_wait` 미적용(`lock_project` FOR UPDATE 대기 무한).

## 5. 검증 (실제 수행한 것만)

로컬 PG-free 단일 파일: `tests/core/test_eval_run_route.py` + `tests/core/test_lock_wait.py` = 97 passed. 실 PG `test_lock_wait_real_pg.py` 13 collected(신규 2 포함) — **NOT_OBSERVED**, hosted Backend 인용은 PR 코멘트. 게이트 chain exit 0. 감사표의 legacy 인용은 파일 열람과 `git grep`으로 확인했고, pools admit·create_pool·storage 등록·`errors.py` 상태표·`app.py` 범주는 Claude가 직접 재확인했다.

## 6. 다음

1. hosted Backend·Core(run-core) green 인용 → Codex 검토(코드 + §4 인계 목록 수용 여부).
2. §4-1 High는 Codex 카드로; 수용되면 Claude가 실 PG replay 시험 작성 지원.
