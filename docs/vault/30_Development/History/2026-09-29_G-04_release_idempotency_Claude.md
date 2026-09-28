---
doc_id: "HIST-CLAUDE-G04-RELEASE-IDEMPOTENCY-001"
title: "release route에 W2/W4와 같은 서버 idempotency 계약 — 응답 유실 뒤 재시도가 stage 재기록·mirror intent 중복을 내지 않는다 (카드 113)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-29T00:39:01+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["G-04"]
tags: ["g-04", "idempotency", "release", "model-registry", "claude"]
---

# release route idempotency (카드 113)

Codex #219 r4 F1: `POST /projects/{p}/models/{m}/versions/{v}/release`(`src/saintvision/api/v1/model_release.py::release_model`)에 W2(`model_versions.py`)·W4(`model_retention.py`)가 가진 서버 idempotency 계약이 없어, 응답 유실 뒤 재시도가 `services/lineage.py::release_model_version`의 stage 재기록과 `enqueue_mirror(release_mirror_payload)` 중복을 냈다. base는 #221 head `2f853a94`(착지 전이라 그 branch에 stack), branch `agent/claude/release-idempotency`. **migration 없음**(원장 `idempotency_records`·advisory lock을 그대로 재사용).

## 1. 들어간 것

- `model_release.py`: `Idempotency-Key` header **필수**(`_require_idempotency_key` 재사용, W2/W4와 같은 `VAL-0003` 422), `ENDPOINT` 상수(IDEM-2), ledger payload `{modelId, version, request}`(경로가 키의 일부), 순서 **permission preflight → key → body → kernel 관측(tx 없음) → 쓰기 tx**: `serialise_idempotent_write`(IDEM-6 advisory lock) → live canApprove → clock 1회(`request.app.state.clock()`, `get_now` 의존 제거 — #191 F3/#196 F2 선례) → `replay_or_reserve`(같은 key·같은 payload는 저장 응답 replay, 다른 payload는 `GRAPH-0002` 409) → parent read → row `FOR UPDATE` → canApprove 재확인 → **이미 `released`면 `GRAPH-0002` 409**(다른 key로 두 번째 release = stage 재기록·mirror intent 중복 그 자체) → 선행조건·선언 비교 → `release_model_version` → audit → `store_idempotent_response`(같은 tx). `TRANSLATION`에 `GRAPH_IDEMPOTENCY_CONFLICT → GRAPH-0002/409`. bounded span 2 유지(`test_lock_wait` ratchet 통과).
- `schemas.ModelReleaseRequest` docstring에 header·replay·409 규칙 → `contracts/model-release-request.schema.json` description 갱신(export 재생성, `--check` PASS 78). body 필드 무변경. OpenAPI는 `Header` 파라미터로 자동 노출.
- 시험 PG-free `tests/core/test_model_release_route.py`: harness에 W4와 같은 ledger stub(advisory-lock·ledger-read·ledger-write·clock) + 기존 요청 전부 key 포함; 신규 12건 — 순서(`FULL_ORDER`), ENDPOINT = `POST /v1` + path, key 부재/형식 4종 422(preflight 뒤·body/kernel/쓰기 span 전), replay 시 lock·release·audit·store 0, 다른 payload 409 고정 detail, payload에 경로 포함, 이미 released 409, clock 1회·lock 뒤·세 곳 동일 instant, lock 뒤 권한 재확인, 번역표, helper 재사용·사본 없음(`pg_advisory_xact_lock`·`IdempotencyRecord` 문자열 부재)·span 2·`get_now` 부재. 실 PG `tests/integration/test_model_release_real_pg.py`: 같은 key 2회 → 동일 body·stage 1회·**mirror intent 1**·audit 1·ledger 1; 같은 key 다른 declaration → 409·intent 1; 다른 key 재release → 409·intent 1; key 없음 → 422·draft·intent 0; barrier로 동시 최초 2건 → 200/200 동일·intent 1·ledger 1. `tests/integration/test_lock_wait_real_pg.py`의 release 호출 2곳에 key 추가.

## 2. 판단한 것

- **이미 released인 row의 재release는 409**로 했다. 카드는 같은 key replay만 요구했지만, 다른 key의 두 번째 release가 만드는 두 번째 mirror intent가 바로 이 계약이 막으려는 중복이다. 200 no-op(W4의 extended:false 식)은 "release가 일어났다"로 읽히므로 고르지 않았다. Codex 확인 요청.
- **replay가 kernel 관측 GET 뒤에 온다.** 원장 읽기를 preflight span에 넣으면 span이 셋이 되어 "두 span 유지"에 어긋나고, 관측을 tx 밖에 두는 것이 이 route의 이유다. 재시도는 읽기 전용 GET 한 번을 더 하고 저장 응답을 받는다; kernel이 죽어 있으면 replay 대신 503이 난다 — 한계로 적었다.
- **key 검사는 preflight 뒤**(W4 순서): 비회원이 key 판정으로 아무것도 배우지 않는다. `tests/core/test_canonical_denial_audit.py`가 key 없이 403을 기대하는 것과 정합.
- 호환: FE는 #219에서 release를 미노출로 전환했으므로 소비자 0; 시험 호출자(`test_lock_wait_real_pg`)만 갱신. 기존 클라이언트가 있다면 key 없는 요청은 422가 된다 — PR 본문에 명시.

## 3. 검증 (실제 수행한 것만)

로컬 PG-free: `tests/core/test_model_release_route.py` 74 passed(신규 12 포함) + `test_lock_wait.py`; 이웃 6파일(`test_canonical_denial_audit`·`test_lock_wait`·`test_low_risk_write_response_contracts`·`test_model_retention_pin_route`·`test_model_verify_route`·`test_route_coverage`) 241 passed. 실 PG 3파일 27 collected — **NOT_OBSERVED**, hosted 인용은 PR 코멘트. 게이트 chain exit 0, `export_schemas --check` 78, FE `contracts:check` 20(변경 없음).

## 4. 다음

1. hosted Backend/Core green 인용 → Codex 동시성·보안 검토.
2. #221이 착지/재지정되면 이 PR도 base를 따라간다(runbook #225 §4).
