// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import * as storageObsApi from '../src/shared/api/storageObservation';
import { NodeItem } from '../src/contracts/types';
import { discoveryCandidatesFixture } from './fixtures/discovery-candidates';

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

    // MUT-05 kill assertion: verify 3-tier pool capacity cards are rendered truthfully
    expect(container.textContent).toContain('총 제공량 (Total Offered)');
    expect(container.textContent).toContain('단일 노드 최대 한도 (Largest Single)');
    expect(container.textContent).toContain('현재 유휴 여유량 (Spare Now)');
    expect(container.textContent).toContain('16C · 64 GB · 1 GPU');

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

  describe('Discovery Tenant Boundary Enforcement & Zero-Call Invariant', () => {
    it('suppresses discovery announcement (0 network calls) and disables broadcast button when tenantId is missing', async () => {
      const broadcastSpy = vi.spyOn(fabricApi, 'broadcastAnnouncement').mockResolvedValue({
        state: 'announced',
        announcementId: 'ann_dummy_01',
      } as any);

      // Render with NO tenantId
      await act(async () => {
        root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
      });

      // 1. Honest notice MUST be rendered
      const notice = container.querySelector('[data-testid="discovery-tenant-required-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.textContent).toContain('인증된 세션 테넌트 식별자(tenantId)가 없어');

      // 2. Broadcast button MUST be disabled
      const broadcastBtn = container.querySelector<HTMLButtonElement>('[data-testid="broadcast-announcement-btn"]');
      expect(broadcastBtn).not.toBeNull();
      expect(broadcastBtn?.disabled).toBe(true);

      // 3. Attempting to click disabled button MUST produce exactly 0 network calls
      await act(async () => {
        broadcastBtn!.click();
        await Promise.resolve();
      });

      expect(broadcastSpy).toHaveBeenCalledTimes(0);
    });

    it('enables broadcast button and passes authenticated tenantId in announcement when provided', async () => {
      const broadcastSpy = vi.spyOn(fabricApi, 'broadcastAnnouncement').mockResolvedValue({
        state: 'announced',
        announcementId: 'ann_live_123',
      } as any);

      // Render with authenticated tenantId
      await act(async () => {
        root.render(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" tenantId="ten_authenticated_corp" />);
      });

      // 1. Notice MUST NOT be rendered
      expect(container.querySelector('[data-testid="discovery-tenant-required-notice"]')).toBeNull();

      // 2. Broadcast button MUST be enabled
      const broadcastBtn = container.querySelector<HTMLButtonElement>('[data-testid="broadcast-announcement-btn"]');
      expect(broadcastBtn).not.toBeNull();
      expect(broadcastBtn?.disabled).toBe(false);

      // 3. Clicking button calls broadcastAnnouncement with the exact authenticated tenantId
      await act(async () => {
        broadcastBtn!.click();
        await Promise.resolve();
      });

      expect(broadcastSpy).toHaveBeenCalledTimes(1);
      expect(broadcastSpy).toHaveBeenCalledWith(expect.any(Object), 'ten_authenticated_corp');
    });

    it('proves planRunId defaults to empty string and gates create-plan-btn', async () => {
      await act(async () => {
        root.render(<ResourceExplorer nodes={sampleNodes} initialTab="pools" />);
      });

      const planRunInput = container.querySelector<HTMLInputElement>('[data-testid="plan-run-id-input"]');
      expect(planRunInput).not.toBeNull();
      // Crucial: Must default to empty string, NOT 'run_01JABCDEF_DEMO'
      expect(planRunInput?.value).toBe('');

      const createPlanBtn = container.querySelector<HTMLButtonElement>('[data-testid="create-plan-btn"]');
      expect(createPlanBtn).not.toBeNull();
      expect(createPlanBtn?.disabled).toBe(true);
      expect(createPlanBtn?.textContent).toContain('승인 Run ID 필요');
      expect(container.querySelector('[data-testid="plan-run-id-user-action-notice"]')?.textContent).toContain('[사용자 조치 필요]');
    });

    it('proves register-contribution-btn is disabled when cluster has no nodes', async () => {
      await act(async () => {
        root.render(<ResourceExplorer nodes={[]} initialTab="storage" />);
      });

      const registerBtn = container.querySelector<HTMLButtonElement>('[data-testid="register-contribution-btn"]');
      expect(registerBtn).not.toBeNull();
      expect(registerBtn?.disabled).toBe(true);
      expect(registerBtn?.textContent).toContain('등록 가능 노드 없음');
      expect(container.querySelector('[data-testid="storage-no-nodes-notice"]')?.textContent).toContain('[운영자 조치 필요]');
    });

    it('proves storage-observation-section renders and enforces anti-synthesis unknown health with genuine counts', async () => {
      const mockObservation = {
        requestId: '66666666-6666-4666-8666-666666666666',
        tenantId: '00000000-0000-4000-8000-000000000001',
        projectId: 'prj_0123456789ABCDEFGHJKMNPQRS',
        runId: 'run_0123456789ABCDEFGHJKMNPQRS',
        contributionId: 'stc_0123456789ABCDEFGHJKMNPQRS',
        status: 'recorded' as const,
        createdAt: '2026-09-21T12:00:00Z',
        expiresAt: 1790000000,
        currentHealth: 'unknown' as const,
        operationalAcceptanceAssessed: false as const,
        observation: {
          evidenceId: 'evd_0123456789ABCDEFGHJKMNPQRS',
          checkId: 'chk_0123456789ABCDEFGHJKMNPQRS',
          observedAt: 1790000000,
          integrityVerified: true as const,
          sampleHealthy: true,
          sampled: 10,
          mismatches: 0,
          unverifiable: 0,
          examined: 10,
          unsampled: 0,
        },
      };

      const fetchSpy = vi.spyOn(storageObsApi, 'fetchStorageObservation').mockResolvedValue(mockObservation);

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="storage"
            projectId="prj_0123456789ABCDEFGHJKMNPQRS"
            runId="run_0123456789ABCDEFGHJKMNPQRS"
            initialSampleRequestId="66666666-6666-4666-8666-666666666666"
          />
        );
      });

      const section = container.querySelector('[data-testid="storage-observation-section"]');
      expect(section).not.toBeNull();

      const input = container.querySelector<HTMLInputElement>('[data-testid="storage-sample-req-input"]');
      const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="fetch-storage-observation-btn"]');
      expect(input).not.toBeNull();
      expect(fetchBtn).not.toBeNull();
      expect(input?.value).toBe('66666666-6666-4666-8666-666666666666');
      expect(fetchBtn?.disabled).toBe(false);

      // Click fetch button
      await act(async () => {
        fetchBtn!.click();
        await Promise.resolve();
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        'prj_0123456789ABCDEFGHJKMNPQRS',
        'run_0123456789ABCDEFGHJKMNPQRS',
        '66666666-6666-4666-8666-666666666666'
      );

      // Invariant: currentHealth MUST remain "unknown" (never "healthy")
      const healthElem = container.querySelector('[data-testid="storage-observation-health"]');
      expect(healthElem?.textContent).toBe('unknown');

      // Invariant: operationalAcceptanceAssessed MUST be false
      const acceptanceElem = container.querySelector('[data-testid="storage-observation-acceptance"]');
      expect(acceptanceElem?.textContent).toContain('false');

      // Integrity verified is PASS
      const integrityElem = container.querySelector('[data-testid="storage-observation-integrity"]');
      expect(integrityElem?.textContent).toContain('무결성 확인됨 (VERIFIED)');

      // Counts rendered accurately
      const countsElem = container.querySelector('[data-testid="storage-observation-counts"]');
      expect(countsElem?.textContent).toContain('표본수: 10');
      expect(countsElem?.textContent).toContain('불일치: 0');
    });

    it('proves storage-observation disables fetch when projectId or runId is absent (0 network calls guard)', async () => {
      const fetchSpy = vi.spyOn(storageObsApi, 'fetchStorageObservation');

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="storage"
            // projectId and runId absent
          />
        );
      });

      const warning = container.querySelector('[data-testid="storage-observation-context-warning"]');
      expect(warning).not.toBeNull();
      expect(warning?.textContent).toContain('활성 프로젝트/실행(Run) 컨텍스트가 없어');
      expect(warning?.textContent).toContain('[사용자 조치 필요]');

      const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="fetch-storage-observation-btn"]');
      expect(fetchBtn?.disabled).toBe(true);

      // Attempting to click disabled button must not call API
      await act(async () => {
        fetchBtn!.click();
      });

      expect(fetchSpy).not.toHaveBeenCalled();
    });
  });

  describe('Discovery Empty-State Tri-Partition & Architectural Rule Notice (UI-FB-03)', () => {
    it('State 1 (Clean Zero Candidates): renders discovery-empty-state with truthful operator CLI credential rule notice, suppressing error banner', async () => {
      const pending = deferred<any>();
      vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="discovery"
            tenantId="ten_authenticated_corp"
          />
        );
      });

      // Initially in loading state
      expect(container.querySelector('[data-testid="discovery-loading"]')).not.toBeNull();

      // Query returns 0 items cleanly
      await act(async () => {
        pending.resolve({ items: [] });
      });

      // 1. discovery-empty-state MUST be rendered
      const emptyState = container.querySelector('[data-testid="discovery-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.textContent).toContain('승인 대기 중인 디스커버리 후보가 없습니다');
      expect(emptyState?.textContent).toContain('후보 목록이 비어 있는 이유 (시스템 아키텍처 규칙)');
      expect(emptyState?.textContent).toContain('saint operator issue-grant');
      expect(emptyState?.textContent).toContain('일회용 자격증명');
      expect(emptyState?.textContent).toContain('[운영자 조치 필요]');

      // 2. Negative controls: Error banner, tenant missing warning, and admission buttons MUST NOT exist
      expect(container.querySelector('[data-testid="discovery-error-banner"]')).toBeNull();
      expect(container.querySelector('[data-testid="discovery-tenant-required-notice"]')).toBeNull();
      expect(container.textContent).not.toContain('승인 & 토큰 발급');
    });

    it('State 2 (Query Failure): renders discovery-error-banner with role="alert" and retry button, suppressing empty-state and candidate cards', async () => {
      const pending = deferred<any>();
      vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockReturnValue(pending.promise);

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="discovery"
            tenantId="ten_authenticated_corp"
          />
        );
      });

      // Query fails with 503 error
      await act(async () => {
        pending.reject(new Error('503 Service Unavailable: Discovery daemon unreachable'));
      });

      // 1. Error banner MUST be rendered with role="alert"
      const errorBanner = container.querySelector('[data-testid="discovery-error-banner"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('디스커버리 서비스 연결 오류');
      expect(errorBanner?.textContent).toContain('503 Service Unavailable: Discovery daemon unreachable');

      // 2. Retry button MUST exist
      expect(container.querySelector('[data-testid="discovery-retry-btn"]')).not.toBeNull();

      // 3. Negative controls: discovery-empty-state and candidate rows MUST NOT exist
      expect(container.querySelector('[data-testid="discovery-empty-state"]')).toBeNull();
      expect(container.textContent).not.toContain('saint operator issue-grant');
      expect(container.textContent).not.toContain('승인 & 토큰 발급');
    });

    it('State 3 (Session Tenant Missing): renders discovery-tenant-required-notice, disables broadcast button, and enforces 0 network calls', async () => {
      const broadcastSpy = vi.spyOn(fabricApi, 'broadcastAnnouncement');

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="discovery"
            // tenantId is omitted
          />
        );
      });

      // 1. Tenant required barrier notice MUST appear
      const tenantNotice = container.querySelector('[data-testid="discovery-tenant-required-notice"]');
      expect(tenantNotice).not.toBeNull();
      expect(tenantNotice?.textContent).toContain('인증된 세션 테넌트 식별자(tenantId)가 없어');
      expect(tenantNotice?.textContent).toContain('위조 테넌트 합성 및 후보 한도 소진 방지');
      expect(tenantNotice?.textContent).toContain('[사용자 조치 필요]');

      // 2. Broadcast button MUST be disabled
      const broadcastBtn = container.querySelector<HTMLButtonElement>('[data-testid="broadcast-announcement-btn"]');
      expect(broadcastBtn).not.toBeNull();
      expect(broadcastBtn?.disabled).toBe(true);

      // 3. Attempting to click disabled button MUST produce exactly 0 network calls (zero-call guard)
      await act(async () => {
        broadcastBtn!.click();
        await Promise.resolve();
      });

      expect(broadcastSpy).toHaveBeenCalledTimes(0);
    });

    it('Tri-Partition Re-query Transition: proves State 1 (clean empty) <-> State 2 (error) mutual exclusion across live state transitions', async () => {
      let callCount = 0;
      const firstCall = deferred<any>();
      const secondCall = deferred<any>();

      vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockImplementation(() => {
        callCount++;
        return callCount === 1 ? firstCall.promise : secondCall.promise;
      });

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="discovery"
            tenantId="ten_authenticated_corp"
          />
        );
      });

      // 1. Resolve first call with empty array -> State 1 (Clean Empty)
      await act(async () => {
        firstCall.resolve({ items: [] });
      });

      expect(container.querySelector('[data-testid="discovery-empty-state"]')).not.toBeNull();
      expect(container.querySelector('[data-testid="discovery-error-banner"]')).toBeNull();

      // 2. Click refresh -> initiate second query
      const refreshBtn = container.querySelector<HTMLButtonElement>('[data-testid="discovery-refresh-btn"]');
      expect(refreshBtn).not.toBeNull();
      await act(async () => {
        refreshBtn!.click();
      });

      // 3. Reject second call -> Transition from State 1 to State 2 (Error)
      await act(async () => {
        secondCall.reject(new Error('500 Internal Discovery Failure'));
      });

      // Error banner MUST appear and empty state MUST be removed
      expect(container.querySelector('[data-testid="discovery-error-banner"]')).not.toBeNull();
      expect(container.querySelector('[data-testid="discovery-empty-state"]')).toBeNull();
    });

    it('proves canonical contract fixture binding: renders exact wire candidate and admission controls with state="candidate"', async () => {
      vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockResolvedValue(discoveryCandidatesFixture);
      const admitSpy = vi.spyOn(fabricApi, 'admitDiscoveryCandidate').mockResolvedValue({
        announcementId: 'ann_contract_fixture_01',
        bootstrapToken: 'btk_canonical_fixture_token_abc123',
        expiresAt: '2026-09-22T10:00:00Z',
        next: 'bootstrap_and_enroll',
      });

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={sampleNodes}
            initialTab="discovery"
            tenantId="ten_authenticated_corp"
          />
        );
      });

      // 1. Verify exact wire contract values rendered
      expect(container.textContent).toContain('fixture-node');
      expect(container.textContent).toContain('192.0.2.41');
      expect(container.textContent).toContain('ann_contract_fixture_01');
      expect(container.textContent).toContain('CANDIDATE');
      expect(container.textContent).toContain('linux · 8C · 32 GB · 1 GPU');

      // 2. Candidate state admission button MUST be present
      const admitBtn = container.querySelector<HTMLButtonElement>('[data-testid="admit-candidate-btn"]');
      const declineBtn = container.querySelector<HTMLButtonElement>('[data-testid="decline-candidate-btn"]');
      expect(admitBtn).not.toBeNull();
      expect(declineBtn).not.toBeNull();
      expect(admitBtn?.textContent).toContain('승인 & 토큰 발급');

      // 3. Click admit and verify admission result modal appears
      await act(async () => {
        admitBtn!.click();
      });

      expect(admitSpy).toHaveBeenCalledWith('ann_contract_fixture_01');
      const modal = container.querySelector('[data-testid="admission-result-modal"]');
      expect(modal).not.toBeNull();
      expect(modal?.textContent).toContain('일회용 부트스트랩 토큰 발급 완료');
      expect(modal?.textContent).toContain('btk_canonical_fixture_token_abc123');
    });
  });
});
