import { beforeEach, expect, it, vi } from 'vitest';
import type { ShardObservation } from '../src/contracts/types';
import { apiClient } from '../src/shared/api/client';
import { fetchShardObservation, shardRows, shardRefreshNotice } from '../src/shared/api/shardObservation';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
beforeEach(() => { api.mockReset(); });
const view = (): ShardObservation => ({
  planId: 'plan', parentRunId: 'parent', rootPlanId: 'plan', sourcePlanId: null,
  generation: 0, parentState: 'running', aggregateManifestSha256: null,
  shardCount: 1, allPhysicallyStopped: false, allSucceeded: false,
  resultManifest: null, resultManifestSha256: null,
  shards: [{ index: 0, runId: 'child', nodeId: 'node', state: 'running', phase: 'uncertain', evidenceId: null }],
});

it('refreshes through the scoped observation endpoint', async () => {
  api.mockResolvedValue(view());
  expect((await fetchShardObservation('project', 'parent')).shards).toHaveLength(1);
  expect(api).toHaveBeenCalledExactlyOnceWith('/v1/projects/project/runs/parent/shards');
});
it('does not infer attempts or resource release from a stop phase', () => {
  const v = view(); v.shards[0] = { ...v.shards[0], phase: 'stopped', state: 'failed', evidenceId: 'evidence' };
  const row = shardRows(v)[0];
  expect(row.physicallyStopped).toBe(true);
  expect(row.verified).toBe(false);
  expect(row.attempt).toBeUndefined();
  expect(row.resourceReleasePending).toBeUndefined();
});
it('uses canonical shards even when a legacy items array disagrees', () => {
  const v = view(); v.items = []; expect(shardRows(v)).toHaveLength(1);
});
it('represents a new empty observation without retaining old rows', () => {
  const v = view(); expect(shardRows(v)).toHaveLength(1);
  v.shards = []; expect(shardRows(v)).toEqual([]);
});
it('does not report receipt arrival or complete resource return from refresh alone', () => {
  expect(shardRefreshNotice(view())).toContain('아직');
  expect(shardRefreshNotice({ ...view(), allPhysicallyStopped: true })).toContain('Run에서 확인');
});
it.each(['different-parent', null])('rejects mismatched parent %s', async parentRunId => {
  api.mockResolvedValue({ ...view(), parentRunId });
  await expect(fetchShardObservation('project', 'parent')).rejects.toThrow();
});
it('does not fallback or report success after denied access', async () => {
  api.mockRejectedValue(new Error('403'));
  await expect(fetchShardObservation('project', 'parent')).rejects.toThrow('403');
  expect(api).toHaveBeenCalledTimes(1);
});
it('does not invent a project identifier', async () => {
  await expect(fetchShardObservation('', 'parent')).rejects.toThrow();
  expect(api).not.toHaveBeenCalled();
});
