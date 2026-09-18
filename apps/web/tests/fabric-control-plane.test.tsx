import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../src/shared/api/client';
import {
  getStorageContributions,
  registerStorageContribution,
  activateStorageContribution,
  revokeStorageContribution,
  getStorageLocations,
  getPoolCapacity,
  getPoolPlacementPreview,
  createPoolPlan,
  addPoolMember,
  removePoolMember,
  getNodeDetail,
  postNodeHeartbeat,
  triggerLivenessSweep,
  getDiscoveryCandidates,
  broadcastAnnouncement,
  admitDiscoveryCandidate,
  declineDiscoveryCandidate,
} from '../src/features/desktop/fabricControlApi';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { NodeItem } from '../src/contracts/types';

vi.mock('../src/shared/api/client', () => ({
  apiClient: vi.fn(),
}));

const mockApi = vi.mocked(apiClient);

const sampleNodes: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 24 * 1024 ** 3,
    allocatableCores: 12,
    allocatableMemoryBytes: 40 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 1,
    gpuVramTotalBytes: 24 * 1024 ** 3,
    gpuVramUsedBytes: 6 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 500 * 1024 ** 3,
    heartbeatAt: '2026-09-18T00:00:00Z',
  },
  {
    id: 'nod_01JABCDEF02',
    hostname: 'Node-02-LinuxWorker',
    status: 'online',
    os: 'linux',
    cpuCores: 32,
    cpuUsagePercent: 45,
    memoryTotalBytes: 128 * 1024 ** 3,
    memoryUsedBytes: 64 * 1024 ** 3,
    allocatableCores: 28,
    allocatableMemoryBytes: 64 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuCount: 0,
    storageTotalBytes: 4000 * 1024 ** 3,
    storageUsedBytes: 1200 * 1024 ** 3,
    heartbeatAt: '2026-09-18T00:00:00Z',
  },
];

