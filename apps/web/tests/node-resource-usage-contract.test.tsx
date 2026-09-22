// @vitest-environment happy-dom
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { apiClient } from '@/shared/api/client';
import {
  observedNodeResourceUsage,
  type NodeResourceUsageResponse,
} from '@/contracts/kernel-observation';
import { getNodeResourceUsage } from '@/features/desktop/fabricControlApi';
import { NodeDetail } from '@/features/nodes/NodeDetail';
import { NodeList } from '@/features/nodes/NodeList';
import type { NodeItem } from '@/contracts/types';

vi.mock('@/shared/api/client', () => ({
  apiClient: vi.fn(),
}));

const mockApi = vi.mocked(apiClient);

describe('NodeResourceUsage Contract & ViewModel (GM-02 / S02-FE)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  const fixtureWireResponse: NodeResourceUsageResponse = {
    source: 'execution-kernel',
    nodeId: 'nod_00000000000000000000000000',
    stateAsOf: '2026-09-22T07:00:00Z',
    resources: [
      {
        resourceId: 'res_00000000000000000000000000',
        kind: 'cpu',
        unit: 'millicores',
        capacity: 8000,
        offered: 6000,
        reserved: 3000,
        spare: 3000,
        measured: true,
        observedAt: '2026-09-22T07:00:00Z',
      },
      {
        resourceId: 'res_11111111111111111111111111',
        kind: 'gpu',
        unit: 'devices',
        capacity: 2,
        offered: 1,
        reserved: null,
        spare: null,
        measured: false,
        observedAt: null,
      },
    ],
  };

  it('observedNodeResourceUsage projects wire response and preserves nulls for unmeasured metrics (Zero-Mock)', () => {
    const projected = observedNodeResourceUsage(fixtureWireResponse);

    expect(projected.source).toBe('execution-kernel');
    expect(projected.nodeId).toBe('nod_00000000000000000000000000');
    expect(projected.stateAsOf).toBe('2026-09-22T07:00:00Z');
    expect(projected.resources).toHaveLength(2);

    const cpu = projected.resources[0];
    expect(cpu.kind).toBe('cpu');
    expect(cpu.unit).toBe('millicores');
    expect(cpu.capacity).toBe(8000);
    expect(cpu.offered).toBe(6000);
    expect(cpu.reserved).toBe(3000);
    expect(cpu.spare).toBe(3000);
    expect(cpu.measured).toBe(true);
    expect(cpu.observedAt).toBe('2026-09-22T07:00:00Z');

    const gpu = projected.resources[1];
    expect(gpu.kind).toBe('gpu');
    expect(gpu.unit).toBe('devices');
    expect(gpu.capacity).toBe(2);
    expect(gpu.offered).toBe(1);
    // Strict Zero-Mock: never synthesize 0 or current timestamp when measured is false
    expect(gpu.reserved).toBeNull();
    expect(gpu.spare).toBeNull();
    expect(gpu.measured).toBe(false);
    expect(gpu.observedAt).toBeNull();
  });

  it('observedNodeResourceUsage preserves null when capacity or offered are non-finite (Anti-F4 silent coercion)', () => {
    const nonFiniteWireResponse: NodeResourceUsageResponse = {
      source: 'execution-kernel',
      nodeId: 'nod_nonfinite_000000000000',
      stateAsOf: '2026-09-22T08:00:00Z',
      resources: [
        {
          resourceId: 'res_nonfinite_cpu',
          kind: 'cpu',
          unit: 'millicores',
          capacity: (NaN as any),
          offered: (undefined as any),
          reserved: null,
          spare: null,
          measured: false,
          observedAt: null,
        },
      ],
    };

    const projected = observedNodeResourceUsage(nonFiniteWireResponse);
    expect(projected.resources[0].capacity).toBeNull();
    expect(projected.resources[0].offered).toBeNull();
  });

  it('NodeDetail renders telemetry unavailable banner without hiding node capabilities', async () => {
    const mockNode: NodeItem = {
      id: 'nod_unmeasured_01',
      hostname: 'node-edge-01',
      ipAddress: '192.168.45.101',
      os: 'linux',
      status: 'active',
      cpuCores: 16,
      cpuUsagePercent: 0,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 0,
      storageTotalBytes: 500 * 1024 ** 3,
      storageUsedBytes: 0,
      gpuCount: 0,
      telemetryUnavailable: true,
      heartbeatAt: '2026-09-22T07:00:00Z',
    };

    await act(async () => {
      root.render(<NodeDetail node={mockNode} onBack={() => {}} />);
    });

    const banner = container.querySelector('[data-testid="node-telemetry-unavailable-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('동적 텔레메트리 미관측 상태');

    // Hardware capability panel must be preserved (not hidden by premature return)
    expect(container.textContent).toContain('하드웨어 Capability');
    expect(container.textContent).toContain('16 코어');
    expect(container.textContent).toContain('64.0 GiB');
  });

  it('NodeDetail renders capability resource usage panel with disclaimer and measured/unmeasured badges', async () => {
    const mockNode: NodeItem = {
      id: 'nod_00000000000000000000000000',
      hostname: 'node-fabric-01',
      ipAddress: '192.168.45.102',
      os: 'linux',
      status: 'active',
      cpuCores: 8,
      cpuUsagePercent: 0,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 0,
      storageTotalBytes: 1000 * 1024 ** 3,
      storageUsedBytes: 0,
      gpuCount: 2,
      gpuName: 'NVIDIA RTX 4090',
      gpuVramTotalBytes: 48 * 1024 ** 3,
      telemetryUnavailable: true,
      heartbeatAt: '2026-09-22T07:00:00Z',
    };

    const usage = observedNodeResourceUsage(fixtureWireResponse);

    await act(async () => {
      root.render(
        <NodeDetail node={mockNode} resourceUsage={usage} onBack={() => {}} />
      );
    });

    const panel = container.querySelector('[data-testid="capability-resource-usage-panel"]');
    expect(panel).not.toBeNull();
    expect(panel?.textContent).toContain('(실시간 캡처나 화면 갱신 시각이 아닙니다)');

    const cpuCard = container.querySelector('[data-testid="resource-usage-card-cpu"]');
    expect(cpuCard).not.toBeNull();
    const cpuBadge = container.querySelector('[data-testid="resource-measured-badge-cpu"]');
    expect(cpuBadge?.textContent).toContain('측정됨 (Measured)');
    expect(cpuCard?.textContent).toContain('3,000');

    const gpuCard = container.querySelector('[data-testid="resource-usage-card-gpu"]');
    expect(gpuCard).not.toBeNull();
    const gpuBadge = container.querySelector('[data-testid="resource-measured-badge-gpu"]');
    expect(gpuBadge?.textContent).toContain('미측정 (Unmeasured)');
    expect(gpuCard?.textContent).toContain('미측정');
  });

  it('NodeList renders active status notice and inspection button for unmeasured telemetry nodes', async () => {
    const onSelectNode = vi.fn();
    const mockNodes: NodeItem[] = [
      {
        id: 'nod_active_unmeasured',
        hostname: 'node-active-01',
        os: 'linux',
        status: 'active',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        gpuCount: 0,
        telemetryUnavailable: true,
        heartbeatAt: '2026-09-22T07:00:00Z',
      },
    ];

    await act(async () => {
      root.render(<NodeList nodes={mockNodes} onSelectNode={onSelectNode} />);
    });

    const activeNotice = container.querySelector(
      '[data-testid="node-active-status-notice-nod_active_unmeasured"]'
    );
    expect(activeNotice).not.toBeNull();
    expect(activeNotice?.textContent).toContain('계약 상태: active');

    const inspectBtn = container.querySelector(
      '[data-testid="node-detail-btn-nod_active_unmeasured"]'
    ) as HTMLButtonElement | null;
    expect(inspectBtn).not.toBeNull();

    await act(async () => {
      inspectBtn?.click();
    });
    expect(onSelectNode).toHaveBeenCalledWith('nod_active_unmeasured');
  });

  it('getNodeResourceUsage calls canonical project-scoped route with encoded parameters', async () => {
    mockApi.mockResolvedValueOnce(fixtureWireResponse);
    const result = await getNodeResourceUsage('nod-1/test', 'prj-1/main');
    expect(mockApi).toHaveBeenCalledWith(
      '/v1/projects/prj-1%2Fmain/nodes/nod-1%2Ftest/resource-usage'
    );
    expect(result.source).toBe('execution-kernel');
    expect(result.nodeId).toBe('nod_00000000000000000000000000');
  });

  it('NodeDetail renders unselected project notice when resourceUsageState is unselected', async () => {
    const mockNode: NodeItem = {
      id: 'nod_test_01',
      hostname: 'node-test',
      status: 'active',
      cpuCores: 4,
      cpuUsagePercent: 0,
      memoryTotalBytes: 16 * 1024 ** 3,
      memoryUsedBytes: 0,
      storageTotalBytes: 100 * 1024 ** 3,
      storageUsedBytes: 0,
      gpuCount: 0,
      telemetryUnavailable: true,
    };

    await act(async () => {
      root.render(
        <NodeDetail
          node={mockNode}
          resourceUsageState="unselected"
          onBack={() => {}}
        />
      );
    });

    const notice = container.querySelector('[data-testid="node-resource-usage-unselected-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.textContent).toContain('프로젝트 미선택 안내');
    expect(container.querySelector('[data-testid="capability-resource-usage-panel"]')).toBeNull();
  });

  it('NodeDetail renders loading state when resourceUsageState is loading', async () => {
    const mockNode: NodeItem = {
      id: 'nod_test_01',
      hostname: 'node-test',
      status: 'active',
      cpuCores: 4,
      cpuUsagePercent: 0,
      memoryTotalBytes: 16 * 1024 ** 3,
      memoryUsedBytes: 0,
      storageTotalBytes: 100 * 1024 ** 3,
      storageUsedBytes: 0,
      gpuCount: 0,
      telemetryUnavailable: true,
    };

    await act(async () => {
      root.render(
        <NodeDetail
          node={mockNode}
          resourceUsageState="loading"
          onBack={() => {}}
        />
      );
    });

    const loading = container.querySelector('[data-testid="node-resource-usage-loading"]');
    expect(loading).not.toBeNull();
    expect(loading?.textContent).toContain('조회 중');
  });

  it('NodeDetail renders error alert with role="alert" when resourceUsageState is error (Anti-F2 silent coercion)', async () => {
    const mockNode: NodeItem = {
      id: 'nod_test_01',
      hostname: 'node-test',
      status: 'active',
      cpuCores: 4,
      cpuUsagePercent: 0,
      memoryTotalBytes: 16 * 1024 ** 3,
      memoryUsedBytes: 0,
      storageTotalBytes: 100 * 1024 ** 3,
      storageUsedBytes: 0,
      gpuCount: 0,
      telemetryUnavailable: true,
    };

    await act(async () => {
      root.render(
        <NodeDetail
          node={mockNode}
          resourceUsageState="error"
          resourceUsageError="커널 연결 실패: 404 Not Found"
          onBack={() => {}}
        />
      );
    });

    const errorAlert = container.querySelector('[data-testid="node-resource-usage-error"]');
    expect(errorAlert).not.toBeNull();
    expect(errorAlert?.getAttribute('role')).toBe('alert');
    expect(errorAlert?.textContent).toContain('자원 사용량 조회 실패');
    expect(errorAlert?.textContent).toContain('404 Not Found');
    expect(container.querySelector('[data-testid="capability-resource-usage-panel"]')).toBeNull();
  });
});
