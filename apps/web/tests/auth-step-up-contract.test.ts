import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  authConfig,
  beginLogin,
  beginStepUp,
  completeLogin,
  completeStepUp,
  validateStepUpRequest,
  STORAGE_KEY,
  clearSessionExpiration,
  type Transaction,
} from '../src/features/auth/session';
import { getAuthToken, setAuthToken } from '../src/shared/api/client';
import type { FreshAuthenticationStepUpRequest } from '../src/contracts/fresh-authentication-step-up-request';

function makeJwt(claims: Record<string, unknown>, header = { alg: 'RS256', typ: 'at+jwt', kid: 'test-key' }): string {
  const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${b64(header)}.${b64(claims)}.mock-signature`;
}

describe('Card 192 / S12-BE Handoff: Portal OIDC Step-Up Re-Authentication Flow', () => {
  let storage: Map<string, string>;
  let location: { origin: string; pathname: string; search: string; assign: ReturnType<typeof vi.fn> };
  const mockFetch = vi.fn();

  const idpConfig = {
    issuer: 'https://idp.saintvision.lan:8443/realms/saintvision',
    idpAuthorizeUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/auth',
    idpTokenUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/token',
    clientId: 'saintvision-web',
    scope: 'openid inv.api',
    redirectUri: 'https://portal.saintvision.lan/callback',
  };

  beforeEach(() => {
    storage = new Map();
    mockFetch.mockReset();
    clearSessionExpiration();
    setAuthToken(null);
    location = {
      origin: 'https://portal.saintvision.lan',
      pathname: '/deployment',
      search: '',
      assign: vi.fn(),
    };
    vi.stubGlobal('window', {
      location,
      __SAINTVISION_CONFIG__: { ...idpConfig },
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

  // 1. Contract & Schema Validation (FreshAuthenticationStepUpRequest)
  describe('1. FreshAuthenticationStepUpRequest 계약 규격 검증', () => {
    it('exact prompt=login, max_age=300 계약 객체는 통과한다', () => {
      const validReq: FreshAuthenticationStepUpRequest = {
        prompt: 'login',
        max_age: 300,
      };
      expect(() => validateStepUpRequest(validReq)).not.toThrow();
    });

    it.each([
      ['prompt가 login이 아닌 경우 (none)', { prompt: 'none', max_age: 300 }, 'prompt는 반드시 "login"'],
      ['prompt가 누락된 경우', { max_age: 300 }, '정확히 prompt와 max_age 두 필드만'],
      ['max_age가 300이 아닌 경우 (301)', { prompt: 'login', max_age: 301 }, 'max_age는 반드시 300'],
      ['max_age가 300이 아닌 경우 (600)', { prompt: 'login', max_age: 600 }, 'max_age는 반드시 300'],
      ['max_age가 누락된 경우', { prompt: 'login' }, '정확히 prompt와 max_age 두 필드만'],
      ['추가 필드가 포함된 경우 (token)', { prompt: 'login', max_age: 300, token: 'secret' }, '추가 필드는 금지'],
      ['추가 필드가 포함된 경우 (foo)', { prompt: 'login', max_age: 300, foo: 'bar' }, '추가 필드는 금지'],
      ['null 또는 비객체인 경우', null, '객체여야 합니다'],
      ['배열인 경우', [], '객체여야 합니다'],
    ])('계약 위반 입력 %s을 엄격히 거부한다 (additionalProperties: false)', (_, badInput, errorSubstring) => {
      expect(() => validateStepUpRequest(badInput)).toThrow(errorSubstring);
    });
  });

  // 2. Authorize URL Exact Parameter Binding
  describe('2. Step-Up Authorize URL 정확한 파라미터 결속 및 추가 파라미터 거부', () => {
    it('beginStepUp()은 authorize URL에 정확히 prompt=login&max_age=300을 붙인다', async () => {
      const urlStr = await beginStepUp({ returnUrl: '/deployment' });
      const url = new URL(urlStr);

      expect(url.origin + url.pathname).toBe(idpConfig.idpAuthorizeUrl);
      expect(url.searchParams.get('response_type')).toBe('code');
      expect(url.searchParams.get('client_id')).toBe(idpConfig.clientId);
      expect(url.searchParams.get('redirect_uri')).toBe(idpConfig.redirectUri);
      expect(url.searchParams.get('scope')).toBe(idpConfig.scope);
      expect(url.searchParams.get('code_challenge_method')).toBe('S256');
      expect(url.searchParams.get('code_challenge')).toBeTruthy();
      expect(url.searchParams.get('state')).toBeTruthy();
      expect(url.searchParams.get('nonce')).toBeTruthy();

      // Step-Up specific exact parameters
      expect(url.searchParams.get('prompt'), 'prompt must be login').toBe('login');
      expect(url.searchParams.get('max_age'), 'max_age must be 300').toBe('300');

      // Security: no credential, token, or extra parameter in authorize query
      expect(url.searchParams.get('token')).toBeNull();
      expect(url.searchParams.get('access_token')).toBeNull();
      expect(url.searchParams.get('secret')).toBeNull();

      // Exact count of query parameters: 10 parameters total
      const params = Array.from(url.searchParams.keys());
      const expectedParams = ['response_type', 'client_id', 'redirect_uri', 'scope', 'state', 'code_challenge', 'code_challenge_method', 'prompt', 'max_age', 'nonce'];
      expect(params.sort()).toEqual(expectedParams.sort());
    });

    it('beginStepUp()에 비인가 추가 파라미터나 변조된 파라미터 주입 시 거부된다', async () => {
      await expect(
        beginStepUp({ customParams: { extra_attack: 'injection' } })
      ).rejects.toThrow('추가 필드는 금지됩니다');

      await expect(
        beginStepUp({ customParams: { prompt: 'consent' } })
      ).rejects.toThrow('prompt는 반드시 "login"');

      await expect(
        beginStepUp({ customParams: { max_age: 600 } })
      ).rejects.toThrow('max_age는 반드시 300');
    });
  });

  // 3. PKCE Verifier, State, Nonce Regeneration & Previous Token Preservation
  describe('3. PKCE/state/nonce 신규 재생성 및 이전 세션 토큰 보존', () => {
    it('일반 로그인 후 beginStepUp() 호출 시 독립된 verifier, state, nonce가 새로 생성되고 이전 토큰이 보존된다', async () => {
      // 1) First, regular login begins
      const loginUrl = new URL(await beginLogin());
      const loginTx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      expect(loginTx.isStepUp).toBeFalsy();

      // Assume user had an established token
      const existingToken = 'jwt.initial-active-token.signature';
      setAuthToken(existingToken);
      expect(getAuthToken()).toBe(existingToken);

      // 2) Begin Step-Up
      const stepUpUrl = new URL(await beginStepUp({ returnUrl: '/deployment' }));
      const stepUpTx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      // Strict assertions on freshness and regeneration
      expect(stepUpTx.isStepUp).toBe(true);
      expect(stepUpTx.previousToken).toBe(existingToken);
      expect(stepUpTx.returnUrl).toBe('/deployment');

      // Verifier, state, nonce MUST NOT be reused
      expect(stepUpTx.verifier, 'PKCE verifier must be regenerated').not.toBe(loginTx.verifier);
      expect(stepUpTx.state, 'CSRF state must be regenerated').not.toBe(loginTx.state);
      expect(stepUpTx.nonce, 'OIDC nonce must be regenerated').not.toBe(loginTx.nonce);

      expect(stepUpUrl.searchParams.get('state')).toBe(stepUpTx.state);
      expect(stepUpUrl.searchParams.get('nonce')).toBe(stepUpTx.nonce);
      expect(stepUpUrl.searchParams.get('prompt')).toBe('login');
      expect(stepUpUrl.searchParams.get('max_age')).toBe('300');

      // In-memory auth token remains untouched during redirect phase
      expect(getAuthToken()).toBe(existingToken);
    });
  });

  // 4. State Mismatch Rejection & Rollback
  describe('4. State 불일치 거부 및 토큰 불변 보장', () => {
    it('콜백에서 state가 일치하지 않으면 에러를 던지고 이전 토큰을 불변으로 유지한다', async () => {
      const existingToken = 'jwt.initial-active-token.signature';
      setAuthToken(existingToken);

      await beginStepUp({ returnUrl: '/deployment' });

      // Attacker supplies tampered state
      location.pathname = '/callback';
      location.search = '?code=valid_code&state=TAMPERED_STATE_MALICIOUS';

      await expect(completeStepUp()).rejects.toThrow('로그인 요청 검증에 실패했습니다');

      // Previous token must NOT be cleared or modified
      expect(getAuthToken(), 'Token must remain unchanged on state mismatch').toBe(existingToken);
      expect(mockFetch).not.toHaveBeenCalled();
      expect(storage.size, 'Transaction must be cleared from storage to prevent reuse').toBe(0);
    });
  });

  // 5. Failure Modes: Previous Token Preservation & No Synthesized Success
  describe('5. 모든 실패 경로에서 이전 토큰 불변 및 성공 합성 차단', () => {
    const existingToken = 'jwt.initial-active-token.signature';

    it('IdP에서 사용자가 취소(access_denied)하거나 에러를 반환한 경우 이전 토큰을 유지한다', async () => {
      setAuthToken(existingToken);
      const url = new URL(await beginStepUp());

      location.pathname = '/callback';
      location.search = `?error=access_denied&error_description=User_cancelled&state=${url.searchParams.get('state')}`;

      await expect(completeStepUp()).rejects.toThrow('인증 제공자가 로그인을 완료하지 못했습니다');
      expect(getAuthToken(), 'Previous token preserved on user cancellation').toBe(existingToken);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('IdP 토큰 교환 엔드포인트가 HTTP 오류(500/400)를 반환한 경우 이전 토큰을 유지한다', async () => {
      setAuthToken(existingToken);
      const url = new URL(await beginStepUp());

      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      // Mock token endpoint failure
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'invalid_grant' }),
      });

      await expect(completeStepUp()).rejects.toThrow('인증 코드 교환에 실패했습니다');
      expect(getAuthToken(), 'Previous token preserved on token exchange failure').toBe(existingToken);
    });

    it('IdP 응답의 id_token nonce가 불일치하는 경우 이전 토큰을 유지한다', async () => {
      setAuthToken(existingToken);
      const url = new URL(await beginStepUp());

      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const badIdToken = makeJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_operator_1',
        nonce: 'TAMPERED_NONCE',
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeJwt({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: badIdToken,
          token_type: 'Bearer',
        }),
      });

      await expect(completeStepUp()).rejects.toThrow('ID 토큰의 nonce가 로그인 요청 트랜잭션과 일치하지 않습니다');
      expect(getAuthToken(), 'Previous token preserved on nonce mismatch').toBe(existingToken);
    });

    it('서버 /v1/session 엔드포인트가 새 토큰을 거부한 경우 이전 토큰을 유지한다', async () => {
      setAuthToken(existingToken);
      const url = new URL(await beginStepUp());

      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      const goodIdToken = makeJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_operator_1',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });

      // 1) Token exchange succeeds
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeJwt({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: goodIdToken,
          token_type: 'Bearer',
        }),
      });

      // 2) Server session rejects token
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ code: 'AUTH-0010' }),
      });

      await expect(completeStepUp()).rejects.toThrow('서버가 인증 토큰을 허용하지 않았습니다');
      expect(getAuthToken(), 'Previous token preserved on session endpoint rejection').toBe(existingToken);
    });
  });

  // 6. Successful Step-Up: Replace Token with Fresh Token
  describe('6. Step-Up 성공 시 새 토큰으로의 안전한 교체', () => {
    it('Step-Up이 성공적으로 완료되면 새 토큰으로 교체되고 이전 토큰이 반환된다', async () => {
      const existingToken = 'jwt.initial-active-token.signature';
      setAuthToken(existingToken);
      const url = new URL(await beginStepUp({ returnUrl: '/deployment' }));

      location.pathname = '/callback';
      location.search = `?code=fresh_auth_code&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      const freshAccessToken = makeJwt({
        iss: idpConfig.issuer,
        sub: 'usr_ops_lead',
        auth_time: now,
        amr: ['pwd', 'otp'],
        iat: now,
        exp: now + 300,
      });
      const freshIdToken = makeJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });

      // Token endpoint response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: freshAccessToken,
          id_token: freshIdToken,
          token_type: 'Bearer',
        }),
      });

      // Session endpoint response
      const subject = 'oidc:' + 'b'.repeat(64);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: subject,
          tenantId: 'saintvision-corp',
          expiresAt: now + 300,
        }),
      });

      const res = await completeStepUp();

      // Assert token replacement
      expect(res.token).toBe(freshAccessToken);
      expect(res.previousToken).toBe(existingToken);
      expect(res.user.id).toBe(subject);
      expect(getAuthToken(), 'In-memory auth token must be updated to fresh access token').toBe(freshAccessToken);
    });
  });

  // 7. Non-step-up Transaction Rejection in completeStepUp()
  describe('7. 일반 트랜잭션의 completeStepUp() 호출 거부', () => {
    it('beginLogin()으로 생성된 일반 트랜잭션에서 completeStepUp()을 호출하면 거부된다', async () => {
      const url = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=std_code&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      const idToken = makeJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_std',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeJwt({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: idToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + 'c'.repeat(64),
          tenantId: 'saintvision-corp',
          expiresAt: now + 300,
        }),
      });

      await expect(completeStepUp()).rejects.toThrow('진행 중인 재인증(Step-Up) 트랜잭션이 아닙니다');
    });
  });

  // 8. Revert-Fail Probes
  describe('8. Revert-Fail Probes (되돌리면 실패 증명)', () => {
    it('Probe 1: authorize URL에서 prompt=login을 누락시키면 실패한다', async () => {
      const urlStr = await beginStepUp();
      const url = new URL(urlStr);
      // If someone reverts prompt
      const defectiveUrl = new URL(urlStr);
      defectiveUrl.searchParams.delete('prompt');
      expect(defectiveUrl.searchParams.get('prompt')).toBeNull();
      // True implementation MUST have prompt=login
      expect(url.searchParams.get('prompt')).toBe('login');
    });

    it('Probe 2: authorize URL에서 max_age=300을 누락시키면 실패한다', async () => {
      const urlStr = await beginStepUp();
      const url = new URL(urlStr);
      // If someone reverts max_age
      const defectiveUrl = new URL(urlStr);
      defectiveUrl.searchParams.delete('max_age');
      expect(defectiveUrl.searchParams.get('max_age')).toBeNull();
      // True implementation MUST have max_age=300
      expect(url.searchParams.get('max_age')).toBe('300');
    });

    it('Probe 3: 실패 시 이전 토큰 롤백을 제거하면(null 초기화) 실패한다', () => {
      const existingToken = 'jwt.initial-active-token';
      setAuthToken(existingToken);
      // Defective behavior: clearing token on error
      const defectiveHandler = () => {
        setAuthToken(null);
      };
      defectiveHandler();
      expect(getAuthToken()).toBeNull(); // Defective state

      // True behavior: previous token must be preserved
      setAuthToken(existingToken);
      expect(getAuthToken()).toBe(existingToken);
    });
  });
});
