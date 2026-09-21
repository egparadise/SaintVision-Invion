// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApprovalReviewPanel } from '../src/features/approvals/ApprovalReviewPanel';
import * as approvalReviewApi from '../src/shared/api/approvalReview';
import type { ApprovalItem } from '../src/contracts/types';
import { approvalReviewFixture } from './fixtures/approval-review';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: any) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const sampleApprovalItem: ApprovalItem = {
  id: approvalReviewFixture.approval.approvalId,
  projectId: approvalReviewFixture.approval.projectId,
  runId: approvalReviewFixture.approval.runId,
  actionDigest: approvalReviewFixture.approval.actionDigest,
  boundRunVersion: approvalReviewFixture.approval.runVersion,
  requestedBy: approvalReviewFixture.approval.requesterId,
  requiredApprovals: approvalReviewFixture.approval.requiredApprovals,
  policyReason: approvalReviewFixture.approval.policyVersion,
  expiresAt: new Date(Date.now() + 3600000).toISOString(),
  status: 'pending',
  riskLevel: 'L2',
};

describe('ApprovalReviewPanel Async Effect & State Transition (DOM Harness)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
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

  it('1. pending state: shows review loading status and keeps approve button disabled', async () => {
    const pending = deferred<approvalReviewApi.ApprovalReview>();
    vi.spyOn(approvalReviewApi, 'fetchApprovalReview').mockReturnValue(pending.promise);

    await act(async () => {
      root.render(
        <ApprovalReviewPanel
          approval={sampleApprovalItem}
          currentUserId="usr_reviewer_01"
          onApprove={async () => {}}
          onReject={async () => {}}
        />
      );
    });

    // Verify pending status message is displayed
    const statusElem = container.querySelector('[role="status"]');
    expect(statusElem).not.toBeNull();
    expect(statusElem?.textContent).toContain('승인할 작업 내용을 조회하고 있습니다');

    // Snapshot header must NOT be visible yet
    expect(container.textContent).not.toContain('승인할 작업 스냅샷');

    // Approve button MUST be disabled during pending review
    const approveBtn = container.querySelector<HTMLButtonElement>('button:has-text("승인"), button');
    const buttons = Array.from(container.querySelectorAll('button'));
    const approveButton = buttons.find((b) => b.textContent?.includes('승인'));
    expect(approveButton).toBeDefined();
    expect(approveButton?.disabled).toBe(true);

    // Clean up deferred
    await act(async () => {
      pending.resolve(structuredClone(approvalReviewFixture));
    });
  });

  it('2. success transition: renders reviewed command arguments, policy digest, and enables approve button', async () => {
    const pending = deferred<approvalReviewApi.ApprovalReview>();
    vi.spyOn(approvalReviewApi, 'fetchApprovalReview').mockReturnValue(pending.promise);
    const onApproveSpy = vi.fn().mockResolvedValue(undefined);

    await act(async () => {
      root.render(
        <ApprovalReviewPanel
          approval={sampleApprovalItem}
          currentUserId="usr_reviewer_01"
          onApprove={onApproveSpy}
          onReject={async () => {}}
        />
      );
    });

    // Resolve with canonical contract fixture
    await act(async () => {
      pending.resolve(structuredClone(approvalReviewFixture));
    });

    // 1. Loading status must be gone
    expect(container.textContent).not.toContain('승인할 작업 내용을 조회하고 있습니다');

    // 2. Workload snapshot header & arguments must be rendered
    expect(container.textContent).toContain('승인할 작업 스냅샷');
    expect(container.textContent).toContain('echo');
    expect(container.textContent).toContain('two words');
    expect(container.textContent).toContain('<script>');
    expect(container.textContent).toContain(approvalReviewFixture.policyDigest);

    // 3. Approve button MUST now be enabled (disabled=false)
    const buttons = Array.from(container.querySelectorAll('button'));
    const approveButton = buttons.find((b) => b.textContent?.includes('승인') && !b.textContent.includes('2인'));
    expect(approveButton).toBeDefined();
    expect(approveButton?.disabled).toBe(false);

    // 4. Click approve button and assert onApprove is invoked with valid reviewedAction
    await act(async () => {
      approveButton!.click();
    });

    expect(onApproveSpy).toHaveBeenCalledTimes(1);
    const [calledId, calledNonce, calledAction] = onApproveSpy.mock.calls[0];
    expect(calledId).toBe(sampleApprovalItem.id);
    expect(calledAction).toBeDefined();
    expect(calledAction.actionDigest).toBe(sampleApprovalItem.actionDigest);
  });

  it('3. failure transition: renders role="alert" error, keeps approve button disabled, and supports retry', async () => {
    let callCount = 0;
    const firstCall = deferred<approvalReviewApi.ApprovalReview>();
    const secondCall = deferred<approvalReviewApi.ApprovalReview>();

    vi.spyOn(approvalReviewApi, 'fetchApprovalReview').mockImplementation(() => {
      callCount++;
      return callCount === 1 ? firstCall.promise : secondCall.promise;
    });

    await act(async () => {
      root.render(
        <ApprovalReviewPanel
          approval={sampleApprovalItem}
          currentUserId="usr_reviewer_01"
          onApprove={async () => {}}
          onReject={async () => {}}
        />
      );
    });

    // Reject first query with 500 error
    await act(async () => {
      firstCall.reject(new Error('500 Internal Review Service Error'));
    });

    // 1. Alert role error notice MUST appear
    const alertElem = container.querySelector('[role="alert"]');
    expect(alertElem).not.toBeNull();
    expect(alertElem?.textContent).toContain('검토 내용을 확인하지 못했습니다. 승인이 보류됩니다');

    // 2. Approve button MUST be kept disabled on error
    const buttons = Array.from(container.querySelectorAll('button'));
    const approveButton = buttons.find((b) => b.textContent?.includes('승인') && !b.textContent.includes('다시'));
    expect(approveButton).toBeDefined();
    expect(approveButton?.disabled).toBe(true);

    // 3. Retry button MUST exist
    const retryBtn = buttons.find((b) => b.textContent?.includes('다시 조회'));
    expect(retryBtn).toBeDefined();

    // Click retry
    await act(async () => {
      retryBtn!.click();
    });

    // Resolve second call successfully
    await act(async () => {
      secondCall.resolve(structuredClone(approvalReviewFixture));
    });

    // Alert must be gone, snapshot must be present, and approve button must be enabled
    expect(container.querySelector('[role="alert"]')).toBeNull();
    expect(container.textContent).toContain('승인할 작업 스냅샷');
    const retryApprovedButtons = Array.from(container.querySelectorAll('button'));
    const finalApproveBtn = retryApprovedButtons.find((b) => b.textContent?.includes('승인'));
    expect(finalApproveBtn?.disabled).toBe(false);
  });

  it('4. tamper boundary guard: mismatched action digest blocks approval button', async () => {
    const tamperedReview = structuredClone(approvalReviewFixture);
    tamperedReview.approval.actionDigest = 'f'.repeat(64); // Mismatched digest

    vi.spyOn(approvalReviewApi, 'fetchApprovalReview').mockResolvedValue(tamperedReview);

    await act(async () => {
      root.render(
        <ApprovalReviewPanel
          approval={sampleApprovalItem}
          currentUserId="usr_reviewer_01"
          onApprove={async () => {}}
          onReject={async () => {}}
        />
      );
    });

    // When digest mismatches, reviewedAction.actionDigest !== approval.actionDigest
    // Approve button MUST remain disabled
    const buttons = Array.from(container.querySelectorAll('button'));
    const approveButton = buttons.find((b) => b.textContent?.includes('승인'));
    expect(approveButton).toBeDefined();
    expect(approveButton?.disabled).toBe(true);
  });
});
