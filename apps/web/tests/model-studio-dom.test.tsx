// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ModelStudioView } from '../src/features/desktop/ModelStudioView';
import { ModelManifest } from '../src/contracts/virtualFabric';
import { NodeItem } from '../src/contracts/types';

const clusterNodesFixture: NodeItem[] = [
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
    gpuVramUsedBytes: 8 * 1024 ** 3, // 16GB available
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
    gpuVramUsedBytes: 6 * 1024 ** 3, // 4GB available
    storageTotalBytes: 1024 * 1024 ** 3,
    storageUsedBytes: 400 * 1024 ** 3,
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
    observationOnly: true, // Observation only node
    gpuCount: 0,
    storageTotalBytes: 4096 * 1024 ** 3,
    storageUsedBytes: 1800 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
];

const sampleModel: ModelManifest = {
  modelId: 'med-cxr-seg',
  name: 'med-cxr-seg',
  version: '2.1.0',
  format: 'safetensors',
  totalBytes: 12 * 1024 ** 3, // 12 GB
  contentHash: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
  shards: [
    {
      shardIndex: 0,
      shardId: 'shd_0',
      byteRange: '0-6442450943',
      layers: 'layer.0-15',
      contentHash: 'hash0',
      sizeBytes: 6 * 1024 ** 3,
      replicas: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          status: 'healthy',
        },
        {
          nodeId: 'nod_01JABCDEF02',
          nodeHostname: 'Node-02-WinWork',
          status: 'missing', // Shard 0 is degraded!
        },
      ],
    },
    {
      shardIndex: 1,
      shardId: 'shd_1',
      byteRange: '6442450944-12884901887',
      layers: 'layer.16-31',
      contentHash: 'hash1',
      sizeBytes: 6 * 1024 ** 3,
      replicas: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          status: 'healthy',
        },
        {
          nodeId: 'nod_01JABCDEF02',
          nodeHostname: 'Node-02-WinWork',
          status: 'healthy',
        },
      ],
    },
  ],
  runtimeCompatibility: ['vllm', 'onnxruntime'],
  licensePolicy: 'internal_medical_license',
  classification: 'confidential',
  encryption: { enabled: false },
  supportedModes: [
    'single_node',
    'request_routing',
    'data_parallel',
    'tensor_pipeline_parallel',
    'cpu_gpu_offload',
  ],
  status: 'committed',
  createdAt: '2026-09-21T00:00:00Z',
  updatedAt: '2026-09-21T00:00:00Z',
};

