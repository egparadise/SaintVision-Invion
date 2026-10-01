# Intranet end-to-end smoke — BLOCKED_EXTERNAL

- code SHA: `4e60acf35075e32bda3252b005c8ad9d25d26374`
- collector SHA-256: `b3c1d6f011f822fb1881e9d541f594a1d89f4b1502c9033600911bc377dcf859`
- observed: 2026-09-30T01:51:02Z
- ran in: **operator-workstation**
- issuer under test: `https://idp.sv.lan/realms/saintvision` (taken from the control plane's own config)
- control plane config SHA-256: `a2eb56f0bb2ba7d767b46203a1e998ef2ee8095938c8114d983ffb6a79e9f2cc`
- trust bundle SHA-256: `fee3816aec406534d41646dc9ad1ef80d17b52b1dd5077ad6ee39f47dfff199c`
- CA bundle SHA-256: `92455f1b778130334da43b0eee977357b5ae498eb1005bc29ecc6c3afb7192ba` — a trust anchor, not a pin
- approved anchors: 2
- control plane: `loopback:18082` (readyz: 503)

| observation | status | detail |
|---|---|---|
| `controlPlaneConfigurationBound` | MEASURED_PASS | issuerIsCanonical=True, clientIdSha256=13c95d85eba6d768927953300fc8136037048105df85461f86b76c87dd8ee17f, trustedKeyCount=1 |
| `idpNameResolves` | BLOCKED_EXTERNAL | reason=hosts-not-applied |
| `idpHttpsVerified` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `idpDiscoveryIssuer` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `portalClientKnown` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `idpJwksMatchesTrustBundle` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `passwordGrantRefused` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `clientCredentialsRefused` | BLOCKED_EXTERNAL | reason=the issuer's host does not resolve on this host |
| `controlPlaneRejectsBadToken` | MEASURED_PASS | httpStatus=401, contentType=application/problem+json, problemCode=AUTH-0050, canonicalShape=True, probe=signed-but-invalid |
| `controlPlaneRejectsMissingToken` | MEASURED_PASS | httpStatus=401, contentType=application/problem+json, problemCode=AUTH-0050, canonicalShape=True, probe=no-authorization |

The issuer, the client id and the trusted key ids come from the control plane's
configuration, not from this command line, and the TLS target is derived from that
issuer -- so the SNI, the Host header and the announced issuer are one string.
Verification cannot be turned off and resolution cannot be substituted. Once a name
has resolved, a connection or TLS failure is a failure, not a missing precondition.
