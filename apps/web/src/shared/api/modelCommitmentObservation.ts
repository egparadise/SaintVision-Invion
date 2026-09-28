import { apiClient } from './client';
import type { ModelCommitObservation } from '@/contracts/types';

/**
 * Fetch committed model observation from control-plane.
 * Endpoint: GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment
 * Synchronized with services/control-plane/src/inv/app.py:449 and inv/model_view.py:37
 */
export async function fetchModelCommitment(
  projectId: string,
  modelId: string,
  version: string,
  signal?: AbortSignal
): Promise<ModelCommitObservation> {
  const p = projectId?.trim();
  const m = modelId?.trim();
  const v = version?.trim();
  if (!p || !m || !v) {
    throw new Error('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
  }

  const path = [p, m, v].map(encodeURIComponent);
  const result = await apiClient<ModelCommitObservation>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/commitment`,
    { method: 'GET', signal }
  );

  if (
    !result ||
    result.projectId !== p ||
    result.modelId !== m ||
    result.version !== v ||
    typeof result.manifestHash !== 'string' ||
    typeof result.sourceRunId !== 'string' ||
    result.committed !== true
  ) {
    throw new Error('ModelCommitObservation 응답 계약 불일치');
  }

  return result;
}
