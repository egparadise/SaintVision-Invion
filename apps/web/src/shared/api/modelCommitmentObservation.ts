import { apiClient } from './client';
import type { ModelCommitObservation } from '@/contracts/types';

const PROJECT_ID_PATTERN = /^prj_[0-9A-HJKMNP-TV-Z]{26}$/;
const MODEL_ID_PATTERN = /^mdl_[0-9A-HJKMNP-TV-Z]{26}$/;
const RUN_ID_PATTERN = /^run_[0-9A-HJKMNP-TV-Z]{26}$/;
const VERSION_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const MANIFEST_HASH_PATTERN = /^[0-9a-f]{64}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ISO_DATETIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

/**
 * Strict runtime schema guard for ModelCommitObservation.
 * Validates all required fields, patterns, ranges, enums, and const values
 * against contracts/v1alpha1/core.schema.json.
 */
export function isModelCommitObservation(value: unknown): value is ModelCommitObservation {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;

  // Check required ID patterns & versions
  if (typeof o.projectId !== 'string' || !PROJECT_ID_PATTERN.test(o.projectId)) return false;
  if (typeof o.modelId !== 'string' || !MODEL_ID_PATTERN.test(o.modelId)) return false;
  if (typeof o.version !== 'string' || !VERSION_PATTERN.test(o.version)) return false;
  if (typeof o.manifestHash !== 'string' || !MANIFEST_HASH_PATTERN.test(o.manifestHash)) return false;
  if (typeof o.sourceRunId !== 'string' || !RUN_ID_PATTERN.test(o.sourceRunId)) return false;
  if (typeof o.committedAt !== 'string' || !ISO_DATETIME_PATTERN.test(o.committedAt)) return false;
  if (typeof o.commitRecoveryEpoch !== 'string' || !UUID_PATTERN.test(o.commitRecoveryEpoch)) return false;
  if (typeof o.format !== 'string' || o.format.length < 1 || o.format.length > 64) return false;
  if (typeof o.totalBytes !== 'number' || !Number.isInteger(o.totalBytes) || o.totalBytes < 1 || o.totalBytes > 1099511627776) return false;
  if (typeof o.shardCount !== 'number' || !Number.isInteger(o.shardCount) || o.shardCount < 1 || o.shardCount > 1024) return false;
  if (typeof o.licensePolicy !== 'string' || o.licensePolicy.length < 1 || o.licensePolicy.length > 200) return false;
  if (typeof o.classification !== 'string' || !['public', 'internal', 'restricted'].includes(o.classification)) return false;

  // Strict const invariants
  if (o.committed !== true) return false;
  if (o.currentAvailability !== 'unknown') return false;
  if (o.requiresExecutionRevalidation !== true) return false;

  return true;
}

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
  const result = await apiClient<unknown>(
    `/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/commitment`,
    { method: 'GET', signal }
  );

  if (
    !isModelCommitObservation(result) ||
    result.projectId !== p ||
    result.modelId !== m ||
    result.version !== v
  ) {
    throw new Error('ModelCommitObservation 응답 계약 불일치');
  }

  return result;
}
