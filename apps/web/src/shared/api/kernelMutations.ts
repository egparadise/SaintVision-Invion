import { apiClient, generateTraceId } from './client';

interface ApprovalIntent {
  id: string;
  projectId?: string;
  actionDigest?: string;
}

function scope(projectId: string | undefined): string {
  if (!projectId) throw new Error('프로젝트를 확인한 뒤 다시 시도하세요.');
  return `/v1/projects/${encodeURIComponent(projectId)}`;
}

/** The displayed action digest stays fixed across the challenge roundtrip. */
export async function decideApproval(intent: ApprovalIntent, decision: 'approve' | 'reject') {
  const base = `${scope(intent.projectId)}/approvals/${encodeURIComponent(intent.id)}`;
  const actionDigest = intent.actionDigest;
  if (!actionDigest) throw new Error('승인 내용을 새로고침한 뒤 다시 시도하세요.');
  const challenge = await apiClient<{ nonce: string }>(`${base}/challenge`, {
    method: 'POST', body: JSON.stringify({}),
  });
  if (!challenge?.nonce) throw new Error('승인 확인 정보를 받지 못했습니다.');
  return apiClient(`${base}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, nonce: challenge.nonce, actionDigest }),
    idempotencyKey: generateTraceId(),
  });
}

/** Read the current version; never retry a mutation through an alternate route. */
export async function cancelKernelRun(projectId: string | undefined, runId: string) {
  const base = `${scope(projectId)}/runs/${encodeURIComponent(runId)}`;
  const current = await apiClient<{ runId: string; version: number }>(base);
  if (current?.runId !== runId || !Number.isSafeInteger(current.version) || current.version < 1) {
    throw new Error('실행 버전을 확인하지 못했습니다. 새로고침한 뒤 다시 시도하세요.');
  }
  return apiClient(`${base}/cancel`, {
    method: 'POST', body: JSON.stringify({ expectedVersion: current.version }),
    idempotencyKey: generateTraceId(),
  });
}
