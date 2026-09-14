import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { cancelKernelRun, decideApproval } from './kernelMutations';

vi.mock('./client', () => ({ apiClient: vi.fn(), generateTraceId: () => 'test-intent-key' }));
const api = vi.mocked(apiClient);
beforeEach(() => api.mockReset());

describe('kernel mutation contracts', () => {
  it.each(['approve', 'reject'] as const)('%s obtains a challenge before deciding', async decision => {
    api.mockResolvedValueOnce({ nonce: 'issued-nonce' }).mockResolvedValueOnce({ status: 'pending' });
    await decideApproval({ id: 'approval', projectId: 'project', actionDigest: 'displayed-digest' }, decision);
    expect(api.mock.calls).toEqual([
      ['/v1/projects/project/approvals/approval/challenge', { method: 'POST', body: '{}' }],
      ['/v1/projects/project/approvals/approval/decision', {
        method: 'POST', body: JSON.stringify({ decision, nonce: 'issued-nonce', actionDigest: 'displayed-digest' }),
        idempotencyKey: 'test-intent-key',
      }],
    ]);
  });

  it('preserves the reviewed digest while the challenge is outstanding', async () => {
    const intent = { id: 'approval', projectId: 'project', actionDigest: 'reviewed' };
    api.mockImplementationOnce(async () => { intent.actionDigest = 'changed'; return { nonce: 'nonce' }; });
    await decideApproval(intent, 'approve');
    expect(JSON.parse(api.mock.calls[1][1]!.body as string).actionDigest).toBe('reviewed');
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
      ['/v1/projects/project/runs/run/cancel', { method: 'POST', body: '{"expectedVersion":9}', idempotencyKey: 'test-intent-key' }],
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
});
