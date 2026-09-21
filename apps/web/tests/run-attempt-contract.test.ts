import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { runAttemptListFixture } from './fixtures/run-attempt';

const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));

const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);

const validateAttemptList = ajv.compile({ $ref: `${schema.$id}#/$defs/RunAttemptList` });

describe('kernel run attempts shared wire fixtures', () => {
  it('validates runAttemptListFixture against core.schema.json #/$defs/RunAttemptList', () => {
    expect(validateAttemptList(runAttemptListFixture), JSON.stringify(validateAttemptList.errors)).toBe(true);
  });

  it('rejects runAttemptListFixture when required envelope field "source" is not "execution-kernel"', () => {
    const broken = { ...runAttemptListFixture, source: 'invalid-source' };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when required envelope field "nextCursor" is missing', () => {
    const { nextCursor: _nextCursor, ...broken } = runAttemptListFixture;
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when attempt required field "commandId" is missing', () => {
    const broken = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: '2026-09-21T12:00:00Z',
          nodeId: 'nod_0123456789ABCDEFGHJKMNPQRS',
          // missing commandId
          stopReceiptId: '22222222-2222-4222-8222-222222222222',
          exitCode: 0,
          reason: 'completed',
          evidenceId: 'evd_0123456789ABCDEFGHJKMNPQRS',
        },
      ],
    };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when attempt required field "stopReceiptId" is missing', () => {
    const broken = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: '2026-09-21T12:00:00Z',
          nodeId: 'nod_0123456789ABCDEFGHJKMNPQRS',
          commandId: '11111111-1111-4111-8111-111111111111',
          // missing stopReceiptId
          exitCode: 0,
          reason: 'completed',
          evidenceId: 'evd_0123456789ABCDEFGHJKMNPQRS',
        },
      ],
    };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when attempt required field "exitCode" is missing', () => {
    const broken = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: '2026-09-21T12:00:00Z',
          nodeId: 'nod_0123456789ABCDEFGHJKMNPQRS',
          commandId: '11111111-1111-4111-8111-111111111111',
          stopReceiptId: '22222222-2222-4222-8222-222222222222',
          // missing exitCode
          reason: 'completed',
          evidenceId: 'evd_0123456789ABCDEFGHJKMNPQRS',
        },
      ],
    };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when attempt required field "reason" is missing', () => {
    const broken = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: '2026-09-21T12:00:00Z',
          nodeId: 'nod_0123456789ABCDEFGHJKMNPQRS',
          commandId: '11111111-1111-4111-8111-111111111111',
          stopReceiptId: '22222222-2222-4222-8222-222222222222',
          exitCode: 0,
          // missing reason
          evidenceId: 'evd_0123456789ABCDEFGHJKMNPQRS',
        },
      ],
    };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('rejects runAttemptListFixture when attempt required field "evidenceId" is missing', () => {
    const broken = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: '2026-09-21T12:00:00Z',
          nodeId: 'nod_0123456789ABCDEFGHJKMNPQRS',
          commandId: '11111111-1111-4111-8111-111111111111',
          stopReceiptId: '22222222-2222-4222-8222-222222222222',
          exitCode: 0,
          reason: 'completed',
          // missing evidenceId
        },
      ],
    };
    expect(validateAttemptList(broken), JSON.stringify(validateAttemptList.errors)).toBe(false);
  });

  it('accepts null values for startedAt and nodeId in attempt items (contract richness: nullable required fields)', () => {
    const nullableValid = {
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: null, // scheduled or pre-dispatch attempt
          nodeId: null, // unassigned attempt
          commandId: null,
          stopReceiptId: null,
          exitCode: null,
          reason: null,
          evidenceId: null,
        },
      ],
    };
    expect(validateAttemptList(nullableValid), JSON.stringify(validateAttemptList.errors)).toBe(true);
  });
});
