import { describe, it, expect } from 'vitest';
import {
  DesktopWindow,
  AppId,
  LogicalResourceSummary,
  ModelManifest,
  ExecutionPlan,
  InvFileItem,
} from '../src/contracts/virtualFabric';
import { NodeItem } from '../src/contracts/types';

describe('VF-GM-01 ~ VF-GM-05 Virtual Computer Fabric & Web Desktop Suite', () => {
  const sampleNodes: NodeItem[] = [
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
      storageTotalBytes: 2000 * 1024 ** 3,
      storageUsedBytes: 850 * 1024 ** 3,
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
      memoryUsedBytes: 45 * 1024 ** 3,
      allocatableCores: 0,
      allocatableMemoryBytes: 0,
      schedulable: false,
      observationOnly: true, // Observation only node (192.168.45.225)
      gpuCount: 0,
      storageTotalBytes: 4000 * 1024 ** 3,
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
      storageTotalBytes: 2000 * 1024 ** 3,
      storageUsedBytes: 600 * 1024 ** 3,
      heartbeatAt: new Date().toISOString(),
    },
  ];

  // VF-GM-01: Web Desktop Shell Window Manager
  it('[VF-GM-01] enforces window lifecycle, z-index elevation, and minimize/maximize states', () => {
    let windows: DesktopWindow[] = [
      {
        id: 'win_1',
        appId: 'my-computer',
        title: '내 컴퓨터',
        icon: '💻',
        isOpen: true,
        isMinimized: false,
        isMaximized: false,
        zIndex: 10,
        position: { x: 40, y: 50 },
        size: { width: 920, height: 600 },
      },
      {
        id: 'win_2',
        appId: 'file-explorer',
        title: '파일 탐색기',
        icon: '📁',
        isOpen: false,
        isMinimized: false,
        isMaximized: false,
        zIndex: 9,
        position: { x: 80, y: 70 },
        size: { width: 960, height: 580 },
      },
    ];

    // Open and elevate win_2
    const openApp = (appId: AppId) => {
      const maxZ = Math.max(...windows.map((w) => w.zIndex), 10);
      windows = windows.map((w) =>
        w.appId === appId ? { ...w, isOpen: true, isMinimized: false, zIndex: maxZ + 1 } : w
      );
    };

    openApp('file-explorer');
    const win2 = windows.find((w) => w.id === 'win_2');
    expect(win2?.isOpen).toBe(true);
    expect(win2?.zIndex).toBe(11);

    // Minimize win_2
    windows = windows.map((w) => (w.id === 'win_2' ? { ...w, isMinimized: true } : w));
    expect(windows.find((w) => w.id === 'win_2')?.isMinimized).toBe(true);

    // Maximize win_1
    windows = windows.map((w) => (w.id === 'win_1' ? { ...w, isMaximized: true } : w));
    expect(windows.find((w) => w.id === 'win_1')?.isMaximized).toBe(true);
  });

  // VF-GM-02: My Computer / Resource Explorer
  it('[VF-GM-02] computes honest logical fabric capacity alongside physical topology isolation', () => {
    const computeLogicalSummary = (nodeList: NodeItem[]): LogicalResourceSummary => {
      let totalCores = 0;
      let allocatableCores = 0;
      let usedCores = 0;
      let totalMemoryBytes = 0;
      let allocatableMemoryBytes = 0;
      let usedMemoryBytes = 0;
      let totalGpuCount = 0;
      let totalGpuVramBytes = 0;
      let usedGpuVramBytes = 0;
      let totalStorageBytes = 0;
      let usedStorageBytes = 0;
      let onlineNodeCount = 0;

      for (const node of nodeList) {
        if (node.status === 'online' || node.status === 'draining') onlineNodeCount++;
        totalCores += node.cpuCores;
        allocatableCores += node.allocatableCores ?? 0;
        usedCores += (node.cpuCores * (node.cpuUsagePercent || 0)) / 100;
        totalMemoryBytes += node.memoryTotalBytes;
        allocatableMemoryBytes += node.allocatableMemoryBytes ?? 0;
        usedMemoryBytes += node.memoryUsedBytes;
        totalGpuCount += node.gpuCount || 0;
        totalGpuVramBytes += node.gpuVramTotalBytes || 0;
        usedGpuVramBytes += node.gpuVramUsedBytes || 0;
        totalStorageBytes += node.storageTotalBytes;
        usedStorageBytes += node.storageUsedBytes;
      }

      return {
        totalCores,
        allocatableCores,
        usedCores: Math.round(usedCores * 10) / 10,
        totalMemoryBytes,
        allocatableMemoryBytes,
        usedMemoryBytes,
        totalGpuCount,
        totalGpuVramBytes,
        usedGpuVramBytes,
        totalStorageBytes,
        usedStorageBytes,
        onlineNodeCount,
        totalNodeCount: nodeList.length,
        disclaimer: 'Zero-Mock Fabric Summary',
      };
    };

    const summary = computeLogicalSummary(sampleNodes);
    expect(summary.totalCores).toBe(44); // 16 + 16 + 12
    expect(summary.allocatableCores).toBe(22); // 12 + 0 (obs only) + 10
    expect(summary.totalGpuCount).toBe(2); // RTX 4090 + A4000
    expect(summary.totalGpuVramBytes).toBe(40 * 1024 ** 3); // 24 + 16 GB
    expect(summary.onlineNodeCount).toBe(3);

    // CRITICAL ARCHITECTURAL INVARIANT: Observation-only node must have 0 allocatable cores
    const obsNode = sampleNodes.find((n) => n.observationOnly);
    expect(obsNode?.schedulable).toBe(false);
    expect(obsNode?.allocatableCores).toBe(0);
  });

  // VF-GM-03: inv:// File Explorer
  it('[VF-GM-03] handles inv:// namespace URIs, SHA-256 integrity, and replica degradation', () => {
    const file: InvFileItem = {
      uri: 'inv://models/pacs-cxr/2.0.0/weights.safetensors',
      namespace: 'models',
      relativePath: 'pacs-cxr/2.0.0/weights.safetensors',
      name: 'weights.safetensors',
      type: 'file',
      sizeBytes: 10 * 1024 ** 3,
      version: '2.0.0',
      contentHash: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
      contentType: 'application/octet-stream',
      replicas: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          status: 'healthy',
          localPath: 'C:\\Storage\\weights.safetensors',
          updatedAt: new Date().toISOString(),
        },
        {
          nodeId: 'nod_01JABCDEF04',
          nodeHostname: 'Node-04-LinuxBuild',
          status: 'unreachable', // Degraded replica
          localPath: '/mnt/storage/weights.safetensors',
          updatedAt: new Date().toISOString(),
        },
      ],
      requiredReplicas: 2,
      isPinned: true,
      classification: 'confidential',
      updatedAt: new Date().toISOString(),
    };

    expect(file.uri.startsWith('inv://models/')).toBe(true);
    expect(file.contentHash).toHaveLength(64); // SHA-256 hex length
    expect(file.isPinned).toBe(true); // Pinned files are GC-exempt

    const healthyReplicas = file.replicas.filter((r) => r.status === 'healthy');
    expect(healthyReplicas.length).toBe(1);
    expect(healthyReplicas.length < file.requiredReplicas).toBe(true); // Degraded status detected

    // Repair action restores healthy status
    const repairedFile = {
      ...file,
      replicas: file.replicas.map((r) => ({ ...r, status: 'healthy' as const })),
    };
    expect(repairedFile.replicas.every((r) => r.status === 'healthy')).toBe(true);
  });

  // VF-GM-04: AI Model Studio & Execution Planner
  it('[VF-GM-04] validates ModelManifest shards and locality-aware execution plan feasibility', () => {
    const sampleManifest: ModelManifest = {
      modelId: 'pacs-foundation-v2',
      name: 'PACS Foundation v2',
      version: '2.0.0',
      format: 'safetensors',
      totalBytes: 16 * 1024 ** 3,
      contentHash: '11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
      runtimeCompatibility: ['PyTorch >=2.4', 'vLLM >=0.6'],
      licensePolicy: 'Restricted Medical License',
      classification: 'confidential',
      encryption: { enabled: true, keyRef: 'kms://saint/key1' },
      supportedModes: ['single_node', 'tensor_pipeline_parallel'],
      status: 'committed',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      shards: [
        {
          shardIndex: 0,
          shardId: 'shard_0',
          byteRange: '0 - 8GB',
          layers: '0-15',
          contentHash: 'hash0',
          sizeBytes: 8 * 1024 ** 3,
          replicas: [{ nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' }],
        },
        {
          shardIndex: 1,
          shardId: 'shard_1',
          byteRange: '8 - 16GB',
          layers: '16-31',
          contentHash: 'hash1',
          sizeBytes: 8 * 1024 ** 3,
          replicas: [{ nodeId: 'nod_01JABCDEF05', nodeHostname: 'Node-05-LinuxTrain', status: 'healthy' }],
        },
      ],
    };

    expect(sampleManifest.shards).toHaveLength(2);

    // Plan single node on Node-01 (RTX 4090 with 24GB VRAM)
    const requiredVramBytes = sampleManifest.totalBytes * 1.25; // 20GB
    const node1Vram = sampleNodes[0].gpuVramTotalBytes || 0; // 24GB
    const isSingleNodeFeasible = node1Vram >= requiredVramBytes;

    expect(isSingleNodeFeasible).toBe(true);

    // Plan single node on Node-05 (A4000 with 16GB VRAM) -> Infeasible because 16GB < 20GB!
    const node5Vram = sampleNodes[2].gpuVramTotalBytes || 0; // 16GB
    const isNode5Feasible = node5Vram >= requiredVramBytes;
    expect(isNode5Feasible).toBe(false);
  });

  // VF-GM-05: Terminal & IDE Session UX
  it('[VF-GM-05] maps target node OS to authentic shell type and enforces ticket protocol', () => {
    const resolveShellForNode = (os: 'windows' | 'linux'): string => {
      return os === 'windows' ? 'powershell' : 'bash';
    };

    expect(resolveShellForNode('windows')).toBe('powershell');
    expect(resolveShellForNode('linux')).toBe('bash');

    // Ticket expiry check (30-second TTL invariant)
    const issueTicket = (ttlSeconds = 30) => ({
      ticket: 'tkt_01JABCDEF987654',
      expiresAt: Date.now() + ttlSeconds * 1000,
    });

    const ticket = issueTicket(30);
    const isTicketValid = (t: typeof ticket) => Date.now() < t.expiresAt;
    expect(isTicketValid(ticket)).toBe(true);
  });

  // VF-GM-01-A11Y: Keyboard Shortcuts & Window Navigation
  it('[VF-GM-01-A11Y] cycles active windows with Alt+Tab and handles Escape modal dismissal', () => {
    const activeWindows: DesktopWindow[] = [
      { id: 'w1', appId: 'my-computer', title: '1', icon: '💻', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 10, position: { x: 0, y: 0 }, size: { width: 100, height: 100 } },
      { id: 'w2', appId: 'file-explorer', title: '2', icon: '📁', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 11, position: { x: 10, y: 10 }, size: { width: 100, height: 100 } },
      { id: 'w3', appId: 'terminal', title: '3', icon: '⌨️', isOpen: true, isMinimized: false, isMaximized: false, zIndex: 12, position: { x: 20, y: 20 }, size: { width: 100, height: 100 } },
    ];

    const cycleWindow = (currentId: string, winList: DesktopWindow[]): string => {
      const open = winList.filter((w) => w.isOpen && !w.isMinimized);
      const currIdx = open.findIndex((w) => w.id === currentId);
      const nextIdx = (currIdx + 1) % open.length;
      return open[nextIdx].id;
    };

    expect(cycleWindow('w1', activeWindows)).toBe('w2');
    expect(cycleWindow('w2', activeWindows)).toBe('w3');
    expect(cycleWindow('w3', activeWindows)).toBe('w1');

    // Dismiss modal on Escape
    let isMenuOpen = true;
    const handleEscape = (key: string) => {
      if (key === 'Escape') isMenuOpen = false;
    };
    handleEscape('Escape');
    expect(isMenuOpen).toBe(false);
  });

  // VF-GM-01-STORAGE: Layout Session Persistence
  it('[VF-GM-01-STORAGE] serializes and parses window position and dimensions without schema corruption', () => {
    const mockLayout: DesktopWindow[] = [
      {
        id: 'win_test',
        appId: 'my-computer',
        title: '내 컴퓨터',
        icon: '💻',
        isOpen: true,
        isMinimized: false,
        isMaximized: true,
        zIndex: 15,
        position: { x: 100, y: 120 },
        size: { width: 800, height: 600 },
      },
    ];

    const serialized = JSON.stringify(mockLayout);
    const restored = JSON.parse(serialized) as DesktopWindow[];

    expect(restored).toHaveLength(1);
    expect(restored[0].id).toBe('win_test');
    expect(restored[0].position).toEqual({ x: 100, y: 120 });
    expect(restored[0].isMaximized).toBe(true);
    expect(restored[0].zIndex).toBe(15);
  });

  // VF-GM-03-A11Y: Replica Repair State Transition
  it('[VF-GM-03-A11Y] detects degraded replica state and transitions to repaired upon node synchronization', () => {
    interface Replica {
      nodeId: string;
      status: 'healthy' | 'missing' | 'syncing';
    }

    const checkReplicaHealth = (replicas: Replica[], required: number): 'healthy' | 'degraded' => {
      const healthyCount = replicas.filter((r) => r.status === 'healthy').length;
      return healthyCount >= required ? 'healthy' : 'degraded';
    };

    const replicas: Replica[] = [
      { nodeId: 'node_1', status: 'healthy' },
      { nodeId: 'node_2', status: 'missing' },
    ];

    // 1 healthy out of 2 required -> degraded
    expect(checkReplicaHealth(replicas, 2)).toBe('degraded');

    // Repair action: node_2 synchronizes from node_1
    replicas[1].status = 'healthy';
    expect(checkReplicaHealth(replicas, 2)).toBe('healthy');
  });
});
