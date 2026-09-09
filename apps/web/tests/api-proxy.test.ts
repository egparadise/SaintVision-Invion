import { describe, it, expect, vi } from 'vitest';
import { apiClient, ApiError, generateTraceId, generateSpanId } from '../src/shared/api/client';
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

  it('correctly parses RFC 9457 problem details when receiving 4xx/5xx responses', async () => {
    const problemPayload: ProblemDetails = {
      type: 'https://saintvision.invenio/problems/node-not-found',
      title: 'Node Not Found',
      status: 404,
      detail: "Node with ID 'nod_999' was not found.",
      code: 'RES-NODE-404',
      category: 'RES',
      traceId: '762e595b40778bb35b693b8c852117b2',
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
      expect(apiErr.problem.code).toBe('RES-NODE-404');
      expect(apiErr.problem.category).toBe('RES');
      expect(apiErr.problem.detail).toContain('nod_999');
    } finally {
      fetchSpy.mockRestore();
    }
  });
});
