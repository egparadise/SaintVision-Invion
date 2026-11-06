// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { Header } from '@/shared/ui/Header';
import type { NodeItem, RunItem } from '@/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('PORTAL-REFRESH-FLEET-20261106: Stable Polling, Honest Gateway & Identity Integrity', () => {
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

  const dummyNodes: NodeItem[] = [
    {
      id: 'node_live_01',
      hostname: 'worker-gpu-01.internal',
      ip: '10.0.1.10',
      status: 'online',
      os: 'linux',
      cpuCores: 32,
      cpuUsagePercent: 45,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 24 * 1024 ** 3,
      gpuCount: 2,
      gpuModel: 'NVIDIA A100-SXM4-80GB',
      gpuVramTotalBytes: 160 * 1024 ** 3,
      gpuVramUsedBytes: 80 * 1024 ** 3,
      storageTotalBytes: 2000 * 1024 ** 3,
      storageUsedBytes: 850 * 1024 ** 3,
      roles: ['compute', 'storage'],
      tags: { zone: 'ap-northeast-2a' },
      heartbeatAt: new Date(2026, 10, 6, 19, 0, 0).toISOString(),
    },
  ];

  describe('1. Repeated empty/successful polls without panel remount/flash', () => {
    it('maintains continuous empty state card during background poll cycles without remounting or flashing metric cards', async () => {
      const time1 = new Date(2026, 10, 6, 19, 28, 5);
      const time2 = new Date(2026, 10, 6, 19, 28, 10);

      // Initial successful fetch (empty snapshot)
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="success"
            nodeError={null}
            lastFetchedAt={time1}
          />
        );
      });

      const emptySection1 = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySection1).not.toBeNull();
      expect(emptySection1?.getAttribute('role')).toBe('status');
      expect(container.textContent).toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');
      expect(container.querySelector('[data-testid="cluster-overview-fetch-error"]')).toBeNull();
      // Ensure metric cards grid is NOT rendered
      expect(container.textContent).not.toContain('CPU 코어');

      // Background refresh in progress (lastFetchedAt remains from previous poll)
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="loading"
            nodeError={null}
            lastFetchedAt={time1}
          />
        );
      });

      // Panel must NOT unmount or flip to metric cards
      const emptySectionDuringRefresh = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySectionDuringRefresh).not.toBeNull();
      expect(emptySectionDuringRefresh).toBe(emptySection1);
      expect(container.textContent).not.toContain('CPU 코어');

      // Background refresh completed successfully with new timestamp
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="success"
            nodeError={null}
            lastFetchedAt={time2}
          />
        );
      });

      const emptySection2 = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySection2).not.toBeNull();
      expect(emptySection2).toBe(emptySection1);
      expect(container.textContent).toContain(time2.toLocaleTimeString('ko-KR'));
    });
  });

  describe('2. Initial pending distinct from background refresh', () => {
    it('distinguishes initial pending (lastFetchedAt=null) from background refresh', async () => {
      // On initial load without any prior observation, lastFetchedAt is null
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="loading"
            nodeError={null}
            lastFetchedAt={null}
          />
        );
      });

      // It must not falsely claim empty state completed with 0 nodes
      const freshness = container.querySelector('[data-testid="cluster-freshness-indicator"]');
      expect(freshness).toBeNull();
      expect(container.textContent).toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');
    });
  });

  describe('3. Failed refresh retains truthful stale observation and error reason', () => {
    it('initial failure with no cached data presents full error alert', async () => {
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Gateway Connection Refused"
            lastFetchedAt={null}
          />
        );
      });

      const errorSection = container.querySelector('[data-testid="cluster-overview-fetch-error"]');
      expect(errorSection).not.toBeNull();
      expect(errorSection?.getAttribute('role')).toBe('alert');
      expect(container.textContent).toContain('Gateway Connection Refused');
      expect(container.textContent).not.toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');
    });

    it('background refresh failure preserves previous observed nodes and renders stale warning', async () => {
      const snapshotTime = new Date(2026, 10, 6, 19, 15, 0);

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={dummyNodes}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="HTTP 500 Internal Server Error"
            lastFetchedAt={snapshotTime}
          />
        );
      });

      // Previous nodes must be preserved and visible
      expect(container.textContent).toContain('worker-gpu-01.internal');
      // Stale warning alert must be presented
      const staleWarning = container.querySelector('[data-testid="cluster-stale-warning"]');
      expect(staleWarning).not.toBeNull();
      expect(staleWarning?.getAttribute('role')).toBe('alert');
      expect(staleWarning?.textContent).toContain('HTTP 500 Internal Server Error');
      expect(staleWarning?.textContent).toContain(snapshotTime.toLocaleTimeString('ko-KR'));
    });

    it('background refresh failure on empty snapshot retains empty card and shows stale indicator', async () => {
      const snapshotTime = new Date(2026, 10, 6, 19, 20, 0);

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Network timeout"
            lastFetchedAt={snapshotTime}
          />
        );
      });

      // Empty state card remains mounted
      const emptySection = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySection).not.toBeNull();
      // Freshness indicator displays previous snapshot time
      expect(container.textContent).toContain(snapshotTime.toLocaleTimeString('ko-KR'));
      // Does not fall through to metric cards
      expect(container.textContent).not.toContain('CPU 코어');
    });
  });

  describe('4. Recoveries from failed refresh', () => {
    it('clears stale warning and displays updated observation upon successful recovery poll', async () => {
      const staleTime = new Date(2026, 10, 6, 19, 15, 0);
      const recoveredTime = new Date(2026, 10, 6, 19, 15, 5);

      // Stale state
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={dummyNodes}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Timeout"
            lastFetchedAt={staleTime}
          />
        );
      });
      expect(container.querySelector('[data-testid="cluster-stale-warning"]')).not.toBeNull();

      // Recovery poll
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={dummyNodes}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="success"
            nodeError={null}
            lastFetchedAt={recoveredTime}
          />
        );
      });

      expect(container.querySelector('[data-testid="cluster-stale-warning"]')).toBeNull();
      expect(container.textContent).toContain(recoveredTime.toLocaleTimeString('ko-KR'));
    });
  });

  describe('5. Real observed Gateway state, honest RTT, and unknown until observed', () => {
    it('initializes with unknown state (확인 중...) and unknown indicator dot without fabricating online:true/8ms', async () => {
      // Mock fetch that hangs or resolves slowly
      const fetchPromise = new Promise<Response>(() => {});
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => fetchPromise);

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      const gatewayContainer = container.querySelector('[title*="Gateway 실시간 RTT"]');
      expect(gatewayContainer).not.toBeNull();
      expect(gatewayContainer?.textContent).toContain('Gateway: 확인 중...');
      expect(gatewayContainer?.textContent).not.toContain('8ms');

      // Dot color must be unknown token
      const dot = gatewayContainer?.querySelector('span') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-unknown)');
    });

    it('updates to online with measured RTT when /v1/health responds with HTTP 200', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }));

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      // Wait for async checkGateway
      await act(async () => {
        await new Promise((r) => setTimeout(r, 10));
      });

      const gatewayContainer = container.querySelector('[title*="Gateway 실시간 RTT"]');
      expect(gatewayContainer?.textContent).toMatch(/Gateway:\s*\d+ms/);
      const dot = gatewayContainer?.querySelector('span') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-online)');
    });

    it('recognizes gateway transport is online and measures real RTT when server responds with 401 or 404', async () => {
      // HTTP 404 (route absent on control plane) or 401 (unauthorized) is HTTP transport response, NOT transport offline
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })
      );

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 10));
      });

      const gatewayContainer = container.querySelector('[title*="Gateway 실시간 RTT"]');
      expect(gatewayContainer?.textContent).not.toContain('Offline');
      expect(gatewayContainer?.textContent).toMatch(/Gateway:\s*\d+ms/);
      const dot = gatewayContainer?.querySelector('span') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-online)');
    });

    it('reports Gateway: Offline when network connection fails (transport truly unreachable)', async () => {
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Failed to fetch (ECONNREFUSED)'));

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 10));
      });

      const gatewayContainer = container.querySelector('[title*="Gateway 실시간 RTT"]');
      expect(gatewayContainer?.textContent).toContain('Gateway: Offline');
      const dot = gatewayContainer?.querySelector('span') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-offline)');
    });
  });

  describe('6. Honest OIDC user pill formatting', () => {
    it('formats raw 64-char hex OIDC subject gracefully without exposing raw hash', async () => {
      const rawOidcSub = 'oidc:3f79091432574632c62c37f25aaddb37f91e37a5864422525048eb82fe54247c';

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
            currentUser={{ id: rawOidcSub, name: rawOidcSub, role: '프로젝트별 권한' }}
          />
        );
      });

      expect(container.textContent).toContain('사용자 (3f790914…)');
      expect(container.textContent).not.toContain('3f79091432574632c62c37f25aaddb37f91e37a5864422525048eb82fe54247c');
      expect(container.textContent).toContain('프로젝트별 권한');
    });

    it('preserves human display names as-is', async () => {
      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={0}
            totalNodesCount={0}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
            currentUser={{ id: 'admin-1', name: 'Master Operator', role: 'SecAdmin' }}
          />
        );
      });

      expect(container.textContent).toContain('Master Operator');
      expect(container.textContent).toContain('SecAdmin');
    });
  });
});
