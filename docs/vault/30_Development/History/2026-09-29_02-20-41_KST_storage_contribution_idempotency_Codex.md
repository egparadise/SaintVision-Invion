---
doc_id: "HIST-CODEX-STORAGE-CONTRIBUTION-IDEMPOTENCY-001"
title: "Storage contribution 동시 최초 요청과 unique 충돌 경계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T02:20:41+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["security", "idempotency", "storage", "integrity-error", "card-122"]
---

# Storage contribution 동시성·충돌 경계

## 변경

- `Idempotency-Key`가 있으면 bounded lock budget 안에서 key별 transaction advisory lock을 먼저 잡고 ledger를 읽는다. 동시 최초 두 요청은 첫 응답을 하나만 만들고 둘째 요청은 commit 뒤 같은 응답을 replay한다.
- key가 없어도 storage contribution write의 DB lock wait는 bounded다. 같은 node의 같은 normalized path가 이미 있으면 등록된 `uq_storage_contributions_node_id_normalized_path`만 기존 `GRAPH-INVALID-TRANSITION`/409로 번역한다.
- contribution insert는 savepoint 안에서 수행하므로 알려진 unique 충돌 뒤에도 오류 번역이 안전하며, allowlist 밖 IntegrityError는 그대로 전파해 DB 결함을 client 충돌로 숨기지 않는다.
- 공개 요청·응답 schema와 migration은 바꾸지 않았다. key는 기존처럼 선택적이며, 없는 key의 재시도는 새 ID를 합성하지 않고 정직한 409다.

## 검증

- PG-free: storage 보안 시험과 write response contract **58 passed**. advisory→ledger→service→audit→ledger 순서, replay side-effect 0, known constraint 409, unknown constraint 전파를 고정했다.
- real PG: `tests/test_api.py`에 동시 최초 요청 2건이 201/동일 body/row 1건인 경계와 no-key duplicate 409를 추가했다. 로컬 실 PG는 실행하지 않고 hosted Backend/Core를 근거로 한다.
- `check_docs`, `check_contract_bindings`, `check_ontology`, `py_compile`, `git diff --check`를 PR 전 다시 실행한다.
