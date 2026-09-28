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
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

export function isValidIsoDateTime(value: unknown): boolean {
  if (typeof value !== 'string') return false;
  const match = ISO_DATE_TIME_REGEX.exec(value);
  if (!match) return false;
  const [, yStr, mStr, dStr, hStr, minStr, sStr] = match;
  const year = parseInt(yStr, 10);
  const month = parseInt(mStr, 10);
  const day = parseInt(dStr, 10);
  const hour = parseInt(hStr, 10);
  const min = parseInt(minStr, 10);
  const sec = parseInt(sStr, 10);
  if (month < 1 || month > 12) return false;
  if (hour < 0 || hour > 23 || min < 0 || min > 59 || sec < 0 || sec > 60) return false;
  const isLeap = (year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0));
  const daysInMonth = [31, isLeap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > daysInMonth[month - 1]) return false;
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

const LINEAGE_DATASET_VERSION_KEYS = new Set([
  'datasetVersionId',
  'version',
  'contentSha256',
  'uri',
]);

export function isLineageDatasetVersion(data: unknown): data is LineageDatasetVersion {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const d = data as Record<string, unknown>;
  const keys = Object.keys(d);
  if (keys.length !== LINEAGE_DATASET_VERSION_KEYS.size) return false;
  if (!keys.every((k) => LINEAGE_DATASET_VERSION_KEYS.has(k))) return false;

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

const LINEAGE_DEPLOYMENT_KEYS = new Set([
  'deploymentId',
  'environment',
  'status',
  'deployedDigest',
  'deployedAt',
  'approvalId',
  'imageId',
  'supersededAt',
]);

export function isLineageDeployment(data: unknown): data is LineageDeployment {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const d = data as Record<string, unknown>;
  const keys = Object.keys(d);
  if (!keys.every((k) => LINEAGE_DEPLOYMENT_KEYS.has(k))) return false;

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

const LINEAGE_UNRESOLVED_KEYS = new Set(['kind', 'count']);

export function isLineageUnresolved(data: unknown): data is LineageUnresolved {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const d = data as Record<string, unknown>;
  const keys = Object.keys(d);
  if (keys.length !== LINEAGE_UNRESOLVED_KEYS.size) return false;
  if (!keys.every((k) => LINEAGE_UNRESOLVED_KEYS.has(k))) return false;

  return (
    typeof d.kind === 'string' &&
    d.kind.length >= 1 &&
    d.kind.length <= 32 &&
    typeof d.count === 'number' &&
    Number.isInteger(d.count) &&
    d.count >= 1
  );
}

const MODEL_LINEAGE_TRACE_RESPONSE_KEYS = new Set([
  'modelVersionId',
  'version',
  'stage',
  'contentSha256',
  'datasets',
  'deployments',
  'missing',
  'unresolved',
  'fullyTraceable',
  'traceabilityLimitedByScope',
  'detailedKinds',
  'countOnlyKinds',
  'producedByRunId',
  'truncated',
]);

export function isModelLineageTraceResponse(data: unknown): data is ModelLineageTraceResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const r = data as Record<string, unknown>;
  const keys = Object.keys(r);
  if (!keys.every((k) => MODEL_LINEAGE_TRACE_RESPONSE_KEYS.has(k))) return false;

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

  // Collection bounds: datasets max 200, deployments max 200, missing max 16, unresolved max 16, detailedKinds max 16, countOnlyKinds max 16
  if (!Array.isArray(r.datasets) || r.datasets.length > 200 || !r.datasets.every(isLineageDatasetVersion)) {
    return false;
  }
  if (!Array.isArray(r.deployments) || r.deployments.length > 200 || !r.deployments.every(isLineageDeployment)) {
    return false;
  }
  if (!Array.isArray(r.missing) || r.missing.length > 16 || !r.missing.every((m) => typeof m === 'string')) {
    return false;
  }
  if (!Array.isArray(r.unresolved) || r.unresolved.length > 16 || !r.unresolved.every(isLineageUnresolved)) {
    return false;
  }
  if (!Array.isArray(r.detailedKinds) || r.detailedKinds.length > 16 || !r.detailedKinds.every((k) => typeof k === 'string')) {
    return false;
  }
  if (!Array.isArray(r.countOnlyKinds) || r.countOnlyKinds.length > 16 || !r.countOnlyKinds.every((k) => typeof k === 'string')) {
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

const MODEL_VERSION_RESPONSE_KEYS = new Set([
  'modelVersionId',
  'modelId',
  'version',
  'stage',
  'contentSha256',
  'byteSize',
  'uri',
  'createdAt',
]);

export function isModelVersionResponse(data: unknown): data is ModelVersionResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const r = data as Record<string, unknown>;
  const keys = Object.keys(r);
  if (keys.length !== MODEL_VERSION_RESPONSE_KEYS.size) return false;
  if (!keys.every((k) => MODEL_VERSION_RESPONSE_KEYS.has(k))) return false;

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

const RETENTION_PIN_RESPONSE_KEYS = new Set([
  'modelVersionId',
  'modelId',
  'version',
  'stage',
  'retentionPinnedUntil',
  'extended',
]);

export function isRetentionPinResponse(data: unknown): data is RetentionPinResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const r = data as Record<string, unknown>;
  const keys = Object.keys(r);
  if (keys.length !== RETENTION_PIN_RESPONSE_KEYS.size) return false;
  if (!keys.every((k) => RETENTION_PIN_RESPONSE_KEYS.has(k))) return false;

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

const MODEL_RELEASE_RESPONSE_KEYS = new Set([
  'modelVersionId',
  'modelId',
  'version',
  'stage',
  'contentSha256',
]);

export function isModelReleaseResponse(data: unknown): data is ModelReleaseResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const r = data as Record<string, unknown>;
  const keys = Object.keys(r);
  if (keys.length !== MODEL_RELEASE_RESPONSE_KEYS.size) return false;
  if (!keys.every((k) => MODEL_RELEASE_RESPONSE_KEYS.has(k))) return false;

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
  options?: { signal?: AbortSignal; idempotencyKey?: string }
): Promise<ModelVersionResponse> {
  if (!projectId || !modelId) {
    throw new Error('프로젝트 ID와 모델 ID를 확인하세요.');
  }
  if (!payload || !payload.version || !payload.contentSha256) {
    throw new Error('버전 및 contentSha256(64자 16진수) 필드가 필수입니다.');
  }

  const key = options?.idempotencyKey || generateIdempotencyKey('reg');
  const path = [projectId, modelId].map(encodeURIComponent);
  const result = await apiClient<ModelVersionResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      idempotencyKey: key,
      signal: options?.signal,
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
  options?: { signal?: AbortSignal; idempotencyKey?: string }
): Promise<RetentionPinResponse> {
  if (!projectId || !modelId || !version) {
    throw new Error('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
  }
  if (!payload || !isValidIsoDateTime(payload.until)) {
    throw new Error('유효한 ISO date-time 형식의 until 필드가 필수입니다.');
  }

  const key = options?.idempotencyKey || generateIdempotencyKey('pin');
  const path = [projectId, modelId, version].map(encodeURIComponent);
  const result = await apiClient<RetentionPinResponse>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/retention-pin`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
      idempotencyKey: key,
      signal: options?.signal,
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
  options?: { signal?: AbortSignal }
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
      signal: options?.signal,
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
