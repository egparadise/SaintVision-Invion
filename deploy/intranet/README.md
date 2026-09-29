# deploy/intranet

사내망 identity provider와 control plane의 OIDC 신뢰 bundle을 세우는 스크립트다.
절차·근거·검증 결과는 `docs/vault/40_Operations/사내망_IdP_호스트명_인벤토리_런북_2026-09-30.md`에 있다.

| 파일 | 어디서 실행 | 무엇 |
|---|---|---|
| `idp-up.sh` | IdP 노드 | Keycloak + 전용 PostgreSQL을 digest 고정으로 기동한다. 비밀은 노드의 `0600` 파일에서 만들고, 이미 있으면 다시 만들지 않는다 |
| `idp-realm.sh` | IdP 노드 | realm·client·mapper·client scope·사용자를 설정한다. **빈 Keycloak에서 realm 전체를 만들 수 있고**, 다시 돌려도 아무것도 새로 만들지 않는다. 매 실행 정본 값을 다시 적용한 뒤 **live 설정을 되읽어 판정**하며, 어긋나면 실패한다 |
| `reissue-oidc-trust-bundle.sh` | control plane 호스트 | IdP의 JWKS로 신뢰 bundle을 다시 만든다. 임시 파일에 쓰고 검증한 뒤에만 자리를 바꾸므로 실패해도 기존 bundle이 남는다 |
| `sv-oidc-trust-bundle.service` / `.timer` | control plane 호스트 | 위 스크립트를 **매일** 돌린다. bundle은 7일이면 만료되므로 주 1회로는 한 번의 실패가 곧 장애다 |
| `inventory.example.json` | — | `tools/s01_readiness_preflight.py`가 읽는 인벤토리의 **형태**. 실제 값이 담긴 파일은 저장소에 두지 않는다 |

함께 쓰는 도구:

| 도구 | 무엇 |
|---|---|
| `tools/make_oidc_trust_bundle.py` | provider JWKS → 신뢰 bundle. verifier가 거부할 것은 쓰지 않고, `--jwks-url`은 issuer origin에 결속된다 |
| `tools/check_idp_realm_config.py` | live realm 설정이 verifier의 토큰 계약과 맞는지 판정한다. `idp-realm.sh`의 마지막 단계가 이것이다 |
| `tools/collect_oidc_identity_evidence.py` | 살아 있는 provider의 토큰이 실제 `AccessTokens.verify`를 통과하는지 측정해 redacted 증거를 남긴다. 토큰·사용자·키는 기록하지 않는다 |

bundle을 만드는 쪽은 `tools/make_oidc_trust_bundle.py`이고, 받아들이는 쪽은
`services/control-plane/src/inv/identity.py`의 `AccessTokens`다. 두 쪽의 수용 조건이
같다는 것은 `tests/core/test_make_oidc_trust_bundle.py`가 붙들고 있고, realm 설정이
완화되면 보고된다는 것은 `tests/core/test_check_idp_realm_config.py`가,
미관측이 PASS로 가지 못한다는 것은 `tests/core/test_collect_oidc_identity_evidence.py`가
붙들고 있다.

## TLS 전 노출

TLS 종단이 없는 동안 `idp-up.sh`는 Keycloak을 **loopback에만** bind한다. 평문 로그인
폼과 평문 토큰 endpoint를 LAN에 올려 두지 않기 위한 것이고, 넓히는 것은
`SV_IDP_BIND_ADDRESS`를 명시적으로 주는 별개의 행위다 — https 전환 뒤에 할 일이다.

## 비밀

비밀번호·private key·토큰은 노드의 `0600` 파일에만 둔다. 이 디렉터리의 어떤 파일도
비밀을 담지 않으며, 담게 되는 변경은 받지 않는다.
