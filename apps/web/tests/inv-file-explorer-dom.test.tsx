// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { InvFileExplorer, calculateSha256 } from '../src/features/desktop/InvFileExplorer';
import * as wsEditApi from '../src/shared/api/workspaceEditObservation';
import { InvFileItem, InvReplicaLocation } from '../src/contracts/virtualFabric';
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
    observationOnly: true, // Observation only node
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

const sampleDegradedFile: InvFileItem = {
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
      updatedAt: '2026-09-21T00:00:00Z',
    },
    {
      nodeId: 'nod_01JABCDEF04',
      nodeHostname: 'Node-04-LinuxBuild',
      status: 'unreachable', // Degraded replica
      localPath: '/mnt/storage/weights.safetensors',
      updatedAt: '2026-09-21T00:00:00Z',
    },
  ],
  requiredReplicas: 2,
  isPinned: true,
  classification: 'confidential',
  updatedAt: '2026-09-21T00:00:00Z',
};

const sampleDatasetFile: InvFileItem = {
  uri: 'inv://datasets/chest-xray-14/1.0.0/manifest.json',
  namespace: 'datasets',
  relativePath: 'chest-xray-14/1.0.0/manifest.json',
  name: 'manifest.json',
  type: 'file',
  sizeBytes: 50 * 1024 ** 2,
  version: '1.0.0',
  contentHash: '11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
  contentType: 'application/json',
  replicas: [
    {
      nodeId: 'nod_01JABCDEF01',
      nodeHostname: 'Node-01-WinMain',
      status: 'healthy',
      localPath: 'C:\\Storage\\manifest.json',
      updatedAt: '2026-09-21T00:00:00Z',
    },
    {
      nodeId: 'nod_01JABCDEF02',
      nodeHostname: 'Node-02-WinWork',
      status: 'healthy',
      localPath: 'C:\\Storage\\manifest.json',
      updatedAt: '2026-09-21T00:00:00Z',
    },
  ],
  requiredReplicas: 2,
  isPinned: false,
  classification: 'internal',
  updatedAt: '2026-09-21T00:00:00Z',
};

