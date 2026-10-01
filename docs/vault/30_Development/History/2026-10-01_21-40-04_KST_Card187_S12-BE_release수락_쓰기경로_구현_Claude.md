---
doc_id: "HISTORY-S12-BE-RELEASE-ACCEPTANCE-WRITE-IMPL-20261001"
title: "S12-BE release 수락·operator sign-off 쓰기 경로 구현 — 두 사람, 그 순서로. 그리고 왜 지금은 닫혀 있는지 (카드 187)"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T02:59:16+09:00"
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

## 6. 검토에서 바뀐 결정 — write-time grant의 단일 정본은 DB 함수다

`#286` 보안 검토 r2에서 Codex가 변이 하나를 들었다: `src/saintvision/services/release_acceptance.py`의 **두 번째**
`require_global_administrator()` 호출을 **지워도 시험이 전부 통과한다**. 설계 §4 step 8이 "쓰기 직전 권한 재검사"를
요구하므로 그 호출은 그 문장을 코드로 옮긴 것처럼 보였다.

**측정한 것.** 그 호출이 왜 죽일 수 없는지 먼저 확인했다. `public.business_admin_allowed`는 grant 행에 **`FOR SHARE`** 를
잡는다. 그래서 요청 머리에서의 **첫** 검사가 그 행을 **transaction 전체 동안** 고정하고, 동시 회수는 commit까지 **막힌다**
— scratch database에서 직접 재현했다: 회수하는 statement가 그대로 멈춰 timeout까지 간다. 같은 transaction 안에서의 두 번째
호출은 따라서 **다른 답을 낼 수 없다**. 변이가 생존한 이유는 시험이 약해서가 아니라 그 코드가 **증명 가능하게 무력**하기
때문이다.

**결정.** 호출을 **삭제했다**. 보안 검사처럼 보이는 죽은 코드는 없는 것보다 나쁘다 — 읽는 사람에게 grant가 두 번
집행된다고 말하지만 두 번째는 무력하고, 시험으로 보호할 수도 없으니 다음 refactor가 아무 신호 없이 지워도 똑같다.
그래서 **`public.release_acceptance_confirm`이 write-time grant의 단일 정본**이다. 남는 것은 둘이다.

| 무엇이 실제로 집행하나 | 어디서 |
|---|---|
| 요청 경계의 첫 검사 — 그리고 **lock을 잡는 쪽이 이것**이다 | `confirm()` 머리의 `require_global_administrator()` |
| 쓰기 직전 재검사 — grant를 **스스로 다시 읽는다**, 행을 넣는 **같은 statement 안에서** | `public.release_acceptance_confirm` (0057, `SECURITY INVOKER`) |

두 번째가 §4 step 8을 만족시키고, **service 함수를 거치지 않고 table에 닿는 경로까지** 덮는다(§4-1). 반대 선택지는 service
재검사를 독립 경계로 선언하고 호출을 잡는 시험을 두는 것이었는데, 그 시험은 **집행을 측정하지 못한다** — 호출이 있는지만
본다. 측정할 수 없는 경계를 선언하지 않기로 했다.

이 결정은 세 자리에 적는다: 계약·설계는 `#282` v1.3.0 §4 step 8, 주석은 호출이 있던 자리
(`src/saintvision/services/release_acceptance.py`의 `confirm()` 안, manifest 재확인 바로 위), 그리고 이 절이다.

### 6-1. 같은 round의 다른 두 가지

- **commit되는 409도 감사한다.** 만료·manifest-superseded는 lifecycle 행과 slot 해제를 **commit한 뒤** 409를 돌려주므로
  정본 problem handler를 거치지 않았고, `proposal_invalidated`만 남고 `denied`는 **0행**이었다(Codex 측정). route가 스스로
  `record_denial_out_of_band()`로 **정확히 1행**을 쓴다 — repository 규칙("route는 거부가 되돌리는 transaction 안에 있다")이
  **적용되지 않는 유일한 경우**가 이것이고, 그래서 band 밖에서 쓴다. **전이를 수행한 요청만** 기록한다: 같은 key replay와
  다른 key 재요청은 같은 사실에 대한 같은 답이므로 0행이고, 그렇지 않으면 감사가 거부가 아니라 **재시도**를 센다.
