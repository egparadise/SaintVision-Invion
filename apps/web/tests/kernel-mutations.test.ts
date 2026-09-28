import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/api/client';
import { cancelKernelRun, decideApproval, _resetKernelMutationCache } from '@/shared/api/kernelMutations';
import { approvalReviewFixture } from './fixtures/approval-review';
import { approvalChallengeFixture } from './fixtures/approval-challenge';

let traceCount = 0;
vi.mock('@/shared/api/client', () => ({
  apiClient: vi.fn(),
  generateTraceId: () => `test-intent-key-${++traceCount}`,
}));
const api = vi.mocked(apiClient);
beforeEach(() => {
  api.mockReset();
  _resetKernelMutationCache();
  traceCount = 0;
});

describe('kernel mutation contracts', () => {
  it.each(['approve', 'reject'] as const)('%s obtains a challenge before deciding', async decision => {
    api.mockResolvedValueOnce(approvalChallengeFixture).mockResolvedValueOnce(approvalReviewFixture.approval);
    const result = await decideApproval({
      id: approvalChallengeFixture.approvalId,
      projectId: approvalReviewFixture.approval.projectId,
      actionDigest: approvalReviewFixture.approval.actionDigest,
    }, decision);
    expect(result).toEqual(approvalReviewFixture.approval);
    expect(api.mock.calls).toEqual([
      [`/v1/projects/${approvalReviewFixture.approval.projectId}/approvals/${approvalChallengeFixture.approvalId}/challenge`, { method: 'POST', body: '{}' }],
      [`/v1/projects/${approvalReviewFixture.approval.projectId}/approvals/${approvalChallengeFixture.approvalId}/decision`, {
        method: 'POST', body: JSON.stringify({
          decision,
          nonce: approvalChallengeFixture.nonce,
          actionDigest: approvalReviewFixture.approval.actionDigest,
        }),
        idempotencyKey: 'test-intent-key-1',
      }],
    ]);
  });

  it('preserves the reviewed digest while the challenge is outstanding', async () => {
    const intent = { id: 'approval', projectId: 'project', actionDigest: 'reviewed' };
    api.mockImplementationOnce(async () => {
      intent.actionDigest = 'changed';
      return approvalChallengeFixture;
    }).mockResolvedValueOnce(approvalReviewFixture.approval);
    await decideApproval(intent, 'approve');
    expect(JSON.parse(api.mock.calls[1][1]!.body as string)).toEqual({
      decision: 'approve', nonce: approvalChallengeFixture.nonce, actionDigest: 'reviewed',
    });
  });

  it.each([undefined, ''])('refuses missing action digest %s before requesting a challenge', async actionDigest => {
    await expect(decideApproval({ id: 'approval', projectId: 'project', actionDigest }, 'approve')).rejects.toThrow();
    expect(api).not.toHaveBeenCalled();
  });

  it('does not send a decision after challenge failure', async () => {
    api.mockRejectedValueOnce(new Error('403'));
    await expect(decideApproval({ id: 'approval', projectId: 'project', actionDigest: 'digest' }, 'approve')).rejects.toThrow('403');
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('reads the Run version then sends only the canonical cancel body', async () => {
    api.mockResolvedValueOnce({ runId: 'run', version: 9 }).mockResolvedValueOnce({ state: 'cancelled' });
    await expect(cancelKernelRun('project', 'run')).resolves.toEqual({ state: 'cancelled' });
    expect(api.mock.calls).toEqual([
      ['/v1/projects/project/runs/run'],
      ['/v1/projects/project/runs/run/cancel', { method: 'POST', body: '{"expectedVersion":9}', idempotencyKey: 'test-intent-key-1' }],
    ]);
  });

  it.each([0, undefined, 1.5])('refuses invalid Run version %s', async version => {
    api.mockResolvedValueOnce({ runId: 'run', version });
    await expect(cancelKernelRun('project', 'run')).rejects.toThrow();
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('propagates cancellation failure without another mutation', async () => {
    api.mockResolvedValueOnce({ runId: 'run', version: 9 }).mockRejectedValueOnce(new Error('503'));
    await expect(cancelKernelRun('project', 'run')).rejects.toThrow('503');
    expect(api).toHaveBeenCalledTimes(2);
  });

  it('requires project scope instead of inventing one', async () => {
    await expect(cancelKernelRun(undefined, 'run')).rejects.toThrow();
    expect(api).not.toHaveBeenCalled();
  });

  it('F2: reuses identical Idempotency-Key and payload when retrying cancelKernelRun after failure without refetching Run version', async () => {
    api
      .mockResolvedValueOnce({ runId: 'run-retry', version: 9 })
      .mockRejectedValueOnce(new Error('503 Service Unavailable'));

    await expect(cancelKernelRun('prj-1', 'run-retry')).rejects.toThrow('503 Service Unavailable');
    expect(api).toHaveBeenCalledTimes(2);

    const firstCancelCall = api.mock.calls[1];
    const firstKey = firstCancelCall[1]?.idempotencyKey;
    const firstBody = firstCancelCall[1]?.body;
    expect(firstKey).toBe('test-intent-key-1');
    expect(firstBody).toBe('{"expectedVersion":9}');

    // 2nd attempt (retry): reuses firstKey and firstBody without refetching Run version
    api.mockResolvedValueOnce({ state: 'cancelled' });

    const retryResult = await cancelKernelRun('prj-1', 'run-retry');
    expect(retryResult).toEqual({ state: 'cancelled' });
    expect(api).toHaveBeenCalledTimes(3);

    const retryCancelCall = api.mock.calls[2];
    expect(retryCancelCall[0]).toBe('/v1/projects/prj-1/runs/run-retry/cancel');
    expect(retryCancelCall[1]?.idempotencyKey).toBe(firstKey);
    expect(retryCancelCall[1]?.body).toBe(firstBody);
  });

  it('F2: reuses identical Idempotency-Key and challenge payload when retrying decideApproval after failure', async () => {
    api
      .mockResolvedValueOnce(approvalChallengeFixture)
      .mockRejectedValueOnce(new Error('500 Internal Error'));

    const intent = {
      id: approvalChallengeFixture.approvalId,
      projectId: approvalReviewFixture.approval.projectId,
      actionDigest: approvalReviewFixture.approval.actionDigest,
    };

    await expect(decideApproval(intent, 'approve')).rejects.toThrow('500 Internal Error');
    expect(api).toHaveBeenCalledTimes(2);

    const firstDecisionCall = api.mock.calls[1];
    const firstKey = firstDecisionCall[1]?.idempotencyKey;
    const firstBody = firstDecisionCall[1]?.body;
    expect(firstKey).toBe('test-intent-key-1');

    // 2nd attempt (retry): reuses key and body
    api.mockResolvedValueOnce(approvalReviewFixture.approval);

    const retryResult = await decideApproval(intent, 'approve');
    expect(retryResult).toEqual(approvalReviewFixture.approval);
    expect(api).toHaveBeenCalledTimes(3);

    const retryDecisionCall = api.mock.calls[2];
    expect(retryDecisionCall[1]?.idempotencyKey).toBe(firstKey);
    expect(retryDecisionCall[1]?.body).toBe(firstBody);
  });
});
