import { apiClient } from './client';
import type {
  ModelVersionRegisterRequest,
} from '@/contracts/model-version-register-request';
import type {
  ModelVersionResponse,
} from '@/contracts/model-version-response';
import type {
  RetentionPinRequest,
} from '@/contracts/retention-pin-request';
import type {
  RetentionPinResponse,
} from '@/contracts/retention-pin-response';
import type {
  ModelReleaseRequest,
} from '@/contracts/model-release-request';
import type {
  ModelReleaseResponse,
} from '@/contracts/model-release-response';
import type {
  ModelLineageTraceResponse,
  LineageDatasetVersion,
  LineageDeployment,
  LineageUnresolved,
} from '@/contracts/model-lineage-trace-response';

const HEX_64_REGEX = /^[0-9a-f]{64}$/;
const ISO_DATE_TIME_REGEX =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

export function isValidIsoDateTime(value: unknown): boolean {
  if (typeof value !== 'string') return false;
  if (!ISO_DATE_TIME_REGEX.test(value)) return false;
  const parsed = Date.parse(value);
  return !Number.isNaN(parsed);
}

export function generateIdempotencyKey(prefix = 'idem'): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  const nonce = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `${prefix}_${Date.now()}_${nonce}`.slice(0, 128);
}

export function isLineageDatasetVersion(data: unknown): data is LineageDatasetVersion {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.datasetVersionId === 'string' &&
    d.datasetVersionId.length > 0 &&
    typeof d.version === 'string' &&
    d.version.length >= 1 &&
    d.version.length <= 64 &&
    typeof d.contentSha256 === 'string' &&
    HEX_64_REGEX.test(d.contentSha256) &&
    typeof d.uri === 'string' &&
    d.uri.length >= 1
  );
}

export function isLineageDeployment(data: unknown): data is LineageDeployment {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  const validEnvironments = ['lab', 'staging', 'pilot'];
  const validStatuses = ['pending', 'active', 'superseded', 'rolled_back', 'failed'];

  if (
    typeof d.deploymentId !== 'string' ||
    d.deploymentId.length === 0 ||
    typeof d.environment !== 'string' ||
    !validEnvironments.includes(d.environment) ||
    typeof d.status !== 'string' ||
    !validStatuses.includes(d.status) ||
    typeof d.deployedDigest !== 'string' ||
    !HEX_64_REGEX.test(d.deployedDigest) ||
    !isValidIsoDateTime(d.deployedAt)
  ) {
    return false;
  }

  if (d.approvalId !== undefined && d.approvalId !== null && typeof d.approvalId !== 'string') {
    return false;
  }
  if (d.imageId !== undefined && d.imageId !== null && typeof d.imageId !== 'string') {
    return false;
  }
  if (
    d.supersededAt !== undefined &&
    d.supersededAt !== null &&
    !isValidIsoDateTime(d.supersededAt)
  ) {
    return false;
  }

  return true;
}

export function isLineageUnresolved(data: unknown): data is LineageUnresolved {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return (
    typeof d.kind === 'string' &&
    d.kind.length >= 1 &&
    d.kind.length <= 32 &&
    typeof d.count === 'number' &&
    Number.isInteger(d.count) &&
    d.count >= 1
  );
}

export function isModelLineageTraceResponse(data: unknown): data is ModelLineageTraceResponse {
  if (!data || typeof data !== 'object') return false;
  const r = data as Record<string, unknown>;

  const validStages = ['draft', 'candidate', 'released', 'retired'];
  if (
    typeof r.modelVersionId !== 'string' ||
    r.modelVersionId.length === 0 ||
    typeof r.version !== 'string' ||
    r.version.length < 1 ||
    r.version.length > 64 ||
    typeof r.stage !== 'string' ||
    !validStages.includes(r.stage) ||
    typeof r.contentSha256 !== 'string' ||
    !HEX_64_REGEX.test(r.contentSha256) ||
    typeof r.fullyTraceable !== 'boolean' ||
    typeof r.traceabilityLimitedByScope !== 'boolean'
  ) {
    return false;
  }

  if (!Array.isArray(r.datasets) || !r.datasets.every(isLineageDatasetVersion)) {
    return false;
  }
  if (!Array.isArray(r.deployments) || !r.deployments.every(isLineageDeployment)) {
    return false;
  }
  if (!Array.isArray(r.missing) || !r.missing.every((m) => typeof m === 'string')) {
    return false;
  }
  if (!Array.isArray(r.unresolved) || !r.unresolved.every(isLineageUnresolved)) {
    return false;
  }
  if (!Array.isArray(r.detailedKinds) || !r.detailedKinds.every((k) => typeof k === 'string')) {
    return false;
  }
  if (!Array.isArray(r.countOnlyKinds) || !r.countOnlyKinds.every((k) => typeof k === 'string')) {
    return false;
  }

  if (
    r.producedByRunId !== undefined &&
    r.producedByRunId !== null &&
    typeof r.producedByRunId !== 'string'
  ) {
    return false;
  }

  if (r.truncated !== undefined && r.truncated !== null) {
    if (typeof r.truncated !== 'object' || Array.isArray(r.truncated)) return false;
    for (const val of Object.values(r.truncated as Record<string, unknown>)) {
      if (typeof val !== 'number' || !Number.isInteger(val)) return false;
    }
  }

  return true;
}

