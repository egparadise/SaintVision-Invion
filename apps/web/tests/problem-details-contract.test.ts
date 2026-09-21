import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import type { ProblemDetails } from '../src/contracts/types';
import { ApiError, apiClient } from '../src/shared/api/client';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const fixtureUrl = new URL('../../../contracts/fixtures/problem-details-response.json', import.meta.url);
const fixture = JSON.parse(readFileSync(fixtureUrl, 'utf8')) as ProblemDetails;
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validate = ajv.compile({ $ref: `${schema.$id}#/$defs/ProblemDetails` });

describe('ProblemDetails shared contract fixture', () => {
  it('is consumed using the generated frontend type and canonical schema', () => {
    expect(validate(fixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects a fixture missing a required nullable reference field', () => {
    const changed = { ...fixture } as Partial<ProblemDetails>;
    delete changed.causeRef;
    expect(validate(changed), JSON.stringify(validate.errors)).toBe(false);
  });

  it('accepts the shared fixture from the API client without translating it', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: fixture.status,
      statusText: 'Too Many Requests',
      headers: new Headers({ 'content-type': 'application/problem+json' }),
      json: async () => fixture,
    } as Response);

    try {
      const error = await apiClient('/v1/example').catch((caught) => caught as ApiError);
      expect(error).toBeInstanceOf(ApiError);
      expect(error.problem).toEqual(fixture);
      expect(validate(error.problem), JSON.stringify(validate.errors)).toBe(true);
    } finally {
      fetch.mockRestore();
    }
  });

  it.each(['plain-text', 'malformed-json', 'noncanonical-json'] as const)(
    'keeps local %s communication errors inside the canonical contract',
    async (kind) => {
      const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        headers: new Headers({
          'content-type': kind === 'plain-text' ? 'text/plain' : 'application/json',
        }),
        text: async () => 'x'.repeat(1200),
        json: async () => {
          if (kind === 'noncanonical-json') return { detail: 'Request failed' };
          throw new SyntaxError('invalid JSON');
        },
      } as Response);

      try {
        const caught = await apiClient('/v1/example').catch((error) => error as ApiError);
        expect(caught).toBeInstanceOf(ApiError);
        expect(validate(caught.problem), JSON.stringify(validate.errors)).toBe(true);
        expect(caught.problem.code).toBe('NET-0503');
        expect(caught.problem.detail.length).toBeLessThanOrEqual(1000);
      } finally {
        fetch.mockRestore();
      }
    },
  );
});
