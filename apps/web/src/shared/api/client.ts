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

/**
 * Clear the in-memory access token on logout.
 */
export function clearAuthToken(): void {
  inMemoryAuthToken = null;
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
}

/**
 * Distinguish between an unmapped HTTP route 404 (Route Not Found)
 * and an application/resource 404 (Entity Not Found or permission-masked).
 * A migration fallback to a flat route MUST ONLY occur if the route itself does not exist.
 * If the server returned an application RFC 9457 ProblemDetails with a business code
 * (e.g. RES-RUN-404, RES-APPROVAL-404, RES-404), the route exists and the entity was missing or masked;
 * in that case, fallback is strictly rejected to prevent duplicate mutation or unauthorized probing.
 */
export function isRouteNotFoundError(err: any): boolean {
  if (!err) return false;
  const status = err.problem?.status || err.status;
  if (status !== 404) return false;

  const problem = err.problem;
  // If the server explicitly returned a structured problem with an application code,
  // the route is mapped and served by the backend controller.
  if (
    problem?.code &&
    (problem.code.startsWith('RES-') ||
      problem.code.startsWith('APP-') ||
      problem.code.startsWith('SEC-') ||
      problem.code.startsWith('VAL-'))
  ) {
    return false;
  }
  // Generic Starlette / FastAPI unmapped route response: {"detail": "Not Found"}
  // or network-level client synth 404: code === "NET-404"
  return problem?.detail === 'Not Found' || problem?.code === 'NET-404' || !problem?.code;
}

/**
 * Robust fetch wrapper with W3C traceparent injection, Bearer auth, and RFC 9457 Problem Details error handling.
 */
export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const traceId = options.traceId || generateTraceId();
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
        problem = await response.json();
      } else {
        problem = {
          type: 'https://saintvision.invenio/problems/http-error',
          title: response.statusText || 'HTTP Error',
          status: response.status,
          detail: await response.text(),
          code: `NET-${response.status}`,
          category: 'NET',
          retryable: response.status >= 500,
          traceId,
        };
      }
    } catch {
      problem = {
        type: 'https://saintvision.invenio/problems/unknown',
        title: 'Communication Failure',
        status: response.status,
        detail: 'Failed to parse error response from server.',
        code: 'NET-PARSE',
        category: 'NET',
        retryable: true,
        traceId,
      };
    }
    throw new ApiError(problem);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
