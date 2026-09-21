import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchStorageObservation } from '../src/shared/api/storageObservation';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validateStorageObservation = ajv.compile({ $ref: `${schema.$id}#/$defs/StorageObservationView` });
const readFixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));

describe('StorageObservationView contract fixture and storageObservation consumer', () => {
  beforeEach(() => api.mockReset());

  it('validates the shared storage-observation fixture against canonical backend schema', () => {
    const fixture = readFixture('storage-observation-response.json');
    expect(validateStorageObservation(fixture), JSON.stringify(validateStorageObservation.errors)).toBe(true);
  });

  it('rejects storage-observation fixture when currentHealth is synthesized as "healthy"', () => {
    const changed = readFixture('storage-observation-response.json');
    changed.currentHealth = 'healthy';
    expect(validateStorageObservation(changed)).toBe(false);
  });

  it('rejects storage-observation fixture when operationalAcceptanceAssessed is synthesized as true', () => {
    const changed = readFixture('storage-observation-response.json');
    changed.operationalAcceptanceAssessed = true;
    expect(validateStorageObservation(changed)).toBe(false);
  });

  it('rejects storage-observation fixture when integrityVerified is false for recorded status', () => {
    const changed = readFixture('storage-observation-response.json');
    changed.observation.integrityVerified = false;
    expect(validateStorageObservation(changed)).toBe(false);
  });

  it('fetchStorageObservation fetches and validates canonical response', async () => {
    const fixture = readFixture('storage-observation-response.json');
    api.mockResolvedValue(fixture);

    const result = await fetchStorageObservation(
      fixture.projectId,
      fixture.runId,
      fixture.requestId
    );

    expect(result).toEqual(fixture);
    expect(result.currentHealth).toBe('unknown');
    expect(result.operationalAcceptanceAssessed).toBe(false);
    expect(result.observation?.integrityVerified).toBe(true);
    expect(api).toHaveBeenCalledWith(
      `/v1/projects/${encodeURIComponent(fixture.projectId)}/runs/${encodeURIComponent(fixture.runId)}/storage-samples/${encodeURIComponent(fixture.requestId)}`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('fetchStorageObservation throws when response violates anti-synthesis constraint (healthy)', async () => {
    const fixture = readFixture('storage-observation-response.json');
    api.mockResolvedValue({
      ...fixture,
      currentHealth: 'healthy' as any,
    });

    await expect(
      fetchStorageObservation(fixture.projectId, fixture.runId, fixture.requestId)
    ).rejects.toThrow('StorageObservationView 응답 계약 불일치');
  });

  it('fetchStorageObservation guards against empty identifiers without making network requests', async () => {
    await expect(fetchStorageObservation('', 'run_01', 'req_01')).rejects.toThrow(
      '프로젝트 ID, Run ID, Request ID를 확인하세요.'
    );
    await expect(fetchStorageObservation('prj_01', '', 'req_01')).rejects.toThrow(
      '프로젝트 ID, Run ID, Request ID를 확인하세요.'
    );
    await expect(fetchStorageObservation('prj_01', 'run_01', '')).rejects.toThrow(
      '프로젝트 ID, Run ID, Request ID를 확인하세요.'
    );
    expect(api).not.toHaveBeenCalled();
  });
});
