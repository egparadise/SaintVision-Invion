import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { discoveryCandidatesFixture } from './fixtures/discovery-candidates';

const schemaUrl = new URL('../../../contracts/discovery-candidates-response.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
const validate = ajv.compile(schema);

describe('discovery candidates shared fixture', () => {
  it('matches the checked-in provider JSON Schema', () => {
    expect(validate(discoveryCandidatesFixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects mock drift when a required field is removed', () => {
    const { items, ...withoutItems } = discoveryCandidatesFixture;
    expect(validate(withoutItems), JSON.stringify(validate.errors)).toBe(false);
  });
});
