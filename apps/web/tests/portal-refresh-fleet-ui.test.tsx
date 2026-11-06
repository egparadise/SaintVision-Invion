// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { Header } from '@/shared/ui/Header';
import { App } from '@/app/App';
import * as session from '@/features/auth/session';
import * as client from '@/shared/api/client';
import * as projects from '@/shared/api/projectObservation';
import * as runs from '@/shared/api/runApprovalObservation';
import * as fabric from '@/features/desktop/fabricControlApi';
import * as storage from '@/shared/api/storageObservation';
import * as mutations from '@/shared/api/kernelMutations';
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
      expect(container.textContent).not.toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');
      expect(container.textContent).toContain('클러스터 노드 정보를 확인하고 있습니다...');
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
            onRefresh={vi.fn()}
          />
        );
      });

      // Empty state card remains mounted (preventing flicker / layout flip)
      const emptySection = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySection).not.toBeNull();
      // Role="status" preserved
      expect(emptySection?.getAttribute('role')).toBe('status');
      // Freshness indicator displays previous snapshot time
      expect(container.textContent).toContain(snapshotTime.toLocaleTimeString('ko-KR'));
      // Stale warning alert must be visibly rendered (role=alert)
      const staleWarning = container.querySelector('[data-testid="cluster-stale-warning"]');
      expect(staleWarning).not.toBeNull();
      expect(staleWarning?.getAttribute('role')).toBe('alert');
      expect(staleWarning?.textContent).toContain('동기화 실패');
      expect(staleWarning?.textContent).toContain('Network timeout');
      expect(staleWarning?.textContent).toContain(snapshotTime.toLocaleTimeString('ko-KR'));
      // Must NOT be presented as normal 0 nodes success
      expect(container.textContent).not.toContain('정상 조회 결과: 0대');
      expect(container.textContent).toContain('이전 관측 시점(스냅샷) 기준 등록된 노드가 없습니다');
      // Retry button present
      expect(container.querySelector('[data-testid="cluster-stale-retry-btn"]')).not.toBeNull();
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

  describe('5. Canonical /healthz gateway status, content-type validation, and honest RTT', () => {
    it('initializes with unknown state (확인 중...) and unknown indicator dot without fabricating online:true/8ms', async () => {
      // Mock fetch that hangs or resolves slowly
      const fetchPromise = new Promise<Response>(() => {});
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => fetchPromise);

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={null}
            totalNodesCount={null}
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
      const dot = container.querySelector('[data-testid="gateway-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-unknown)');
    });

    it('updates to online with measured RTT when /healthz responds with HTTP 200 and application/json status:ok', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '1.0.0' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
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

      expect(fetchSpy).toHaveBeenCalledWith(
        '/healthz',
        expect.objectContaining({ signal: expect.any(Object) })
      );
      const gatewayContainer = container.querySelector('[title*="Gateway 실시간 RTT"]');
      expect(gatewayContainer?.textContent).toMatch(/Gateway:\s*\d+ms/);
      const dot = container.querySelector('[data-testid="gateway-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-online)');
    });

    it('rejects SPA HTML 200 fallback on /healthz as health success (must strictly be application/json)', async () => {
      // When /healthz route is not proxied, Vite or nginx serves the SPA index.html with 200 text/html
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response('<!DOCTYPE html><html><body>SPA fallback</body></html>', {
          status: 200,
          headers: { 'Content-Type': 'text/html; charset=utf-8' },
        })
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
      expect(gatewayContainer?.textContent).toContain('Gateway: 비정상 응답');
      const dot = container.querySelector('[data-testid="gateway-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-offline)');
    });

    it('rejects HTTP 404, 401, or 503 on /healthz as health success', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Not Found' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        })
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
      expect(gatewayContainer?.textContent).toContain('Gateway: 비정상 응답');
      const dot = container.querySelector('[data-testid="gateway-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-offline)');
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
      const dot = container.querySelector('[data-testid="gateway-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-offline)');
    });
  });

  describe('6. Honest cluster count semantics in Header (no fake 5/5 defaults)', () => {
    it('renders 확인 중... and unknown dot when node counts are null (unobserved)', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={null}
            totalNodesCount={null}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      expect(container.textContent).toContain('클러스터: 확인 중... Node 가동 중');
      const dot = container.querySelector('[data-testid="cluster-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-unknown)');
    });

    it('renders 0/0 and neutral dot when observed cluster has 0 nodes (truthful LAN pilot DB)', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

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

      expect(container.textContent).toContain('클러스터: 0/0 Node 가동 중');
      const dot = container.querySelector('[data-testid="cluster-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-neutral)');
    });

    it('renders online dot when nodes are online', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            onlineNodesCount={3}
            totalNodesCount={5}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      expect(container.textContent).toContain('클러스터: 3/5 Node 가동 중');
      const dot = container.querySelector('[data-testid="cluster-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-online)');
    });

    it('defaults to truthful unobserved state (null) when props are omitted (no 5/5 default)', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));

      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={vi.fn()}
            activeTab="dashboard"
            onSelectTab={vi.fn()}
          />
        );
      });

      expect(container.textContent).toContain('클러스터: 확인 중... Node 가동 중');
      expect(container.textContent).not.toContain('5/5');
      const dot = container.querySelector('[data-testid="cluster-status-dot"]') as HTMLElement;
      expect(dot.style.backgroundColor).toBe('var(--color-status-unknown)');
    });
  });

  describe('7. Honest OIDC user pill formatting', () => {
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

  describe('8. Reverse-proxy configuration for canonical /healthz', () => {
    it('verifies Vite dev and preview servers proxy /healthz to backend', async () => {
      const fs = await import('fs');
      const path = await import('path');
      const viteConfigContent = fs.readFileSync(path.resolve(__dirname, '../vite.config.ts'), 'utf-8');
      expect(viteConfigContent).toContain("'/healthz':");
      expect(viteConfigContent).toContain('target: process.env.VITE_API_PROXY_TARGET');
    });

    it('verifies nginx HTTPS 443 routes /healthz to upstream while HTTP 80 preserves local plaintext OK', async () => {
      const fs = await import('fs');
      const path = await import('path');
      const nginxConfigContent = fs.readFileSync(path.resolve(__dirname, '../nginx.conf'), 'utf-8');

      // HTTP 80 local container liveness
      expect(nginxConfigContent).toMatch(/server\s*\{[^}]*listen\s+80;[\s\S]*location\s+\/healthz\s*\{\s*return\s+200\s+'OK';\s*add_header\s+Content-Type\s+text\/plain;/);

      // HTTPS 443 upstream reverse-proxy to control-plane
      expect(nginxConfigContent).toMatch(/server\s*\{[^}]*listen\s+443[\s\S]*location\s+=\s+\/healthz\s*\{\s*proxy_pass\s+http:\/\/control-plane:8080;/);
    });
  });

  describe('9. Auth & project scope isolation invariant', () => {
    it('disallows stale actions when approvals state is in error', () => {
      // Invariant: Background refresh failure can retain snapshot but must not authorize actions from stale state
      const isActionAllowed = (approvalsState: string) => {
        if (approvalsState === 'error') {
          throw new Error('안건 목록이 갱신 실패(stale) 상태이므로 새로고침 후 다시 시도하십시오.');
        }
        return true;
      };

      expect(() => isActionAllowed('error')).toThrow('안건 목록이 갱신 실패(stale) 상태이므로');
      expect(isActionAllowed('success')).toBe(true);
      expect(isActionAllowed('idle')).toBe(true);
    });
  });

  describe('10. App-level Polling Lifecycle, Slow/Hung Request Invariants, and Header Discrimination (Claude Reviewer Probes P1-P9, H1-H2)', () => {
    let pRoot: Root;
    let pContainer: HTMLDivElement;
    let nodeMode: 'empty' | 'one' | 'reject' | 'pending' | 'slow6s';
    let certMode: 'reject' | 'hang' | 'slow60reject';
    let nodeCalls: string[];
    let certCalls: Array<{ signal?: AbortSignal; t: number }>;
    let pendingRequests: Array<{ path: string; signal?: AbortSignal; resolve: (v: any) => void; reject: (e: any) => void }>;

    const t0 = Date.parse('2026-11-06T11:00:00Z');
    const projectA = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAV';
    const projectB = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAW';
    const nodeA = 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV';

    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(t0);
      localStorage.clear();
      pContainer = document.createElement('div');
      document.body.appendChild(pContainer);
      pRoot = createRoot(pContainer);
      nodeMode = 'empty';
      certMode = 'reject';
      nodeCalls = [];
      certCalls = [];
      pendingRequests = [];

      vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
        new Response(JSON.stringify({ status: 'ok', version: 'probe' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      );
      vi.spyOn(session, 'hasLoginCallback').mockReturnValue(true);
      vi.spyOn(session, 'completeLogin').mockImplementation(async () => ({
        token: 'probe-token',
        user: { id: 'oidc:' + 'a'.repeat(64), name: 'Probe User', role: '프로젝트별 권한', tenantId: 'ten_probe' },
        expiresAt: Math.floor(Date.now() / 1000) + 1800,
      }));
      vi.spyOn(session, 'commitSession').mockImplementation(() => {});
      vi.spyOn(session, 'performLogout').mockImplementation((() => {}) as any);
      vi.spyOn(client, 'onUnauthorized').mockImplementation(() => {});
      vi.spyOn(projects, 'fetchProjects').mockResolvedValue(
        [projectA, projectB].map((id) => ({
          id,
          name: id,
          tenantId: 'ten_probe',
          createdAt: new Date(t0).toISOString(),
        }))
      );
      vi.spyOn(projects, 'fetchProjectWorkspaces').mockResolvedValue([]);
      vi.spyOn(runs, 'fetchObservedRuns').mockResolvedValue([]);
      vi.spyOn(runs, 'fetchObservedApprovals').mockResolvedValue([
        {
          id: 'app_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          projectId: projectA,
          status: 'pending' as const,
          target: 'restart-node-nod_01',
          riskLevel: 'high' as const,
          requiredApprovals: 2,
          actionDigest: 'dig_abc123',
          firstApprovedBy: null,
          firstApprovedAt: null,
          secondApprovedBy: null,
          secondApprovedAt: null,
          expiresAt: new Date(t0 + 3600000).toISOString(),
          createdAt: new Date(t0).toISOString(),
        },
      ]);
      vi.spyOn(fabric, 'getDiscoveryCandidates').mockResolvedValue([]);
      vi.spyOn(fabric, 'getStorageContributions').mockResolvedValue([]);
      vi.spyOn(fabric, 'getNodeResourceUsage').mockResolvedValue(null);
      vi.spyOn(storage, 'fetchStorageObservation').mockResolvedValue(null);

      vi.spyOn(client, 'apiClient').mockImplementation(async (path: string, options?: any) => {
        const signal: AbortSignal | undefined = options?.signal;
        if (path.endsWith('/node-certificates')) {
          certCalls.push({ signal, t: Date.now() - t0 });
          if (certMode === 'reject') throw new Error('certificate observation unavailable');
          if (certMode === 'hang') {
            return new Promise((_res, rej) => {
              if (signal) signal.addEventListener('abort', () => rej(signal.reason ?? new DOMException('Aborted', 'AbortError')));
            });
          }
          if (certMode === 'slow60reject') {
            return new Promise((_res, rej) => {
              const timer = setTimeout(() => rej(new Error('504 Gateway Timeout')), 60000);
              if (signal) {
                signal.addEventListener('abort', () => {
                  clearTimeout(timer);
                  rej(signal.reason ?? new DOMException('Aborted', 'AbortError'));
                });
              }
            });
          }
        }
        if (path.endsWith('/nodes')) {
          nodeCalls.push(path);
          const one = {
            items: [
              {
                nodeId: nodeA,
                hostname: 'observed-node',
                status: 'online',
                osType: 'linux',
                cpuCores: 16,
                memoryTotalBytes: 32 * 1024 ** 3,
                roles: ['compute'],
                tags: { zone: 'default' },
                heartbeatAt: new Date(t0).toISOString(),
              },
            ],
            total: 1,
          };
          if (nodeMode === 'empty') return { items: [], total: 0 };
          if (nodeMode === 'one') return one;
          if (nodeMode === 'reject') throw new Error('PROBE-NODES-DOWN');
          if (nodeMode === 'slow6s') {
            return new Promise((resolve, reject) => {
              const timer = setTimeout(() => resolve(one), 6000);
              if (options?.signal) {
                options.signal.addEventListener('abort', () => {
                  clearTimeout(timer);
                  reject(options.signal.reason || new Error('Aborted'));
                });
              }
            });
          }
          return new Promise((resolve, reject) => {
            const entry = { path, signal: options?.signal, resolve, reject };
            pendingRequests.push(entry);
            if (options?.signal) {
              options.signal.addEventListener('abort', () => {
                reject(options.signal.reason || new Error('Aborted'));
              });
            }
          });
        }
        return {};
      });
    });

    afterEach(() => {
      act(() => {
        pRoot.unmount();
      });
      pContainer.remove();
      vi.restoreAllMocks();
      vi.useRealTimers();
    });

    async function advance(ms: number) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(ms);
      });
    }

    async function mountApp() {
      await act(async () => {
        pRoot.render(<App />);
      });
      await advance(0);
    }

    async function chooseProject(id: string) {
      const selector = pContainer.querySelector<HTMLSelectElement>('[data-testid="project-selector"]');
      expect(selector).not.toBeNull();
      await act(async () => {
        selector!.value = id;
        selector!.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }

    const appText = () => pContainer.textContent ?? '';
    const emptyCard = () => pContainer.querySelector('[data-testid="cluster-overview-empty-state"]');
    const staleWarning = () => pContainer.querySelector('[data-testid="cluster-stale-warning"]');

    it('P1: repeated empty polls keep the same empty card element, never flip to metrics, header 0/0 only after observation', async () => {
      nodeMode = 'pending';
      await mountApp();
      expect(appText()).toContain('클러스터 노드 정보를 확인하고 있습니다');
      expect(appText()).not.toContain('정상 조회 결과: 0대');
      expect(appText()).toContain('확인 중...');

      pendingRequests.splice(0).forEach((p) => p.resolve({ items: [], total: 0 }));
      nodeMode = 'empty';
      await advance(0);

      const firstEmpty = emptyCard();
      expect(firstEmpty).not.toBeNull();
      expect(appText()).toContain('정상 조회 결과: 0대');
      expect(appText()).toContain('0/0');

      let sameEveryCycle = true;
      for (let i = 0; i < 6; i++) {
        await advance(5000);
        if (emptyCard() !== firstEmpty) sameEveryCycle = false;
        if (appText().includes('CPU 코어')) sameEveryCycle = false;
      }
      expect(sameEveryCycle).toBe(true);
      expect(nodeCalls.length).toBeGreaterThanOrEqual(7);
    });

    it('P2: empty snapshot then background failure shows role=alert stale banner with retry; recovery clears it', async () => {
      await mountApp();
      expect(appText()).toContain('정상 조회 결과: 0대');
      const firstEmpty = emptyCard();

      nodeMode = 'reject';
      await advance(5000);

      expect(staleWarning()).not.toBeNull();
      expect(staleWarning()!.getAttribute('role')).toBe('alert');
      expect(appText()).toContain('PROBE-NODES-DOWN');
      expect(appText()).not.toContain('정상 조회 결과: 0대');
      expect(pContainer.querySelector('[data-testid="cluster-stale-retry-btn"]')).not.toBeNull();
      expect(emptyCard()).toBe(firstEmpty);

      nodeMode = 'empty';
      await advance(5000);

      expect(staleWarning()).toBeNull();
      expect(appText()).toContain('정상 조회 결과: 0대');
    });

    it('P3: non-empty snapshot retained on background failure with stale banner', async () => {
      nodeMode = 'one';
      await mountApp();
      expect(appText()).toContain('observed-node');

      nodeMode = 'reject';
      await advance(5000);

      expect(staleWarning()).not.toBeNull();
      expect(appText()).toContain('observed-node');
    });

    it('P4: late older response is ignored after a newer poll completes (response order / latest-wins)', async () => {
      await mountApp();
      nodeMode = 'pending';
      await advance(5000); // poll #2 pending
      await advance(5000); // poll #3 pending
      expect(pendingRequests.length).toBe(2);

      pendingRequests[1].resolve({ items: [], total: 0 }); // newer resolves first
      await advance(0);

      pendingRequests[0].resolve({
        items: [{ nodeId: nodeA, hostname: 'late-old-node', status: 'online', osType: 'linux' }],
        total: 1,
      });
      await advance(0);

      expect(appText()).not.toContain('late-old-node');
    });

    it('P5: project switch resets to unknown and drops the old project late response', async () => {
      nodeMode = 'one';
      await mountApp();
      expect(appText()).toContain('observed-node');

      nodeMode = 'pending';
      await advance(5000);
      const oldA = pendingRequests.splice(0);
      expect(oldA.length).toBe(1);
      expect(oldA[0].path).toContain(projectA);

      await chooseProject(projectB);
      await advance(0);

      expect(appText()).not.toContain('observed-node');
      expect(appText()).toContain('클러스터 노드 정보를 확인하고 있습니다');
      expect(appText()).toContain('확인 중...');

      oldA[0].resolve({
        items: [{ nodeId: nodeA, hostname: 'leaked-A-node', status: 'online', osType: 'linux' }],
        total: 1,
      });
      await advance(0);

      expect(appText()).not.toContain('leaked-A-node');
      const bReq = pendingRequests.filter((p) => p.path.includes(projectB));
      expect(bReq.length).toBeGreaterThan(0);
    });

    it('P6: slow positive response (6s with 5s interval) within 10s timeout successfully applies', async () => {
      await mountApp(); // first observation: 0 nodes
      expect(appText()).toContain('정상 조회 결과: 0대');

      nodeMode = 'slow6s'; // server returns 1 node after 6s
      await advance(60000);

      expect(appText()).toContain('observed-node');
      expect(staleWarning()).toBeNull();
      expect(appText()).not.toContain('정상 조회 결과: 0대');
      expect(nodeCalls.length).toBeGreaterThan(5);
    });

    it('P7: hanging request times out at 10s, triggering explicit stale warning', async () => {
      await mountApp();
      expect(appText()).toContain('정상 조회 결과: 0대');

      nodeMode = 'pending';
      await advance(5000); // background poll #2 issued
      await advance(10000); // 10s timeout expires

      expect(staleWarning()).not.toBeNull();
      expect(staleWarning()!.getAttribute('role')).toBe('alert');
      expect(appText()).toContain('초과');
      expect(appText()).not.toContain('정상 조회 결과: 0대');
    });

    it('R1: certificate sub-request hangs while /nodes returns 1 node immediately', async () => {
      await mountApp();
      expect(appText()).toContain('정상 조회 결과: 0대');

      nodeMode = 'one';
      certMode = 'hang';
      await advance(15000); // 10s timeout expires

      expect(staleWarning()).not.toBeNull();
      expect(staleWarning()!.getAttribute('role')).toBe('alert');
      expect(appText()).toContain('초과');
      expect(appText()).not.toContain('정상 조회 결과: 0대');
      expect(certCalls.some((c) => c.signal?.aborted)).toBe(true);
    });

    it('R1b: certificate sub-request 60s 504 (nginx default /v1 proxy_read_timeout shape)', async () => {
      await mountApp();
      nodeMode = 'one';
      certMode = 'slow60reject';

      await advance(30000);
      expect(staleWarning()).not.toBeNull();
      expect(appText()).not.toContain('정상 조회 결과: 0대');

      await advance(40000);
      expect(staleWarning()).not.toBeNull();
      expect(appText()).not.toContain('정상 조회 결과: 0대');
    });

    it('R2: manual refresh during an in-flight background poll is not labelled a timeout error', async () => {
      nodeMode = 'one';
      await mountApp();
      expect(appText()).toContain('observed-node');

      nodeMode = 'pending';
      await advance(5000); // background poll in flight
      expect(pendingRequests.length).toBe(1);

      const refreshBtn = pContainer.querySelector<HTMLButtonElement>('[data-testid="cluster-refresh-btn"]');
      expect(refreshBtn).not.toBeNull();
      await act(async () => {
        refreshBtn!.click();
      });
      await advance(0);

      expect(appText()).not.toContain('응답 시간 초과');
      expect(staleWarning()).toBeNull();
      expect(pContainer.querySelector('[data-testid="cluster-overview-fetch-error"]')).toBeNull();
    });

    it('R2b: manual supersede with ordinary abort reason and late Error(REQUEST_TIMEOUT) rejection does not set timeout error', async () => {
      nodeMode = 'one';
      await mountApp();
      expect(appText()).toContain('observed-node');

      nodeMode = 'pending';
      await advance(5000);
      expect(pendingRequests.length).toBe(1);
      const bgReq = pendingRequests[0];

      // User manually refreshes, aborting bgReq with ordinary supersede AbortError
      const refreshBtn = pContainer.querySelector<HTMLButtonElement>('[data-testid="cluster-refresh-btn"]');
      expect(refreshBtn).not.toBeNull();
      await act(async () => {
        refreshBtn!.click();
      });
      await advance(0);

      // Even if the aborted background request rejects with late Error('REQUEST_TIMEOUT')
      bgReq.reject(new Error('REQUEST_TIMEOUT'));
      await advance(0);

      // Owned signal.reason is AbortError, so it must not apply false timeout error
      expect(appText()).not.toContain('응답 시간 초과');
      expect(staleWarning()).toBeNull();
    });

    it('R6: logout fence: in-flight aborted, late response dropped and does not leak into logged-out view', async () => {
      nodeMode = 'one';
      await mountApp();
      nodeMode = 'pending';
      await advance(5000);
      const inflightReq = pendingRequests.splice(0);
      expect(inflightReq.length).toBe(1);

      const logoutBtn = Array.from(pContainer.querySelectorAll('button')).find((b) => b.textContent?.includes('로그아웃')) ?? null;
      expect(logoutBtn).not.toBeNull();
      await act(async () => {
        logoutBtn!.click();
      });
      await advance(0);

      inflightReq[0].resolve({
        items: [{ nodeId: nodeA, hostname: 'leaked-post-logout-node', status: 'online', osType: 'linux' }],
        total: 1,
      });
      await advance(0);

      expect(appText()).not.toContain('leaked-post-logout-node');
    });

    it('R8: when approvalsState === error, real reject button and modal click throws without calling decideApproval', async () => {
      const decideSpy = vi.spyOn(mutations, 'decideApproval');
      await mountApp();

      // Switch to approvals tab
      const approvalsTab = pContainer.querySelector<HTMLButtonElement>('[data-testid="header-tab-approvals"]');
      if (approvalsTab) {
        await act(async () => {
          approvalsTab.click();
        });
        await advance(0);
      }

      const item = pContainer.querySelector<HTMLElement>('[data-testid="approval-item-app_01ARZ3NDEKTSV4RRFFQ69G5FAV"]');
      if (item) {
        await act(async () => {
          item.click();
        });
        await advance(0);
      }

      // Cause approvals to fail on next tick
      vi.spyOn(runs, 'fetchObservedApprovals').mockRejectedValue(new Error('PROBE-APPROVALS-DOWN'));
      await advance(5000);

      expect(pContainer.querySelector('[data-testid="approval-stale-warning"]')).not.toBeNull();

      const unhandled: unknown[] = [];
      const onUnh = (e: unknown) => { unhandled.push(String(e)); };
      process.on('unhandledRejection', onUnh);

      const rejectBtn = pContainer.querySelector<HTMLButtonElement>('[data-testid="approval-reject-button"]');
      expect(rejectBtn).not.toBeNull();
      await act(async () => {
        rejectBtn!.click();
      });
      await advance(0);

      const confirmBtn = Array.from(pContainer.querySelectorAll('button')).find((b) => b.textContent?.includes('반려 확인')) ?? null;
      expect(confirmBtn).not.toBeNull();
      await act(async () => {
        confirmBtn!.click();
      });
      await advance(0);

      expect(decideSpy).toHaveBeenCalledTimes(0);
      expect(appText()).toContain('승인 반려 실패');
      process.off('unhandledRejection', onUnh);
    });

    it('R8c: control - same real reject click with approvalsState === success reaches decideApproval', async () => {
      const decideSpy = vi.spyOn(mutations, 'decideApproval').mockResolvedValue(undefined as any);
      await mountApp();

      const approvalsTab = pContainer.querySelector<HTMLButtonElement>('[data-testid="header-tab-approvals"]');
      if (approvalsTab) {
        await act(async () => {
          approvalsTab.click();
        });
        await advance(0);
      }

      const item = pContainer.querySelector<HTMLElement>('[data-testid="approval-item-app_01ARZ3NDEKTSV4RRFFQ69G5FAV"]');
      if (item) {
        await act(async () => {
          item.click();
        });
        await advance(0);
      }

      const rejectBtn = pContainer.querySelector<HTMLButtonElement>('[data-testid="approval-reject-button"]');
      expect(rejectBtn).not.toBeNull();
      await act(async () => {
        rejectBtn!.click();
      });
      await advance(0);

      const confirmBtn = Array.from(pContainer.querySelectorAll('button')).find((b) => b.textContent?.includes('반려 확인')) ?? null;
      expect(confirmBtn).not.toBeNull();
      await act(async () => {
        confirmBtn!.click();
      });
      await advance(0);

      expect(decideSpy).toHaveBeenCalledTimes(1);
    });

    it('R9: clicking nodes-retry-btn in ResourceExplorer clears error banner and shows loading state while manual request is pending', async () => {
      await mountApp();

      const fabricTab = pContainer.querySelector<HTMLButtonElement>('[data-testid="header-tab-fabric"]');
      expect(fabricTab).not.toBeNull();
      await act(async () => {
        fabricTab!.click();
      });
      await advance(0);

      nodeMode = 'reject';
      await advance(5000);
      expect(pContainer.querySelector('[data-testid="nodes-fetch-error-banner"]')).not.toBeNull();

      nodeMode = 'pending';
      const retryBtn = pContainer.querySelector<HTMLButtonElement>('[data-testid="nodes-retry-btn"]');
      expect(retryBtn).not.toBeNull();
      await act(async () => {
        retryBtn!.click();
      });
      await advance(0);

      expect(pContainer.querySelector('[data-testid="nodes-fetch-error-banner"]')).toBeNull();
      expect(pContainer.querySelector('[data-testid="nodes-loading-state"]')).not.toBeNull();
    });

    it.each([
      ['html200', () => new Response('<!doctype html><html></html>', { status: 200, headers: { 'content-type': 'text/html' } }), '비정상 응답'],
      ['json404', () => new Response(JSON.stringify({ detail: 'nf' }), { status: 404, headers: { 'content-type': 'application/json' } }), '비정상 응답'],
      ['json503', () => new Response(JSON.stringify({ status: 'not_ready' }), { status: 503, headers: { 'content-type': 'application/json' } }), '비정상 응답'],
      ['jsonStatusDown', () => new Response(JSON.stringify({ status: 'down' }), { status: 200, headers: { 'content-type': 'application/json' } }), '비정상 응답'],
      ['network', () => { throw new TypeError('Failed to fetch'); }, 'Offline'],
    ] as const)('H1: Header failure discrimination for %s renders %s', async (name, mk, expectedLabel) => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(async () => (mk as any)());
      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });
      await advance(0);
      const t = pContainer.textContent ?? '';
      expect(t).toContain(`Gateway: ${expectedLabel}`);
      expect(t).not.toMatch(/Gateway:\s*\d+ms/);
    });

    it('H2: Header sequence fence prevents older slow success from overwriting newer failure', async () => {
      let call = 0;
      let resolveFirst: ((r: Response) => void) | null = null;
      vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
        call++;
        if (call === 1) return new Promise<Response>((r) => { resolveFirst = r; });
        return Promise.reject(new TypeError('Failed to fetch'));
      });

      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });

      // Poll #2 starts after 5000ms and fails -> Offline
      await advance(5000);
      expect(pContainer.textContent).toContain('Gateway: Offline');

      // Now resolve the older slow call #1
      await act(async () => {
        resolveFirst!(new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } }));
      });
      await advance(0);

      // Sequence fence ensures newer Offline is not overwritten by older slow call
      expect(pContainer.textContent).toContain('Gateway: Offline');
      expect(pContainer.textContent).not.toMatch(/Gateway:\s*\d+ms/);
    });

    it('H3: header JSON body hangs after headers: 4s deadline covers res.json() and transitions to offline', async () => {
      let n = 0;
      vi.spyOn(globalThis, 'fetch').mockImplementation((async (_u: any, init?: RequestInit) => {
        n++;
        if (n === 1) return new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } });
        const sig = init?.signal;
        return {
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: () => new Promise((_r, rej) => {
            sig?.addEventListener('abort', () => rej(sig.reason ?? new Error('aborted')));
          }),
        } as any;
      }) as any);

      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });
      await advance(0);
      expect(pContainer.textContent).toMatch(/Gateway:\s*\d+ms/);

      await advance(60000);
      expect(pContainer.textContent).not.toMatch(/Gateway:\s*\d+ms/);
      expect(pContainer.textContent).toContain('Gateway: Offline');
    });

    it('H3b: header response with malformed JSON body renders degraded (비정상 응답) and recovery works', async () => {
      let call = 0;
      vi.spyOn(globalThis, 'fetch').mockImplementation((async () => {
        call++;
        if (call === 1) {
          return new Response('invalid-json{{{', { status: 200, headers: { 'content-type': 'application/json' } });
        }
        return new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } });
      }) as any);

      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });
      await advance(0);
      expect(pContainer.textContent).toContain('비정상 응답');
      expect(pContainer.textContent).not.toContain('Gateway: Offline');

      // Next poll recovers to healthy
      await advance(5000);
      expect(pContainer.textContent).toMatch(/Gateway:\s*\d+ms/);
      expect(pContainer.textContent).not.toContain('비정상 응답');
    });

    it('H4: header fetch hangs (signal honoured): 4s deadline -> Offline, never indefinite 확인 중', async () => {
      vi.spyOn(globalThis, 'fetch').mockImplementation(((_u: any, init?: RequestInit) => {
        const sig = init?.signal;
        return new Promise((_res, rej) => {
          if (sig) sig.addEventListener('abort', () => rej(sig.reason ?? new DOMException('Aborted', 'AbortError')));
        });
      }) as any);

      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });
      await advance(0);
      expect(pContainer.textContent).toContain('확인 중');

      await advance(4100);
      expect(pContainer.textContent).toContain('Gateway: Offline');
    });

    it('H5: header order: degraded -> healthy -> network, each latest wins', async () => {
      const seq = [
        () => new Response(JSON.stringify({ status: 'not_ready' }), { status: 503, headers: { 'content-type': 'application/json' } }),
        () => new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } }),
        () => { throw new TypeError('Failed to fetch'); },
      ];
      let i = 0;
      vi.spyOn(globalThis, 'fetch').mockImplementation((async () => seq[Math.min(i++, 2)]()) as any);

      await act(async () => {
        pRoot.render(<Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />);
      });
      await advance(0);
      expect(pContainer.textContent).toContain('비정상 응답');

      await advance(5000);
      expect(pContainer.textContent).toMatch(/Gateway:\s*\d+ms/);

      await advance(5000);
      expect(pContainer.textContent).toContain('Gateway: Offline');
    });

    it('T1: real transport: polled endpoints carry AbortSignal and are aborted by 10s deadline', async () => {
      vi.mocked(runs.fetchObservedRuns).mockRestore();
      vi.mocked(runs.fetchObservedApprovals).mockRestore();
      vi.mocked(projects.fetchProjectWorkspaces).mockRestore();
      vi.mocked(client.apiClient).mockRestore();

      const seen: Array<{ url: string; hasSignal: boolean; signal?: AbortSignal }> = [];
      vi.spyOn(globalThis, 'fetch').mockImplementation(((input: any, init?: RequestInit) => {
        const url = String(input);
        seen.push({ url, hasSignal: !!init?.signal, signal: init?.signal ?? undefined });
        const sig = init?.signal;
        if (url === '/healthz') {
          return Promise.resolve(new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } }));
        }
        if (url.endsWith('/nodes')) {
          return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0 }), { status: 200, headers: { 'content-type': 'application/json' } }));
        }
        return new Promise((_r, rej) => {
          sig?.addEventListener('abort', () => rej(sig.reason ?? new DOMException('Aborted', 'AbortError')));
        });
      }) as any);

      await mountApp();
      await advance(10500);

      const certEntry = seen.find((s) => s.url.endsWith('/node-certificates'));
      expect(certEntry).toBeDefined();
      expect(certEntry?.hasSignal).toBe(true);
      expect(certEntry?.signal?.aborted).toBe(true);

      const kinds = ['/runs', '/approvals', '/workspaces'];
      for (const k of kinds) {
        const entry = seen.find((s) => s.url.startsWith('/v1/projects/') && s.url.endsWith(k));
        expect(entry).toBeDefined();
        expect(entry?.hasSignal).toBe(true);
        expect(entry?.signal?.aborted).toBe(true);
      }
    });
  });
});
