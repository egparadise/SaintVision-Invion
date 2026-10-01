---
doc_id: "HISTORY-S12-BE-RELEASE-ACCEPTANCE-WRITE-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 보안 계약 — 설계·strict schema"
version: "1.2.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T19:55:28+09:00"
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
- `accepted`는 서로 다른 두 사람의 같은 proposal digest 확인이 있어야만 그 decision의
  `decisionSignOff=true`다. release 전체 `operatorSignOff`는 required criterion 전부를
  집계한 읽기 projection만 계산한다.
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
`tools/export_schemas.py`로 JSON Schema 8개를 생성했다.

- `ReleaseAcceptanceDecisionRequest`
- `ReleaseAcceptanceConfirmationRequest`
- `ReleaseAcceptanceProposalResponse`
- `ReleaseAcceptanceProposalReviewResponse`
- `ReleaseAcceptanceProposalReviewPageResponse`
- `ReleaseAcceptanceRecordedResponse`
- `ReleaseAcceptanceWithdrawalRequest`
- `ReleaseAcceptanceWithdrawalResponse`

request의 unknown field, 사람 ID, secret, free-form note는 모두 거부한다. generated schema에도
conditional limitation과 accepted 2인 quorum/sign-off 조건을 `if/then/else`로 넣어 Pydantic
validator에만 숨어 있지 않게 했다.

## Claude r1 수정 반영

- 두 번째 운영자가 proposal의 target·measurement·reason·expiry를 직접 보는 인증된 GET 계약과
  strict `ReleaseAcceptanceProposalReviewResponse`를 추가했다. proposer/confirming user ID는
  응답하지 않는다.
- idempotency canonical payload를 `{releaseId,proposalId|acceptanceId,request}`로 고정하고,
  replay 전에 active human·fresh AMR·live permission을 다시 확인한다. 다른 path에 같은 key를
  재사용하면 `IDEM-0001`이다.
- proposal은 immutable이고 만료·manifest drift를 lifecycle event로 append한 뒤 coordination
  slot을 해제해 commit한다. error rollback과 상태 영속화의 모순을 제거했다.
- `operatorSignOff`는 required criterion 전부가 2인 accepted일 때만 true이고, legacy 1인
  `record_acceptance(accepted)`는 계수하지 않도록 고정했다. 철회 digest는 current manifest가
  아니라 철회 대상 final row의 `acceptedManifestSha256`이다.
- #280 새 head `4114f8ba`의 fail-closed 읽기 의미와 맞췄다. 구현 전에는
  `operatorSignOff=false`/`human-attestation-contract-absent`이고 distinct user 수는 관측값이다.
  vote에 fresh interactive human attestation을 immutable하게 저장·검증한 뒤에만 true 계약을 연다.
- migration의 RLS/FORCE RLS, append-only grant, vote/withdrawal/slot unique, permission CHECK,
  SECURITY DEFINER 금지 경계를 명시했다. IdP에는 `auth_time`·RFC 8176 `amr` mapper와 portal
  step-up이 선행돼야 하며 `pwd` 단독은 허용하지 않는다.
- digest는 strip 전 소문자 hex 64자를 요구하고 canonical datetime은 UTC 6자리 소수초 `Z`로
  고정했다. 8개 contract의 exact required set과 대문자·63자·끝 개행 부정 시험을 추가했다.

## Claude r2 조건 반영

- 기존 `contracts` 디렉터리에 둘 S12-BE 소유 Git 정본
  `release-acceptance-policy-registry-v1.json`의 도입 계약을 설계 v1.2에 고정했다. registry
  누락·parse 실패·빈 required set·중복·digest/version drift는
  반드시 release sign-off false이고, registry 밖 criterion decision은 409다. 빈 `all()` true를
  허용하지 않는다.
- 코디네이터의 N2 최종 결정에 따라 #282가 release 범위 의미를 소유한다.
  `confirmedOperatorCount`는 fresh interactive human attestation이 유효한 서로 다른 운영자 수이고,
  `operatorSignOff`는 비어 있지 않은 registry의 required criterion 전부가 유효한 경우에만 true다.
  구현 전 #280은 이 값을 0과 `human-attestation-implementation-unavailable` blocker로 내며,
  legacy raw count는 `matchingAcceptedUserCount`로 분리한다.
- #282의 proposal/decision 응답은 `proposalConfirmationCount`·`decisionConfirmationCount`·
  `decisionSignOff`로 분리했다. withdrawal의 `operatorSignOff`만 철회 뒤 release 집계다.
- pending proposal discovery 목록 contract를 추가해 confirmer가 proposal ID와 검토 내용을
  인증된 route로 찾게 했다. canonical write는 SECURITY INVOKER·`inv_app` 전용이고 verified
  `SET LOCAL` identity를 읽는다. 만료/drift 409 receipt, 2인 bootstrap 경계도 고정했다.
- Claude r2의 생존 변이였던 review response의 sign-off bool 완화를 별도 부정 시험으로 닫았다.

## 실제 검증

- `python -m pytest tests/core/test_release_acceptance_write_contract.py -q` → **27 passed**.
- `python -m pytest tests/core/test_release_acceptance_write_contract.py tests/core/test_release_manifest_route.py -q`
  → **50 passed**.
- Pydantic **2.11.5와 2.13.5** 각각에서 계약 시험 **27 passed**, schema export
  **PASS, 93 schemas match**.
- `python tools/check_contract_bindings.py` → **exit 0**. 새 7 dead contract는 fixture·contract
  시험에 결속됐고 아직 backend route가 없다는 report-only dead-contract 경고는 이 카드의
  계약 선행 범위와 일치한다.
- `python tools/check_docs.py` → **exit 0**, `check_doc_path_citations --ratchet` → **exit 0**
  (기존 baseline 290, 신규·stale 위반 0), `git diff --check` → **exit 0**.
- real PG·route·migration 시험은 구현 범위가 아니므로 실행하지 않았다.

## 다음

Claude r1 재검토 뒤 다음 구현 카드가 OIDC verified claim 전달, migration, tenant permission,
route·service·audit, hosted real-PG 경합 시험을 구현한다. authoritative target/Evidence resolve가
없으면 accepted route는 enable하지 않는다.
