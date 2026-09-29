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

// Invariant: Bind mutation cache lifetime to auth session lifecycle (C2)
if (typeof globalThis !== 'undefined') {
  if (!globalThis.__sv_auth_teardown_listeners) {
    globalThis.__sv_auth_teardown_listeners = new Set();
  }
  globalThis.__sv_auth_teardown_listeners.add(() => {
    _resetKernelMutationCache();
  });
}

/**
 * Determines whether a mutation failure should preserve the idempotency cache for retry.
 * Invariant:
 * - Network errors or transient 5xx/408/429 (or retryable: true) keep the cached key & payload.
 * - Non-retryable final errors (409 GRAPH-0003, 403 AUTH-0034, 422, or retryable: false)
 *   MUST invalidate the cache so subsequent user clicks re-query canonical state (M1).
 */
function isRetryableMutationError(err: any): boolean {
  const isProblem = !!err?.problem;
  const status = err?.problem?.status;
  const retryableFlag = err?.problem?.retryable;

  if (!isProblem) {
    // Network error (timeout, network drop before HTTP response)
    return true;
  }
  if (retryableFlag === false) {
    // Explicitly marked non-retryable by server (e.g. 409 GRAPH-0003, 403 AUTH-0034, 422)
    return false;
  }
  if (status === 408 || status === 429 || (typeof status === 'number' && status >= 500)) {
    // Transient server or rate-limit errors
    return true;
  }
  if (retryableFlag === true && status !== 409 && status !== 403 && status !== 422) {
    return true;
  }
  // Other 4xx client errors (400, 401, 403, 404, 409, 422)
  return false;
}

/** The displayed action digest stays fixed across the challenge roundtrip. Reuses Idempotency-Key on retry. */
export async function decideApproval(
  intent: ApprovalIntent,
  decision: 'approve' | 'reject',
  options?: { idempotencyKey?: string }
) {
  const base = `${scope(intent.projectId)}/approvals/${encodeURIComponent(intent.id)}`;
  const actionDigest = intent.actionDigest;
  if (!actionDigest) throw new Error('승인 내용을 새로고침한 뒤 다시 시도하세요.');

  const opKey = `${intent.projectId ?? ''}:${intent.id}:${decision}:${actionDigest}`;
  let idempotencyKey: string;
  let input: ApprovalDecisionInput;

  const cached = decisionMutationCache.get(opKey);
  if (cached) {
    // Invariant: Once dispatched, retry uses the authoritative cached key and payload (C2)
    idempotencyKey = cached.idempotencyKey;
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
    if (!isRetryableMutationError(err)) {
      decisionMutationCache.delete(opKey);
    }
    throw err;
  }
}

/** Read the current version; never retry a mutation through an alternate route. Reuses Idempotency-Key and payload on retry. */
export async function cancelKernelRun(
  projectId: string | undefined,
  runId: string,
  options?: { idempotencyKey?: string }
) {
  const base = `${scope(projectId)}/runs/${encodeURIComponent(runId)}`;
  const opKey = `${projectId ?? ''}:${runId}`;

  let idempotencyKey: string;
  let expectedVersion: number;

  const cached = cancelMutationCache.get(opKey);
  if (cached) {
    // Invariant: Once dispatched, retry uses the authoritative cached key and payload (C2)
    idempotencyKey = cached.idempotencyKey;
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
    if (!isRetryableMutationError(err)) {
      cancelMutationCache.delete(opKey);
    }
    throw err;
  }
}
