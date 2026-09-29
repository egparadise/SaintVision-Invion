# deploy/intranet

사내망 identity provider와 control plane의 OIDC 신뢰 bundle을 세우는 스크립트다.
절차·근거·검증 결과는 `docs/vault/40_Operations/사내망_IdP_호스트명_인벤토리_런북_2026-09-30.md`에 있다.

| 파일 | 어디서 실행 | 무엇 |
|---|---|---|
| `idp-up.sh` | IdP 노드 | Keycloak + 전용 PostgreSQL을 digest 고정으로 기동한다. 비밀은 노드의 `0600` 파일에서 만들고, 이미 있으면 다시 만들지 않는다 |
| `idp-realm.sh` | IdP 노드 | realm·client·mapper·client scope·사용자를 설정한다. **빈 Keycloak에서 realm 전체를 만들 수 있고**, 다시 돌려도 아무것도 새로 만들지 않는다 |
| `reissue-oidc-trust-bundle.sh` | control plane 호스트 | IdP의 JWKS로 신뢰 bundle을 다시 만든다. 임시 파일에 쓰고 검증한 뒤에만 자리를 바꾸므로 실패해도 기존 bundle이 남는다 |
| `sv-oidc-trust-bundle.service` / `.timer` | control plane 호스트 | 위 스크립트를 **매일** 돌린다. bundle은 7일이면 만료되므로 주 1회로는 한 번의 실패가 곧 장애다 |
| `inventory.example.json` | — | `tools/s01_readiness_preflight.py`가 읽는 인벤토리의 **형태**. 실제 값이 담긴 파일은 저장소에 두지 않는다 |

bundle을 만드는 쪽은 `tools/make_oidc_trust_bundle.py`이고, 받아들이는 쪽은
`services/control-plane/src/inv/identity.py`의 `AccessTokens`다. 두 쪽의 수용 조건이
같다는 것은 `tests/core/test_make_oidc_trust_bundle.py`가 붙들고 있다.

## 비밀

비밀번호·private key·토큰은 노드의 `0600` 파일에만 둔다. 이 디렉터리의 어떤 파일도
비밀을 담지 않으며, 담게 되는 변경은 받지 않는다.
