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
    expect(storageErrorBanner?.getAttribute('role')).toBe('alert');
    expect(container.textContent).toContain('스토리지 정보 조회 실패');
    expect(container.textContent).toContain('500 Internal Storage Ledger Failure');
    expect(container.querySelector('[data-testid="storage-retry-btn"]')).not.toBeNull();
    // Critical: must NOT show misleading empty state message on failure
    expect(container.querySelector('[data-testid="storage-empty-state"]')).toBeNull();
  });

  it('proves candidate -> empty re-query transition: clears previous row and shows discovery-empty-state (fails if items.length > 0 mutant injected)', async () => {
    let callCount = 0;
    const firstCall = deferred<any>();
    const secondCall = deferred<any>();

    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockImplementation(() => {
      callCount++;
      return callCount === 1 ? firstCall.promise : secondCall.promise;
    });

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    // 1st query resolves with 1 candidate
    const candidate: fabricApi.DiscoveryCandidate = {
      announcementId: 'ann_live_01',
      instanceId: 'inst_01',
      sourceIp: '192.168.1.101',
      claimedHostname: 'Node-01-Candidate',
      claimedOsType: 'linux',
      claimedCpuCores: 16,
      claimedRamBytes: 64 * 1024 ** 3,
      claimedGpuCount: 1,
      state: 'pending',
      verified: false,
    };
    await act(async () => {
      firstCall.resolve({ items: [candidate] });
    });

    // Verify row and operational buttons exist
    expect(container.textContent).toContain('Node-01-Candidate');
    expect(container.textContent).toContain('승인 & 토큰 발급');
    expect(container.querySelector('[data-testid="discovery-empty-state"]')).toBeNull();

    // Trigger 2nd query via refresh button
    const refreshBtn = container.querySelector<HTMLButtonElement>('[data-testid="discovery-refresh-btn"]');
    expect(refreshBtn).not.toBeNull();
    await act(async () => {
      refreshBtn!.click();
    });

    // 2nd query resolves with empty array
    await act(async () => {
      secondCall.resolve({ items: [] });
    });

    // Verify previous candidate and operational buttons are GONE, and empty state is displayed
    expect(container.textContent).not.toContain('Node-01-Candidate');
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
    expect(container.querySelector('[data-testid="discovery-empty-state"]')).not.toBeNull();
    expect(container.textContent).toContain('승인 대기 중인 디스커버리 후보가 없습니다');
  });

  it('proves candidate -> error re-query transition: clears previous row and suppresses operational buttons (fails if setCandidates([]) removed from catch)', async () => {
    let callCount = 0;
    const firstCall = deferred<any>();
    const secondCall = deferred<any>();

    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockImplementation(() => {
      callCount++;
      return callCount === 1 ? firstCall.promise : secondCall.promise;
    });

    await act(async () => {
      root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
    });

    const candidate: fabricApi.DiscoveryCandidate = {
      announcementId: 'ann_live_02',
      instanceId: 'inst_02',
      sourceIp: '192.168.1.102',
      claimedHostname: 'Node-02-Candidate',
      claimedOsType: 'windows',
      claimedCpuCores: 8,
      claimedRamBytes: 32 * 1024 ** 3,
      claimedGpuCount: 0,
      state: 'pending',
      verified: false,
    };
    await act(async () => {
      firstCall.resolve({ items: [candidate] });
    });

    // Verify candidate is visible
    expect(container.textContent).toContain('Node-02-Candidate');
    expect(container.textContent).toContain('승인 & 토큰 발급');

    // Trigger re-query
    const refreshBtn = container.querySelector<HTMLButtonElement>('[data-testid="discovery-refresh-btn"]');
    await act(async () => {
      refreshBtn!.click();
    });

    // 2nd query fails
    await act(async () => {
      secondCall.reject(new Error('500 Internal Discovery Failure'));
    });

    // Error banner MUST appear with role="alert"
    const errorBanner = container.querySelector('[data-testid="discovery-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(container.textContent).toContain('500 Internal Discovery Failure');

    // Previous candidate and admission buttons MUST BE CLEARED
    expect(container.textContent).not.toContain('Node-02-Candidate');
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
    expect(container.textContent).not.toContain('거부 (DELETE');

    // Critical: While retrying after error, stale candidates must NOT flash during loading
    const retryBtn = container.querySelector<HTMLButtonElement>('[data-testid="discovery-retry-btn"]');
    expect(retryBtn).not.toBeNull();
    const retryCall = deferred<any>();
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(retryCall.promise);
    await act(async () => {
      retryBtn!.click();
    });
    // Stale candidate MUST NOT be visible during retry loading
    expect(container.textContent).not.toContain('Node-02-Candidate');
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
  });

  it('proves error state suppresses operational buttons even when candidate data is supplied (fails if candidatesState !== "error" guard removed)', async () => {
    const candidate: fabricApi.DiscoveryCandidate = {
      announcementId: 'ann_live_03',
      instanceId: 'inst_03',
      sourceIp: '192.168.1.103',
      claimedHostname: 'Node-03-GhostCandidate',
      claimedOsType: 'linux',
      claimedCpuCores: 64,
      claimedRamBytes: 256 * 1024 ** 3,
      claimedGpuCount: 4,
      state: 'pending',
      verified: false,
    };

    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={sampleNodes}
          initialTab="discovery"
          initialCandidatesState="error"
          initialCandidatesError="503 Service Unavailable"
          initialCandidates={[candidate]}
        />
      );
    });

    // Error banner MUST be visible with role="alert"
    const errorBanner = container.querySelector('[data-testid="discovery-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(container.textContent).toContain('503 Service Unavailable');

    // Candidate card and operational buttons MUST BE SUPPRESSED by error guard
    expect(container.textContent).not.toContain('승인 & 토큰 발급');
    expect(container.textContent).not.toContain('거부 (DELETE');
    expect(container.textContent).not.toContain('Node-03-GhostCandidate');
  });
});
