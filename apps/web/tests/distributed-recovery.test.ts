import { describe, it, expect } from 'vitest';
import {
  DistributedRecoveryManager,
  isTokenValidAndCurrent,
  isTokenNewer,
  InitialRecoveryNode,
} from '../src/features/recovery/recoveryEngine';

const INITIAL_NODES: InitialRecoveryNode[] = [
  { nodeId: 'nod_01JABCDEF01', hostname: 'Node-01-WinMain', activeWorkspaces: 3, status: 'online', heartbeatAt: new Date().toISOString() },
  { nodeId: 'nod_01JABCDEF02', hostname: 'Node-02-LinuxWorker1', activeWorkspaces: 2, status: 'online', heartbeatAt: new Date().toISOString() },
  { nodeId: 'nod_01JABCDEF03', hostname: 'Node-03-LinuxWorker2', activeWorkspaces: 4, status: 'online', heartbeatAt: new Date().toISOString() },
  { nodeId: 'nod_01JABCDEF04', hostname: 'Node-04-LinuxWorker3', activeWorkspaces: 1, status: 'online', heartbeatAt: new Date().toISOString() },
  { nodeId: 'nod_01JABCDEF05', hostname: 'Node-05-SpareCold', activeWorkspaces: 0, status: 'online', heartbeatAt: new Date().toISOString() },
];

