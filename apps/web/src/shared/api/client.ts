import { ProblemDetails } from '@/contracts/types';

/**
 * Generate a 32-character lowercase hex string for W3C trace-id
 */
export function generateTraceId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Generate a 16-character lowercase hex string for W3C span-id
 */
export function generateSpanId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function localProblem(
  status: number,
  title: string,
  detail: string,
  traceId: string,
  retryable: boolean,
): ProblemDetails {
  const safeStatus = Number.isInteger(status) && status >= 400 && status <= 599 ? status : 500;
  return {
    type: 'about:blank',
    title: title.slice(0, 200) || 'Request rejected',
    status: safeStatus,
    code: `NET-${String(safeStatus).padStart(4, '0')}`,
    category: 'NET',
    detail: detail.slice(0, 1000),
    retryable,
    traceId,
    causeRef: null,
    evidenceId: null,
  };
}

const PROBLEM_DETAIL_KEYS = new Set([
  'type', 'title', 'status', 'code', 'category', 'detail', 'retryable',
  'traceId', 'causeRef', 'evidenceId',
]);

const LEGACY_AUTH_PROBLEM_KEYS = new Set([
  ...PROBLEM_DETAIL_KEYS,
  'instance',
]);

export function isProblemDetails(value: unknown, expectedStatus?: number): value is ProblemDetails {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const problem = value as Record<string, unknown>;
  if (typeof expectedStatus === 'number' && problem.status !== expectedStatus) return false;
  const isLegacyAuth = problem.status === 401 && problem.code === 'AUTH-MISSING-CREDENTIAL';
  const allowedKeys = isLegacyAuth ? LEGACY_AUTH_PROBLEM_KEYS : PROBLEM_DETAIL_KEYS;
  return Object.keys(problem).every((key) => allowedKeys.has(key)) &&
    (problem.type === 'about:blank' || (isLegacyAuth && problem.type === 'https://saintvision.invenio/problems/auth-missing-credential')) &&
    typeof problem.title === 'string' && problem.title.length > 0 && problem.title.length <= 200 &&
    Number.isInteger(problem.status) && Number(problem.status) >= 400 && Number(problem.status) <= 599 &&
    typeof problem.code === 'string' && (/^[A-Z]+-[0-9]{4}$/.test(problem.code) || isLegacyAuth) &&
    typeof problem.category === 'string' && /^[A-Z]+$/.test(problem.category) &&
    typeof problem.detail === 'string' && problem.detail.length <= 1000 &&
    typeof problem.retryable === 'boolean' &&
    typeof problem.traceId === 'string' && /^[0-9a-f]{32}$/.test(problem.traceId) &&
    (problem.causeRef === null || (typeof problem.causeRef === 'string' && problem.causeRef.length > 0 && problem.causeRef.length <= 200)) &&
    (problem.evidenceId === null || (typeof problem.evidenceId === 'string' && /^evd_[0-9A-HJKMNP-TV-Z]{26}$/.test(problem.evidenceId))) &&
    (!('instance' in problem) || problem.instance === null || (typeof problem.instance === 'string' && problem.instance.length <= 500));
}

let inMemoryAuthToken: string | null = null;

/**
 * Set the current in-memory access token (OIDC / OAuth Bearer).
 * Strict adherence to memory-only storage: NEVER persisted to localStorage/sessionStorage.
 */
export function setAuthToken(token: string | null): void {
  inMemoryAuthToken = token;
}

/**
 * Get current in-memory access token.
 */
export function getAuthToken(): string | null {
  return inMemoryAuthToken;
}

declare global {
  // eslint-disable-next-line no-var
  var __sv_auth_teardown_listeners: Set<() => void> | undefined;
  // eslint-disable-next-line no-var
  var __sv_has_auth_token: (() => boolean) | undefined;
}

if (typeof globalThis !== 'undefined') {
  globalThis.__sv_has_auth_token = () => inMemoryAuthToken !== null;
}

export function hasAuthToken(): boolean {
  return inMemoryAuthToken !== null;
}

