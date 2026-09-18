import type { ApprovalItem, ApprovalPage, RunItem, RunState } from '@/contracts/types';
import { apiClient } from './client';
const states: RunState[] = ['draft', 'validated', 'planned', 'awaiting_approval', 'scheduled',
  'running', 'verifying', 'recovering', 'succeeded', 'failed', 'cancelled'];
export interface KernelRun {
  runId: string; tenantId: string; projectId: string; state: RunState; version: number; attempt: number;
}
export async function fetchObservedRuns(projectId: string): Promise<RunItem[]> {
  const page = await apiClient<{ items: KernelRun[] }>(`/v1/projects/${encodeURIComponent(projectId)}/runs`);
  if (!Array.isArray(page.items)) throw new Error('Run 응답 형식 불일치');
  return page.items.map(run => {
    if (run.projectId !== projectId || !run.runId || !states.includes(run.state) ||
        !Number.isSafeInteger(run.version) || run.version < 1 ||
        !Number.isSafeInteger(run.attempt) || run.attempt < 0) throw new Error('Run 관측 계약 불일치');
    return { id: run.runId, projectId: run.projectId, state: run.state, version: run.version, attempt: run.attempt };
  });
}
export async function fetchObservedApprovals(projectId: string): Promise<ApprovalItem[]> {
  const page = await apiClient<ApprovalPage>(`/v1/projects/${encodeURIComponent(projectId)}/approvals`);
  if (!Array.isArray(page.items)) throw new Error('승인 응답 형식 불일치');
  return page.items.map(item => {
    if (item.projectId !== projectId || !item.approvalId || !item.runId || !item.requesterId ||
        !item.actionDigest || ![1, 2].includes(item.requiredApprovals) ||
        !['pending','approved','rejected','expired','dispatched'].includes(item.status) ||
        !Number.isFinite(Date.parse(item.expiresAt)) || !Number.isSafeInteger(item.runVersion) || item.runVersion < 1)
      throw new Error('승인 관측 계약 불일치');
    return { id: item.approvalId, projectId: item.projectId, runId: item.runId,
      requestedBy: item.requesterId, actionDigest: item.actionDigest, requiredApprovals: item.requiredApprovals,
      status: item.status, expiresAt: item.expiresAt, boundRunVersion: item.runVersion,
      policyReason: item.policyVersion };
  });
}
