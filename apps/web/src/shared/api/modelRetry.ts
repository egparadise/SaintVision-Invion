import { apiClient } from './client';
import type { ModelRetryPrepareInput, ModelRetryPrepareResult, ProblemDetails } from '@/contracts/types';

export interface PrepareModelRetryOptions {
  input?: Partial<ModelRetryPrepareInput>;
  idempotencyKey?: string;
}

/**
 * Format RFC 9457 Problem Details for Model Retry domain errors according to Section 6 of design memo.
 */
export function formatModelRetryProblem(problem: ProblemDetails, projectId: string): string {
  const status = problem.status;
  const detail = problem.detail || problem.title || '서버 오류';

  if (status === 409) {
    return `재시도 충돌 (409): 부모 Run이 실패 종단 상태가 아니거나, 이미 활성 자식 Run 또는 유효한 배치 예약이 존재합니다. (${detail})`;
  }
  if (status === 403) {
    return `권한 거부 (403): 현재 사용자 계정은 프로젝트 ${projectId}에 대한 Model Retry 생성 권한이 없습니다. 관리자에게 문의하십시오. (${detail})`;
  }
  if (status === 503) {
    return `서비스 이용 불가 (503): 제어 평면의 Model Retry 스케줄러가 구성되지 않았거나, 클러스터 내 요구 사양을 만족하는 가용 노드가 없습니다. (${detail})`;
  }
  if (status === 400) {
    return `요청 규격 오류 (400): 요청 파라미터가 ModelRetryPrepareInput 계약 규격에 부합하지 않습니다. (${detail})`;
  }
  return `Model Retry 요청 실패 (${status}): ${detail}`;
}

/**
 * Request preparation of Model Retry on a failed terminal Run (POST /v1/projects/{project}/runs/{parent}/model-retries).
 * Adheres strictly to Decision #6 6a and Contract 563c54ce.
 */
export async function prepareModelRetry(
  projectId: string,
  parentRunId: string,
  options: PrepareModelRetryOptions = {},
): Promise<ModelRetryPrepareResult> {
  if (!projectId || !projectId.trim()) {
    throw new Error('프로젝트 식별자(projectId)가 유효하지 않습니다.');
  }
  if (!parentRunId || !parentRunId.trim()) {
    throw new Error('부모 실행 식별자(parentRunId)가 유효하지 않습니다.');
  }

  const payload: ModelRetryPrepareInput = {
    cpuMillis: options.input?.cpuMillis ?? 500,
    memoryBytes: options.input?.memoryBytes ?? 1073741824,
    gpuCount: options.input?.gpuCount ?? 0,
    minVramBytes: options.input?.minVramBytes ?? 0,
    requiredBytes: options.input?.requiredBytes ?? 0,
    maxHostLoad: options.input?.maxHostLoad ?? 0.8,
    runtime: 'container',
    policyVersion: options.input?.policyVersion ?? 'model-retry:1',
    ttlSeconds: options.input?.ttlSeconds ?? 30,
    ...(options.input?.nodeIds ? { nodeIds: options.input.nodeIds } : {}),
  };

  const idempotencyKey =
    options.idempotencyKey ||
    `idmp_model_retry_${projectId}_${parentRunId}_${Date.now()}`;

  const endpoint = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(parentRunId)}/model-retries`;

  return apiClient<ModelRetryPrepareResult>(endpoint, {
    method: 'POST',
    idempotencyKey,
    body: JSON.stringify(payload),
  });
}
