import type { RunLogView } from '@/contracts/types';
import { apiClient } from './client';

export async function fetchRunLogs(projectId: string, runId: string): Promise<RunLogView> {
  const result = await apiClient<RunLogView>(
    `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/logs`
  );

  if (!result || typeof result !== 'object') {
    throw new Error('RunLogView 응답 형식 불일치');
  }

  if (result.source !== 'execution-kernel') {
    throw new Error(`RunLogView source 계약 불일치: expected 'execution-kernel', got '${(result as any).source}'`);
  }

  if (typeof result.runId !== 'string' || !result.runId) {
    throw new Error('RunLogView runId 누락');
  }

  if (typeof result.redacted !== 'boolean') {
    throw new Error('RunLogView redacted 계약 불일치');
  }

  if (result.truncated !== null && typeof result.truncated !== 'boolean') {
    throw new Error('RunLogView truncated 계약 불일치');
  }

  if (result.absentReason !== null && typeof result.absentReason !== 'string') {
    throw new Error('RunLogView absentReason 계약 불일치');
  }

  return result;
}
