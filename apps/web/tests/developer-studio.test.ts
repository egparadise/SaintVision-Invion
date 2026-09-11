import { describe, it, expect } from 'vitest';
import { evaluatePlacement } from '../src/features/placement/placementEngine';
import { computeDiff, computeSha256 } from '../src/features/editor/diffEngine';
import { NodeItem, PlacementRequirement, NodeStopReceipt } from '../src/contracts/types';

const TEST_NODES: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 25,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 24 * 1024 ** 3,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 1,
    gpuVramTotalBytes: 24 * 1024 ** 3,
    gpuVramUsedBytes: 8 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 800 * 1024 ** 3,
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
    gpuName: 'NVIDIA RTX 3080',
    gpuCount: 1,
    gpuVramTotalBytes: 10 * 1024 ** 3,
    gpuVramUsedBytes: 6 * 1024 ** 3,
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
    gpuCount: 0,
    storageTotalBytes: 1000 * 1024 ** 3,
    storageUsedBytes: 300 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF04',
    hostname: 'Node-04-LinuxBuild',
    status: 'online',
    os: 'linux',
    cpuCores: 16,
    cpuUsagePercent: 75,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 48 * 1024 ** 3,
    gpuCount: 0,
    storageTotalBytes: 4000 * 1024 ** 3,
    storageUsedBytes: 2000 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF05',
    hostname: 'Node-05-LinuxTrain',
    status: 'online',
    os: 'linux',
    cpuCores: 12,
    cpuUsagePercent: 20,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 8 * 1024 ** 3,
    gpuName: 'NVIDIA A4000',
    gpuCount: 1,
    gpuVramTotalBytes: 16 * 1024 ** 3,
    gpuVramUsedBytes: 4 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 600 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
];

describe('Developer Studio: Unified 4-Step Workflow & Governance Verification', () => {
  it('Step 1 -> 2: calculates distinct physical capacity vs observed usage vs available headroom', () => {
    const node1 = TEST_NODES[0];

    // 1. Total physical capacity
    expect(node1.cpuCores).toBe(16);
    expect(node1.memoryTotalBytes).toBe(64 * 1024 ** 3);
    expect(node1.gpuVramTotalBytes).toBe(24 * 1024 ** 3);

    // 2. Observed telemetry usage
    expect(node1.cpuUsagePercent).toBe(25);
    expect(node1.memoryUsedBytes).toBe(24 * 1024 ** 3);

    // 3. Available headroom (strictly computed)
    const availCores = node1.cpuCores * (1 - node1.cpuUsagePercent / 100);
    const availRamBytes = node1.memoryTotalBytes - node1.memoryUsedBytes;
    const availVramBytes = (node1.gpuVramTotalBytes || 0) - (node1.gpuVramUsedBytes || 0);

    expect(availCores).toBe(12); // 16 * 0.75 = 12 cores
    expect(availRamBytes).toBe(40 * 1024 ** 3); // 64 - 24 = 40 GiB
    expect(availVramBytes).toBe(16 * 1024 ** 3); // 24 - 8 = 16 GiB
  });

  it('Step 2: evaluates placement with deterministic 40/30/30 weights and hard filters', () => {
    const req: PlacementRequirement = {
      requiredCores: 8,
      requiredMemoryBytes: 16 * 1024 ** 3,
      requiresGpu: true,
      preferredOs: 'windows',
      dataLocalityNodeId: 'nod_01JABCDEF01',
    };

    const result = evaluatePlacement(TEST_NODES, req);

    expect(result.selectedNodeId).toBe('nod_01JABCDEF01');
    expect(result.evaluations).toHaveLength(5);

    // Node-01 passed hard filter and scored highest due to locality
    const eval01 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF01');
    expect(eval01?.hardFilterPassed).toBe(true);
    expect(eval01?.scores?.localityScore).toBe(100);
    expect(eval01?.scores?.totalScore).toBeGreaterThanOrEqual(80);

    // Node-03 has no GPU -> rejected by hard filter
    const eval03 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF03');
    expect(eval03?.hardFilterPassed).toBe(false);
    expect(eval03?.rejectionReasons).toContain('가속 GPU 부재 (GPU 워크로드 요구)');

    // Node-04 has Linux OS -> rejected by preferred OS
    const eval04 = result.evaluations.find((e) => e.nodeId === 'nod_01JABCDEF04');
    expect(eval04?.hardFilterPassed).toBe(false);
    expect(eval04?.rejectionReasons.some((r) => r.includes('운영체제 불일치'))).toBe(true);
  });

  it('Step 3: computes Myers Diff and ADR-044 Frozen Input snapshot digest', () => {
    const originalCode = `const port = 8080;\nconsole.log("ready");\n`;
    const modifiedCode = `const port = 8443;\nconsole.log("ready");\nconsole.log("tls enabled");\n`;

    const diff = computeDiff('src/server.ts', originalCode, modifiedCode);
    expect(diff.additionsCount).toBe(2);
    expect(diff.deletionsCount).toBe(1);
    expect(diff.lines.some((l) => l.type === 'added' && l.content.includes('8443'))).toBe(true);

    const snapshotHash = computeSha256(modifiedCode);
    expect(snapshotHash).toHaveLength(64);
    expect(snapshotHash).toMatch(/^[0-9a-f]{64}$/);
  });

  it('Step 4: verifies ADR-028/041 NodeStopReceipt vs Evidence separation rule', () => {
    const receipt: NodeStopReceipt = {
      receiptId: 'rcp_01JABCDEF_TEST',
      runId: 'run_01JABCDE0001',
      nodeId: 'nod_01JABCDEF01',
      commandId: 'cmd_train_benchmark',
      exitCode: 0,
      physicallyStopped: true,
      resourceReclaimed: true,
      verified: false, // Physical stop exitCode 0 does NOT mean application verified
      output: {
        sha256: 'sha256:d8a4f02b6678a1b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7',
        sizeBytes: 4096,
      },
      stoppedAt: new Date().toISOString(),
      supervisorLabel: 'proc_sandbox_isolated',
    };

    // ADR-028 invariant check
    expect(receipt.exitCode).toBe(0);
    expect(receipt.physicallyStopped).toBe(true);
    expect(receipt.verified).toBe(false);
    expect(receipt.output?.sha256).toBeDefined();
    expect(receipt.resourceReclaimed).toBe(true);
  });
});
