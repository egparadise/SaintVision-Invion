import type { ApprovalItem, ApprovalView, RiskLevel } from '@/contracts/types';
import { apiClient } from './client';
import { decideApproval } from './kernelMutations';
export interface ApprovalReview {
  approval: ApprovalView;
  workload: { projectId: string; workspaceId: string; command: string[]; imageDigest: string;
    resources: Record<string, number>; timeoutSeconds: number; [key: string]: unknown };
  riskLevel: Exclude<RiskLevel, 'L3'>;
  policyDigest: string;
}
export interface ReviewedAction { approvalId: string; projectId: string; actionDigest: string; runVersion: number }
const sha256 = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
export function reviewIdentity(item: ApprovalItem): string {
  return JSON.stringify([item.projectId, item.id, item.runId, item.actionDigest, item.boundRunVersion,
    item.requestedBy, item.requiredApprovals, item.policyReason, item.expiresAt, item.status]);
}
export async function fetchApprovalReview(item: ApprovalItem): Promise<ApprovalReview> {
  const expected = { ...item }; // Capture the displayed binding before awaiting the response.
  if (!expected.projectId || !sha256(expected.actionDigest)) throw new Error('승인 검토 정보가 불완전합니다.');
  const result = await apiClient<ApprovalReview>(`/v1/projects/${encodeURIComponent(expected.projectId)}/approvals/${encodeURIComponent(expected.id)}/review`);
  const a = result?.approval; const w = result?.workload;
  if (!a || a.approvalId !== expected.id || a.projectId !== expected.projectId || a.runId !== expected.runId ||
      a.actionDigest !== expected.actionDigest || a.runVersion !== expected.boundRunVersion ||
      a.requesterId !== expected.requestedBy || a.requiredApprovals !== expected.requiredApprovals ||
      a.policyVersion !== expected.policyReason || a.expiresAt !== expected.expiresAt || a.status !== expected.status ||
      !sha256(result.policyDigest) || !['L0', 'L1', 'L2'].includes(result.riskLevel) ||
      !w || w.projectId !== expected.projectId || typeof w.workspaceId !== 'string' || !w.workspaceId ||
      !Array.isArray(w.command) || !w.command.length || w.command.some(arg => typeof arg !== 'string') ||
      typeof w.imageDigest !== 'string' || !/^sha256:[a-f0-9]{64}$/.test(w.imageDigest) ||
      !Number.isSafeInteger(w.timeoutSeconds) || w.timeoutSeconds < 1 || !w.resources ||
      ['cpuMillis','memoryBytes','gpuCount','minVramBytes'].some(k =>
        typeof w.resources[k] !== 'number' || !Number.isFinite(w.resources[k]) || w.resources[k] < 0)) {
    throw new Error('표시할 승인 내용이 현재 안건과 일치하지 않습니다. 목록을 새로고침하세요.');
  }
  return result;
}
export function reviewedAction(review: ApprovalReview): ReviewedAction {
  const a = review.approval;
  return { approvalId: a.approvalId, projectId: a.projectId, actionDigest: a.actionDigest, runVersion: a.runVersion };
}
export async function approveReviewed(item: ApprovalItem, shown?: ReviewedAction) {
  if (!shown || item.id !== shown.approvalId || item.projectId !== shown.projectId ||
      item.actionDigest !== shown.actionDigest || item.boundRunVersion !== shown.runVersion ||
      !sha256(shown.actionDigest) || item.status !== 'pending' || !Number.isFinite(Date.parse(item.expiresAt)) || Date.parse(item.expiresAt) <= Date.now())
    throw new Error('확인한 승인 내용이 변경되었습니다. 다시 검토하세요.');
  return decideApproval({ id: shown.approvalId, projectId: shown.projectId, actionDigest: shown.actionDigest }, 'approve');
}
