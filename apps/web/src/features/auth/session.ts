import { generateCodeVerifier, generateCodeChallenge, generateState, generateNonce } from './pkce';
import { clearAuthToken } from '@/shared/api/client';

export interface SessionUser {
  id: string;
  name: string;
  role: string;
  tenantId: string;
}

export interface OidcConfig {
  issuer?: string;
  clientId: string;
  scope?: string;
  idpAuthorizeUrl?: string;
  idpTokenUrl?: string;
  idpLogoutUrl?: string;
  redirectUri?: string;
}

export interface ResolvedOidcConfig {
  issuer?: string;
  clientId: string;
  scope: string;
  idpAuthorizeUrl: string;
  idpTokenUrl: string;
  idpLogoutUrl?: string;
  redirectUri: string;
}

export interface Transaction {
  state: string;
  nonce?: string;
  verifier: string;
  createdAt: number;
  redirectUri: string;
  config: ResolvedOidcConfig;
}

export interface JwtClaims {
  iss?: string;
  sub?: string;
  aud?: string | string[];
  exp?: number;
  iat?: number;
  nbf?: number;
  jti?: string;
  client_id?: string;
  scope?: string;
  [key: string]: unknown;
}

export const STORAGE_KEY = 'saintvision.oauth.transaction';

export type ExpirationCallback = (reason: string) => void;
let expirationTimer: ReturnType<typeof setTimeout> | null = null;
const expirationListeners = new Set<ExpirationCallback>();

export function onTokenExpired(callback: ExpirationCallback): () => void {
  expirationListeners.add(callback);
  return () => {
    expirationListeners.delete(callback);
  };
}

export function registerSessionExpiration(expiresAtUnixSeconds: number): void {
  if (expirationTimer) {
    clearTimeout(expirationTimer);
    expirationTimer = null;
  }
  const now = Math.floor(Date.now() / 1000);
  const remaining = expiresAtUnixSeconds - now;
  if (remaining <= 0) {
    triggerTokenExpired('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');
    return;
  }
  const delayMs = remaining * 1000;
  expirationTimer = setTimeout(() => {
    expirationTimer = null;
    triggerTokenExpired('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');
  }, delayMs);
}

export function clearSessionExpiration(): void {
  if (expirationTimer) {
    clearTimeout(expirationTimer);
    expirationTimer = null;
  }
}

function triggerTokenExpired(reason: string): void {
  clearAuthToken();
  expirationListeners.forEach((cb) => {
    try {
      cb(reason);
    } catch {
      // ignore listener errors during expiration callback
    }
  });
}

export const CLOCK_SKEW_SEC = 120;

function isSubpathOf(targetPath: string, basePath: string): boolean {
  const normBase = basePath === '/' ? '/' : basePath.replace(/\/+$/, '') + '/';
  const normTarget = targetPath.replace(/\/+$/, '') + '/';
  return normBase === '/' || normTarget.startsWith(normBase);
}

function endpoint(value: unknown, fieldName = '인증 서버 URL'): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`${fieldName} 설정이 필요합니다.`);
  }
  const url = new URL(value.trim());
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.hash) {
    throw new Error(`${fieldName}이(가) 안전한 주소가 아닙니다.`);
  }
  return url.href;
}

function cleanIssuerUrl(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('인증 서버 issuer 설정이 필요합니다.');
  }
  const url = new URL(value.trim());
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.hash) {
    throw new Error('인증 서버 issuer URL이 안전한 주소가 아닙니다.');
  }
  const pathname = url.pathname.replace(/\/+$/, '');
  return `${url.origin}${pathname}`;
}

