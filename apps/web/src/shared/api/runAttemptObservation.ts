import type { RunAttemptList } from '@/contracts/types';
import { apiClient } from './client';

export interface FetchRunAttemptsOptions {
  after?: number;
  limit?: number;
}

export async function fetchRunAttempts(
  projectId: string,
  runId: string,
  options?: FetchRunAttemptsOptions
): Promise<RunAttemptList> {
  const queryParams = new URLSearchParams();
  if (options?.after !== undefined) queryParams.set('after', String(options.after));
  if (options?.limit !== undefined) queryParams.set('limit', String(options.limit));
  const queryString = queryParams.toString() ? `?${queryParams.toString()}` : '';

  const result = await apiClient<RunAttemptList>(
    `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/attempts${queryString}`
  );

  if (!result || typeof result !== 'object') {
    throw new Error('RunAttemptList 응답 형식 불일치');
  }

  if (result.source !== 'execution-kernel') {
    throw new Error(`RunAttemptList source 계약 불일치: expected 'execution-kernel', got '${(result as any).source}'`);
  }

  if (typeof result.runId !== 'string' || !result.runId) {
    throw new Error('RunAttemptList runId 누락');
  }

  if (!Array.isArray(result.attempts)) {
    throw new Error('RunAttemptList attempts 배열 누락');
  }

  if (typeof result.count !== 'number' || result.count < 0) {
    throw new Error('RunAttemptList count 계약 불일치');
  }

  if (result.nextCursor !== null && typeof result.nextCursor !== 'number') {
    throw new Error('RunAttemptList nextCursor 계약 불일치');
  }

  for (const item of result.attempts) {
    if (typeof item.attemptNumber !== 'number') {
      throw new Error('RunAttemptItem attemptNumber 계약 불일치');
    }
    if (item.startedAt !== null && typeof item.startedAt !== 'string') {
      throw new Error('RunAttemptItem startedAt 계약 불일치');
    }
    if (item.nodeId !== null && typeof item.nodeId !== 'string') {
      throw new Error('RunAttemptItem nodeId 계약 불일치');
    }
    if (item.commandId !== null && typeof item.commandId !== 'string') {
      throw new Error('RunAttemptItem commandId 계약 불일치');
    }
    if (item.stopReceiptId !== null && typeof item.stopReceiptId !== 'string') {
      throw new Error('RunAttemptItem stopReceiptId 계약 불일치');
    }
    if (item.exitCode !== null && typeof item.exitCode !== 'number') {
      throw new Error('RunAttemptItem exitCode 계약 불일치');
    }
    if (item.reason !== null && typeof item.reason !== 'string') {
      throw new Error('RunAttemptItem reason 계약 불일치');
    }
    if (item.evidenceId !== null && typeof item.evidenceId !== 'string') {
      throw new Error('RunAttemptItem evidenceId 계약 불일치');
    }
  }

  return result;
}
