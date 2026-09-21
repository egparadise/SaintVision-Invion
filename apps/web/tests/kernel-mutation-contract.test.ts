import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { approvalChallengeFixture } from './fixtures/approval-challenge';
import { approvalReviewFixture } from './fixtures/approval-review';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validateChallenge = ajv.compile({ $ref: `${schema.$id}#/$defs/ApprovalChallenge` });
const validateApproval = ajv.compile({ $ref: `${schema.$id}#/$defs/ApprovalView` });

describe('approval mutation response fixtures', () => {
  it('validates the challenge response fixture against the backend schema', () => {
    expect(validateChallenge(approvalChallengeFixture), JSON.stringify(validateChallenge.errors)).toBe(true);
  });

  it('rejects challenge fixture drift that removes its expiry', () => {
    const { expiresAt: _expiresAt, ...changed } = approvalChallengeFixture;
    expect(validateChallenge(changed), JSON.stringify(validateChallenge.errors)).toBe(false);
  });

  it('validates the decision response fixture against the backend schema', () => {
    expect(validateApproval(approvalReviewFixture.approval), JSON.stringify(validateApproval.errors)).toBe(true);
  });

  it('rejects decision response fixture drift that invents an unknown field', () => {
    const changed = { ...approvalReviewFixture.approval, inventedApproval: true };
    expect(validateApproval(changed), JSON.stringify(validateApproval.errors)).toBe(false);
  });
});
