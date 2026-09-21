import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { runLogViewFixture } from './fixtures/run-log';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);

const validateLogView = ajv.compile({ $ref: `${schema.$id}#/$defs/RunLogView` });

describe('kernel run log shared wire fixtures', () => {
  it('validates runLogViewFixture against core.schema.json #/$defs/RunLogView', () => {
    expect(validateLogView(runLogViewFixture), JSON.stringify(validateLogView.errors)).toBe(true);
  });

  it('rejects runLogViewFixture when required field "source" is invalid (not "execution-kernel")', () => {
    const broken = { ...runLogViewFixture, source: 'invalid-source' };
    expect(validateLogView(broken), JSON.stringify(validateLogView.errors)).toBe(false);
  });

  it('rejects runLogViewFixture when required field "stdout" is removed', () => {
    const { stdout: _stdout, ...broken } = runLogViewFixture;
    expect(validateLogView(broken), JSON.stringify(validateLogView.errors)).toBe(false);
  });

  it('rejects runLogViewFixture when required field "truncated" is removed', () => {
    const { truncated: _truncated, ...broken } = runLogViewFixture;
    expect(validateLogView(broken), JSON.stringify(validateLogView.errors)).toBe(false);
  });

  it('rejects runLogViewFixture when required field "absentReason" is removed', () => {
    const { absentReason: _absentReason, ...broken } = runLogViewFixture;
    expect(validateLogView(broken), JSON.stringify(validateLogView.errors)).toBe(false);
  });

  it('rejects runLogViewFixture when required field "redacted" is removed', () => {
    const { redacted: _redacted, ...broken } = runLogViewFixture;
    expect(validateLogView(broken), JSON.stringify(validateLogView.errors)).toBe(false);
  });
});
