---
doc_id: "HISTORY-S12-BE-RELEASE-ACCEPTANCE-WRITE-IMPL-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 경로 구현 — 두 사람, 그 순서로. 그리고 왜 지금은 닫혀 있는지 (카드 187)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-01T21:40:04+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b96068b6"
task_ids: ["S12-BE", "S12-FE"]
tags: ["s12", "release-acceptance", "two-person", "security", "migration", "claude"]
---

# 카드 187 — 쓰기 경로를 구현하고, 닫아 둔 채로 증명했다

계약은 `#282` v1.3.0(Codex). 구현 owner는 Claude, 보안 축 검토는 Codex. base는 `b96068b6`.

## 0. 먼저 측정한 것 — 이 카드가 열 수 없는 두 문

구현을 시작하기 전에 계약이 조건으로 단 전제를 **문자열로 찾아** 확인했다.

| 계약이 요구하는 전제 | 측정 결과 |
|---|---|
| 검증된 `auth_time`·`amr` 공급과 portal step-up(§1, §10) | `auth_time`·`amr`가 **`src/`·`deploy/`·`tests/` 어디에도 없다**(0건). `deploy/intranet/idp-realm.sh`에 mapper 없음, `Principal`에 필드 없음 |
| authoritative target/Evidence resolver(§3-1, §10) | `contracts/`에 target registry 없음. `evidence_envelopes`에 **envelope digest 열이 없다**(있는 것은 `input_sha256`·`output_ref`) |

그래서 질문 5건을 `#282`에 올렸고 계약 owner가 v1.3.0 §0-1로 고정했다. 그 답을 **해석하지 않고 그대로** 구현했다:
blocker literal은 `release-acceptance-prerequisites-unavailable`, Evidence digest fallback 금지, 새 permission은 `releases.accept` 하나,
이 카드가 만드는 파일은 policy registry 하나, route는 **등록하되 `SYS-0003`/503으로 닫는다**.

## 1. 0057 — 결정의 주변 역사

`acceptance_records`는 이미 `users`로 가는 외래키를 갖고 있었고 그것으로 충분하지 않았다. `(release_id, acceptance_id_ref)` unique라
한 기준은 **한 번만** 결정될 수 있고, 재결정도 철회도 2인 투표도 표현하지 못한다. 그 행을 넓히는 것은 역사를 제자리에서 고치는 것이므로,
결정은 그 자리에 두고 **주변 역사**를 새로 만들었다.

| table | 불변식 | 왜 schema에 있나 |
|---|---|---|
| `release_acceptance_proposals` | append-only. manifest digest·proposal digest·policy pin을 함께 고정 | registry가 바뀌면 재범위화가 아니라 **무효화**다 |
| `release_acceptance_votes` | **UNIQUE `(proposal_id, user_id)`** | 2인 규칙을 service가 아니라 **schema가** 말한다 |
| `release_acceptance_withdrawals` | UNIQUE `acceptance_id` | 두 번째 철회는 더 강한 진술이 아니고, 허용하면 "언제 철회됐나"에 답이 둘이 된다 |
| `release_acceptance_lifecycle_events` | UNIQUE `(proposal_id, event_kind)` | proposal은 **행을 덧붙여** 닫는다. 그래서 §4가 닫는 transaction을 commit하고 **그 뒤에** 409를 돌려줄 수 있다 |
| `release_acceptance_slots` | UNIQUE `(tenant, release, criterion)` + state machine trigger | 동시 proposal 둘이 하나로 수렴하는 자리 |

`acceptance_records`는 `attestation_version`(기존 행은 전부 `legacy-unverified` — **판정이 아니라 분류**)과 `proposal_id`를 얻고,
**attested `accepted` 행은 proposal을 반드시 지목해야 한다**는 CHECK가 붙는다. 기준 unique는 slot의 key로 대체하고 `UPDATE`·`DELETE`는 회수했다.

`inv.user_id`가 `inv.tenant_id` 옆에 transaction 상태로 들어갔다. §4-1이 canonical 함수에 **raw user ID 인자를 금지**하기 때문이고, 그 금지가 옳다:
인자는 caller의 주장이고, 인자를 받는 함수는 "다른 사람으로" 기록해 달라고 요청받을 수 있다. 그러면 2인 규칙은 caller가 보낸 두 문자열에 대한 규칙이 된다.

### 1-1. 함수가 약속할 수 없는 것을 적었다

`public.release_acceptance_confirm`은 §4-1 요구대로 **`SECURITY INVOKER`**다. 그래서 caller의 권한으로 돌고, 그 말은 application role이
같은 INSERT를 직접 할 수 있다는 뜻이다. **"이 행은 함수만 쓸 수 있다"는 권한 경계가 아니고, migration에 그렇게 적었다.** 누가 쓰든 서는 것은
schema에 있는 것들이다 — 네 개의 UNIQUE, slot의 단일 상태 CHECK와 state machine trigger, attested acceptance가 proposal을 지목해야 하는 CHECK.

## 2. 게이트 순서 — O1

0. **전제 게이트.** 다섯 route 전부, **GET 둘 포함**. ledger보다 먼저, 행을 읽기 전에.
1. 신원·신선도·live 권한(replay 전에도 다시).
2. path ID까지 포함한 idempotency lock·ledger.
3. manifest 행 lock + digest 비교. 4. slot. 5. ref 재결속. 6. 행과 감사 사건을 같은 transaction에, 그 뒤 receipt.

