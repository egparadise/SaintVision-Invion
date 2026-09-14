# Studio authentication entry

`/` keeps the pilot observation dashboard. `/studio` loads the full App and requires
login; `/callback` finishes the same login transaction. These paths need the SPA
index fallback at the frontend server. Proxy `/v1/*` and `/readyz` to the configured
kernel factory. The optional business surface may also be enabled on that factory.

The operator serves public configuration in `/auth-config.js` before the app bundle:

```js
window.__SAINTVISION_CONFIG__ = {
  idpAuthorizeUrl: 'https://identity.example/authorize',
  idpTokenUrl: 'https://identity.example/token',
  clientId: 'registered-public-web-client',
  scope: 'inv.api'
};
```

These example URLs are placeholders. No operational identity provider is configured
by this commit. Register the exact frontend origin plus `/callback` as redirect URI.
Use a public client supporting authorization code with S256 PKCE and token-endpoint
CORS for the exact frontend origin. HTTPS is required except for localhost testing.
The kernel must trust the matching issuer/JWKS, audience, client ID and tenant; project
permissions remain database grants. Configure the browser origin on the kernel too.
Never put a client secret, signing key, access token or refresh token in this file.

Code exchange uses a form body, the original redirect URI and verifier
([RFC 6749 §4.1.3](https://www.rfc-editor.org/rfc/rfc6749#section-4.1.3),
[RFC 7636 §4.5](https://www.rfc-editor.org/rfc/rfc7636#section-4.5)). The browser consumes
the state transaction once with a ten-minute deadline and validates that configuration
has not changed. It does not parse JWT claims into permissions. `GET /v1/session`
validates the access token on the resource server and returns `SessionView`:
`subjectId`, operator-configured `tenantId`, and Unix-seconds `expiresAt`. Responses
are no-store; no raw token or IdP role claims are returned. User display currently uses
this canonical subject, not an unverified display name. ID/refresh tokens are not used;
reload requires a new login. Logout clears the local session, not the IdP SSO session.

The kernel-only project catalog is `{items:[{projectId}]}`; the optional business
catalog is `{projects:[...]}`. The frontend distinguishes these envelopes without a
second fallback request. Kernel catalog rows have no fabricated display names, creation
dates or business linkage status. Workspace provisioning and every other screen still
need their own configured capabilities and acceptance; entry integration is not full
product acceptance.

Validation: install requirements-browser.txt and frontend dependencies, then run
`python tools/run_approval_browser_test.py`. This creates a disposable PostgreSQL
cluster and exercises both the ApprovalCenter harness and the real `/studio` entry in
Edge/Chromium. The local synthetic authorization server verifies single-use code,
redirect URI, client and S256 verifier; the production factory validates signed JWTs.
The full App test checks valid login/project/approval/logout and wrong-audience token
rejection. No responses are intercepted by Playwright. This is not operational SSO,
remote Node execution, or independent reviewer acceptance.
