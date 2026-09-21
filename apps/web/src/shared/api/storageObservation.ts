import { apiClient } from './client';
import type { StorageObservationView, RecordedStorageObservation } from '@/contracts/types';

export async function fetchStorageObservation(
  projectId: string,
  runId: string,
  requestId: string,
  signal?: AbortSignal
): Promise<StorageObservationView> {
  if (!projectId || !projectId.trim() || !runId || !runId.trim() || !requestId || !requestId.trim()) {
    throw new Error('프로젝트 ID, Run ID, Request ID를 확인하세요.');
  }

  const path = [projectId.trim(), runId.trim(), requestId.trim()].map(encodeURIComponent);
  const result = await apiClient<StorageObservationView>(
    `/v1/projects/${path[0]}/runs/${path[1]}/storage-samples/${path[2]}`,
    { method: 'GET', signal }
  );

  if (
    !result ||
    result.requestId !== requestId.trim() ||
    result.projectId !== projectId.trim() ||
    result.runId !== runId.trim() ||
    !['pending', 'expired', 'recorded'].includes(result.status) ||
    result.currentHealth !== 'unknown' ||
    result.operationalAcceptanceAssessed !== false
  ) {
    throw new Error('StorageObservationView 응답 계약 불일치');
  }

  if (result.status === 'recorded') {
    const obs = result.observation as RecordedStorageObservation | null;
    if (
      !obs ||
      obs.integrityVerified !== true ||
      typeof obs.sampleHealthy !== 'boolean' ||
      typeof obs.sampled !== 'number' ||
      typeof obs.mismatches !== 'number' ||
      typeof obs.unverifiable !== 'number' ||
      typeof obs.examined !== 'number' ||
      typeof obs.unsampled !== 'number'
    ) {
      throw new Error('RecordedStorageObservation 응답 계약 불일치');
    }
  } else {
    if (result.observation !== null) {
      throw new Error('Pending/Expired 상태의 observation은 null이어야 합니다.');
    }
  }

  return result;
}
