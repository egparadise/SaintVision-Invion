---
doc_id: "S12-BE-FRESH-AUTH-SOURCE-001"
title: "S12-BE fresh-auth claim 공급원 및 portal step-up 인계"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T21:39:29+09:00"
source_of_truth: "Git"
base_sha: "89c8f3665d8f467cfa9d73e7160a985841488ef3"
source_commit: "e166b214a9c6eb4b57b8bdbf2acaa58224732704"
card: "188"
---

# S12-BE fresh-auth claim 공급원 및 portal step-up 인계

## 1. 결정과 비주장 경계

PR #282 v1.3.0이 정한 release acceptance 쓰기 경계는 서명 검증된 access token의
`auth_time`과 `amr`만 fresh-auth 증거로 사용한다. 이번 카드는 그 공급원과 판정 계약을
추가하지만 release acceptance write route를 enable하지 않는다.
#282가 `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false`를 기본으로 설계했지만 이 branch에는 아직
route와 flag 구현이 없다(Claude 카드 187 구현 범위). 실제 Keycloak token 관측과 portal step-up,
target/Evidence resolver가 끝나기 전에는 그 구현도 모든 write route를 disabled로 유지해야 한다.

사내 hosts가 아직 적용되지 않아 실제 `idp.sv.lan` 로그인과 access token 관측은
**BLOCKED_EXTERNAL**이다. 따라서 이 문서는 live Keycloak PASS, 운영자 수락 완료 또는
operator sign-off 완료를 주장하지 않는다.

## 2. 검증된 claim 공급원

`deploy/intranet/idp-realm.sh`는 portal client에 다음 access-token-only mapper를 고정한다.

| claim | Keycloak 공급원 | 고정 조건 |
|---|---|---|
| `auth_time` | 서버 user-session note `AUTH_TIME` | integer, access token만 |
| `amr` | `oidc-amr-mapper` | access token만, completed execution reference만 |

Keycloak 26의 realm-wide `basic` scope도 `auth_time`을 낼 수 있다. client-local mapper는
그 scope 존재에 기대지 않고 동일한 `AUTH_TIME` scalar를 고정한다. 두 mapper가 함께
적용돼도 값의 출처가 같으며 caller 입력으로 값을 만들지 않는다.

browser flow의 password와 OTP execution에는 RFC 8176 reference `pwd`, `otp`와
`default.reference.maxAge=300`을 지정한다. hardware/software key execution은 현재 realm에
없으므로 설정이나 관측을 주장하지 않는다. 서버 정책은 향후 정본 mapper가 내는 `hwk`,
`swk`를 수용할 수 있지만 임의 문자열과 `webauthn` 문자열은 거부한다.

정적 checker가 확인하는 것은 두 execution reference **객체의 모양**까지다. 그것만으로 portal이
실제로 쓰는 realm `browserFlow` 또는 client `authenticationFlowBindingOverrides`에 execution이
연결됐다고 주장하지 않는다. 또한 현재 realm user에게 OTP credential/required action이 없으면
실제 token은 `amr=["pwd"]`이고 fresh-auth는 누구에게도 성립하지 않는다. 운영 enable 전에는
서로 다른 두 사람 모두 `CONFIGURE_TOTP`를 완료하고, portal authorization-code flow가 사용하는
flow에서 password+OTP가 완료되며, redacted live access token에 `pwd`+`otp`(또는 승인된 `mfa`)
조합이 나타나는 것을 관측해야 한다. 하나라도 없으면 `BLOCKED_EXTERNAL`이며 checker exit 0을
"AMR 공급 가능" 또는 write-ready 증거로 세지 않는다.

`services/control-plane/src/inv/identity.py`는 JWT signature, issuer, audience, subject,
expiry, token type, client와 scope 검증이 모두 끝난 뒤에만 두 claim을 trusted Identity로
복사한다. claim이 없거나 type·값 집합·중복이 잘못되면 일반 read 인증은 유지하되
fresh-auth metadata는 비워 둔다. `src/saintvision/identity/oidc.py` 외 경로가 만든
Principal은 verified flag가 없으므로 claim 값을 채워도 fresh로 인정되지 않는다.

## 3. 서버 판정 계약

`src/saintvision/identity/principal.py`의 판정은 다음을 모두 요구한다.

1. `auth_time`은 timezone-aware 현재 시각보다 미래가 아니고 나이가 0..300초다.
2. `amr`는 `mfa`, `pwd`, `otp`, `hwk`, `swk`의 집합만 허용한다.
3. 허용 조합은 `mfa` 또는 `pwd`와 `otp|hwk|swk` 중 하나다.
4. `pwd` 단독, `otp` 단독, `webauthn`, 누락, malformed, stale, future claim은 모두 false다.
5. 300초보다 넓은 freshness window를 호출자가 선택할 수 없다.

이 predicate는 기존 read route를 깨지 않는다. 향후 #282 write route만 false 결과를
정본 `AUTH-0030` 경계로 번역한다.

## 4. portal step-up 계약과 Antigravity 인계

정본 redirect/query parameter는 생성 계약
`contracts/fresh-authentication-step-up-request.schema.json`의 exact 두 필드다.

```json
{"prompt":"login","max_age":300}
```

portal/FE owner는 Antigravity(Gemini)다. 구현 카드는 다음 조건을 보존해야 한다.

1. 기존 authorization-code + PKCE S256 흐름을 재사용하고 `prompt=login`, `max_age=300`을
   authorization request에 정확히 추가한다.
2. 기존 `state`, `nonce`, redirect URI 검증을 우회하지 않는다.
3. callback 성공 후 새 access token으로 session을 교체한다. 원래 write 요청은 사용자의
   명시적 재시도 전까지 자동 재전송하지 않는다.
4. claim, token 또는 credential을 control-plane JSON body나 query에 복사하지 않는다.
5. step-up 취소·오류·claim 누락은 sign-off 성공으로 합성하지 않는다.

이번 PR에는 portal 코드를 넣지 않는다. 그래서 FE 구현 및 실제 Keycloak 로그인 관측 전
write-route enable 조건은 충족되지 않는다.

## 5. 정적 검증과 후속 인수

- `tools/check_idp_realm_config.py`는 두 mapper와 password/OTP reference·300초 max age를
  live snapshot에서 exact 비교한다. flow binding·사용자 OTP 등록·실제 token AMR은 별도 live
  관측 항목이며 이 static PASS로 대체하지 않는다.
- `tests/core/test_check_idp_realm_config.py`는 mapper 또는 reference 완화 변이를 거부한다.
- `tests/core/test_fresh_auth_claims.py`는 서명 검증 후 전파, 허용/거부 조합, 300초 경계와
  portal redirect 계약을 고정한다.
- hosts 적용 뒤 `idp-realm.sh`를 재실행하고 실제 token에서 `auth_time`, `amr`를 redacted
  형태로 관측해야 BLOCKED_EXTERNAL을 해소할 수 있다.
- Antigravity 카드가 portal step-up을 구현하고 exact redirect parameter 및 callback 보안
  시험을 통과해야 한다.
- 두 후속 증거가 없으면 #282 write route flag는 계속 off다.
