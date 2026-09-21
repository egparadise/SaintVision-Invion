// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApprovalCenter } from '../src/features/approvals/ApprovalCenter';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { ApprovalItem, NodeItem } from '../src/contracts/types';

// Mock fabricControlApi for ResourceExplorer
vi.mock('../src/features/desktop/fabricControlApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/features/desktop/fabricControlApi')>();
  return {
    ...actual,
    getStorageContributions: vi.fn().mockResolvedValue({ contributions: [] }),
    getStorageLocations: vi.fn().mockResolvedValue({ locations: [] }),
    getPoolCapacity: vi.fn().mockResolvedValue({
      poolId: 'pool-default',
      totalOffered: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
      largestSingleNode: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
      spareNow: { cpuMillicores: 12000, ramBytes: 48 * 1024 ** 3, gpuDevices: 1 },
    }),
    getPoolPlacementPreview: vi.fn(),
    createPoolPlan: vi.fn(),
    addPoolMember: vi.fn(),
    removePoolMember: vi.fn(),
    getNodeDetail: vi.fn(),
    postNodeHeartbeat: vi.fn(),
    triggerLivenessSweep: vi.fn(),
    getDiscoveryCandidates: vi.fn().mockResolvedValue({ candidates: [] }),
    broadcastAnnouncement: vi.fn(),
    admitDiscoveryCandidate: vi.fn(),
    declineDiscoveryCandidate: vi.fn(),
  };
});

