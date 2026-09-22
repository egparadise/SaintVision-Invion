import { apiClient } from './client';
import type { ModelRetryPrepareInput, ModelRetryPrepareResult, ProblemDetails } from '@/contracts/types';

export interface PrepareModelRetryOptions {
  idempotencyKey?: string;
  runVersion?: number;
}

/**
 * Format RFC 9457 Problem Details for Model Retry domain errors according to Section 6 of design memo.
 * Evaluates both ProblemDetails.code and status.
 */
export function formatModelRetryProblem(problem: ProblemDetails, projectId: string): string {
  const status = problem.status;
  const code = problem.code || '';
  const detail = problem.detail || problem.title || '서버 오류';

  if (code === 'MODEL-0003' || (status === 409 && detail.includes('active'))) {
    return `재시도 충돌 (409 MODEL-0003): 부모 Run이 실패 종단 상태가 아니거나 이미 활성 자식 Run 또는 유효한 배치 예약이 존재합니다. (${detail})`;
  }
  if (code === 'MODEL-0001') {
    return `모델 미등록 충돌 (409 MODEL-0001): 대상 모델 식별자 또는 매핑이 등록되어 있지 않습니다. (${detail})`;
  }
  if (code === 'IDEM-0001') {
    return `멱등성 충돌 (409 IDEM-0001): 동일한 멱등성 키로 상이한 재시도 파라미터가 요청되었습니다. (${detail})`;
  }
  if (code === 'AUTH-0030' || status === 403) {
    return `권한 거부 (403 AUTH-0030): 현재 계정은 프로젝트 ${projectId}에 대한 Model Retry 생성 권한이 없습니다. 관리자에게 문의하십시오. (${detail})`;
  }
  if (code === 'MODEL-0007' || code === 'LEASE-0003' || code === 'MODEL-0002' || status === 503) {
    return `서비스 이용 불가 (503): 제어 평면의 Model Retry 스케줄러가 구성되지 않았거나 클러스터 내 요구 사양을 만족하는 가용 노드가 없습니다. (${detail})`;
  }
  if (code.startsWith('VAL-') || status === 422 || status === 400) {
    return `요청 규격 위반 (${status || 422} ${code || 'VAL'}): 요청 파라미터가 ModelRetryPrepareInput 계약 규격에 부합하지 않습니다. (${detail})`;
  }
  if (status === 409) {
    return `재시도 충돌 (409): ${detail}`;
  }
  return `Model Retry 요청 실패 (${status || '오류'}): ${detail}`;
}

/**
 * Request preparation of Model Retry on a failed terminal Run (POST /v1/projects/{project}/runs/{parent}/model-retries).
 * Adheres strictly to Decision #6 6a and Contract 563c54ce.
 * Enforces stable Idempotency-Key per parent Run and refuses synthetic resource defaults.
 */
export async function prepareModelRetry(
  projectId: string,
  parentRunId: string,
  input: ModelRetryPrepareInput,
  options: PrepareModelRetryOptions = {},
): Promise<ModelRetryPrepareResult> {
  if (!projectId || !projectId.trim()) {
    throw new Error('프로젝트 식별자(projectId)가 유효하지 않습니다.');
  }
  if (!parentRunId || !parentRunId.trim()) {
    throw new Error('부모 실행 식별자(parentRunId)가 유효하지 않습니다.');
  }
  if (!input || typeof input.cpuMillis !== 'number' || typeof input.memoryBytes !== 'number') {
    throw new Error('재시도 입력 사양(input)이 유효하지 않습니다.');
  }

  const idempotencyKey =
    options.idempotencyKey ||
    `model-retry:${projectId}:${parentRunId}:${options.runVersion ?? 1}`;

  const endpoint = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(parentRunId)}/model-retries`;

  return apiClient<ModelRetryPrepareResult>(endpoint, {
    method: 'POST',
    idempotencyKey,
    body: JSON.stringify(input),
  });
}
