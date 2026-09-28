import { apiClient } from './client';
import type { ModelCommitObservation } from '@/contracts/types';

const PROJECT_ID_PATTERN = /^prj_[0-9A-HJKMNP-TV-Z]{26}$/;
const MODEL_ID_PATTERN = /^mdl_[0-9A-HJKMNP-TV-Z]{26}$/;
const RUN_ID_PATTERN = /^run_[0-9A-HJKMNP-TV-Z]{26}$/;
const VERSION_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const MANIFEST_HASH_PATTERN = /^[0-9a-f]{64}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MODEL_COMMIT_OBSERVATION_KEYS = new Set([
  'projectId',
  'modelId',
  'version',
  'manifestHash',
  'sourceRunId',
  'committedAt',
  'commitRecoveryEpoch',
  'format',
  'totalBytes',
  'shardCount',
  'licensePolicy',
  'classification',
  'committed',
  'currentAvailability',
  'requiresExecutionRevalidation',
]);

/**
 * Validate strict RFC 3339 date-time format including calendar validity (leap year, days in month).
 */
export function isValidIsoDateTime(val: string): boolean {
  if (typeof val !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(val);
  if (!match) return false;

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const minute = parseInt(match[5], 10);
  const second = parseInt(match[6], 10);

  if (month < 1 || month > 12) return false;
  if (day < 1 || day > 31) return false;
  if (hour < 0 || hour > 23) return false;
  if (minute < 0 || minute > 59) return false;
  if (second < 0 || second > 60) return false;

  const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  const daysInMonth = [31, isLeapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day > daysInMonth[month - 1]) return false;

  const tzSign = match[8];
  if (tzSign && match[9] && match[10]) {
    const tzHour = parseInt(match[9], 10);
    const tzMin = parseInt(match[10], 10);
    if (tzHour < 0 || tzHour > 23 || tzMin < 0 || tzMin > 59) return false;
  }

  const d = new Date(val);
  return !isNaN(d.getTime());
}

/**
 * Strict runtime schema guard for ModelCommitObservation.
 * Validates all required fields, patterns, ranges, enums, and const values
 * against contracts/v1alpha1/core.schema.json, strictly enforcing additionalProperties: false.
 */
export function isModelCommitObservation(value: unknown): value is ModelCommitObservation {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;

  // additionalProperties: false check (exact 15 allowed keys)
  const keys = Object.keys(o);
  if (keys.length !== MODEL_COMMIT_OBSERVATION_KEYS.size) return false;
  if (!keys.every((key) => MODEL_COMMIT_OBSERVATION_KEYS.has(key))) return false;

  // Check required ID patterns & versions
  if (typeof o.projectId !== 'string' || !PROJECT_ID_PATTERN.test(o.projectId)) return false;
  if (typeof o.modelId !== 'string' || !MODEL_ID_PATTERN.test(o.modelId)) return false;
  if (typeof o.version !== 'string' || !VERSION_PATTERN.test(o.version)) return false;
  if (typeof o.manifestHash !== 'string' || !MANIFEST_HASH_PATTERN.test(o.manifestHash)) return false;
  if (typeof o.sourceRunId !== 'string' || !RUN_ID_PATTERN.test(o.sourceRunId)) return false;
  if (typeof o.committedAt !== 'string' || !isValidIsoDateTime(o.committedAt)) return false;
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
