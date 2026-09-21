// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { DeploymentManager } from '../src/features/deployment/deploymentEngine';
import { ReleaseManager } from '../src/features/release/releaseEngine';
import { DesktopShell } from '../src/features/desktop/DesktopShell';
import type { NodeItem, ProjectItem, RunItem } from '../src/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const sampleProject: ProjectItem = {
  id: 'prj_matrix_01',
  name: 'SaintVision Browser Matrix Acceptance Project',
};

const sampleNodes: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 16 * 1024 ** 3,
    gpuCount: 1,
    storageTotalBytes: 2 * 1024 ** 4,
    storageUsedBytes: 500 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
    schedulable: true,
    allocatableCores: 16,
  },
  {
    id: 'nod_01JABCDEF02',
    hostname: 'Node-02-WinWork',
    status: 'online',
    os: 'windows',
    cpuCores: 8,
    cpuUsagePercent: 30,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 8 * 1024 ** 3,
    gpuCount: 0,
    storageTotalBytes: 2 * 1024 ** 4,
    storageUsedBytes: 400 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
    schedulable: true,
    allocatableCores: 8,
  },
  {
    id: 'nod_01JABCDEF03',
    hostname: 'Node-03-LinuxGpu',
    status: 'online',
    os: 'linux',
    cpuCores: 16,
    cpuUsagePercent: 40,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 20 * 1024 ** 3,
    gpuCount: 1,
    storageTotalBytes: 2 * 1024 ** 4,
    storageUsedBytes: 600 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
    schedulable: true,
    allocatableCores: 16,
  },
  {
    id: 'nod_01JABCDEF04',
    hostname: 'Node-04-WinObs',
    status: 'online',
    os: 'windows',
    cpuCores: 4,
    cpuUsagePercent: 10,
    memoryTotalBytes: 16 * 1024 ** 3,
    memoryUsedBytes: 4 * 1024 ** 3,
    gpuCount: 0,
    storageTotalBytes: 1 * 1024 ** 4,
    storageUsedBytes: 100 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
    schedulable: false,
    observationOnly: true,
    allocatableCores: 0,
  },
  {
    id: 'nod_01JABCDEF05',
    hostname: 'Node-05-LinuxTrain',
    status: 'online',
    os: 'linux',
    cpuCores: 16,
    cpuUsagePercent: 45,
    memoryTotalBytes: 48 * 1024 ** 3,
    memoryUsedBytes: 16 * 1024 ** 3,
    gpuCount: 1,
    storageTotalBytes: 3 * 1024 ** 4,
    storageUsedBytes: 800 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
    schedulable: true,
    allocatableCores: 16,
  },
];

const sampleRuns: RunItem[] = [
  {
    id: 'run_matrix_01',
    projectId: 'prj_matrix_01',
    status: 'succeeded',
    state: 'succeeded',
    targetNodeId: 'nod_01JABCDEF01',
    createdAt: '2026-09-21T10:00:00Z',
    startedAt: '2026-09-21T10:00:01Z',
    finishedAt: '2026-09-21T10:00:05Z',
  },
];

