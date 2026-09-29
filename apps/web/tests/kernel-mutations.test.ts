import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient, clearAuthToken } from '@/shared/api/client';
import { cancelKernelRun, decideApproval, _resetKernelMutationCache } from '@/shared/api/kernelMutations';
import { approvalReviewFixture } from './fixtures/approval-review';
import { approvalChallengeFixture } from './fixtures/approval-challenge';

let traceCount = 0;
vi.mock('@/shared/api/client', () => ({
  apiClient: vi.fn(),
  generateTraceId: () => `test-intent-key-${++traceCount}`,
  clearAuthToken: () => {
    globalThis.__sv_auth_teardown_listeners?.forEach((fn) => fn());
  },
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
  it('M1: non-retryable 409 GRAPH-0003 invalidates cache so subsequent call refetches Run version and generates a new key', async () => {
    // 1st attempt: reads version 9, but cancel fails with non-retryable 409 conflict
    api
      .mockResolvedValueOnce({ runId: 'run-409', version: 9 })
      .mockRejectedValueOnce({
        problem: {
          status: 409,
          code: 'GRAPH-0003',
          title: 'Version Conflict',
          detail: 'Run version was already advanced by another actor',
          retryable: false,
        },
      });

    await expect(cancelKernelRun('prj-1', 'run-409')).rejects.toMatchObject({
      problem: { code: 'GRAPH-0003' },
    });
    expect(api).toHaveBeenCalledTimes(2);
    expect(api.mock.calls[1][1]?.idempotencyKey).toBe('test-intent-key-1');

    // Subsequent click: cache was purged, so it MUST refetch the canonical Run version and issue a new key
    api
      .mockResolvedValueOnce({ runId: 'run-409', version: 10 })
      .mockResolvedValueOnce({ state: 'cancelled' });

    const secondResult = await cancelKernelRun('prj-1', 'run-409');
    expect(secondResult).toEqual({ state: 'cancelled' });
    expect(api).toHaveBeenCalledTimes(4);

    // Call 3 was GET run to read fresh version
    expect(api.mock.calls[2][0]).toBe('/v1/projects/prj-1/runs/run-409');
    // Call 4 was POST cancel with updated expectedVersion 10 and NEW key
    const secondCancelCall = api.mock.calls[3];
    expect(secondCancelCall[1]?.body).toBe('{"expectedVersion":10}');
    expect(secondCancelCall[1]?.idempotencyKey).toBe('test-intent-key-2');
  });

  it('M1: non-retryable 403 AUTH-0034 invalidates decision cache so subsequent call refetches challenge and generates a new key', async () => {
    const intent = {
      id: 'apr-403',
      projectId: 'prj-1',
      actionDigest: 'act-digest-1',
    };

    api
      .mockResolvedValueOnce({ approvalId: 'apr-403', nonce: 'nonce-stale' })
      .mockRejectedValueOnce({
        problem: {
          status: 403,
          code: 'AUTH-0034',
          title: 'Challenge Expired',
          detail: 'Nonce expired or consumed',
          retryable: false,
        },
      });

    await expect(decideApproval(intent, 'approve')).rejects.toMatchObject({
      problem: { code: 'AUTH-0034' },
    });
    expect(api).toHaveBeenCalledTimes(2);

    // Subsequent call must request a fresh challenge and issue a new key
    api
      .mockResolvedValueOnce({ approvalId: 'apr-403', nonce: 'nonce-fresh' })
      .mockResolvedValueOnce({ id: 'apr-403', status: 'approved' });

    await decideApproval(intent, 'approve');
    expect(api).toHaveBeenCalledTimes(4);

    // Call 3 was POST challenge
    expect(api.mock.calls[2][0]).toBe('/v1/projects/prj-1/approvals/apr-403/challenge');
    // Call 4 was POST decision with fresh nonce and NEW key
    const secondDecisionCall = api.mock.calls[3];
    expect(JSON.parse(secondDecisionCall[1]?.body as string).nonce).toBe('nonce-fresh');
    expect(secondDecisionCall[1]?.idempotencyKey).toBe('test-intent-key-2');
  });

  it('C2: retry cannot be overridden by caller-supplied idempotencyKey (cached key is strictly authoritative)', async () => {
    api
      .mockResolvedValueOnce({ runId: 'run-immutable', version: 5 })
      .mockRejectedValueOnce(new Error('503 Service Unavailable'));

    // 1st attempt: emits test-intent-key-1
    await expect(cancelKernelRun('prj-1', 'run-immutable')).rejects.toThrow('503 Service Unavailable');
    expect(api.mock.calls[1][1]?.idempotencyKey).toBe('test-intent-key-1');

    // 2nd attempt passes a different key option: cached key MUST remain authoritative
    api.mockResolvedValueOnce({ state: 'cancelled' });
    await cancelKernelRun('prj-1', 'run-immutable', { idempotencyKey: 'rogue-key-override' });

    expect(api.mock.calls[2][1]?.idempotencyKey).toBe('test-intent-key-1');
  });

  it('C2: auth teardown (clearAuthToken) purges mutation cache across logout/re-login', async () => {
    api
      .mockResolvedValueOnce({ runId: 'run-auth', version: 3 })
      .mockRejectedValueOnce(new Error('500 Server Error'));

    // User A makes a call that fails transiently (cached)
    await expect(cancelKernelRun('prj-1', 'run-auth')).rejects.toThrow('500 Server Error');
    expect(api.mock.calls[1][1]?.idempotencyKey).toBe('test-intent-key-1');

    // User A logs out (triggers onAuthTeardown -> _resetKernelMutationCache)
    clearAuthToken();

    // User B calls same resource: MUST NOT reuse cached key from previous session
    api
      .mockResolvedValueOnce({ runId: 'run-auth', version: 3 })
      .mockResolvedValueOnce({ state: 'cancelled' });

    await cancelKernelRun('prj-1', 'run-auth');
    expect(api).toHaveBeenCalledTimes(4);
    // Call 4 must use fresh key test-intent-key-2
    expect(api.mock.calls[3][1]?.idempotencyKey).toBe('test-intent-key-2');
  });
});
