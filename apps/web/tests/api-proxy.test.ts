import { describe, it, expect, vi } from 'vitest';
import {
  apiClient,
  ApiError,
  generateTraceId,
  generateSpanId,
  isRouteNotFoundError,
} from '../src/shared/api/client';
import { ProblemDetails } from '../src/contracts/types';

describe('API Client W3C Trace Context & RFC 9457 Conformance', () => {
  it('generates valid 32-character W3C traceId and 16-character spanId', () => {
    const traceId = generateTraceId();
    const spanId = generateSpanId();

    expect(traceId).toHaveLength(32);
    expect(traceId).toMatch(/^[0-9a-f]{32}$/);

    expect(spanId).toHaveLength(16);
    expect(spanId).toMatch(/^[0-9a-f]{16}$/);
  });

  it('injects traceparent header into outgoing requests', async () => {
    const mockResponse = { ok: true, status: 200, json: async () => ({ status: 'healthy' }) };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    await apiClient('/v1/health');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;

    expect(headers).toBeDefined();
    const traceparent = headers.get('traceparent');
    expect(traceparent).toBeDefined();
    expect(traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);

    fetchSpy.mockRestore();
  });

  it('injects Idempotency-Key header when idempotencyKey option is provided', async () => {
    const mockResponse = { ok: true, status: 200, json: async () => ({ status: 'cancelled' }) };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    await apiClient('/v1/runs/run_01/cancel', {
      method: 'POST',
      idempotencyKey: 'idmp_test_12345',
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Headers;

    expect(headers).toBeDefined();
    expect(headers.get('Idempotency-Key')).toBe('idmp_test_12345');

    fetchSpy.mockRestore();
  });

  it('correctly parses RFC 9457 problem details when receiving 4xx/5xx responses', async () => {
    const problemPayload: ProblemDetails = {
      type: 'about:blank',
      title: 'Node Not Found',
      status: 404,
      detail: "Node with ID 'nod_999' was not found.",
      code: 'RES-0004',
      category: 'RES',
      traceId: '762e595b40778bb35b693b8c852117b2',
      retryable: false,
      causeRef: null,
      evidenceId: null,
    };

    const mockResponse = {
      ok: false,
      status: 404,
      statusText: 'Not Found',
      headers: new Headers({ 'content-type': 'application/problem+json' }),
      json: async () => problemPayload,
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any);

    try {
      await apiClient('/v1/nodes/nod_999');
      expect.fail('Expected apiClient to throw ApiError');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(404);
      expect(apiErr.problem.code).toBe('RES-0004');
      expect(apiErr.problem.category).toBe('RES');
      expect(apiErr.problem.detail).toContain('nod_999');
    } finally {
      fetchSpy.mockRestore();
    }
  });

  describe('isRouteNotFoundError boundary discrimination', () => {
    it('identifies unmapped FastAPI route 404 ({detail: "Not Found"}) as route not found', () => {
      const err = new ApiError({
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        code: 'NET-0404',
        category: 'NET',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
        detail: 'Not Found',
      });
      expect(isRouteNotFoundError(err)).toBe(true);
    });

    it('identifies synthetic client network 404 as route not found', () => {
      const err = new ApiError({
        type: 'about:blank',
        title: 'Not Found',
        status: 404,
        code: 'NET-0404',
        category: 'NET',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
        detail: 'Network 404',
      });
      expect(isRouteNotFoundError(err)).toBe(true);
    });

    it('distinguishes entity/resource RES-RUN-404 from route not found', () => {
      const err = new ApiError({
        type: 'about:blank',
        title: 'Run Not Found',
        status: 404,
        code: 'RES-0004',
        category: 'RES',
        detail: 'Run run_123 does not exist or is masked',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
      });
      expect(isRouteNotFoundError(err)).toBe(false);
    });

    it('distinguishes SEC-TWO-PERSON-403, VAL-400, SEC-STATE-409 from route not found', () => {
      const err403 = new ApiError({
        type: 'about:blank',
        title: 'Forbidden',
        status: 403,
        code: 'SEC-0003',
        category: 'SEC',
        detail: 'Proposer cannot approve',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
      });
      const err409 = new ApiError({
        type: 'about:blank',
        title: 'Conflict',
        status: 409,
        code: 'SEC-0004',
        category: 'SEC',
        detail: 'Run not in resumable state',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
      });
      const err500 = new ApiError({
        type: 'about:blank',
        title: 'Internal Server Error',
        status: 500,
        code: 'SYS-0500',
        category: 'SYS',
        detail: 'Internal server error',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
      });

      expect(isRouteNotFoundError(err403)).toBe(false);
      expect(isRouteNotFoundError(err409)).toBe(false);
      expect(isRouteNotFoundError(err500)).toBe(false);
      expect(isRouteNotFoundError(null)).toBe(false);
      expect(isRouteNotFoundError(undefined)).toBe(false);
    });
  });
});
