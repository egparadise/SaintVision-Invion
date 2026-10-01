# OIDC identity evidence — PASS

- code SHA: `8cf656eab8799da7e9ad6b3c368394de2ba8d59b`
- collector SHA-256: `558ad4b739215781f0e7e24d0fb0a4aac0b6e3fc8dd4edd20c26986f6b2a419b`
- observed: 2026-09-30T00:14:45Z
- provider: **production**
- signing keys arrived: **out-of-band-file** (this artifact says nothing about that transport)
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