describe('Distributed Fencing Token & Recovery Engine (ADR-006 & ERR-DESIGN-006)', () => {
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

  describe('Monotonic Fencing Invariants', () => {
    it('strictly accepts identical (epoch, sequence) tokens', () => {
      const current = { epoch: 2, sequence: 15 };
      expect(isTokenValidAndCurrent({ epoch: 2, sequence: 15 }, current)).toBe(true);
    });

    it('strictly rejects stale tokens with smaller epoch (zombie write protection)', () => {
      const current = { epoch: 2, sequence: 15 };
      expect(isTokenValidAndCurrent({ epoch: 1, sequence: 99 }, current)).toBe(false);
    });

    it('strictly rejects stale tokens with identical epoch but smaller sequence', () => {
      const current = { epoch: 2, sequence: 15 };
      expect(isTokenValidAndCurrent({ epoch: 2, sequence: 14 }, current)).toBe(false);
    });

    it('strictly rejects unissued future tokens (epoch > current)', () => {
      const current = { epoch: 2, sequence: 15 };
      expect(isTokenValidAndCurrent({ epoch: 3, sequence: 1 }, current)).toBe(false);
    });

    it('evaluates token seniority via isTokenNewer', () => {
      const baseline = { epoch: 2, sequence: 10 };
      expect(isTokenNewer({ epoch: 3, sequence: 1 }, baseline)).toBe(true);
      expect(isTokenNewer({ epoch: 2, sequence: 11 }, baseline)).toBe(true);
      expect(isTokenNewer({ epoch: 2, sequence: 10 }, baseline)).toBe(false);
      expect(isTokenNewer({ epoch: 1, sequence: 99 }, baseline)).toBe(false);
    });
  });

  describe('Zombie Task Interception & Late Result Blocking (AC-07 Invariant)', () => {
    it('blocks 50 consecutive late writes with stale tokens and logs rejections', () => {
      const mgr = new DistributedRecoveryManager(INITIAL_NODES);
      const target = 'nod_01JABCDEF01';

      // 1. Advance epoch via network partition simulation
      mgr.simulateNetworkPartition(target);
      const node = mgr.getNode(target);
      expect(node).toBeDefined();
      expect(node!.fencingToken.epoch).toBe(2);

      // 2. Attempt 50 writes with stale Epoch 1
      for (let i = 0; i < 50; i++) {
        const res = mgr.attemptWrite(target, { epoch: 1, sequence: 10 + i }, `zombie_payload_${i}`);
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
      const customNodes: InitialRecoveryNode[] = [
        { nodeId: 'nod_actual_online', hostname: 'Node-Online', status: 'online', heartbeatAt: new Date().toISOString() },
        { nodeId: 'nod_actual_stale', hostname: 'Node-Stale', status: 'online', heartbeatAt: pastTime },
        { nodeId: 'nod_actual_offline', hostname: 'Node-Offline', status: 'offline', heartbeatAt: pastTime },
        { nodeId: 'nod_actual_ancient', hostname: 'Node-Ancient', status: 'online', heartbeatAt: ancientTime },
        { nodeId: 'nod_actual_lost', hostname: 'Node-Lost', status: 'lost', heartbeatAt: null },
        { nodeId: 'nod_actual_degraded', hostname: 'Node-Degraded', status: 'degraded', heartbeatAt: new Date().toISOString() },
        { nodeId: 'nod_actual_unknown', hostname: 'Node-Unknown', status: undefined, heartbeatAt: null },
      ];

      const mgr = new DistributedRecoveryManager(customNodes);

      // 1. Online node with fresh heartbeat
      expect(mgr.getNode('nod_actual_online')?.healthState).toBe('online');
      expect(mgr.getNode('nod_actual_online')?.actualStatus).toBe('online');
      expect(mgr.getNode('nod_actual_online')?.heartbeatAgeSeconds).toBeLessThanOrEqual(5);

      // 2. Stale node due to >60s heartbeat
      expect(mgr.getNode('nod_actual_stale')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_actual_stale')?.heartbeatAgeSeconds).toBeGreaterThanOrEqual(70);

      // 3. Offline node explicitly marked offline
      expect(mgr.getNode('nod_actual_offline')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_offline')?.actualStatus).toBe('offline');

      // 4. Ancient heartbeat (>120s) -> offline
      expect(mgr.getNode('nod_actual_ancient')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_ancient')?.heartbeatAgeSeconds).toBeGreaterThanOrEqual(140);

      // 5. Lost node with null heartbeat must be OFFLINE, never synthetic 2s/ONLINE
      expect(mgr.getNode('nod_actual_lost')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_lost')?.actualStatus).toBe('lost');
      expect(mgr.getNode('nod_actual_lost')?.heartbeatAgeSeconds).toBe(-1);
      expect(mgr.getNode('nod_actual_lost')?.lastHeartbeatAt).toBe('');

      // 6. Degraded node mapped to stale
      expect(mgr.getNode('nod_actual_degraded')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_actual_degraded')?.actualStatus).toBe('degraded');

      // 7. Unknown node without heartbeat
      expect(mgr.getNode('nod_actual_unknown')?.healthState).toBe('offline');
      expect(mgr.getNode('nod_actual_unknown')?.actualStatus).toBe('unknown');
      expect(mgr.getNode('nod_actual_unknown')?.heartbeatAgeSeconds).toBe(-1);
    });

    it('dynamically syncs nodes and preserves non-simulation modified status via syncNodes', () => {
      const mgr = new DistributedRecoveryManager([
        { nodeId: 'nod_dyn_01', hostname: 'Node-Dynamic-01', status: 'online', heartbeatAt: new Date().toISOString() },
      ]);
      expect(mgr.getNodes()).toHaveLength(1);
      expect(mgr.getNode('nod_dyn_01')?.healthState).toBe('online');

      // Update with new incoming list (nod_dyn_01 becomes draining, nod_dyn_02 added)
      mgr.syncNodes([
        { nodeId: 'nod_dyn_01', hostname: 'Node-Dynamic-01', status: 'draining', heartbeatAt: new Date().toISOString() },
        { nodeId: 'nod_dyn_02', hostname: 'Node-Dynamic-02', status: 'offline', heartbeatAt: null },
      ]);

      expect(mgr.getNodes()).toHaveLength(2);
      expect(mgr.getNode('nod_dyn_01')?.actualStatus).toBe('draining');
      expect(mgr.getNode('nod_dyn_01')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_dyn_02')?.actualStatus).toBe('offline');
      expect(mgr.getNode('nod_dyn_02')?.healthState).toBe('offline');
    });

    it('protects simulation modified node heartbeat from being overwritten by incoming polling syncNodes', () => {
      const mgr = new DistributedRecoveryManager([
        { nodeId: 'nod_sim_01', hostname: 'Node-Sim-01', status: 'online', heartbeatAt: new Date().toISOString() },
      ]);
      // Simulate heartbeat delay (75s)
      mgr.simulateHeartbeatDelay('nod_sim_01', 75);
      expect(mgr.getNode('nod_sim_01')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_sim_01')?.heartbeatAgeSeconds).toBe(75);

      // Incoming background polling with fresh heartbeat (e.g. 3s ago)
      const freshHeartbeat = new Date(Date.now() - 3000).toISOString();
      mgr.syncNodes([
        { nodeId: 'nod_sim_01', hostname: 'Node-Sim-01', status: 'online', heartbeatAt: freshHeartbeat },
      ]);

      // Polling must not overwrite the simulated stale health state or simulated age
      expect(mgr.getNode('nod_sim_01')?.healthState).toBe('stale');
      expect(mgr.getNode('nod_sim_01')?.heartbeatAgeSeconds).toBe(75);
      expect(mgr.getNode('nod_sim_01')?.isSimulationModified).toBe(true);
    });
  });
});
