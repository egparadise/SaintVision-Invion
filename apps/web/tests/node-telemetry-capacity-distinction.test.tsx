// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { NodeItem } from '../src/contracts/types';

describe('ResourceExplorer - Static Capacity vs Dynamic Utilization & Telemetry Absence', () => {
  let container: HTMLDivElement;
  let root: Root;

  const mockNodeWithoutTelemetry: NodeItem = {
    id: 'node_live_01',
    hostname: 'worker-node-01',
    ipAddress: '10.0.0.11',
    status: 'online',
    cpuCores: 16,
    allocatableCores: 14,
    cpuUsagePercent: Number.NaN,
    memoryTotalBytes: 32 * 1024 * 1024 * 1024,
    memoryUsedBytes: Number.NaN,
    allocatableMemoryBytes: 28 * 1024 * 1024 * 1024,
    storageTotalBytes: 500 * 1024 * 1024 * 1024,
    storageUsedBytes: Number.NaN,
    gpuCount: 0,
    gpuVramTotalBytes: 0,
    gpuVramUsedBytes: Number.NaN,
    schedulable: false,
    observationOnly: false,
    telemetryUnavailable: true,
    labels: { zone: 'ap-northeast-2a' },
  };

  const mockNodeUnknownCapacity: NodeItem = {
    id: 'node_unobserved_02',
    hostname: 'worker-node-unobserved',
    ipAddress: '10.0.0.12',
    status: 'online',
    cpuCores: Number.NaN,
    allocatableCores: Number.NaN,
    cpuUsagePercent: Number.NaN,
    memoryTotalBytes: Number.NaN,
    memoryUsedBytes: Number.NaN,
    allocatableMemoryBytes: Number.NaN,
    storageTotalBytes: Number.NaN,
    storageUsedBytes: Number.NaN,
    gpuCount: Number.NaN,
    gpuVramTotalBytes: Number.NaN,
    gpuVramUsedBytes: Number.NaN,
    schedulable: false,
    observationOnly: false,
    telemetryUnavailable: true,
    labels: {},
  };

  const mockNodeWithGpu: NodeItem = {
    id: 'node_gpu_03',
    hostname: 'worker-node-gpu',
    ipAddress: '10.0.0.13',
    status: 'online',
    cpuCores: 32,
    allocatableCores: 30,
    cpuUsagePercent: Number.NaN,
    memoryTotalBytes: 64 * 1024 * 1024 * 1024,
    memoryUsedBytes: Number.NaN,
    allocatableMemoryBytes: 60 * 1024 * 1024 * 1024,
    storageTotalBytes: 1000 * 1024 * 1024 * 1024,
    storageUsedBytes: Number.NaN,
    gpuCount: 2,
    gpuName: 'NVIDIA RTX 4090',
    gpuVramTotalBytes: 48 * 1024 * 1024 * 1024,
    gpuVramUsedBytes: Number.NaN,
    schedulable: false,
    observationOnly: false,
    telemetryUnavailable: true,
    labels: { accelerator: 'nvidia' },
  };

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
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

  it('preserves cluster nodes and does NOT vanish into empty list when telemetry is unavailable', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeWithoutTelemetry]} />);
    });

    const card = container.querySelector('[data-testid="node-card-node_live_01"]');
    expect(card).not.toBeNull();
    expect(container.textContent).toContain('worker-node-01');
    expect(container.querySelector('[data-testid="storage-no-nodes-notice"]')).toBeNull();
  });

  it('renders "미제공 (API 미노출)" for logical utilization and avoids 0 Cores / 0 B idle deception', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeWithoutTelemetry]} />);
    });

    const vcpuUsed = container.querySelector('[data-testid="logical-vcpu-used"]');
    expect(vcpuUsed).not.toBeNull();
    expect(vcpuUsed?.textContent).toBe('미제공 (API 미노출)');
    expect(vcpuUsed?.textContent).not.toContain('0 Cores');

    const ramUsed = container.querySelector('[data-testid="logical-ram-used"]');
    expect(ramUsed).not.toBeNull();
    expect(ramUsed?.textContent).toBe('미제공 (API 미노출)');
    expect(ramUsed?.textContent).not.toContain('0 B');

    const storageUsed = container.querySelector('[data-testid="logical-storage-used"]');
    expect(storageUsed).not.toBeNull();
    expect(storageUsed?.textContent).toBe('미제공 (API 미노출)');
    expect(storageUsed?.textContent).not.toContain('0 B');
  });

  it('strictly distinguishes GPU "0 (없음: 0대)" vs "모른다 (장치 미확인)" vs ">0 (모델명 및 대수)"', async () => {
    // 0대 탑재 노드
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeWithoutTelemetry]} />);
    });
    const gpuZero = container.querySelector('[data-testid="node-gpu-node_live_01"]');
    expect(gpuZero?.textContent).toBe('GPU: 없음 (0대)');
    expect(gpuZero?.textContent).not.toBe('GPU: 장치 미확인');

    // 미관측/NaN 노드
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeUnknownCapacity]} />);
    });
    const gpuUnknown = container.querySelector('[data-testid="node-gpu-node_unobserved_02"]');
    expect(gpuUnknown?.textContent).toBe('GPU: 장치 미확인');
    expect(gpuUnknown?.textContent).not.toBe('GPU: 없음 (0대)');
    expect(gpuUnknown?.textContent).not.toContain('NaN');

    // 2대 탑재 노드
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeWithGpu]} />);
    });
    const gpuWithCards = container.querySelector('[data-testid="node-gpu-node_gpu_03"]');
    expect(gpuWithCards?.textContent).toBe('GPU: NVIDIA RTX 4090 (2대)');
  });

  it('defends against NaN and renders "용량 미확인" and "미확인" when hardware capacity is absent', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeUnknownCapacity]} />);
    });

    const cpuNode = container.querySelector('[data-testid="node-cpu-node_unobserved_02"]');
    expect(cpuNode?.textContent).toContain('CPU: 용량 미확인');
    expect(cpuNode?.textContent).not.toContain('NaN');

    const ramNode = container.querySelector('[data-testid="node-ram-node_unobserved_02"]');
    expect(ramNode?.textContent).toBe('RAM: 미확인');
    expect(ramNode?.textContent).not.toContain('NaN');

    const storageNode = container.querySelector('[data-testid="node-storage-node_unobserved_02"]');
    expect(storageNode?.textContent).toBe('스토리지: 미확인');
    expect(storageNode?.textContent).not.toContain('NaN');
  });

  it('renders node utilization banner with role="status" and honest route absence notice', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={[mockNodeWithoutTelemetry]} />);
    });

    const banner = container.querySelector('[data-testid="node-utilization-status-node_live_01"]');
    expect(banner).not.toBeNull();
    expect(banner?.getAttribute('role')).toBe('status');
    expect(banner?.textContent).toBe('📊 자원 사용률: 미제공 (HTTP 읽기 경로 부재)');
  });

  it('renders static capacity distinction notice in Tab 4 when node detail is inspected', async () => {
    const mockDetail = {
      node: {
        nodeId: 'node_live_01',
        hostname: 'worker-node-01',
        osType: 'linux',
        osVersion: 'Ubuntu 24.04',
        agentVersion: '0.1.0',
        status: 'online',
        enrolledAt: '2026-09-21T00:00:00Z',
        lastHeartbeatAt: '2026-09-21T12:00:00Z',
        heartbeatSequence: 104,
        labels: {},
      },
      capabilities: [
        {
          capabilityId: 'cap_cpu_01',
          kind: 'cpu',
          vendor: 'AMD',
          model: 'EPYC 7763',
          totalQuantity: 16,
          unit: 'cores',
          divisible: true,
          deviceIndex: null,
        },
      ],
    };

    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={[mockNodeWithoutTelemetry]}
          initialTab="nodes"
          initialSelectedNodeId="node_live_01"
          initialNodeDetail={mockDetail as any}
        />
      );
    });

    const notice = container.querySelector('[data-testid="capabilities-static-capacity-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.getAttribute('role')).toBe('status');
    expect(notice?.textContent).toContain('정적 용량과 사용률 구별 고지');
    expect(notice?.textContent).toContain('정적 하드웨어 총용량(Total Capacity)');
    expect(notice?.textContent).toContain('HTTP 읽기 라우트가 부재(미제공)');
  });
});
