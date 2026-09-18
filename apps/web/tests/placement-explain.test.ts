import { describe, it, expect } from 'vitest';
import { evaluatePlacement } from '../src/features/placement/placementEngine';
import { NodeItem, PlacementRequirement } from '../src/contracts/types';

describe('S05-FE Placement Engine & Exclusion Explain (AC-05)', () => {
  const mockNodes: NodeItem[] = [
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
    {
      id: 'nod_01JABCDEF02',
      hostname: 'Node-02-WinWork',
      status: 'online',
      os: 'windows',
      cpuCores: 8,
      cpuUsagePercent: 30,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 15 * 1024 ** 3,
      allocatableCores: 4,
      allocatableMemoryBytes: 12 * 1024 ** 3,
      gpuCount: 1,
      gpuName: 'NVIDIA RTX 3080',
      gpuVramTotalBytes: 10 * 1024 ** 3,
      gpuVramUsedBytes: 4 * 1024 ** 3,
      storageTotalBytes: 1000 * 1024 ** 3,
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
      gpuCount: 0,
      storageTotalBytes: 1000 * 1024 ** 3,
      storageUsedBytes: 200 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF04',
      hostname: 'Node-04-LinuxBuild',
      status: 'online',
      os: 'linux',
      cpuCores: 16,
      cpuUsagePercent: 60,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 40 * 1024 ** 3,
      allocatableCores: 4,
      allocatableMemoryBytes: 16 * 1024 ** 3,
      gpuCount: 0,
      storageTotalBytes: 4000 * 1024 ** 3,
      storageUsedBytes: 1500 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
    {
      id: 'nod_01JABCDEF05',
      hostname: 'Node-05-LinuxTrain',
      status: 'online',
      os: 'linux',
      cpuCores: 12,
      cpuUsagePercent: 15,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 8 * 1024 ** 3,
      allocatableCores: 10,
      allocatableMemoryBytes: 24 * 1024 ** 3,
      gpuCount: 1,
      gpuName: 'NVIDIA A4000',
      gpuVramTotalBytes: 16 * 1024 ** 3,
      gpuVramUsedBytes: 2 * 1024 ** 3,
      storageTotalBytes: 2000 * 1024 ** 3,
      storageUsedBytes: 600 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
  ];

  it('should guarantee deterministic placement for identical inputs across 50 runs (AC-05)', () => {
    const req: PlacementRequirement = {
      requiredCores: 4,
      requiredMemoryBytes: 8 * 1024 ** 3,
      requiresGpu: true,
      preferredOs: 'windows',
      dataLocalityNodeId: 'nod_01JABCDEF01',
    };

    const firstDecision = evaluatePlacement(mockNodes, req).selectedNodeId;
    expect(firstDecision).toBe('nod_01JABCDEF01');

    for (let i = 0; i < 50; i++) {
      const decision = evaluatePlacement(mockNodes, req).selectedNodeId;
      expect(decision).toBe(firstDecision);
    }
  });

  it('should exclude nodes lacking required GPU via Hard Filter with explicit reason', () => {
    const req: PlacementRequirement = {
      requiredCores: 2,
      requiredMemoryBytes: 4 * 1024 ** 3,
      requiresGpu: true,
    };

    const result = evaluatePlacement(mockNodes, req);

    const node03 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF03');
    const node04 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF04');

    expect(node03?.hardFilterPassed).toBe(false);
    expect(node03?.rejectionReasons).toContain('가속 GPU 부재 (GPU 워크로드 요구)');

    expect(node04?.hardFilterPassed).toBe(false);
    expect(node04?.rejectionReasons).toContain('가속 GPU 부재 (GPU 워크로드 요구)');
  });

  it('should reject all candidates when required resources exceed available capacity (Zero-Oversubscription)', () => {
    const req: PlacementRequirement = {
      requiredCores: 100, // Exceeds all nodes
      requiredMemoryBytes: 500 * 1024 ** 3,
      requiresGpu: false,
    };

    const result = evaluatePlacement(mockNodes, req);

    expect(result.selectedNodeId).toBeNull();
    result.evaluations.forEach((evalItem) => {
      expect(evalItem.hardFilterPassed).toBe(false);
      expect(evalItem.rejectionReasons.some((r) => r.includes('부족'))).toBe(true);
    });
  });

  it('should unconditionally exclude fenced nodes from candidate selection', () => {
    const req: PlacementRequirement = {
      requiredCores: 4,
      requiredMemoryBytes: 8 * 1024 ** 3,
      requiresGpu: true,
      preferredOs: 'windows',
      dataLocalityNodeId: 'nod_01JABCDEF01',
    };

    const fenced = new Set(['nod_01JABCDEF01']);
    const result = evaluatePlacement(mockNodes, req, fenced);

    // Node-01 was the natural winner, but now fenced, so Node-02 must be selected
    expect(result.selectedNodeId).toBe('nod_01JABCDEF02');

    const node01 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF01');
    expect(node01?.hardFilterPassed).toBe(false);
    expect(node01?.rejectionReasons).toContain('노드가 격리/Fenced 상태로 안전 잠금됨');
  });

  it('should calculate weighted total score accurately (locality 40% + headroom 30% + network 30%)', () => {
    const req: PlacementRequirement = {
      requiredCores: 2,
      requiredMemoryBytes: 4 * 1024 ** 3,
      requiresGpu: false,
      dataLocalityNodeId: 'nod_01JABCDEF01',
    };

    const result = evaluatePlacement(mockNodes, req);
    const node01 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF01');

    expect(node01?.hardFilterPassed).toBe(true);
    expect(node01?.scores).toBeDefined();

    const { localityScore, headroomScore, networkCostScore, totalScore } = node01!.scores!;
    const expectedTotal = Math.round(localityScore * 0.4 + headroomScore * 0.3 + networkCostScore * 0.3);

    expect(totalScore).toBe(expectedTotal);
  });

  it('should reject candidates when allocatable capacity is unverified (undefined)', () => {
    const unverifiedNode: NodeItem = {
      ...mockNodes[0],
      id: 'nod_unverified',
      allocatableCores: undefined,
    };
    const req: PlacementRequirement = {
      requiredCores: 2,
      requiredMemoryBytes: 4 * 1024 ** 3,
      requiresGpu: false,
    };
    const result = evaluatePlacement([unverifiedNode], req);
    expect(result.evaluations[0].hardFilterPassed).toBe(false);
    expect(result.evaluations[0].rejectionReasons).toContain(
      '서버의 예약 가능량(allocatable) 미확인으로 작업 배치 차단됨'
    );
  });

  it('should safely return empty evaluation when nodes array is empty (resilience)', () => {
    const req: PlacementRequirement = {
      requiredCores: 2,
      requiredMemoryBytes: 4 * 1024 ** 3,
      requiresGpu: false,
    };
    const result = evaluatePlacement([], req);
    expect(result.selectedNodeId).toBeNull();
    expect(result.evaluations).toHaveLength(0);
    expect(result.policyVersion).toBe('POLICY-PLACEMENT-v1.0.0');
  });

  it('should reject nodes that are currently draining or offline with explicit reason', () => {
    const drainingNode: NodeItem = {
      ...mockNodes[0],
      id: 'nod_draining',
      isDraining: true,
      status: 'draining',
    };
    const offlineNode: NodeItem = {
      ...mockNodes[1],
      id: 'nod_offline',
      status: 'offline',
    };
    const req: PlacementRequirement = {
      requiredCores: 2,
      requiredMemoryBytes: 4 * 1024 ** 3,
      requiresGpu: false,
    };
    const result = evaluatePlacement([drainingNode, offlineNode], req);
    const drainEval = result.evaluations.find((e) => e.nodeId === 'nod_draining');
    const offlineEval = result.evaluations.find((e) => e.nodeId === 'nod_offline');

    expect(drainEval?.hardFilterPassed).toBe(false);
    expect(drainEval?.rejectionReasons.some((r) => r.includes('Drain'))).toBe(true);

    expect(offlineEval?.hardFilterPassed).toBe(false);
    expect(offlineEval?.rejectionReasons.some((r) => r.includes('비정상 (offline)'))).toBe(true);
  });
});

