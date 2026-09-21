// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import { NodeItem } from '../src/contracts/types';

const sampleNodes: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 20 * 1024 ** 3,
    allocatableCores: 12,
    allocatableMemoryBytes: 36 * 1024 ** 3,
    gpuCount: 1,
    gpuName: 'NVIDIA RTX 4090',
    gpuVramTotalBytes: 24 * 1024 ** 3,
    gpuVramUsedBytes: 6 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 500 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: any) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('ResourceExplorer Async Effect & State Transition (DOM Harness)', () => {
  let container: HTMLDivElement;
  let root: Root;

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

  it('proves pending transition: shows discovery-loading, no sentinel node, and no admission buttons', async () => {
    const pending = deferred<any>();
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    // In pending state while effect is awaiting network:
    expect(container.querySelector('[data-testid="discovery-loading"]')).not.toBeNull();
    expect(container.textContent).toContain('디스커버리 후보 목록을 조회하는 중입니다');
    // Critical boundary: No phantom/sentinel candidate cards and NO admission buttons while pending
    expect(container.textContent).not.toContain('Node-06-EdgeWorker');
    expect(container.textContent).not.toContain('ann_node06_unverified');
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
    expect(container.textContent).not.toContain('거부 (DELETE');

    // Clean up deferred
    await act(async () => {
      pending.resolve({ items: [] });
    });
  });

  it('proves success-with-data transition: renders discovered candidates and admission controls (catches setCandidates([]) mutation)', async () => {
    const pending = deferred<any>();
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    const realCandidate: fabricApi.DiscoveryCandidate = {
      announcementId: 'ann_live_99',
      instanceId: 'inst_live_99',
      sourceIp: '192.168.1.199',
      claimedHostname: 'Node-99-LiveDiscovered',
      claimedOsType: 'linux',
      claimedCpuCores: 32,
      claimedRamBytes: 128 * 1024 ** 3,
      claimedGpuCount: 2,
      firstSeenAt: new Date().toISOString(),
      lastSeenAt: new Date().toISOString(),
      announceCount: 1,
      stale: false,
      state: 'pending',
      verified: false,
    };

    // Resolve deferred with genuine candidates
    await act(async () => {
      pending.resolve({ items: [realCandidate] });
    });

    // Loading must be gone
    expect(container.querySelector('[data-testid="discovery-loading"]')).toBeNull();
    // Discovered machine MUST be visible
    expect(container.textContent).toContain('Node-99-LiveDiscovered');
    expect(container.textContent).toContain('192.168.1.199');
    expect(container.textContent).toContain('ann_live_99');
    // Operational buttons MUST be rendered for live candidate
    expect(container.textContent).toContain('승인 & 토큰 발급');
    expect(container.textContent).toContain('거부 (DELETE /candidates/ann_live_99)');
  });

  it('proves success-empty transition: renders discovery-empty-state truthfully after empty response', async () => {
    const pending = deferred<any>();
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    await act(async () => {
      pending.resolve({ items: [] });
    });

    expect(container.querySelector('[data-testid="discovery-loading"]')).toBeNull();
    expect(container.querySelector('[data-testid="discovery-empty-state"]')).not.toBeNull();
    expect(container.textContent).toContain('승인 대기 중인 디스커버리 후보가 없습니다');
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
  });

  it('proves error transition: renders discovery-error-banner and suppresses all candidate cards and admission buttons', async () => {
    const pending = deferred<any>();
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    await act(async () => {
      pending.reject(new Error('503 Service Unavailable: Discovery registry down'));
    });

    expect(container.querySelector('[data-testid="discovery-loading"]')).toBeNull();
    const errorBanner = container.querySelector('[data-testid="discovery-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(container.textContent).toContain('디스커버리 서비스 연결 오류');
    expect(container.textContent).toContain('503 Service Unavailable: Discovery registry down');
    expect(container.querySelector('[data-testid="discovery-retry-btn"]')).not.toBeNull();
    // Negative controls: no candidates, no buttons
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
    expect(container.textContent).not.toContain('Node-06-EdgeWorker');
  });

  it('proves storage error transition: renders storage-error-banner and suppresses false empty list text', async () => {
    const pendingContribs = deferred<any>();
    const pendingLocations = deferred<any>();
    vi.spyOn(fabricApi, 'getStorageContributions').mockReturnValue(pendingContribs.promise);
    vi.spyOn(fabricApi, 'getStorageLocations').mockReturnValue(pendingLocations.promise);

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="storage" />);
    });

    await act(async () => {
      pendingContribs.reject(new Error('500 Internal Storage Ledger Failure'));
      pendingLocations.resolve({ locations: [] });
    });

    const storageErrorBanner = container.querySelector('[data-testid="storage-error-banner"]');
    expect(storageErrorBanner).not.toBeNull();
    expect(container.textContent).toContain('스토리지 정보 조회 실패');
    expect(container.textContent).toContain('500 Internal Storage Ledger Failure');
    expect(container.querySelector('[data-testid="storage-retry-btn"]')).not.toBeNull();
    // Critical: must NOT show misleading empty state message on failure
    expect(container.querySelector('[data-testid="storage-empty-state"]')).toBeNull();
  });
});