시험이 세 가지로 고정한다: 다섯 route 전부 `SYS-0003`/503/`retryable=false` + 고정 문장 하나, **거부된 요청은 receipt를 만들지 않는다**,
그리고 **거부된 요청은 session을 건드리지 않는다**(session 의존성이 어떤 접근에도 실패하는 객체다 — 늦게 거부하면 그 메시지로 죽는다).
`_gate(settings)`가 각 handler 본문의 **첫 문장**인지도 source를 읽어 단언한다.

### 2-1. 내가 틀렸던 것 — 인증과 게이트의 순서

처음에는 인증되지 않은 caller에게도 503을 돌려주도록 시험을 썼다. "닫힌 표면은 oracle이 아니어야 한다"는 이유였는데 **방향이 틀렸다**:
이 API의 **모든** route가 token 없이 401을 돌려주므로 여기서의 401은 이 route에 대해 아무것도 말하지 않는다. 반대로 익명 caller에게 503을 주면
**경로가 존재하고 기능이 꺼져 있을 뿐이라는 것을 확인해 준다.** 측정한 실제 동작(401 `AUTH-MISSING-CREDENTIAL` / 403 `auth-invalid-credential` / 503)을
시험에 적고, 왜 바꿨는지를 시험 docstring에 남겼다.

**계약과의 편차 1건을 보고한다.** §7은 token 부재·무효에 `AUTH-0050`/401을 요구한다. 이 application의 공용 auth 의존성은
부재에 `AUTH-MISSING-CREDENTIAL`/401, 무효에 `auth-invalid-credential`/403을 낸다. `AUTH-0050`은 **kernel application**(`services/control-plane`)의
어휘이고 business API에는 없다. 다섯 route에서 그것을 내려면 **모든 business route의 인증 오류를 바꿔야** 하므로 이 카드에서 결정하지 않았다.

## 3. fresh-auth 배관 — 카드 188 전에도, 후에도 같은 코드

`Principal`이 `FreshAuth`(verified `auth_time`·`amr`·issuer·client·exp)를 **선택적으로** 나른다. kernel verifier의 `Identity`는
`getattr`로 **관용적으로** 읽는다: 오늘은 아무것도 주지 않으므로 `None`이고, `None`은 거부다. 카드 188이 공급을 만들면 **같은 코드가** 실제 값을 나른다.
`inv/identity.py`를 고치지 않았다 — 그 파일은 188의 것이고, 둘이 같은 줄을 고치면 충돌한다.

규칙(§2-1)은 전부 측정으로 확인했다: `pwd` 단독 거부, 비등록 `webauthn` 거부, `mfa` 또는 `pwd`+(`otp|hwk|swk`) 허용,
300초 초과 거부, **미래 `auth_time` 거부**(clamp하지 않는다 — 그만큼 틀린 시계는 증거가 아니고, 미래를 "아주 신선함"으로 읽으면 오류가 공격자에게 유용해진다).

## 4. 검증

| 항목 | 결과 |
|---|---|
| 실 PostgreSQL | `test_pilot` 46 · `test_release_sign_off` 11 · `test_release_acceptance_invariants` **29** |
| PG-free | `test_release_acceptance_routes` **34** · policy 40 · digest 22 · route(읽기) 40 · migrations 27 |
| 합산 | **297 passed** |
| gate | `check_docs`·`check_doc_single_source`·`check_vf_cl_registry`·`check_contract_bindings`·`export_schemas --check`·citation ratchet(base `b96068b6`)·`git diff --check` 전부 exit 0 |

§9 hosted 목록 중 이 카드가 덮은 것: append-only UPDATE·DELETE 거부(5개 table), 중복 투표, 이중 철회, 이중 close,
slot 우회 두 형태, attested acceptance의 proposal CHECK, 함수 EXECUTE가 `inv_app`에만·`SECURITY INVOKER`,
proposer self-confirm·만료·digest 불일치·manifest drift·권한 회수·정지된 사용자 거부, distinct 2인 성공 경로, 그리고 **두 연결 경합**.

### 4-1. 경합 시험에서 내가 틀렸던 것

처음 쓴 경합 시험은 첫 transaction이 slot을 **commit하지 않은 채** 두 번째가 `FOR UPDATE`로 막히는 것을 기대했다. **막히지 않았다** —
commit되지 않은 행은 보이지 않으므로 두 번째는 잠글 행을 찾지 못한다. 실제 기구는 두 단계다: 행이 없을 때는 **unique index**에서,
있을 때는 **행 lock**에서 막힌다. 시험을 두 단계로 다시 썼고, 왜 첫 버전이 틀렸는지를 docstring에 남겼다.

## 5. 이 카드가 하지 않은 것

- **route를 열지 않았다.** `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED`는 기본 false이고, **켜도 열리지 않는다** — 게이트의 둘째 조건이
  설정이 아니라 배포 사실이기 때문이다. 그것이 이 flag를 안전하게 내보낼 수 있는 이유다.
- **target registry와 Evidence canonical digest resolver를 만들지 않았다**(§0-1.2·§0-1.4로 별도 카드). resolver는 `active_resolver()`라는
  **이름 붙은 seam**이고 지금 구현은 거부한다. caller가 보낸 ID·hash만 맞춰보는 fallback은 **넣지 않았다** — §3-1이 금지한 바로 그 구현이다.
- **읽기 표면의 literal을 풀지 않았다.** `operatorSignOff`는 `Literal[False]`, `confirmedOperatorCount`는 `Literal[0]`으로 그대로 두었다.
  projection은 이미 있고 그 값들과 **일치하는지 시험이 확인한다**(카드 187 1단계).
- **감사 사건은 여섯 종으로 닫았고**, 일곱 번째를 쓰면 `ValueError`다. denial 감사는 기존 `record_denial_out_of_band` 경로를 쓴다.
- Keycloak mapper·portal step-up은 카드 188의 것이다.
