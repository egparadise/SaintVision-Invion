import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  authConfig,
  beginLogin,
  completeLogin,
  parseJwtPayload,
  validateTokenExpiration,
  registerSessionExpiration,
  clearSessionExpiration,
  onTokenExpired,
  buildLogoutUrl,
  performLogout,
  STORAGE_KEY,
} from '../src/features/auth/session';
import { getAuthToken, setAuthToken } from '../src/shared/api/client';

function makeJwt(claims: Record<string, unknown>, header = { alg: 'RS256', typ: 'at+jwt', kid: 'test-key' }): string {
  const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${b64(header)}.${b64(claims)}.mock-signature`;
}

describe('OIDC Corporate IdP & Server Contract Verification (Card 153)', () => {
  let storage: Map<string, string>;
  let location: { origin: string; pathname: string; search: string; assign: ReturnType<typeof vi.fn> };
  const mockFetch = vi.fn();

  beforeEach(() => {
    storage = new Map();
    mockFetch.mockReset();
    clearSessionExpiration();
    setAuthToken(null);
    location = {
      origin: 'https://portal.saintvision.lan',
      pathname: '/studio',
      search: '',
      assign: vi.fn(),
    };
    vi.stubGlobal('window', {
      location,
      __SAINTVISION_CONFIG__: {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
      },
      history: { replaceState: vi.fn() },
    });
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => storage.set(k, v),
      removeItem: (k: string) => storage.delete(k),
    });
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    clearSessionExpiration();
    setAuthToken(null);
    vi.unstubAllGlobals();
  });

  describe('1. Dynamic Issuer & Client ID Configuration (No Hardcoding, No Dev IdP Fallback)', () => {
    it('resolves standard Keycloak/OIDC endpoints from issuer without trailing slash', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision/',
        clientId: 'saintvision-web',
      };
      const cfg = authConfig();
      expect(cfg.issuer).toBe('https://192.168.45.143:8443/realms/saintvision');
      expect(cfg.clientId).toBe('saintvision-web');
      expect(cfg.scope).toBe('openid inv.api');
      expect(cfg.idpAuthorizeUrl).toBe('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/auth');
      expect(cfg.idpTokenUrl).toBe('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/token');
      expect(cfg.idpLogoutUrl).toBe('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/logout');
      expect(cfg.redirectUri).toBe('https://portal.saintvision.lan/callback');
    });

    it('allows explicit endpoint overrides alongside issuer', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'custom-client',
        idpAuthorizeUrl: 'https://idp.saintvision.lan:8443/custom/auth?realm=sv',
        idpTokenUrl: 'https://idp.saintvision.lan:8443/custom/token',
        idpLogoutUrl: 'https://idp.saintvision.lan:8443/custom/logout',
        scope: 'openid profile email inv.api',
      };
      const cfg = authConfig();
      expect(cfg.idpAuthorizeUrl).toBe('https://idp.saintvision.lan:8443/custom/auth?realm=sv');
      expect(cfg.idpTokenUrl).toBe('https://idp.saintvision.lan:8443/custom/token');
      expect(cfg.idpLogoutUrl).toBe('https://idp.saintvision.lan:8443/custom/logout');
      expect(cfg.scope).toBe('openid profile email inv.api');
    });

    it('fails closed when clientId is missing or blank', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: '   ',
      };
      expect(() => authConfig()).toThrow('클라이언트 ID(clientId) 설정이 필요합니다.');
    });

    it('fails closed when neither issuer nor endpoint pair is configured (No Dev IdP Fallback)', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        clientId: 'saintvision-web',
      };
      expect(() => authConfig()).toThrow('인증 서버 설정(issuer 또는 idpAuthorizeUrl과 idpTokenUrl)이 필요합니다.');
    });

    it('rejects remote plain HTTP endpoints to prevent credential interception', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'http://192.168.45.143:8080/realms/saintvision',
        clientId: 'saintvision-web',
      };
      expect(() => authConfig()).toThrow('인증 서버 issuer URL이 안전한 주소가 아닙니다.');
    });

    it('rejects endpoints containing embedded credentials or URL fragments', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://admin:secret@idp.corp.lan/realms/saintvision',
        clientId: 'saintvision-web',
      };
      expect(() => authConfig()).toThrow('인증 서버 issuer URL이 안전한 주소가 아닙니다.');
    });
  });

  describe('2. OIDC Authorization Code Flow with PKCE (RFC 7636)', () => {
    it('initiates login with S256 code challenge, nonce, state, and standard OIDC query params', async () => {
      const authUrlString = await beginLogin();
      const authUrl = new URL(authUrlString);

      expect(authUrl.origin + authUrl.pathname).toBe('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/auth');
      expect(authUrl.searchParams.get('response_type')).toBe('code');
      expect(authUrl.searchParams.get('client_id')).toBe('saintvision-web');
      expect(authUrl.searchParams.get('redirect_uri')).toBe('https://portal.saintvision.lan/callback');
      expect(authUrl.searchParams.get('scope')).toBe('openid inv.api');
      expect(authUrl.searchParams.get('code_challenge_method')).toBe('S256');

      const challenge = authUrl.searchParams.get('code_challenge');
      expect(challenge).toBeTruthy();
      expect(/^[A-Za-z0-9_-]+$/.test(challenge!)).toBe(true);

      const state = authUrl.searchParams.get('state');
      expect(state).toHaveLength(32);

      const nonce = authUrl.searchParams.get('nonce');
      expect(nonce).toHaveLength(32);

      // Transaction stored in sessionStorage
      const rawTx = storage.get(STORAGE_KEY);
      expect(rawTx).toBeTruthy();
      const tx = JSON.parse(rawTx!);
      expect(tx.state).toBe(state);
      expect(tx.nonce).toBe(nonce);
      expect(tx.verifier).toBeTruthy();
      expect(tx.verifier.length).toBeGreaterThanOrEqual(43);
    });
  });

  describe('3. Token Expiration Enforcement (Server Contract: exp - iat <= 3600)', () => {
    it('accepts tokens strictly complying with server lifetime limit (lifetime <= 3600)', () => {
      const now = Math.floor(Date.now() / 1000);
      const validToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now,
        exp: now + 3600, // exactly 1 hour
      });

      expect(() => validateTokenExpiration(validToken, now)).not.toThrow();
      const claims = parseJwtPayload(validToken);
      expect(claims?.exp).toBe(now + 3600);
      expect(claims?.iat).toBe(now);
    });

    it('rejects tokens exceeding 3600s server contract lifetime (e.g. 2-hour or 24-hour tokens)', () => {
      const now = Math.floor(Date.now() / 1000);
      const excessiveToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now,
        exp: now + 7200, // 2 hours
      });

      expect(() => validateTokenExpiration(excessiveToken, now)).toThrow(
        '인증 토큰 유효 기간이 서버 계약 허용치(최대 3600초)를 초과하거나 올바르지 않습니다.'
      );
    });

    it('rejects tokens where exp <= iat (reversed or zero lifetime)', () => {
      const now = Math.floor(Date.now() / 1000);
      const invalidToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now + 100,
        exp: now + 50,
      });

      expect(() => validateTokenExpiration(invalidToken, now)).toThrow(
        '인증 토큰 유효 기간이 서버 계약 허용치(최대 3600초)를 초과하거나 올바르지 않습니다.'
      );
    });

    it('rejects already expired tokens (exp <= now)', () => {
      const now = Math.floor(Date.now() / 1000);
      const expiredToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now - 1800,
        exp: now - 10,
      });

      expect(() => validateTokenExpiration(expiredToken, now)).toThrow(
        '이미 만료된 인증 토큰입니다.'
      );
    });
  });

  describe('4. Mock OIDC End-to-End Code Exchange & Resource Server Verification', () => {
    it('executes full code exchange and session mount with mock Keycloak and /v1/session', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
        client_id: 'saintvision-web',
        scope: 'openid inv.api',
      });

      const serverSubject = 'oidc:' + 'f'.repeat(64);
      const serverTenant = '00000000-0000-0000-0000-000000000099';

      // 1st fetch: IdP token endpoint
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          token_type: 'Bearer',
          expires_in: 1800,
        }),
      });

      // 2nd fetch: /v1/session resource server verification
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: serverSubject,
          tenantId: serverTenant,
          expiresAt: now + 1800,
        }),
      });

      const session = await completeLogin();
      expect(session.token).toBe(oidcToken);
      expect(session.user.id).toBe(serverSubject);
      expect(session.user.tenantId).toBe(serverTenant);
      expect(session.expiresAt).toBe(now + 1800);

      // Verify token request parameters
      const [tokenUrl, tokenOptions] = mockFetch.mock.calls[0];
      expect(tokenUrl).toBe('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/token');
      expect(tokenOptions.method).toBe('POST');
      const body = tokenOptions.body as URLSearchParams;
      expect(body.get('grant_type')).toBe('authorization_code');
      expect(body.get('code')).toBe('auth-code-12345');
      expect(body.get('client_id')).toBe('saintvision-web');
      expect(body.get('redirect_uri')).toBe('https://portal.saintvision.lan/callback');
      expect(body.get('code_verifier')).toBeTruthy();

      // Verify resource server /v1/session request
      const [sessionUrl, sessionOptions] = mockFetch.mock.calls[1];
      expect(sessionUrl).toBe('/v1/session');
      expect(sessionOptions.headers.Authorization).toBe(`Bearer ${oidcToken}`);

      // Transaction removed from sessionStorage (single-use)
      expect(storage.size).toBe(0);
    });

    it('rejects IdP token that violates server lifetime limit before calling /v1/session', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-violator&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const invalidLifetimeToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'bad-token-user',
        iat: now,
        exp: now + 7200, // 2h > 3600 limit
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: invalidLifetimeToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow(
        '인증 토큰 유효 기간이 서버 계약 허용치(최대 3600초)를 초과하거나 올바르지 않습니다.'
      );
      // Resource server /v1/session was never called because fail-closed check stopped it
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it('rejects server session when /v1/session reports an expired timestamp', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-expired-srv&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-srv-exp',
        iat: now - 100,
        exp: now + 500,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + 'e'.repeat(64),
          tenantId: '00000000-0000-0000-0000-000000000099',
          expiresAt: now - 5, // expired on server
        }),
      });

      await expect(completeLogin()).rejects.toThrow('서버 사용자 응답이 올바르지 않습니다.');
    });
  });

  describe('5. Active Token Expiration Lifecycle & Re-login Notification', () => {
    it('schedules session expiration timer and dispatches [AUTH-0050] on timeout', () => {
      vi.useFakeTimers();
      const expiredHandler = vi.fn();
      const unsubscribe = onTokenExpired(expiredHandler);

      setAuthToken('bearer-active-session');
      expect(getAuthToken()).toBe('bearer-active-session');

      const now = Math.floor(Date.now() / 1000);
      const expiresAt = now + 60; // 60 seconds

      registerSessionExpiration(expiresAt);
      expect(expiredHandler).not.toHaveBeenCalled();

      // Advance by 59 seconds: still active
      vi.advanceTimersByTime(59000);
      expect(expiredHandler).not.toHaveBeenCalled();
      expect(getAuthToken()).toBe('bearer-active-session');

      // Advance by 2 more seconds: expired
      vi.advanceTimersByTime(2000);
      expect(expiredHandler).toHaveBeenCalledTimes(1);
      expect(expiredHandler).toHaveBeenCalledWith('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');
      // In-memory token cleared immediately
      expect(getAuthToken()).toBeNull();

      unsubscribe();
      vi.useRealTimers();
    });

    it('immediately expires if registerSessionExpiration is called with past timestamp', () => {
      const expiredHandler = vi.fn();
      const unsubscribe = onTokenExpired(expiredHandler);

      setAuthToken('bearer-already-expired');
      const now = Math.floor(Date.now() / 1000);

      registerSessionExpiration(now - 1);
      expect(expiredHandler).toHaveBeenCalledTimes(1);
      expect(expiredHandler).toHaveBeenCalledWith('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');
      expect(getAuthToken()).toBeNull();

      unsubscribe();
    });

    it('cancels pending expiration timer when clearSessionExpiration is called', () => {
      vi.useFakeTimers();
      const expiredHandler = vi.fn();
      const unsubscribe = onTokenExpired(expiredHandler);

      const now = Math.floor(Date.now() / 1000);
      registerSessionExpiration(now + 30);

      clearSessionExpiration();

      vi.advanceTimersByTime(60000);
      expect(expiredHandler).not.toHaveBeenCalled();

      unsubscribe();
      vi.useRealTimers();
    });
  });

  describe('6. Logout & Session Teardown', () => {
    it('builds standard OIDC RP-initiated logout URL with client_id and post_logout_redirect_uri', () => {
      const logoutUrl = buildLogoutUrl('https://portal.saintvision.lan/login');
      expect(logoutUrl).toBe(
        'https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/logout?client_id=saintvision-web&post_logout_redirect_uri=https%3A%2F%2Fportal.saintvision.lan%2Flogin'
      );
    });

    it('clears token, cancels timer, and purges storage during performLogout', () => {
      vi.useFakeTimers();
      const expiredHandler = vi.fn();
      const unsubscribe = onTokenExpired(expiredHandler);

      setAuthToken('bearer-to-be-logged-out');
      storage.set(STORAGE_KEY, JSON.stringify({ state: 'pending-tx' }));

      const now = Math.floor(Date.now() / 1000);
      registerSessionExpiration(now + 60);

      performLogout();

      expect(getAuthToken()).toBeNull();
      expect(storage.size).toBe(0);

      // Advance timers to verify timer was cleared
      vi.advanceTimersByTime(70000);
      expect(expiredHandler).not.toHaveBeenCalled();

      unsubscribe();
      vi.useRealTimers();
    });

    it('redirects to IdP end-session endpoint when redirectIdp option is specified', () => {
      setAuthToken('sample-token');
      const logoutUrl = performLogout({ redirectIdp: true });

      expect(logoutUrl).toContain('https://192.168.45.143:8443/realms/saintvision/protocol/openid-connect/logout');
      expect(location.assign).toHaveBeenCalledWith(logoutUrl);
      expect(getAuthToken()).toBeNull();
    });
  });
});
