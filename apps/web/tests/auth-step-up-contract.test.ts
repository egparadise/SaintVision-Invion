import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  authConfig,
  beginLogin,
  beginStepUp,
  commitSession,
  completeLogin,
  completeStepUp,
  validateStepUpRequest,
  STORAGE_KEY,
  clearSessionExpiration,
  type Transaction,
} from '../src/features/auth/session';
import { clearAuthToken, getAuthToken, setAuthToken } from '../src/shared/api/client';
import type { FreshAuthenticationStepUpRequest } from '../src/contracts/fresh-authentication-step-up-request';

describe('Card 192 / S12-BE Handoff: Portal OIDC Step-Up Re-Authentication Flow', () => {
  let storage: Map<string, string>;
  let location: { origin: string; pathname: string; search: string; assign: ReturnType<typeof vi.fn> };
  const mockFetch = vi.fn();

  let keyPair: CryptoKeyPair;
  let publicJwk: JsonWebKey & { kid: string; alg: string };

  beforeAll(async () => {
    // Generate real RS256 keypair for authentic ID token signing and JWKS verification
    keyPair = await crypto.subtle.generateKey(
      {
        name: 'RSASSA-PKCS1-v1_5',
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: 'SHA-256',
      },
      true,
      ['sign', 'verify'],
    );
    const jwk = await crypto.subtle.exportKey('jwk', keyPair.publicKey);
    publicJwk = { ...jwk, kid: 'test-key-01', alg: 'RS256' };
  });

  const getBaseIdpConfig = () => ({
    issuer: 'https://idp.saintvision.lan:8443/realms/saintvision',
    idpAuthorizeUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/auth',
    idpTokenUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/token',
    clientId: 'saintvision-web',
    scope: 'openid inv.api',
    redirectUri: 'https://portal.saintvision.lan/callback',
    jwks: { keys: [publicJwk] },
  });

  async function makeSignedJwt(
    claims: Record<string, unknown>,
    header: { alg: string; typ: string; kid?: string } = { alg: 'RS256', typ: 'JWT', kid: 'test-key-01' },
    key: CryptoKey = keyPair.privateKey,
  ): Promise<string> {
    const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString('base64url');
    const data = `${b64(header)}.${b64(claims)}`;
    if (header.alg === 'none') {
      return `${data}.`;
    }
    const sigBytes = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, new TextEncoder().encode(data));
    const sig = Buffer.from(sigBytes).toString('base64url');
    return `${data}.${sig}`;
  }

  function makeMockAccessToken(claims: Record<string, unknown>): string {
    const b64 = (obj: unknown) => Buffer.from(JSON.stringify(obj)).toString('base64url');
    return `${b64({ alg: 'RS256', typ: 'at+jwt' })}.${b64(claims)}.at-mock-sig`;
  }

  beforeEach(() => {
    storage = new Map();
    mockFetch.mockReset();
    clearSessionExpiration();
    clearAuthToken();
    location = {
      origin: 'https://portal.saintvision.lan',
      pathname: '/deployment',
      search: '',
      assign: vi.fn(),
    };
    vi.stubGlobal('window', {
      location,
      __SAINTVISION_CONFIG__: getBaseIdpConfig(),
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
    clearAuthToken();
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
      ['prompt가 login이 아닌 경우 (consent)', { prompt: 'consent', max_age: 300 }, 'prompt는 반드시 "login"'],
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
      const idpConfig = getBaseIdpConfig();
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
        beginStepUp({ customParams: { extra_attack: 'injection' } }),
      ).rejects.toThrow('추가 필드는 금지됩니다');

      await expect(
        beginStepUp({ customParams: { prompt: 'consent' } }),
      ).rejects.toThrow('prompt는 반드시 "login"');

      await expect(
        beginStepUp({ customParams: { max_age: 600 } }),
      ).rejects.toThrow('max_age는 반드시 300');
    });
  });

  // 3. PKCE Verifier, State, Nonce & Codex Decision (b) Storage Invariant
  describe('3. PKCE/state/nonce 신규 재생성 및 sessionStorage 토큰 잔류 0건 불변식', () => {
    it('beginStepUp() 호출 시 verifier/state/nonce가 새로 생성되며, sessionStorage에 토큰 및 자격증명이 일절 저장되지 않는다 (선택지 b)', async () => {
      // 1) First, regular login begins
      const loginUrl = new URL(await beginLogin());
      const loginTx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      expect(loginTx.isStepUp).toBeFalsy();

      // Existing active token in memory before step-up
      const existingToken = 'jwt.initial-active-token.signature';
      setAuthToken(existingToken);
      expect(getAuthToken()).toBe(existingToken);

      // 2) Begin Step-Up
      const stepUpUrl = new URL(await beginStepUp({ returnUrl: '/deployment?tab=releases' }));
      const stepUpTx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      // Strict assertions on freshness and regeneration
      expect(stepUpTx.isStepUp).toBe(true);
      expect(stepUpTx.returnUrl).toBe('/deployment?tab=releases');

      // F-R2 & Codex Security Decision (b): previousToken must be REMOVED, storage must contain ZERO tokens/credentials
      expect((stepUpTx as any).previousToken, 'previousToken must be completely absent from transaction').toBeUndefined();
      const rawStored = storage.get(STORAGE_KEY)!;
      expect(rawStored).not.toContain(existingToken);
      expect(rawStored).not.toContain('previousToken');
      expect(rawStored).not.toContain('access_token');
      expect(rawStored).not.toContain('Bearer');

      // Verifier, state, nonce MUST NOT be reused
      expect(stepUpTx.verifier, 'PKCE verifier must be regenerated').not.toBe(loginTx.verifier);
      expect(stepUpTx.state, 'CSRF state must be regenerated').not.toBe(loginTx.state);
      expect(stepUpTx.nonce, 'OIDC nonce must be regenerated').not.toBe(loginTx.nonce);

      expect(stepUpUrl.searchParams.get('state')).toBe(stepUpTx.state);
      expect(stepUpUrl.searchParams.get('nonce')).toBe(stepUpTx.nonce);
      expect(stepUpUrl.searchParams.get('prompt')).toBe('login');
      expect(stepUpUrl.searchParams.get('max_age')).toBe('300');

      // Before redirect (current page lifecycle), existing memory token is untouched
      expect(getAuthToken(), 'In-memory auth token remains untouched in current page before unload').toBe(existingToken);
    });

    it('beginStepUp() 호출 시마다 verifier, state, nonce가 새로 생성되어 이전 값과 일치하지 않는다 (재사용 변이 사살)', async () => {
      const url1 = new URL(await beginStepUp());
      const tx1: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      const url2 = new URL(await beginStepUp());
      const tx2: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      expect(tx1.state, 'CSRF state must be uniquely regenerated').not.toBe(tx2.state);
      expect(tx1.nonce, 'OIDC nonce must be uniquely regenerated').not.toBe(tx2.nonce);
      expect(tx1.verifier, 'PKCE verifier must be uniquely regenerated').not.toBe(tx2.verifier);
      expect(url1.searchParams.get('state')).toBe(tx1.state);
      expect(url2.searchParams.get('state')).toBe(tx2.state);
      expect(url1.searchParams.get('state')).not.toBe(url2.searchParams.get('state'));
    });

    it('returnUrl에 절대 URL, scheme-relative, fragment, 사용자 정보 주입 시 /studio로 정규화된다', async () => {
      // Attack returnUrls
      const maliciousCases = [
        'https://attacker.com/steal',
        'http://attacker.com/evil',
        '//attacker.com/scheme-relative',
        'javascript:alert(1)',
        '/deployment#fragment-attack',
        '/admin@attacker.com',
      ];

      for (const badReturnUrl of maliciousCases) {
        await beginStepUp({ returnUrl: badReturnUrl });
        const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
        expect(tx.returnUrl, `Malicious returnUrl ${badReturnUrl} must be sanitized to /studio`).toBe('/studio');
      }

      // Safe same-origin returnUrls
      await beginStepUp({ returnUrl: '/deployment?release=v1.2' });
      const safeTx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      expect(safeTx.returnUrl).toBe('/deployment?release=v1.2');
    });
  });

  // 4. F-R4: openid Scope Requirement (Fail-Closed)
  describe('4. F-R4: step-up은 openid 스코프 필수 (Fail-Closed)', () => {
    it('config.scope에 openid가 누락된 경우 beginStepUp()은 즉시 거절한다', async () => {
      vi.stubGlobal('window', {
        location,
        __SAINTVISION_CONFIG__: {
          ...getBaseIdpConfig(),
          scope: 'inv.api', // openid omitted
        },
        history: { replaceState: vi.fn() },
      });

      await expect(beginStepUp()).rejects.toThrow('재인증(Step-Up)을 위해서는 openid 스코프가 필수입니다');
    });
  });

  // 5. F-R3: Pre-exchange Step-Up Validation
  describe('5. F-R3: 토큰 교환 전 Step-Up 트랜잭션 식별 및 일반/Step-Up 교차 호출 차단', () => {
    it('beginLogin() 일반 트랜잭션으로 completeStepUp()을 호출하면 토큰 엔드포인트 호출 전에 즉시 거부한다', async () => {
      const url = new URL(await beginLogin());
      location.pathname = '/callback';
      location.search = `?code=std_code&state=${url.searchParams.get('state')}`;

      // Simulate page redirect memory wipe
      clearAuthToken();

      await expect(completeStepUp()).rejects.toThrow('진행 중인 재인증(Step-Up) 트랜잭션이 아닙니다');

      // Crucial invariant: zero token exchange, zero session calls, active token remains null
      expect(mockFetch, 'Must NOT invoke token endpoint or session endpoint on invalid step-up marker').not.toHaveBeenCalled();
      expect(getAuthToken()).toBeNull();
      expect(storage.size, 'Transaction must be cleared').toBe(0);
    });

    it('beginStepUp() 트랜잭션으로 일반 completeLogin()을 호출하면 토큰 엔드포인트 호출 전에 즉시 거부한다', async () => {
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=step_code&state=${url.searchParams.get('state')}`;

      // Simulate page redirect memory wipe
      clearAuthToken();

      await expect(completeLogin()).rejects.toThrow('재인증(Step-Up) 트랜잭션은 completeStepUp()으로 처리해야 합니다');

      expect(mockFetch, 'Must NOT invoke token endpoint on crossed callback').not.toHaveBeenCalled();
      expect(getAuthToken()).toBeNull();
      expect(storage.size, 'Transaction must be cleared').toBe(0);
    });
  });

  // 6. F-R1: ID Token Signature Verification via JWKS
  describe('6. F-R1: ID 토큰 전자 서명 검증 (RS256 & JWKS 결속)', () => {
    it('진본 서명된 ID 토큰은 서명 검증을 통과한다', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      const authenticIdToken = await makeSignedJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });

      const accessToken = makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: accessToken,
          id_token: authenticIdToken,
          token_type: 'Bearer',
        }),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          subjectId: 'oidc:' + '1'.repeat(64),
          tenantId: 'saintvision-corp',
          expiresAt: now + 300,
        }),
      });

      const res = await completeStepUp();
      expect(res.token).toBe(accessToken);
      expect(res.isStepUp).toBe(true);
    });

    it('ID 토큰 서명이 한 글자라도 변조되면 토큰 교체 전 거절되고 active token은 설정되지 않는다', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      const authenticIdToken = await makeSignedJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });

      // Tamper signature by changing the last character
      const parts = authenticIdToken.split('.');
      const lastChar = parts[2].slice(-1);
      const replacementChar = lastChar === 'a' ? 'b' : 'a';
      const tamperedIdToken = `${parts[0]}.${parts[1]}.${parts[2].slice(0, -1)}${replacementChar}`;

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: tamperedIdToken,
          token_type: 'Bearer',
        }),
      });

      // Simulate full redirect memory wipe
      clearAuthToken();

      let stepUpError: any = null;
      try {
        await completeStepUp();
      } catch (err) {
        stepUpError = err;
      }
      expect(stepUpError).toBeInstanceOf(Error);
      expect(stepUpError?.message).toContain('ID 토큰 전자 서명 검증에 실패했습니다');

      // Crucial: token was NOT committed, /v1/session was NOT called
      expect(getAuthToken()).toBeNull();
      expect(mockFetch).toHaveBeenCalledTimes(1); // token endpoint only, no session check
    });

    it('JWKS에 존재하지 않는 unknown kid가 전달되면 거절된다', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      const unknownKidToken = await makeSignedJwt(
        {
          iss: idpConfig.issuer,
          aud: idpConfig.clientId,
          sub: 'usr_ops_lead',
          nonce: tx.nonce,
          iat: now,
          exp: now + 300,
        },
        { alg: 'RS256', typ: 'JWT', kid: 'unknown-adversary-key' },
      );

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: unknownKidToken,
          token_type: 'Bearer',
        }),
      });

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('kid(unknown-adversary-key)에 해당하는 공개키를 JWKS에서 찾을 수 없습니다');
      expect(getAuthToken()).toBeNull();
    });

    it.each([
      ['none 알고리즘 완화', 'none'],
      ['대칭키 알고리즘 HS256', 'HS256'],
    ])('알고리즘 완화 공격 %s은 즉시 거절된다', async (_, badAlg) => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code_123&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);

      const weakToken = await makeSignedJwt(
        {
          iss: idpConfig.issuer,
          aud: idpConfig.clientId,
          sub: 'usr_ops_lead',
          nonce: tx.nonce,
          iat: now,
          exp: now + 300,
        },
        { alg: badAlg, typ: 'JWT', kid: 'test-key-01' },
      );

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: weakToken,
          token_type: 'Bearer',
        }),
      });

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('지원되지 않거나 허용되지 않은 서명 알고리즘입니다');
      expect(getAuthToken()).toBeNull();
    });
  });

  // 7. Claude S2 & Codex S2 / S3: Redirect memory simulation and failure modes
  describe('7. 리다이렉트 후 콜백 실패 시 재로그인 요구 및 자격증명 잔류 0건', () => {
    it('사용자가 인증을 취소(access_denied)한 경우 재로그인을 요구하고 토큰은 null로 유지된다', async () => {
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?error=access_denied&error_description=User_cancelled&state=${url.searchParams.get('state')}`;

      // Simulate full redirect memory wipe
      clearAuthToken();

      await expect(completeStepUp()).rejects.toThrow('인증 제공자가 로그인을 완료하지 못했습니다');
      expect(getAuthToken(), 'No token must be resurrected upon cancellation').toBeNull();
      expect(storage.size, 'Storage transaction cleared').toBe(0);
    });

    it('state가 불일치하거나 위조된 경우 거절되고 토큰은 null로 유지된다', async () => {
      await beginStepUp();
      location.pathname = '/callback';
      location.search = '?code=valid_code&state=ATTACKER_FORGED_STATE';

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('로그인 요청 검증에 실패했습니다');
      expect(getAuthToken()).toBeNull();
      expect(storage.size).toBe(0);
    });

    it('IdP 토큰 엔드포인트 교환 실패(HTTP 400/500) 시 거절되고 토큰은 null로 유지된다', async () => {
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code&state=${url.searchParams.get('state')}`;

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'invalid_grant' }),
      });

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('인증 코드 교환에 실패했습니다');
      expect(getAuthToken()).toBeNull();
      expect(storage.size).toBe(0);
    });

    it('ID 토큰 nonce 불일치 시 거절되고 토큰은 null로 유지된다', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const mismatchIdToken = await makeSignedJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: 'DIFFERENT_NONCE_UNEXPECTED',
        iat: now,
        exp: now + 300,
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now }),
          id_token: mismatchIdToken,
          token_type: 'Bearer',
        }),
      });

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('ID 토큰의 nonce가 로그인 요청 트랜잭션과 일치하지 않습니다');
      expect(getAuthToken()).toBeNull();
    });

    it('서버 /v1/session 엔드포인트가 새 토큰을 거부한 경우, 새 토큰이 사전에 메모리에 설정되지 않고 즉시 소멸한다 (변이 X6 사살)', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp());
      location.pathname = '/callback';
      location.search = `?code=auth_code&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      const authenticIdToken = await makeSignedJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });
      const unverifiedNewAccessToken = makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: unverifiedNewAccessToken,
          id_token: authenticIdToken,
          token_type: 'Bearer',
        }),
      });

      // Backend session endpoint rejects token
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ code: 'AUTH-0010', message: 'unauthorized' }),
      });

      clearAuthToken();
      await expect(completeStepUp()).rejects.toThrow('서버가 인증 토큰을 허용하지 않았습니다');

      // Crucial test against mutation X6 (setting token before /v1/session):
      // Active token MUST NOT be unverifiedNewAccessToken
      expect(getAuthToken(), 'Unverified token must never remain in active token storage').toBeNull();
      expect(storage.size).toBe(0);
    });
  });

  // 8. Successful Step-Up & Atomic Session Commit
  describe('8. Step-Up 성공 및 commitSession 원자적 세션 반영', () => {
    it('Step-Up 검증 성공 후 commitSession을 통해 활성 토큰과 만료 타이머가 원자적으로 반영된다', async () => {
      const idpConfig = getBaseIdpConfig();
      const url = new URL(await beginStepUp({ returnUrl: '/deployment' }));
      location.pathname = '/callback';
      location.search = `?code=auth_code_success&state=${url.searchParams.get('state')}`;

      const now = Math.floor(Date.now() / 1000);
      const tx: Transaction = JSON.parse(storage.get(STORAGE_KEY)!);
      const authenticIdToken = await makeSignedJwt({
        iss: idpConfig.issuer,
        aud: idpConfig.clientId,
        sub: 'usr_ops_lead',
        nonce: tx.nonce,
        iat: now,
        exp: now + 300,
      });
      const freshAccessToken = makeMockAccessToken({ iss: idpConfig.issuer, exp: now + 300, iat: now });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: freshAccessToken,
          id_token: authenticIdToken,
          token_type: 'Bearer',
        }),
      });

      const subject = 'oidc:' + 'f'.repeat(64);
      mockFetch.mockImplementation(async (url: any) => {
        if (String(url).includes('/v1/session')) {
          expect(getAuthToken(), 'Token must not be set in memory before /v1/session validation succeeds (M4 kill)').toBeNull();
          return {
            ok: true,
            json: async () => ({
              subjectId: subject,
              tenantId: 'saintvision-corp',
              expiresAt: now + 300,
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({
            access_token: freshAccessToken,
            id_token: authenticIdToken,
            token_type: 'Bearer',
          }),
        };
      });

      clearAuthToken();
      const res = await completeStepUp();

      // completeStepUp returns token without committing to global state
      expect(getAuthToken(), 'completeStepUp must not prematurely commit authToken before commitSession (M4 kill)').toBeNull();

      expect(res.token).toBe(freshAccessToken);
      expect(res.isStepUp).toBe(true);
      expect(res.user.id).toBe(subject);

      // Verify that caller commits the token atomically
      commitSession(res.token, res.expiresAt);
      expect(getAuthToken()).toBe(freshAccessToken);
    });
  });

  // 9. Revert-Fail Probes
  describe('9. Revert-Fail Probes (실제 코드 변이 시 엄격 실패 증명)', () => {
    it('Probe 1: validateStepUpRequest에서 prompt가 login이 아니면 즉시 실패한다', () => {
      expect(() => validateStepUpRequest({ prompt: 'consent', max_age: 300 })).toThrow('prompt는 반드시 "login"');
    });

    it('Probe 2: validateStepUpRequest에서 max_age가 300이 아니면 즉시 실패한다', () => {
      expect(() => validateStepUpRequest({ prompt: 'login', max_age: 600 })).toThrow('max_age는 반드시 300');
    });

    it('Probe 3: beginStepUp에서 openid 스코프가 누락되면 fail-closed 실패한다', async () => {
      vi.stubGlobal('window', {
        location,
        __SAINTVISION_CONFIG__: {
          ...getBaseIdpConfig(),
          scope: 'inv.api',
        },
        history: { replaceState: vi.fn() },
      });
      await expect(beginStepUp()).rejects.toThrow('openid 스코프가 필수');
    });

    it('Probe 4: beginStepUp 호출 후 sessionStorage에 토큰이 잔류하면 실패한다 (0건 불변식)', async () => {
      setAuthToken('bearer-secret-token');
      await beginStepUp();
      const stored = storage.get(STORAGE_KEY)!;
      // If someone mutates code to store the token in storage, this probe kills it
      expect(stored.includes('bearer-secret-token')).toBe(false);
      expect(stored.includes('previousToken')).toBe(false);
    });
  });
});
