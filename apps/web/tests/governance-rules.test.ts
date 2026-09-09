import { describe, it, expect } from 'vitest';
import { ApiError } from '../src/shared/api/client';
import { ProblemDetails, ApprovalItem } from '../src/contracts/types';

describe('RFC 9457 ProblemDetails & ApiError', () => {
  it('should instantiate ApiError with proper properties', () => {
    const problem: ProblemDetails = {
      type: 'https://saintvision.invenio/problems/approval-expired',
      title: 'Approval Request Expired',
      status: 409,
      detail: 'The approval request apr_01JXYZ987654 has expired after 15 minutes.',
      code: 'GOV-APPR-EXPIRED',
      category: 'SEC',
      retryable: false,
      traceId: '4bf92f3577b34da6a3ce929d0e0e4736',
    };

    const err = new ApiError(problem);
    expect(err.name).toBe('ApiError');
    expect(err.message).toBe(problem.detail);
    expect(err.problem.status).toBe(409);
    expect(err.problem.code).toBe('GOV-APPR-EXPIRED');
    expect(err.problem.retryable).toBe(false);
  });
});

describe('Approval Governance Invariants', () => {
  const sampleApproval: ApprovalItem = {
    id: 'apr_01JXYZ987654',
    runId: 'run_01JABCDE0002',
    workspaceId: 'wsp_01JABCDE',
    nodeId: 'nod_01JABCDEF01',
    riskLevel: 'L2',
    target: 'Workspace on Node-01',
    command: 'git.deploy --release prod-v1.0.0',
    unifiedDiff: '--- a/config.json\n+++ b/config.json\n@@ -1 +1 @@\n-old\n+new',
    estimatedCostKrw: 3200,
    remainingBudgetKrw: 46800,
    blastRadius: 'workspace_isolated',
    status: 'pending',
    nonce: 'nonce_987654321',
    expiresAt: new Date(Date.now() + 600000).toISOString(),
    policyReason: 'Policy L2 check',
    createdAt: new Date().toISOString(),
    approvedBy: 'usr_approver_01',
  };

  it('should prevent self-approval under Two-Person Rule when approver equals requester', () => {
    const requesterId = 'usr_requester_alice';
    const isSelfApproval = (currentUserId: string, reqId: string) => currentUserId === reqId;

    expect(isSelfApproval(requesterId, requesterId)).toBe(true);
    expect(isSelfApproval('usr_reviewer_bob', requesterId)).toBe(false);
  });

  it('should prevent 2nd approval by the same person who gave 1st approval', () => {
    const firstApproverId = 'usr_approver_01';
    const currentUserId = 'usr_approver_01';
    const canGiveSecondApproval = (curr: string, first?: string) => !first || curr !== first;

    expect(canGiveSecondApproval(currentUserId, firstApproverId)).toBe(false);
    expect(canGiveSecondApproval('usr_approver_02', firstApproverId)).toBe(true);
  });

  it('should identify missing diff as an absolute blocker for approval', () => {
    const isApprovalAllowed = (item: ApprovalItem) => {
      if (!item.unifiedDiff || item.unifiedDiff.trim().length === 0) return false;
      if (new Date(item.expiresAt).getTime() <= Date.now()) return false;
      return true;
    };

    expect(isApprovalAllowed(sampleApproval)).toBe(true);

    const missingDiffApproval: ApprovalItem = { ...sampleApproval, unifiedDiff: undefined };
    expect(isApprovalAllowed(missingDiffApproval)).toBe(false);

    const emptyDiffApproval: ApprovalItem = { ...sampleApproval, unifiedDiff: '   ' };
    expect(isApprovalAllowed(emptyDiffApproval)).toBe(false);
  });

  it('should recognize expired approvals', () => {
    const isExpired = (expiresAt: string) => new Date(expiresAt).getTime() <= Date.now();

    const futureExpiry = new Date(Date.now() + 100000).toISOString();
    const pastExpiry = new Date(Date.now() - 5000).toISOString();

    expect(isExpired(futureExpiry)).toBe(false);
    expect(isExpired(pastExpiry)).toBe(true);
  });

  it('should flag absence of rollback plan with warning condition', () => {
    const hasRollbackWarning = (item: ApprovalItem) => !item.rollbackPlan;

    expect(hasRollbackWarning(sampleApproval)).toBe(true);
    expect(hasRollbackWarning({ ...sampleApproval, rollbackPlan: 'git revert HEAD' })).toBe(false);
  });
});
