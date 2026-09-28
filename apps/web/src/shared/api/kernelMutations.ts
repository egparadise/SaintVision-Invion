import { apiClient, generateTraceId } from './client';
import type {
  ApprovalChallenge,
  ApprovalDecisionInput,
  ApprovalView,
  ControlRunDetail,
} from '../../../../../packages/contracts-ts/src';

interface ApprovalIntent {
  id: string;
  projectId?: string;
  actionDigest?: string;
}

function scope(projectId: string | undefined): string {
  if (!projectId) throw new Error('프로젝트를 확인한 뒤 다시 시도하세요.');
  return `/v1/projects/${encodeURIComponent(projectId)}`;
}

interface CachedCancellation {
  idempotencyKey: string;
  expectedVersion: number;
}

const cancelMutationCache = new Map<string, CachedCancellation>();

interface CachedDecision {
  idempotencyKey: string;
  input: ApprovalDecisionInput;
}

const decisionMutationCache = new Map<string, CachedDecision>();

export function _resetKernelMutationCache() {
  cancelMutationCache.clear();
  decisionMutationCache.clear();
}

/** The displayed action digest stays fixed across the challenge roundtrip. Reuses Idempotency-Key on retry. */
export async function decideApproval(
  intent: ApprovalIntent,
  decision: 'approve' | 'reject',
  options?: { idempotencyKey?: string; forceNewKey?: boolean }
) {
  const base = `${scope(intent.projectId)}/approvals/${encodeURIComponent(intent.id)}`;
  const actionDigest = intent.actionDigest;
  if (!actionDigest) throw new Error('승인 내용을 새로고침한 뒤 다시 시도하세요.');

  const opKey = `${intent.projectId ?? ''}:${intent.id}:${decision}:${actionDigest}`;
  let idempotencyKey: string;
  let input: ApprovalDecisionInput;

  const cached = decisionMutationCache.get(opKey);
  if (cached && !options?.forceNewKey) {
    idempotencyKey = options?.idempotencyKey || cached.idempotencyKey;
    input = cached.input;
  } else {
    const challenge = await apiClient<ApprovalChallenge>(`${base}/challenge`, {
      method: 'POST', body: JSON.stringify({}),
    });
    if (!challenge?.nonce) throw new Error('승인 확인 정보를 받지 못했습니다.');
    idempotencyKey = options?.idempotencyKey || generateTraceId();
    input = { decision, nonce: challenge.nonce, actionDigest };
    decisionMutationCache.set(opKey, { idempotencyKey, input });
  }

  try {
    const result = await apiClient<ApprovalView>(`${base}/decision`, {
      method: 'POST',
      body: JSON.stringify(input),
      idempotencyKey,
    });
    decisionMutationCache.delete(opKey);
    return result;
  } catch (err) {
    throw err;
  }
}

/** Read the current version; never retry a mutation through an alternate route. Reuses Idempotency-Key and payload on retry. */
export async function cancelKernelRun(
  projectId: string | undefined,
  runId: string,
  options?: { idempotencyKey?: string; forceNewKey?: boolean }
) {
  const base = `${scope(projectId)}/runs/${encodeURIComponent(runId)}`;
  const opKey = `${projectId ?? ''}:${runId}`;

  let idempotencyKey: string;
  let expectedVersion: number;

  const cached = cancelMutationCache.get(opKey);
  if (cached && !options?.forceNewKey) {
    idempotencyKey = options?.idempotencyKey || cached.idempotencyKey;
    expectedVersion = cached.expectedVersion;
  } else {
    const current = await apiClient<ControlRunDetail>(base);
    if (current?.runId !== runId || !Number.isSafeInteger(current.version) || current.version < 1) {
      throw new Error('실행 버전을 확인하지 못했습니다. 새로고침한 뒤 다시 시도하세요.');
    }
    idempotencyKey = options?.idempotencyKey || generateTraceId();
    expectedVersion = current.version;
    cancelMutationCache.set(opKey, { idempotencyKey, expectedVersion });
  }

  try {
    const result = await apiClient(`${base}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ expectedVersion }),
      idempotencyKey,
    });
    cancelMutationCache.delete(opKey);
    return result;
  } catch (err) {
    throw err;
  }
}
