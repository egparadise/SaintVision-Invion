import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { approvalReviewFixture } from './fixtures/approval-review';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validate = ajv.compile({ $ref: `${schema.$id}#/$defs/ApprovalReviewView` });

describe('approval review shared wire fixture', () => {
  it('matches the backend-generated ApprovalReviewView schema', () => {
    expect(validate(approvalReviewFixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects fixture drift that removes the immutable policy digest', () => {
    const { policyDigest: _policyDigest, ...changed } = approvalReviewFixture;
    expect(validate(changed), JSON.stringify(validate.errors)).toBe(false);
  });
});
