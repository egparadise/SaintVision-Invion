import type { ApprovalItem } from '@/contracts/types';
import type { ApprovalReviewView } from '../../../../../packages/contracts-ts/src';
import { apiClient } from './client';
import { decideApproval } from './kernelMutations';
export type ApprovalReview = ApprovalReviewView;
type ReviewedWorkload = ApprovalReview['workload'];
type BuildReviewSummary = Extract<ReviewedWorkload, { kind: 'build' }>;
export interface ReviewedAction { approvalId: string; projectId: string; actionDigest: string; runVersion: number }
const sha256 = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
export const isBuildReviewSummary = (workload: ReviewedWorkload): workload is BuildReviewSummary =>
  workload.kind === 'build';

const BUILD_REVIEW_KEYS = [
  'kind', 'target', 'riskLevel', 'profileId', 'profileVersion', 'sourceRevision',
  'contextDigest', 'dockerfileDigest', 'networkMode', 'cacheMode', 'usesSecrets', 'secretCount',
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, expected: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const required = [...expected].sort();
  return actual.length === required.length && actual.every((key, index) => key === required[index]);
}

function projectBuildReviewSummary(value: unknown, riskLevel: string): BuildReviewSummary | null {
  if (!isRecord(value) || !hasExactKeys(value, BUILD_REVIEW_KEYS)) return null;
  const workload = value as unknown as BuildReviewSummary;
  const valid = workload.kind === 'build' && workload.target === 'image' &&
    workload.riskLevel === 'L2' && riskLevel === 'L2' &&
    typeof workload.profileId === 'string' && workload.profileId.length > 0 &&
    /^bpp_[0-9A-HJKMNP-TV-Z]{26}$/.test(workload.profileId) &&
    Number.isSafeInteger(workload.profileVersion) && workload.profileVersion > 0 &&
    Number.isSafeInteger(workload.sourceRevision) && workload.sourceRevision > 0 &&
    sha256(workload.contextDigest) && sha256(workload.dockerfileDigest) &&
    workload.networkMode === 'none' && ['disabled', 'read-only'].includes(workload.cacheMode) &&
    typeof workload.usesSecrets === 'boolean' && Number.isSafeInteger(workload.secretCount) &&
    workload.secretCount >= 0 && workload.secretCount <= 32 &&
    workload.usesSecrets === (workload.secretCount > 0);
  if (!valid) return null;
  return {
    kind: workload.kind,
    target: workload.target,
    riskLevel: workload.riskLevel,
    profileId: workload.profileId,
    profileVersion: workload.profileVersion,
    sourceRevision: workload.sourceRevision,
    contextDigest: workload.contextDigest,
    dockerfileDigest: workload.dockerfileDigest,
    networkMode: workload.networkMode,
    cacheMode: workload.cacheMode,
    usesSecrets: workload.usesSecrets,
    secretCount: workload.secretCount,
  };
}

function validWorkloadSpec(workload: Exclude<ReviewedWorkload, BuildReviewSummary>, projectId: string): boolean {
  return workload.projectId === projectId && typeof workload.workspaceId === 'string' &&
    workload.workspaceId.length > 0 && Array.isArray(workload.command) && workload.command.length > 0 &&
    workload.command.every((arg: string) => typeof arg === 'string') &&
    typeof workload.imageDigest === 'string' && /^sha256:[a-f0-9]{64}$/.test(workload.imageDigest) &&
    Number.isSafeInteger(workload.timeoutSeconds) && workload.timeoutSeconds > 0 &&
    Boolean(workload.resources) &&
    (['cpuMillis','memoryBytes','gpuCount','minVramBytes'] as const).every(k =>
      typeof workload.resources[k] === 'number' && Number.isFinite(workload.resources[k]) && workload.resources[k] >= 0);
}
export function reviewIdentity(item: ApprovalItem): string {
  return JSON.stringify([item.projectId, item.id, item.runId, item.actionDigest, item.boundRunVersion,
    item.requestedBy, item.requiredApprovals, item.policyReason, item.expiresAt, item.status]);
}
export async function fetchApprovalReview(item: ApprovalItem): Promise<ApprovalReview> {
  const expected = { ...item }; // Capture the displayed binding before awaiting the response.
  if (!expected.projectId || !sha256(expected.actionDigest)) throw new Error('승인 검토 정보가 불완전합니다.');
  const result = await apiClient<ApprovalReview>(`/v1/projects/${encodeURIComponent(expected.projectId)}/approvals/${encodeURIComponent(expected.id)}/review`);
  const a = result?.approval; const w: unknown = result?.workload;
  const workloadRecord = isRecord(w) ? w : null;
  const projectedBuild = workloadRecord?.kind === 'build'
    ? projectBuildReviewSummary(workloadRecord, result.riskLevel)
    : null;
  const workloadValid = projectedBuild !== null ||
    (workloadRecord?.kind === 'Workload' &&
      validWorkloadSpec(w as Exclude<ReviewedWorkload, BuildReviewSummary>, expected.projectId));
  if (!a || a.approvalId !== expected.id || a.projectId !== expected.projectId || a.runId !== expected.runId ||
      a.actionDigest !== expected.actionDigest || a.runVersion !== expected.boundRunVersion ||
      a.requesterId !== expected.requestedBy || a.requiredApprovals !== expected.requiredApprovals ||
      a.policyVersion !== expected.policyReason || a.expiresAt !== expected.expiresAt || a.status !== expected.status ||
      !sha256(result.policyDigest) || !['L0', 'L1', 'L2'].includes(result.riskLevel) ||
      !workloadValid) {
    throw new Error('표시할 승인 내용이 현재 안건과 일치하지 않습니다. 목록을 새로고침하세요.');
  }
  return projectedBuild ? { ...result, workload: projectedBuild } : result;
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
