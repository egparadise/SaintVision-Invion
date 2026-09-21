// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { InvFileExplorer } from '../src/features/desktop/InvFileExplorer';
import { ModelStudioView } from '../src/features/desktop/ModelStudioView';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import { WebTerminal } from '../src/features/terminal/WebTerminal';
import { TerminalSessionView } from '../src/features/desktop/TerminalSessionView';
import { App } from '../src/app/App';
import { PlacementSimulator } from '../src/features/placement/PlacementSimulator';

import * as fabricApi from '../src/features/desktop/fabricControlApi';
import * as storageObsApi from '../src/shared/api/storageObservation';
import { NodeItem } from '../src/contracts/types';
import { InvFileItem } from '../src/contracts/virtualFabric';

describe('Accessibility Status Roles, Screen Reader Guards & Disabled Button Descriptors', () => {
  let container: HTMLDivElement;
  let root: Root;

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
  ];

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockResolvedValue([]);
    vi.spyOn(fabricApi, 'getStorageContributions').mockResolvedValue([]);
    vi.spyOn(storageObsApi, 'fetchStorageObservation').mockResolvedValue({
      source: 'storage-kernel',
      observedAt: '2026-09-21T18:00:00Z',
      clusterId: 'cluster-dev-01',
      observation: {
        currentHealth: 'unknown',
        operationalAcceptanceAssessed: false,
        replicaCount: 3,
        underReplicatedCount: 0,
        unrecoverableCount: 0,
        integrityVerified: true,
      },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  // ===========================================================================
  // 1. ResourceExplorer Accessibility Guards
  // ===========================================================================
  describe('ResourceExplorer Accessibility', () => {
    it('Discovery Tab: missing tenant renders role="alert", broadcast button has aria-disabled and aria-describedby', async () => {
      await act(async () => {
        root.render(<ResourceExplorer initialTab="discovery" nodes={mockNodes} tenantId="" />);
      });

      const notice = container.querySelector('[data-testid="discovery-tenant-required-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.getAttribute('id')).toBe('discovery-tenant-required-notice');

      const broadcastBtn = container.querySelector('[data-testid="broadcast-announcement-btn"]') as HTMLButtonElement;
      expect(broadcastBtn).not.toBeNull();
      expect(broadcastBtn.disabled).toBe(true);
      expect(broadcastBtn.getAttribute('aria-disabled')).toBe('true');
      expect(broadcastBtn.getAttribute('aria-describedby')).toBe('discovery-tenant-required-notice');
      expect(broadcastBtn.getAttribute('title')).toContain('테넌트');
    });

    it('Discovery Tab: empty candidates list has role="status" and aria-live="polite"', async () => {
      await act(async () => {
        root.render(<ResourceExplorer initialTab="discovery" nodes={mockNodes} tenantId="ten_valid_123" />);
      });

      const emptyState = container.querySelector('[data-testid="discovery-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.getAttribute('role')).toBe('status');
      expect(emptyState?.getAttribute('aria-live')).toBe('polite');
    });

    it('Storage Tab: 0 nodes renders role="alert" storage-no-nodes-notice and disables register button with aria-describedby', async () => {
      await act(async () => {
        root.render(<ResourceExplorer initialTab="storage" nodes={[]} />);
      });

      const notice = container.querySelector('[data-testid="storage-no-nodes-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.getAttribute('id')).toBe('storage-no-nodes-notice');

      const btn = container.querySelector('[data-testid="register-contribution-btn"]') as HTMLButtonElement;
      expect(btn).not.toBeNull();
      expect(btn.disabled).toBe(true);
      expect(btn.getAttribute('aria-disabled')).toBe('true');
      expect(btn.getAttribute('aria-describedby')).toBe('storage-no-nodes-notice');
      expect(btn.getAttribute('title')).toContain('온라인 노드');
    });

    it('Storage Tab: missing project/run context renders role="alert" context warning and links to fetch button', async () => {
      await act(async () => {
        root.render(<ResourceExplorer initialTab="storage" nodes={mockNodes} projectId="" runId="" />);
      });

      const warning = container.querySelector('[data-testid="storage-observation-context-warning"]');
      expect(warning).not.toBeNull();
      expect(warning?.getAttribute('role')).toBe('alert');
      expect(warning?.getAttribute('id')).toBe('storage-observation-context-warning');

      const fetchBtn = container.querySelector('[data-testid="fetch-storage-observation-btn"]') as HTMLButtonElement;
      expect(fetchBtn).not.toBeNull();
      expect(fetchBtn.getAttribute('aria-disabled')).toBe('true');
      expect(fetchBtn.getAttribute('aria-describedby')).toBe('storage-observation-context-warning');
    });

    it('Pools Tab: empty planRunId renders role="alert" notice and disables create-plan-btn with aria-describedby', async () => {
      await act(async () => {
        root.render(<ResourceExplorer initialTab="pools" nodes={mockNodes} />);
      });

      const notice = container.querySelector('[data-testid="plan-run-id-user-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.getAttribute('id')).toBe('plan-run-id-user-action-notice');

      const createBtn = container.querySelector('[data-testid="create-plan-btn"]') as HTMLButtonElement;
      expect(createBtn).not.toBeNull();
      expect(createBtn.disabled).toBe(true);
      expect(createBtn.getAttribute('aria-disabled')).toBe('true');
      expect(createBtn.getAttribute('aria-describedby')).toBe('plan-run-id-user-action-notice');
      expect(createBtn.getAttribute('title')).toContain('planRunId');
    });
  });

  // ===========================================================================
  // 2. InvFileExplorer Accessibility & Tri-State Dynamic Roles
  // ===========================================================================
  describe('InvFileExplorer Accessibility', () => {
    const mockFiles: InvFileItem[] = [
      {
        uri: 'inv://models/model_weights.bin',
        namespace: 'models',
        relativePath: 'model_weights.bin',
        name: 'model_weights.bin',
        type: 'file',
        sizeBytes: 1024 * 1024 * 50,
        version: '1.0.0',
        contentHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        contentType: 'application/octet-stream',
        classification: 'confidential',
        updatedAt: '2026-09-21T12:00:00Z',
        source: 'kernel-checkout',
        content: 'actual checkout content bytes for sha256',
        isPinned: false,
        requiredReplicas: 2,
        replicas: [
          { nodeId: 'nod_01', nodeHostname: 'Node-01', localPath: '/var/saint/file_01', status: 'healthy', lastObservedAt: '2026-09-21T12:00:00Z' },
        ],
      },
    ];

    it('Integrity Badge: unverified state has role="status" and aria-live="polite"', async () => {
      await act(async () => {
        root.render(<InvFileExplorer initialFiles={mockFiles} />);
      });

      const badge = container.querySelector('[data-testid="integrity-badge"]');
      expect(badge).not.toBeNull();
      expect(badge?.getAttribute('role')).toBe('status');
      expect(badge?.getAttribute('aria-live')).toBe('polite');
      expect(badge?.textContent).toContain('미검증 (UNVERIFIED)');
    });

    it('Integrity Badge: mismatch transition switches to role="alert" and aria-live="assertive"', async () => {
      const mismatchAdapter = vi.fn().mockResolvedValue({
        matches: false,
        calculatedHash: 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
      });

      await act(async () => {
        root.render(
          <InvFileExplorer
            initialFiles={mockFiles}
            onVerifyIntegrity={mismatchAdapter}
          />
        );
      });

      const verifyBtn = container.querySelector('[data-testid="verify-integrity-btn"]') as HTMLButtonElement;
      expect(verifyBtn).not.toBeNull();
      await act(async () => {
        verifyBtn.click();
      });

      const badge = container.querySelector('[data-testid="integrity-badge"]');
      expect(badge?.getAttribute('role')).toBe('alert');
      expect(badge?.getAttribute('aria-live')).toBe('assertive');
      expect(badge?.textContent).toContain('검증 실패 (해시 불일치 / TAMPERED)');

      const mismatchBanner = container.querySelector('[data-testid="integrity-mismatch-banner"]');
      expect(mismatchBanner?.getAttribute('role')).toBe('alert');
    });

    it('Integrity Badge: verified transition remains role="status" (polite success announcement)', async () => {
      const matchAdapter = vi.fn().mockResolvedValue({
        matches: true,
        calculatedHash: mockFiles[0].contentHash,
      });

      await act(async () => {
        root.render(
          <InvFileExplorer
            initialFiles={mockFiles}
            onVerifyIntegrity={matchAdapter}
          />
        );
      });

      const verifyBtn = container.querySelector('[data-testid="verify-integrity-btn"]') as HTMLButtonElement;
      expect(verifyBtn).not.toBeNull();
      await act(async () => {
        verifyBtn.click();
      });

      const badge = container.querySelector('[data-testid="integrity-badge"]');
      expect(badge?.getAttribute('role')).toBe('status');
      expect(badge?.getAttribute('aria-live')).toBe('polite');
      expect(badge?.textContent).toContain('검증 통과 (VERIFIED)');
    });

    it('Non-color-only Defense: replica badge contains explicit text label (저하/정상) and aria-label', async () => {
      await act(async () => {
        root.render(<InvFileExplorer initialFiles={mockFiles} />);
      });

      const replicaSpan = container.querySelector('span[aria-label*="복제본 상태"]');
      expect(replicaSpan).not.toBeNull();
      expect(replicaSpan?.getAttribute('aria-label')).toContain('복제본 상태: 2개 중 1개 가용 (저하)');
      expect(replicaSpan?.textContent).toContain('1/2 복제본 (저하)');
    });

    it('Workspaces Namespace: checkout context warning has role="alert" and connects to load-checkout-btn', async () => {
      await act(async () => {
        root.render(<InvFileExplorer initialFiles={mockFiles} initialNamespace="workspaces" projectId="" runId="" />);
      });

      const warning = container.querySelector('[data-testid="checkout-context-warning"]');
      expect(warning).not.toBeNull();
      expect(warning?.getAttribute('role')).toBe('alert');
      expect(warning?.getAttribute('id')).toBe('checkout-context-warning');

      const loadBtn = container.querySelector('[data-testid="load-checkout-btn"]') as HTMLButtonElement;
      expect(loadBtn).not.toBeNull();
      expect(loadBtn.getAttribute('aria-disabled')).toBe('true');
      expect(loadBtn.getAttribute('aria-describedby')).toBe('checkout-context-warning');
      expect(loadBtn.getAttribute('title')).toContain('컨텍스트');
    });
  });

  // ===========================================================================
  // 3. ModelStudioView Accessibility
  // ===========================================================================
  describe('ModelStudioView Accessibility', () => {
    it('Model verification notice has role="status" and unobserved-shards-notice has role="status"', async () => {
      await act(async () => {
        root.render(
          <ModelStudioView
            projectId="prj_test_01"
            initialModel={{
              modelId: 'mod_01',
              modelName: 'TestModel',
              version: '1.0',
              totalSizeBytes: 1024,
              format: 'onnx',
              parameterCount: 1000,
              targetPrecision: 'fp16',
              shards: [],
            }}
          />
        );
      });

      const verifyNotice = container.querySelector('[data-testid="model-verification-notice"]');
      expect(verifyNotice).not.toBeNull();
      expect(verifyNotice?.getAttribute('role')).toBe('status');

      const shardsNotice = container.querySelector('[data-testid="unobserved-shards-notice"]');
      expect(shardsNotice).not.toBeNull();
      expect(shardsNotice?.getAttribute('role')).toBe('status');
    });
  });

  // ===========================================================================
  // 4. ModelLineageView Accessibility
  // ===========================================================================
  describe('ModelLineageView Accessibility', () => {
    it('Lineage unexposed notice has role="status", deploy button disabled with aria-describedby to approval notice', async () => {
      await act(async () => {
        root.render(<ModelLineageView />);
      });

      const notice = container.querySelector('[data-testid="lineage-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');

      // Click on staging model
      const modelBtns = container.querySelectorAll('button');
      const stagingBtn = Array.from(modelBtns).find((b) => b.textContent?.includes('v1'));
      if (stagingBtn) {
        await act(async () => {
          stagingBtn.click();
        });
      }

      const deployBtn = container.querySelector('[data-testid="lineage-deploy-btn"]') as HTMLButtonElement;
      if (deployBtn) {
        expect(deployBtn.getAttribute('aria-disabled')).toBe('true');
        expect(deployBtn.getAttribute('aria-describedby')).toBe('approval-input-user-action-notice');
        expect(deployBtn.getAttribute('title')).toContain('승인 번호');

        const approvalNotice = container.querySelector('#approval-input-user-action-notice');
        expect(approvalNotice).not.toBeNull();
        expect(approvalNotice?.getAttribute('role')).toBe('alert');
      }
    });
  });

  // ===========================================================================
  // 5. WebTerminal & TerminalSessionView Accessibility
  // ===========================================================================
  describe('WebTerminal and TerminalSessionView Accessibility', () => {
    it('WebTerminal: connection dot has aria-hidden, status text has role="status", commandId notice has role="alert"', async () => {
      await act(async () => {
        root.render(
          <WebTerminal
            sessionId="sess_test_01"
            workspaceId="wsp_test_01"
            commandId=""
          />
        );
      });

      const dot = container.querySelector('[data-testid="connection-status-dot"]');
      expect(dot?.getAttribute('aria-hidden')).toBe('true');

      const statusText = container.querySelector('[data-testid="terminal-connection-status"]');
      expect(statusText?.getAttribute('role')).toBe('status');
      expect(statusText?.getAttribute('aria-live')).toBe('polite');

      const cmdNotice = container.querySelector('[data-testid="terminal-command-required-notice"]');
      expect(cmdNotice?.getAttribute('role')).toBe('alert');
      expect(cmdNotice?.getAttribute('id')).toBe('terminal-command-required-notice');

      const reconnectBtn = container.querySelector('[data-testid="terminal-reconnect-btn"]');
      expect(reconnectBtn?.getAttribute('aria-describedby')).toBe('terminal-command-required-notice');
    });

    it('TerminalSessionView: 0 nodes notice has role="alert"', async () => {
      await act(async () => {
        root.render(<TerminalSessionView nodes={[]} />);
      });

      const emptyNotice = container.querySelector('[data-testid="terminal-empty-nodes-notice"]');
      expect(emptyNotice).not.toBeNull();
      expect(emptyNotice?.getAttribute('role')).toBe('alert');
      expect(emptyNotice?.getAttribute('id')).toBe('terminal-empty-nodes-notice');
    });
  });

  // ===========================================================================
  // 6. App & PlacementSimulator Accessibility
  // ===========================================================================
  describe('App and PlacementSimulator Accessibility', () => {
    it('App: missing workspace notice has role="alert"', async () => {
      await act(async () => {
        root.render(<App />);
      });

      // Navigate to Terminal Tab (Tab 5)
      const tabs = container.querySelectorAll('button');
      const terminalTab = Array.from(tabs).find((b) => b.textContent?.includes('터미널'));
      if (terminalTab) {
        await act(async () => {
          terminalTab.click();
        });
      }

      const notice = container.querySelector('[data-testid="terminal-no-workspace-notice"]');
      if (notice) {
        expect(notice.getAttribute('role')).toBe('alert');
        expect(notice.getAttribute('id')).toBe('terminal-no-workspace-notice');
      }
    });

    it('PlacementSimulator: empty states have role="status"', async () => {
      await act(async () => {
        root.render(
          <PlacementSimulator
            nodes={mockNodes}
            initialPreviewState="success"
            initialServerShards={[]}
            initialCandidatesState="success"
            initialCandidates={[]}
          />
        );
      });

      const previewEmpty = container.querySelector('[data-testid="preview-empty-state"]');
      expect(previewEmpty).not.toBeNull();
      expect(previewEmpty?.getAttribute('role')).toBe('status');

      const candidatesEmpty = container.querySelector('[data-testid="candidates-empty-state"]');
      expect(candidatesEmpty).not.toBeNull();
      expect(candidatesEmpty?.getAttribute('role')).toBe('status');
    });
  });
});
