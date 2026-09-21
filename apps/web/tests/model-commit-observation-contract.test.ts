import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fabricObservation } from '../src/shared/api/fabricObservation';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validateModelCommit = ajv.compile({ $ref: `${schema.$id}#/$defs/ModelCommitObservation` });
const readFixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));

describe('model commit observation contract fixture and fabricObservation consumer', () => {
  beforeEach(() => api.mockReset());

  it('validates the shared model-commit-observation fixture against canonical backend schema', () => {
    const fixture = readFixture('model-commit-observation-response.json');
    expect(validateModelCommit(fixture), JSON.stringify(validateModelCommit.errors)).toBe(true);
  });

  it('rejects model-commit-observation fixture with invalid classification enum', () => {
    const changed = readFixture('model-commit-observation-response.json');
    changed.classification = 'top-secret';
    expect(validateModelCommit(changed)).toBe(false);
  });

  it('rejects model-commit-observation fixture with missing required field', () => {
    const changed = readFixture('model-commit-observation-response.json');
    delete changed.currentAvailability;
    expect(validateModelCommit(changed)).toBe(false);
  });

  it('fabricObservation.model fetches and validates canonical commitment response', async () => {
    const fixture = readFixture('model-commit-observation-response.json');
    api.mockResolvedValue(fixture);

    const result = await fabricObservation.model(
      fixture.projectId,
      fixture.modelId,
      fixture.version
    );

    expect(result).toEqual(fixture);
    expect(result.currentAvailability).toBe('unknown');
    expect(result.requiresExecutionRevalidation).toBe(true);
    expect(api).toHaveBeenCalledWith(
      `/v1/projects/${encodeURIComponent(fixture.projectId)}/models/${encodeURIComponent(fixture.modelId)}/versions/${encodeURIComponent(fixture.version)}/commitment`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('fabricObservation.model throws when commitment response drifts from unknown availability invariant', async () => {
    const fixture = readFixture('model-commit-observation-response.json');
    api.mockResolvedValue({
      ...fixture,
      currentAvailability: 'ready', // drift
    });

    await expect(
      fabricObservation.model(fixture.projectId, fixture.modelId, fixture.version)
    ).rejects.toThrow('Model observation mismatch');
  });
});
