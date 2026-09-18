import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';
import { observedNode } from '../src/shared/api/nodeObservation';
import { fetchProjects, fetchProjectWorkspaces } from '../src/shared/api/projectObservation';
import { apiClient } from '../src/shared/api/client';
import { NodeList } from '../src/features/nodes/NodeList';
import { NodeDetail } from '../src/features/nodes/NodeDetail';
import { ClusterOverview } from '../src/features/dashboard/ClusterOverview';
vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
beforeEach(() => { api.mockReset(); });
const metrics = { nodeId: 'node', hostname: 'PC', status: 'online', osType: 'windows',
  lastHeartbeatAt: '2026-09-14T12:00:00Z', cpuCores: 8, cpuUsagePercent: 0,
  memoryTotalBytes: 8192, memoryUsedBytes: 0, storageTotalBytes: 16384, storageUsedBytes: 0,
  gpuCount: 0, schedulable: true, observationOnly: false, isDraining: false,
  killSwitchEngaged: false, allocatableCores: 8, allocatableMemoryBytes: 8192 };
it('preserves observed zero usage and GPU absence', () => {
  expect(observedNode(metrics)).toMatchObject({ telemetryUnavailable: false, cpuUsagePercent: 0,
    memoryUsedBytes: 0, gpuVramTotalBytes: 0, schedulable: true });
});
it.each([
  { cpuCores: undefined }, { cpuUsagePercent: Number.NaN }, { memoryUsedBytes: -1 },
  { cpuUsagePercent: 101 }, { memoryUsedBytes: 9000 }, { storageUsedBytes: 20000 },
  { lastHeartbeatAt: undefined }, { status: 'invented' }, { gpuCount: 1 }, { nodeId: '' },
])('does not admit incomplete or inconsistent telemetry %o', patch => {
  expect(observedNode({ ...metrics, ...patch })).toMatchObject({ telemetryUnavailable: true, schedulable: false });
});
it('never substitutes current time for a missing heartbeat', () => {
  expect(observedNode({ nodeId: 'node' }).heartbeatAt).toBe('');
});
it.each([{ allocatableCores: undefined }, { killSwitchEngaged: undefined }, { isDraining: true },
  { observationOnly: true }, { status: 'offline' }])('requires explicit admission observations %o', patch => {
  expect(observedNode({ ...metrics, ...patch }).schedulable).toBe(false);
});
it('renders missing telemetry without NaN or fabricated resource totals', () => {
  const node = observedNode({ nodeId: 'node', hostname: 'PC', status: 'online' });
  for (const view of [<NodeList nodes={[node]} isLoading={false} error={null} />,
    <NodeDetail node={node} onBack={() => {}} />,
    <ClusterOverview nodes={[node]} runs={[]} pendingApprovalsCount={0} onNavigate={() => {}} />]) {
    const html = renderToStaticMarkup(view);
    expect(html).toContain('미관측'); expect(html).not.toContain('NaN');
    expect(html).not.toContain('60 Cores'); expect(html).not.toContain('224 GiB');
  }
});
it('reads the business project envelope without inventing owner or capacity', async () => {
  api.mockResolvedValue({ projects: [{ projectId: 'project', displayName: '실제 프로젝트',
    createdAt: '2026-09-14', kernelLinked: false, kernelEnabled: false }], count: 1 });
  expect(await fetchProjects()).toEqual([{ id: 'project', name: '실제 프로젝트',
    createdAt: '2026-09-14', kernelLinked: false, kernelEnabled: false }]);
});
it('rejects an unsupported project envelope', async () => {
  api.mockResolvedValue({ unknown: [] }); await expect(fetchProjects()).rejects.toThrow();
});
it('preserves empty workspace lists without sample fallbacks', async () => {
  api.mockResolvedValue({ projectId: 'project', workspaces: [], count: 0 });
  expect(await fetchProjectWorkspaces('project')).toEqual([]);
});
it('rejects workspaces belonging to another project', async () => {
  api.mockResolvedValue({ projectId: 'project', workspaces: [{ workspaceId: 'workspace', projectId: 'other' }] });
  await expect(fetchProjectWorkspaces('project')).rejects.toThrow();
});
it('encodes project identifiers for the workspace route', async () => {
  api.mockResolvedValue({ projectId: 'a/b', workspaces: [] });
  await fetchProjectWorkspaces('a/b');
  expect(api).toHaveBeenCalledWith('/v1/projects/a%2Fb/workspaces');
});

it('reads kernel grant catalog without inventing business metadata', async () => {
  api.mockResolvedValue({ items: [{ projectId: 'actual-project' }] });
  expect(await fetchProjects()).toEqual([{ id: 'actual-project', name: 'actual-project', createdAt: '' }]);
});
it('rejects ambiguous catalog envelopes', async () => {
  api.mockResolvedValue({ projects: [], items: [] }); await expect(fetchProjects()).rejects.toThrow();
});
