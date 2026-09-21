import type { RunArtifactList } from '@/contracts/types';
import { apiClient } from './client';

export async function fetchRunArtifacts(projectId: string, runId: string): Promise<RunArtifactList> {
  if (!projectId) throw new Error('프로젝트 정보가 없습니다.');
  const result = await apiClient<RunArtifactList>(
    `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/artifacts`
  );

  if (!result || typeof result !== 'object') {
    throw new Error('RunArtifactList 응답 형식 불일치');
  }

  if (result.source !== 'execution-kernel') {
    throw new Error(`RunArtifactList source 계약 불일치: expected 'execution-kernel', got '${(result as any).source}'`);
  }

  if (typeof result.runId !== 'string' || !result.runId) {
    throw new Error('RunArtifactList runId 누락');
  }

  if (!Array.isArray(result.artifacts)) {
    throw new Error('RunArtifactList artifacts 배열 누락');
  }

  if (typeof result.count !== 'number') {
    throw new Error('RunArtifactList count 계약 불일치');
  }

  if (typeof result.verifiedCount !== 'number') {
    throw new Error('RunArtifactList verifiedCount 계약 불일치');
  }

  if (result.completedAt !== undefined && result.completedAt !== null && typeof result.completedAt !== 'string') {
    throw new Error('RunArtifactList completedAt 계약 불일치');
  }

  return result;
}

export function getArtifactDownloadUrl(projectId: string, runId: string, path: string): string {
  return `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/artifacts/content?path=${encodeURIComponent(path)}`;
}