export function authConfig(): ResolvedOidcConfig {
  const raw = (window as unknown as { __SAINTVISION_CONFIG__?: Partial<OidcConfig> }).__SAINTVISION_CONFIG__;
  if (!raw || typeof raw !== 'object') {
    throw new Error('인증 서버와 클라이언트 설정이 필요합니다.');
  }

  if (typeof raw.clientId !== 'string' || !raw.clientId.trim()) {
    throw new Error('클라이언트 ID(clientId) 설정이 필요합니다.');
  }
  const clientId = raw.clientId.trim();

  let issuer: string | undefined;
  if (typeof raw.issuer === 'string' && raw.issuer.trim()) {
    issuer = cleanIssuerUrl(raw.issuer);
  }

  let idpAuthorizeUrl: string;
  let idpTokenUrl: string;
  let idpLogoutUrl: string | undefined;

  if (issuer) {
    const issuerUrl = new URL(issuer);
    idpAuthorizeUrl = raw.idpAuthorizeUrl ? endpoint(raw.idpAuthorizeUrl, '인가 엔드포인트 URL') : `${issuer}/protocol/openid-connect/auth`;
    idpTokenUrl = raw.idpTokenUrl ? endpoint(raw.idpTokenUrl, '토큰 엔드포인트 URL') : `${issuer}/protocol/openid-connect/token`;
    idpLogoutUrl = raw.idpLogoutUrl ? endpoint(raw.idpLogoutUrl, '로그아웃 엔드포인트 URL') : `${issuer}/protocol/openid-connect/logout`;

    const authUrl = new URL(idpAuthorizeUrl);
    const tokenUrl = new URL(idpTokenUrl);
    if (authUrl.origin !== issuerUrl.origin || !isSubpathOf(authUrl.pathname, issuerUrl.pathname)) {
      throw new Error('인가 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    }
    if (tokenUrl.origin !== issuerUrl.origin || !isSubpathOf(tokenUrl.pathname, issuerUrl.pathname)) {
      throw new Error('토큰 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
    }
    if (idpLogoutUrl) {
      const logoutUrl = new URL(idpLogoutUrl);
      if (logoutUrl.origin !== issuerUrl.origin || !isSubpathOf(logoutUrl.pathname, issuerUrl.pathname)) {
        throw new Error('로그아웃 엔드포인트의 origin 또는 경로가 issuer와 일치하지 않습니다.');
      }
    }
  } else if (raw.idpAuthorizeUrl && raw.idpTokenUrl) {
    idpAuthorizeUrl = endpoint(raw.idpAuthorizeUrl, '인가 엔드포인트 URL');
    idpTokenUrl = endpoint(raw.idpTokenUrl, '토큰 엔드포인트 URL');
    idpLogoutUrl = raw.idpLogoutUrl ? endpoint(raw.idpLogoutUrl, '로그아웃 엔드포인트 URL') : undefined;

    const authUrl = new URL(idpAuthorizeUrl);
    const tokenUrl = new URL(idpTokenUrl);
    if (tokenUrl.origin !== authUrl.origin) {
      throw new Error('인가 엔드포인트와 토큰 엔드포인트의 origin이 서로 일치하지 않습니다.');
    }
    if (idpLogoutUrl) {
      const logoutUrl = new URL(idpLogoutUrl);
      if (logoutUrl.origin !== authUrl.origin) {
        throw new Error('로그아웃 엔드포인트의 origin이 인가 엔드포인트와 일치하지 않습니다.');
      }
    }
  } else {
    throw new Error('인증 서버 설정(issuer 또는 idpAuthorizeUrl과 idpTokenUrl)이 필요합니다.');
  }

  const scope = (typeof raw.scope === 'string' && raw.scope.trim())
    ? raw.scope.trim()
    : 'openid inv.api';

  const origin = window.location.origin;
  if (raw.redirectUri !== undefined && (typeof raw.redirectUri !== 'string' || !raw.redirectUri.trim())) {
    throw new Error('redirect_uri 설정 형식이 올바르지 않습니다.');
  }
  const resolvedRedirect = raw.redirectUri ? new URL(raw.redirectUri.trim(), origin) : new URL('/callback', origin);
  if (resolvedRedirect.origin !== origin) {
    throw new Error('redirect_uri의 origin이 현재 웹 애플리케이션과 일치하지 않습니다.');
  }
  if (resolvedRedirect.pathname !== '/callback') {
    throw new Error('redirect_uri의 경로는 /callback 이어야 합니다.');
  }
  if (resolvedRedirect.hash) {
    throw new Error('redirect_uri에 fragment(해시)를 포함할 수 없습니다 (RFC 6749 §3.1.2).');
  }
  const redirectUri = resolvedRedirect.href;

  return {
    issuer,
    clientId,
    scope,
    idpAuthorizeUrl,
    idpTokenUrl,
    idpLogoutUrl,
    redirectUri,
  };
}

export function parseJwtPayload(token: string): JwtClaims | null {
  if (typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const segment = parts[1];
    if (!/^[A-Za-z0-9_-]+$/.test(segment)) return null;
    const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const json = atob(padded);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function validateTokenExpiration(
  token: string,
  nowUnixSeconds = Math.floor(Date.now() / 1000),
  options: { requireJwt?: boolean } = {},
): void {
  const { requireJwt = true } = options;
  if (typeof token !== 'string' || !token.trim()) {
    throw new Error('인증 토큰이 비어 있습니다.');
  }
  const parts = token.split('.');
  if (parts.length !== 3) {
    if (requireJwt) {
      throw new Error('인증 토큰(JWT) 형식이 올바르지 않습니다.');
    }
    return;
  }
  const claims = parseJwtPayload(token);
  if (!claims) {
    throw new Error('인증 토큰(JWT) 형식이 올바르지 않습니다.');
  }

  if (!Number.isInteger(claims.exp) || !Number.isInteger(claims.iat)) {
    throw new Error('인증 토큰에 유효한 정수형 exp 및 iat 클레임이 필요합니다.');
  }

  const lifetime = claims.exp! - claims.iat!;
  if (lifetime <= 0 || lifetime > 3600) {
    throw new Error('인증 토큰 유효 기간이 서버 계약 허용치(최대 3600초)를 초과하거나 올바르지 않습니다.');
  }

  if (claims.exp! + CLOCK_SKEW_SEC <= nowUnixSeconds) {
    throw new Error('이미 만료된 인증 토큰입니다.');
  }
}

export function buildLogoutUrl(postLogoutRedirectUri?: string): string | null {
  try {
    const config = authConfig();
    if (!config.idpLogoutUrl) return null;
    const url = new URL(config.idpLogoutUrl);
    url.searchParams.set('client_id', config.clientId);
    url.searchParams.set('post_logout_redirect_uri', postLogoutRedirectUri || window.location.origin);
    return url.href;
  } catch {
    return null;
  }
}

export function performLogout(options?: { redirectIdp?: boolean; postLogoutRedirectUri?: string }): string | null {
  clearSessionExpiration();
  clearAuthToken();
  sessionStorage.removeItem(STORAGE_KEY);
  if (options?.redirectIdp) {
    const logoutUrl = buildLogoutUrl(options.postLogoutRedirectUri);
    if (logoutUrl && typeof window !== 'undefined' && window.location) {
      window.location.assign(logoutUrl);
      return logoutUrl;
    }
  }
  return null;
}

export async function beginLogin(): Promise<string> {
  const config = authConfig();
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  const isOpenId = config.scope.split(/\s+/).includes('openid');
  const nonce = isOpenId ? generateNonce() : undefined;
  const tx: Transaction = {
    config,
    verifier,
    state: generateState(),
    nonce,
    createdAt: Date.now(),
    redirectUri: config.redirectUri,
  };
  const url = new URL(config.idpAuthorizeUrl);
  const params: Record<string, string> = {
    response_type: 'code',
    client_id: config.clientId,
    redirect_uri: tx.redirectUri,
    scope: config.scope,
    state: tx.state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
  };
  if (tx.nonce) {
    params.nonce = tx.nonce;
  }
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tx));
  return url.href;
}

export function hasLoginCallback(): boolean {
  return window.location.pathname === '/callback';
}

export async function completeLogin(): Promise<{ token: string; user: SessionUser; expiresAt: number }> {
  const params = new URLSearchParams(window.location.search);
  const saved = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  window.history.replaceState({}, '', '/studio');
  if (!saved) throw new Error('로그인 요청이 없거나 만료됐습니다. 다시 로그인하세요.');
  const tx: Transaction = JSON.parse(saved);
  const config = authConfig();
  if (JSON.stringify(tx.config) !== JSON.stringify(config) ||
      tx.redirectUri !== config.redirectUri ||
      typeof tx.state !== 'string' || !tx.state || params.getAll('state').length !== 1 || params.get('state') !== tx.state ||
      !Number.isFinite(tx.createdAt) || Date.now() - tx.createdAt > 600000 || Date.now() < tx.createdAt ||
      typeof tx.verifier !== 'string' || !/^[A-Za-z0-9_-]{43,128}$/.test(tx.verifier)) {
    throw new Error('로그인 요청 검증에 실패했습니다. 다시 로그인하세요.');
  }
  if (params.has('error') || params.getAll('code').length !== 1 || !params.get('code')) {
    throw new Error('인증 제공자가 로그인을 완료하지 못했습니다.');
  }
  // No resource token or tracing header may be sent to the IdP.
  const response = await fetch(config.idpTokenUrl, {
    method: 'POST',
    credentials: 'omit',
    redirect: 'error',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code: params.get('code')!,
      code_verifier: tx.verifier,
      client_id: config.clientId,
      redirect_uri: tx.redirectUri,
    }),
  });
  if (!response.ok) throw new Error('인증 코드 교환에 실패했습니다. 다시 로그인하세요.');
  const result = await response.json();
  if (typeof result.access_token !== 'string' || !result.access_token ||
      typeof result.token_type !== 'string' || result.token_type.toLowerCase() !== 'bearer') {
    throw new Error('인증 토큰 응답이 올바르지 않습니다.');
  }

  const nowSec = Math.floor(Date.now() / 1000);

  // OIDC ID token validation (when nonce was sent or id_token is provided)
  // Per OIDC Core 1.0 §3.1.3.7 Rule 6: When ID token is received via direct communication
  // between Client and TLS Token Endpoint, TLS server validation validates the issuer in place
  // of checking the JWS token signature. Authoritative token signature and credential validation
  // is performed by the server-side control plane (/v1/session).
  // The client fail-closed validates essential token claims:
  // - nonce: matches transaction nonce exactly
  // - iss: matches configured issuer (when issuer mode is configured)
  // - aud & azp: single aud equals clientId; multi-aud includes clientId and azp equals clientId (Rules 3 & 4)
  // - exp: required integer, not expired within CLOCK_SKEW_SEC (120s) leeway
  // - iat: required integer if present
  if (tx.nonce || result.id_token) {
    if (typeof result.id_token !== 'string' || !result.id_token.trim()) {
      throw new Error('OIDC 인증 응답에 ID 토큰(id_token)이 누락되었습니다.');
    }
    const idClaims = parseJwtPayload(result.id_token);
    if (!idClaims) {
      throw new Error('ID 토큰 페이로드가 올바르지 않습니다.');
    }
    if (tx.nonce && (typeof idClaims.nonce !== 'string' || idClaims.nonce !== tx.nonce)) {
      throw new Error('ID 토큰의 nonce가 로그인 요청 트랜잭션과 일치하지 않습니다.');
    }
    if (config.issuer && (typeof idClaims.iss !== 'string' || idClaims.iss !== config.issuer)) {
      throw new Error('ID 토큰의 발급자(iss)가 설정된 issuer와 일치하지 않습니다.');
    }
    if (typeof idClaims.aud === 'string') {
      if (idClaims.aud !== config.clientId) {
        throw new Error('ID 토큰의 대상(aud)이 클라이언트 ID와 일치하지 않습니다.');
      }
    } else if (Array.isArray(idClaims.aud)) {
      if (!idClaims.aud.includes(config.clientId)) {
        throw new Error('ID 토큰의 대상(aud) 목록에 클라이언트 ID가 포함되지 않았습니다.');
      }
      if (idClaims.aud.length > 1 && idClaims.azp !== config.clientId) {
        throw new Error('다중 대상(aud) ID 토큰의 azp가 클라이언트 ID와 일치하지 않습니다.');
      }
    } else {
      throw new Error('ID 토큰의 대상(aud)이 올바르지 않습니다.');
    }
    if (idClaims.azp !== undefined && idClaims.azp !== config.clientId) {
      throw new Error('ID 토큰의 azp가 클라이언트 ID와 일치하지 않습니다.');
    }
    if (!Number.isInteger(idClaims.exp)) {
      throw new Error('ID 토큰의 만료 시각(exp)이 정수가 아니거나 누락되었습니다.');
    }
    if (idClaims.exp! + CLOCK_SKEW_SEC <= nowSec) {
      throw new Error('ID 토큰이 이미 만료되었습니다.');
    }
    if (idClaims.iat !== undefined && !Number.isInteger(idClaims.iat)) {
      throw new Error('ID 토큰의 발급 시각(iat)이 정수가 아닙니다.');
    }
  }

  // Client-side fail-closed token validity check against server contract (0 < exp - iat <= 3600)
  validateTokenExpiration(result.access_token, nowSec, { requireJwt: false });

  const session = await fetch('/v1/session', {
    credentials: 'omit',
    redirect: 'error',
    cache: 'no-store',
    headers: { Authorization: `Bearer ${result.access_token}` },
  });
  if (!session.ok) throw new Error('서버가 인증 토큰을 허용하지 않았습니다.');
  const identity = await session.json();
  if (typeof identity.subjectId !== 'string' || !/^oidc:[0-9a-f]{64}$/.test(identity.subjectId) ||
      typeof identity.tenantId !== 'string' || !identity.tenantId ||
      !Number.isInteger(identity.expiresAt) || identity.expiresAt + CLOCK_SKEW_SEC <= nowSec) {
    throw new Error('서버 사용자 응답이 올바르지 않습니다.');
  }
  if (identity.expiresAt - nowSec > 3600 + CLOCK_SKEW_SEC) {
    throw new Error('서버 사용자 세션 유효 기간이 계약 허용치(최대 3600초)를 초과합니다.');
  }

  return {
    token: result.access_token,
    user: {
      id: identity.subjectId,
      name: identity.subjectId,
      tenantId: identity.tenantId,
      role: '프로젝트별 권한',
    },
    expiresAt: identity.expiresAt,
  };
}
