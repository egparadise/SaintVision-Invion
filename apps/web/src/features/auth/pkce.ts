/**
 * Standard PKCE (Proof Key for Code Exchange) RFC 7636 Implementation
 * Uses standard Web Crypto API (crypto.subtle & crypto.getRandomValues)
 */

function bufferToBase64Url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Generates high-entropy cryptographic random string for PKCE code_verifier.
 */
export function generateCodeVerifier(length = 43): string {
  const bytes = new Uint8Array(Math.max(32, Math.min(96, length)));
  crypto.getRandomValues(bytes);
  return bufferToBase64Url(bytes.buffer);
}

/**
 * Calculates S256 code_challenge from code_verifier using SHA-256.
 */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return bufferToBase64Url(digest);
}

/**
 * Generates CSRF state token.
 */
export function generateState(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Generates replay-protection nonce.
 */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Safely decodes RFC 7519 JWT payload without external libraries.
 */
export function parseJwtPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const jsonStr = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

/**
 * Resolves standard user identity from token response or JWT claims.
 */
export function resolveUserFromToken(
  tokenResponse: { access_token: string; user?: { id: string; name: string; role: string; tenantId?: string } }
): { id: string; name: string; role: string; tenantId?: string } {
  if (tokenResponse.user) {
    return tokenResponse.user;
  }
  const claims = parseJwtPayload(tokenResponse.access_token);
  return {
    id: claims?.sub || 'usr_oidc_user',
    name: claims?.preferred_username || claims?.name || 'OIDC Operator',
    role: claims?.role || (claims?.realm_access?.roles?.includes('cluster:admin') ? 'cluster:admin' : 'operator'),
    tenantId: claims?.tenant_id || claims?.tid,
  };
}
