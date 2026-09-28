# S02-DB AC-02 acceptance evidence — `1e8baf045c5a`

- verdict (measured part): **FAIL** · acceptanceClaim: `false`
- captured: 2026-09-28T05:30:57+09:00 · executor: Claude · clean tree: False
- API suite `tests/test_api.py`: status `complete`, exit 0, counts {'passed': 28, 'failed': 0, 'error': 0, 'skipped': 0}, junit sha256 `f9525f6579e889b8`

| AC-02 clause | status | cases |
|---|---|---|
| 허용 Node 등록·조회 성공 (`allowed-node-registration-and-read`) | **pass** | test_enrolled_node_is_registered_and_readable=passed, test_node_enrollment_db_route_rejects_invalid_response_shape=passed, test_heartbeat_advances_and_replays_are_ignored=passed, test_heartbeat_observations_land_in_the_right_partition=passed |
| 토큰 재사용 차단 (`bootstrap-token-replay-blocked`) | **pass** | test_bootstrap_token_cannot_be_used_twice=passed, test_unknown_bootstrap_token_is_rejected=passed, test_missing_credential_is_refused=passed, test_unknown_credential_is_refused=passed |
| 다른 project/tenant 정보 접근 차단 (`cross-tenant-project-isolation`) | **pass** | test_another_tenants_node_is_not_listed=passed, test_another_tenants_node_is_not_readable_by_id=passed, test_project_scope_is_checked_separately_from_tenancy=passed, test_another_tenant_cannot_see_the_contribution=passed, test_a_tokens_tenant_is_binding=passed, test_a_heartbeat_for_a_node_you_are_not_is_refused=passed, test_liveness_sweep_does_not_cross_tenants=passed |
| 인증 실패 기록 (`denial-recorded`) | **pass** | test_denials_are_recorded=passed |

- RLS boundary: **VIOLATIONS** (exit 1), roles ['inv_app', 'inv_discovery_issuer', 'inv_discovery_issuer_guard', 'inv_kernel', 'inv_runtime_dev'], violations 1, accepted 9, unmeasured 0 → `docs\vault\30_Development\Evidence\s02-db-acceptance\s02-acceptance-1e8baf045c5a-20260927-rls.json`

| external wait | status | value |
|---|---|---|
| U2 실 IdP(OIDC issuer/JWKS) 경유 로그인 (user decision; S02-BE) | UNMEASURED | — |
| U3 실 CA 발급 Node 인증서 (user; S01-BE) | UNMEASURED | — |
| U4 DNS/endpoint 확정 (user; S01-BE) | UNMEASURED | — |
| U5 물리 Node mTLS/heartbeat 실장비 (user hardware; S02-BE) | UNMEASURED | — |

- browser acceptance: `not_in_scope` (browser (Gemini/Codex))

- note: card 13 fixed-SHA run; disposable PostgreSQL 16 at 127.0.0.1:55432; sequential single invocation
