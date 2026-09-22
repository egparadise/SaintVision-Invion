import { generateCodeVerifier, generateCodeChallenge, generateState } from './pkce';

export interface SessionUser { id: string; name: string; role: string; tenantId: string }
interface Config { idpAuthorizeUrl: string; idpTokenUrl: string; clientId: string; scope: string }
interface Transaction { state: string; verifier: string; createdAt: number; redirectUri: string; config: Config }
const STORAGE_KEY = 'saintvision.oauth.transaction';

function endpoint(value: unknown): string {
  if (typeof value !== 'string') throw new Error('인증 서버 설정이 필요합니다.');
  const url = new URL(value);
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.hash) {
    throw new Error('인증 서버 URL이 안전한 주소가 아닙니다.');
  }
  return url.href;
}
export function authConfig(): Config {
  const raw = (window as unknown as { __SAINTVISION_CONFIG__?: Partial<Config> }).__SAINTVISION_CONFIG__;
  if (!raw || typeof raw.clientId !== 'string' || !raw.clientId.trim() ||
      typeof raw.scope !== 'string' || !raw.scope.trim()) throw new Error('인증 서버와 클라이언트 설정이 필요합니다.');
  return { idpAuthorizeUrl: endpoint(raw.idpAuthorizeUrl), idpTokenUrl: endpoint(raw.idpTokenUrl),
    clientId: raw.clientId, scope: raw.scope };
}
export async function beginLogin(): Promise<string> {
  const config = authConfig();
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  const tx: Transaction = { config, verifier, state: generateState(), createdAt: Date.now(),
    redirectUri: `${window.location.origin}/callback` };
  const url = new URL(config.idpAuthorizeUrl);
  const params = { response_type: 'code', client_id: config.clientId, redirect_uri: tx.redirectUri,
    scope: config.scope, state: tx.state, code_challenge: challenge, code_challenge_method: 'S256' };
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tx));
  return url.href;
}
export function hasLoginCallback(): boolean { return window.location.pathname === '/callback'; }

export async function completeLogin(): Promise<{ token: string; user: SessionUser }> {
  const params = new URLSearchParams(window.location.search);
  const saved = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  window.history.replaceState({}, '', '/studio');
  if (!saved) throw new Error('로그인 요청이 없거나 만료됐습니다. 다시 로그인하세요.');
  const tx: Transaction = JSON.parse(saved);
  const config = authConfig();
  if (JSON.stringify(tx.config) !== JSON.stringify(config) ||
      tx.redirectUri !== `${window.location.origin}/callback` ||
      typeof tx.state !== 'string' || !tx.state || params.getAll('state').length !== 1 || params.get('state') !== tx.state ||
      !Number.isFinite(tx.createdAt) || Date.now() - tx.createdAt > 600000 || Date.now() < tx.createdAt ||
      typeof tx.verifier !== 'string' || !/^[A-Za-z0-9_-]{43,128}$/.test(tx.verifier)) {
    throw new Error('로그인 요청 검증에 실패했습니다. 다시 로그인하세요.');
  }
  if (params.has('error') || params.getAll('code').length !== 1 || !params.get('code')) {
    throw new Error('인증 제공자가 로그인을 완료하지 못했습니다.');
  }
  // No resource token or tracing header may be sent to the IdP.
  const response = await fetch(config.idpTokenUrl, { method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code', code: params.get('code')!,
      code_verifier: tx.verifier, client_id: config.clientId, redirect_uri: tx.redirectUri }) });
  if (!response.ok) throw new Error('인증 코드 교환에 실패했습니다. 다시 로그인하세요.');
  const result = await response.json();
  if (typeof result.access_token !== 'string' || !result.access_token ||
      typeof result.token_type !== 'string' || result.token_type.toLowerCase() !== 'bearer') {
    throw new Error('인증 토큰 응답이 올바르지 않습니다.');
  }
  const session = await fetch('/v1/session', { credentials: 'omit', redirect: 'error', cache: 'no-store',
    headers: { Authorization: `Bearer ${result.access_token}` } });
  if (!session.ok) {
    let msg = '서버가 인증 토큰을 허용하지 않았습니다.';
    try {
      const prob = await session.json();
      if (prob?.code && prob?.detail) {
        msg = `서버가 인증 토큰을 허용하지 않았습니다. (${prob.code}: ${prob.detail})`;
      }
    } catch {}
    throw new Error(msg);
  }
  const identity = await session.json();
  if (typeof identity.subjectId !== 'string' || !/^oidc:[0-9a-f]{64}$/.test(identity.subjectId) ||
      typeof identity.tenantId !== 'string' || !identity.tenantId ||
      !Number.isInteger(identity.expiresAt) || identity.expiresAt <= Date.now() / 1000) {
    throw new Error('서버 사용자 응답이 올바르지 않습니다.');
  }
  return { token: result.access_token, user: { id: identity.subjectId, name: identity.subjectId,
    tenantId: identity.tenantId, role: '프로젝트별 권한' } };
}
