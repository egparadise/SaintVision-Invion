---
doc_id: "HISTORY-S12-BE-RELEASE-ACCEPTANCE-WRITE-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 보안 계약 — 설계·strict schema"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T18:55:55+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3ff89b84"
task_ids: ["S12-BE", "S12-FE"]
tags: ["history", "s12", "acceptance", "operator-sign-off", "security", "contract", "codex"]
---

# S12-BE release 수락·operator sign-off 쓰기 계약

## 선택 근거와 범위

PR #280 head `3ff89b84`는 release manifest 읽기 두 route와 strict 응답 계약을 열었지만,
[[S12-BE_release_manifest_읽기_route_설계_메모]]는 사람 증명·tenant 전역 권한·멱등·digest·
감사 결정을 Codex 보안 계약으로 명시적으로 넘겼다. 그래서 #280 branch 위에서 공개 쓰기
body를 먼저 고정했다. 이 PR은 설계·계약만이며 route·DB·migration·runtime 권한 구현은 0이다.

## 결정

- 모든 결정과 철회는 5분 이내 신선한 interactive OIDC 인증과 live
  `releases.accept` permission을 요구한다. 사람 ID·token·재인증 proof는 body에서 받지 않고
  server-derived active user만 쓴다.
- `accepted`는 서로 다른 두 사람의 같은 proposal digest 확인이 있어야만
  `operatorSignOff=true`다. `conditional/rejected`는 한 사람 기록이지만 sign-off는 false다.
- caller의 `targetManifestSha256`은 optimistic target일 뿐이다. 잠근 release의 server digest와
  일치할 때만 server 값을 final row에 쓴다.
- `targetRefs`와 `measurementRefs`를 분리하고 둘 다 최소 1개를 요구한다. 구현은 caller hash를
  믿지 않고 authoritative registry/Evidence에 exact digest로 재결속해야 한다.
- 철회는 append-only POST이고 과거 row를 삭제·수정하지 않는다. 한 fresh operator가 안전 쪽
  전이를 수행할 수 있고 철회된 row는 sign-off에 기여하지 않는다. release 전체 값은 남은
  다른 criterion의 유효한 accepted decision까지 재계산한다.

상세 transaction lock 순서, replay·경합, 오류 표면, audit closed set, hosted real-PG 부정
시험 계획은 [[S12-BE_release_acceptance_operator_signoff_쓰기_계약_설계]]에 고정했다.

## 공개 계약

`src/saintvision/api/schemas.py`에 아래 strict Pydantic source를 추가하고
`tools/export_schemas.py`로 JSON Schema 6개를 생성했다.

- `ReleaseAcceptanceDecisionRequest`
- `ReleaseAcceptanceConfirmationRequest`
- `ReleaseAcceptanceProposalResponse`
- `ReleaseAcceptanceRecordedResponse`
- `ReleaseAcceptanceWithdrawalRequest`
- `ReleaseAcceptanceWithdrawalResponse`

request의 unknown field, 사람 ID, secret, free-form note는 모두 거부한다. generated schema에도
conditional limitation과 accepted 2인 quorum/sign-off 조건을 `if/then/else`로 넣어 Pydantic
validator에만 숨어 있지 않게 했다.

## 실제 검증

- `python -m pytest tests/core/test_release_acceptance_write_contract.py -q` → **22 passed**.
- `python tools/export_schemas.py --check` → **PASS, 91 schemas match**.
- `python tools/check_contract_bindings.py` → **exit 0**. 새 6 contract는 fixture·contract
  시험에 결속됐고 아직 backend route가 없다는 report-only dead-contract 경고는 이 카드의
  계약 선행 범위와 일치한다.
- `python tools/check_docs.py` → **exit 0**, `check_doc_path_citations --ratchet` → **exit 0**
  (기존 baseline 290, 신규·stale 위반 0), `git diff --check` → **exit 0**.
- real PG·route·migration 시험은 구현 범위가 아니므로 실행하지 않았다.

## 다음

Claude 독립 설계 검토 뒤 다음 구현 카드가 OIDC verified claim 전달, migration, tenant permission,
route·service·audit, hosted real-PG 경합 시험을 구현한다. authoritative target/Evidence resolve가
없으면 accepted route는 enable하지 않는다.
