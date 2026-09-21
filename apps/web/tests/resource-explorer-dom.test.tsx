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

describe('VF-GM-02: My Computer / Resource Explorer Fabric & Topology Harness', () => {
  let container: HTMLDivElement;
  let root: Root;

  const cluster5Nodes: NodeItem[] = [
    {
      id: 'nod_01JABCDEF01',
      hostname: 'Node-01-WinMain',
      status: 'online',
      os: 'windows',
      cpuCores: 16,
      cpuUsagePercent: 25,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 28 * 1024 ** 3,
      allocatableCores: 12,
      allocatableMemoryBytes: 36 * 1024 ** 3,
      schedulable: true,
      observationOnly: false,
      gpuName: 'NVIDIA RTX 4090',
      gpuCount: 1,
      gpuVramTotalBytes: 24 * 1024 ** 3,
      gpuVramUsedBytes: 8 * 1024 ** 3,
      storageTotalBytes: 2048 * 1024 ** 3,
      storageUsedBytes: 850 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF02',
      hostname: 'Node-02-WinWork',
      status: 'online',
      os: 'windows',
      cpuCores: 8,
      cpuUsagePercent: 50,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 16 * 1024 ** 3,
      allocatableCores: 4,
      allocatableMemoryBytes: 12 * 1024 ** 3,
      schedulable: true,
      observationOnly: false,
      gpuName: 'NVIDIA RTX 3080',
      gpuCount: 1,
      gpuVramTotalBytes: 10 * 1024 ** 3,
      gpuVramUsedBytes: 6 * 1024 ** 3,
      storageTotalBytes: 1024 * 1024 ** 3,
      storageUsedBytes: 400 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF03',
      hostname: 'Node-03-WinDev',
      status: 'online',
      os: 'windows',
      cpuCores: 8,
      cpuUsagePercent: 10,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 8 * 1024 ** 3,
      allocatableCores: 6,
      allocatableMemoryBytes: 20 * 1024 ** 3,
      schedulable: true,
      observationOnly: false,
      gpuCount: 0,
      storageTotalBytes: 1024 * 1024 ** 3,
      storageUsedBytes: 300 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF04',
      hostname: 'Node-04-LinuxBuild',
      ipAddress: '192.168.45.225',
      status: 'online',
      os: 'linux',
      cpuCores: 16,
      cpuUsagePercent: 60,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 45 * 1024 ** 3,
      allocatableCores: 0,
      allocatableMemoryBytes: 0,
      schedulable: false,
      observationOnly: true,
      gpuCount: 0,
      storageTotalBytes: 4096 * 1024 ** 3,
      storageUsedBytes: 1800 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF05',
      hostname: 'Node-05-LinuxTrain',
      status: 'online',
      os: 'linux',
      cpuCores: 12,
      cpuUsagePercent: 10,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 8 * 1024 ** 3,
      allocatableCores: 10,
      allocatableMemoryBytes: 24 * 1024 ** 3,
      schedulable: true,
      observationOnly: false,
      gpuName: 'NVIDIA A4000',
      gpuCount: 1,
      gpuVramTotalBytes: 16 * 1024 ** 3,
      gpuVramUsedBytes: 2 * 1024 ** 3,
      storageTotalBytes: 2048 * 1024 ** 3,
      storageUsedBytes: 600 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
  ];

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

  it('proves side-by-side comparison: renders 60 vCPU, 224 GB RAM, 3 GPU 50GB VRAM, 10TB Storage against 5 physical nodes', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={cluster5Nodes} initialTab="overview" />);
    });

    // 1. Disclaimer banner with ADR-028 / ARCH-WEB-FABRIC-001
    const banner = container.querySelector('[data-testid="fabric-disclaimer-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.getAttribute('role')).toBe('alert');
    expect(banner?.textContent).toContain('물리 자원 분산 보존 원칙 (ADR-028 / ARCH-WEB-FABRIC-001)');
    expect(banner?.textContent).toContain('단일 하드웨어 버스로 마법처럼 병합된 것이 아니며');

    // 2. Logical Unified Capacity Cards
    const vcpuCard = container.querySelector('[data-testid="logical-vcpu-card"]');
    expect(vcpuCard).not.toBeNull();
    expect(vcpuCard?.textContent).toContain('60 Cores');
    expect(vcpuCard?.textContent).toContain('스케줄 가용: 32 Cores');

    const ramCard = container.querySelector('[data-testid="logical-ram-card"]');
    expect(ramCard).not.toBeNull();
    expect(ramCard?.textContent).toContain('224 GB');
    expect(ramCard?.textContent).toContain('스케줄 가용: 92 GB');

    const gpuCard = container.querySelector('[data-testid="logical-gpu-card"]');
    expect(gpuCard).not.toBeNull();
    expect(gpuCard?.textContent).toContain('3 장 (독립)');
    expect(gpuCard?.textContent).toContain('총 VRAM: 50 GB');

    const storageCard = container.querySelector('[data-testid="logical-storage-card"]');
    expect(storageCard).not.toBeNull();
    expect(storageCard?.textContent).toContain('10 TB');

    // 3. Physical Node Cards for all 5 nodes
    for (const node of cluster5Nodes) {
      const card = container.querySelector(`[data-testid="node-card-${node.id}"]`);
      expect(card).not.toBeNull();
      expect(card?.textContent).toContain(node.hostname);
    }
  });

  it('proves ADR-041 observation-only isolation boundary: Node-04 displays observation badge, unschedulable badge, 0 allocatable cores and filters accurately', async () => {
    await act(async () => {
      root.render(<ResourceExplorer nodes={cluster5Nodes} initialTab="overview" />);
    });

    // Node-04 card must render observe-only and unschedulable badges
    const node4Card = container.querySelector('[data-testid="node-card-nod_01JABCDEF04"]');
    expect(node4Card).not.toBeNull();
    expect(node4Card?.textContent).toContain('192.168.45.225');
    expect(node4Card?.textContent).toContain('CPU: 16C (0 가용)');

    const observeBadge = container.querySelector('[data-testid="observe-only-badge-nod_01JABCDEF04"]');
    expect(observeBadge).not.toBeNull();
    expect(observeBadge?.textContent).toBe('관측 전용');

    const unschedBadge = container.querySelector('[data-testid="unschedulable-badge-nod_01JABCDEF04"]');
    expect(unschedBadge).not.toBeNull();
    expect(unschedBadge?.textContent).toBe('스케줄 불가');

    // Negative control: Schedulable Node-01 must NOT have observation-only badge
    expect(container.querySelector('[data-testid="observe-only-badge-nod_01JABCDEF01"]')).toBeNull();
    expect(container.querySelector('[data-testid="unschedulable-badge-nod_01JABCDEF01"]')).toBeNull();

    // Filter test: 'observe' mode shows only Node-04
    const filterObserveBtn = container.querySelector<HTMLButtonElement>('[data-testid="filter-observe-btn"]');
    expect(filterObserveBtn).not.toBeNull();
    await act(async () => {
      filterObserveBtn!.click();
    });
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF04"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF01"]')).toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF02"]')).toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF03"]')).toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF05"]')).toBeNull();

    // Filter test: 'gpu' mode shows Node-01, 02, 05
    const filterGpuBtn = container.querySelector<HTMLButtonElement>('[data-testid="filter-gpu-btn"]');
    expect(filterGpuBtn).not.toBeNull();
    await act(async () => {
      filterGpuBtn!.click();
    });
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF01"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF02"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF05"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF03"]')).toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF04"]')).toBeNull();

    // Filter test: 'schedulable' mode excludes Node-04
    const filterSchedBtn = container.querySelector<HTMLButtonElement>('[data-testid="filter-schedulable-btn"]');
    expect(filterSchedBtn).not.toBeNull();
    await act(async () => {
      filterSchedBtn!.click();
    });
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF01"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF02"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF03"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF05"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="node-card-nod_01JABCDEF04"]')).toBeNull();

    // Filter test: 'all' restores all 5 nodes
    const filterAllBtn = container.querySelector<HTMLButtonElement>('[data-testid="filter-all-btn"]');
    expect(filterAllBtn).not.toBeNull();
    await act(async () => {
      filterAllBtn!.click();
    });
    for (const node of cluster5Nodes) {
      expect(container.querySelector(`[data-testid="node-card-${node.id}"]`)).not.toBeNull();
    }
  });

  it('proves Defect Pattern 1 & 2 guard: strictly rejects observation-only node (Node-04) from compute pool enrollment', async () => {
    const addMemberSpy = vi.spyOn(fabricApi, 'addPoolMember').mockResolvedValue({ poolId: 'pool-default', memberCount: 3 });

    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={cluster5Nodes}
          initialTab="pools"
          initialPoolCapacity={{
            poolId: 'pool-default',
            totalOffered: { cpuMillicores: 32000, ramBytes: 92 * 1024 ** 3, gpuDevices: 3 },
            largestSingleNode: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
            spareNow: { cpuMillicores: 20000, ramBytes: 50 * 1024 ** 3, gpuDevices: 2 },
          }}
          initialPoolCapacityState="success"
        />
      );
    });

    const select = container.querySelector<HTMLSelectElement>('[data-testid="pool-member-select"]');
    expect(select).not.toBeNull();

    // Verify option for Node-04 is disabled in DOM
    const node4Option = Array.from(select!.options).find((opt) => opt.value === 'nod_01JABCDEF04');
    expect(node4Option).toBeDefined();
    expect(node4Option?.disabled).toBe(true);
    expect(node4Option?.textContent).toContain('관측 전용 - 편입 불가');

    // Simulate selecting Node-04 and clicking add
    await act(async () => {
      select!.value = 'nod_01JABCDEF04';
      select!.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const addBtn = container.querySelector<HTMLButtonElement>('[data-testid="add-pool-member-btn"]');
    expect(addBtn).not.toBeNull();

    await act(async () => {
      addBtn!.click();
    });

    // Critical Pattern 2 check: Outer guard MUST intercept, addPoolMember API MUST NOT be invoked!
    expect(addMemberSpy).not.toHaveBeenCalled();

    // Pattern 1 check: Honest error banner with role="alert" must be visible
    const poolError = container.querySelector('[data-testid="pool-action-error"]');
    expect(poolError).not.toBeNull();
    expect(poolError?.getAttribute('role')).toBe('alert');
    expect(poolError?.textContent).toContain('관측 전용(schedulable: false)이므로 연산 풀에 편입할 수 없습니다');

    // Contrast with legitimate schedulable node (Node-03):
    await act(async () => {
      select!.value = 'nod_01JABCDEF03';
      select!.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await act(async () => {
      addBtn!.click();
    });
    expect(addMemberSpy).toHaveBeenCalledWith('pool-default', 'nod_01JABCDEF03');
    const poolSuccess = container.querySelector('[data-testid="pool-action-success"]');
    expect(poolSuccess).not.toBeNull();
    expect(poolSuccess?.textContent).toContain('노드 풀 멤버 추가 완료 (nod_01JABCDEF03)');
  });

  it('proves Defect Pattern 1 & 3 guard: storage registration failure renders honest role="alert" error banner', async () => {
    vi.spyOn(fabricApi, 'registerStorageContribution').mockRejectedValue(new Error('403 Forbidden: Quota exceeded'));
    vi.spyOn(fabricApi, 'getStorageContributions').mockResolvedValue({ items: [] });
    vi.spyOn(fabricApi, 'getStorageLocations').mockResolvedValue({ items: [] });

    await act(async () => {
      root.render(<ResourceExplorer nodes={cluster5Nodes} initialTab="storage" />);
    });

    const registerBtn = container.querySelector<HTMLButtonElement>('[data-testid="register-contribution-btn"]');
    expect(registerBtn).not.toBeNull();

    await act(async () => {
      registerBtn!.click();
      await Promise.resolve();
    });

    const storageActionError = container.querySelector('[data-testid="storage-action-error"]');
    expect(storageActionError).not.toBeNull();
    expect(storageActionError?.getAttribute('role')).toBe('alert');
    expect(storageActionError?.textContent).toContain('403 Forbidden: Quota exceeded');
    expect(container.querySelector('[data-testid="storage-action-success"]')).toBeNull();
  });

  it('proves Defect Pattern 1 & 3 guard: cluster sweep failure renders honest role="alert" error banner on overview', async () => {
    vi.spyOn(fabricApi, 'triggerLivenessSweep').mockRejectedValue(new Error('504 Gateway Timeout: Cluster sweep unreachable'));

    await act(async () => {
      root.render(<ResourceExplorer nodes={cluster5Nodes} initialTab="overview" />);
    });

    const sweepBtn = container.querySelector<HTMLButtonElement>('[data-testid="liveness-sweep-btn"]');
    expect(sweepBtn).not.toBeNull();

    await act(async () => {
      sweepBtn!.click();
      await Promise.resolve();
    });

    const livenessError = container.querySelector('[data-testid="liveness-action-error"]');
    expect(livenessError).not.toBeNull();
    expect(livenessError?.getAttribute('role')).toBe('alert');
    expect(livenessError?.textContent).toContain('504 Gateway Timeout: Cluster sweep unreachable');
    expect(container.querySelector('[data-testid="liveness-action-success"]')).toBeNull();
  });

  it('proves Defect Pattern 3 guard: node detail error suppresses hardware capabilities and allows retry', async () => {
    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={cluster5Nodes}
          initialTab="nodes"
          initialNodeDetailError="500 Internal Error: IPMI offline"
        />
      );
    });

    const nodeDetailError = container.querySelector('[data-testid="node-detail-error"]');
    expect(nodeDetailError).not.toBeNull();
    expect(nodeDetailError?.getAttribute('role')).toBe('alert');
    expect(nodeDetailError?.textContent).toContain('500 Internal Error: IPMI offline');

    // Hardware capabilities table MUST NOT be displayed
    expect(container.textContent).not.toContain('하드웨어 Capabilities 원장:');

    // Retry recovery
    const retryBtn = container.querySelector<HTMLButtonElement>('[data-testid="node-detail-retry"]');
    expect(retryBtn).not.toBeNull();

    vi.spyOn(fabricApi, 'getNodeDetail').mockResolvedValue({
      node: {
        nodeId: 'nod_01JABCDEF01',
        hostname: 'Node-01-WinMain',
        osType: 'windows',
        heartbeatSequence: 42,
        status: 'online',
      },
      capabilities: [
        {
          capabilityId: 'cap_cpu_01',
          kind: 'cpu',
          vendor: 'AMD',
          model: 'Ryzen 9 7950X',
          totalQuantity: 16,
          unit: 'cores',
          divisible: true,
        },
      ],
    });

    await act(async () => {
      retryBtn!.click();
      await Promise.resolve();
    });

    // Error banner MUST be cleared and capabilities table MUST appear
    expect(container.querySelector('[data-testid="node-detail-error"]')).toBeNull();
    expect(container.textContent).toContain('하드웨어 Capabilities 원장:');
    expect(container.textContent).toContain('Ryzen 9 7950X');
    expect(container.textContent).toContain('AMD');
  });
});
