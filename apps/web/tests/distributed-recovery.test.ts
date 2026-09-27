import { describe, it, expect } from 'vitest';
import {
  DistributedRecoveryManager,
  isTokenValidAndCurrent,
  isTokenNewer,
} from '../src/features/recovery/recoveryEngine';

const INITIAL_NODES = [
  { nodeId: 'nod_01JABCDEF01', hostname: 'Node-01-WinMain', activeWorkspaces: 2 },
  { nodeId: 'nod_01JABCDEF02', hostname: 'Node-02-WinWork', activeWorkspaces: 1 },
  { nodeId: 'nod_01JABCDEF03', hostname: 'Node-03-WinDev', activeWorkspaces: 0 },
  { nodeId: 'nod_01JABCDEF04', hostname: 'Node-04-LinuxBuild', activeWorkspaces: 3 },
  { nodeId: 'nod_01JABCDEF05', hostname: 'Node-05-LinuxGPU', activeWorkspaces: 1 },
];

describe('S07-FE: Distributed Recovery Dashboard & Monotonic Fencing Validation (AC-07)', () => {
  describe('Heartbeat Age & Stale Detection Time (AC-07 ≤ 60s)', () => {
    it('detects node stale condition within 60s threshold', () => {
      const mgr = new DistributedRecoveryManager(INITIAL_NODES);
      const target = 'nod_01JABCDEF01';

      // 1. Healthy heartbeat (5s age)
      expect(mgr.evaluateNodeHealth(target, 5)).toBe('online');

      // 2. Bound check at 60s
      expect(mgr.evaluateNodeHealth(target, 60)).toBe('online');

      // 3. Exceeded 60s (61s age) -> must transition to stale
      expect(mgr.evaluateNodeHealth(target, 61)).toBe('stale');

      // 4. Delayed 125s -> transitions to offline
      expect(mgr.evaluateNodeHealth(target, 125)).toBe('offline');
    });
  });

  describe('Monotonic Fencing Token Rules (ADR-006 & ERR-DESIGN-006)', () => {
    it('validates higher epoch takes precedence regardless of sequence', () => {
      // New epoch with seq 1 beats older epoch with seq 9999
      expect(isTokenNewer({ epoch: 2, sequence: 1 }, { epoch: 1, sequence: 9999 })).toBe(true);
      expect(isTokenNewer({ epoch: 1, sequence: 9999 }, { epoch: 2, sequence: 1 })).toBe(false);
    });

    it('validates higher sequence takes precedence when epochs are equal', () => {
      expect(isTokenNewer({ epoch: 2, sequence: 15 }, { epoch: 2, sequence: 10 })).toBe(true);
      expect(isTokenNewer({ epoch: 2, sequence: 10 }, { epoch: 2, sequence: 10 })).toBe(false);
      expect(isTokenNewer({ epoch: 2, sequence: 9 }, { epoch: 2, sequence: 10 })).toBe(false);
    });

    it('strictly requires exact match for current active token and rejects future/stale tokens', () => {
      expect(isTokenValidAndCurrent({ epoch: 1, sequence: 100 }, { epoch: 1, sequence: 100 })).toBe(true);
      // Rejects unissued future epoch or sequence
      expect(isTokenValidAndCurrent({ epoch: 99, sequence: 1 }, { epoch: 1, sequence: 100 })).toBe(false);
      expect(isTokenValidAndCurrent({ epoch: 1, sequence: 999 }, { epoch: 1, sequence: 100 })).toBe(false);
      // Rejects stale epoch or sequence
      expect(isTokenValidAndCurrent({ epoch: 0, sequence: 100 }, { epoch: 1, sequence: 100 })).toBe(false);
      expect(isTokenValidAndCurrent({ epoch: 1, sequence: 99 }, { epoch: 1, sequence: 100 })).toBe(false);
    });
  });

  describe('Late Result Rejection & Zero Stale Writes (AC-07)', () => {
    it('strictly rejects zombie late write attempts with zero stale writes allowed', () => {
      const mgr = new DistributedRecoveryManager(INITIAL_NODES);
      const target = 'nod_01JABCDEF04';
      const node = mgr.getNode(target)!;

      const currentEpoch = node.fencingToken.epoch;
      const currentSeq = node.fencingToken.sequence;

      // 1. Simulate Network Partition / Split-Brain
      mgr.simulateNetworkPartition(target);
      expect(mgr.getNode(target)?.healthState).toBe('fenced');
      expect(mgr.getNode(target)?.fencingToken.epoch).toBe(currentEpoch + 1);

      // 2. 50 simulated concurrent late writes from isolated zombie worker using previous token
      const staleToken = { epoch: currentEpoch, sequence: currentSeq + 10 };
      for (let i = 0; i < 50; i++) {
        const res = mgr.attemptWrite(target, staleToken, `stale_write_attempt_${i}`);
        expect(res.success).toBe(false);
        expect(res.error).toContain('STALE_FENCING_TOKEN');
      }

      // 3. Invariant: Stale writes allowed MUST be exactly 0
      expect(mgr.getStaleWritesAllowed()).toBe(0);
      expect(mgr.getLateRejections()).toHaveLength(50);
    });
  });

  describe('Cluster Drain & Reconciliation Recovery (AC-07 ≥ 95%)', () => {
    it('evacuates active workspaces, heals partition, advances epoch, and restores online status during single node reconciliation (REC-01)', () => {
      const mgr = new DistributedRecoveryManager(INITIAL_NODES);
      const target = 'nod_01JABCDEF01';
      const node = mgr.getNode(target)!;
      const initialEpoch = node.fencingToken.epoch;
      const initialWorkspaces = node.activeWorkspacesCount;
      expect(initialWorkspaces).toBeGreaterThan(0);

      // 1. Partition the node
      mgr.simulateNetworkPartition(target);
      expect(node.isPartitioned).toBe(true);
      expect(node.healthState).toBe('fenced');
      const partitionedEpoch = node.fencingToken.epoch;
      expect(partitionedEpoch).toBe(initialEpoch + 1);

      // 2. Reconcile node
      const record = mgr.reconcileNode(target);

      // Explicit assertions resolving REC-01 expect 0 defect
      expect(record.recoverySuccess).toBe(true);
      expect(record.evacuatedWorkspacesCount).toBe(initialWorkspaces);
      expect(node.activeWorkspacesCount).toBe(0);
      expect(node.isPartitioned).toBe(false);
      expect(node.healthState).toBe('online');
      expect(node.fencingToken.epoch).toBe(partitionedEpoch + 1);
      expect(record.newEpoch).toBe(node.fencingToken.epoch);
      expect(record.nodeId).toBe(target);
      expect(mgr.getReconciliations()).toHaveLength(1);
    });

    it('evacuates workspaces, advances epoch, and achieves 100% recovery rate over 20 runs', () => {
      const mgr = new DistributedRecoveryManager(INITIAL_NODES);

      let successfulReconciliations = 0;
      const totalRuns = 20;

      for (let i = 0; i < totalRuns; i++) {
        const targetNodeId = INITIAL_NODES[i % INITIAL_NODES.length].nodeId;

        // Partition the node
        mgr.simulateNetworkPartition(targetNodeId);
        expect(mgr.getNode(targetNodeId)?.healthState).toBe('fenced');

        // Drain & reconcile
        const record = mgr.reconcileNode(targetNodeId);
        expect(record.recoverySuccess).toBe(true);
        expect(mgr.getNode(targetNodeId)?.isPartitioned).toBe(false);
        if (record.recoverySuccess && mgr.getNode(targetNodeId)?.healthState === 'online') {
          successfulReconciliations++;
        }
      }

      const recoveryRate = successfulReconciliations / totalRuns;
      expect(recoveryRate).toBe(1.0); // 100%
      expect(recoveryRate).toBeGreaterThanOrEqual(0.95); // AC-07 threshold: ≥95%
    });

    it('initializes node health and heartbeat age from actual backend status and heartbeatAt timestamp', () => {
      const pastTime = new Date(Date.now() - 75 * 1000).toISOString();
      const ancientTime = new Date(Date.now() - 150 * 1000).toISOString();
      const customNodes = [
        { nodeId: 'nod_actual_online', hostname: 'Node-Online', status: 'healthy', heartbeatAt: new Date().toISOString() },
        { nodeId: 'nod_actual_stale', hostname: 'Node-Stale', status: 'healthy', heartbeatAt: pastTime },
        { nodeId: 'nod_actual_offline', hostname: 'Node-Offline', status: 'offline', heartbeatAt: pastTime },
        { nodeId: 'nod_actual_ancient', hostname: 'Node-Ancient', status: 'healthy', heartbeatAt: ancientTime },
      ];

      const mgr = new DistributedRecoveryManager(customNodes);
      expect(mgr.getNode('nod_actual_online')?.healthState).toBe('online');
      expect(mgr.getNode('nod_actual_online')?.actualStatus).toBe('healthy');
      expect(mgr.getNode('nod_actual_online')?.heartbeatAgeSeconds).toBeLessThanOrEqual(5);

      expect(mgr.getNode('nod_actual_stale')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_actual_stale')?.heartbeatAgeSeconds).toBeGreaterThanOrEqual(70);

      expect(mgr.getNode('nod_actual_offline')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_offline')?.actualStatus).toBe('offline');

      expect(mgr.getNode('nod_actual_ancient')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_ancient')?.heartbeatAgeSeconds).toBeGreaterThanOrEqual(140);
    });
  });
});
