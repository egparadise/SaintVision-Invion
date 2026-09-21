import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import type { NodeDetailResponse } from '@/contracts/node-detail-response';
import type { NodePageResponse } from '@/contracts/node-page-response';

const root = new URL('../../../contracts/', import.meta.url);
const fixtureRoot = new URL('../../../contracts/fixtures/', import.meta.url);
const load = (base: URL, name: string) => JSON.parse(readFileSync(new URL(name, base), 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const validatePage = ajv.compile(load(root, 'node-page-response.schema.json'));
const validateDetail = ajv.compile(load(root, 'node-detail-response.schema.json'));

describe('shared node inventory and detail contracts', () => {
  it('validates the shared node page fixture without inventing telemetry', () => {
    const fixture = load(fixtureRoot, 'node-page-response.json') as NodePageResponse;
    expect(validatePage(fixture), JSON.stringify(validatePage.errors)).toBe(true);
    expect(JSON.stringify(fixture)).not.toContain('cpuUsage');
    expect(JSON.stringify(fixture)).not.toContain('memoryUsed');
  });

  it('validates the shared node detail fixture', () => {
    const fixture = load(fixtureRoot, 'node-detail-response.json') as NodeDetailResponse;
    expect(validateDetail(fixture),
      JSON.stringify(validateDetail.errors)).toBe(true);
  });

  it('rejects extra or missing node fields and malformed capability quantities', () => {
    const page = load(fixtureRoot, 'node-page-response.json');
    const missing = structuredClone(page);
    delete missing.items[0].heartbeatSequence;
    expect(validatePage(missing)).toBe(false);

    const extra = structuredClone(page);
    extra.items[0].cpuUsage = 0;
    expect(validatePage(extra)).toBe(false);

    const detail = load(fixtureRoot, 'node-detail-response.json');
    detail.capabilities[0].totalQuantity = -1;
    expect(validateDetail(detail)).toBe(false);
  });
});