- **release의 정체성과 policy pin은 다시 쓸 수 없다**(`#291` r2 Low). 0005가 app 역할에 `release_manifests` 전체 UPDATE를
  주었으므로, `manifest_sha256`을 고칠 수 있는 사람은 **수락 행을 건드리지 않고** 이미 수락된 결정이 본 적 없는 구성을
  가리키게 만들 수 있었다. `release_manifest_pin_is_final()` trigger(`SECURITY INVOKER`)가 digest는 **불변**, policy 쌍은
  **한 번만 쓰기**로 고정한다 — 열 권한 회수가 아니라 trigger인 이유는 그 grant가 이 카드가 소유하지 않은 writer와 공유되기
  때문이다.

## 7. fresh-auth 단일 정본 — §3의 `FreshAuth` 서술은 더 이상 코드가 아니다

`#286` 보안 검토에서 Codex가 `#285`·`#286`·`#291` 결합 tree를 대조하고 **결정**을 냈다: **`#285`의 검증·정규화 결과와 `has_fresh_interactive_auth()`가 유일한 정본**이다. 그대로 구현했고, 그래서 §3이 적은 "`Principal`이 `FreshAuth`를 선택적으로 나른다"는 **지금 코드가 아니다.**

**두 표현을 함께 두면 양쪽으로 틀릴 수 있었다**는 것이 결정의 근거이고, 둘 다 측정된 것이다.

| 방향 | 무엇 |
|---|---|
| fail-open | `mfa+sms`는 canonical allowlist(`{mfa,pwd,otp,hwk,swk}`)가 거부하는데 이 카드의 **독립 RFC 8176 검사는 통과**시킨다 — `sms`는 등록된 값이고 `mfa`가 있으므로 |
| 영구 fail-closed | 이 카드의 `_fresh_auth_from()`은 `identity.issuer`·`client_id`를 기대했지만 kernel `Identity`는 **그 필드를 내보내지 않았다** — 실 OIDC 경로에서는 언제나 `fresh_auth=None`이고, 그 사실이 시험에 걸리지 않았다 |

**바뀐 것**: `FreshAuth` 와 `Principal.fresh_auth`, `oidc._fresh_auth_from()`, 그리고 이 카드가 들고 있던 `RFC8176_VALUES`·`SECOND_FACTORS`·`FRESH_AUTH_WINDOW_SECONDS`를 **지웠다**. `Principal`은 `#285`의 `verified_fresh_auth_claims`·`auth_time`·`amr`에 **token provenance 셋**(`verified_token_issuer`·`verified_token_client_id`·`verified_token_expires_at`)을 더해 나르고, 그 셋은 `inv.identity.Identity`가 **이미 검증한 값**을 그대로 넘긴 것이다(kernel에 `issuer`·`client_id` 필드를 더했다). `proof_of_interactive_human()`은 **consumer**다 — canonical predicate가 참인 뒤 digest와 window만 만들고, window 길이도 `FRESH_AUTH_MAX_AGE_SECONDS`를 가져다 쓴다.

**시험**: 실 signed token을 `AccessTokens.verify → OidcPrincipalVerifier.verify → require_fresh_operator`로 통과시키는 **단일 행렬**을 실 PG에 넣었다 — 허용 `mfa`·`pwd+otp`·`pwd+hwk`·`pwd+swk` × age 0·300, 거부 12종(claims 부재, bool·string·float·음수 `auth_time`, 미래, 301초, 빈 AMR, `pwd` 단독, `otp` 단독, `webauthn`, 그리고 **`mfa+sms`** — 두 정책이 갈라지던 그 조합). provenance 셋 중 하나라도 없으면 `AUTH-0030`/403이고 write 3표 0행이며 **거부는 1행 감사된다**(§8이 요구하는 것이 그것이다). 손으로 채운 principal은 `verified_fresh_auth_claims`가 거짓이라 거부된다. 그리고 정적 단언으로 **지운 이름들이 돌아오지 못하게** 고정했다(`FreshAuth`·`_fresh_auth_from`·세 상수·`webauthn` 문자열 0건, canonical predicate 호출 1건, 다섯 route 전부가 같은 consumer를 쓴다는 것을 route 수와 대조).