export function onAuthTeardown(listener: () => void): () => void {
  if (!globalThis.__sv_auth_teardown_listeners) {
    globalThis.__sv_auth_teardown_listeners = new Set();
  }
  globalThis.__sv_auth_teardown_listeners.add(listener);
  return () => {
    globalThis.__sv_auth_teardown_listeners?.delete(listener);
  };
}

/**
 * Clear the in-memory access token on logout and notify teardown listeners.
 */
export function clearAuthToken(): void {
  inMemoryAuthToken = null;
  globalThis.__sv_auth_teardown_listeners?.forEach((fn) => {
    try {
      fn();
    } catch {
      // ignore listener errors during teardown
    }
  });
}

export type UnauthorizedHandler = (problem: ProblemDetails) => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function onUnauthorized(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  public readonly problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title);
    this.name = 'ApiError';
    this.problem = problem;
  }
}

export interface RequestOptions extends RequestInit {
  traceId?: string;
  idempotencyKey?: string;
  expectedStatus?: number | number[];
}

/**
 * Distinguish between an unmapped HTTP route 404 (Route Not Found)
 * and an application/resource 404 (Entity Not Found or permission-masked).
 * A migration fallback to a flat route MUST ONLY occur if the route itself does not exist.
 * If the server returned an application RFC 9457 ProblemDetails with a business code
 * (e.g. RES-0004, AUTH-0030), the route exists and the entity was missing or masked;
 * in that case, fallback is strictly rejected to prevent duplicate mutation or unauthorized probing.
 */
export function isRouteNotFoundError(err: any): boolean {
  if (!err) return false;
  const status = err.problem?.status || err.status;
  if (status !== 404) return false;

  const problem = err.problem;
  const code = problem?.code || err.code;

  // Synthesized network/route absence: client mapped unmapped route to NET-0404
  if (code === 'NET-0404') return true;

  // Any structured problem code indicates an application controller was reached (fail-closed)
  if (code) return false;

  // Unmapped HTTP 404 without a structured problem code
  return true;
}

/**
 * Robust fetch wrapper with W3C traceparent injection, Bearer auth, and RFC 9457 Problem Details error handling.
 */
export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const traceId = options.traceId && /^[0-9a-f]{32}$/.test(options.traceId)
    ? options.traceId
    : generateTraceId();
  const spanId = generateSpanId();
  const traceparent = `00-${traceId}-${spanId}-01`;

  const headers = new Headers(options.headers || {});
  headers.set('traceparent', traceparent);
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (inMemoryAuthToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${inMemoryAuthToken}`);
  }
  if (options.idempotencyKey && !headers.has('Idempotency-Key')) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let problem: ProblemDetails;
    try {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/problem+json') || contentType.includes('application/json')) {
        const payload: unknown = await response.json();
        if (isProblemDetails(payload, response.status)) {
          problem = payload;
        } else {
          const detail =
            payload && typeof payload === 'object' &&
            typeof (payload as Record<string, unknown>).detail === 'string'
              ? (payload as Record<string, string>).detail
              : response.statusText || 'Server returned an invalid error response.';
          problem = localProblem(
            response.status,
            'Request rejected',
            detail,
            traceId,
            response.status >= 500,
          );
        }
      } else {
        problem = localProblem(
          response.status,
          response.statusText || 'HTTP Error',
          await response.text(),
          traceId,
          response.status >= 500,
        );
      }
    } catch {
      problem = localProblem(
        response.status,
        'Communication Failure',
        'Failed to parse error response from server.',
        traceId,
        true,
      );
    }
    if (problem.status === 401 && unauthorizedHandler) {
      unauthorizedHandler(problem);
    }
    throw new ApiError(problem);
  }

  if (options.expectedStatus !== undefined) {
    const expected = Array.isArray(options.expectedStatus) ? options.expectedStatus : [options.expectedStatus];
    if (!expected.includes(response.status)) {
      const problem = localProblem(
        response.status,
        'Unexpected status code',
        `Unexpected status code: Server returned status ${response.status}, expected ${expected.join(' or ')}`,
        traceId,
        false
      );
      throw new ApiError(problem);
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
