import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';
import { apiClient } from '../src/shared/api/client';
import { fetchObservedRuns, fetchObservedApprovals } from '../src/shared/api/runApprovalObservation';
import { ApprovalCenter } from '../src/features/approvals/ApprovalCenter';
import { RunList } from '../src/features/runs/RunList';
vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
beforeEach(() => { api.mockReset(); });
const run = { runId: 'run', tenantId: 'tenant', projectId: 'project', state: 'running', version: 3, attempt: 0 };
const approval = { approvalId: 'approval', runId: 'run', projectId: 'project', requesterId: 'requester',
  actionDigest: 'a'.repeat(64), policyVersion: 'policy-v1', requiredApprovals: 2, status: 'pending',
  expiresAt: '2099-09-14T12:00:00Z', runVersion: 3 };
it('maps canonical Run identity and preserves zero attempts without inventing metadata', async () => {
  api.mockResolvedValue({ items: [run], nextCursor: null });
  expect(await fetchObservedRuns('project')).toEqual([{ id: 'run', projectId: 'project', state: 'running', version: 3, attempt: 0 }]);
});
it.each([{ projectId: 'other' }, { runId: '' }, { state: 'invented' }, { version: 0 }, { attempt: -1 }])(
  'rejects invalid or cross-project Run observations %o', async patch => {
    api.mockResolvedValue({ items: [{ ...run, ...patch }], nextCursor: null });
    await expect(fetchObservedRuns('project')).rejects.toThrow();
});
it('does not interpret required approval count as risk level', async () => {
  api.mockResolvedValue({ items: [approval], nextCursor: null });
  const [item] = await fetchObservedApprovals('project');
  expect(item.requiredApprovals).toBe(2); expect(item.boundRunVersion).toBe(3);
  for (const key of ['riskLevel','command','nodeId','workspaceId','createdAt','nonce','estimatedCostKrw','remainingBudgetKrw','blastRadius']) {
    expect(item).not.toHaveProperty(key);
  }
});
it.each([{ projectId: 'other' }, { actionDigest: '' }, { runVersion: 0 }, { expiresAt: 'invalid' },
  { status: 'invented' }, { requiredApprovals: 3 }, { requesterId: '' }])(
  'rejects incomplete approval bindings %o', async patch => {
    api.mockResolvedValue({ items: [{ ...approval, ...patch }], nextCursor: null });
    await expect(fetchObservedApprovals('project')).rejects.toThrow();
});
it('preserves dispatched status instead of manufacturing pending approvals', async () => {
  api.mockResolvedValue({ items: [{ ...approval, status: 'dispatched' }], nextCursor: null });
  expect((await fetchObservedApprovals('project'))[0].status).toBe('dispatched');
});
it('replaces old lists with actual empty responses', async () => {
  api.mockResolvedValue({ items: [], nextCursor: null });
  expect(await fetchObservedRuns('project')).toEqual([]);
  expect(await fetchObservedApprovals('project')).toEqual([]);
});
it('rejects unsupported list envelopes', async () => {
  api.mockResolvedValue({ results: [] });
  await expect(fetchObservedRuns('project')).rejects.toThrow();
  await expect(fetchObservedApprovals('project')).rejects.toThrow();
});
it('renders real Run IDs without invalid dates or fabricated objectives', async () => {
  api.mockResolvedValue({ items: [run], nextCursor: null });
  const html = renderToStaticMarkup(<RunList runs={await fetchObservedRuns('project')} isLoading={false} />);
  expect(html).toContain('미관측'); expect(html).not.toContain('Invalid Date');
  expect(html).toContain('run');
});
it('shows unknown approval information, actual reviewer, and a disabled approval button', async () => {
  api.mockResolvedValue({ items: [approval], nextCursor: null });
  const html = renderToStaticMarkup(<ApprovalCenter approvals={await fetchObservedApprovals('project')}
    currentUserId="actual-user" onApprove={async () => {}} onReject={async () => {}} />);
  expect(html).toContain('actual-user'); expect(html).toContain('미관측'); expect(html).toContain('승인이 보류');
  expect(html).not.toContain('usr_reviewer_02'); expect(html).not.toContain('<select');
  expect(html).not.toContain('10,000,000'); expect(html).not.toContain('deploy.release');
  expect(html).toMatch(/<button[^>]*disabled=""[^>]*>[^<]*승인/);
});
