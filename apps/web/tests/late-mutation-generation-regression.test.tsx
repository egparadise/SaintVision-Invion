// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { App } from '../src/app/App';
import * as sessionModule from '../src/features/auth/session';
import * as clientModule from '../src/shared/api/client';
import * as projectObsModule from '../src/shared/api/projectObservation';
import * as runApprovalObsModule from '../src/shared/api/runApprovalObservation';
import * as kernelMutationsModule from '../src/shared/api/kernelMutations';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import * as storageObsApi from '../src/shared/api/storageObservation';

describe('S1 Codex Security Delta: Deterministic Delayed-Promise Generation Regression', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }));
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockResolvedValue([]);
    vi.spyOn(fabricApi, 'getStorageContributions').mockResolvedValue([]);
    vi.spyOn(fabricApi, 'getNodeResourceUsage').mockResolvedValue(null);
    vi.spyOn(storageObsApi, 'fetchStorageObservation').mockResolvedValue({
      source: 'storage-kernel',
      observedAt: '2026-09-22T00:00:00Z',
      clusterId: 'cluster-dev-01',
      observation: {
        currentHealth: 'healthy',
        operationalAcceptanceAssessed: true,
        replicaCount: 1,
        activeReplicas: 1,
        syncLagMs: 0,
        unhealthyReplicas: [],
        degradedReasons: [],
      },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('suppresses late-resolving workspace creation when logout occurs in-flight (Zero Tenant Leaks)', async () => {
    // 1. Initial Login for User A
    const hasCb = vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'mock-jwt-tenant-a',
      user: { id: 'usr_tenant_a', name: 'User A', role: 'developer', tenantId: 'ten_alpha' },
    });

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_alpha', name: 'Project Alpha', tenantId: 'ten_alpha', createdAt: '2026-09-22T00:00:00Z' }];
      }
      if (path.includes('/nodes')) {
        return { items: [], total: 0 };
      }
      return {};
    });

    vi.spyOn(projectObsModule, 'fetchProjects').mockResolvedValue([
      { id: 'prj_alpha', name: 'Project Alpha', tenantId: 'ten_alpha', createdAt: '2026-09-22T00:00:00Z' },
    ]);
    vi.spyOn(projectObsModule, 'fetchProjectWorkspaces').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedRuns').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedApprovals').mockResolvedValue([]);

    // Deferred promise for createProjectWorkspace
    let resolveCreate: ((val: any) => void) | null = null;
    const createDeferred = new Promise<any>((resolve) => {
      resolveCreate = resolve;
    });
    const createSpy = vi.spyOn(projectObsModule, 'createProjectWorkspace').mockReturnValue(createDeferred);

    // Mount App
    await act(async () => {
      root.render(<App />);
    });
    // Wait for login exchange & project fetching to complete
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    hasCb.mockReturnValue(false);

    // Switch to Workspace tab
    const tabs = Array.from(container.querySelectorAll('button'));
    const wspTab = tabs.find((b) => b.textContent?.includes('Workspaces'));
    expect(wspTab).toBeDefined();
    await act(async () => {
      wspTab?.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // Click "+ 새 Workspace 생성" to open modal
    const openModalBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('새 Workspace 생성')
    );
    expect(openModalBtn).toBeDefined();
    await act(async () => {
      openModalBtn?.click();
    });

    // Fill workspace name and click create
    const nameInput = container.querySelector('[data-testid="workspace-name-input"]') as HTMLInputElement;
    expect(nameInput).not.toBeNull();
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(nameInput, 'leaked-workspace-alpha');
      nameInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const form = container.querySelector('form') as HTMLFormElement;
    expect(form).not.toBeNull();

    // Trigger creation (enters in-flight await)
    await act(async () => {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(createSpy).toHaveBeenCalledWith('prj_alpha', 'leaked-workspace-alpha');

    // 2. WHILE IN-FLIGHT: User A logs out (triggers resetAuthenticatedState)
    const logoutBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('로그아웃')
    );
    expect(logoutBtn).toBeDefined();
    await act(async () => {
      logoutBtn?.click();
    });

    // Verify logged out
    const loginHeader = container.querySelector('h1');
    expect(loginHeader?.textContent).toContain('SaintVision 로그인');

    // 3. Late resolution of User A's workspace creation
    await act(async () => {
      resolveCreate!({ workspaceId: 'wsp_leaked_tenant_a', name: 'leaked-workspace-alpha' });
    });

    // 4. User B logs in (Different tenant: ten_bravo)
    const loginSuccessCallback = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('조직 계정으로 로그인')
    );
    // User B's projects
    vi.spyOn(projectObsModule, 'fetchProjects').mockResolvedValue([
      { id: 'prj_bravo', name: 'Project Bravo', tenantId: 'ten_bravo', createdAt: '2026-09-22T00:00:00Z' },
    ]);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'mock-jwt-tenant-b',
      user: { id: 'usr_tenant_b', name: 'User B', role: 'developer', tenantId: 'ten_bravo' },
    });

    await act(async () => {
      loginSuccessCallback?.click();
    });

    // Verify User B does not have User A's workspace selected!
    expect(container.querySelector('[data-testid="execution-result-view"]')).toBeNull();
    expect(container.textContent).not.toContain('wsp_leaked_tenant_a');
  });

  it('suppresses late-rejecting mutation error when 401 occurs in-flight (No Ghost Error Banners)', async () => {
    // 1. Initial Login
    const hasCb2 = vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'mock-jwt-tenant-a',
      user: { id: 'usr_tenant_a', name: 'User A', role: 'developer', tenantId: 'ten_alpha' },
    });

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_alpha', name: 'Project Alpha', tenantId: 'ten_alpha', createdAt: '2026-09-22T00:00:00Z' }];
      }
      if (path.includes('/nodes')) {
        return { items: [], total: 0 };
      }
      return {};
    });

    vi.spyOn(projectObsModule, 'fetchProjects').mockResolvedValue([
      { id: 'prj_alpha', name: 'Project Alpha', tenantId: 'ten_alpha', createdAt: '2026-09-22T00:00:00Z' },
    ]);
    vi.spyOn(projectObsModule, 'fetchProjectWorkspaces').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedRuns').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedApprovals').mockResolvedValue([
      {
        id: 'appr_stale_01',
        projectId: 'prj_alpha',
        decision: 'pending',
        actionType: 'run_dispatch',
        riskScore: 20,
        createdAt: '2026-09-22T00:00:00Z',
        policyFingerprint: 'fp-1',
        command: 'echo test',
        status: 'pending',
        expiresAt: new Date(Date.now() + 100000).toISOString(),
        actionDigest: 'dig-1',
        riskLevel: 'L1',
      } as any,
    ]);

    // Deferred promise for decideApproval
    let rejectApprovalMutation: ((err: any) => void) | null = null;
    const approvalDeferred = new Promise<any>((_, reject) => {
      rejectApprovalMutation = reject;
    });
    approvalDeferred.catch(() => {});
    vi.spyOn(kernelMutationsModule, 'decideApproval').mockReturnValue(approvalDeferred);

    let capturedUnauthorizedCallback: ((prob: any) => void) | null = null;
    vi.spyOn(clientModule, 'onUnauthorized').mockImplementation((cb: any) => {
      capturedUnauthorizedCallback = cb;
    });

    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    hasCb2.mockReturnValue(false);

    // Switch to approvals tab
    const tabs = Array.from(container.querySelectorAll('button'));
    const apprTab = tabs.find((b) => b.textContent?.includes('승인'));
    expect(apprTab).toBeDefined();
    await act(async () => {
      apprTab?.click();
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // Click reject button
    const rejectBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('반려')
    );
    expect(rejectBtn).toBeDefined();
    await act(async () => {
      rejectBtn?.click();
    });

    // 2. WHILE IN-FLIGHT: 401 unauthorized occurs
    expect(capturedUnauthorizedCallback).not.toBeNull();
    await act(async () => {
      capturedUnauthorizedCallback!({ code: 'AUTH-0050', detail: 'Token expired during mutation' });
      await new Promise((r) => setTimeout(r, 50));
    });

    // Verify logged out
    expect(container.querySelector('[data-testid="login-error-alert"]')).not.toBeNull();

    // 3. Late rejection of the in-flight mutation promise
    await act(async () => {
      try {
        rejectApprovalMutation!({
          problem: { detail: 'Old tenant DB unreachable', code: 'DB-500', traceId: 'trc-123' },
        });
      } catch {
        // Expected
      }
    });

    // Verify actionError banner is NOT shown!
    expect(container.querySelector('[data-testid="app-global-action-error"]')).toBeNull();
    expect(container.textContent).not.toContain('Old tenant DB unreachable');
  });
});
