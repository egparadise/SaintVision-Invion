---
doc_id: "HIST-CODEX-LEGACY-OPTIONAL-IDEMPOTENCY-001"
title: "Legacy audit write 7개 선택적 idempotency 소비"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T02:30:04+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["security", "idempotency", "audit", "legacy-api", "card-122"]
---

# Legacy audit write 선택적 idempotency

## 닫은 공백

웹 클라이언트가 보내던 `Idempotency-Key`를 무시해 같은 성공 mutation의 audit/version/timestamp를 다시 쓰던 legacy route 7개가 이제 key를 소비한다.

1. workspace tool 설정
2. project member role 설정
3. project member 삭제
4. user status 설정
5. project status 설정
6. workspace status 설정
7. capability offer 설정

각 route는 live 권한을 먼저 확인하고, bounded advisory lock→durable ledger replay를 거친다. replay면 service·audit·두 번째 ledger write를 전혀 실행하지 않는다. 최초 성공의 service write, audit, response ledger는 같은 기존 transaction 안이다. 같은 key와 다른 path/body는 canonical digest 충돌로 409가 유지된다. key가 없으면 기존 요청 계약과 동작을 유지하되 DB lock wait만 bounded다.

## 보안 경계

Replay가 권한 검사를 우회하지 않도록 project/user/resource 권한 preflight를 ledger read보다 앞에 두고, 실제 write service가 lock 후 최종 권한을 다시 검사한다. 따라서 이전에 허용된 key를 보유한 사용자가 권한 철회 뒤 response를 다시 읽는 경로도 닫힌다. 공개 response schema·status·migration은 변경하지 않았다.

## 검증

- PG-free: helper 순서·key 없음 advisory 0·7 route replay-before-service/audit를 고정한 9건과 기존 response contract를 포함해 **91 passed**.
- real PG: member role route를 같은 key로 두 번 호출해 동일 response, audit 1행, ledger 1행을 검증하도록 hosted 시험을 보강했다. 로컬 실 PG는 실행하지 않았다.
- `check_docs`, `check_contract_bindings`, `check_ontology`, `py_compile`, `git diff --check`를 PR 전 실행한다.
