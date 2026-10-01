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
  CLOCK_SKEW_SEC,
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

    it('allows explicit endpoint overrides alongside issuer scoped to same origin and path', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'custom-client',
        idpAuthorizeUrl: 'https://192.168.45.143:8443/realms/saintvision/custom/auth',
        idpTokenUrl: 'https://192.168.45.143:8443/realms/saintvision/custom/token',
        idpLogoutUrl: 'https://192.168.45.143:8443/realms/saintvision/custom/logout',
        scope: 'openid profile email inv.api',
      };
      const cfg = authConfig();
      expect(cfg.idpAuthorizeUrl).toBe('https://192.168.45.143:8443/realms/saintvision/custom/auth');
      expect(cfg.idpTokenUrl).toBe('https://192.168.45.143:8443/realms/saintvision/custom/token');
      expect(cfg.idpLogoutUrl).toBe('https://192.168.45.143:8443/realms/saintvision/custom/logout');
      expect(cfg.scope).toBe('openid profile email inv.api');
    });

    it('rejects cross-origin authorize endpoint override alongside issuer', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpAuthorizeUrl: 'https://attacker.evil.lan:8443/steal/auth',
      };
      expect(() => authConfig()).toThrow('인가 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects authorize endpoint override outside issuer subpath', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpAuthorizeUrl: 'https://192.168.45.143:8443/other-realm/auth',
      };
      expect(() => authConfig()).toThrow('인가 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects cross-origin logout endpoint override alongside issuer', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpLogoutUrl: 'https://attacker.evil.lan:8443/steal/logout',
      };
      expect(() => authConfig()).toThrow('로그아웃 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects logout endpoint override outside issuer subpath', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpLogoutUrl: 'https://192.168.45.143:8443/other-realm/logout',
      };
      expect(() => authConfig()).toThrow('로그아웃 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects cross-origin token endpoint override alongside issuer (Codex Finding 1)', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpTokenUrl: 'https://attacker.evil.lan:8443/steal/token',
      };
      expect(() => authConfig()).toThrow('토큰 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects endpoint overrides outside issuer path hierarchy', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        idpTokenUrl: 'https://192.168.45.143:8443/other-realm/token',
      };
      expect(() => authConfig()).toThrow('토큰 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    });

    it('rejects mismatched logout origin in endpoint-pair mode without issuer', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        clientId: 'saintvision-web',
        idpAuthorizeUrl: 'https://auth.saintvision.lan/authorize',
        idpTokenUrl: 'https://auth.saintvision.lan/token',
        idpLogoutUrl: 'https://evil.saintvision.lan/logout',
      };
      expect(() => authConfig()).toThrow('로그아웃 엔드포인트의 origin이 인가 엔드포인트와 일치하지 않습니다.');
    });

    it('rejects mismatched origins in endpoint-pair mode without issuer', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        clientId: 'saintvision-web',
        idpAuthorizeUrl: 'https://auth.saintvision.lan/authorize',
        idpTokenUrl: 'https://token.saintvision.lan/token',
      };
      expect(() => authConfig()).toThrow('인가 엔드포인트와 토큰 엔드포인트의 origin이 서로 일치하지 않습니다.');
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

    it('rejects redirect_uri with cross-origin or non-/callback path (Claude L4 & L5-②)', () => {
      (window as any).__SAINTVISION_CONFIG__ = {
        issuer: 'https://192.168.45.143:8443/realms/saintvision',
        clientId: 'saintvision-web',
        redirectUri: 'https://evil.example.com/callback',
      };
      expect(() => authConfig()).toThrow('redirect_uri의 origin이 현재 웹 애플리케이션과 일치하지 않습니다.');

      (window as any).__SAINTVISION_CONFIG__.redirectUri = 'https://portal.saintvision.lan/wrong-path';
      expect(() => authConfig()).toThrow('redirect_uri의 경로는 /callback 이어야 합니다.');

      (window as any).__SAINTVISION_CONFIG__.redirectUri = '/callback#frag';
      expect(() => authConfig()).toThrow('redirect_uri에 fragment(해시)를 포함할 수 없습니다 (RFC 6749 §3.1.2).');

      (window as any).__SAINTVISION_CONFIG__.redirectUri = '/callback';
      expect(authConfig().redirectUri).toBe('https://portal.saintvision.lan/callback');
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

  describe('3. Token Expiration Enforcement (Server Contract: exp - iat <= 3600 & Clock Skew)', () => {
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

    it('rejects already expired tokens beyond clock skew (exp + 120 <= now)', () => {
      const now = Math.floor(Date.now() / 1000);
      const expiredToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now - 1800,
        exp: now - 150, // 150s past, beyond 120s clock skew
      });

      expect(() => validateTokenExpiration(expiredToken, now)).toThrow(
        '이미 만료된 인증 토큰입니다.'
      );
    });

    it('allows clock skew of up to 120s for expiring tokens (Claude M3)', () => {
      const now = Math.floor(Date.now() / 1000);
      // exp is 60s in the past; with 120s clock skew allowance, exp + 120 > now, so it does not throw
      const slightlyBehindToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-001',
        iat: now - 1800,
        exp: now - 60,
      });
      expect(() => validateTokenExpiration(slightlyBehindToken, now)).not.toThrow();
    });

    it('rejects malformed non-JWT tokens when requireJwt is enabled (Codex Finding 5)', () => {
      expect(() => validateTokenExpiration('opaque-token')).toThrow('인증 토큰(JWT) 형식이 올바르지 않습니다.');
      expect(() => validateTokenExpiration('a.b.c')).toThrow('인증 토큰(JWT) 형식이 올바르지 않습니다.');
    });

    it('rejects opaque token when options is empty object {} by defaulting requireJwt to true (Codex 2)', () => {
      expect(() => validateTokenExpiration('opaque-token', undefined, {})).toThrow('인증 토큰(JWT) 형식이 올바르지 않습니다.');
    });

    it('rejects JWT tokens missing integer exp or iat (Codex Finding 5)', () => {
      const now = Math.floor(Date.now() / 1000);
      expect(() => validateTokenExpiration(makeJwt({ sub: 'user' }))).toThrow(
        '인증 토큰에 유효한 정수형 exp 및 iat 클레임이 필요합니다.'
      );
      expect(() => validateTokenExpiration(makeJwt({ exp: 'not-int', iat: now }))).toThrow(
        '인증 토큰에 유효한 정수형 exp 및 iat 클레임이 필요합니다.'
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

      const idToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      const serverSubject = 'oidc:' + 'f'.repeat(64);
      const serverTenant = '00000000-0000-0000-0000-000000000099';

      // 1st fetch: IdP token endpoint
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: idToken,
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

    it('rejects callback when OIDC id_token is missing from token response (Codex Finding 2, Claude M2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('OIDC 인증 응답에 ID 토큰(id_token)이 누락되었습니다.');
    });

    it('rejects callback when OIDC id_token nonce does not match transaction nonce (Codex Finding 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const badNonceIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: 'attacker-tampered-nonce',
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: badNonceIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 nonce가 로그인 요청 트랜잭션과 일치하지 않습니다.');
    });

    it('rejects callback when OIDC id_token aud does not match clientId (Codex Finding 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const badAudIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'other-client-id',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: badAudIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 대상(aud)이 클라이언트 ID와 일치하지 않습니다.');
    });

    it('rejects callback when OIDC id_token iss does not match issuer (Codex Finding 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const badIssIdToken = makeJwt({
        iss: 'https://rogue-idp.example.com/realms/rogue',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: badIssIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 발급자(iss)가 설정된 issuer와 일치하지 않습니다.');
    });

    it('rejects callback when OIDC id_token exp is missing (Claude C1)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const missingExpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: missingExpIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 만료 시각(exp)이 정수가 아니거나 누락되었습니다.');
    });

    it('rejects callback when OIDC id_token exp is not an integer (Claude C1)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const stringExpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: '2026-10-01' as any,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: stringExpIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 만료 시각(exp)이 정수가 아니거나 누락되었습니다.');
    });

    it('rejects callback when OIDC id_token is already expired beyond clock skew (Claude C1)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now - 3600,
        exp: now + 1800,
      });

      const expiredIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now - 3600,
        exp: now - 150, // 150s in past > 120s clock skew
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: expiredIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰이 이미 만료되었습니다.');
    });

    it('accepts callback when OIDC id_token is expired by less than clock skew (120s) (Claude C1)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now - 1800,
        exp: now + 1800,
      });

      const slightlyExpiredIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now - 1800,
        exp: now - 60, // 60s past, within 120s clock skew
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: slightlyExpiredIdToken,
          token_type: 'Bearer',
        }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
          tenantId: 'tenant-test',
          expiresAt: now + 1800,
        }),
      });

      const session = await completeLogin();
      expect(session.token).toBe(oidcToken);
    });

    it('rejects multi-audience OIDC id_token when azp is missing (Claude R1)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const multiAudMissingAzpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: ['saintvision-web', 'other-client'] as any,
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: multiAudMissingAzpIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('다중 대상(aud) ID 토큰의 azp가 클라이언트 ID와 일치하지 않습니다.');
    });

    it('rejects multi-audience OIDC id_token when azp does not match clientId (Codex 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const multiAudBadAzpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: ['saintvision-web', 'other-client'] as any,
        azp: 'other-client',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: multiAudBadAzpIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('다중 대상(aud) ID 토큰의 azp가 클라이언트 ID와 일치하지 않습니다.');
    });

    it('rejects single-audience OIDC id_token with foreign azp (Claude R2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const singleAudBadAzpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        azp: 'other-client',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: singleAudBadAzpIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 azp가 클라이언트 ID와 일치하지 않습니다.');
    });

    it('rejects multi-audience OIDC id_token when aud array does not contain clientId (Claude R2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const audArrayWithoutClientId = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: ['foreign-client-1', 'foreign-client-2'] as any,
        azp: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: audArrayWithoutClientId,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 대상(aud) 목록에 클라이언트 ID가 포함되지 않았습니다.');
    });

    it('rejects OIDC id_token when aud is neither string nor array (Claude R2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const nonStringOrArrayAudIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 12345 as any,
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: nonStringOrArrayAudIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 대상(aud)이 올바르지 않습니다.');
    });

    it('accepts multi-audience OIDC id_token when azp matches clientId (Codex 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const multiAudGoodAzpIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: ['saintvision-web', 'other-client'] as any,
        azp: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: multiAudGoodAzpIdToken,
          token_type: 'Bearer',
        }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
          tenantId: 'tenant-test',
          expiresAt: now + 1800,
        }),
      });

      const session = await completeLogin();
      expect(session.token).toBe(oidcToken);
    });

    it('rejects callback when OIDC id_token iat is not an integer (Codex 2)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-12345&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'operator-alice',
        iat: now,
        exp: now + 1800,
      });

      const badIatIdToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'operator-alice',
        nonce: authUrl.searchParams.get('nonce'),
        iat: 'invalid' as any,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: badIatIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeLogin()).rejects.toThrow('ID 토큰의 발급 시각(iat)이 정수가 아닙니다.');
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

      const idToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'bad-token-user',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: invalidLifetimeToken,
          id_token: idToken,
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

      const idToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'user-srv-exp',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now - 100,
        exp: now + 500,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: idToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + 'e'.repeat(64),
          tenantId: '00000000-0000-0000-0000-000000000099',
          expiresAt: now - 200, // expired beyond clock skew
        }),
      });

      await expect(completeLogin()).rejects.toThrow('서버 사용자 응답이 올바르지 않습니다.');
    });

    it('rejects server session when identity.expiresAt - nowSec > 3600 + CLOCK_SKEW_SEC (Claude L5-①)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-srv-exceed&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-srv-exceed',
        iat: now,
        exp: now + 1800,
      });

      const idToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'user-srv-exceed',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: idToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + 'e'.repeat(64),
          tenantId: '00000000-0000-0000-0000-000000000099',
          expiresAt: now + 3600 + CLOCK_SKEW_SEC + 10, // exceeds 3600 + 120
        }),
      });

      await expect(completeLogin()).rejects.toThrow('서버 사용자 세션 유효 기간이 계약 허용치(최대 3600초)를 초과합니다.');
    });

    it('accepts server session within clock skew allowance (expiresAt - nowSec <= 3600 + 120) (Claude M3)', async () => {
      const authUrl = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=auth-code-srv-skew&state=${authUrl.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const oidcToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        sub: 'user-srv-skew',
        iat: now,
        exp: now + 1800,
      });

      const idToken = makeJwt({
        iss: 'https://192.168.45.143:8443/realms/saintvision',
        aud: 'saintvision-web',
        sub: 'user-srv-skew',
        nonce: authUrl.searchParams.get('nonce'),
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: oidcToken,
          id_token: idToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + 'e'.repeat(64),
          tenantId: '00000000-0000-0000-0000-000000000099',
          expiresAt: now + 3600 + 60, // 60s clock skew, within 120s allowance
        }),
      });

      const session = await completeLogin();
      expect(session.expiresAt).toBe(now + 3600 + 60);
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