describe('VF-GM-04: Model Studio DOM Harness & ADR-041 Guarantees', () => {
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

  // ---------------------------------------------------------------------------
  // 1. Query & Manifest Explorer
  // ---------------------------------------------------------------------------
  it('[VF-GM-04-QUERY] queries model and renders manifest metadata', async () => {
    const onQueryMock = vi.fn().mockResolvedValue({
      modelId: 'med-cxr-seg',
      version: '2.1.0',
      committedAt: '2026-09-21T00:00:00Z',
      manifestHash: sampleModel.contentHash,
      sourceRunId: 'run_train_01',
      format: 'safetensors',
      totalBytes: sampleModel.totalBytes,
      shardCount: 2,
      licensePolicy: 'internal_medical_license',
      classification: 'confidential',
    });

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          clusterNodes={clusterNodesFixture}
          onQueryModel={onQueryMock}
        />
      );
    });

    const modelInput = container.querySelector<HTMLInputElement>('[data-testid="model-id-input"]');
    const versionInput = container.querySelector<HTMLInputElement>('[data-testid="model-version-input"]');
    const queryBtn = container.querySelector<HTMLButtonElement>('[data-testid="query-model-btn"]');

    expect(modelInput).not.toBeNull();
    expect(versionInput).not.toBeNull();
    expect(queryBtn?.disabled).toBe(true);

    const setInputValue = (input: HTMLInputElement, value: string) => {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      descriptor?.set?.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    await act(async () => {
      setInputValue(modelInput!, 'med-cxr-seg');
      setInputValue(versionInput!, '2.1.0');
    });

    expect(queryBtn?.disabled).toBe(false);

    await act(async () => {
      queryBtn!.click();
      await Promise.resolve();
    });

    expect(onQueryMock).toHaveBeenCalledWith('prj_01', 'med-cxr-seg', '2.1.0');
    expect(container.querySelector('[data-testid="model-manifest-article"]')).not.toBeNull();
    expect(container.textContent).toContain('med-cxr-seg · 2.1.0');
    expect(container.textContent).toContain('internal_medical_license');
  });

  // ---------------------------------------------------------------------------
  // 2. Shard & Replica Fabric Matrix
  // ---------------------------------------------------------------------------
  it('[VF-GM-04-SHARD-MATRIX] renders shards matrix and surfaces degradation badge on missing replica', async () => {
    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const shardsTable = container.querySelector('[data-testid="shards-table"]');
    expect(shardsTable).not.toBeNull();

    // Shard 0 has a missing replica -> Degraded badge must be rendered with role="alert"
    const shard0Row = container.querySelector('[data-testid="shard-row-0"]');
    expect(shard0Row).not.toBeNull();
    const degradedBadge = shard0Row?.querySelector('[data-testid="shard-degradation-badge"]');
    expect(degradedBadge).not.toBeNull();
    expect(degradedBadge?.getAttribute('role')).toBe('alert');
    expect(degradedBadge?.textContent).toContain('저하 (1/2)');

    // Shard 1 is healthy -> Degraded badge must NOT be rendered
    const shard1Row = container.querySelector('[data-testid="shard-row-1"]');
    expect(shard1Row?.querySelector('[data-testid="shard-degradation-badge"]')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 3. Shard Repair Guard & Outcomes
  // ---------------------------------------------------------------------------
  it('[VF-GM-04-REPAIR-GUARD] disables repair and displays alert when 0 surviving eligible nodes exist', async () => {
    // Only Node-01 (hosts replica) and Node-04 (observation-only)
    const clusterWithZeroSurviving: NodeItem[] = [
      clusterNodesFixture[0],
      clusterNodesFixture[2], // Node-04: observationOnly
    ];

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterWithZeroSurviving}
        />
      );
    });

    const shard0Row = container.querySelector('[data-testid="shard-row-0"]');
    const noSurviving = shard0Row?.querySelector('[data-testid="no-surviving-nodes-0"]');
    expect(noSurviving).not.toBeNull();
    expect(noSurviving?.getAttribute('role')).toBe('alert');
    expect(noSurviving?.textContent).toContain('생존 노드 없음 (복구 불가)');
    expect(shard0Row?.querySelector('[data-testid="repair-shard-0-btn"]')).toBeNull();
  });

  it('[VF-GM-04-REPAIR-FAIL] surfaces honest error alert when shard repair fails (Catches Mutation 4)', async () => {
    const onRepairMock = vi.fn().mockResolvedValue({
      success: false,
      repairedReplicas: sampleModel.shards[0].replicas,
      message: '507 Insufficient Disk on Target Node',
    });

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
          onRepairShard={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-shard-0-btn"]');
    expect(repairBtn).not.toBeNull();

    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    expect(onRepairMock).toHaveBeenCalled();
    const repairError = container.querySelector('[data-testid="shard-repair-error"]');
    expect(repairError).not.toBeNull();
    expect(repairError?.getAttribute('role')).toBe('alert');
    expect(repairError?.textContent).toContain('507 Insufficient Disk on Target Node');
    expect(container.querySelector('[data-testid="shard-repair-success"]')).toBeNull();
  });

  it('[VF-GM-04-REPAIR-PARTIAL] surfaces warning alert when repaired shard remains degraded', async () => {
    const onRepairMock = vi.fn().mockResolvedValue({
      success: true,
      repairedReplicas: [
        { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
        { nodeId: 'nod_01JABCDEF02', nodeHostname: 'Node-02-WinWork', status: 'missing' },
      ],
    });

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
          onRepairShard={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-shard-0-btn"]');
    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    const warning = container.querySelector('[data-testid="shard-repair-warning"]');
    expect(warning).not.toBeNull();
    expect(warning?.getAttribute('role')).toBe('alert');
    expect(warning?.textContent).toContain('1/2 복제본 (여전히 저하 상태)');
    expect(container.querySelector('[data-testid="shard-repair-success"]')).toBeNull();
  });

  it('[VF-GM-04-REPAIR-SUCCESS] surfaces success banner when shard is restored to 2/2 healthy', async () => {
    const onRepairMock = vi.fn().mockResolvedValue({
      success: true,
      repairedReplicas: [
        { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
        { nodeId: 'nod_01JABCDEF02', nodeHostname: 'Node-02-WinWork', status: 'healthy' },
      ],
    });

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
          onRepairShard={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-shard-0-btn"]');
    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    const success = container.querySelector('[data-testid="shard-repair-success"]');
    expect(success).not.toBeNull();
    expect(success?.textContent).toContain('샤드 복구 완료 (2/2 정상 복제본 확보)');
  });

  // ---------------------------------------------------------------------------
  // 4. Locality & Capability Aware Execution Planner (ADR-041 & ADR-028)
  // ---------------------------------------------------------------------------
  it('[VF-GM-04-ADR041-LAN-WARNING] displays ADR-041 LAN constraint warning when tensor_pipeline_parallel is selected across multi-node (Catches Mutation 1)', async () => {
    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    // Select Node-02 as well (so 2 nodes are selected)
    const node2Checkbox = container.querySelector<HTMLInputElement>('[data-testid="node-select-nod_01JABCDEF02"]');
    expect(node2Checkbox).not.toBeNull();
    await act(async () => {
      node2Checkbox!.click();
    });

    // Switch mode to tensor_pipeline_parallel
    const modeSelect = container.querySelector<HTMLSelectElement>('[data-testid="execution-mode-select"]');
    expect(modeSelect).not.toBeNull();
    await act(async () => {
      modeSelect!.value = 'tensor_pipeline_parallel';
      modeSelect!.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // Warning banner MUST appear with role="alert"
    const lanWarning = container.querySelector('[data-testid="tensor-parallel-lan-warning"]');
    expect(lanWarning).not.toBeNull();
    expect(lanWarning?.getAttribute('role')).toBe('alert');
    expect(lanWarning?.textContent).toContain('네트워크 제약 경고 (ADR-041)');
    expect(lanWarning?.textContent).toContain('1Gbps 이더넷 환경에서 교차 노드 텐서 병렬 처리는 심각한 통신 대기시간');
  });

  it('[VF-GM-04-ADR041-OBSERVATION-GUARD] strictly prevents observation-only Node-04 from being assigned execution (Catches Mutation 2)', async () => {
    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const node4Row = container.querySelector('[data-testid="node-row-nod_01JABCDEF04"]');
    expect(node4Row).not.toBeNull();

    // Checkbox MUST be disabled
    const checkbox = node4Row?.querySelector<HTMLInputElement>('[data-testid="node-select-nod_01JABCDEF04"]');
    expect(checkbox?.disabled).toBe(true);

    // Ineligible badge MUST be visible with role="alert"
    const badge = node4Row?.querySelector('[data-testid="node-ineligible-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.getAttribute('role')).toBe('alert');
    expect(badge?.textContent).toContain('관측 전용 노드 (연산 할당 불가)');
  });

  it('[VF-GM-04-FEASIBILITY-REJECTION] rejects placement with role="alert" when allocated VRAM is insufficient (Catches Mutation 3)', async () => {
    // Only Node-02 (has 4GB available VRAM), model requires 12 GB
    const clusterWithLowVram: NodeItem[] = [
      clusterNodesFixture[1], // Node-02: 4GB available
    ];

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterWithLowVram}
        />
      );
    });

    // Feasibility status MUST be infeasible
    const infeasibleBadge = container.querySelector('[data-testid="plan-infeasible-badge"]');
    expect(infeasibleBadge).not.toBeNull();
    expect(infeasibleBadge?.getAttribute('role')).toBe('alert');

    const alertBox = container.querySelector('[data-testid="plan-infeasible-alert"]');
    expect(alertBox).not.toBeNull();
    expect(alertBox?.getAttribute('role')).toBe('alert');
    expect(alertBox?.textContent).toContain('가용 VRAM 부족');
  });

  it('[VF-GM-04-FEASIBILITY-SUCCESS] renders feasible badge when allocated VRAM is sufficient', async () => {
    // Node-01 has 16GB available VRAM, model requires 12 GB
    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const feasibleBadge = container.querySelector('[data-testid="plan-feasible-badge"]');
    expect(feasibleBadge).not.toBeNull();
    expect(feasibleBadge?.textContent).toContain('배치 가능 (Feasible)');
    expect(container.querySelector('[data-testid="plan-infeasible-alert"]')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 5. Defensive Honesty: Summary Observation & Absent Repair Adapter
  // ---------------------------------------------------------------------------
  it('[VF-GM-04-SUMMARY-HONESTY] renders honest unknown availability and unobserved shards notice without fabricating shards', async () => {
    // ModelCommitObservation summary without shards
    const summaryCommitObservation = {
      projectId: 'prj_01',
      modelId: 'med-cxr-seg',
      version: '2.1.0',
      manifestHash: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      sourceRunId: 'run_train_01',
      committedAt: '2026-09-21T12:00:00Z',
      commitRecoveryEpoch: '33333333-3333-4333-8333-333333333333',
      format: 'safetensors',
      totalBytes: 1024 * 1024 * 1024,
      shardCount: 1,
      licensePolicy: 'apache-2.0',
      classification: 'internal',
      committed: true,
      currentAvailability: 'unknown',
      requiresExecutionRevalidation: true,
    };

    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={summaryCommitObservation as any}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    // Invariant 1: Availability status MUST indicate unknown and revalidation requirement
    const availStatus = container.querySelector('[data-testid="model-availability-status"]');
    expect(availStatus).not.toBeNull();
    expect(availStatus?.textContent).toContain('알 수 없음 (unknown)');
    expect(availStatus?.textContent).toContain('실행 재검증 필요');
    expect(availStatus?.textContent).not.toContain('관측 완료 · 분산 패브릭 연동');

    // Invariant 2: Unobserved shards notice MUST be displayed with role="status"
    const unobservedNotice = container.querySelector('[data-testid="unobserved-shards-notice"]');
    expect(unobservedNotice).not.toBeNull();
    expect(unobservedNotice?.getAttribute('role')).toBe('status');
    expect(unobservedNotice?.textContent).toContain('개별 샤드 및 복제본 위치 관측 데이터가 없습니다');

    // Invariant 3: Shards matrix section MUST NOT exist (no fabricated shards)
    expect(container.querySelector('[data-testid="shards-matrix-section"]')).toBeNull();
  });

  it('[VF-GM-04-ABSENT-REPAIR-ADAPTER] surfaces honest error alert without simulating repair success when onRepairShard is absent', async () => {
    await act(async () => {
      root.render(
        <ModelStudioView
          projectId="prj_01"
          initialModel={sampleModel}
          clusterNodes={clusterNodesFixture}
          // onRepairShard intentionally omitted
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-shard-0-btn"]');
    expect(repairBtn).not.toBeNull();

    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    // Invariant: without adapter, must show honest error and NOT simulate success
    const repairError = container.querySelector('[data-testid="shard-repair-error"]');
    expect(repairError).not.toBeNull();
    expect(repairError?.getAttribute('role')).toBe('alert');
    expect(repairError?.textContent).toContain('서버 샤드 복구 어댑터(onRepairShard)가 연결되지 않아 복구를 수행할 수 없습니다.');

    expect(container.querySelector('[data-testid="shard-repair-success"]')).toBeNull();
  });
});
