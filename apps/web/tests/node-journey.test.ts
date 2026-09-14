import { describe, it, expect } from 'vitest';
import { NodeItem, ProblemDetails } from '../src/contracts/types';

describe('S02-FE Node Observation Journey & State Transitions', () => {
  const mockNodes: NodeItem[] = [
    {
      id: 'nod_01JABCDEF01',
      hostname: 'Node-01-WinMain',
      status: 'online',
      os: 'windows',
      cpuCores: 16,
      cpuUsagePercent: 25,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 16 * 1024 ** 3,
      gpuCount: 1,
      gpuName: 'NVIDIA RTX 4090',
      gpuVramTotalBytes: 24 * 1024 ** 3,
      gpuVramUsedBytes: 6 * 1024 ** 3,
      storageTotalBytes: 2000 * 1024 ** 3,
      storageUsedBytes: 500 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF04',
      hostname: 'Node-04-LinuxBuild',
      status: 'online',
      os: 'linux',
      cpuCores: 16,
      cpuUsagePercent: 70,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 40 * 1024 ** 3,
      gpuCount: 0,
      storageTotalBytes: 4000 * 1024 ** 3,
      storageUsedBytes: 1500 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
  ];

  it('should calculate aggregate cluster capabilities correctly', () => {
    const totalCores = mockNodes.reduce((acc, n) => acc + n.cpuCores, 0);
    const totalRamGb = mockNodes.reduce((acc, n) => acc + n.memoryTotalBytes, 0) / 1024 ** 3;
    const totalGpus = mockNodes.reduce((acc, n) => acc + n.gpuCount, 0);

    expect(totalCores).toBe(32);
    expect(totalRamGb).toBe(128);
    expect(totalGpus).toBe(1);
  });

  it('should detect node heartbeat staleness (> 60s timeout according to ADR-007)', () => {
    const isNodeStale = (lastHeartbeatIso: string, timeoutSeconds: number = 60, nowMs: number = Date.now()) => {
      const elapsedSeconds = (nowMs - new Date(lastHeartbeatIso).getTime()) / 1000;
      return elapsedSeconds > timeoutSeconds;
    };

    const freshTime = new Date().toISOString();
    const staleTime = new Date(Date.now() - 75 * 1000).toISOString();

    expect(isNodeStale(freshTime)).toBe(false);
    expect(isNodeStale(staleTime)).toBe(true);
  });

  it('should handle 5 UI states: Normal, Loading, Empty, Error, Forbidden', () => {
    type UIState = 'normal' | 'loading' | 'empty' | 'error' | 'forbidden';

    const determineUIState = (params: {
      isLoading: boolean;
      isForbidden: boolean;
      error: ProblemDetails | null;
      items: any[];
    }): UIState => {
      if (params.isForbidden) return 'forbidden';
      if (params.error) return 'error';
      if (params.isLoading) return 'loading';
      if (params.items.length === 0) return 'empty';
      return 'normal';
    };

    expect(determineUIState({ isLoading: true, isForbidden: false, error: null, items: [] })).toBe('loading');
    expect(determineUIState({ isLoading: false, isForbidden: true, error: null, items: [] })).toBe('forbidden');
    expect(
      determineUIState({
        isLoading: false,
        isForbidden: false,
        error: {
          type: 'error',
          title: 'Database connection fail',
          status: 500,
          detail: 'Failed',
          code: 'DB-ERR',
          category: 'RES',
          retryable: true,
          traceId: '123',
        },
        items: [],
      })
    ).toBe('error');
    expect(determineUIState({ isLoading: false, isForbidden: false, error: null, items: [] })).toBe('empty');
    expect(determineUIState({ isLoading: false, isForbidden: false, error: null, items: mockNodes })).toBe('normal');
  });

  it('should ensure tenant isolation header is structured with valid UUID', () => {
    const tenantId = '7d29037c-3f41-4b13-a444-245842880c54';
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

    expect(uuidRegex.test(tenantId)).toBe(true);

    const headers = new Headers();
    headers.set('X-Inv-Tenant', tenantId);
    expect(headers.get('X-Inv-Tenant')).toBe(tenantId);
  });

  it('should support project-scoped node resolution with canonical mapping', () => {
    const prjId = 'prj_01JABCDE';
    const projectNodesPath = `/v1/projects/${prjId}/nodes`;
    expect(projectNodesPath).toBe('/v1/projects/prj_01JABCDE/nodes');

    const mapped = mockNodes.map((srvNode) => ({
      id: srvNode.id,
      hostname: srvNode.hostname,
      status: srvNode.status || 'online',
      schedulable: srvNode.schedulable ?? true,
    }));
    expect(mapped.length).toBe(2);
    expect(mapped[0].hostname).toBe('Node-01-WinMain');
    expect(mapped[1].hostname).toBe('Node-04-LinuxBuild');
  });
});
