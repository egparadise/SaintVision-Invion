# OIDC identity evidence — NOT_OBSERVED

- code SHA: `b64ba4cb84e10c11df1bd156dffc4ce53a2bf5d6`
- collector SHA-256: `f7f11c3196086d6ca804c59bb1e2c32f7fc6c71d9e11114617cc519c837cf49b`
- observed: 2026-09-29T23:17:34Z
- provider: **production**
- issuer mode: **http**, issuer SHA-256 `c3c087f30dcaaaea458c9361160b427ac74fa555e5f27aa1e5486d12cff38ddb`
- keys in bundle: None (dropped non-signing: None)
- temporary bundle removed: True

| observation | status | detail |
|---|---|---|
| `bundleAccepted` | NOT_OBSERVED | reason=measurement raised BundleRefused |
| `liveTokenVerified` | NOT_OBSERVED | reason=measurement raised BundleRefused |
| `tamperedTokenRefused` | NOT_OBSERVED | reason=measurement raised BundleRefused |

No token, username or key material is recorded here. A key id appears only as
its SHA-256, and the issuer only as its scheme plus a SHA-256 of the string.
