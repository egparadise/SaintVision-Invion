import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';
import type { ApprovalItem } from '../src/contracts/types';
import { apiClient } from '../src/shared/api/client';
import { approveReviewed, fetchApprovalReview, reviewedAction, reviewIdentity, type ApprovalReview } from '../src/shared/api/approvalReview';
import { ApprovalDetail } from '../src/features/approvals/ApprovalDetail';
import { approvalReviewFixture } from './fixtures/approval-review';
vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn(), generateTraceId: () => 'unique-test-key' }));
const api = vi.mocked(apiClient);
beforeEach(() => { api.mockReset(); });
const item = (): ApprovalItem => ({ id: approvalReviewFixture.approval.approvalId,
  projectId: approvalReviewFixture.approval.projectId, runId: approvalReviewFixture.approval.runId,
  actionDigest: approvalReviewFixture.approval.actionDigest, boundRunVersion: approvalReviewFixture.approval.runVersion,
  requestedBy: approvalReviewFixture.approval.requesterId,
  requiredApprovals: approvalReviewFixture.approval.requiredApprovals,
  policyReason: approvalReviewFixture.approval.policyVersion,
  expiresAt: approvalReviewFixture.approval.expiresAt, status: approvalReviewFixture.approval.status });
const review = (): ApprovalReview => structuredClone(approvalReviewFixture);
it('reads only the project-scoped review and preserves argument boundaries', async () => {
  api.mockResolvedValue(review()); const result = await fetchApprovalReview(item());
  expect(result.workload.command).toEqual(['echo','two words','<script>']);
  expect(api).toHaveBeenCalledExactlyOnceWith(
    `/v1/projects/${approvalReviewFixture.approval.projectId}/approvals/${approvalReviewFixture.approval.approvalId}/review`,
  );
});
it.each([{ approvalId: 'other' }, { projectId: 'other' }, { runId: 'other' },
  { actionDigest: 'b'.repeat(64) }, { runVersion: 5 }, { requesterId: 'other' },
  { requiredApprovals: 1 }, { policyVersion: 'new' }, { status: 'approved' }])(
  'rejects review binding mismatch %o', async patch => {
    const v = review(); api.mockResolvedValue({ ...v, approval: { ...v.approval, ...patch } });
    await expect(fetchApprovalReview(item())).rejects.toThrow();
});
it.each([{ command: [] }, { command: 'shell text' }, { projectId: 'other' }, { timeoutSeconds: 0 },
  { resources: {} }, { imageDigest: 'latest' }])('rejects incomplete action details %o', async patch => {
  const v = review(); api.mockResolvedValue({ ...v, workload: { ...v.workload, ...patch } });
  await expect(fetchApprovalReview(item())).rejects.toThrow();
});
it('does not fallback or enable approval when review is unsupported', async () => {
  api.mockRejectedValue(new Error('404')); await expect(fetchApprovalReview(item())).rejects.toThrow();
  expect(api).toHaveBeenCalledTimes(1);
});
it('captures the requested binding before a delayed response arrives', async () => {
  let resolve!: (value: ApprovalReview) => void;
  api.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  const current = item(); const pending = fetchApprovalReview(current); current.actionDigest = 'd'.repeat(64);
  resolve(review()); const result = await pending;
  await expect(approveReviewed(current, reviewedAction(result))).rejects.toThrow();
  expect(api).toHaveBeenCalledTimes(1);
});
it('requires the displayed proof before requesting a challenge', async () => {
  await expect(approveReviewed(item())).rejects.toThrow(); expect(api).not.toHaveBeenCalled();
});
it.each([{ id: 'other' }, { projectId: 'other' }, { actionDigest: 'd'.repeat(64) },
  { boundRunVersion: 5 }, { status: 'approved' as const }, { expiresAt: 'invalid' }])(
  'rejects a changed or invalid decision target %o', async patch => {
    await expect(approveReviewed({ ...item(), ...patch }, reviewedAction(review()))).rejects.toThrow();
    expect(api).not.toHaveBeenCalled();
});
it('keeps the displayed digest fixed throughout the challenge roundtrip', async () => {
  let resolve!: (value: { nonce: string }) => void;
  api.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  api.mockResolvedValueOnce({ status: 'approved' });
  const shown = reviewedAction(review()); const pending = approveReviewed(item(), shown);
  shown.actionDigest = 'd'.repeat(64); resolve({ nonce: 'challenge' }); await pending;
  expect(JSON.parse(api.mock.calls[1][1]!.body as string)).toEqual({ decision: 'approve', nonce: 'challenge', actionDigest: 'a'.repeat(64) });
});
it('invalidates displayed review identity when the binding changes', () => {
  expect(reviewIdentity(item())).not.toBe(reviewIdentity({ ...item(), boundRunVersion: 5 }));
});
it('renders reviewed arguments escaped and enables only the reviewed approval', () => {
  const v = review(); const enriched = { ...item(), command: JSON.stringify(v.workload.command), riskLevel: v.riskLevel };
  const render = (verified: boolean) => renderToStaticMarkup(<ApprovalDetail approval={enriched} currentUserId="reviewer"
    reviewedAction={verified ? reviewedAction(v) : undefined} onApprove={async () => {}} onReject={async () => {}} />);
  expect(render(false)).toMatch(/<button[^>]*disabled=""[^>]*>[^<]*승인/);
  expect(render(true)).not.toMatch(/<button[^>]*disabled=""[^>]*>[^<]*승인/);
  expect(render(true)).toContain('2인 승인 필요'); expect(render(true)).not.toContain('1차 승인 대기 중');
  expect(render(true)).toContain('&lt;script&gt;'); expect(render(true)).not.toContain('<script>');
});