describe('VF-GM-03: inv:// File Explorer DOM Harness & Defensive Guarantees', () => {
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
  // 1. inv:// Namespace Exploration & Address Bar Navigation
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-EXPLORE] handles inv:// namespace navigation, address bar input, and empty state', async () => {
    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile, sampleDatasetFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const addressBar = container.querySelector<HTMLInputElement>('[data-testid="inv-address-bar"]');
    expect(addressBar).not.toBeNull();
    expect(addressBar?.value).toBe('inv://models');

    // Models file visible
    expect(container.textContent).toContain('weights.safetensors');

    // Click datasets namespace quick-button
    const navDatasets = container.querySelector<HTMLButtonElement>('[data-testid="nav-namespace-datasets"]');
    expect(navDatasets).not.toBeNull();
    await act(async () => {
      navDatasets!.click();
    });

    expect(addressBar?.value).toBe('inv://datasets/chest-xray-14/1.0.0/manifest.json');
    expect(container.textContent).toContain('manifest.json');

    // Click workspaces (which has 0 files)
    const navWorkspaces = container.querySelector<HTMLButtonElement>('[data-testid="nav-namespace-workspaces"]');
    await act(async () => {
      navWorkspaces!.click();
    });

    const emptyState = container.querySelector('[data-testid="inv-empty-state"]');
    expect(emptyState).not.toBeNull();
    expect(emptyState?.textContent).toContain('등록된 파일이 없습니다.');
  });

  // ---------------------------------------------------------------------------
  // 2. Requirement 1: Actual SHA-256 Hash Comparison (Tampered vs Verified)
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-HASH-COMPARE] executes genuine hash comparison and surfaces TAMPERED alert on mismatch (Catches Mutation 1)', async () => {
    // Mock integrity verification returning a TAMPERED hash that does NOT match expected contentHash
    const onVerifyMock = vi.fn().mockResolvedValue({
      calculatedHash: '9999999999999999999999999999999999999999999999999999999999999999',
      matches: false,
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onVerifyIntegrity={onVerifyMock}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    expect(verifyBtn).not.toBeNull();

    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    expect(onVerifyMock).toHaveBeenCalledWith(sampleDegradedFile);

    // Tri-state badge MUST indicate MISMATCH / TAMPERED
    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('검증 실패 (해시 불일치 / TAMPERED)');
    expect(badge?.textContent).not.toContain('검증 통과 (VERIFIED)');

    // Explicit mismatch banner MUST appear with role="alert"
    const mismatchBanner = container.querySelector('[data-testid="integrity-mismatch-banner"]');
    expect(mismatchBanner).not.toBeNull();
    expect(mismatchBanner?.getAttribute('role')).toBe('alert');
    expect(mismatchBanner?.textContent).toContain('무결성 검증 실패: 계산된 해시가 카탈로그 체크섬과 불일치합니다 (변조 감지)');

    // Both expected and calculated hashes must be rendered for audit
    expect(container.querySelector('[data-testid="expected-hash"]')?.textContent).toBe(sampleDegradedFile.contentHash);
    expect(container.querySelector('[data-testid="calculated-hash"]')?.textContent).toBe(
      '9999999999999999999999999999999999999999999999999999999999999999'
    );
  });

  it('[VF-GM-03-HASH-COMPARE] displays VERIFIED badge and suppresses mismatch banner when hashes strictly match', async () => {
    // Mock integrity verification returning an exact matching hash
    const onVerifyMock = vi.fn().mockResolvedValue({
      calculatedHash: sampleDegradedFile.contentHash,
      matches: true,
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onVerifyIntegrity={onVerifyMock}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).toContain('검증 통과 (VERIFIED)');
    expect(badge?.textContent).not.toContain('검증 실패');

    // Mismatch banner MUST NOT exist
    expect(container.querySelector('[data-testid="integrity-mismatch-banner"]')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 3. Requirement 2: Strict Tri-State Distinction (UNVERIFIED vs VERIFIED vs MISMATCH)
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-TRISTATE] strictly treats missing catalog checksum as UNVERIFIED, never VERIFIED (Catches Mutation 2)', async () => {
    const fileWithoutChecksum: InvFileItem = {
      ...sampleDegradedFile,
      contentHash: '', // Missing catalog hash
    };

    const onVerifyMock = vi.fn();

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[fileWithoutChecksum]}
          clusterNodes={clusterNodesFixture}
          onVerifyIntegrity={onVerifyMock}
        />
      );
    });

    // Initial state is unverified
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toBe('미검증 (UNVERIFIED)');

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    // Verification must NOT be invoked and state must STAY UNVERIFIED
    expect(onVerifyMock).not.toHaveBeenCalled();
    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).toBe('미검증 (UNVERIFIED)');
    expect(badge?.textContent).not.toContain('검증 통과 (VERIFIED)');
  });

  // ---------------------------------------------------------------------------
  // 4. Requirement 3: Fresh Failure Masking Elimination (No Stale "VERIFIED" Retention)
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-NO-STALE-MASKING] immediately wipes prior VERIFIED state when a fresh re-verification fails (Catches Mutation 3)', async () => {
    let callCount = 0;
    const onVerifyMock = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        // First verification succeeds
        return { calculatedHash: sampleDegradedFile.contentHash, matches: true };
      }
      // Fresh second verification fails (e.g. network partition or node offline)
      throw new Error('503 Service Unavailable: Verification daemon offline');
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onVerifyIntegrity={onVerifyMock}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');

    // 1st verification -> PASS
    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toBe('검증 통과 (VERIFIED)');

    // 2nd re-verification -> FAILS with network error
    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    // Stale VERIFIED state MUST BE WIPED OUT
    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).not.toBe('검증 통과 (VERIFIED)');
    expect(badge?.textContent).toBe('검증 오류 (ERROR)');

    // Fresh error alert MUST be visible
    const actionError = container.querySelector('[data-testid="integrity-action-error"]');
    expect(actionError).not.toBeNull();
    expect(actionError?.getAttribute('role')).toBe('alert');
    expect(actionError?.textContent).toContain('503 Service Unavailable: Verification daemon offline');
  });

  // ---------------------------------------------------------------------------
  // 5. Requirement 4: Honest Replica Degradation & Repair Guard
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-REPLICA-DEGRADED] accurately surfaces replica degradation badge when healthy < required', async () => {
    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    // 1 healthy, 2 required -> Degraded badge must be present with role="alert"
    const degradedBadge = container.querySelector('[data-testid="replica-degradation-badge"]');
    expect(degradedBadge).not.toBeNull();
    expect(degradedBadge?.getAttribute('role')).toBe('alert');
    expect(degradedBadge?.textContent).toContain('1/2 Replicas Available (Degraded)');
    expect(container.querySelector('[data-testid="replica-healthy-badge"]')).toBeNull();
  });

  it('[VF-GM-03-REPAIR-GUARD] disables repair button and displays warning alert when 0 surviving nodes exist', async () => {
    // Only Node-01 (which already hosts the replica) and Node-04 (observation-only) exist in cluster
    const clusterWithNoSurvivingNodes: NodeItem[] = [
      clusterNodesFixture[0], // Node-01: already hosts healthy replica
      clusterNodesFixture[3], // Node-04: observationOnly: true, schedulable: false
    ];

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterWithNoSurvivingNodes}
        />
      );
    });

    // Zero surviving eligible nodes -> Notice banner MUST be rendered with role="alert"
    const noSurvivingNotice = container.querySelector('[data-testid="no-surviving-nodes-notice"]');
    expect(noSurvivingNotice).not.toBeNull();
    expect(noSurvivingNotice?.getAttribute('role')).toBe('alert');
    expect(noSurvivingNotice?.textContent).toContain('생존 노드 없음 (복구 불가');

    // Repair button MUST be disabled
    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-replicas-btn"]');
    expect(repairBtn).toBeNull(); // Replaced by disabled banner or not clickable
  });

  it('[VF-GM-03-REPAIR-FAIL] surfaces honest error alert when repair request fails (Catches Mutation 4)', async () => {
    const onRepairMock = vi.fn().mockResolvedValue({
      success: false,
      repairedReplicas: sampleDegradedFile.replicas,
      message: '507 Insufficient Storage on Target Node-02',
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onRepairReplicas={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-replicas-btn"]');
    expect(repairBtn).not.toBeNull();

    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    expect(onRepairMock).toHaveBeenCalled();

    // Honest error banner with role="alert" must be visible
    const repairError = container.querySelector('[data-testid="repair-action-error"]');
    expect(repairError).not.toBeNull();
    expect(repairError?.getAttribute('role')).toBe('alert');
    expect(repairError?.textContent).toContain('507 Insufficient Storage on Target Node-02');

    // False success banner MUST NOT exist
    expect(container.querySelector('[data-testid="repair-action-success"]')).toBeNull();
    expect(container.textContent).not.toContain('복제본 복구 완료');
  });

  it('[VF-GM-03-REPAIR-PARTIAL] accurately reports partial restoration warning when replicas are still degraded (Catches Mutation 4b)', async () => {
    // Repair succeeded partially, but only returned 1 healthy replica (e.g. 1/2, still degraded)
    const onRepairMock = vi.fn().mockResolvedValue({
      success: true,
      repairedReplicas: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          status: 'healthy' as const,
          localPath: 'C:\\Storage\\weights.safetensors',
          updatedAt: '2026-09-21T00:00:00Z',
        },
        {
          nodeId: 'nod_01JABCDEF02',
          nodeHostname: 'Node-02-WinWork',
          status: 'stale' as const, // Still stale / degraded
          localPath: 'C:\\Storage\\weights.safetensors',
          updatedAt: '2026-09-21T00:00:00Z',
        },
      ],
      message: 'Partial sync completed',
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onRepairReplicas={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-replicas-btn"]');
    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    // Warning banner for still degraded state MUST be shown with role="alert"
    const warning = container.querySelector('[data-testid="repair-action-warning"]');
    expect(warning).not.toBeNull();
    expect(warning?.getAttribute('role')).toBe('alert');
    expect(warning?.textContent).toContain('1/2 복제본 (여전히 저하 상태)');

    // False full success MUST NOT be displayed
    expect(container.querySelector('[data-testid="repair-action-success"]')).toBeNull();
  });

  it('[VF-GM-03-REPAIR-SUCCESS] displays success banner and restores healthy badge when all required replicas become healthy', async () => {
    const onRepairMock = vi.fn().mockResolvedValue({
      success: true,
      repairedReplicas: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          status: 'healthy' as const,
          localPath: 'C:\\Storage\\weights.safetensors',
          updatedAt: '2026-09-21T00:00:00Z',
        },
        {
          nodeId: 'nod_01JABCDEF02',
          nodeHostname: 'Node-02-WinWork',
          status: 'healthy' as const, // Successfully restored to healthy!
          localPath: 'C:\\Storage\\weights.safetensors',
          updatedAt: '2026-09-21T00:00:00Z',
        },
      ],
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          onRepairReplicas={onRepairMock}
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-replicas-btn"]');
    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    // Success banner MUST appear
    const successBanner = container.querySelector('[data-testid="repair-action-success"]');
    expect(successBanner).not.toBeNull();
    expect(successBanner?.textContent).toContain('복제본 복구 완료 (2/2 정상)');

    // Healthy badge MUST appear and degradation badge MUST be gone
    expect(container.querySelector('[data-testid="replica-healthy-badge"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="replica-degradation-badge"]')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 6. Byte Source / Verifier Absence & Actual Byte Hash Verification
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-ABSENT-BYTES-REFUSAL] marks status unverified and displays honest refusal when file content and verifier adapter are both absent', async () => {
    // sampleDegradedFile has contentHash but NO content bytes
    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          // onVerifyIntegrity intentionally omitted
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    expect(verifyBtn).not.toBeNull();

    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    // Invariant: Without bytes or adapter, status MUST remain unverified, NEVER verified
    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).toBe('미검증 (UNVERIFIED)');

    const actionError = container.querySelector('[data-testid="integrity-action-error"]');
    expect(actionError).not.toBeNull();
    expect(actionError?.getAttribute('role')).toBe('alert');
    expect(actionError?.textContent).toContain('파일 본문 바이트(content) 또는 검증 어댑터가 부재하여 무결성을 검증할 수 없습니다.');
  });

  it('[VF-GM-03-BYTE-VERIFY-MATCH] computes genuine SHA-256 over file content bytes without onVerifyIntegrity adapter', async () => {
    const rawContent = 'INV-FABRIC-REAL-BYTES-TEST';
    const computedHash = await calculateSha256(rawContent);

    const fileWithContent: InvFileItem = {
      ...sampleDegradedFile,
      content: rawContent,
      contentHash: computedHash,
      source: 'kernel-checkout',
    };

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[fileWithContent]}
          clusterNodes={clusterNodesFixture}
          // onVerifyIntegrity intentionally omitted to force client-side byte hash computation
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).toContain('검증 통과 (VERIFIED)');
    expect(container.querySelector('[data-testid="calculated-hash"]')?.textContent).toBe(computedHash);

    const fileSourceBadge = container.querySelector('[data-testid="file-source-badge"]');
    expect(fileSourceBadge?.textContent).toContain('커널 체크아웃 (WorkspaceEditView 실 바이트)');
  });

  it('[VF-GM-03-DEMO-FILE-UNVERIFIED] strictly refuses verification for demo/unconnected files and retains unverified status', async () => {
    const rawContent = 'DEMO-DATA-NOT-CONNECTED';
    const computedHash = await calculateSha256(rawContent);

    const demoFile: InvFileItem = {
      ...sampleDegradedFile,
      content: rawContent,
      contentHash: computedHash,
      source: 'demo',
    };

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[demoFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    const badge = container.querySelector('[data-testid="integrity-badge"]');
    expect(badge?.textContent).toBe('미검증 (UNVERIFIED)');
    expect(badge?.textContent).not.toContain('검증 통과 (VERIFIED)');

    const actionError = container.querySelector('[data-testid="integrity-action-error"]');
    expect(actionError).not.toBeNull();
    expect(actionError?.getAttribute('role')).toBe('alert');
    expect(actionError?.textContent).toContain(
      '데모/미연결 데이터: 실제 저장소 바이트(WorkspaceEditView)가 연결되지 않아 무결성을 검증할 수 없습니다. (미검증 유지)'
    );

    const fileSourceBadge = container.querySelector('[data-testid="file-source-badge"]');
    expect(fileSourceBadge?.textContent).toContain('로컬/데모 (실제 저장소 미연결 · 무결성 검증 유보)');
  });

  it('[VF-GM-03-ABSENT-REPAIR-ADAPTER] displays honest error alert without synthesizing repaired replicas when onRepairReplicas is absent', async () => {
    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[sampleDegradedFile]}
          clusterNodes={clusterNodesFixture}
          // onRepairReplicas intentionally omitted
        />
      );
    });

    const repairBtn = container.querySelector<HTMLButtonElement>('[data-testid="repair-replicas-btn"]');
    expect(repairBtn).not.toBeNull();

    await act(async () => {
      repairBtn!.click();
      await Promise.resolve();
    });

    // Invariant: without adapter, must show honest error and NOT synthesize fake healthy replicas
    const repairError = container.querySelector('[data-testid="repair-action-error"]');
    expect(repairError).not.toBeNull();
    expect(repairError?.getAttribute('role')).toBe('alert');
    expect(repairError?.textContent).toContain('서버에 온디맨드 복구 실행 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)');

    expect(container.querySelector('[data-testid="repair-action-success"]')).toBeNull();
    expect(container.querySelector('[data-testid="replica-degradation-badge"]')).not.toBeNull();
  });

  it('[VF-GM-03-WEBCRYPTO-ABSENT] throws explicit error when WebCrypto API is unavailable rather than returning 64 zeroes', async () => {
    const originalCrypto = globalThis.crypto;
    try {
      // Mock missing crypto.subtle
      Object.defineProperty(globalThis, 'crypto', {
        value: {},
        configurable: true,
      });

      await expect(calculateSha256('test')).rejects.toThrow('WebCrypto API가 지원되지 않아 무결성을 검증할 수 없습니다.');
    } finally {
      Object.defineProperty(globalThis, 'crypto', {
        value: originalCrypto,
        configurable: true,
      });
    }
  });

  // ---------------------------------------------------------------------------
  // 8. WorkspaceEditView Genuine Integrity Verification & Mutation Proofs
  // ---------------------------------------------------------------------------
  it('[VF-GM-03-BEFORE-AFTER-VERIFY] demonstrates Before (unconnected demo file remains unverified) vs After (genuine kernel checkout byte hash matches and is marked VERIFIED)', async () => {
    // 1. BEFORE: Unconnected demo file
    const demoContent = "print('demo-unconnected')\n";
    const demoHash = await calculateSha256(demoContent);
    const demoFile: InvFileItem = {
      ...sampleDegradedFile,
      content: demoContent,
      contentHash: demoHash,
      source: 'demo',
    };

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[demoFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    expect(verifyBtn).not.toBeNull();

    await act(async () => {
      verifyBtn!.click();
      await Promise.resolve();
    });

    // BEFORE GUARANTEE: Invariant holds -- demo files NEVER get marked verified under any circumstance
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain('미검증 (UNVERIFIED)');
    expect(container.querySelector('[data-testid="integrity-status-verified"]')).toBeNull();
    expect(container.querySelector('[data-testid="integrity-action-error"]')?.textContent).toContain(
      '데모/미연결 데이터: 실제 저장소 바이트(WorkspaceEditView)가 연결되지 않아 무결성을 검증할 수 없습니다.'
    );

    // 2. AFTER: Genuine Kernel Checkout with matching byte hash
    const genuineContent = "print('genuine-verified')\n";
    const genuineHash = await calculateSha256(genuineContent);
    const genuineFile: InvFileItem = {
      ...sampleDegradedFile,
      content: genuineContent,
      contentHash: genuineHash,
      source: 'kernel-checkout',
    };

    await act(async () => {
      root.render(
        <InvFileExplorer
          key="after-genuine"
          initialFiles={[genuineFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const verifyBtnAfter = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtnAfter!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    // AFTER GUARANTEE: Genuine checkout byte equality transitions to VERIFIED
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain('검증 통과 (VERIFIED)');
    expect(container.querySelector('[data-testid="integrity-status-verified"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="calculated-hash"]')?.textContent).toBe(genuineHash);
    expect(container.querySelector('[data-testid="integrity-mismatch-banner"]')).toBeNull();
  });

  it('[VF-GM-03-MUTATION-PROOF-HASH] proves Mutation 1: Server fixture hash mismatch strictly fails and triggers TAMPERED alert (NEVER verified)', async () => {
    // In canonical fixture workspace-edit-view-response.json:
    // dataBase64 = "cHJpbnQoJ2hlbGxvJykK" -> "print('hello')\n" -> sha256 = "03e693d9f2f687e0f40e36a8df7fcb4d1c22974012b7c2a55c000eb30f305824"
    // But fixture sha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" (mismatch / tampered)
    const fixtureFiles = wsEditApi.mapWorkspaceFilesToInvItems({
      checkoutId: '55555555-5555-4555-8555-555555555555',
      revision: 1,
      sha256: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      snapshot: {
        format: 'workspace-snapshot:1',
        workspaceId: 'wsp_0123456789ABCDEFGHJKMNPQRS',
        directories: ['src'],
        files: [
          {
            path: 'src/main.py',
            executable: false,
            sha256: 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            sizeBytes: 15,
            dataBase64: 'cHJpbnQoJ2hlbGxvJykK',
          },
        ],
      },
    });

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={fixtureFiles}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    // MUTATION DETECTED: Hashes differ -> MUST be mismatch / tampered, NEVER verified
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain(
      '검증 실패 (해시 불일치 / TAMPERED)'
    );
    expect(container.querySelector('[data-testid="integrity-status-verified"]')).toBeNull();
    expect(container.querySelector('[data-testid="integrity-status-mismatch"]')).not.toBeNull();

    const mismatchBanner = container.querySelector('[data-testid="integrity-mismatch-banner"]');
    expect(mismatchBanner).not.toBeNull();
    expect(mismatchBanner?.textContent).toContain('무결성 검증 실패: 계산된 해시가 카탈로그 체크섬과 불일치합니다 (변조 감지)');
  });

  it('[VF-GM-03-MUTATION-PROOF-BYTES] proves Mutation 2: Tampered file byte content produces mismatch even when expected hash is valid', async () => {
    const originalContent = "print('hello')\n";
    const validHash = await calculateSha256(originalContent);

    // Tampered bytes injected in transit
    const tamperedContent = "print('hacked')\n";

    const tamperedFile: InvFileItem = {
      ...sampleDegradedFile,
      content: tamperedContent,
      contentHash: validHash, // Expects original hash
      source: 'kernel-checkout',
    };

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[tamperedFile]}
          clusterNodes={clusterNodesFixture}
        />
      );
    });

    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain(
      '검증 실패 (해시 불일치 / TAMPERED)'
    );
    expect(container.querySelector('[data-testid="integrity-status-verified"]')).toBeNull();
    expect(container.querySelector('[data-testid="integrity-status-mismatch"]')).not.toBeNull();
  });

  it('[VF-GM-03-CHECKOUT-INPUT-LOAD] loads checkout files through UI input and verifies loaded file integrity', async () => {
    const canonicalContent = "print('hello')\n";
    const canonicalHash = await calculateSha256(canonicalContent);

    const mockCheckoutView = {
      checkoutId: '55555555-5555-4555-8555-555555555555',
      revision: 1,
      sha256: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      snapshot: {
        format: 'workspace-snapshot:1' as const,
        workspaceId: 'wsp_0123456789ABCDEFGHJKMNPQRS',
        directories: ['src'],
        files: [
          {
            path: 'src/main.py',
            executable: false,
            sha256: canonicalHash, // Correct matching hash
            sizeBytes: 15,
            dataBase64: 'cHJpbnQoJ2hlbGxvJykK',
          },
        ],
      },
    };

    const fetchSpy = vi.spyOn(wsEditApi, 'fetchWorkspaceEditView').mockResolvedValue(mockCheckoutView);

    await act(async () => {
      root.render(
        <InvFileExplorer
          projectId="prj_0123456789ABCDEFGHJKMNPQRS"
          runId="run_0123456789ABCDEFGHJKMNPQRS"
          checkoutId="55555555-5555-4555-8555-555555555555"
          clusterNodes={clusterNodesFixture}
          initialNamespace="workspaces"
        />
      );
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      'prj_0123456789ABCDEFGHJKMNPQRS',
      'run_0123456789ABCDEFGHJKMNPQRS',
      '55555555-5555-4555-8555-555555555555'
    );

    // File from checkout is loaded and selected
    expect(container.textContent).toContain('main.py');
    expect(container.querySelector('[data-testid="file-source-badge"]')?.textContent).toContain(
      '커널 체크아웃 (WorkspaceEditView 실 바이트)'
    );

    // Click verify on loaded file
    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    // Verification PASSES genuinely
    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain('검증 통과 (VERIFIED)');
    expect(container.querySelector('[data-testid="integrity-status-verified"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="calculated-hash"]')?.textContent).toBe(canonicalHash);
  });

  it('[VF-GM-03-DECODE-ERROR-GUARD] proves base64 decode error renders alert banner and blocks verification as error', async () => {
    const brokenFile = wsEditApi.mapWorkspaceFilesToInvItems({
      checkoutId: '55555555-5555-4555-8555-555555555555',
      revision: 1,
      sha256: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
      snapshot: {
        format: 'workspace-snapshot:1',
        workspaceId: 'wsp_0123456789ABCDEFGHJKMNPQRS',
        directories: ['src'],
        files: [
          {
            path: 'src/corrupted.bin',
            executable: false,
            sha256: '1111111111111111111111111111111111111111111111111111111111111111',
            sizeBytes: 100,
            dataBase64: '!!!illegal-non-base64-character-sequence!!!',
          },
        ],
      },
    })[0];

    await act(async () => {
      root.render(
        <InvFileExplorer
          initialFiles={[brokenFile]}
          clusterNodes={clusterNodesFixture}
          initialNamespace="workspaces"
        />
      );
    });

    // 1. Decode error banner is displayed with role="alert"
    const decodeBanner = container.querySelector('[data-testid="file-decode-error-banner"]');
    expect(decodeBanner).not.toBeNull();
    expect(decodeBanner?.getAttribute('role')).toBe('alert');
    expect(decodeBanner?.textContent).toContain('파일 본문 디코딩 실패 (Base64 손상 또는 미지원 형식)');
    expect(decodeBanner?.textContent).toContain('사용자 조치 필요');

    // 2. Click verify button -> strictly blocks and transitions to error (NEVER verified, NEVER calculating fake hash)
    const verifyBtn = container.querySelector<HTMLButtonElement>('[data-testid="verify-integrity-btn"]');
    await act(async () => {
      verifyBtn!.click();
      await new Promise((r) => setTimeout(r, 20));
    });

    expect(container.querySelector('[data-testid="integrity-badge"]')?.textContent).toContain('검증 오류 (ERROR)');
    const errorBanner = container.querySelector('[data-testid="integrity-action-error"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('본문 Base64 디코딩 실패로 무결성을 검증할 수 없습니다');
  });
});
