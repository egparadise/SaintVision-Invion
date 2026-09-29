import type { RunRecordResponse } from '@/contracts/run-record-response';
import type { RunRecordArtifactPageResponse, RunRecordArtifactPin } from '@/contracts/run-record-artifact-page-response';
import type { ArtifactPinVerificationResponse } from '@/contracts/artifact-pin-verification-response';
import type { ContextBundleResponse, ContextBundleItemSummary } from '@/contracts/context-bundle-response';
import { apiClient } from './client';

const RUN_RECORD_ALLOWED_KEYS = new Set([
  'attemptCount',
  'bundleHash',
  'bundleId',
  'componentVersions',
  'evidenceId',
  'finalState',
  'recordId',
  'runId',
  'sealedAt',
  'terminationReason',
  'workloadSpecSha256',
]);

const ARTIFACT_PAGE_ALLOWED_KEYS = new Set([
  'count',
  'items',
  'nextCursor',
  'recordId',
  'role',
  'runId',
]);

const ARTIFACT_PIN_ALLOWED_KEYS = new Set([
  'artifactId',
  'byteSize',
  'checksumSha256',
  'objectVersion',
  'role',
  'uri',
]);

const ARTIFACT_VERIFY_ALLOWED_KEYS = new Set([
  'artifactId',
  'pinnedChecksumSha256',
  'recordId',
  'runId',
  'verified',
]);

const CONTEXT_BUNDLE_ALLOWED_KEYS = new Set([
  'builtAt',
  'bundleHash',
  'bundleId',
  'componentVersions',
  'hashVerified',
  'itemCount',
  'items',
  'retrievalStrategy',
  'runId',
  'sealed',
  'tokenEstimate',
  'totalBytes',
]);

const CONTEXT_ITEM_ALLOWED_KEYS = new Set([
  'byteSize',
  'confidence',
  'contentHash',
  'itemId',
  'itemVersion',
  'kind',
  'ordinal',
  'redacted',
]);

const SHA256_HEX_RE = /^[0-9a-f]{64}$/;
const ARTIFACT_ROLE_RE = /^(diff|test_report|trace|log|model|dataset|other)$/;
const BUNDLE_STRATEGY_RE = /^(lexical|metadata|hybrid|explicit)$/;
const BUNDLE_ITEM_KIND_RE = /^(document|code|message|tool_output|summary)$/;

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

export function isRunRecordResponse(data: unknown): data is RunRecordResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!RUN_RECORD_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.recordId !== 'string' || !obj.recordId) return false;
  if (typeof obj.runId !== 'string' || !obj.runId) return false;
  if (typeof obj.finalState !== 'string' || obj.finalState.length < 1 || obj.finalState.length > 16) return false;
  if (typeof obj.terminationReason !== 'string' || obj.terminationReason.length < 1 || obj.terminationReason.length > 24) return false;
  if (typeof obj.workloadSpecSha256 !== 'string' || !SHA256_HEX_RE.test(obj.workloadSpecSha256)) return false;
  if (!obj.componentVersions || typeof obj.componentVersions !== 'object' || Array.isArray(obj.componentVersions)) return false;
  for (const v of Object.values(obj.componentVersions as Record<string, unknown>)) {
    if (typeof v !== 'string') return false;
  }
  if (typeof obj.attemptCount !== 'number' || !Number.isInteger(obj.attemptCount) || obj.attemptCount < 0) return false;
  if (!isValidIsoDateTime(obj.sealedAt as string)) return false;

  if (obj.bundleHash !== undefined && obj.bundleHash !== null) {
    if (typeof obj.bundleHash !== 'string' || !SHA256_HEX_RE.test(obj.bundleHash)) return false;
  }
  if (obj.bundleId !== undefined && obj.bundleId !== null) {
    if (typeof obj.bundleId !== 'string') return false;
  }
  if (obj.evidenceId !== undefined && obj.evidenceId !== null) {
    if (typeof obj.evidenceId !== 'string') return false;
  }

  return true;
}

export function isRunRecordArtifactPin(data: unknown): data is RunRecordArtifactPin {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!ARTIFACT_PIN_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.artifactId !== 'string' || !obj.artifactId) return false;
  if (typeof obj.role !== 'string' || !ARTIFACT_ROLE_RE.test(obj.role)) return false;
  if (typeof obj.uri !== 'string' || obj.uri.length < 1) return false;
  if (typeof obj.checksumSha256 !== 'string' || !SHA256_HEX_RE.test(obj.checksumSha256)) return false;
  if (typeof obj.byteSize !== 'number' || !Number.isInteger(obj.byteSize) || obj.byteSize < 0) return false;
  if (obj.objectVersion !== undefined && obj.objectVersion !== null && typeof obj.objectVersion !== 'string') return false;

  return true;
}

export function isRunRecordArtifactPageResponse(data: unknown): data is RunRecordArtifactPageResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!ARTIFACT_PAGE_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.recordId !== 'string' || !obj.recordId) return false;
  if (typeof obj.runId !== 'string' || !obj.runId) return false;
  if (typeof obj.count !== 'number' || !Number.isInteger(obj.count) || obj.count < 0 || obj.count > 200) return false;
  if (!Array.isArray(obj.items) || obj.items.length > 200) return false;
  for (const item of obj.items) {
    if (!isRunRecordArtifactPin(item)) return false;
  }
  if (obj.role !== undefined && obj.role !== null) {
    if (typeof obj.role !== 'string' || !ARTIFACT_ROLE_RE.test(obj.role)) return false;
  }
  if (obj.nextCursor !== undefined && obj.nextCursor !== null && typeof obj.nextCursor !== 'string') return false;

  return true;
}

