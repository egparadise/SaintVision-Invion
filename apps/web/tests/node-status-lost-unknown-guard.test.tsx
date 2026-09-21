// @vitest-environment happy-dom
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { observedNode } from '@/shared/api/nodeObservation';
import { NodeList } from '@/features/nodes/NodeList';

describe('Node Status: Lost & Unknown Guard (조용한 합류 둔갑 차단)', () => {
  describe('observedNode mapper unit tests', () => {
    it('백엔드 lost 노드를 enrolling으로 둔갑시키지 않고 lost로 보존한다', () => {
      const rawLost = {
        nodeId: 'nod_pacs_worker_lost_01',
        hostname: 'pacs-worker-lost-01',
        status: 'lost',
        os: 'linux',
        heartbeatAt: '2026-09-22T02:00:00Z',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 34359738368,
        memoryUsedBytes: 0,
        storageTotalBytes: 1099511627776,
        storageUsedBytes: 0,
        gpuCount: 0,
      };

      const mapped = observedNode(rawLost);
      expect(mapped.status).toBe('lost');
      expect(mapped.status).not.toBe('enrolling');
      expect(mapped.telemetryUnavailable).toBe(true);
      expect(mapped.schedulable).toBe(false);
    });

    it('백엔드의 미정합 어휘(active)를 조용히 enrolling으로 바꾸지 않고 unknown으로 명시한다', () => {
      const rawActive = {
        nodeId: 'nod_pacs_worker_active_01',
        hostname: 'pacs-worker-active-01',
        status: 'active', // 백엔드 DB CHECK 어휘이나 화면이 아직 어휘 정합 전인 미지의 상태
        os: 'linux',
        heartbeatAt: '2026-09-22T03:00:00Z',
        cpuCores: 16,
        cpuUsagePercent: 35,
        memoryTotalBytes: 68719476736,
        memoryUsedBytes: 24000000000,
        storageTotalBytes: 2199023255552,
        storageUsedBytes: 500000000000,
        gpuCount: 1,
      };

      const mapped = observedNode(rawActive);
      expect(mapped.status).toBe('unknown');
      expect(mapped.status).not.toBe('enrolling');
      expect(mapped.telemetryUnavailable).toBe(true);
      expect(mapped.schedulable).toBe(false);
    });

    it('임의의 알 수 없는 상태도 그럴듯하게 enrolling으로 꾸미지 않고 unknown으로 매핑한다', () => {
      const rawWeird = {
        nodeId: 'nod_weird_01',
        hostname: 'weird-worker',
        status: 'something_unrecognized',
        os: 'windows',
        heartbeatAt: '2026-09-22T03:00:00Z',
        cpuCores: 4,
        cpuUsagePercent: 10,
        memoryTotalBytes: 17179869184,
        memoryUsedBytes: 4000000000,
        storageTotalBytes: 500000000000,
        storageUsedBytes: 100000000000,
        gpuCount: 0,
      };

      const mapped = observedNode(rawWeird);
      expect(mapped.status).toBe('unknown');
      expect(mapped.status).not.toBe('enrolling');
    });

    it('실제 합류 중인 enrolling 노드는 enrolling으로 정확히 유지한다', () => {
      const rawEnrolling = {
        nodeId: 'nod_joining_01',
        hostname: 'joining-worker',
        status: 'enrolling',
        os: 'linux',
        heartbeatAt: '2026-09-22T03:00:00Z',
        cpuCores: 8,
        cpuUsagePercent: 5,
        memoryTotalBytes: 34359738368,
        memoryUsedBytes: 1000000000,
        storageTotalBytes: 1099511627776,
        storageUsedBytes: 10000000000,
        gpuCount: 0,
      };

      const mapped = observedNode(rawEnrolling);
      expect(mapped.status).toBe('enrolling');
    });
  });

  describe('NodeList DOM rendering tests', () => {
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
    });

    it('lost 노드를 렌더링할 때 합류 중으로 둘러대지 않고 role=alert와 [LOST (단절)] 경고를 표출한다', async () => {
      const lostNode = observedNode({
        nodeId: 'nod_dead_01',
        hostname: 'dead-worker-node',
        status: 'lost',
        os: 'linux',
        heartbeatAt: '2026-09-22T00:00:00Z',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 34359738368,
        memoryUsedBytes: 0,
        storageTotalBytes: 1099511627776,
        storageUsedBytes: 0,
        gpuCount: 0,
      });

      await act(async () => {
        root.render(<NodeList nodes={[lostNode]} />);
      });

      const card = container.querySelector('[data-testid="node-card-nod_dead_01"]');
      expect(card).not.toBeNull();
      expect(card?.getAttribute('role')).toBe('alert');

      const badge = container.querySelector('[data-testid="node-status-badge-nod_dead_01"]');
      expect(badge?.textContent).toContain('LOST (단절)');
      expect(badge?.textContent).not.toContain('ENROLLING');
      expect(badge?.textContent).not.toContain('합류 중');

      expect(card?.textContent).toContain('통신이 두절되어 상태가 유실(Lost)되었습니다');
    });

    it('unknown 노드를 렌더링할 때 합류 중으로 위장하지 않고 [UNKNOWN (미확인)]과 조용한 합류 둔갑 차단 고지를 표출한다', async () => {
      const unknownNode = observedNode({
        nodeId: 'nod_active_01',
        hostname: 'active-unmapped-node',
        status: 'active', // 아직 어휘 정합 전인 미지의 상태
        os: 'linux',
        heartbeatAt: '2026-09-22T03:00:00Z',
        cpuCores: 16,
        cpuUsagePercent: 50,
        memoryTotalBytes: 68719476736,
        memoryUsedBytes: 30000000000,
        storageTotalBytes: 2199023255552,
        storageUsedBytes: 500000000000,
        gpuCount: 0,
      });

      await act(async () => {
        root.render(<NodeList nodes={[unknownNode]} />);
      });

      const card = container.querySelector('[data-testid="node-card-nod_active_01"]');
      expect(card).not.toBeNull();
      expect(card?.getAttribute('role')).toBe('status');

      const badge = container.querySelector('[data-testid="node-status-badge-nod_active_01"]');
      expect(badge?.textContent).toContain('UNKNOWN (미확인)');
      expect(badge?.textContent).not.toContain('ENROLLING');
      expect(badge?.textContent).not.toContain('합류 중');

      expect(card?.textContent).toContain('서버에서 관측된 노드 상태를 화면에서 해석할 수 없습니다');
      expect(card?.textContent).toContain('조용한 합류 둔갑 차단');
    });
  });
});
