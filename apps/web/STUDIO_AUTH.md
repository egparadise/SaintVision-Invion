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


## Built HTTPS proxy verification

Compose requires `INV_WEB_AUTH_CONFIG` to point to an existing public JavaScript
configuration file. It mounts that single file read-only at `/auth-config.js` and
will not create a missing host path. Keep TLS certificate/key mounts separate.
The provided Compose publishes HTTPS on 8443 and HTTP on 8081; HTTP redirects target
8443. A different external port needs an explicit redirect configuration change.

```powershell
docker build -t saintvision-web-candidate:studio-tls apps/web
$env:INV_WEB_IMAGE = 'saintvision-web-candidate:studio-tls'
python -m pytest -q tests/integration/test_web_container.py tests/core/test_deployment_credentials.py
```

Install requirements-backend.txt and requirements-browser.txt first. Windows uses
installed Edge; Linux needs `python -m playwright install --with-deps chromium`.
The opt-in test runs the actual built frontend container, with an ephemeral local
certificate and a separate HTTP transport fixture. Ports bind only to 127.0.0.1.
httpx trusts the test certificate explicitly and rejects it without that trust;
the browser pins only its ephemeral SPKI. No OS trust store or operational certificate
is modified. Containers and networks are removed only after ownership-label checks.

The tests cover mounted public configuration, full `/studio` bundle rendering,
no-store and security headers, cache exclusion, real proxy Bearer/status forwarding,
first SSE event delivery before the upstream finishes, query/Referer log redaction,
and disconnect/reconnect of the same upstream container. The upstream is deliberately
**a transport fixture**, not a replacement for kernel/JWT/DB acceptance or the prior
synthetic PKCE full-App test. No operational SSO or remote Node execution is claimed.

Nginx's local Docker health check measures its HTTP liveness. `/readyz` separately
proxies backend readiness and preserves failure statuses. Static cache headers must
include security-headers.conf because Nginx 1.27 does not inherit parent `add_header`
when a location declares its own ([Nginx reference](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header)).
Canonical project Run SSE has buffering disabled. Upstream connection timeout is two
seconds; a stopped endpoint returns 502/504 instead of serving SPA success content.
Existing `tools/deploy_intranet.ps1` is not part of this acceptance: its hard-coded
success reporting and simulated deployment checks need a separate cleanup before it
can serve as an operational acceptance script.
