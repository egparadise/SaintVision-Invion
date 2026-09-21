import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { storageContributionsFixture, storageLocationsFixture } from './fixtures/storage-catalog';

function loadSchema(name: string) {
  return JSON.parse(readFileSync(
    new URL(`../../../contracts/${name}.schema.json`, import.meta.url),
    'utf8',
  ));
}

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const validateContributions = ajv.compile(loadSchema('contribution-page-response'));
const validateLocations = ajv.compile(loadSchema('data-location-page-response'));

describe('storage catalog shared wire fixtures', () => {
  it('validates the exact contribution page mock against the backend-generated schema', () => {
    expect(validateContributions(storageContributionsFixture), JSON.stringify(validateContributions.errors)).toBe(true);
  });

  it('validates the exact data-location page mock against the backend-generated schema', () => {
    expect(validateLocations(storageLocationsFixture), JSON.stringify(validateLocations.errors)).toBe(true);
  });

  it('rejects fixture drift that omits a contribution field', () => {
    const { nodeId: _nodeId, ...item } = storageContributionsFixture.items[0];
    const changed = { ...storageContributionsFixture, items: [item] };
    expect(validateContributions(changed), JSON.stringify(validateContributions.errors)).toBe(false);
  });

  it('rejects fixture drift that adds an unknown location field', () => {
    const changed = {
      ...storageLocationsFixture,
      items: [{ ...storageLocationsFixture.items[0], fabricatedReady: true }],
    };
    expect(validateLocations(changed), JSON.stringify(validateLocations.errors)).toBe(false);
  });
});