describe('CX-01 Fabric Control Plane API Client & ResourceExplorer Tests', () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  describe('Storage Control Plane Endpoints (1-5)', () => {
    it('1. getStorageContributions fetches contributions with optional nodeId filter', async () => {
      const mockResult = { items: [], nextCursor: null };
      mockApi.mockResolvedValueOnce(mockResult);

      const res = await getStorageContributions('nod_01JABCDEF01');
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/contributions?nodeId=nod_01JABCDEF01');
      expect(res).toEqual(mockResult);

      mockApi.mockResolvedValueOnce(mockResult);
      await getStorageContributions();
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/contributions');
    });

    it('2. registerStorageContribution sends POST with idempotencyKey option', async () => {
      const mockCreated = {
        contribution: {
          contributionId: 'sc_test1',
          nodeId: 'nod_1',
          declaredPath: 'C:\\Data',
          normalizedPath: 'C:/Data',
          mode: 'read_write' as const,
          status: 'active' as const,
          capacityBytes: 500 * 1024 ** 3,
          availableBytes: 450 * 1024 ** 3,
          registeredAt: '2026-09-18T00:00:00Z',
        },
      };
      mockApi.mockResolvedValueOnce(mockCreated);

      const res = await registerStorageContribution(
        {
          nodeId: 'nod_1',
          declaredPath: 'C:\\Data',
          mode: 'read_write',
          capacityBytes: 500 * 1024 ** 3,
          availableBytes: 450 * 1024 ** 3,
        },
        'idemp-key-999'
      );

      expect(mockApi).toHaveBeenCalledWith('/v1/storage/contributions', {
        method: 'POST',
        body: expect.stringContaining('"nodeId":"nod_1"'),
        idempotencyKey: 'idemp-key-999',
      });
      expect(res).toEqual(mockCreated);
    });

    it('3. activateStorageContribution sends POST activation', async () => {
      const mockActivated = {
        contribution: {
          contributionId: 'sc_test1',
          nodeId: 'nod_1',
          declaredPath: 'C:\\Data',
          normalizedPath: 'C:/Data',
          mode: 'read_write' as const,
          status: 'active' as const,
          capacityBytes: 500 * 1024 ** 3,
          availableBytes: 450 * 1024 ** 3,
          registeredAt: '2026-09-18T00:00:00Z',
        },
      };
      mockApi.mockResolvedValueOnce(mockActivated);

      const res = await activateStorageContribution('sc_test1');
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/contributions/sc_test1/activation', {
        method: 'POST',
      });
      expect(res.contribution.status).toBe('active');
    });

    it('4. revokeStorageContribution sends DELETE', async () => {
      const mockRevoked = {
        contribution: {
          contributionId: 'sc_test1',
          nodeId: 'nod_1',
          declaredPath: 'C:\\Data',
          normalizedPath: 'C:/Data',
          mode: 'read_write' as const,
          status: 'revoked' as const,
          capacityBytes: 500 * 1024 ** 3,
          availableBytes: 450 * 1024 ** 3,
          registeredAt: '2026-09-18T00:00:00Z',
        },
      };
      mockApi.mockResolvedValueOnce(mockRevoked);

      const res = await revokeStorageContribution('sc_test1');
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/contributions/sc_test1', {
        method: 'DELETE',
      });
      expect(res.contribution.status).toBe('revoked');
    });

    it('5. getStorageLocations encodes contributionId parameter', async () => {
      mockApi.mockResolvedValueOnce({ items: [], nextCursor: null });
      await getStorageLocations('sc_test1');
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/locations?contributionId=sc_test1');

      mockApi.mockResolvedValueOnce({ items: [], nextCursor: null });
      await getStorageLocations();
      expect(mockApi).toHaveBeenCalledWith('/v1/storage/locations');
    });
  });

  describe('Pools & Placement Control Plane Endpoints (6-10)', () => {
    it('6. getPoolCapacity fetches capacity summary', async () => {
      const mockCap = {
        totalOffered: { cpuMillicores: 32000, ramBytes: 128 * 1024 ** 3, gpuDevices: 2 },
        largestSingleNode: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 1 },
        spareNow: { cpuMillicores: 24000, ramBytes: 96 * 1024 ** 3, gpuDevices: 2 },
        units: { cpu: 'millicores', ram: 'bytes', gpu: 'devices' },
      };
      mockApi.mockResolvedValueOnce(mockCap);

      const res = await getPoolCapacity('pool-alpha');
      expect(mockApi).toHaveBeenCalledWith('/v1/pools/pool-alpha/capacity');
      expect(res).toEqual(mockCap);
    });

    it('7. getPoolPlacementPreview queries with query string parameters', async () => {
      const mockPreview = { poolId: 'pool-alpha', candidates: [], candidateCount: 0 };
      mockApi.mockResolvedValueOnce(mockPreview);

      await getPoolPlacementPreview('pool-alpha', {
        cpuMillicores: 4000,
        ramBytes: 16 * 1024 ** 3,
        gpuDevices: 1,
      });

      expect(mockApi).toHaveBeenCalledWith(
        expect.stringContaining('/v1/pools/pool-alpha/placement-preview?')
      );
    });

    it('8. createPoolPlan issues POST /v1/pools/{id}/plans with strategy', async () => {
      const mockPlan = {
        planId: 'plan_01JTEST',
        runId: 'run_123',
        strategy: 'spread',
        shardCount: 2,
        placements: [],
      };
      mockApi.mockResolvedValueOnce(mockPlan);

      const res = await createPoolPlan('pool-alpha', {
        runId: 'run_123',
        strategy: 'spread',
        shardCount: 2,
        shardCpuMillicores: 2000,
        shardRamBytes: 8 * 1024 ** 3,
        shardGpuDevices: 0,
        splittableDeclared: true,
      });

      expect(mockApi).toHaveBeenCalledWith('/v1/pools/pool-alpha/plans', {
        method: 'POST',
        body: expect.stringContaining('"strategy":"spread"'),
      });
      expect(res.planId).toBe('plan_01JTEST');
    });

    it('9. addPoolMember issues PUT /v1/pools/{id}/members/{node_id}', async () => {
      mockApi.mockResolvedValueOnce({ poolId: 'pool-alpha', nodeId: 'nod_test', member: true });
      await addPoolMember('pool-alpha', 'nod_test');
      expect(mockApi).toHaveBeenCalledWith('/v1/pools/pool-alpha/members/nod_test', {
        method: 'PUT',
      });
    });

    it('10. removePoolMember issues DELETE /v1/pools/{id}/members/{node_id}', async () => {
      mockApi.mockResolvedValueOnce({ poolId: 'pool-alpha', nodeId: 'nod_test', removed: true });
      await removePoolMember('pool-alpha', 'nod_test');
      expect(mockApi).toHaveBeenCalledWith('/v1/pools/pool-alpha/members/nod_test', {
        method: 'DELETE',
      });
    });
  });

  describe('Nodes & Discovery Control Plane Endpoints (11-16)', () => {
    it('11. getNodeDetail fetches node capabilities and spec', async () => {
      const mockDetail = {
        node: {
          nodeId: 'nod_1',
          hostname: 'host1',
          osType: 'linux',
          osVersion: '24.04',
          agentVersion: '0.1.0',
          status: 'online',
          enrolledAt: '2026-09-18T00:00:00Z',
          lastHeartbeatAt: '2026-09-18T00:00:00Z',
          heartbeatSequence: 5,
          labels: {},
        },
        capabilities: [],
      };
      mockApi.mockResolvedValueOnce(mockDetail);

      const res = await getNodeDetail('nod_1');
      expect(mockApi).toHaveBeenCalledWith('/v1/nodes/nod_1');
      expect(res.node.nodeId).toBe('nod_1');
    });

    it('12. postNodeHeartbeat posts observations and sequence', async () => {
      mockApi.mockResolvedValueOnce({ nodeId: 'nod_1', applied: true, heartbeatSequence: 6 });
      const res = await postNodeHeartbeat('nod_1', {
        sequence: 6,
        observations: [{ capabilityId: 'cap_cpu', usedQuantity: 2, unit: 'cores' }],
      });
      expect(mockApi).toHaveBeenCalledWith('/v1/nodes/nod_1/heartbeats', {
        method: 'POST',
        body: expect.stringContaining('"sequence":6'),
      });
      expect(res.heartbeatSequence).toBe(6);
    });

    it('13. triggerLivenessSweep invokes sweep POST', async () => {
      mockApi.mockResolvedValueOnce({ markedLost: 0, timeoutSeconds: 30 });
      const res = await triggerLivenessSweep();
      expect(mockApi).toHaveBeenCalledWith('/v1/nodes/liveness-sweeps', {
        method: 'POST',
      });
      expect(res.markedLost).toBe(0);
    });

    it('14. getDiscoveryCandidates queries candidates list with optional includeStale', async () => {
      mockApi.mockResolvedValueOnce({ items: [], note: 'Unverified' });
      const res = await getDiscoveryCandidates();
      expect(mockApi).toHaveBeenCalledWith('/v1/discovery/candidates');
      expect(res.items).toEqual([]);

      mockApi.mockResolvedValueOnce({ items: [], note: 'Unverified' });
      await getDiscoveryCandidates(true);
      expect(mockApi).toHaveBeenCalledWith('/v1/discovery/candidates?includeStale=true');
    });

    it('14b. broadcastAnnouncement sends announcement payload and tenant header', async () => {
      mockApi.mockResolvedValueOnce({ accepted: true, state: 'registered' });
      const res = await broadcastAnnouncement(
        {
          instanceId: 'inst_1',
          hostname: 'node-new',
          osType: 'linux',
          osVersion: '24.04',
          agentVersion: '0.1.0',
          cpuCores: 8,
          ramBytes: 32 * 1024 ** 3,
          gpuCount: 0,
          labels: { role: 'compute' },
        },
        '00000000-0000-0000-0000-000000000001'
      );
      expect(mockApi).toHaveBeenCalledWith('/v1/discovery/announcements', {
        method: 'POST',
        headers: {
          'X-Inv-Tenant': '00000000-0000-0000-0000-000000000001',
        },
        body: expect.stringContaining('"instanceId":"inst_1"'),
      });
      expect(res.state).toBe('registered');
    });

    it('15. admitDiscoveryCandidate admits candidate and receives bootstrap token', async () => {
      mockApi.mockResolvedValueOnce({
        announcementId: 'ann_1',
        bootstrapToken: 'btk_token_secret_123',
        expiresAt: '2026-09-18T01:00:00Z',
        next: 'run',
      });
      const res = await admitDiscoveryCandidate('ann_1');
      expect(mockApi).toHaveBeenCalledWith('/v1/discovery/candidates/ann_1/admission', {
        method: 'POST',
      });
      expect(res.bootstrapToken).toBe('btk_token_secret_123');
    });

    it('16. declineDiscoveryCandidate sends DELETE to reject candidate', async () => {
      mockApi.mockResolvedValueOnce({ announcementId: 'ann_1', state: 'declined' });
      await declineDiscoveryCandidate('ann_1', 'unauthorized');
      expect(mockApi).toHaveBeenCalledWith('/v1/discovery/candidates/ann_1?reason=unauthorized', {
        method: 'DELETE',
      });
    });
  });

  describe('ResourceExplorer UI Component Multi-Tab Rendering', () => {
    it('renders Overview tab by default with Logical Fabric Pool and Nodes', () => {
      const markup = renderToStaticMarkup(<ResourceExplorer nodes={sampleNodes} initialTab="overview" />);
      expect(markup).toContain('물리 자원 분산 보존 원칙');
      expect(markup).toContain('논리 vCPU 풀');
      expect(markup).toContain('물리 노드별 실제 토폴로지');
      expect(markup).toContain('Node-01-WinMain');
      expect(markup).toContain('Node-02-LinuxWorker');
    });

    it('renders Storage tab with registration form and contribution ledger', () => {
      const markup = renderToStaticMarkup(<ResourceExplorer nodes={sampleNodes} initialTab="storage" />);
      expect(markup).toContain('새 스토리지 폴더 기여 등록');
      expect(markup).toContain('POST /v1/storage/contributions');
      expect(markup).toContain('등록된 스토리지 기여 목록');
      expect(markup).toContain('데이터 위치 원장 (GET /v1/storage/locations)');
    });

    it('renders Pools tab with capacity card, member management, and placement preview', () => {
      const markup = renderToStaticMarkup(<ResourceExplorer nodes={sampleNodes} initialTab="pools" />);
      expect(markup).toContain('풀 집계 용량 (GET /v1/pools/');
      expect(markup).toContain('풀 멤버 노드 관리');
      expect(markup).toContain('배치 미리보기 (GET /v1/pools/');
      expect(markup).toContain('분산 배치 계획 수립 (POST /v1/pools/');
    });

    it('renders Nodes tab with diagnostic detail and heartbeat controls', () => {
      const markup = renderToStaticMarkup(<ResourceExplorer nodes={sampleNodes} initialTab="nodes" />);
      expect(markup).toContain('검사 노드:');
      expect(markup).toContain('하트비트 시퀀스 전송 (POST /v1/nodes/');
    });

    it('renders Discovery tab with candidate admission controls', () => {
      const markup = renderToStaticMarkup(<ResourceExplorer nodes={sampleNodes} initialTab="discovery" />);
      expect(markup).toContain('미등록 머신 안내 방송 전송 (POST /v1/discovery/announcements)');
      expect(markup).toContain('승인 대기 중인 디스커버리 후보');
      expect(markup).toContain('승인 &amp; 토큰 발급');
    });
  });
});