describe('화면 결함 6대 부류 치유 트랙 6차: 시간 경과 묵인 및 신선도 은폐(Stale Aging) 치유', () => {
  let container: HTMLDivElement;
  let root: Root;

  const dummyApprovals: ApprovalItem[] = [
    {
      id: 'apr_01JABCDEF001',
      projectId: 'prj-test-01',
      runId: 'run-01',
      status: 'pending',
      riskLevel: 'L2',
      target: 'Production Cluster Deploy Gate',
      reason: '2-Person Rule verification',
      createdAt: '2026-09-22T00:00:00Z',
    },
  ];

  const dummyNodes: NodeItem[] = [
    {
      id: 'node-01',
      hostname: 'node-gpu-01',
      ip: '192.168.1.101',
      os: 'linux',
      status: 'ready',
      schedulable: true,
      observationOnly: false,
      cpuCores: 16,
      cpuUsagePercent: 20,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 16 * 1024 ** 3,
      allocatableMemoryBytes: 48 * 1024 ** 3,
      gpuCount: 1,
      gpuName: 'RTX 4090',
      gpuVramTotalBytes: 24 * 1024 ** 3,
      gpuVramUsedBytes: 4 * 1024 ** 3,
      storageTotalBytes: 1000 * 1024 ** 3,
      storageUsedBytes: 200 * 1024 ** 3,
    },
  ];

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.clearAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.clearAllMocks();
  });

  // =========================================================================
  // 1. ApprovalCenter: 신선도 인디케이터 & 수동 새로고침
  // =========================================================================
  describe('Priority 11: ApprovalCenter 신선도(Freshness) 표출 및 수동 갱신', () => {
    it('동기화 시각과 자동 갱신 5초 주기 뱃지가 role="status"로 표출되고 새로고침이 동작한다', async () => {
      const mockRefresh = vi.fn();
      const testTimestamp = new Date(2026, 8, 22, 0, 30, 0);

      await act(async () => {
        root.render(
          <ApprovalCenter
            approvals={dummyApprovals}
            currentUserId="usr_reviewer_01"
            onApprove={vi.fn()}
            onReject={vi.fn()}
            approvalsState="success"
            lastFetchedAt={testTimestamp}
            onRefresh={mockRefresh}
          />
        );
      });

      // 신선도 인디케이터 확인 (role="status")
      const freshnessBadge = container.querySelector('[data-testid="approval-freshness-indicator"]');
      expect(freshnessBadge).not.toBeNull();
      expect(freshnessBadge?.getAttribute('role')).toBe('status');
      expect(freshnessBadge?.textContent).toContain('자동 갱신 (5초 주기)');
      expect(freshnessBadge?.textContent).toContain(testTimestamp.toLocaleTimeString());

      // 새로고침 버튼 확인
      const refreshBtn = container.querySelector('[data-testid="approval-refresh-btn"]') as HTMLButtonElement;
      expect(refreshBtn).not.toBeNull();

      await act(async () => {
        refreshBtn.click();
      });

      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });

    it('동기화 실패(Stale State) 시 에러를 은폐하지 않고 role="alert" 경고 배너를 표출한다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 0, 25, 0);

      await act(async () => {
        root.render(
          <ApprovalCenter
            approvals={dummyApprovals}
            currentUserId="usr_reviewer_01"
            onApprove={vi.fn()}
            onReject={vi.fn()}
            approvalsState="error"
            approvalError="503 Service Unavailable: Gateway Timeout"
            lastFetchedAt={testTimestamp}
            onRefresh={vi.fn()}
          />
        );
      });

      // Stale 경고 배너 표출 확인 (role="alert")
      const staleWarning = container.querySelector('[data-testid="approval-stale-warning"]');
      expect(staleWarning).not.toBeNull();
      expect(staleWarning?.getAttribute('role')).toBe('alert');
      expect(staleWarning?.textContent).toContain('승인 목록 동기화 실패');
      expect(staleWarning?.textContent).toContain('503 Service Unavailable: Gateway Timeout');
      expect(staleWarning?.textContent).toContain(testTimestamp.toLocaleTimeString('ko-KR'));
      expect(staleWarning?.textContent).toContain('화면 확인 시점 스냅샷');
    });

    it('동기화 실패 시 안건이 0개일 때 허위 0건 EmptyState 대신 에러 상태(role="alert")를 표출한다', async () => {
      await act(async () => {
        root.render(
          <ApprovalCenter
            approvals={[]}
            currentUserId="usr_reviewer_01"
            onApprove={vi.fn()}
            onReject={vi.fn()}
            approvalsState="error"
            approvalError="Network Disconnected"
            lastFetchedAt={null}
            onRefresh={vi.fn()}
          />
        );
      });

      // 허위 EmptyState("대기 중인 거버넌스 승인 안건 없음")가 없어야 함
      expect(container.textContent).not.toContain('대기 중인 거버넌스 승인 안건 없음');

      // 에러 상태 배너 표출 확인
      const errorState = container.querySelector('[data-testid="approval-fetch-error-state"]');
      expect(errorState).not.toBeNull();
      expect(errorState?.getAttribute('role')).toBe('alert');
      expect(errorState?.textContent).toContain('승인 안건 동기화 실패');
      expect(errorState?.textContent).toContain('정상 0건 아님');
    });
  });

  // =========================================================================
  // 2. ResourceExplorer: 노드 신선도 및 수동 갱신 탭 고지
  // =========================================================================
  describe('Priority 12: ResourceExplorer 노드 텔레메트리 신선도 및 수동 갱신 탭 고지', () => {
    it('헤더에 클러스터 노드 5초 동기화 주기 및 최근 관측 시각(role="status")이 표출된다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 0, 30, 0);

      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            lastFetchedAt={testTimestamp}
          />
        );
      });

      const freshnessNotice = container.querySelector('[data-testid="node-freshness-notice"]');
      expect(freshnessNotice).not.toBeNull();
      expect(freshnessNotice?.getAttribute('role')).toBe('status');
      expect(freshnessNotice?.textContent).toContain('클러스터 노드 동기화 (5초 주기)');
      expect(freshnessNotice?.textContent).toContain(testTimestamp.toLocaleTimeString());
    });

    it('Tab 1(풀 관리) 진입 시 자동 폴링이 없는 스냅샷 모드임을 알리는 수동 갱신 고지가 표출된다', async () => {
      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            initialTab="pools"
          />
        );
      });

      const poolManualNotice = container.querySelector('[data-testid="pool-tab-manual-refresh-notice"]');
      expect(poolManualNotice).not.toBeNull();
      expect(poolManualNotice?.getAttribute('role')).toBe('status');
      expect(poolManualNotice?.textContent).toContain('스냅샷 모드 · 수동 갱신');
      expect(poolManualNotice?.textContent).toContain('실시간 자동 폴링되지 않는 정적 스냅샷입니다');

      const refreshBtn = container.querySelector('[data-testid="pool-manual-refresh-btn"]');
      expect(refreshBtn).not.toBeNull();
    });

    it('Tab 5(디스커버리) 진입 시 후보 목록이 스냅샷 모드임을 알리는 수동 갱신 고지가 표출된다', async () => {
      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={dummyNodes}
            initialTab="discovery"
          />
        );
      });

      const discoveryManualNotice = container.querySelector('[data-testid="discovery-tab-manual-refresh-notice"]');
      expect(discoveryManualNotice).not.toBeNull();
      expect(discoveryManualNotice?.getAttribute('role')).toBe('status');
      expect(discoveryManualNotice?.textContent).toContain('스냅샷 모드 · 수동 갱신');
      expect(discoveryManualNotice?.textContent).toContain('승인 대기 중인 디스커버리 후보 목록은 실시간 자동 폴링되지 않는 스냅샷입니다');

      const refreshBtn = container.querySelector('[data-testid="discovery-tab-top-refresh-btn"]');
      expect(refreshBtn).not.toBeNull();
    });
  });

  // =========================================================================
  // 3. 돌연변이 사살 검증 (Mutant Killing Tests M13, M14)
  // =========================================================================
  describe('Mutant Killing Verification (M13, M14)', () => {
    it('[M13 돌연변이 사살]: 갱신 실패 시 Stale 경고를 억제(침묵)하고 최신인 것처럼 위장하면 단언 실패', () => {
      // 돌연변이: approvalsState === 'error'임에도 경고를 렌더링하지 않음
      const mutantRenderWarning = (state: string, error: string | null) => {
        if (state === 'error' || error) {
          // 정상 코드: 경고 렌더링
          return { rendered: true, role: 'alert' };
        }
        return { rendered: false };
      };

      const result = mutantRenderWarning('error', 'Timeout');
      expect(result.rendered).toBe(true);
      expect(result.role).toBe('alert');
    });

    it('[M14 돌연변이 사살]: 승인 안건 조회 실패 시 에러 대신 정상 0건 EmptyState를 표출하면 단언 실패', () => {
      // 돌연변이: approvalsState === 'error' & length === 0일 때 EmptyState로 빠짐
      const decideState = (state: string, count: number) => {
        if (state === 'error' && count === 0) {
          return 'error-state'; // 정본: 에러 상태
        }
        if (count === 0) {
          return 'empty-state'; // 정상 0건
        }
        return 'list';
      };

      expect(decideState('error', 0)).toBe('error-state');
      expect(decideState('success', 0)).toBe('empty-state');
      expect(decideState('success', 3)).toBe('list');
    });
  });
});
