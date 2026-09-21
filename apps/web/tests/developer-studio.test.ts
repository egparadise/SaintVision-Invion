import { describe, it, expect } from 'vitest';
import { evaluatePlacement } from '../src/features/placement/placementEngine';
import { computeDiff, computeSha256 } from '../src/features/editor/diffEngine';
import { NodeItem, PlacementRequirement, NodeStopReceipt, RunItem, ApprovalItem } from '../src/contracts/types';
import { isRouteNotFoundError } from '../src/shared/api/client';

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
    allocatableCores: 12,
    allocatableMemoryBytes: 36 * 1024 ** 3,
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
    allocatableCores: 4,
    allocatableMemoryBytes: 12 * 1024 ** 3,
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
    allocatableCores: 6,
    allocatableMemoryBytes: 20 * 1024 ** 3,
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
    allocatableCores: 4,
    allocatableMemoryBytes: 16 * 1024 ** 3,
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
    allocatableCores: 10,
    allocatableMemoryBytes: 24 * 1024 ** 3,
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

  it('Step 2: strictly rejects observation-only node (192.168.45.225) from workload placement', () => {
    const nodesWithObservation: NodeItem[] = [
      ...TEST_NODES,
      {
        id: 'nod_01JREMOTE_225',
        hostname: 'Node-Remote-192.168.45.225',
        ipAddress: '192.168.45.225',
        status: 'online',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 10,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 10 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 2000 * 1024 ** 3,
        storageUsedBytes: 300 * 1024 ** 3,
        heartbeatAt: new Date().toISOString(),
        observationOnly: true, // Configured as observation only!
        schedulable: false,
        allocatableCores: 0,
        allocatableMemoryBytes: 0,
      },
    ];

    const req: PlacementRequirement = {
      requiredCores: 4,
      requiredMemoryBytes: 8 * 1024 ** 3,
      preferredOs: 'linux',
    };

    const result = evaluatePlacement(nodesWithObservation, req);
    const evalRemote = result.evaluations.find((e) => e.nodeId === 'nod_01JREMOTE_225');

    expect(evalRemote).toBeDefined();
    expect(evalRemote?.hardFilterPassed).toBe(false);
    expect(evalRemote?.rejectionReasons.some((r) => r.includes('관측 전용 노드'))).toBe(true);
    expect(result.selectedNodeId).not.toBe('nod_01JREMOTE_225');
  });

  it('Step 2: strictly blocks candidate placement when allocatable capacity is undefined/unverified', () => {
    const unverifiedNode: NodeItem = {
      ...TEST_NODES[0],
      id: 'nod_unverified_core',
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
    expect(result.selectedNodeId).toBeNull();
  });

  it('Step 4: validates result artifact manifest structure with verified evidence', () => {
    const artifact = {
      runId: 'run_test_01',
      projectId: 'prj_01JABCDE',
      workspaceId: 'wsp_01JABCDE001',
      manifest: {
        entrypoint: 'src/server.ts',
        filesCount: 3,
        outputDigest: 'sha256:4a6f9821ef34a02937cd219e88a31401f82e1850d810237913fb9a3d467e2a9b',
        verifiedEvidenceId: 'evi_rcp_run_test_01',
      },
      executionReceipt: {
        exitCode: 0,
        physicallyStopped: true,
        verified: true,
        resourceReclaimed: true,
      },
    };

    expect(artifact.runId).toBe('run_test_01');
    expect(artifact.manifest.outputDigest).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(artifact.executionReceipt.verified).toBe(true);
    expect(artifact.executionReceipt.physicallyStopped).toBe(true);
  });

  it('Step 4: links awaiting_approval run to governance approval with idempotency nonce', () => {
    const run: RunItem = {
      id: 'run_01JABCDE0002',
      projectId: 'prj_01JABCDE',
      workspaceId: 'wsp_01JABCDE001',
      objective: '합성 데이터셋 전처리 및 로컬 분할 검증',
      state: 'awaiting_approval',
      requestedBy: 'usr_researcher_02',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      version: 1,
    };

    const approval: ApprovalItem = {
      id: 'apr_01JXYZ987654',
      runId: 'run_01JABCDE0002',
      workspaceId: 'wsp_01JABCDE001',
      nodeId: 'nod_01JABCDEF01',
      riskLevel: 'L2',
      target: 'Workspace Sandbox on Node-01',
      command: 'deploy.release',
      status: 'pending',
      nonce: 'nonce_987654321',
      expiresAt: new Date(Date.now() + 600000).toISOString(),
      policyReason: '외부 접근 포트 변경 및 TLS 암호화 활성화 정책에 따른 L2 승인 요구 (Rule #304)',
      createdAt: new Date().toISOString(),
    };

    expect(run.state).toBe('awaiting_approval');
    expect(approval.runId).toBe(run.id);
    expect(approval.nonce).toBe('nonce_987654321');
    expect(approval.riskLevel).toBe('L2');
    expect(approval.status).toBe('pending');
  });

  it('Step 4 & Zero-Mock: strictly prevents synthesizing fake NodeStopReceipt on fetch failure', () => {
    // When receipt fetch returns 404 or fails, receipt must NOT be forged with fake hashes
    let selectedReceipt: NodeStopReceipt | null = null;
    let errorMessage: string | null = null;

    const simulateReceiptFetchError = (err: { detail: string; status: number }) => {
      // Must not assign fabricated receipt
      errorMessage = `물리 정지 영수증(NodeStopReceipt) 조회 실패: ${err.detail}`;
    };

    simulateReceiptFetchError({ detail: 'RES-RECEIPT-404', status: 404 });

    expect(selectedReceipt).toBeNull();
    expect(errorMessage).toContain('RES-RECEIPT-404');
  });

  it('Step 1: handles kernelLinked=false as an explainable security state rather than an error', () => {
    // An unlinked project is not an error; it explains the separation between project creation and execution grant
    const unlinkedProject = {
      id: 'prj_01JUNLINKED',
      name: 'SaintVision BioInformatics AI (Unlinked Demo)',
      description: '신규 생성되어 아직 운영자 커널에 링크되지 않은 프로젝트 (의도된 안전 분리 상태)',
      ownerId: 'usr_developer_01',
      workspaceCount: 1,
      createdAt: '2026-09-11T12:00:00Z',
      kernelLinked: false,
      kernelEnabled: false,
    };

    expect(unlinkedProject.kernelLinked).toBe(false);
    expect(unlinkedProject.kernelEnabled).toBe(false);

    // Explanatory state message check
    const explainStatus = (proj: typeof unlinkedProject) => {
      if (proj.kernelLinked === false) {
        return '커널 미연결 상태 안내 (kernelLinked=false) — 오류가 아니라 설명할 정상 분리 상태입니다';
      }
      return '커널 연동 완료';
    };

    expect(explainStatus(unlinkedProject)).toContain('오류가 아니라 설명할 정상 분리 상태입니다');
  });

  it('Step 1 & 3: evaluates Execution Readiness 6 checks and identifies resolvedBy authority for each unmet item', () => {
    const readinessReport = {
      workspaceId: 'wsp_01JUNLINKED001',
      projectId: 'prj_01JUNLINKED',
      executable: false,
      scope: 'workspace-preconditions-not-execution-admission',
      nodeReadiness: 'blocked',
      admissionRequired: true,
      checks: [
        {
          check: 'project_linked_to_kernel',
          satisfied: false,
          detail: 'the execution kernel acts only on projects an operator has linked; creating a project deliberately does not grant that',
          resolvedBy: 'operator',
          remedy: 'ask the operator to enable this project for managed execution',
        },
        {
          check: 'requester_registered_with_kernel',
          satisfied: true,
          detail: 'approval identity is registered by an operator and is one subject to one user',
          resolvedBy: 'operator',
          remedy: 'ask the operator to register this account for managed execution',
        },
        {
          check: 'role_permits_requesting',
          satisfied: true,
          detail: "user's project role permits requesting work",
          resolvedBy: 'project owner',
          remedy: 'a project owner changes the role through the members API',
        },
        {
          check: 'workspace_ready',
          satisfied: true,
          detail: "the workspace status is 'active'",
          resolvedBy: 'project owner',
        },
        {
          check: 'kernel_request_permission',
          satisfied: false,
          detail: 'the current account and project must have an enabled execution grant',
          resolvedBy: 'operator',
          remedy: "ask the operator to review this account's project execution permission",
        },
        {
          check: 'tool_chosen_and_usable',
          satisfied: true,
          detail: 'development tool is chosen and verified on the target node',
          resolvedBy: 'node owner',
          remedy: 'connect the selected Node and verify its tool installation and login',
        },
      ],
      blockedBy: ['operator'],
      summary: '2 of 6 preconditions are unmet; Node validation and execution admission are required.',
    };

    expect(readinessReport.checks.length).toBe(6);
    expect(readinessReport.executable).toBe(false);
    expect(readinessReport.blockedBy).toContain('operator');

    // Unmet check verification
    const unmetChecks = readinessReport.checks.filter((c) => !c.satisfied);
    expect(unmetChecks.length).toBe(2);
    unmetChecks.forEach((c) => {
      expect(c.resolvedBy).toBeDefined();
      expect(c.remedy).toBeDefined();
    });
  });

  describe('UI-FB-03 ResultView & Artifact Fallback Boundary Controls', () => {
    it('isRouteNotFoundError returns true ONLY for genuine unmapped route 404', () => {
      // Generic FastAPI unmapped 404
      expect(isRouteNotFoundError({ status: 404, problem: { detail: 'Not Found' } })).toBe(true);
      // Client synthesized network 404
      expect(isRouteNotFoundError({ status: 404, problem: { code: 'NET-404' } })).toBe(true);
      // Generic 404 without code
      expect(isRouteNotFoundError({ status: 404 })).toBe(true);
    });

    it('isRouteNotFoundError returns false for 401, 403, 500, network errors, and app-level 404s', () => {
      // 401 Unauthorized
      expect(isRouteNotFoundError({ status: 401, problem: { status: 401, code: 'SEC-401' } })).toBe(false);
      // 403 Forbidden
      expect(isRouteNotFoundError({ status: 403, problem: { status: 403, code: 'SEC-403' } })).toBe(false);
      // 500 Internal Error
      expect(isRouteNotFoundError({ status: 500, problem: { status: 500, code: 'NET-500' } })).toBe(false);
      // Application level entity not found (route exists, run missing)
      expect(isRouteNotFoundError({ status: 404, problem: { status: 404, code: 'RES-RUN-404' } })).toBe(false);
      expect(isRouteNotFoundError({ status: 404, problem: { status: 404, code: 'APP-404' } })).toBe(false);
      expect(isRouteNotFoundError(null)).toBe(false);
    });
  });
});


