# OIDC identity evidence — PASS

- code SHA: `de84d1061a3358ff2163c81538a9b96e1a37aee8`
- collector SHA-256: `f7f11c3196086d6ca804c59bb1e2c32f7fc6c71d9e11114617cc519c837cf49b`
- observed: 2026-09-29T23:42:47Z
- provider: **production**
- issuer mode: **https**, issuer SHA-256 `ae8816d9369e5861cd6ac6b9a4269fae617855bb3adb4cb7088649ba5466bd93`
- keys in bundle: 1 (dropped non-signing: 1)
- temporary bundle removed: True

| observation | status | detail |
|---|---|---|
| `bundleAccepted` | MEASURED_PASS | loadedKeyCount=1 |
| `liveTokenVerified` | MEASURED_PASS | tokenTypeHeader=at+jwt, subjectIsDerivedPseudonym=True, expiresAtInFuture=True |
| `tamperedTokenRefused` | MEASURED_PASS | code=AUTH-0050, httpStatus=401 |

No token, username or key material is recorded here. A key id appears only as
its SHA-256, and the issuer only as its scheme plus a SHA-256 of the string.
