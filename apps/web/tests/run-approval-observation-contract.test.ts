import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchObservedApprovals, fetchObservedRuns } from '../src/shared/api/runApprovalObservation';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const schemaUrl = new URL('../../../contracts/v1alpha1/core.schema.json', import.meta.url);
const schema = JSON.parse(readFileSync(schemaUrl, 'utf8'));
const ajv = new Ajv2020({ allErrors: true });
addFormats(ajv);
ajv.addSchema(schema);
const validateRunPage = ajv.compile({ $ref: `${schema.$id}#/$defs/ControlRunPage` });
const validateApprovalPage = ajv.compile({ $ref: `${schema.$id}#/$defs/ApprovalPage` });
const readFixture = (name: string) => JSON.parse(readFileSync(new URL(`../../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));

describe('run and approval observation response contract fixtures', () => {
  beforeEach(() => api.mockReset());

  it('validates the shared run and approval fixtures against canonical backend schemas', () => {
    const runPage = readFixture('control-run-page-response.json');
    const approvalPage = readFixture('approval-page-response.json');
    expect(validateRunPage(runPage), JSON.stringify(validateRunPage.errors)).toBe(true);
    expect(validateApprovalPage(approvalPage), JSON.stringify(validateApprovalPage.errors)).toBe(true);
  });

  it.each([
    ['control-run-page-response.json', validateRunPage],
    ['approval-page-response.json', validateApprovalPage],
  ])('rejects a shared %s fixture with a missing page cursor', (filename, validate) => {
    const changed = readFixture(filename);
    delete changed.nextCursor;
    expect(validate(changed)).toBe(false);
  });

  it('maps the shared run fixture and uses the project-scoped route', async () => {
    const fixture = readFixture('control-run-page-response.json');
    api.mockResolvedValue(fixture);
    const projectId = fixture.items[0].projectId;
    const result = await fetchObservedRuns(projectId);
    expect(result).toEqual([{ id: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV', projectId: 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAV', state: 'awaiting_approval', version: 3, attempt: 1 }]);
    expect(api).toHaveBeenCalledWith(`/v1/projects/${projectId}/runs`);
  });

  it('maps the shared approval fixture and uses the project-scoped route', async () => {
    const fixture = readFixture('approval-page-response.json');
    api.mockResolvedValue(fixture);
    const projectId = fixture.items[0].projectId;
    const result = await fetchObservedApprovals(projectId);
    expect(result).toEqual([{
      id: 'apr_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      projectId: 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      runId: 'run_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      requestedBy: 'usr_contract_requester',
      actionDigest: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      requiredApprovals: 1,
      status: 'pending',
      expiresAt: '2026-09-21T08:00:00+00:00',
      boundRunVersion: 3,
      policyReason: 'policy-v1',
    }]);
    expect(api).toHaveBeenCalledWith(`/v1/projects/${projectId}/approvals`);
  });

  it('rejects malformed page envelopes before mapping rows', async () => {
    api.mockResolvedValue({ items: [], nextCursor: 17 });
    await expect(fetchObservedRuns('prj_contract')).rejects.toThrow('Run 응답 형식 불일치');
    api.mockResolvedValue({ items: [], nextCursor: false });
    await expect(fetchObservedApprovals('prj_contract')).rejects.toThrow('승인 응답 형식 불일치');
  });
});
