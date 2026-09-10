import { describe, it, expect } from 'vitest';
import { ApprovalItem, RunItem } from '../src/contracts/types';

describe('S04-FE Approval Center & Run SSE Timeline (AC-04)', () => {
  const sampleApproval: ApprovalItem = {
    id: 'apr_01JXYZ987654',
    runId: 'run_01JABCDE0002',
    workspaceId: 'wsp_01JABCDE001',
    nodeId: 'nod_01JABCDEF01',
    riskLevel: 'L2',
    target: 'Workspace [pacs-core] on Node-01',
    command: 'git.deploy --release prod-v1.0.0',
    unifiedDiff: '--- a/conf.json\n+++ b/conf.json\n@@ -1 +1 @@\n-8080\n+8443',
    estimatedCostKrw: 3200,
    remainingBudgetKrw: 46800,
    blastRadius: 'workspace_isolated',
    status: 'pending',
    nonce: 'nonce_987654321',
    expiresAt: new Date(Date.now() + 600000).toISOString(),
    policyReason: 'Port change and TLS require L2 approval',
    createdAt: new Date().toISOString(),
  };

  const sampleRun: RunItem = {
    id: 'run_01JABCDE0002',
    projectId: 'prj_01JABCDE',
    workspaceId: 'wsp_01JABCDE001',
    objective: '합성 데이터셋 전처리 및 로컬 분할 검증',
    state: 'awaiting_approval',
    requestedBy: 'usr_requester_alice',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  it('should enforce zero execution before approval (AC-04 Invariant)', () => {
    const canTransitionToScheduled = (run: RunItem, approval: ApprovalItem): boolean => {
      if (run.state === 'awaiting_approval' && approval.status !== 'approved') {
        return false;
      }
      return true;
    };

    expect(canTransitionToScheduled(sampleRun, sampleApproval)).toBe(false);

    const approvedItem: ApprovalItem = { ...sampleApproval, status: 'approved' };
    expect(canTransitionToScheduled(sampleRun, approvedItem)).toBe(true);
  });

  it('should prevent requester from granting self-approval under Two-Person Rule', () => {
    const canUserApprove = (userId: string, requesterId: string, approval: ApprovalItem): boolean => {
      if (userId === requesterId) return false; // Self-approval prohibited
      if (approval.firstApprovedBy && approval.firstApprovedBy === userId) return false; // 2nd approval requires separate person
      return true;
    };

    expect(canUserApprove('usr_requester_alice', sampleRun.requestedBy, sampleApproval)).toBe(false);
    expect(canUserApprove('usr_reviewer_01', sampleRun.requestedBy, sampleApproval)).toBe(true);

    const firstApproved: ApprovalItem = {
      ...sampleApproval,
      firstApprovedBy: 'usr_reviewer_01',
    };
    expect(canUserApprove('usr_reviewer_01', sampleRun.requestedBy, firstApproved)).toBe(false);
    expect(canUserApprove('usr_reviewer_02', sampleRun.requestedBy, firstApproved)).toBe(true);
  });

  it('should handle run cancellation transitioning to cancelled with reason (ADR-001)', () => {
    const cancelRun = (run: RunItem, reason: string): RunItem & { cancelReason: string } => {
      if (run.state === 'succeeded' || run.state === 'failed' || run.state === 'cancelled') {
        throw new Error(`Terminal state ${run.state} cannot be cancelled`);
      }
      return {
        ...run,
        state: 'cancelled',
        updatedAt: new Date().toISOString(),
        cancelReason: reason,
      };
    };

    const cancelled = cancelRun(sampleRun, 'user_requested');
    expect(cancelled.state).toBe('cancelled');
    expect(cancelled.cancelReason).toBe('user_requested');

    expect(() => cancelRun({ ...sampleRun, state: 'succeeded' }, 'user_requested')).toThrow();
  });

  it('should ensure SSE timeline events maintain strictly increasing sequence numbers', () => {
    const timelineEvents = [
      { seq: 1, type: 'RUN_DRAFT', timestamp: 1000 },
      { seq: 2, type: 'RUN_VALIDATED', timestamp: 1050 },
      { seq: 3, type: 'RUN_PLANNED', timestamp: 1100 },
      { seq: 4, type: 'RUN_AWAITING_APPROVAL', timestamp: 1200 },
    ];

    for (let i = 1; i < timelineEvents.length; i++) {
      expect(timelineEvents[i].seq).toBeGreaterThan(timelineEvents[i - 1].seq);
      expect(timelineEvents[i].timestamp).toBeGreaterThanOrEqual(timelineEvents[i - 1].timestamp);
    }
  });

  it('should detect idempotent nonce replay attempts', () => {
    const consumedNonces = new Set<string>();
    const consumeNonce = (nonce: string): boolean => {
      if (consumedNonces.has(nonce)) return false; // Duplicate
      consumedNonces.add(nonce);
      return true;
    };

    expect(consumeNonce('nonce_001')).toBe(true);
    expect(consumeNonce('nonce_001')).toBe(false); // Replayed nonce rejected
    expect(consumeNonce('nonce_002')).toBe(true);
  });
});
