# Intranet end-to-end smoke — BLOCKED_EXTERNAL

- code SHA: `13c20c83b959f88c466c09d6198c4b824889ee7e`
- collector SHA-256: `767736d454d0d9015a735912927523c4060b2f1b4a4a75f14b39af4d59eb3178`
- observed: 2026-09-30T00:35:15Z
- ran in: **operator-workstation**
- IdP name: `idp.sv.lan` (no address is recorded)
- expected issuer: `https://idp.sv.lan/realms/saintvision`
- CA bundle SHA-256: `92455f1b778130334da43b0eee977357b5ae498eb1005bc29ecc6c3afb7192ba` — a trust anchor, not a pin
- control plane: `loopback:18081`

| observation | status | detail |
|---|---|---|
| `idpNameResolves` | BLOCKED_EXTERNAL | reason=hosts-not-applied |
| `idpHttpsVerified` | BLOCKED_EXTERNAL | reason=the IdP name does not resolve on this host |
| `idpDiscoveryIssuer` | BLOCKED_EXTERNAL | reason=the IdP name does not resolve on this host |
| `idpJwksSameOrigin` | BLOCKED_EXTERNAL | reason=the IdP name does not resolve on this host |
| `passwordGrantRefused` | BLOCKED_EXTERNAL | reason=the IdP name does not resolve on this host |
| `clientCredentialsRefused` | BLOCKED_EXTERNAL | reason=the IdP name does not resolve on this host |
| `controlPlaneRejectsBadToken` | MEASURED_PASS | httpStatus=401, problemCode=AUTH-0050 |
| `controlPlaneRejectsMissingToken` | MEASURED_PASS | httpStatus=401, problemCode=AUTH-0050 |

Certificate verification is on and cannot be turned off; name resolution is the
system resolver and has no override. A `BLOCKED_EXTERNAL` here is a precondition
an operator still owes, not a defect to route around.
