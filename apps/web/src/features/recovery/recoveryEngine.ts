import { NodeHealthState, FencingToken, LateResultRejection, ReconciliationRecord } from '@/contracts/types';

export interface ResilientNodeState {
  nodeId: string;
  hostname: string;
  healthState: NodeHealthState;
  lastHeartbeatAt: string;
  heartbeatAgeSeconds: number;
  fencingToken: FencingToken;
  activeWorkspacesCount: number;
  isPartitioned: boolean;
}

/**
 * Monotonic Fencing Token Validator (ADR-006 & ERR-DESIGN-006)
 * Precedence: higher epoch wins; if epoch identical, higher sequence wins.
 */
export function isTokenValidAndCurrent(
  attempted: { epoch: number; sequence: number },
  current: { epoch: number; sequence: number }
): boolean {
  // Monotonic fencing invariant:
  // An attempted execution/write token must match the currently issued active fencing token.
  // Stale tokens (attempted < current) and unissued future tokens (attempted > current) are strictly rejected.
  return attempted.epoch === current.epoch && attempted.sequence === current.sequence;
}

export function isTokenNewer(
  candidate: { epoch: number; sequence: number },
  baseline: { epoch: number; sequence: number }
): boolean {
  if (candidate.epoch > baseline.epoch) return true;
  if (candidate.epoch === baseline.epoch && candidate.sequence > baseline.sequence) return true;
  return false;
}

export class DistributedRecoveryManager {
  private nodes: Map<string, ResilientNodeState> = new Map();
  private lateResultRejections: LateResultRejection[] = [];
  private reconciliationHistory: ReconciliationRecord[] = [];
  private staleTokenWritesAllowed = 0;

  constructor(initialNodes: Array<{ nodeId: string; hostname: string; activeWorkspaces?: number }>) {
    const now = new Date().toISOString();
    initialNodes.forEach((n, idx) => {
      this.nodes.set(n.nodeId, {
        nodeId: n.nodeId,
        hostname: n.hostname,
        healthState: 'online',
        lastHeartbeatAt: now,
        heartbeatAgeSeconds: 2,
        fencingToken: {
          nodeId: n.nodeId,
          epoch: 1,
          sequence: 10 + idx * 5,
          issuedAt: now,
        },
        activeWorkspacesCount: n.activeWorkspaces ?? (idx + 1),
        isPartitioned: false,
      });
    });
  }

  getNodes(): ResilientNodeState[] {
    return Array.from(this.nodes.values());
  }

  getNode(nodeId: string): ResilientNodeState | undefined {
    return this.nodes.get(nodeId);
  }

  getLateRejections(): LateResultRejection[] {
    return [...this.lateResultRejections];
  }

  getReconciliations(): ReconciliationRecord[] {
    return [...this.reconciliationHistory];
  }

  getStaleWritesAllowed(): number {
    return this.staleTokenWritesAllowed;
  }

  /**
   * Evaluate node health states based on heartbeat age (AC-07: detection <= 60s)
   */
  evaluateNodeHealth(nodeId: string, currentAgeSeconds: number): NodeHealthState {
    const node = this.nodes.get(nodeId);
    if (!node) return 'offline';

    node.heartbeatAgeSeconds = currentAgeSeconds;

    if (node.isPartitioned) {
      node.healthState = 'fenced';
    } else if (currentAgeSeconds > 120) {
      node.healthState = 'offline';
    } else if (currentAgeSeconds > 60) {
      node.healthState = 'stale';
    } else if (node.healthState === 'stale' || node.healthState === 'offline') {
      node.healthState = 'recovering';
    } else if (node.healthState !== 'recovering') {
      node.healthState = 'online';
    }

    return node.healthState;
  }

  /**
   * Simulate Heartbeat Drop (>60s triggers STALE)
   */
  simulateHeartbeatDelay(nodeId: string, ageSeconds: number): void {
    const node = this.nodes.get(nodeId);
    if (!node) return;
    const delayedTime = new Date(Date.now() - ageSeconds * 1000).toISOString();
    node.lastHeartbeatAt = delayedTime;
    this.evaluateNodeHealth(nodeId, ageSeconds);
  }

  /**
   * Simulate Network Partition (ADR-006 Split-Brain fencing)
   */
  simulateNetworkPartition(nodeId: string): void {
    const node = this.nodes.get(nodeId);
    if (!node) return;

    node.isPartitioned = true;
    node.healthState = 'fenced';
    // Advance cluster epoch for this node boundary to invalidate future partitioned attempts
    node.fencingToken.epoch += 1;
    node.fencingToken.sequence = 1;
  }

  /**
   * Attempt write with fencing token (AC-07: Stale token writes MUST be 0)
   */
  attemptWrite(
    nodeId: string,
    attemptedToken: { epoch: number; sequence: number },
    _payload?: string
  ): { success: boolean; error?: string } {
    const node = this.nodes.get(nodeId);
    if (!node) return { success: false, error: 'Node not found' };

    const isValid = isTokenValidAndCurrent(attemptedToken, node.fencingToken);

    if (!isValid) {
      // Monotonic fencing rejection
      const rejection: LateResultRejection = {
        requestId: `req_${Math.random().toString(36).slice(2, 8)}`,
        nodeId,
        attemptedToken,
        currentToken: { epoch: node.fencingToken.epoch, sequence: node.fencingToken.sequence },
        rejectedAt: new Date().toISOString(),
        reason: `STALE_FENCING_TOKEN: attempted (${attemptedToken.epoch}, ${attemptedToken.sequence}) < current (${node.fencingToken.epoch}, ${node.fencingToken.sequence})`,
      };
      this.lateResultRejections.unshift(rejection);
      return {
        success: false,
        error: rejection.reason,
      };
    }

    // Success write
    node.fencingToken.sequence++;
    return { success: true };
  }

  /**
   * Reconcile Node: Drain workspaces, heal partition, advance epoch, restore health (AC-07: >=95% recovery)
   */
  reconcileNode(nodeId: string): ReconciliationRecord {
    const node = this.nodes.get(nodeId);
    if (!node) {
      throw new Error(`Node ${nodeId} not found`);
    }

    const evacuatedCount = node.activeWorkspacesCount;
    node.activeWorkspacesCount = 0;
    node.isPartitioned = false;
    node.healthState = 'recovering';
    node.heartbeatAgeSeconds = 0;
    node.lastHeartbeatAt = new Date().toISOString();

    // Advance epoch to guarantee new lease
    node.fencingToken.epoch += 1;
    node.fencingToken.sequence = 1;
    node.fencingToken.issuedAt = new Date().toISOString();

    // Fast transition from recovering -> online
    node.healthState = 'online';

    const record: ReconciliationRecord = {
      reconciliationId: `rec_${Date.now().toString(36)}`,
      nodeId,
      evacuatedWorkspacesCount: evacuatedCount,
      newEpoch: node.fencingToken.epoch,
      recoverySuccess: true,
      timestamp: new Date().toISOString(),
    };

    this.reconciliationHistory.unshift(record);
    return record;
  }
}