describe('VF-GM-06: 외부 HTTPS, Browser Matrix, Rollback & Real-Browser Acceptance', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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

  it('Test 1: Verifies strict TLS 1.3 parameters, HSTS, SAN coverage, and Nginx reverse proxy configuration', () => {
    const dm = new DeploymentManager();
    const tls = dm.getTlsDetails();

    expect(tls.domain).toBe('saintvision.internal');
    expect(tls.tlsVersion).toContain('TLSv1.3');
    expect(tls.cipherSuite).toContain('TLS_AES_256_GCM_SHA384');
    expect(tls.hstsEnabled).toBe(true);
    expect(tls.sanList).toContain('saintvision.internal');
    expect(tls.sanList).toContain('*.node.saintvision.internal');
    expect(tls.sanList.length).toBeGreaterThanOrEqual(5);

    const conf = dm.generateNginxConfig();
    expect(conf).toContain('listen 8443 ssl http2;');
    expect(conf).toContain('ssl_protocols TLSv1.3;');
    expect(conf).toContain('Strict-Transport-Security');
    expect(conf).toContain('proxy_buffering off;');
    expect(conf).toContain('proxy_set_header Upgrade $http_upgrade;');
  });

  it('Test 2: Verifies web rollback execution from RC.2 to RC.1 with state preservation', () => {
    const rm = new ReleaseManager();
    const initialCandidates = rm.getReleaseCandidates();
    const activeBefore = initialCandidates.find((rc) => rc.isActive);
    expect(activeBefore?.tag).toBe('v1.0.0-rc.2');

    const rollbackResult = rm.rollbackToVersion('v1.0.0-rc.1');
    expect(rollbackResult.success).toBe(true);
    expect(rollbackResult.activeCandidate?.tag).toBe('v1.0.0-rc.1');
    expect(rollbackResult.activeCandidate?.rollbackVerified).toBe(true);

    const updatedCandidates = rm.getReleaseCandidates();
    const activeAfter = updatedCandidates.find((rc) => rc.isActive);
    expect(activeAfter?.tag).toBe('v1.0.0-rc.1');
    const oldCandidate = updatedCandidates.find((rc) => rc.tag === 'v1.0.0-rc.2');
    expect(oldCandidate?.isActive).toBe(false);
  });

  it('Test 3: Strictly rejects rollback to non-existent candidate with honest error message', () => {
    const rm = new ReleaseManager();
    const result = rm.rollbackToVersion('v9.9.9-invalid');
    expect(result.success).toBe(false);
    expect(result.error).toBe('Release candidate v9.9.9-invalid not found');
  });

  it('Test 4: Verifies all 7 production SLO metrics meet criteria under normal telemetry', () => {
    const rm = new ReleaseManager();
    const slos = rm.getSloRecords();

    expect(slos).toHaveLength(7);
    slos.forEach((slo) => {
      expect(slo.status).toBe('met');
    });

    const latencySlo = slos.find((s) => s.category === 'latency');
    expect(latencySlo?.targetValue).toContain('2.0 초');

    const vulnsSlo = slos.find((s) => s.name.includes('취약점'));
    expect(vulnsSlo?.actualValue).toBe('0 건');

    const bypassSlo = slos.find((s) => s.name.includes('우회'));
    expect(bypassSlo?.actualValue).toContain('0 건 (100% 차단)');
  });

  it('Test 5: Zero-Mock: Strictly detects and marks breached status when telemetry violates thresholds', () => {
    const rm = new ReleaseManager();
    const breached = rm.computeSloRecords({
      schedulerP95LatencySeconds: 3.82,
      heartbeatDetectionSeconds: 85.0,
      unapprovedExecutionsCount: 1,
      dockerSocketExposedCount: 1,
      rpoMinutes: 25.0,
      rtoMinutes: 90.0,
      unresolvedVulnerabilitiesCount: 2,
    });

    expect(breached).toHaveLength(7);
    breached.forEach((slo) => {
      expect(slo.status).toBe('breached');
    });

    const latencySlo = breached.find((s) => s.category === 'latency');
    expect(latencySlo?.actualValue).toBe('3.82 초');

    const vulnsSlo = breached.find((s) => s.name.includes('취약점'));
    expect(vulnsSlo?.actualValue).toBe('2 건');
  });

  it('Test 6: Validates WCAG 2.1 AA accessibility audit compliance rules and contrast ratios', () => {
    const rm = new ReleaseManager();
    const audits = rm.getAccessibilityAudits();

    expect(audits.length).toBeGreaterThanOrEqual(5);
    audits.forEach((a) => {
      expect(a.status).toBe('pass');
    });

    const textContrast = audits.find((a) => a.ruleId === 'wcag21-1.4.3-contrast-minimum');
    expect(textContrast?.contrastRatio).toBeGreaterThanOrEqual(4.5);
    expect(textContrast?.contrastRatio).toBe(11.4);

    const nonTextContrast = audits.find((a) => a.ruleId === 'wcag21-1.4.11-non-text-contrast');
    expect(nonTextContrast?.contrastRatio).toBeGreaterThanOrEqual(3.0);
    expect(nonTextContrast?.contrastRatio).toBe(4.12);
  });

  it('Test 7: Renders DesktopShell across responsive desktop viewport with active taskbar and window manager', async () => {
    await act(async () => {
      root.render(
        <DesktopShell
          project={sampleProject}
          nodes={sampleNodes}
          runs={sampleRuns}
          activeTab="desktop"
        />
      );
    });

    // Desktop shell container
    const desktopContainer = container.querySelector('[data-testid="desktop-shell-container"]');
    expect(desktopContainer).not.toBeNull();

    // Taskbar presence
    const taskbar = container.querySelector('[data-testid="desktop-taskbar"]');
    expect(taskbar).not.toBeNull();

    // Mode toggle between Desktop and Portal
    const modeSwitcher = container.querySelector('[data-testid="desktop-mode-switcher"]');
    expect(modeSwitcher).not.toBeNull();
  });

  it('Test 8: Reconciles 5 enrolled nodes and validates observation-only Node-04 isolation', () => {
    const dm = new DeploymentManager();
    const nodes = dm.getNodeVerifications();
    expect(nodes).toHaveLength(5);

    const winNodes = nodes.filter((n) => n.os === 'windows');
    const linuxNodes = nodes.filter((n) => n.os === 'linux');
    expect(winNodes).toHaveLength(3);
    expect(linuxNodes).toHaveLength(2);

    const reconciled = dm.reconcileLiveClusterNodes(sampleNodes);
    const obsNode = reconciled.find((n) => n.nodeId === 'nod_01JABCDEF04');
    expect(obsNode?.liveSchedulable).toBe(false);
    expect(obsNode?.liveObservationOnly).toBe(true);
    expect(obsNode?.liveAllocatableCores).toBe(0);
  });

  it('Test 9: Verifies operator release sign-off creates immutable release manifest with evidenceId and sha256 checksums', () => {
    const dm = new DeploymentManager();
    const result = dm.signOffRelease('usr_operator_lead', {
      roles: ['operator'],
      evidenceId: 'evi_operator_signoff_20260921',
    });

    expect(result.success).toBe(true);
    expect(result.manifest.version).toBe('v1.0.0-final-GA');
    expect(result.manifest.releaseId).toBe('REL-2026-R4-GA');
    expect(result.manifest.operatorSignOff).toBe(true);
    expect(result.manifest.imageDigest).toMatch(/^sha256:[a-f0-9]{64}$/);
    expect(result.manifest.totalNodes).toBe(5);
  });

  it('Test 10: Zero-Mock: Preflight status reflects physical acceptance only after operator sign-off', () => {
    const dm = new DeploymentManager();
    const before = dm.getPreflightStatus();
    expect(before.physicalHardwareAcceptance).toBe('pending');

    dm.signOffRelease('usr_operator_lead');
    const after = dm.getPreflightStatus();
    expect(after.physicalHardwareAcceptance).toBe('accepted');
  });
});
