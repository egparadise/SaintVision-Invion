---
doc_id: "HISTORY-CARD188-FRESH-AUTH-20261001"
title: "Card 188 fresh-auth claim 공급원 구현"
version: "1.0.2"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T21:20:29+09:00"
source_of_truth: "Git"
source_commit: "e166b214a9c6eb4b57b8bdbf2acaa58224732704"
---

# Card 188 fresh-auth claim 공급원 구현

## 선택 근거와 범위

- owner Codex, reviewer Claude, branch `agent/codex/c188-fresh-auth-claims`, base
  `89c8f3665d8f467cfa9d73e7160a985841488ef3`에서 시작했다.
- PR #282 v1.3.0은 verified `auth_time`·`amr`와 portal step-up 증거가 없으면 release
  acceptance write route 전체를 disabled로 두도록 정했다. 코드 검색에서 mapper,
  Principal metadata, `prompt=login&max_age=300` 계약이 모두 없었으므로 이 공급원 카드를
  구현했다.
- write route flag, release acceptance route와 migration은 변경하지 않았다.
- 구현 source commit은 `e166b214a9c6eb4b57b8bdbf2acaa58224732704`다.

## 구현

- `deploy/intranet/idp-realm.sh`: portal client의 `AUTH_TIME`→`auth_time` mapper와 AMR mapper,
  browser password/OTP execution의 RFC 8176 `pwd`/`otp` reference 및 300초 max age를
  re-runnable하게 고정했다.
- `services/control-plane/src/inv/identity.py`: access-token 검증 성공 뒤에만 fresh claim을
  trusted Identity로 옮긴다. 누락·malformed·unknown·중복 AMR은 fresh proof가 아니다.
- `src/saintvision/identity/oidc.py`, `src/saintvision/identity/principal.py`: 검증 출처 flag와
  300초·AMR 조합 predicate를 추가했다. `mfa` 또는 `pwd+(otp|hwk|swk)`만 true다.
- `src/saintvision/api/schemas.py`와 생성 schema: portal step-up query를 exact
  `prompt=login`, `max_age=300`, 추가 필드 금지로 고정했다.
- `tools/check_idp_realm_config.py`: live realm snapshot에서 mapper·execution reference drift를
  fail closed로 검출하도록 확장했다.

## 검증 기록

| 시각(KST) | 명령 | 결과 |
|---|---|---|
| 2026-10-01 21:08 | Python 3.14 focused pytest 3 files | 97 passed, exit 0 |
| 2026-10-01 21:08 | `bash -n deploy/intranet/idp-realm.sh` | exit 0 |
| 2026-10-01 21:14 | focused pytest + 비밀 argv 회귀 | 131 passed, exit 0 |
| 2026-10-01 21:14 | `tools/export_schemas.py --check` | 86 schemas, exit 0 |
| 2026-10-01 21:15 | `tools/check_contract_bindings.py` | exit 0 |
| 2026-10-01 21:15 | `tools/check_docs.py` | exit 0 |
| 2026-10-01 21:16 | doc path citation ratchet (base `89c8f366`) | 신규 위반 0, exit 0 |
| 2026-10-01 21:16 | `tools/check_ontology.py` | exit 0 |
| 2026-10-01 21:17 | mapper script 정적 결속 focused pytest | 98 passed, exit 0 |
| 2026-10-01 21:19 | 최종 focused pytest 4 files | 132 passed, exit 0 |
| 2026-10-01 21:20 | 최종 schema·contract·docs·citation·ontology·diff gate | 전부 exit 0 |

exact-head hosted CI 결과는 PR 생성 뒤 PR 코멘트에 기록한다.

## 정직성 경계와 다음 owner

- 사내 hosts 미적용으로 실제 `idp.sv.lan` token은 관측하지 못했다. live mapper/token
  결과는 **BLOCKED_EXTERNAL**이며 이번 로컬 정적 결과를 운영 PASS로 세지 않는다.
- portal step-up은 Gemini/Antigravity 영역이다. exact parameter, PKCE/state/nonce 유지,
  callback 뒤 새 token 교체와 실패 시 sign-off 합성 금지를 별도 카드로 인계한다.
- 두 live 후속이 끝날 때까지 `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false`를 유지한다.