export function isArtifactPinVerificationResponse(data: unknown): data is ArtifactPinVerificationResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!ARTIFACT_VERIFY_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.recordId !== 'string' || !obj.recordId) return false;
  if (typeof obj.runId !== 'string' || !obj.runId) return false;
  if (typeof obj.artifactId !== 'string' || !obj.artifactId) return false;
  if (typeof obj.verified !== 'boolean') return false;
  if (typeof obj.pinnedChecksumSha256 !== 'string' || !SHA256_HEX_RE.test(obj.pinnedChecksumSha256)) return false;

  return true;
}

export function isContextBundleItemSummary(data: unknown): data is ContextBundleItemSummary {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!CONTEXT_ITEM_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.ordinal !== 'number' || !Number.isInteger(obj.ordinal) || obj.ordinal < 0) return false;
  if (typeof obj.itemId !== 'string' || obj.itemId.length < 1 || obj.itemId.length > 255) return false;
  if (typeof obj.itemVersion !== 'number' || !Number.isInteger(obj.itemVersion) || obj.itemVersion < 1) return false;
  if (typeof obj.kind !== 'string' || !BUNDLE_ITEM_KIND_RE.test(obj.kind)) return false;
  if (typeof obj.contentHash !== 'string' || !SHA256_HEX_RE.test(obj.contentHash)) return false;
  if (typeof obj.byteSize !== 'number' || !Number.isInteger(obj.byteSize) || obj.byteSize < 0) return false;
  if (typeof obj.redacted !== 'boolean') return false;
  if (obj.confidence !== undefined && obj.confidence !== null) {
    if (typeof obj.confidence !== 'number' || obj.confidence < 0.0 || obj.confidence > 1.0) return false;
  }

  return true;
}

export function isContextBundleResponse(data: unknown): data is ContextBundleResponse {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  const obj = data as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!CONTEXT_BUNDLE_ALLOWED_KEYS.has(key)) return false;
  }

  if (typeof obj.bundleId !== 'string' || !obj.bundleId) return false;
  if (typeof obj.runId !== 'string' || !obj.runId) return false;
  if (typeof obj.bundleHash !== 'string' || !SHA256_HEX_RE.test(obj.bundleHash)) return false;
  if (typeof obj.hashVerified !== 'boolean') return false;
  if (typeof obj.sealed !== 'boolean') return false;
  if (typeof obj.itemCount !== 'number' || !Number.isInteger(obj.itemCount) || obj.itemCount < 0) return false;
  if (typeof obj.totalBytes !== 'number' || !Number.isInteger(obj.totalBytes) || obj.totalBytes < 0) return false;
  if (typeof obj.retrievalStrategy !== 'string' || !BUNDLE_STRATEGY_RE.test(obj.retrievalStrategy)) return false;
  if (!obj.componentVersions || typeof obj.componentVersions !== 'object' || Array.isArray(obj.componentVersions)) return false;
  for (const v of Object.values(obj.componentVersions as Record<string, unknown>)) {
    if (typeof v !== 'string') return false;
  }
  if (!isValidIsoDateTime(obj.builtAt as string)) return false;
  if (!Array.isArray(obj.items)) return false;
  for (const item of obj.items) {
    if (!isContextBundleItemSummary(item)) return false;
  }
  if (obj.tokenEstimate !== undefined && obj.tokenEstimate !== null) {
    if (typeof obj.tokenEstimate !== 'number' || !Number.isInteger(obj.tokenEstimate) || obj.tokenEstimate < 0) return false;
  }

  return true;
}

export interface FetchRunRecordArtifactsOptions {
  role?: string;
  limit?: number;
  cursor?: string;
}

export async function fetchRunRecord(
  projectId: string,
  runId: string,
  signal?: AbortSignal
): Promise<RunRecordResponse> {
  const path = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/record`;
  const result = await apiClient<unknown>(path, { signal });
  if (!isRunRecordResponse(result)) {
    throw new Error('RunRecordResponse 계약 규격 불일치: 필수 필드 누락 또는 임의 추가 필드 감지');
  }
  return result;
}

export async function fetchRunRecordArtifacts(
  projectId: string,
  runId: string,
  options?: FetchRunRecordArtifactsOptions,
  signal?: AbortSignal
): Promise<RunRecordArtifactPageResponse> {
  const queryParams = new URLSearchParams();
  if (options?.role) queryParams.set('role', options.role);
  if (options?.limit !== undefined) queryParams.set('limit', String(options.limit));
  if (options?.cursor) queryParams.set('cursor', options.cursor);
  const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';

  const path = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/record/artifacts${qs}`;
  const result = await apiClient<unknown>(path, { signal });
  if (!isRunRecordArtifactPageResponse(result)) {
    throw new Error('RunRecordArtifactPageResponse 계약 규격 불일치');
  }
  return result;
}

export async function verifyRunRecordArtifact(
  projectId: string,
  runId: string,
  artifactId: string,
  signal?: AbortSignal
): Promise<ArtifactPinVerificationResponse> {
  const path = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/record/artifacts/${encodeURIComponent(artifactId)}/verify`;
  const result = await apiClient<unknown>(path, { signal });
  if (!isArtifactPinVerificationResponse(result)) {
    throw new Error('ArtifactPinVerificationResponse 계약 규격 불일치');
  }
  return result;
}

export async function fetchContextBundle(
  projectId: string,
  runId: string,
  signal?: AbortSignal
): Promise<ContextBundleResponse> {
  const path = `/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/context-bundle`;
  const result = await apiClient<unknown>(path, { signal });
  if (!isContextBundleResponse(result)) {
    throw new Error('ContextBundleResponse 계약 규격 불일치: 필수 필드 누락 또는 임의 추가 필드 감지');
  }
  return result;
}