export function isModelVersionResponse(data: unknown): data is ModelVersionResponse {
  if (!data || typeof data !== 'object') return false;
  const r = data as Record<string, unknown>;
  return (
    typeof r.modelVersionId === 'string' &&
    r.modelVersionId.length > 0 &&
    typeof r.modelId === 'string' &&
    r.modelId.length > 0 &&
    typeof r.version === 'string' &&
    r.version.length >= 1 &&
    r.version.length <= 64 &&
    r.stage === 'draft' &&
    typeof r.contentSha256 === 'string' &&
    HEX_64_REGEX.test(r.contentSha256) &&
    typeof r.byteSize === 'number' &&
    Number.isInteger(r.byteSize) &&
    r.byteSize >= 0 &&
    typeof r.uri === 'string' &&
    r.uri.length >= 1 &&
    isValidIsoDateTime(r.createdAt)
  );
}

export function isRetentionPinResponse(data: unknown): data is RetentionPinResponse {
  if (!data || typeof data !== 'object') return false;
  const r = data as Record<string, unknown>;
  const validStages = ['draft', 'candidate', 'released', 'retired'];
  return (
    typeof r.modelVersionId === 'string' &&
    r.modelVersionId.length > 0 &&
    typeof r.modelId === 'string' &&
    r.modelId.length > 0 &&
    typeof r.version === 'string' &&
    r.version.length >= 1 &&
    r.version.length <= 64 &&
    typeof r.stage === 'string' &&
    validStages.includes(r.stage) &&
    isValidIsoDateTime(r.retentionPinnedUntil) &&
    typeof r.extended === 'boolean'
  );
}

export function isModelReleaseResponse(data: unknown): data is ModelReleaseResponse {
  if (!data || typeof data !== 'object') return false;
  const r = data as Record<string, unknown>;
  return (
    typeof r.modelVersionId === 'string' &&
    r.modelVersionId.length > 0 &&
    typeof r.modelId === 'string' &&
    r.modelId.length > 0 &&
    typeof r.version === 'string' &&
    r.version.length >= 1 &&
    r.version.length <= 64 &&
    r.stage === 'released' &&
    typeof r.contentSha256 === 'string' &&
    HEX_64_REGEX.test(r.contentSha256)
  );
}

export async function fetchModelLineage(
  projectId: string,
  modelId: string,
  version: string,
  signal?: AbortSignal
): Promise<ModelLineageTraceResponse> {
  if (!projectId || !modelId || !version) {
    throw new Error('프로젝트 ID, 모델 ID, 버전 정보를 확인하세요.');
  }

  const path = [projectId, modelId, version].map(encodeURIComponent);
  const result = await apiClient<ModelLineageTraceResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/lineage`,
    { method: 'GET', signal }
  );

  if (!isModelLineageTraceResponse(result)) {
    throw new Error('ModelLineageTraceResponse 응답 계약 불일치');
  }

  return result;
}

export async function registerModelVersion(
  projectId: string,
  modelId: string,
  payload: ModelVersionRegisterRequest,
  idempotencyKey?: string,
  signal?: AbortSignal
): Promise<ModelVersionResponse> {
  if (!projectId || !modelId) {
    throw new Error('프로젝트 ID와 모델 ID를 확인하세요.');
  }
  if (!payload || !payload.version || !payload.contentSha256) {
    throw new Error('버전 및 contentSha256(64자 16진수) 필드가 필수입니다.');
  }

  const key = idempotencyKey || generateIdempotencyKey('reg');
  const path = [projectId, modelId].map(encodeURIComponent);
  const result = await apiClient<ModelVersionResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      idempotencyKey: key,
      signal,
    }
  );

  if (!isModelVersionResponse(result)) {
    throw new Error('ModelVersionResponse 응답 계약 불일치');
  }

  return result;
}

export async function extendRetentionPin(
  projectId: string,
  modelId: string,
  version: string,
  payload: RetentionPinRequest,
  idempotencyKey?: string,
  signal?: AbortSignal
): Promise<RetentionPinResponse> {
  if (!projectId || !modelId || !version) {
    throw new Error('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
  }
  if (!payload || !isValidIsoDateTime(payload.until)) {
    throw new Error('유효한 ISO date-time 형식의 until 필드가 필수입니다.');
  }

  const key = idempotencyKey || generateIdempotencyKey('pin');
  const path = [projectId, modelId, version].map(encodeURIComponent);
  const result = await apiClient<RetentionPinResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/retention-pin`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      idempotencyKey: key,
      signal,
    }
  );

  if (!isRetentionPinResponse(result)) {
    throw new Error('RetentionPinResponse 응답 계약 불일치');
  }

  return result;
}

export async function releaseModelVersion(
  projectId: string,
  modelId: string,
  version: string,
  payload: ModelReleaseRequest,
  signal?: AbortSignal
): Promise<ModelReleaseResponse> {
  if (!projectId || !modelId || !version) {
    throw new Error('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
  }
  if (!payload || !payload.licensePolicy || !payload.classification) {
    throw new Error('licensePolicy 및 classification 필드가 필수입니다.');
  }

  const path = [projectId, modelId, version].map(encodeURIComponent);
  const result = await apiClient<ModelReleaseResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/release`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    }
  );

  if (!isModelReleaseResponse(result)) {
    throw new Error('ModelReleaseResponse 응답 계약 불일치');
  }

  return result;
}

export const modelRegistryObservation = {
  fetchModelLineage,
  registerModelVersion,
  extendRetentionPin,
  releaseModelVersion,
  isModelLineageTraceResponse,
  isModelVersionResponse,
  isRetentionPinResponse,
  isModelReleaseResponse,
  isValidIsoDateTime,
  generateIdempotencyKey,
};
