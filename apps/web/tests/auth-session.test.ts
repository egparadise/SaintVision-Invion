import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { beginLogin, completeLogin } from '../src/features/auth/session';
const config = { idpAuthorizeUrl: 'https://idp.invalid/authorize?realm=company',
  idpTokenUrl: 'https://idp.invalid/token', clientId: 'configured-web', scope: 'inv.api' };
const key = 'saintvision.oauth.transaction';
let storage: Map<string, string>;
let location: { origin: string; pathname: string; search: string };
const request = vi.fn();
beforeEach(() => {
  storage = new Map(); request.mockReset();
  location = { origin: 'https://studio.invalid', pathname: '/studio', search: '' };
  vi.stubGlobal('window', { location, __SAINTVISION_CONFIG__: { ...config }, history: { replaceState: vi.fn() } });
  vi.stubGlobal('sessionStorage', { getItem: (k: string) => storage.get(k) ?? null,
    setItem: (k: string, v: string) => storage.set(k, v), removeItem: (k: string) => storage.delete(k) });
  vi.stubGlobal('fetch', request);
});
afterEach(() => vi.unstubAllGlobals());
async function callback() {
  const url = new URL(await beginLogin());
  location.pathname = '/callback'; location.search = '?code=one-use&state=' + url.searchParams.get('state');
  return url;
}
it('uses configured client and S256; preserves existing authorize query parameters', async () => {
  const url = await callback();
  expect(url.searchParams.get('realm')).toBe('company');
  expect(url.searchParams.get('client_id')).toBe('configured-web');
  expect(url.searchParams.get('code_challenge_method')).toBe('S256');
  expect(url.searchParams.get('redirect_uri')).toBe('https://studio.invalid/callback');
  expect(request).not.toHaveBeenCalled();
});
it('exchanges a form with no API bearer header and uses only server-verified identity', async () => {
  await callback();
  request.mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'opaque-token', token_type: 'Bearer', user: { id: 'attacker' } }) });
  const subject = 'oidc:' + 'a'.repeat(64);
  request.mockResolvedValueOnce({ ok: true, json: async () => ({ subjectId: subject, tenantId: 'configured-tenant', expiresAt: Math.floor(Date.now() / 1000) + 100 }) });
  expect((await completeLogin()).user.id).toBe(subject);
  const [url, options] = request.mock.calls[0];
  expect(url).toBe(config.idpTokenUrl);
  expect(options.headers).toEqual({ 'Content-Type': 'application/x-www-form-urlencoded' });
  expect(options.body.get('redirect_uri')).toBe('https://studio.invalid/callback');
  expect(options.body.get('code_verifier')).toBeTruthy();
  expect(request.mock.calls[1][0]).toBe('/v1/session');
  expect(storage.size).toBe(0);
  await expect(completeLogin()).rejects.toThrow();
  expect(request).toHaveBeenCalledTimes(2);
});
it.each(['state', 'duplicate-state', 'duplicate-code', 'expired', 'future', 'verifier', 'config', 'redirect', 'error', 'missing'])('rejects callback %s before token transmission', async bad => {
  await callback();
  const tx = JSON.parse(storage.get(key)!);
  if (bad === 'state') location.search = '?code=c&state=other';
  if (bad === 'duplicate-state') location.search += '&state=other';
  if (bad === 'duplicate-code') location.search += '&code=other';
  if (bad === 'error') location.search += '&error=access_denied';
  if (bad === 'expired') tx.createdAt -= 600001;
  if (bad === 'future') tx.createdAt += 600001;
  if (bad === 'verifier') tx.verifier = 'short';
  if (bad === 'config') tx.config.clientId = 'another-client';
  if (bad === 'redirect') tx.redirectUri = 'https://other.invalid/callback';
  storage.set(key, JSON.stringify(tx));
  if (bad === 'missing') storage.clear();
  await expect(completeLogin()).rejects.toThrow();
  expect(request).not.toHaveBeenCalled(); expect(storage.size).toBe(0);
});
it('does not accept a token rejected by the resource server', async () => {
  await callback();
  request.mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'invalid', token_type: 'Bearer' }) });
  request.mockResolvedValueOnce({ ok: false });
  await expect(completeLogin()).rejects.toThrow('서버가 인증 토큰을 허용하지 않았습니다.');
});
it.each(['http://remote.invalid/token', 'https://user:password@idp.invalid/token', 'https://idp.invalid/token#fragment'])('rejects unsafe endpoint %s without a request', async url => {
  (window as any).__SAINTVISION_CONFIG__.idpTokenUrl = url;
  await expect(beginLogin()).rejects.toThrow(); expect(request).not.toHaveBeenCalled();
});
it('does not manufacture a code or call a broker when configuration is missing', async () => {
  (window as any).__SAINTVISION_CONFIG__ = {};
  await expect(beginLogin()).rejects.toThrow(); expect(request).not.toHaveBeenCalled();
});
