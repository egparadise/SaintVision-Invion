---
doc_id: "HIST-CLAUDE-G04-W3-VERIFY-ROUTE-001"
title: "G-04 W3 verify route (PR B) — 측정을 요청하고 kernel 기록만 소비하는 3-span write"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T20:23:58+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["G-04"]
tags: ["g-04", "w3", "route", "lineage", "claude"]
---

# G-04 W3 verify route (PR B)

카드 88. 설계 #209 v1.1 §6 그대로: `POST /projects/{p}/models/{m}/versions/{v}/verify`, body `{measurementId}`만, grade canApprove, 3 span. #213(0054, head ccb35a87) 위에 #211(lock-wait bound, d0306f1e) merge를 얹은 branch에서 구현했다 — `_locked_version`·`bounded_lock_wait`·IDEM-6 helper가 모두 그 tree에 있다.

## 1. 들어간 것

- `src/saintvision/api/v1/model_verify.py` — (1) 짧은 bounded tx: live canApprove → (2) tx 없이 kernel `GET …/measurements/{id}`(caller bearer, `_RefuseRedirect` 공유, 64 KiB bound, 5 s; kernel 404 → 이 route의 404; 그 밖의 실패·redirect·oversize·계약 위반 → `SYS-0001/503/retryable`) → strict `ModelMeasurementObservation`(unknown key 거부) → (3) bounded write tx: IDEM-6 advisory lock → live canApprove → clock 1회 → ledger replay/reserve → `_locked_version`(parent read → `FOR UPDATE/populate_existing`) → live canApprove 재확인 → **identity 재결속**(measurementId·tenant·project·model·modelVersionId·uri = 요청·row; 불일치는 동일 404) → **storage snapshot 재확인**(`resolve_location(row.uri)`가 `kind='model'`·`ready`·같은 location_id/version/relative_path/contribution_id; contribution `active`·같은 version·node; 그 node의 `ready` replica) → **freshness**(`observedAt ≤ recordedAt ≤ now`, `now − observedAt ≤ Settings.model_measurement_max_age_seconds`) → `verify_model_version(measurement_id, content_sha256=observation.sha256)` → 서비스가 잠근 row를 돌려줬는지 identity 단언 → audit `model_version.verify`(detail은 id만) → ledger. 이미 같은 measurement로 검증된 row는 200 `newlyVerified: false`.
- 오류 표: identity 불일치·kernel 404·서비스 not-found = `RES-0004/404`(고정 detail); snapshot drift·digest/size 불일치·stale·둘째 measurement·같은 key 다른 요청 = `GRAPH-0002/409`(값 비노출 고정 detail); kernel 문제 = `SYS-0001/503`; lock wait = `SYS-0001/503`(card 84 helper); 권한 = `AUTH-0030/403` + denial 1행(#195).
- `schemas.ModelVerifyRequest`(`measurementId`만, extra forbid), `schemas.ModelMeasurementObservation`(설계 §6 19 필드, StrictInt·AwareDatetime·id 패턴), `schemas.ModelVerifyResponse`; contracts 2개 export.
- `Settings.model_measurement_max_age_seconds`(기본 86400, `__post_init__`에서 1..31536000 정수 검증, env `INV_MODEL_MEASUREMENT_MAX_AGE_SECONDS`).
- `projects.py`에 `model_verify.register(router)`; `tests/core/test_lock_wait.py` ratchet에 module 추가.

## 2. 판단한 것

- **관측 계약을 kernel catalog(`validate_contract`)가 아니라 business pydantic `Strict` schema로 검증했다.** kernel `core.schema.json`은 ontology 생성물(`tools/generate_contracts.py`, kernel 소유)이고 measurement GET endpoint 자체가 PR A-2(kernel + Go node-agent, owner 결정 대기)다. 설계의 핵심(strict·unknown key 거부·필드 집합)은 그대로이고, A-2가 kernel `$def`를 추가하면 한 줄로 `validate_contract`로 바꿀 수 있다. **설계 §6 문구와 다른 판단** — 코디네이터·Codex 확인 요청.
- kernel HTTP 404는 route 404로(measurement 없음), 그 외 HTTP 오류는 503. 존재 여부 외 어떤 값도 응답에 싣지 않는다.
- byte_size는 서비스가(0054 R1, sentinel 없음) measurement 행과 대조하고, route는 관측 `sha256`만 넘긴다(caller 값 0개).

## 3. 검증 (실제 수행한 것만)

로컬(공유 venv 3.14, PG 없음, 단일 파일): `tests/core/test_model_verify_route.py` **90 passed / 0 failed**(§6 순서·2 span·body depth 0·caller bearer·관측 digest 전달; body에 digest/size/uri → 422; 관측 계약 11 부정(worker 신원 없음 포함) → 503; kernel 불가·redirect·오버사이즈·미설정 → 503, kernel 404 → 404; identity 6 부정 → 404; path 5 부정 → 404; snapshot drift 14 → 409/404 값 비노출; freshness 4 → 409; Settings 범위 6 거부; 서비스 거부 4 번역; 권한·revocation·무토큰 denial 1행; replay·409·ledger payload; 55P03/40P01 → 503). `tests/core/test_lock_wait.py` 30 passed(ratchet에 model_verify 포함), `tests/core/test_model_retention_pin_route.py` 42 passed. `tests/integration/test_model_verify_real_pg.py` 20 collected(실 PG **NOT_OBSERVED** — hosted 인용은 PR 코멘트). `check_contract_bindings` 통과.

## 4. 다음

1. hosted Backend green 인용 → Codex 재검토.
2. #213 R1 Codex 결과·#177 새 head(AC-11 manifest 0054 분류) 반영 시 이 branch도 #213 head를 다시 merge.
3. PR A-2 owner 결정 뒤 kernel endpoint + `validate_contract` 전환.
